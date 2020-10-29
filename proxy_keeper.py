import socket
import asyncio
import pickle
import time
import json

from proxybroker import Broker
import requests
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

PORT = 9090
FIND_EXACTLY = 9
FIND_MAX = 80
ACTIVE_PROXY = 50
PROXY_CHECKING_TIMEOUT = 20

proxy_dict = {'http': [], 'https': []}

_executor = ThreadPoolExecutor(2)

log_time = datetime.now

class HandleRequests(BaseHTTPRequestHandler):
    def do_GET(self):
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Принял get запрос")
        self.send_response(200)
        self.end_headers()
        params = self.path[2:]
        params = params.replace('&', '')
        types = params.split('types=')[1:]
        proxy = get_proxy(types)
        send = json.dumps(proxy).encode()
        self.wfile.write(send)
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Отправил прокси")


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
        #response.raise_for_status()
    except requests.exceptions.Timeout as time_err:
        print(log_time().now().strftime("[%d.%m.%Y / %H:%M:%S] "), 'The request timed out')
        return time_err
    except requests.exceptions.HTTPError as http_err:
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), f'HTTP error occurred: {http_err}')
        return http_err
    except Exception as err:
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), f'Bad proxy: {err}')
        raise err
    return response.elapsed.total_seconds()  # время отклика в секундах


async def find_proxies(proxies):  # Заполняет proxy_dict
    global is_finding_run
    while True:
        proxy = await proxies.get()
        if proxy is None:
            is_finding_run = False
            break
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Добавляем новый прокси", proxy)
        proto = 'https' if 'HTTPS' in proxy.types else 'http'
        val = '%s://%s:%d' % (proto, proxy.host, proxy.port)
        proxy_dict[proto].append({'proxy': val, 'response_time': proxy.avg_resp_time})


async def check_proxies():  # Обновляет proxy_dict
    for http_key in ["http", "https"]:  # Чередует "http" и "https"
        for proxy in proxy_dict[http_key]:
            try:
                res_time = await ioloop.run_in_executor(_executor, get_reponce_time, proxy)
                proxy['response_time'] = res_time
            except requests.exceptions.Timeout:
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем плохой прокси', proxy)
                proxy_dict[http_key].remove(proxy)
            except requests.exceptions.HTTPError:
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем плохой прокси', proxy)
                proxy_dict[http_key].remove(proxy)


def get_proxy(proxy_type):  # Находит в proxy_dict лучший прокси и возвращает его
    start = time.time()
    if isinstance(proxy_type, list):
        for type_key in proxy_type:  # Если просят http и https, но
            best_proxy = None
            type_key = type_key.lower()
            if type_key != 'http' and type_key != 'https':
                return TypeError
            for current_proxy in range(0, len(proxy_dict[type_key])):
                proxy = proxy_dict[type_key][current_proxy]
                if best_proxy is None or proxy['response_time'] < best_proxy['response_time']:
                #best_proxy = {type_key.lower(): proxy}
                    best_proxy = proxy
            if not best_proxy:
                break
            proto = best_proxy['proxy'].split('://')[0]
            answer = {proto: best_proxy['proxy']}
            print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем выданный прокси', proxy)
            proxy_dict[proto].remove(best_proxy)  # удалим выданный прокси из списка
            print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Время поиска лучшего прокси: ', time.time() - start)
            return answer
    else:
        return TypeError

async def main():
    proxies = asyncio.Queue()
    broker = Broker(proxies, timeout=6)
    proxy_find_task = ioloop.create_task(asyncio.sleep(2))
    proxy_add_task = ioloop.create_task(asyncio.sleep(2))
    last_check_time = time.time()

    ioloop.run_in_executor(_executor, HTTPServer(('127.0.0.1', PORT), HandleRequests).serve_forever)
    while True:  # Не создавайте задачи внутри цикла на каждую итерацию!
        if proxy_find_task.done() and proxy_add_task.done() and (len(proxy_dict['http']) < FIND_MAX):
            print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили поиск http прокси!")
            proxy_find_task = ioloop.create_task(broker.find(types=["HTTP"], limit=FIND_MAX-len(proxy_dict['http'])))
        # if proxy_find_task.done() and proxy_add_task.done() and (len(proxy_dict['https']) < FIND_MAX):
        #     print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили поиск https прокси!")
        #     proxy_find_task = ioloop.create_task(broker.find(types=["HTTPS"], limit=FIND_MAX-len(proxy_dict['https'])))
        if proxy_add_task.done() and (len(proxy_dict['http']) < FIND_MAX):
            print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили добавление find_proxies")
            proxy_add_task = ioloop.create_task(find_proxies(proxies))
        if proxy_add_task.done() and (time.time() - last_check_time > PROXY_CHECKING_TIMEOUT):
            print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили проверку прокси")
            ioloop.create_task(check_proxies())
            last_check_time = time.time()
        await asyncio.sleep(0.05)

if __name__ == "__main__":
    proxies = asyncio.Queue()
    broker = Broker(proxies, timeout=6)
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(broker.find(types=['HTTP'], limit=3, post=True)),
             loop.create_task(find_proxies(proxies))]
    wait_tasks = asyncio.wait(tasks)
    loop.run_until_complete(wait_tasks)
    print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Прогрев сервиса прокси завершен")

    ioloop = asyncio.get_event_loop()
    ioloop.run_until_complete(main())