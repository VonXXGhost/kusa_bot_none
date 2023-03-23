"""
自习打卡：
@bot 自习帮助
@bot 开始自习
@bot 结束自习
@bot 我的自习数据
@bot 自习修正 3小时30分
"""
import re
from datetime import timedelta

from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot_plugin_apscheduler import scheduler

from .db import *
from .utils import *


async def clock_help_handle(matcher: Matcher, _: GuildMessageEvent):
    msg = f"""自习打卡相关指令。每次自习最长时间为{get_config()['guild']['clock_overtime']}分钟，超时未结束将自动签退，需修正时间后才能开始新的自习。
@bot 自习帮助
@bot 开始自习
@bot 结束自习
@bot 我的自习   （查询自己的自习统计数据）
@bot /自习修正 3小时30分（或者'2小时'、'45分'等，时长也不能超过上述最长时间，注意开头斜杠）"""
    await matcher.send(msg)


async def clock_my_statistics_handle(matcher: Matcher, event: GuildMessageEvent):
    user_id = event.get_user_id()
    # 自习次数
    clock_count = (ClockEventLog.select()
                   .where((ClockEventLog.status == ClockStatus.FINISH.value) & (ClockEventLog.user_id == user_id))
                   .count())
    # 自习总时长
    total_duration = (ClockEventLog.select(fn.SUM(ClockEventLog.duration).alias('sum_value'))
                      .where((ClockEventLog.status == ClockStatus.FINISH.value)
                             & (ClockEventLog.user_id == user_id))
                      .scalar())
    msg = f"你的自习次数：{clock_count}；总时长：{ClockEventLog.to_duration_desc(total_duration)}"
    await matcher.send(at_user(event) + msg)


async def clock_in_handle(matcher: Matcher, event: GuildMessageEvent):
    # 检查上一次是否为自动签退
    overtime_model = ClockEventLog.query_overtime(event.get_user_id())
    if overtime_model:
        await matcher.send(at_user(event)
                           + f"上一次自习({overtime_model.start_time.month}月{overtime_model.start_time.day}日)"
                             f"被自动签退，请先按命令格式'/自习修正 3小时30分'修正上次自习数据")
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
    working_model.update_duration()
    working_model.save()

    await matcher.send(at_user(event) + f"已结束自习，本次自习时长{working_model.duration_desc()}")
    # 修改用户组
    role_id = await get_role_id_named(get_config()['guild']['clock_role_name'])
    if role_id:
        await set_role(False, role_id, event.get_user_id())


async def clock_correct_time_handle(matcher: Matcher, event: GuildMessageEvent, args: Message = CommandArg()):
    model = ClockEventLog.query_overtime(event.get_user_id())
    if not model:
        await matcher.send(at_user(event) + f"没有需要修正的记录")
        return
    correct_time = args.extract_plain_text().strip()
    match = re.match(r"((?P<hour>\d+)(时|小时))?((?P<minute>\d+)(分|分钟))?", correct_time)
    if not match:
        await matcher.send(at_user(event) + f"时间格式不正确，请检查应为'3小时30分'、'2小时'、'45分'的格式")
        return
    hour = int(match.group('hour')) if match.group('hour') else 0
    minute = int(match.group('minute')) if match.group('minute') else 0
    total_minute = 60 * hour + minute
    if total_minute == 0:
        await matcher.send(at_user(event) + f"时间格式不正确，请检查应为'3小时30分'、'2小时'、'45分'的格式")
        return

    end_time = model.start_time + timedelta(minutes=total_minute)
    end_time = end_time if end_time < datetime.now() else datetime.now()
    model.end_time = end_time
    model.update_duration()
    model.status = ClockStatus.FINISH.value
    model.save()

    await matcher.send(at_user(event) + f"已修正上次自习时长为{model.duration_desc()}")


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


def clock_channel_id() -> str:
    return get_config()['guild']['clock_channel_id']


def is_clock_channel(event: GuildMessageEvent) -> bool:
    return clock_channel_id() == str(event.channel_id)
