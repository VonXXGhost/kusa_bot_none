"""
屋岛作战指挥部专用bot
"""
import tomlkit
from . import db
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.log import logger
from nonebot.plugin import on_fullmatch
from nonebot.rule import to_me
from nonebot_plugin_guild_patch import GuildMessageEvent
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
db.init_database(bot_config["db"]["file"])


async def is_admin_user(event: GuildMessageEvent) -> bool:
    return event.get_user_id() in bot_config['auth']['admin']


reload_config_matcher = on_fullmatch("重载配置", rule=to_me(), permission=is_admin_user)
my_id_matcher = on_fullmatch("我的ID", ignorecase=True, rule=to_me())


@reload_config_matcher.handle()
async def _(event: GuildMessageEvent):
    global bot_config
    bot_config = load_config()
    await reload_config_matcher.send(MessageSegment.at(event.get_user_id()) + "已重载配置")


@my_id_matcher.handle()
async def _(event: GuildMessageEvent):
    await my_id_matcher.send(MessageSegment.at(event.get_user_id()) + f"你的频道用户ID是{event.user_id}")
