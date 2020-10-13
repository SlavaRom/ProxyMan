#!/usr/bin/env python
# -*- coding: utf-8 -*-

import socket
import json
import time

def get_connection():
    sock = socket.socket()
    sock.connect(('127.0.0.1', 9090))
    return sock

def get_proxy(sock, types):
    temp_dict = {"function": "get_proxy", 'params': {'proxy_types': types}}
    json_req = json.dumps(temp_dict)
    sock.send(json_req.encode())
    data = json.loads(sock.recv(2048).decode())
    print(data)


sock = get_connection()

start = time.time()
max = 0
K = 10
I = 10
sum = 0
for k in range(0, K):
    start = time.time()
    for i in range(0, I):
        get_proxy(sock, ["HTTP"])
        lim = time.time() - start
        print(str(k) + str(i), lim)
        sum += lim
        if lim > max:
            max = lim
        start = time.time()
    time.sleep(10)
print('Max time:', max)
sock.close()