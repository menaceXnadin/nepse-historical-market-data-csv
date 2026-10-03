import json
import httpx
from datetime import datetime
import csv

response = httpx.get("https://chukul.com/api/sector/")
# print(response.content)
data= json.loads(response.content.decode('utf-8'))
# print(data[2])
# print(type(data))
# print(type(data[0]))






if isinstance(data,list) and len(data)>0:
    with open("sectormapping.csv","w",newline="",encoding="utf-8") as f:
        writer = csv.DictWriter(f,fieldnames=["symbol","sector"])
        writer.writeheader()
        for i in data:
            for j in i["stocks"]:
                writer.writerow({"symbol":j["symbol"],"sector":i["symbol"]})
                
                




print("successfully written")
