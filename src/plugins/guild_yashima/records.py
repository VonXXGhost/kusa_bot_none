"""
消息存储、词云等
有参考 https://github.com/he0119/nonebot-plugin-wordcloud
"""
import asyncio
import concurrent.futures
import datetime
import json
import re
from datetime import timedelta
from functools import partial, reduce
from io import BytesIO
from typing import Dict

import jieba
import jieba.analyse
import jsonpath_ng as jsonpath
from emoji import replace_emoji
from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import EventMessage, CommandArg
from nonebot_plugin_apscheduler import scheduler
from wordcloud import WordCloud

from .db import *
from .utils import *


async def save_recv_guild_msg_handle(event: GuildMessageEvent):
    """保存所有频道文本消息"""
    msg = event.get_plaintext()
    if len(msg) > 1000 or msg == '':
        return
    model = GuildMessageRecord(channel_id=event.channel_id, user_id=event.get_user_id(), content=msg)
    model.save()


@scheduler.scheduled_job('interval', minutes=30, id="clear_overtime_message_record")
async def clear_overtime_message_record():
    msg_save_days = int(get_config()['db']['msg_save_days'])
    q = (GuildMessageRecord
         .delete()
         .where(GuildMessageRecord.recv_time < (datetime.now() - timedelta(days=msg_save_days))))
    num = q.execute()
    if num > 0:
        logger.info(f"已删除频道聊天记录{num}条")


async def resent_pc_unreadable_msg_handle(matcher: Matcher, _: GuildMessageEvent, message: Message = EventMessage()):
    """解析PC不可读消息并转换发送"""
    if message.count('json') == 0:
        return
    segment = message['json', 0]
    json_data = json.loads(segment.get('data').get('data'))

    def get_json(path: str):
        try:
            return jsonpath.parse(path).find(json_data)[0].value
        except IndexError:
            return None

    app = get_json('$.app')
    link, title = None, None

    if app == 'com.tencent.channel.share':
        link = get_json('$.meta.detail.link')
        title = get_json('$.meta.detail.title')
    elif app == 'com.tencent.miniapp_01':
        link = get_json('$.meta.detail_1.qqdocurl')
        title = get_json('$.meta.detail_1.desc')
    elif app == 'com.tencent.structmsg':
        view = get_json('$.view')
        link = get_json(f'$.meta.{view}.jumpUrl')
        title = get_json(f'$.meta.{view}.title')

    if not link \
            or len(link) > 300 \
            or not link.startswith('http'):
        return
    if len(title) > 50:
        title = title[:50] + "…"
    elif not title:
        title = '未解析到标题'

    # 处理url防止qq二度解析（在http后添加一个零宽空格）
    # link = link.replace("http", "http\u200b")
    to_sent = f"🔗 For Pc：\n{title}\n{link}"
    await matcher.send(to_sent)


async def yesterday_wordcloud_handle(matcher: Matcher, event: GuildMessageEvent, args: Message = CommandArg()):
    yesterday = datetime.now() - timedelta(days=1)
    start_time = yesterday.replace(hour=0, minute=10, second=0, microsecond=0)
    end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
    channel_id = args.extract_plain_text()

    channels = query_wordcloud_generative_channel_ids(start_time, end_time)
    logger.info(f"以下频道将生成词云：{channels}")

    resp = '指定子频'
    if not channel_id:
        channel_id = event.channel_id
        resp = '本子频'
    else:
        channel_id = int(channel_id)
    image = await get_wordcloud_by_time(channel_id, start_time, end_time)
    if image:
        await matcher.send(f'已生成{resp}昨日词云' + MessageSegment.image(image))
    else:
        await matcher.send(at_user(event) + f'{resp}缺少足够的聊天记录生成词云')


@scheduler.scheduled_job('cron', minute='1', hour='0', id="yesterday_wordcloud_job")
async def yesterday_wordcloud_job():
    yesterday = datetime.now() - timedelta(days=1)
    start_time = yesterday.replace(hour=0, minute=10, second=0, microsecond=0)
    end_time = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)
    channels = query_wordcloud_generative_channel_ids(start_time, end_time)
    logger.info(f"以下频道将生成词云：{channels}")

    for channel in channels:
        logger.info(f'开始生成词云，频道ID:{channel}')
        try:
            image = await get_wordcloud_by_time(channel, start_time, end_time)
            if image:
                msg = '已生成本子频昨日词云' + MessageSegment.image(image)
                await get_bot().send_guild_channel_msg(guild_id=get_active_guild_id(), channel_id=channel,
                                                       message=msg)
        except Exception as ex:
            logger.error('生成词云异常', ex)

    logger.info(f'开始生成全频道词云')
    image = await get_wordcloud_by_time(0, start_time, end_time)
    if image:
        msg = '已生成全频道昨日词云' + MessageSegment.image(image)
        await get_bot().send_guild_channel_msg(guild_id=get_active_guild_id(),
                                               channel_id=get_config()['wordcloud']['overall_target_channel'],
                                               message=msg)


def query_wordcloud_generative_channel_ids(start_time: datetime, end_time: datetime) -> List[int]:
    """查找符合生成词云条件的所有子频道"""
    threshold = get_config()['wordcloud']['generation_threshold']
    query = (GuildMessageRecord
             .select(GuildMessageRecord.channel_id, fn.COUNT(GuildMessageRecord.channel_id).alias('cnt'))
             .where((GuildMessageRecord.recv_time > start_time)
                    & (GuildMessageRecord.recv_time < end_time))
             .group_by(GuildMessageRecord.channel_id)
             .having(fn.COUNT(GuildMessageRecord.channel_id) > threshold))
    return [model.channel_id for model in query]


async def get_wordcloud_by_time(channel_id: int, start_time: datetime, end_time: datetime) -> Optional[BytesIO]:
    """channel_id等于0时，查找所有子频道记录"""
    import operator
    expressions = [(GuildMessageRecord.recv_time > start_time),
                   (GuildMessageRecord.recv_time < end_time)]
    if channel_id != 0:
        expressions.append(GuildMessageRecord.channel_id == channel_id)
    else:
        blacklist_channels = get_config()['wordcloud']['blacklist_channels']
        expressions.append(GuildMessageRecord.channel_id.not_in(blacklist_channels))
    blacklist = get_config()['wordcloud']['blacklist_user_ids']
    if blacklist:
        expressions.append(GuildMessageRecord.user_id.not_in(blacklist))

    query = (GuildMessageRecord
             .select()
             .where(reduce(operator.and_, expressions)))
    messages = [model.content for model in query]
    threshold = get_config()['wordcloud']['generation_threshold']
    if len(messages) < threshold:
        logger.info(f"子频道[{channel_id}]时间范围内记录数量过少({len(messages)})，不生成词云")
        return None
    return await get_wordcloud(messages)


def pre_precess(msg: str) -> str:
    """对消息进行预处理"""
    # 去除网址
    # https://stackoverflow.com/a/17773849/9212748
    msg = re.sub(
        r"(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})",
        "",
        msg,
    )
    # 去除 \u200b
    msg = re.sub(r"\u200b", "", msg)
    # 去除 emoji
    # https://github.com/carpedm20/emoji
    msg = replace_emoji(msg)
    return msg


def analyse_message(msg: str) -> Dict[str, float]:
    """分析消息
    分词，并统计词频
    """
    # 设置停用词表
    if get_config()['wordcloud']['stopwords_path']:
        jieba.analyse.set_stop_words(get_config()['wordcloud']['stopwords_path'])
    # 加载用户词典
    # if plugin_config.wordcloud_userdict_path:
    #     jieba.load_userdict(str(plugin_config.wordcloud_userdict_path))
    # 基于 TF-IDF 算法的关键词抽取
    # 返回所有关键词，因为设置了数量其实也只是 tags[:topK]，不如交给词云库处理
    words = jieba.analyse.extract_tags(msg, topK=0, withWeight=True)
    return {word: weight for word, weight in words}


def _get_wordcloud(messages: List[str]) -> Optional[BytesIO]:
    message = " ".join(messages)
    # 预处理
    message = pre_precess(message)
    # 分析消息。分词，并统计词频
    frequency = analyse_message(message)
    # 词云参数
    wordcloud_options = {}
    wordcloud_options.update(get_config()['wordcloud']['options'])
    wordcloud_options.setdefault("font_path", str(get_config()['wordcloud']['font_path']))
    wordcloud_options.setdefault("width", get_config()['wordcloud']['width'])
    wordcloud_options.setdefault("height", get_config()['wordcloud']['height'])
    wordcloud_options.setdefault(
        "background_color", get_config()['wordcloud']['background_color']
    )
    wordcloud_options.setdefault("colormap", get_config()['wordcloud']['colormap'])
    try:
        wordcloud = WordCloud(**wordcloud_options)
        image = wordcloud.generate_from_frequencies(frequency).to_image()
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        return image_bytes
    except ValueError:
        pass


async def get_wordcloud(messages: List[str]) -> Optional[BytesIO]:
    loop = asyncio.get_running_loop()
    pfunc = partial(_get_wordcloud, messages)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, pfunc)
