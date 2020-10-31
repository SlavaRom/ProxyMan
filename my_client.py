import requests as req
import json

for i in range(81):
    types = {'types': ['http']}
    res = req.get(url="http://127.0.0.1:9090", params=types)
    print(res)
    print(res.content.decode())