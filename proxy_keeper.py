import socket
import asyncio
import pickle
import time
import json

from proxybroker import Broker
import requests
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer

FIND_EXACTLY = 9
FIND_MAX = 80
ACTIVE_PROXY = 50
TIMEOUT = 20

proxy_dict = {'http': [], 'https': []}

_executor = ThreadPoolExecutor(2)
is_finding_run = False
is_checking_run = False


class HandleRequests(BaseHTTPRequestHandler):
    def do_GET(self):
        print("Принял get запрос")
        self.send_response(200)
        self.end_headers()
        proxy = get_proxy(["http"])
        send = json.dumps(proxy).encode()
        self.wfile.write(send)
        print("Отправил прокси")


def save_proxy_list():
    print("save: ", proxy_dict)
    with open('proxy_list.pickle', 'wb') as f:
        pickle.dump(proxy_dict, f)


def get_reponce_time(proxy):
    # измерить и вернуть время отклика. Если плохой прокси, вернуть None
    try:
        types = proxy['proxy'].split('://')[0]
        proxy = {types: proxy}
        response = requests.get('https://ya.ru/', proxies=proxy, verify=None, timeout=2)
        print("Ответ во время проверки = ", str(response))
        #response.raise_for_status()
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
    print("Зашли в find_proxies")
    is_finding_run = True
    while True:
        proxy = await proxies.get()
        print("Добавляем новый прокси", proxy)
        if proxy is None:
            is_finding_run = False
            break
        proto = 'https' if 'HTTPS' in proxy.types else 'http'
        val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
        res_time = proxy.avg_resp_time
        proxy_dict[proto].append({'proxy': val, 'response_time': res_time})


async def check_proxies():  # Обновляет proxy_dict
    for http_key in ["http", "https"]:  # Чередует "http" и "https"
        for proxy in proxy_dict[http_key]:
            try:
                res_time = await ioloop.run_in_executor(_executor, get_reponce_time, proxy)
                proxy['response_time'] = res_time
            except requests.exceptions.Timeout:
                proxy_dict[http_key].remove(proxy)
            except requests.exceptions.HTTPError:
                proxy_dict[http_key].remove(proxy)


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


async def main(proxies, broker):
    start = time.time()
    print("Заход в main в ", start)
    # ioloop.create_task(check_connection(conn))
    host = ''
    port = 9090
    # print("start")
    ioloop.run_in_executor(_executor, HTTPServer((host, port), HandleRequests).serve_forever)
    while True:  # Не создавайте задачи внутри цикла!
        if not is_finding_run and (len(proxy_dict['http']) < FIND_MAX or len(proxy_dict['https']) < FIND_MAX):
            print("Обновляем список прокси!")
            ioloop.create_task(broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http'])))
            await asyncio.sleep(0.05)
            ioloop.create_task(find_proxies(proxies))
            print("После find_proxies")
        if not is_finding_run and (time.time() - start > TIMEOUT):
            print("Начинаем проверку прокси")
            ioloop.create_task(check_proxies())
            start = time.time()

proxies = asyncio.Queue()
broker = Broker(proxies, timeout=6)

loop = asyncio.get_event_loop()
tasks = [loop.create_task(broker.find(types=['HTTP'], limit=3, post=True)),
         loop.create_task(find_proxies(proxies))]
wait_tasks = asyncio.wait(tasks)
loop.run_until_complete(wait_tasks)
print("Прокси набрались")

start = time.time()
ioloop = asyncio.get_event_loop()
ioloop.run_until_complete(main(proxies, broker))
print('Close connection')
