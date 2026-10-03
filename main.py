import httpx
import json
import csv
from datetime import datetime
from pprint import pprint
import os
os.makedirs('data/stock/adjusted',exist_ok=True)
os.makedirs('data/stock/unadjusted',exist_ok=True)

response2 = httpx.get("https://chukul.com/api/sector/")
stock_data = json.loads(response2.content.decode('utf-8'))


if isinstance(stock_data,list) and len(stock_data)>0 :
    for is_adjust in [True,False]:
        folder = "adjusted" if is_adjust else "unadjusted"
        for j  in stock_data:
            for k in j["stocks"]:
                if k["can_trade"]==True:
                    stock_name = k["symbol"]
                    response = httpx.get(f"https://sharehubnepal.com/data/api/v1/candle-chart/history?symbol={stock_name}&resolution=1D&countback=0&isAdjust={'true' if is_adjust else 'false'}")
                    data = json.loads(response.content.decode('utf-8'))
                    if data['success'] == True and data['code'] =='SUCCESS' and data["data"]:
                        print("Successfully Fetched from the endpoint")
                        latest_date=datetime.fromtimestamp(data["data"][-1]["time"]/1000).strftime("%Y_%m_%d")
                        safe_stock_name = stock_name.replace('/','_')
                        with open(f"data/stock/{folder}/{safe_stock_name}_{folder}_upto_{latest_date}.csv",'w',newline='',encoding='utf-8') as f:
                            writer = csv.DictWriter(f,fieldnames=data["data"][0].keys())
                            writer.writeheader()
                            for row in data["data"]:
                                row_copy = row.copy()
                                row_copy["time"] = datetime.fromtimestamp(row_copy["time"]/1000).strftime("%Y-%m-%d")
                                writer.writerow(row_copy)
print("successfully written to file")

                





