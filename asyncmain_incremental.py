import asyncio
import contextlib
import httpx
import json
import csv
import logging
import tempfile
from datetime import datetime, timedelta, timezone
import os
import glob
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("asyncmain_incremental")

# Refuse to overwrite data/quarterly_reports.csv unless the new fetch has at
# least this fraction of the rows the existing file already holds. See
# docs/pipeline-audit.md issue 4.
MIN_REPORT_COVERAGE = 0.9

os.makedirs('data/stock/adjusted', exist_ok=True)
os.makedirs('data/stock/unadjusted', exist_ok=True)
os.makedirs('data/index/adjusted', exist_ok=True)
os.makedirs('data/index/unadjusted', exist_ok=True)
os.makedirs('data/subindices/adjusted', exist_ok=True)
os.makedirs('data/subindices/unadjusted', exist_ok=True)
os.makedirs('data', exist_ok=True)  # For quarterly reports

# Separate semaphores for adjusted and unadjusted
semaphore_adjusted = asyncio.Semaphore(15)  # Max 15 concurrent requests for adjusted
semaphore_unadjusted = asyncio.Semaphore(15)  # Max 15 concurrent requests for unadjusted
semaphore_reports = asyncio.Semaphore(10)  # Max 10 concurrent requests for quarterly reports

# Sector ID to Name mapping
SECTOR_MAPPING = {
    1: "BANKING",
    2: "DEVBANK",
    3: "FINANCE",
    4: "HOTELS",
    5: "HYDRO",
    6: "INVESTMENT",
    7: "LIFEINSU",
    8: "MANUFACTURE",
    9: "MICROFINANCE",
    10: "NONLIFEINSU",
    11: "OTHERS",
    12: "TRDIND",
}


# --------------------------------------------------------------------------- #
# Write helpers                                                                #
# --------------------------------------------------------------------------- #


def atomic_write_csv(path, write_fn):
    """Write ``path`` via a temp file in the same directory, then os.replace().

    The previous code truncated the destination in place, so an OOM-kill, a
    Ctrl-C, or a laptop lid-close mid-write left a half-written CSV committed as
    the latest data. os.replace() is atomic on both POSIX and Windows, so a
    reader ever only sees the old file or the new one.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    os.close(fd)
    try:
        write_fn(tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        # Never leave the scratch file behind on failure.
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise


def epoch_ms_to_date(epoch_ms):
    """Epoch-ms -> YYYY-MM-DD in UTC.

    The API emits bars at exactly midnight UTC. The old code used
    datetime.fromtimestamp() with no tz, which resolves against machine-local
    time and therefore shifts every row back a day on any negative-offset host.
    """
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def get_last_fetched_date(symbol_name, folder_type, folder):
    """
    Robustly find the last fetched date from existing CSV files.
    Returns the last date as a datetime object, or None if no file exists.
    """
    safe_symbol_name = symbol_name.replace('/', '_')
    
    # Find all matching CSV files for this symbol
    pattern = f"data/{folder_type}/{folder}/{safe_symbol_name}_*.csv"
    matching_files = glob.glob(pattern)
    
    if not matching_files:
        return None
    
    # If multiple files exist (shouldn't happen, but being robust), use the most recent
    matching_files.sort(reverse=True)
    csv_file = matching_files[0]
    
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file)
        
        if df.empty or 'time' not in df.columns:
            return None
        
        # Get the last row's date
        last_date_str = df['time'].iloc[-1]
        
        # Parse the date (format: YYYY-MM-DD)
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        
        return last_date
    except Exception as e:
        print(f"  Warning: Could not read last date from {csv_file}: {e}")
        return None


def get_existing_file_path(symbol_name, folder_type, folder):
    """
    Get the path of the existing CSV file for this symbol.
    Uses a static filename format without date.
    """
    safe_symbol_name = symbol_name.replace('/', '_')
    file_path = f"data/{folder_type}/{folder}/{safe_symbol_name}_{folder}.csv"
    
    if os.path.exists(file_path):
        return file_path
    
    # Fallback: check for old date-based files and migrate them
    pattern = f"data/{folder_type}/{folder}/{safe_symbol_name}_*.csv"
    matching_files = glob.glob(pattern)
    
    if matching_files:
        matching_files.sort(reverse=True)
        old_file = matching_files[0]
        # Rename old file to new format. Guarded: on Windows an open handle (or
        # an antivirus/indexer lock) raises PermissionError, and an unguarded
        # raise here used to propagate out of asyncio.gather and cancel every
        # other in-flight task.
        try:
            os.replace(old_file, file_path)
            return file_path
        except OSError as exc:
            log.warning("  Could not rename %s -> %s (%s)", old_file, file_path, exc)
            return None

    return None


async def fetch_and_save_incremental(symbol_name, folder_type, folder, is_adjust):
    """
    Fetch and save data incrementally - only fetch new data from the last fetched date.
    folder_type: 'stock', 'index', or 'subindices'
    folder: 'adjusted' or 'unadjusted'
    """
    semaphore = semaphore_adjusted if is_adjust else semaphore_unadjusted
    async with semaphore:
        safe_symbol_name = symbol_name.replace('/', '_')
        
        # Get the last fetched date
        last_fetched_date = get_last_fetched_date(symbol_name, folder_type, folder)
        existing_file = get_existing_file_path(symbol_name, folder_type, folder)
        
        if last_fetched_date:
            # Calculate the "from" timestamp (day after last fetched date).
            # Anchor to UTC midnight to match the API's bar timestamps; the old
            # naive local-midnight .timestamp() landed mid-day in negative-offset
            # zones and silently skipped a trading day on every run.
            from_date = last_fetched_date + timedelta(days=1)
            from_timestamp = int(
                from_date.replace(tzinfo=timezone.utc).timestamp() * 1000
            )
            
            # Check if we're already up to date
            # Allow fetching if from_date is today - data might be available
            if from_date.date() > datetime.now().date():
                print(f"✓ {symbol_name} ({folder_type}/{folder}) - Already up to date (last: {last_fetched_date.strftime('%Y-%m-%d')})")
                return
            
            print(f"  {symbol_name} ({folder_type}/{folder}) - Fetching from {from_date.strftime('%Y-%m-%d')} onwards...")
            # Don't use 'to' parameter - let API return all available data from 'from' date onwards
            url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={symbol_name}&resolution=1D&from={from_timestamp}&isAdjust={'true' if is_adjust else 'false'}"
        else:
            # No existing file, fetch all data
            print(f"  {symbol_name} ({folder_type}/{folder}) - No existing data, fetching all...")
            url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={symbol_name}&resolution=1D&countback=0&isAdjust={'true' if is_adjust else 'false'}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                data = json.loads(response.content.decode('utf-8'))
                
                if data.get('success') == True and data.get('code') == 'SUCCESS' and data.get("data"):
                    new_data_count = len(data["data"])
                    
                    if new_data_count == 0:
                        print(f"✓ {symbol_name} ({folder_type}/{folder}) - No new data available")
                        return
                    
                    # Use static filename without date
                    file_path = f"data/{folder_type}/{folder}/{safe_symbol_name}_{folder}.csv"
                    
                    # Determine category based on folder_type
                    if folder_type == 'stock':
                        category = 'stock'
                    elif folder_type == 'index':
                        category = 'index'
                    elif folder_type == 'subindices':
                        category = 'subindex'
                    else:
                        category = 'unknown'
                    
                    if existing_file and last_fetched_date:
                        # Append to existing file (no renaming!)
                        # Read existing data
                        existing_df = pd.read_csv(existing_file)
                        
                        # Prepare new rows
                        new_rows = []
                        for row in data["data"]:
                            row_copy = row.copy()
                            row_copy["time"] = epoch_ms_to_date(row_copy["time"])
                            row_copy["category"] = category
                            row_copy["open"] = float(row_copy["open"])
                            row_copy["close"] = float(row_copy["close"])
                            row_copy["high"] = float(row_copy["high"])
                            row_copy["low"] = float(row_copy["low"])
                            row_copy["volume"] = int(row_copy["volume"])
                            new_rows.append(row_copy)
                        
                        # Create DataFrame from new rows
                        new_df = pd.DataFrame(new_rows)
                        
                        # Combine existing and new data
                        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                        
                        # Remove duplicates based on 'time' column (keep last occurrence)
                        combined_df = combined_df.drop_duplicates(subset=['time'], keep='last')
                        
                        # Sort by date
                        combined_df['time_sort'] = pd.to_datetime(combined_df['time'])
                        combined_df = combined_df.sort_values('time_sort')
                        combined_df = combined_df.drop(columns=['time_sort'])
                        
                        # Atomically replace the file. NOTE: this rewrites the whole CSV to add one
                        # row, which under Git LFS makes the entire file a new blob
                        # (~60 MB uploaded per run across ~1,073 files). That is
                        # the root cause of the 7.1 GB LFS store; see
                        # docs/pipeline-audit.md issue 2.
                        atomic_write_csv(file_path, lambda p: combined_df.to_csv(p, index=False))
                        
                        print(f"✓ {symbol_name} ({folder_type}/{folder}) - Added {new_data_count} new rows (total: {len(combined_df)})")
                    else:
                        # Create new file with static name (atomically)
                        fieldnames = list(data["data"][0].keys()) + ['category']

                        def _write_new(p):
                            with open(p, 'w', newline='', encoding='utf-8') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                for row in data["data"]:
                                    row_copy = row.copy()
                                    row_copy["time"] = epoch_ms_to_date(row_copy["time"])
                                    row_copy["category"] = category
                                    row_copy["open"] = float(row_copy["open"])
                                    row_copy["close"] = float(row_copy["close"])
                                    row_copy["high"] = float(row_copy["high"])
                                    row_copy["low"] = float(row_copy["low"])
                                    row_copy["volume"] = int(row_copy["volume"])
                                    writer.writerow(row_copy)

                        atomic_write_csv(file_path, _write_new)
                        print(f"✓ {symbol_name} ({folder_type}/{folder}) - Created new file with {new_data_count} rows")
                else:
                    print(f"✗ {symbol_name} ({folder_type}/{folder}) - No data from API")
        except Exception as e:
            print(f"✗ {symbol_name} ({folder_type}/{folder}) - Error: {e}")
        
        await asyncio.sleep(0.1)  # Small delay between requests


async def fetch_quarterly_report(client, stock_id, stock_name):
    """
    Fetch quarterly report for a single stock.
    Returns list of report dictionaries with stock_name and sector mapped.
    """
    async with semaphore_reports:
        url = f"https://chukul.com/api/stock/{stock_id}/report/"
        try:
            response = await client.get(url, timeout=30.0)
            if response.status_code == 200:
                reports = response.json()
                if reports and isinstance(reports, list):
                    # Add stock_name and map sector_id to sector name
                    for report in reports:
                        report["stock_name"] = stock_name
                        sector_id = report.get("sector_id")
                        report["sector"] = SECTOR_MAPPING.get(sector_id, f"UNKNOWN_{sector_id}")
                    return reports
                return []
            log.warning("  %s (%s): report endpoint returned HTTP %s", stock_name, stock_id, response.status_code)
            return []
        except Exception as exc:
            # The old bare `pass` made a rate-limit, a DNS failure and a genuine
            # outage indistinguishable from "this stock has no reports" -- which
            # is what allowed a partial fetch to be committed as a good one.
            log.warning("  %s (%s): report fetch failed (%s: %s)", stock_name, stock_id, type(exc).__name__, exc)
            return []


async def fetch_all_quarterly_reports():
    """
    Fetch quarterly reports for all active stocks and save to CSV.
    Excludes sectors 13, 14, 15 (mutual funds, promoter shares, debentures).
    """
    print("\n" + "=" * 80)
    print("FETCHING QUARTERLY REPORTS")
    print("=" * 80)
    
    # Fetch stock list
    stock_list_url = "https://chukul.com/api/stock/"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(stock_list_url)
            stocks = response.json()
            
            if not stocks:
                print("✗ Failed to fetch stock list")
                return
            
            print(f"Found {len(stocks)} stocks")
            
            # Filter stocks
            EXCLUDED_SECTORS = {13, 14, 15}
            active_stocks = [
                s for s in stocks 
                if not s.get("is_delisted", False) 
                and s.get("sector") not in EXCLUDED_SECTORS
            ]
            
            excluded_count = len(stocks) - len(active_stocks)
            print(f"Active stocks (excluding delisted & sectors 13/14/15): {len(active_stocks)}")
            print(f"Excluded: {excluded_count} (debentures, bonds, promoter shares, mutual funds)")
            print("\nFetching quarterly reports...")
            
            # Fetch reports for all stocks
            tasks = [
                fetch_quarterly_report(client, stock["id"], stock["name"])
                for stock in active_stocks
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results, counting failures explicitly so the coverage
            # check below has something real to assert against.
            all_reports = []
            stocks_with_data = 0
            fetch_errors = 0
            for reports in results:
                if isinstance(reports, BaseException):
                    fetch_errors += 1
                    log.warning("  Report task raised: %s: %s", type(reports).__name__, reports)
                    continue
                if reports:
                    stocks_with_data += 1
                    all_reports.extend(reports)

            # Filter out empty reports
            all_reports = [r for r in all_reports if r.get("fiscal_year")]

            print(f"\nStocks with report data: {stocks_with_data}")
            print(f"Report tasks that errored: {fetch_errors}")
            print(f"Total quarterly reports collected: {len(all_reports)}")

            if not all_reports:
                print("No reports found. Leaving the existing quarterly_reports.csv untouched.")
                return

            # ---- Refuse to shrink the dataset ---------------------------- #
            # quarterly_reports.csv is a single file with no per-record redundancy,
            # so overwriting it with a partial fetch is unrecoverable. Previously
            # a soft block from Chukul (HTTP 200 + empty body for most stocks)
            # silently replaced 6,618 rows with whatever survived.
            previous_count = 0
            output_file = "data/quarterly_reports.csv"
            if os.path.exists(output_file):
                try:
                    with open(output_file, newline='', encoding='utf-8') as f:
                        previous_count = max(0, sum(1 for _ in f) - 1)
                except OSError as exc:
                    log.warning("Could not count existing rows in %s (%s)", output_file, exc)

            min_expected = int(previous_count * MIN_REPORT_COVERAGE)
            if previous_count and len(all_reports) < min_expected:
                print(
                    f"ABORT: collected {len(all_reports)} reports but {output_file} already holds "
                    f"{previous_count}. Refusing to overwrite with less than "
                    f"{MIN_REPORT_COVERAGE:.0%} ({min_expected}) of the existing rows. "
                    f"This usually means the upstream API failed part-way -- rerun, and if it "
                    f"persists check the warnings above."
                )
                return
            
            # Define columns for CSV (ML-relevant only)
            columns = [
                "stock_id", "stock_name", "symbol", "sector", "fiscal_year", "quarter",
                "eps", "dps", "net_worth", "roe", "roa", "pe_ratio", "paidup_capital",
                "reserve_surplus", "total_equity", "total_assets", "deposit", "investments",
                "total_currentassets", "total_currentliabilities", "operating_income",
                "operating_expenses", "administrative_expenses", "depreciation",
                "financial_expenses", "net_profit", "growth_rate", "close"
            ]
            
            # Sort reports
            all_reports.sort(key=lambda x: (
                x.get("stock_id", 0),
                x.get("fiscal_year", ""),
                x.get("quarter", "")
            ))
            
            # Save to CSV (atomically)
            def _write_reports(p):
                with open(p, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(all_reports)

            atomic_write_csv(output_file, _write_reports)
            
            print(f"✓ Saved {len(all_reports)} quarterly reports to {output_file}")
            
    except Exception as e:
        print(f"✗ Error fetching quarterly reports: {e}")


async def load_sector_data():
    """
    Load sector data from API, save to sector.json, and return data.
    Falls back to local sector.json if API fails.
    """
    api_url = "https://chukul.com/api/sector/"
    
    try:
        print("Fetching sector data from API...")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(api_url)
            
            if response.status_code == 200:
                stock_data = response.json()
                
                # Validate that we got proper data
                if isinstance(stock_data, list) and len(stock_data) > 0:
                    # Save to sector.json for future fallback
                    with open('sector.json', 'w', encoding='utf-8') as f:
                        json.dump(stock_data, f, indent=2, ensure_ascii=False)
                    
                    print(f"✓ Fetched {len(stock_data)} sectors from API and saved to sector.json")
                    return stock_data
                else:
                    print("⚠ API response format unexpected, falling back to local file...")
                    raise ValueError("Invalid API response format")
            else:
                print(f"⚠ API returned status {response.status_code}, falling back to local file...")
                raise ValueError(f"API returned status {response.status_code}")
                
    except Exception as e:
        print(f"⚠ Failed to fetch from API ({e}), falling back to local sector.json...")
        
        # Fallback to local file
        try:
            with open('sector.json', 'r', encoding='utf-8') as f:
                stock_data = json.load(f)
            print(f"✓ Loaded {len(stock_data)} sectors from local sector.json")
            return stock_data
        except Exception as fallback_error:
            print(f"✗ Failed to load local sector.json: {fallback_error}")
            raise


async def main():
    print("=" * 80)
    print("INCREMENTAL DATA FETCH - Only fetching new data from last update")
    print("=" * 80)
    print()

    # Load sector data from API (with fallback to local file)
    stock_data = await load_sector_data()
    print()

    # Define indices and subindices
    indices = ["NEPSE", "FLOAT", "SENSITIVE", "SENFLOAT"]
    subindices = ["BANKING", "DEVBANK", "FINANCE", "HOTELS", "HYDROPOWER",
                  "INVESTMENT", "LIFEINSU", "MANUFACTURE", "MICROFINANCE",
                  "MUTUAL", "NONLIFEINSU", "OTHERS", "TRADING"]

    tasks = []

    print("Preparing tasks...")

    # Add tasks for indices
    for index in indices:
        tasks.append(fetch_and_save_incremental(index, "index", "adjusted", True))
        tasks.append(fetch_and_save_incremental(index, "index", "unadjusted", False))

    # Add tasks for subindices
    for subindex in subindices:
        tasks.append(fetch_and_save_incremental(subindex, "subindices", "adjusted", True))
        tasks.append(fetch_and_save_incremental(subindex, "subindices", "unadjusted", False))

    # Add tasks for stocks. One malformed symbol here used to raise out of
    # gather and cancel every other in-flight download, so it is guarded and the
    # bad entry is reported rather than fatal.
    if isinstance(stock_data, list) and len(stock_data) > 0:
        skipped = 0
        for j in stock_data:
            for k in j.get("stocks", []) or []:
                if not isinstance(k, dict):
                    skipped += 1
                    continue
                symbol = k.get("symbol")
                if k.get("can_trade") is True and isinstance(symbol, str) and symbol:
                    tasks.append(fetch_and_save_incremental(symbol, "stock", "adjusted", True))
                    tasks.append(fetch_and_save_incremental(symbol, "stock", "unadjusted", False))
                else:
                    skipped += 1
        if skipped:
            print(f"Skipped {skipped} malformed or non-tradable universe entries")

    print(f"Created {len(tasks)} tasks. Starting incremental downloads...")
    print()

    # return_exceptions=True so a single bad symbol cannot cancel every other
    # in-flight download and leave truncated CSVs behind.
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, BaseException)]
    if failures:
        print(f"WARNING: {len(failures)} of {len(tasks)} download tasks raised.")
        for r in failures[:10]:
            print(f"  {type(r).__name__}: {r}")
    print()
    print("=" * 80)
    print("Stock/Index/Subindex downloads complete!")
    print("=" * 80)
    
    # Fetch quarterly reports
    await fetch_all_quarterly_reports()
    
    print()
    print("=" * 80)
    print("ALL DATA FETCHING COMPLETE!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
