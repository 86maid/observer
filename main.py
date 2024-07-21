from enum import Enum
import json
import random
import traceback
import regex as re
import time
import asyncio
import rich.box
import rich.style
import websockets_proxy
import websockets
import aiohttp
import asyncio


async def get_dexscreener_token(pair, proxy):
    global session
    global amm_id_cache

    result = amm_id_cache.get(pair)

    if result:
        return result

    url = f"wss://io.dexscreener.com/dex/screener/pair/{pair}"

    headers = {
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Host": "io.dexscreener.com",
        "Origin": "https://dexscreener.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    }

    try:
        ws = await websockets_proxy.proxy_connect(
            url, proxy=websockets_proxy.Proxy.from_url(proxy), extra_headers=headers
        )

        text = await ws.recv()

        text = json.loads(text)

        result = [text["pair"]["a"], text["pair"]["quoteToken"]["address"]]

        amm_id_cache[pair] = result

        return result

    except BaseException as e:
        return e


async def get_dexscreener_price(pair, proxy):
    global session

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Cookie": "_ga=GA1.1.1346212385.1721207221; chakra-ui-color-mode=dark; _ga_RD6VMQDXZ6=GS1.1.1721217354.2.0.1721217354.0.0.0; __cf_bm=_QaA1LY5P_qJYV7y9YppTTw74y.h0M4sO4nN3dIapLE-1721223925-1.0.1.1-.sBuo4lbSi5OW3mhvNhyJfjv0.D3U4_ir5tCdii9wOZyqqqhK1HFjioBc6QB8n6pKqtEogqTSuTndILB7bKVfbNnfW5WgIW_adQT5rbvwNc; cf_clearance=f9dHVrzdJB5aGwKKT58OraTEzymvoYwnWQhJdk6D4UU-1721223929-1.0.1.1-lTKyqhP_srCGMv5WP78ST4swHuMnljELwzpPKfBvyAXexzPmvdpnjEn0HMZhHRwKyDr9SGKiaKl7yHFaZWeBuQ; _ga_532KFVB4WT=GS1.1.1721223312.5.1.1721224431.50.0.0",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"',
        "Sec-Ch-Ua-Arch": '"x86"',
        "Sec-Ch-Ua-Bitness": '"64"',
        "Sec-Ch-Ua-Full-Version": '"126.0.2592.102"',
        "Sec-Ch-Ua-Full-Version-List": '"Not/A)Brand";v="8.0.0.0", "Chromium";v="126.0.6478.127", "Microsoft Edge";v="126.0.2592.102"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Model": '""',
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Ch-Ua-Platform-Version": '"10.0.0"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    }

    try:
        result = await get_dexscreener_token(pair, proxy)

        if isinstance(result, BaseException):
            raise result

        url = f"https://io.dexscreener.com/dex/chart/amm/v3/{result[0]}/bars/{pair}?res=1S&cb=2&q={result[1]}"

        if not session:
            session = aiohttp.ClientSession()

        async with session.get(url, headers=headers, proxy=proxy) as response:
            data = await response.read()

            text = repr(data)

            float_pattern = re.compile(
                r"(?<=\\x[0-9a-fA-F]{2}|\\n)[-+]?\d*\.\d+(?:[eE][-+]?\d+)?"
            )

            float_matches = float_pattern.findall(text)

            return float_matches[-2]

            # start_index = data.rfind(b"\x02\x12")
            # if start_index == -1:
            #     start_index = data.rfind(b"\x02\x10")
            #     if start_index == -1:
            #         return IndexError("no start")

            # end_index = data.rfind(b"\x02")
            # if end_index == -1:
            #     return IndexError("no end")

            # extracted_bytes = data[start_index + 2 : end_index]
            # utf8_string = extracted_bytes.decode("utf-8")

            # return utf8_string

    except BaseException as e:
        return e


class ConnectionState(Enum):
    DISCONNECTED = "未连接"
    CONNECTING = "正在重连"
    CONNECTED = "已连接"


class WebSocketClient:
    def __init__(self, proxy, name):
        self.uri = "wss://api.ox.fun/v2/websocket"
        self.proxy = proxy
        self.name = name
        self.ws = None
        self.loop = None
        self.state = ConnectionState.DISCONNECTED

        if not isinstance(name, list):
            self.name = list(name)

    async def connect(self):
        try:
            self.state = ConnectionState.CONNECTING
            self.ws = await websockets_proxy.proxy_connect(
                self.uri, proxy=websockets_proxy.Proxy.from_url(self.proxy)
            )
            await self.subscribe()
            self.state = ConnectionState.CONNECTED
        except BaseException as e:
            return e

    def start_connect_loop(self):
        async def loop():
            while True:
                if self.state != ConnectionState.CONNECTED:
                    await self.connect()
                await asyncio.sleep(1)

        if not self.loop:
            self.loop = asyncio.tasks.create_task(loop())

    async def subscribe(self):
        data = {
            "op": "subscribe",
            "args": [
                n for i in self.name for n in [f"futures/depth:{i}", f"candles60s:{i}"]
            ],
            "tag": "1721232465385",
        }

        await self.ws.send(json.dumps(data))

    async def recv(self):
        try:
            while True:
                try:
                    message = await self.ws.recv()
                except websockets.ConnectionClosedError:
                    self.state = ConnectionState.DISCONNECTED
                    yield None
                try:
                    yield json.loads(message)
                except BaseException:
                    yield None
        except asyncio.CancelledError:
            pass

        yield None

    def close(self):
        if self.ws:
            self.ws = None

        if self.loop:
            self.loop.cancel()

        self.state = ConnectionState.DISCONNECTED

    def __del__(self):
        self.close()

    def get_status(self):
        return self.state.value


async def connect_and_subscribe(name, ws_client):
    await ws_client.connect()
    async for data in ws_client.recv():
        yield data


# async def main():
#     uri = "wss://api.ox.fun/v2/websocket"
#     proxy = "http://127.0.0.1:7890"
#     name = "SPIKE-USD-SWAP-LIN"

#     ws_client = WebSocketClient(proxy, name)

#     # 可以在这里检查状态
#     print(ws_client.get_status())  # 未连接
#     async for data in connect_and_subscribe(name, ws_client):
#         print(data)  # 在这里处理收到的数据
#         print(ws_client.get_status())  # 已连接 or 正在重连

#     await ws_client.close()


# while True:
#     print(get_dexscreener_price("2u7dcqp8j5ebtvgszfjxlsammjgm2rmpwe45g98hgjph"))
#     time.sleep(1)


# async def connect(name):
#     uri = "wss://api.ox.fun/v2/websocket"
#     proxy = "http://127.0.0.1:7890"

#     async with websockets_proxy.proxy_connect(
#         uri, proxy=websockets_proxy.Proxy.from_url(proxy)
#     ) as ws:
#         data = {
#             "op": "subscribe",
#             "args": [
#                 f"futures/depth:{name}",
#                 f"candles60s:{name}",
#             ],
#             "tag": "1721232465385",
#         }

#         await ws.send(json.dumps(data))

#         async for message in ws:
#             data = json.loads(message)

#             if not "table" in data:
#                 continue

#             kind = data["table"]

#             if kind == "candles60s":
#                 print(data["data"])
#             elif kind == "futures/depth":
#                 print(data["data"])


# asks 是卖 bids 是买
# {"table":"candles60s","data":[{"candle":["1721233380000","0.000799","0.000799","0.000799","0.000799","0","0"],"marketCode":"SPIKE-USD-SWAP-LIN"}]}
# {"table":"futures/depth","data":[{"seqNum":434172011379466169,"instrumentId":"SPIKE-USD-SWAP-LIN","asks":[[0.000842,54701490.0],[0.000866,44998690.0],[0.000892,33108960.0],[0.010305,95460.0]],"checksum":2924021925,"bids":[[0.000741,80192910.0],[0.000716,35510220.0],[0.000691,37598350.0]],"timestamp":"1721233360383"}],"action":"partial"}

# asyncio.run(connect())


# def start_client(pair, name, callback):
#     pass


import json
from rich.console import Console
from rich.table import Table
import rich
from rich.live import Live

from typing import List, Tuple, Dict

# def ok(result):
#     if isinstance(result, BaseException):
#         print(result)
#         return False
#     else:
#         return True


async def main():
    with open("config.json", "r") as file:
        data = json.load(file)

    proxy = data.get("proxy")
    interval = data.get("interval", 0.5)
    timeout = data.get("timeout", 3)

    pair_list = [i["pair"] for i in data["product"]]
    name_list = [i["name"] for i in data["product"]]

    assert len(pair_list) == len(name_list)

    ping_list = [None for _ in pair_list]
    dexscreener_price_list = [None for _ in pair_list]
    ox_fun_price_list = [None for _ in name_list]
    ox_fun_depth_list = [None for _ in name_list]

    for pair in pair_list:
        console.log(f"test pair: {pair}")

        result = await get_dexscreener_price(pair, proxy)

        if isinstance(result, BaseException):
            raise result

    console.log("connect ox.fun")

    ws = WebSocketClient(proxy, name_list)

    result = await ws.connect()

    if isinstance(result, BaseException):
        raise result

    ws.start_connect_loop()

    async def task1(index, interval):
        async def sub_task():
            result = await get_dexscreener_price(pair_list[index], proxy)

            if not isinstance(result, BaseException):
                dexscreener_price_list[index] = result

        while True:
            start_time = time.time()

            ping_list[index] = time.time()

            await sub_task()

            display()

            elapsed_time = time.time() - start_time

            if elapsed_time < interval:
                await asyncio.sleep(interval - elapsed_time)

            await asyncio.sleep(random.uniform(1, 2))

    async def task2():
        async for result in ws.recv():
            if result and "table" in result:
                table = result["table"]
                if table == "candles60s":
                    for i in result["data"]:
                        ox_fun_price_list[name_list.index(i["marketCode"])] = i[
                            "candle"
                        ][4]
                elif table == "futures/depth":
                    for i in result["data"]:
                        ox_fun_depth_list[name_list.index(i["instrumentId"])] = [
                            i["bids"],
                            i["asks"],
                        ]
                display()

    task_list = []

    for i in range(len(pair_list)):
        task_list.append(asyncio.create_task(task1(i, interval)))

    task_list.append(asyncio.create_task(task2()))

    console.clear()

    def display():
        global ping_time

        table = Table(show_header=True, box=rich.box.DOUBLE)
        table.add_column("延迟", justify="center", max_width=16)
        table.add_column(
            "产品",
            justify="center",
        )
        table.add_column("dexscreener.com", justify="center")
        table.add_column("ox.fun", justify="center")
        table.add_column("买1", justify="center")
        table.add_column("卖1", justify="center")
        table.add_column("买卖价差 abs(buy - sell) / sell", justify="center")
        table.add_column("价格差 (a - b) / b", justify="center")
        table.add_column(
            "价差调整值 abs(a - b) / b * 2 - abs(buy - sell) / sell", justify="center"
        )

        for index, value in enumerate(name_list):
            if ping_list[index]:
                time_diff = time.time() - ping_list[index]
            else:
                time_diff = 0

            dexscreener_price = dexscreener_price_list[index]
            ox_fun_price = ox_fun_price_list[index]

            if dexscreener_price and ox_fun_price:
                diff = float(dexscreener_price) - float(ox_fun_price)

                try:
                    rate = diff / float(ox_fun_price) * 100
                    rate_real = abs(diff) / float(ox_fun_price)
                except ZeroDivisionError:
                    rate = 0
                    rate_real = 0
            else:
                diff = 0
                rate = 0
                rate_real = 0

            buy1 = ox_fun_depth_list[index]
            sell1 = ox_fun_depth_list[index]

            if buy1 and sell1:
                try:
                    buy1 = buy1[0][0][0]
                    sell1 = sell1[1][0][0]
                except IndexError:
                    buy1 = 0
                    sell1 = 0

                try:
                    buy_sell_diff = abs(float(buy1) - float(sell1))
                    buy_sell_rate = buy_sell_diff / float(sell1) * 100
                    buy_sell_rate_real = buy_sell_diff / float(sell1)
                except ZeroDivisionError:
                    buy_sell_rate = 0
                    buy_sell_rate_real = 0
            else:
                buy_sell_diff = 0
                buy_sell_rate = 0
                buy_sell_rate_real = 0

            diff_mod = rate_real * 2 - buy_sell_rate_real

            table.add_row(
                f"{time_diff:.2f}s {ws.get_status()}",
                value,
                str(dexscreener_price),
                str(ox_fun_price),
                f"[red]{buy1}",
                f"[green]{sell1}",
                (f"{buy_sell_diff:.10f}").rstrip("0").rstrip(".")
                + f" ({buy_sell_rate:.2f}%)",
                (f"[red]{diff:+.10f}" if diff > 0 else f"[green]{diff:+.10f}")
                .rstrip("0")
                .rstrip(".")
                + (f"[red] ({rate:+.2f}%)" if diff > 0 else f"[green] ({rate:+.2f}%)"),
                (f"[red]{diff_mod:.10f}" if diff_mod > 0 else f"[green]{diff_mod:.10f}")
                .rstrip("0")
                .rstrip(".")
                + (
                    f"[red] ({diff_mod * 100:.2f}%)"
                    if diff_mod > 0
                    else f"[green] ({diff_mod * 100:.2f}%)"
                ),
            )

        live.update(table)

    for i in task_list:
        await i


try:
    session: aiohttp.ClientSession = None
    amm_id_cache = {}
    console = Console(record=True)
    live = Live()
    live.__enter__()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
except asyncio.CancelledError:
    pass
except KeyboardInterrupt:
    pass
except BaseException:
    traceback.print_exc()

input("press any key to exit...")

# import io
# import avro.schema
# from avro.io import DatumReader
# from avro.io import BinaryDecoder

# # 定义 Avro Schema
# schema = {
#     "type": "record",
#     "name": "BarSchema",
#     "fields": [
#         {"name": "schemaVersion", "type": "string"},
#         {
#             "name": "bars",
#             "type": {
#                 "type": "array",
#                 "items": {
#                     "type": "record",
#                     "name": "CustomBar",
#                     "fields": [
#                         {"name": "timestamp", "type": "double"},
#                         {"name": "open", "type": "string"},
#                         {
#                             "name": "openUsd",
#                             "type": ["null", "string"],
#                             "default": None,
#                         },
#                         {"name": "high", "type": "string"},
#                         {
#                             "name": "highUsd",
#                             "type": ["null", "string"],
#                             "default": None,
#                         },
#                         {"name": "low", "type": "string"},
#                         {"name": "lowUsd", "type": ["null", "string"], "default": None},
#                         {"name": "close", "type": "string"},
#                         {
#                             "name": "closeUsd",
#                             "type": ["null", "string"],
#                             "default": None,
#                         },
#                         {
#                             "name": "volumeUsd",
#                             "type": ["null", "string"],
#                             "default": None,
#                         },
#                         {"name": "minBlockNumber", "type": "double"},
#                         {"name": "maxBlockNumber", "type": "double"},
#                     ],
#                 },
#             },
#         },
#     ],
# }

# schema = """
# {
#   "type": "record",
#   "name": "BarSchema",
#   "fields": [
#     {"name": "schemaVersion", "type": "string"},
#     {
#       "name": "bars",
#       "type": {
#         "type": "array",
#         "items": {
#           "type": "record",
#           "name": "CustomBar",
#           "fields": [
#             {"name": "timestamp", "type": "double"},
#             {"name": "open", "type": "string"},
#             {
#               "name": "openUsd",
#               "type": ["null", "string"],
#               "default": null
#             },
#             {"name": "high", "type": "string"},
#             {
#               "name": "highUsd",
#               "type": ["null", "string"],
#               "default": null
#             },
#             {"name": "low", "type": "string"},
#             {"name": "lowUsd", "type": ["null", "string"], "default": null},
#             {"name": "close", "type": "string"},
#             {
#               "name": "closeUsd",
#               "type": ["null", "string"],
#               "default": null
#             },
#             {
#               "name": "volumeUsd",
#               "type": ["null", "string"],
#               "default": null
#             },
#             {"name": "minBlockNumber", "type": "double"},
#             {"name": "maxBlockNumber", "type": "double"}
#           ]
#         }
#       }
#     }
#   ]
# }
# """

# # 加密的数据
# data = b"\n1.0.0\x02\x04\x00\x80\x99\x06\x92\x0cyB\x140.00001877\x02\x0e0.06434\x140.00001864\x02\x0e0.06389\x140.00001864\x02\x0e0.06389\x140.00001864\x02\x0e0.06389\x02\x0e3804.95\x00\x00\x00\x00VesA\x00\x00\x00\x00VesA\x00\x80\x87\t\x92\x0cyB\x140.00001864\x02\x0e0.06389\x140.00001880\x02\x0e0.06445\x140.00001880\x02\x0e0.06445\x140.00001880\x02\x0e0.06445\x02\x1025754.56\x00\x00\x00\x10VesA\x00\x00\x00\x10VesA"


# # 解码数据
# def decode_avro(data, schema):
#     reader = DatumReader(schema)
#     bytes_reader = io.BytesIO(data)
#     decoder = BinaryDecoder(bytes_reader)
#     decoded_data = reader.read(decoder)
#     return decoded_data


# decoded_data = decode_avro(data, avro.schema.parse(schema))
# print(decoded_data)


# import fastavro
# from io import BytesIO

# schema = {
#     "type": "record",
#     "name": "barsSchema",
#     "fields": [
#         {"name": "schemaVersion", "type": "string"},
#         {
#             "name": "bars",
#             "type": [
#                 "null",
#                 {
#                     "type": "array",
#                     "items": {
#                         "type": "record",
#                         "name": "customBarObject",
#                         "fields": [
#                             {"name": "timestamp", "type": "double"},
#                             {"name": "open", "type": "string"},
#                             {"name": "openUsd", "type": ["null", "string"]},
#                             {"name": "high", "type": "string"},
#                             {"name": "highUsd", "type": ["null", "string"]},
#                             {"name": "low", "type": "string"},
#                             {"name": "lowUsd", "type": ["null", "string"]},
#                             {"name": "close", "type": "string"},
#                             {"name": "closeUsd", "type": ["null", "string"]},
#                             {"name": "volumeUsd", "type": ["null", "string"]},
#                             {"name": "minBlockNumber", "type": "double"},
#                             {"name": "maxBlockNumber", "type": "double"},
#                         ],
#                     },
#                 },
#             ],
#         },
#     ],
# }

# data = b"1.0.0\x02\x04\x00\x80\x99\x06\x92\x0cyB\x140.00001877\x02\x0e0.06434\x140.00001864\x02\x0e0.06389\x140.00001864\x02\x0e0.06389\x140.00001864\x02\x0e0.06389\x02\x0e3804.95\x00\x00\x00\x00VesA\x00\x00\x00\x00VesA\x00\x80\x87\t\x92\x0cyB\x140.00001864\x02\x0e0.06389\x140.00001880\x02\x0e0.06445\x140.00001880\x02\x0e0.06445\x140.00001880\x02\x0e0.06445\x02\x1025754.56\x00\x00\x00\x10VesA\x00\x00\x00\x10VesA"

# with open("./aaa", "wb") as f:
#     f.write(data)

# # 解析 Avro 数据
# bytes_reader = BytesIO(data)
# avro_reader = fastavro.reader(bytes_reader, schema)

# for record in avro_reader:
#     print(record)
