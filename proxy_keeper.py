import socket
import asyncio
import pickle
import time

from proxybroker import Broker
import urllib.request
import urllib.error
import ssl
import json
import requests
from concurrent.futures import ThreadPoolExecutor

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


async def get_reponce_time(proxy):
    # измерить и вернуть время отклика. Если плохой прокси, вернуть None
    try:
        types = proxy.split('://')[0]
        proxy = {types: proxy}
        response = requests.get('https://ya.ru/', proxies=proxy, verify=None, timeout=2)
        #response.raise_for_status()
        asyncio.sleep(0)
    except requests.exceptions.Timeout as time_err:
        print('The request timed out')
        return time_err
    except requests.exceptions.HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
        return http_err
    except Exception as err:
        print(f'Bad proxy: {err}')
        return err
    return response.elapsed.total_seconds()  # время отклика в секундах


async def find_proxies(proxies):  # Заполняет proxy_dict
    start = time.time()
    while True:
        if time.time() - start > TIMEOUT or len(proxy_dict['http']) < FIND_MAX or len(
                proxy_dict['https']) < FIND_MAX:
            for a in range(0, FIND_MAX-len(proxy_dict['http'])):
                proxy = await proxies.get()
                print("Добавляем новый прокси", proxy)
                if proxy is None:
                    break
                proto = 'https' if 'HTTPS' in proxy.types else 'http'
                val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
                res_time = proxy.avg_resp_time
                # {"https": [{"proxy": val, "responce_time": res_time}, {...}], "http": [...]}
                #proxy_dict[proto].append(val)
                asyncio.sleep(0)
                proxy_dict[proto].append({'proxy': val, 'response_time': res_time})
        else:
            await asyncio.sleep(0.01)


async def check_proxies():  # Обновляет proxy_dict
    for http_key in ["http", "https"]:  # Чередует "http" и "https"
        for proxy in proxy_dict[http_key]:
            try:
                res_time = await get_reponce_time(proxy['proxy'])
                proxy['response_time'] = res_time
            except requests.exceptions.Timeout:
                proxy_dict[http_key].remove(proxy)
            except requests.exceptions.HTTPError:
                proxy_dict[http_key].remove(proxy)

async def check_connection(conn):
    while True:
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
        for type_key in proxy_type:  # Если просят http и https, но
            best_proxy = None
            for current_proxy in range(0, len(proxy_dict[type_key.lower()])):
                proxy = proxy_dict[type_key.lower()][current_proxy]
                if proxy:
                    if best_proxy is None or proxy['response_time'] < best_proxy['response_time']:
                    #best_proxy = {type_key.lower(): proxy}
                        best_proxy = proxy
            if not best_proxy:
                break
            proto = best_proxy['proxy'].split('://')[0]
            answer = {proto: best_proxy['proxy']}
            proxy_dict[proto].remove(best_proxy)  # удалим выданный прокси из списка
            print('Get proxy. Time: ', time.time() - start)
            return answer
    print('Get proxy. Time: ', time.time() - start)


async def main(proxies, broker, start):
    await broker.find(types=["HTTP"], limit=10000)  # Неблокирующий вызов
    while True:
        #await check_connection(conn)
        ioloop.create_task(check_connection(conn))
        if time.time() - start > TIMEOUT or len(proxy_dict['http']) < FIND_MAX or len(
                proxy_dict['https']) < FIND_MAX:
            print("Обновляем список прокси!")
            #asyncio.ensure_future(broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http'])))   # Неблокирующий вызов
            ioloop.create_task(broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http'])))   # Неблокирующий вызов
            #await broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http']))   # Неблокирующий вызов
            # asyncio.ensure_future(broker.find(types=["HTTPS"], limit=FIND_MAX-len(proxy_dict['https'])))   # Неблокирующий вызов
            #await find_proxies(proxies)  # Неблокирующий вызов
            await asyncio.sleep(0.05)
            #asyncio.ensure_future(find_proxies(proxies))  # Неблокирующий вызов
            ioloop.create_task(find_proxies(proxies))  # Неблокирующий вызов
            print("После find_proxies")
            #asyncio.ensure_future(check_proxies())  # Неблокирующий вызов
            #ioloop.create_task(check_proxies())  # Неблокирующий вызов
            start = time.time()


proxies = asyncio.Queue()
broker = Broker(proxies)


#loop.run_until_complete(check_proxies())
print("Прокси набрались")

conn = get_connection()

start = time.time()
ioloop = asyncio.get_event_loop()
ioloop.create_task(broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http'])))
ioloop.create_task(find_proxies(proxies))
ioloop.create_task(check_connection(conn))
ioloop.run_forever()
print('Close connection')
