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
        await matcher.send(at_user(event) + f"你已经打过卡了")
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
    working_model.end_time = datetime.datetime.now()
    working_model.status = ClockStatus.FINISH.value
    working_model.duration = calc_duration(working_model.start_time, working_model.end_time)
    working_model.save()

    hour = int(working_model.duration / 60)
    minu = working_model.duration % 60
    await matcher.send(at_user(event) + f"已结束自习，本次自习时长{hour}小时{minu}分钟")
    # 修改用户组
    role_id = await get_role_id_named(get_config()['guild']['clock_role_name'])
    if role_id:
        await set_role(False, role_id, event.get_user_id())


def calc_duration(start_time: datetime.datetime, end_time: datetime.datetime) -> int:
    return int((end_time - start_time).total_seconds() / 60)


def is_clock_channel(event: GuildMessageEvent) -> bool:
    return get_config()['guild']['clock_channel_id'] == str(event.channel_id)


def find_overtime_and_process():
    overtime = get_config()['guild']['clock_overtime']
    for model in (ClockEventLog.select()
            .where((ClockEventLog.status == ClockStatus.WORKING.value) &
                   (ClockEventLog.start_time < (datetime.datetime.now() - datetime.timedelta(minutes=overtime))))
    ):
        model.end_time = model.start_time + datetime.timedelta(minutes=overtime)
        model.status = ClockStatus.OVERTIME.value

