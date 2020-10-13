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
    temp_dict = {"function": "get_proxy", 'params': [types]}
    json_req = json.dumps(temp_dict)
    sock.send(json_req.encode())
    data = json.loads(sock.recv(2048).decode())
    print(data)


sock = get_connection()

time.sleep(20)  # имитация попадания запроса прокси на момент проверки на сервере работоспособности прокси
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()
get_proxy(sock, ["HTTP"])
print(time.time() - start)
start = time.time()

sock.close()