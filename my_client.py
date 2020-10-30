import requests as req
import json
import time

for i in range(100):
    types = {'types': ['https']}
    res = req.get(url="http://127.0.0.1:9090", params=types)
    print(res)
    print(res.content.decode())
    # time.sleep(1)