from dotenv import load_dotenv
from nonebot import on_command, logger
from nonebot.rule import to_me
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
    MessageSegment,
    Message,
)
from .resources import nslookup_all_records
import ipaddress
from nonebot.params import CommandArg
import aiohttp
from nonebot.matcher import Matcher
from aiohttp import ClientSession, ClientTimeout
import re
import json
import os
import ssl
import time
import asyncio
import sys


def is_in_private_network(ip_string):
    # 这是一个非常粗略且可能不准确的检查
    if (
        ip_string.startswith(
            (
                "10.",
                "172.16.",
                "172.17.",
                "172.18.",
                "172.19.",
                "172.20.",
                "172.21.",
                "172.22.",
                "172.23.",
                "172.24.",
                "172.25.",
                "172.26.",
                "172.27.",
                "172.28.",
                "172.29.",
                "172.30.",
                "172.31.",
                "192.168.",
                "169.254.",
                "fe80::",
                "fd00::",
                "fc00::",
            )
        )
        or ip_string == "::1"
    ):
        return True
    elif ip_string.startswith("127."):
        # 127.x.x.x 是回环地址，不是私有网络的一部分，但这里作为特殊情况处理
        return True
    elif ip_string == "localhost":
        return True
    return False


# 处理Dotenv配置
load_dotenv()
wget_enable: bool = os.getenv("WGET_ENABLE", True)
except_private_network: bool = os.getenv("EXCEPT_PRIVATE_NETWORK", True)
except_url_keywords: list = os.getenv("EXCEPT_URL_KEYWORDS", [])
nslookup_enable: bool = os.getenv("NSLOOKUP_ENABLE", True)

nslookup = on_command(
    "nslookup", priority=10, block=True, aliases={"ns", "NS", "NSLOOKUP"}, rule=to_me()
)
wget = on_command(
    "wget", rule=to_me(), aliases={"GET", "http"}, priority=10, block=True
)


@nslookup.handle()
async def _(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    global nslookup_enable, except_url_keywords
    if not nslookup_enable:
        matcher.skip()

    location = args.extract_plain_text()
    for i in except_url_keywords:
        if i in location:
            matcher.skip()
            return
    try:
        ipaddress.ip_address(location)
        await nslookup.send("请输入地址！格式<域名/子域名>")
        matcher.skip()
    except:
        pass
    if not location:
        await nslookup.send("请输入地址！格式<域名/子域名>")
        return
    message = MessageSegment.text(f"域名{location}的记录：\n")
    for object in nslookup_all_records(location):
        message += MessageSegment.text(f"{object}\n")
    await nslookup.send(message)


@wget.handle()
async def _(
    matcher: Matcher, bot: Bot, event: MessageEvent, args: Message = CommandArg()
):
    global wget_enable
    if not wget_enable:
        matcher.skip()
    if location := args.extract_plain_text():

        if "--tls-safe" in location:
            location = location.replace("--tls-safe", "")
            ssl_context = ssl.create_default_context()
            ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        else:
            ssl_context = False

        # 定义正则表达式模式
        pattern = r"--headers\(\{([^}]*)\}\)"

        # 使用 re.search 查找匹配
        match = re.search(pattern, location)
        location = re.sub("--headers\(\{([^}]*)\}\)", "", location)

        if match:
            #  提取匹配的内容
            json_content = match.group(1)
            logger.debug(json_content)
            try:
                json.loads(f"{json_content}")
            except json.decoder.JSONDecodeError:
                await wget.send("--headers参数格式不正确")
                return
        else:
            logger.debug("No match found")
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/19.0.1084.9 Safari/536.5"
            }

        # 设置超时时间
        timeout = ClientTimeout(total=10)  # 总超时时间，包括连接和响应

        async with ClientSession(timeout=timeout) as session:
            redirect_count = 0
            location = location.lower()
            if not location.startswith("http"):
                await wget.send(f"未填写协议，已添加http://")
                location = "http://" + location
            url = location
            while True:
                try:
                    start_time = time.time()
                    async with session.get(
                        url, headers=headers, allow_redirects=False, ssl=ssl_context
                    ) as response:
                        if not str(response.status).startswith("30"):
                            break

                        location = response.headers.get("Location", None)
                        if not location:
                            break

                        await wget.send(
                            f"收到重定向（{response.status}）到{location}，跟随中..."
                        )
                        redirect_count += 1

                        if redirect_count >= 20:
                            await wget.send("请求出错：重定向次数过多！已停止跟踪。")
                            return
                        # 转换为毫秒并保留两位小数
                        url = location
                except asyncio.TimeoutError:
                    end_time = time.time()
                    await wget.send("GET超时！")
                    logger.warning("GET超时！")
                    return
                except aiohttp.client_exceptions.ClientConnectionError as e:
                    end_time = time.time()
                    await wget.send(f"客户端连接错误: {e}")
                    logger.error(e)
                    return
                except aiohttp.client_exceptions.ClientResponseError as e:
                    end_time = time.time()
                    # 捕获并处理其他客户端响应错误，比如404, 500等
                    await wget.send(f"发生了错误: {e.status} - {e.message}")
                    logger.error(f"发生了错误: {e.status} - {e.message}")
                    logger.error(e)
                    return
                except Exception:
                    end_time = time.time()
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    logger.error(f"Exception type: {exc_type.__name__}")
                    logger.error(f"Exception message: {str(exc_value)}")
                    import traceback

                    logger.error(
                        f"Detailed exception info:\n{''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))}"
                    )
                    await wget.send(f"请求出错：{str(exc_value)}")
                    return

            if response:

                end_time = time.time()
                latency = round((end_time - start_time) * 1000, 2)
                await wget.send(
                    f"HTTP版本：{response.version}\n响应码：{response.status}\n状态描述：{response.reason}\nURL：{response.url}\n响应延迟：{latency}ms"
                )
                logger.debug(
                    f"HTTP版本：{response.version}\n响应码：{response.status}\n状态描述：{response.reason}\nURL：{response.url}\n响应延迟：{latency}ms"
                )
            else:
                await wget.send("无法获取响应。")
                logger.error("无法获取响应。")
    else:
        await wget.send("请提供有效的 URL！")
        return
