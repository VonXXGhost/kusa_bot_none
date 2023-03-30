"""
消息存储、词云等
有参考 https://github.com/he0119/nonebot-plugin-wordcloud
"""
from .db import *
from .utils import *
from nonebot.adapters import Message
from nonebot.params import EventMessage
from nonebot_plugin_apscheduler import scheduler
from datetime import timedelta
import json
import jsonpath_ng as jsonpath
from nonebot.matcher import Matcher


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
