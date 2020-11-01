import asyncio
import pickle
import time
import json
import traceback

from proxybroker import Broker
import requests
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta
log_time = datetime.now

PORT = 9090
FIND_EXACTLY = 9
FIND_MAX = 80
ACTIVE_PROXY = 50
PROXY_CHECKING_TIMEOUT = 300
proxy_dict = {}
_executor = ThreadPoolExecutor(2)
sem = asyncio.Semaphore(50)

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
        proto = list(proxy["proto"].keys())[0]
        proxy = {proto: proto.lower() + ":\\" + proxy["proxy"]}
        print("Чеккер проверяет прокси", proxy)  # TODO Проверка вообще не ходит через прокси сейчас
        response = requests.get('https://ya.ru/', proxies=proxy, verify=None, timeout=2)
        #response.raise_for_status()
    except requests.exceptions.Timeout:
        print(log_time().now().strftime("[%d.%m.%Y / %H:%M:%S] "), 'The request timed out')
        raise requests.exceptions.Timeout('The request timed out')
    except requests.exceptions.HTTPError as http_err:
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), f'HTTP error occurred: {http_err}')
        raise requests.exceptions.HTTPError(f'HTTP error occurred: {http_err}')
    except Exception as err:
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Bad proxy: {}'.format(str(err.args)))
        raise Exception('Bad proxy: {}'.format(str(err.args)))
    return response.elapsed.total_seconds()  # время отклика в секундах


async def find_proxies(proxies):  # Заполняет proxy_dict
    async with sem:
        while True:
            proxy = await proxies.get()
            if proxy is None:
                break

            print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Добавляем новый прокси номер", len(proxy_dict), proxy)
            val = '{host}:{port}'.format(host=proxy.host, port=proxy.port)
            proxy_dict[val] = {'response_time': proxy.avg_resp_time,
                               "proto": proxy.types,
                               "proxy": val,
                               "last_used_time": datetime.now(),
                               "unavailable_until": datetime.now()
                               }

def unavailable_until(proxy, n):
    proxy['unavailable_until'] = datetime.now() + timedelta(seconds=n)

async def check_proxies():  # Обновляет proxy_dict
    async with sem:
        for proxy in proxy_dict:
            try:
                res_time = await ioloop.run_in_executor(_executor, get_reponce_time, proxy_dict[proxy])
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Ответ нашего чеккера:", res_time)
                proxy_dict[proxy]['response_time'] = res_time
            except requests.exceptions.Timeout:
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем плохой прокси', proxy)
                proxy_dict.pop(proxy)
            except requests.exceptions.HTTPError:
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем плохой прокси', proxy)
                proxy_dict.pop(proxy)
            except Exception as err:
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Неизвестная ошибка во время проверки', traceback.format_exc())


def get_proxy(proxy_type):  # Находит в proxy_dict лучший прокси и возвращает его
    start = time.time()
    if not isinstance(proxy_type, list) or not proxy_type:
        return TypeError('Передавайте в функцию get_proxy только непустой массив')

    best_proxy = None
    for type_key in proxy_type:
        type_key = type_key.upper()
        if type_key not in ["HTTP", "HTTPS"]:
            return TypeError('Умеем обрабатывать только HTTP и HTTPS проски. Измените тип запрашиваемых данных')

        for current_proxy in proxy_dict:
            proxy = proxy_dict[current_proxy]
            # второе условие проверяет доступность к использованию прокси
            if type_key not in proxy["proto"].keys() or proxy['unavailable_until'] > datetime.now():
                continue
            if best_proxy is None or proxy['response_time'] < best_proxy['response_time']:
                best_proxy = proxy

        if not best_proxy:
            continue

        answer = {type_key: type_key.lower() + ":\\" + best_proxy["proxy"]}

        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем выданный прокси', best_proxy["proxy"])
        unavailable_until(best_proxy, 3000)
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Время поиска лучшего прокси: ', time.time() - start)
        return answer


async def main():
    async with sem:
        # Создаем сервер для выдачи
        ioloop.run_in_executor(_executor, HTTPServer(('127.0.0.1', PORT), HandleRequests).serve_forever)

        # Переменные для проверки проксей
        proxy_check_task = ioloop.create_task(asyncio.sleep(2))
        last_check_time = time.time()

        # Запускаем поиск и добавление прокси
        proxies = asyncio.Queue()
        broker = Broker(proxies, timeout=30, max_conn=2000)
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили поиск http прокси!")
        ioloop.create_task(broker.find(types=["HTTP", "HTTPS"], limit=0))
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили добавление find_proxies")
        ioloop.create_task(find_proxies(proxies))

        while True:  # Не создавайте задачи внутри цикла на каждую итерацию!
            if proxy_check_task.done() and time.time() - last_check_time > PROXY_CHECKING_TIMEOUT:
                print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), "Запустили проверку прокси")
                proxy_check_task = ioloop.create_task(check_proxies())
                last_check_time = time.time()
            await asyncio.sleep(5)

if __name__ == "__main__":
    ioloop = asyncio.get_event_loop()
    ioloop.run_until_complete(main())
