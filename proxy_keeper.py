#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import socket
# import asyncio
# import pickle
# import time
#
# from proxybroker import Broker
# import urllib.request
# import urllib.error
# import ssl
# import json
#
# FIND_EXACTLY = 3  # количество искомых прокси за раз
# TIME_CHECK = 5    # время, через которое будет проверять прокси на работоспособность (в секундах)
#
# class TypesException(Exception):
#     pass
#
# s = {'http' : [], 'https' : []}
#
# def get_connection():
#     sock = socket.socket()
#     sock.bind(('', 9090))
#     sock.listen(2)
#     conn, addr = sock.accept()
#     print('connected:', addr)
#     proxies = asyncio.Queue()
#     return conn, proxies
#
# async def update_proxy_list(proxies):
#     while True:
#         proxy = await proxies.get()
#         if proxy is None:
#             break
#         proto = 'https' if 'HTTPS' in proxy.types else 'http'
#         val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
#         s[proto].append(val)
#
# async def update_one_proxy(proxies, ind):
#     while True:
#         proxy = await proxies.get()
#         if proxy is None:
#             break
#         proto = 'https' if 'HTTPS' in proxy.types else 'http'
#         val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
#         s[proto][ind] = val
#         print('update_one_proxy', proxy.host)
#
# def save_proxy_list():
#     print("save: ", s)
#     with open('proxy_list.pickle', 'wb') as f:
#         pickle.dump(s, f)
#
# def get_proxy_to_work(proxies, types):
#
#     if not isinstance(types, list):
#         raise TypesException('TypesException')
#     broker = Broker(proxies)
#     print('get_proxy')
#     tasks = asyncio.gather(broker.find(types=types, limit=FIND_EXACTLY),
#                            update_proxy_list(proxies))
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(tasks)
#     save_proxy_list()
#
# def change_one_proxy(proxies, types, ind):
#     broker = Broker(proxies)
#     tasks = asyncio.gather(broker.find(types=types, limit=2),
#                            update_one_proxy(proxies, ind))
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(tasks)
#     save_proxy_list()
#
# async def check_all_proxy():
#     for i in range(0, FIND_EXACTLY):
#         proxy = s['http'][i]
#         if is_bad_proxy(proxy):
#             print('is_bad_proxy!')
#             # change_one_proxy('http', i)
#         else:
#             print('Good!')
#         await asyncio.sleep(0)
#         proxy = s['https'][i]
#         if is_bad_proxy(proxy):
#             print('is_bad_proxy!')
#             # change_one_proxy('https', i)
#         else:
#             print('Good!')
#         await asyncio.sleep(0)
#
# def is_bad_proxy(proxy):
#     try:
#         proxy_handler = urllib.request.ProxyHandler(proxy)
#         opener = urllib.request.build_opener(proxy_handler)
#         opener.addheaders = [('User-agent', 'Mozilla/5.0')]
#         urllib.request.install_opener(opener)
#         req=urllib.request.Request('https://yandex.ru/')
#         sock=urllib.request.urlopen(req, context=ssl._create_unverified_context())
#     except urllib.error.HTTPError as e:
#         print('Error code: ', e.code)
#         return e.code
#     except Exception as detail:
#         print("ERROR:", detail)
#         return True
#     return False
#
#
# conn, proxies = get_connection()
#
# get_proxy_to_work(proxies, ['HTTP'])
# get_proxy_to_work(proxies, ['HTTPS'])
# #change_one_proxy(['HTTP'], 0)
#
#
# timing = time.time()
# current_http_proxy = current_https_proxy = 0
# while True:
#     try:
#         req_body = conn.recv(2048)
#         if req_body:
#             types = json.loads(req_body)
#             types = types['params'][0][0]
#             print('types:', types)
#
#         current_http_proxy = 1 if current_http_proxy > (FIND_EXACTLY - 1) else current_http_proxy
#         current_https_proxy = 1 if current_https_proxy > (FIND_EXACTLY - 1) else current_https_proxy
#
#         """"Проверим все прокси каждые FIND_EXACTLY секунд"""
#
#         if time.time() - timing > TIME_CHECK:
#             check_all_proxy()
#             timing = time.time()
#
#         """"Запрос от клиента обрабатывается"""
#         if types == 'HTTP':
#             #get_proxy('http')
#             proxy = s[types.lower()][current_http_proxy]
#             slovar = {types.lower(): proxy}
#             json_req = json.dumps(slovar)
#             conn.send(json_req.encode())
#             print('Send: ', slovar)
#             change_one_proxy(proxies, [types], current_http_proxy)
#             current_http_proxy += 1
#         if types == 'HTTPS':
#             #get_proxy('https')
#             proxy = s[types.lower()][current_https_proxy]
#             slovar = {types.lower(): proxy}
#             json_req = json.dumps(slovar)
#             conn.send(json_req.encode())
#             print('Send: ', slovar)
#             change_one_proxy(proxies, [types], current_https_proxy)
#             current_https_proxy += 1
#     except ConnectionAbortedError:
#         pass
# conn.close()

import socket
import asyncio
import pickle
import time

from proxybroker import Broker
import urllib.request
import urllib.error
import ssl
import json

TIME_CHECK = 5    # время, через которое будет проверять прокси на работоспособность (в секундах)

class EmptyListProxyException(Exception):
    pass

proxy_dict = {'http': [], 'https': []}

def get_connection():
    sock = socket.socket()
    sock.bind(('', 9090))
    sock.listen(2)
    conn, addr = sock.accept()
    print('connected:', addr)
    return conn

def save_proxy_list():
    print("save: ", proxy_dict)
    with open('proxy_list.pickle', 'wb') as f:
        pickle.dump(proxy_dict, f)

def is_bad_proxy(proxy):
    try:
        types = proxy.split('://')[0]
        proxy = {types: proxy}
        proxy_handler = urllib.request.ProxyHandler(proxy)
        opener = urllib.request.build_opener(proxy_handler)
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        req=urllib.request.Request('https://yandex.ru/')
        sock=urllib.request.urlopen(req, context=ssl._create_unverified_context())
    except urllib.error.HTTPError as e:
        print('Error code: ', e.code)
        return e.code
    except Exception as detail:
        #print("ERROR:", detail)
        return True
    return False

async def find_proxies(proxies):  # Заполняет proxy_dict
    while True:
        proxy = await proxies.get()
        if proxy is None:
            break
        proto = 'https' if 'HTTPS' in proxy.types else 'http'
        val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
        proxy_dict[proto].append(val)


async def check_proxies():  # Обновляет proxy_dict
    #while True:
    for http_key in ["http", "https"]:  # Чередует "http" и "https"
        for proxy in proxy_dict[http_key]:
            if is_bad_proxy(proxy):
                await proxy_dict[http_key].remove(proxy)


async def check_connection(conn):
    req_body = conn.recv(2048)
    if req_body:  # Поменять на "если что-то попросили"
        request = json.loads(req_body)
        proxy = get_proxy(request['params'])
        send = json.dumps(proxy)
        print("Send: ", send)
        conn.send(send.encode())
        print("Success")
    await asyncio.sleep(0)


def get_proxy(req_type):  # Находит в proxy_dict лучший прокси и возвращает его
    if req_type:
        req_type = req_type[0]
        for type_key in req_type:
            for current_proxy in range(0, len(proxy_dict[type_key.lower()])):
                proxy = proxy_dict[type_key.lower()][current_proxy]
                if proxy:
                    best_proxy = {type_key.lower(): proxy}
                    proxy_dict[type_key.lower()].remove(proxy)  # удалим выданный прокси из списка
                    return best_proxy
    print('Implicit context switch back to bar')

conn = get_connection()

proxies = asyncio.Queue()
broker = Broker(proxies)
ioloop = asyncio.get_event_loop()
tasks = [broker.find(types=["HTTP", "HTTPS"], limit=5),
         ioloop.create_task(find_proxies(proxies)),
         ioloop.create_task(check_connection(conn)),
         ioloop.create_task(check_proxies())]
wait_tasks = asyncio.wait(tasks)
ioloop.run_until_complete(wait_tasks)
print('Close connection')
ioloop.close()

