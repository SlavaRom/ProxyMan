import requests as req

for i in range(50):
    res = req.get("http://127.0.0.1:9090")
    print(res)
    print(res.content)