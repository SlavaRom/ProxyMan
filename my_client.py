import requests as req
import json
import time


for i in range(100):
    data = json.dumps({"method": "get_proxy", "params": {'types': ['http', 'https']}})
    res = req.post("http://127.0.0.1:9090/", data)
    ans = json.loads(res.content.decode())
    print(res, ans)
    data = json.dumps({"method": "unavailable_until", "params": [ans, 50]})
    res = req.post("http://127.0.0.1:9090/", data)
    ans = json.loads(res.content.decode())
    print(res, ans)
