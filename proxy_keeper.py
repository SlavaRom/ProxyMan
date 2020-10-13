import socket
import asyncio
import pickle
import time

from proxybroker import Broker
import urllib.request
import urllib.error
import ssl
import json

FIND_EXACTLY = 9
FIND_MAX = 80
ACTIVE_PROXY = 50
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

def is_bad_proxy(proxy):  # get_reponce_time
    #измерить и вернуть время отклика. Если плохой прокси, вернуть None
    try:
        types = proxy.split('://')[0]
        proxy = {types: proxy}
        proxy_handler = urllib.request.ProxyHandler(proxy)
        opener = urllib.request.build_opener(proxy_handler)
        opener.addheaders = [('User-agent', 'Mozilla/5.0')]
        urllib.request.install_opener(opener)
        req=urllib.request.Request('https://ya.ru/')
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
        print("Добавляем новый прокси", proxy)
        if proxy is None:
            break
        proto = 'https' if 'HTTPS' in proxy.types else 'http'
        val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
        #{"https": [{"proxy": val, "responce_time": res_time}, {...}], "http": [...]}
        proxy_dict[proto].append(val)


async def check_proxies():  # Обновляет proxy_dict
    for http_key in ["http", "https"]:  # Чередует "http" и "https"
        for proxy in proxy_dict[http_key]:
            is_bad = await is_bad_proxy(proxy)
            # Обновить время прокси
            if is_bad:
                proxy_dict[http_key].remove(proxy)


async def check_connection(conn):
    req_body = conn.recv(2048)
    if req_body:
        request = json.loads(req_body)
        proxy = get_proxy(request['params']['proxy_types'])
        send = json.dumps(proxy)
        print("Send: ", send)
        conn.send(send.encode())
    await asyncio.sleep(0.01)


def get_proxy(proxy_type):  # Находит в proxy_dict лучший прокси и возвращает его
    start = time.time()
    if proxy_type:
        for type_key in proxy_type:
            for current_proxy in range(0, len(proxy_dict[type_key.lower()])):
                proxy = proxy_dict[type_key.lower()][current_proxy]
                if proxy:
                    best_proxy = {type_key.lower(): proxy}
                    proxy_dict[type_key.lower()].remove(proxy)  # удалим выданный прокси из списка
                    print('Get proxy. Time: ', time.time() - start)
                    return best_proxy
    print('Get proxy. Time: ', time.time() - start)

async def main(proxies, broker, start):
    refresh_flag = True
    await broker.find(types=["HTTP"], limit=10000)  # Неблокирующий вызов
    while True:
        await check_connection(conn)
        asyncio.sleep(0.01)
        if refresh_flag and (time.time() - start > TIMEOUT or len(proxy_dict['http']) < FIND_MAX or len(proxy_dict['https']) < FIND_MAX):
            print("Обновляем список прокси!")
            # asyncio.ensure_future(broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http'])))   # Неблокирующий вызов
            # asyncio.ensure_future(broker.find(types=["HTTPS"], limit=FIND_MAX-len(proxy_dict['https'])))   # Неблокирующий вызов
            await find_proxies(proxies)  # Неблокирующий вызов
            print("После find_proxies")
            asyncio.ensure_future(check_proxies())  # Неблокирующий вызов
            start = time.time()
            refresh_flag = False

proxies = asyncio.Queue()
broker = Broker(proxies)

loop = asyncio.get_event_loop()
tasks = [broker.find(types=["HTTP"], limit=30),
         loop.create_task(find_proxies(proxies))]
wait_tasks = asyncio.wait(tasks)
loop.run_until_complete(wait_tasks)
print("Прокси набрались")
conn = get_connection()

start = time.time()
ioloop = asyncio.get_event_loop()
ioloop.run_until_complete(main(proxies, broker, start))
print('Close connection')
