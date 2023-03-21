"""
屋岛作战指挥部专用bot
"""
import tomlkit
from nonebot.params import CommandArg
from nonebot.adapters import Message

from .db import *
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger
from nonebot.plugin import *
from nonebot.rule import to_me
from nonebot_plugin_guild_patch import GuildMessageEvent, GUILD_ADMIN, GUILD_OWNER
from tomlkit.toml_document import TOMLDocument


# region config
def load_config() -> TOMLDocument:
    with open("config/yashima_config.toml", "r", encoding="utf-8") as file:
        content = file.read()
        logger.info(f"加载yashima_config.toml结果：\n{content}")
        return tomlkit.parse(content)


bot_config = load_config()
# endregion config

# 数据库初始化
init_database(bot_config["db"]["file"])


async def is_admin_user(event: GuildMessageEvent) -> bool:
    return event.get_user_id() in bot_config['auth']['admin']


reload_config_matcher = on_fullmatch("重载配置", rule=to_me(), permission=is_admin_user)
my_id_matcher = on_fullmatch("我的ID", ignorecase=True, rule=to_me())

# 直播日程相关命令
stream_schedule_help_matcher = on_command("直播日程命令说明", rule=to_me())
adjust_stream_schedule_matcher = on_command("直播日程调整", rule=to_me(), permission=(GUILD_ADMIN | GUILD_OWNER))


@reload_config_matcher.handle()
async def _(event: GuildMessageEvent):
    global bot_config
    bot_config = load_config()
    await reload_config_matcher.send(at_user(event) + "已重载配置")


@my_id_matcher.handle()
async def _(event: GuildMessageEvent):
    await my_id_matcher.send(at_user(event) + f"你的频道用户ID是{event.user_id}")


@stream_schedule_help_matcher.handle()
async def _(_: GuildMessageEvent):
    msg = """/直播日程调整 作品名 每周六 23:00
    """
    await stream_schedule_help_matcher.send(msg)


@adjust_stream_schedule_matcher.handle()
async def _(event: GuildMessageEvent, args: Message = CommandArg()):
    def extract_args(msg: str) -> Tuple[str, str, str]:
        msg = msg.strip()
        sp = msg.split(" ")
        if len(sp) != 3:
            return "", "", ""
        return sp[0], sp[1], sp[2]

    work, date_s, time_s = extract_args(args.extract_plain_text())
    if not (work and date_s and time_s):
        await adjust_stream_schedule_matcher.send(at_user(event) + "日程调整格式不正确，请检查/直播日程命令说明")
        return
    user_id, user_name = get_sender_id_and_nickname(event)
    model = StreamSchedule(work_name=work, date_schedule=date_s, time_schedule=time_s,
                           update_user_id=user_id, update_user_nickname=user_name)
    try:
        if model.save():
            await adjust_stream_schedule_matcher.send(at_user(event) + f"{work} 日程调整成功")
        else:
            await adjust_stream_schedule_matcher.send(at_user(event) + f"{work} 日程调整未生效")
    except Exception as err:
        logger.error(f"日程调整失败: {err}")
        await adjust_stream_schedule_matcher.send(at_user(event) + f"{work} 日程调整失败，请联系bot管理")
        raise


def at_user(event: GuildMessageEvent) -> MessageSegment:
    return MessageSegment.at(event.get_user_id())


def get_sender_id_and_nickname(event: GuildMessageEvent) -> Tuple[str, str]:
    return event.get_user_id(), event.sender.nickname
