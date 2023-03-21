import re
from typing import Optional

import aiohttp
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.log import logger
from nonebot.plugin import on_message


async def booru_msg_checker(event: GroupMessageEvent) -> bool:
    return "sakugabooru.com/post/show/" in event.get_plaintext()


matcher = on_message(rule=booru_msg_checker)


@matcher.handle()
async def _(event: GroupMessageEvent):
    message = event.get_plaintext()
    ids = re.findall(r'(?<=post/show/)(\d+)', message)
    if not ids:
        return
    # 如果有多条，只取第一个处理，太多的话回复太长了
    pid = ids[0]
    weibo_data = await get_weibo_data(pid)
    if not weibo_data:
        return
    text = gene_reply_text(weibo_data)
    reply = f"{pid}:\n{text}"
    logger.info(f"回复消息->[{event.user_id}]@[{event.group_id}]: {reply}")
    await matcher.send(reply)


async def get_weibo_data(pid: str) -> Optional[dict]:
    """
    获取微博bot信息
    :param pid: post id
    :return:
    """
    async with aiohttp.ClientSession() as seesion:
        async with seesion.get(f"https://sakugabot.pw/api/posts/{pid}/?format=json") as resp:
            json = await resp.json()
            if not json['weibo']:
                logger.info(f"Post[{pid}]微博数据不存在")
                return None
            return json


def get_copyright(weibo_data: dict) -> str:
    tags = list(filter(lambda t: int(t["type"]) == 3, weibo_data['tags']))
    return ",".join(map(lambda t: t["main_name"], tags)) or ""


def get_artist(weibo_data: dict) -> str:
    tags = list(filter(lambda t: int(t["type"]) == 1, weibo_data['tags']))
    return ",".join(map(lambda t: t["main_name"], tags)) or ""


def gene_reply_text(weibo_data: dict) -> str:
    cr, artist = get_copyright(weibo_data), get_artist(weibo_data)
    source = weibo_data["source"] or ""
    return f"{cr} {source} {artist}"
