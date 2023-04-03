"""
屋岛作战指挥部专用bot
"""
from nonebot.plugin import *
from nonebot.rule import to_me

from .clock import *
from .db import *
from .utils import *
from .records import *

require("nonebot_plugin_apscheduler")

# 数据库初始化
init_database(get_config()["db"]["file"])


async def is_admin_user(event: GuildMessageEvent) -> bool:
    return event.get_user_id() in bot_config['auth']['admin']


reload_config_matcher = on_fullmatch("重载配置", rule=to_me(), permission=is_admin_user)
my_id_matcher = on_fullmatch("我的ID", ignorecase=True, rule=to_me())

# 打卡相关
clock_help = on_fullmatch("自习帮助", rule=(to_me() & is_clock_channel), handlers=[clock_help_handle])
clock_in = on_fullmatch("开始自习", rule=(to_me() & is_clock_channel), handlers=[clock_in_handle])
clock_out = on_fullmatch("结束自习", rule=(to_me() & is_clock_channel), handlers=[clock_out_handle])
clock_correct_time = on_command("自习修正", rule=(to_me() & is_clock_channel), handlers=[clock_correct_time_handle])
clock_my_statistics = on_fullmatch("我的自习", rule=(to_me() & is_clock_channel), handlers=[clock_my_statistics_handle])

# 词云相关
msg_record = on_message(handlers=[save_recv_guild_msg_handle])
resent_pc_unreadable_msg = on_message(handlers=[resent_pc_unreadable_msg_handle])
yesterday_wordcloud = on_command("昨日词云", rule=to_me(), permission=is_admin_user, handlers=[yesterday_wordcloud_handle])


@reload_config_matcher.handle()
async def _(event: GuildMessageEvent):
    reload_config()
    await reload_config_matcher.send(at_user(event) + "已重载配置")


@my_id_matcher.handle()
async def _(event: GuildMessageEvent):
    await my_id_matcher.send(at_user(event) + f"你的频道用户ID是{event.user_id}")
