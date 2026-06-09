import urllib.request
import json

url = "https://rutaigeoproxi-back.onrender.com/workshops/all"
req = urllib.request.Request(url, method="GET")

try:
    with urllib.request.urlopen(req) as r:
        body = r.read().decode("utf-8")
        data = json.loads(body)
        print("Workshops length:", len(data))
        if len(data) > 0:
            print("First workshop:", data[0])
except Exception as e:
    print(e)
