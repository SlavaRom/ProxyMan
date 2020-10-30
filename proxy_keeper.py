import asyncio
import pickle
import time
import json
import traceback

from proxybroker import Broker
import requests
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
log_time = datetime.now

PORT = 9090
FIND_EXACTLY = 9
FIND_MAX = 80
ACTIVE_PROXY = 50
PROXY_CHECKING_TIMEOUT = 300
proxy_dict = {}
_executor = ThreadPoolExecutor(2)

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
    except requests.exceptions.Timeout as time_err:
        print(log_time().now().strftime("[%d.%m.%Y / %H:%M:%S] "), 'The request timed out')
        raise time_err
    except requests.exceptions.HTTPError as http_err:
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), f'HTTP error occurred: {http_err}')
        raise http_err
    except Exception as err:
        print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Bad proxy: {}'.format(str(err.args)))
        raise err
    return response.elapsed.total_seconds()  # время отклика в секундах


async def find_proxies(proxies):  # Заполняет proxy_dict
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
                           "unavailable_until": datetime.now()  # TODO добавить метод "пометить прокси недействительным на n секунд" и добавить в фильтр в get_proxy по этому параметру
                           }


async def check_proxies():  # Обновляет proxy_dict
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
        return TypeError  # TODO добавить описание к ошибкам

    best_proxy = None
    type_key = proxy_type[0].upper()  # TODO сделать цикл
    if type_key not in ["HTTP", "HTTPS"]:
        return TypeError

    for current_proxy in proxy_dict:
        proxy = proxy_dict[current_proxy]
        if type_key not in proxy["proto"].keys():
            continue
        if best_proxy is None or proxy['response_time'] < best_proxy['response_time']:
            best_proxy = proxy

    if not best_proxy:
        return

    answer = {type_key: type_key.lower() + ":\\" + best_proxy["proxy"]}

    print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Удаляем выданный прокси', best_proxy["proxy"])
    proxy_dict.pop(best_proxy["proxy"])  # TODO не удалять, а помечать использованными и добавить фильтр "Не отдавать прокси, если уже отдавали недавно"
    print(log_time().strftime("[%d.%m.%Y / %H:%M:%S] "), 'Время поиска лучшего прокси: ', time.time() - start)
    return answer


async def main():
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
