import socket
import asyncio
import pickle
import time

from proxybroker import Broker
import urllib.request
import urllib.error
import ssl
import json

FIND_EXACTLY = 5
FIND_MAX = 50
ACTIVE_PROXY = 10
TIMEOUT = 20

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
    for http_key in ["http", "https"]:  # Чередует "http" и "https"
        for proxy in proxy_dict[http_key]:
            is_bad = await is_bad_proxy(proxy)
            if is_bad:
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
    start = time.time()
    if req_type:
        req_type = req_type[0]
        for type_key in req_type:
            for current_proxy in range(0, len(proxy_dict[type_key.lower()])):
                proxy = proxy_dict[type_key.lower()][current_proxy]
                if proxy:
                    best_proxy = {type_key.lower(): proxy}
                    proxy_dict[type_key.lower()].remove(proxy)  # удалим выданный прокси из списка
                    print('Get proxy. Time: ', time.time() - start)
                    return best_proxy
    print('Get proxy. Time: ', time.time() - start)
    print('Implicit context switch back to bar')

async def func(proxies, start):
    while True:
        # asyncio.ensure_future(check_connection(conn))  # Неблокирующий вызов
        # await broker.find(types=["HTTPS", "HTTP"], limit=FIND_EXACTLY)  # Блокирующий вызов
        # if time.time() - start > TIMEOUT or len(proxy_dict['http']) < 2 or len(proxy_dict['http']) < 2:
        #     await find_proxies(proxies)  # Блокирующий вызов
        #     await check_proxies()  # Блокирующий вызов
        #     start = time.time()
        await check_connection(conn)  # Блокирующий вызов
        asyncio.ensure_future(broker.find(types=["HTTPS", "HTTP"], limit=FIND_EXACTLY))  # Неблокирующий вызов
        if time.time() - start > TIMEOUT or len(proxy_dict['http']) < ACTIVE_PROXY or len(proxy_dict['http']) < ACTIVE_PROXY:
            asyncio.ensure_future(find_proxies(proxies))  # Неблокирующий вызов
            asyncio.ensure_future(check_proxies())  # Неблокирующий вызов
            start = time.time()


# proxies = asyncio.Queue()
# broker = Broker(proxies)
# ioloop = asyncio.get_event_loop()
# tasks = [broker.find(types=["HTTP", "HTTPS"], limit=5),
#          ioloop.create_task(find_proxies(proxies)),
#          ioloop.create_task(check_connection(conn)),
#          ioloop.create_task(check_proxies())]
# wait_tasks = asyncio.wait(tasks)
# ioloop.run_until_complete(wait_tasks)
# print('Close connection')
# ioloop.close()

proxies = asyncio.Queue()
broker = Broker(proxies)

loop = asyncio.get_event_loop()
tasks = [broker.find(types=["HTTP", "HTTPS"], limit=FIND_MAX),
         loop.create_task(find_proxies(proxies))]
wait_tasks = asyncio.wait(tasks)
loop.run_until_complete(wait_tasks)

conn = get_connection()

start = time.time()
ioloop = asyncio.get_event_loop()
ioloop.run_until_complete(func(proxies, start))
print('Close connection')
ioloop.close()
