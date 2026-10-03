import asyncio
import httpx
import json
import csv
from datetime import datetime
import os
import glob

os.makedirs('data/stock/adjusted', exist_ok=True)
os.makedirs('data/stock/unadjusted', exist_ok=True)
os.makedirs('data/index/adjusted',exist_ok=True)
os.makedirs('data/index/unadjusted',exist_ok=True)
os.makedirs('data/subindices/adjusted',exist_ok=True)
os.makedirs('data/subindices/unadjusted',exist_ok=True)

# Separate semaphores for adjusted and unadjusted
semaphore_adjusted = asyncio.Semaphore(15)  # Max 15 concurrent requests for adjusted
semaphore_unadjusted = asyncio.Semaphore(15)  # Max 15 concurrent requests for unadjusted

async def fetch_and_save(symbol_name, folder_type, folder, is_adjust):
    """
    Fetch and save data for stocks, indices, or subindices
    folder_type: 'stock', 'index', or 'subindices'
    folder: 'adjusted' or 'unadjusted'
    """
    semaphore = semaphore_adjusted if is_adjust else semaphore_unadjusted
    async with semaphore:  # Limit concurrent requests
        safe_symbol_name = symbol_name.replace('/', '_')
        url = f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={symbol_name}&resolution=1D&countback=0&isAdjust={'true' if is_adjust else 'false'}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                data = json.loads(response.content.decode('utf-8'))
                if data.get('success') == True and data.get('code') == 'SUCCESS' and data.get("data"):
                    latest_date = datetime.fromtimestamp(data["data"][-1]["time"]/1000).strftime("%Y_%m_%d")
                    
                    # Delete old files before creating new one
                    old_files = glob.glob(f"data/{folder_type}/{folder}/{safe_symbol_name}_*.csv")
                    for old_file in old_files:
                        os.remove(old_file)
                    
                    # Determine category based on folder_type
                    if folder_type == 'stock':
                        category = 'stock'
                    elif folder_type == 'index':
                        category = 'index'
                    elif folder_type == 'subindices':
                        category = 'subindex'
                    else:
                        category = 'unknown'
                    
                    with open(f"data/{folder_type}/{folder}/{safe_symbol_name}_{latest_date}_{folder}.csv", 'w', newline='', encoding='utf-8') as f:
                        # Add 'category' to fieldnames
                        fieldnames = list(data["data"][0].keys()) + ['category']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        for row in data["data"]:
                            row_copy = row.copy()
                            row_copy["time"] = datetime.fromtimestamp(row_copy["time"]/1000).strftime("%Y-%m-%d")
                            row_copy["category"] = category
                            # Ensure numeric columns are floats to maintain consistent schema
                            row_copy["open"] = float(row_copy["open"])
                            row_copy["close"] = float(row_copy["close"])
                            row_copy["high"] = float(row_copy["high"])
                            row_copy["low"] = float(row_copy["low"])
                            row_copy["volume"] = int(row_copy["volume"])
                            writer.writerow(row_copy)
                    print(f"✓ {symbol_name} ({folder_type}/{folder})")
                else:
                    print(f"✗ {symbol_name} ({folder_type}/{folder}) - No data")
        except Exception as e:
            print(f"✗ {symbol_name} ({folder_type}/{folder}) - Error: {e}")
        await asyncio.sleep(0.1)  # Small delay between requests

async def main():
    print("Starting program...")
    
    # Load sector data from local JSON file
    print("Loading sector data from sector.json...")
    with open('sector.json', 'r', encoding='utf-8') as f:
        stock_data = json.load(f)
    print(f"Got {len(stock_data)} sectors")
    
    # Define indices and subindices
    indices = ["NEPSE", "FLOAT", "SENSITIVE", "SENFLOAT"]
    subindices = ["BANKING", "DEVBANK", "FINANCE", "HOTELS", "HYDROPOWER", 
                 "INVESTMENT", "LIFEINSU", "MANUFACTURE", "MICROFINANCE", 
                 "MUTUAL", "NONLIFEINSU", "OTHERS", "TRADING"]

    tasks = []
    
    # Add tasks for indices
    for index in indices:
        tasks.append(fetch_and_save(index, "index", "adjusted", True))
        tasks.append(fetch_and_save(index, "index", "unadjusted", False))
    
    # Add tasks for subindices
    for subindex in subindices:
        tasks.append(fetch_and_save(subindex, "subindices", "adjusted", True))
        tasks.append(fetch_and_save(subindex, "subindices", "unadjusted", False))
    
    # Add tasks for stocks
    if isinstance(stock_data, list) and len(stock_data) > 0:
        for j in stock_data:
            for k in j["stocks"]:
                if k.get("can_trade") == True:
                    stock_name = k["symbol"]
                    # Create both adjusted and unadjusted tasks for each stock
                    tasks.append(fetch_and_save(stock_name, "stock", "adjusted", True))
                    tasks.append(fetch_and_save(stock_name, "stock", "unadjusted", False))
    
    print(f"Created {len(tasks)} tasks. Starting downloads...")
    await asyncio.gather(*tasks)
    print("All downloads complete!")

if __name__ == "__main__":
    asyncio.run(main())