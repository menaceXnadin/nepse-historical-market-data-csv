"""
Scrape quarterly reports for all NEPSE stocks from Chukul API.
Saves all data to a single CSV file with stock name and symbol.
"""

import asyncio
import aiohttp
import csv
import json
from datetime import datetime
from pathlib import Path

STOCK_LIST_URL = "https://chukul.com/api/stock/"
REPORT_URL_TEMPLATE = "https://chukul.com/api/stock/{stock_id}/report/"
OUTPUT_FILE = Path(__file__).parent / "data" / "quarterly_reports.csv"

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

# Define all possible columns from the report API
REPORT_COLUMNS = [
    "stock_id",
    "stock_name",
    "symbol",
    "sector",
    "fiscal_year",
    "quarter",
    "eps",
    "eps_a",
    "dps",
    "net_worth",
    "roe",
    "roa",
    "pe_ratio",
    "peg_value",
    "paidup_capital",
    "reserve_surplus",
    "total_equity",
    "total_assets",
    "loansandlong_termliabilities",
    "property_plantandequipment",
    "deposit",
    "investments",
    "total_currentassets",
    "total_currentliabilities",
    "net_currentassets",
    "other_assets",
    "operating_income",
    "income_from_sales_of_electricity",
    "income_fromothersources",
    "operating_expenses",
    "project_operatingexpenses",
    "administrative_expenses",
    "other_operatingexpenses",
    "depreciation",
    "financial_expenses",
    "net_profit",
    "prev_quarter_profit",
    "growth_rate",
    "gram_value",
    "discount_rate",
    "close",
    "core_capital",
    "public_shares",
    "share_registar",
    "is_delisted",
    "is_merged",
    "listed_date",
    "expired_date",
    "mega_watt_capacity",
    "mega_watt_per_cost",
    "sister_holding",
]


async def fetch_json(session: aiohttp.ClientSession, url: str) -> dict | list | None:
    """Fetch JSON data from a URL."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"  Error {response.status} for {url}")
                return None
    except Exception as e:
        print(f"  Exception fetching {url}: {e}")
        return None


async def fetch_stock_list(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch the list of all stocks."""
    print("Fetching stock list...")
    stocks = await fetch_json(session, STOCK_LIST_URL)
    if stocks:
        print(f"Found {len(stocks)} stocks")
        return stocks
    return []


async def fetch_report(
    session: aiohttp.ClientSession, 
    stock_id: int, 
    stock_name: str,
    semaphore: asyncio.Semaphore
) -> list[dict]:
    """Fetch quarterly reports for a single stock."""
    async with semaphore:
        url = REPORT_URL_TEMPLATE.format(stock_id=stock_id)
        reports = await fetch_json(session, url)
        
        if reports and isinstance(reports, list):
            # Add stock_name and map sector_id to sector name
            for report in reports:
                report["stock_name"] = stock_name
                # Map sector_id to sector name
                sector_id = report.get("sector_id")
                report["sector"] = SECTOR_MAPPING.get(sector_id, f"UNKNOWN_{sector_id}")
            return reports
        return []


async def main():
    """Main function to scrape all quarterly reports."""
    print(f"Starting quarterly report scraper at {datetime.now()}")
    print("=" * 60)
    
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Limit concurrent requests to be nice to the server
    semaphore = asyncio.Semaphore(10)
    
    async with aiohttp.ClientSession() as session:
        # Get all stocks
        stocks = await fetch_stock_list(session)
        if not stocks:
            print("Failed to fetch stock list. Exiting.")
            return
        
        # Create a mapping of stock_id to stock_name
        stock_info = {s["id"]: s["name"] for s in stocks}
        
        # Filter to only relevant stocks:
        # - Exclude delisted stocks
        # - Exclude sector 13 (Mutual Funds - they don't have quarterly reports)
        # - Exclude sector 14 (Promoter Shares - parent company has the reports)
        # - Exclude sector 15 (Debentures/Bonds - debt instruments, no quarterly reports)
        EXCLUDED_SECTORS = {13, 14, 15}
        
        active_stocks = [
            s for s in stocks 
            if not s.get("is_delisted", False) 
            and s.get("sector") not in EXCLUDED_SECTORS
        ]
        
        excluded_count = len(stocks) - len(active_stocks)
        print(f"Active stocks (excluding delisted & sectors 13/14/15): {len(active_stocks)}")
        print(f"Excluded: {excluded_count} (debentures, bonds, promoter shares, mutual funds)")
        
        # Fetch reports for all stocks concurrently
        print("\nFetching quarterly reports for all stocks...")
        tasks = [
            fetch_report(session, stock["id"], stock["name"], semaphore)
            for stock in active_stocks
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Flatten results and collect all reports
        all_reports = []
        stocks_with_data = 0
        for reports in results:
            if reports:
                stocks_with_data += 1
                all_reports.extend(reports)
        
        print(f"\nStocks with report data: {stocks_with_data}")
        print(f"Total quarterly reports collected: {len(all_reports)}")
        
        if not all_reports:
            print("No reports found. Exiting.")
            return
        
        # Filter out any reports with empty fiscal_year (shouldn't happen, but just in case)
        all_reports = [r for r in all_reports if r.get("fiscal_year")]
        print(f"After filtering empty reports: {len(all_reports)} reports")
        
        # Write to CSV
        print(f"\nWriting to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            
            # Sort by stock_id, fiscal_year, quarter for better organization
            all_reports.sort(key=lambda x: (
                x.get("stock_id", 0),
                x.get("fiscal_year", ""),
                x.get("quarter", "")
            ))
            
            for report in all_reports:
                writer.writerow(report)
        
        print(f"\nDone! Saved {len(all_reports)} quarterly reports to {OUTPUT_FILE}")
        print(f"Finished at {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())
