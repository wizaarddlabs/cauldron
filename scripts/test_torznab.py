import httpx
import xml.etree.ElementTree as ET
import time

url = "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api"

params = {
    "apikey": "of6a05kndn50fdq27313zfw3l66yn3cj",
    "t": "search",
    "q": "Game.of.Thrones.S01E01"
}

print("Querying Jackett...")
start = time.time()

with httpx.Client(timeout=60.0) as client:
    r = client.get(url, params=params)

elapsed = round(time.time() - start, 2)

print("HTTP:", r.status_code)
print("Time:", elapsed, "seconds")
print("Bytes:", len(r.text))

root = ET.fromstring(r.text)

results = root.findall(".//item")

print("Results:", len(results))

for item in results[:10]:
    title = item.find("title")
    if title is not None:
        print("-", title.text)