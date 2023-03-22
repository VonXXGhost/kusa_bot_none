"""
自习打卡：
@bot 自习帮助
@bot 开始自习
@bot 结束自习
@bot 我的自习数据
@bot 自习修正 3小时30分
"""
import re
from typing import Optional

from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot_plugin_apscheduler import scheduler
from datetime import timedelta
from .db import *
from .utils import *


async def clock_in_handle(matcher: Matcher, event: GuildMessageEvent):
    # 检查上一次是否为自动签退
    overtime_model = ClockEventLog.query_overtime(event.get_user_id())
    if overtime_model:
        await matcher.send(at_user(event)
                           + f"上一次自习({overtime_model.start_time.month}月{overtime_model.start_time.day}日)"
                             f"被自动签退，请先按命令格式'自习修正 3小时30分'修正上次自习数据")
        return
    # 检查是否正在自习
    working_model = ClockEventLog.query_working(event.get_user_id())
    if working_model:
        await matcher.send(at_user(event) + f"你已经打过卡惹")
        return
    # 入库
    user_id, user_name = get_sender_id_and_nickname(event)
    model = ClockEventLog(user_name=user_name, user_id=user_id, status=ClockStatus.WORKING.value)
    model.save()
    await matcher.send(at_user(event) + "已成功打卡，开始自习")
    # 修改用户组
    role_id = await get_role_id_named(get_config()['guild']['clock_role_name'])
    if role_id:
        await set_role(True, role_id, user_id)


async def clock_out_handle(matcher: Matcher, event: GuildMessageEvent):
    working_model = ClockEventLog.query_working(event.get_user_id())
    if not working_model:
        await matcher.send(at_user(event) + f"没有正在进行中的自习打卡记录")
        return
    working_model.end_time = datetime.now()
    working_model.status = ClockStatus.FINISH.value
    duration = working_model.update_duration()
    working_model.save()

    hour = int(duration / 60)
    minu = duration % 60
    await matcher.send(at_user(event) + f"已结束自习，本次自习时长{hour}小时{minu}分钟")
    # 修改用户组
    role_id = await get_role_id_named(get_config()['guild']['clock_role_name'])
    if role_id:
        await set_role(False, role_id, event.get_user_id())


def clock_channel_id() -> str:
    return get_config()['guild']['clock_channel_id']


def is_clock_channel(event: GuildMessageEvent) -> bool:
    return clock_channel_id() == str(event.channel_id)


@scheduler.scheduled_job('interval', minutes=1, id="clock_find_overtime_and_process")
async def find_overtime_and_process():
    overtime = get_config()['guild']['clock_overtime']
    model_iter = (ClockEventLog.select()
                  .where((ClockEventLog.status == ClockStatus.WORKING.value)
                         & (ClockEventLog.start_time < (datetime.now() - timedelta(minutes=overtime)))))
    for model in model_iter:
        model.end_time = model.start_time + timedelta(minutes=overtime)
        model.status = ClockStatus.OVERTIME.value
        model.update_duration()
        model.save()
        msg = MessageSegment.at(model.user_id) + "自习已超时自动签退，记得修正数据ヾ(￣▽￣)"
        await get_bot().send_guild_channel_msg(guild_id=get_active_guild_id(), channel_id=clock_channel_id(),
                                               message=msg)
    logger.debug("find_overtime_and_process end")
