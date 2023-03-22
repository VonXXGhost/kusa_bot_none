from typing import Tuple, List, Optional
import tomlkit
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot_plugin_guild_patch import GuildMessageEvent
from tomlkit.toml_document import TOMLDocument
from nonebot import Bot, get_bot
from nonebot.log import logger


# region config
def load_config() -> TOMLDocument:
    with open("config/yashima_config.toml", "r", encoding="utf-8") as file:
        content = file.read()
        logger.info(f"加载yashima_config.toml结果：\n{content}")
        return tomlkit.parse(content)


bot_config = load_config()


def get_config() -> TOMLDocument:
    return bot_config


def reload_config() -> TOMLDocument:
    global bot_config
    bot_config = load_config()
    return bot_config
# endregion config


def at_user(event: GuildMessageEvent) -> MessageSegment:
    return MessageSegment.at(event.get_user_id())


def get_sender_id_and_nickname(event: GuildMessageEvent) -> Tuple[str, str]:
    return event.get_user_id(), event.sender.nickname


def get_active_guild_id() -> str:
    return bot_config['guild']['id']


async def get_guild_rules(bot: Bot) -> List[dict]:
    return await bot.get_guild_roles(guild_id=get_active_guild_id())


guild_roles: Optional[List[dict]] = None


async def init_guild_roles():
    global guild_roles
    guild_roles = await get_guild_rules(get_bot())
    logger.info(f"当前身分组列表：{guild_roles}")


async def get_role_id_named(role_name: str) -> Optional[str]:
    if not guild_roles:
        await init_guild_roles()
    for role in guild_roles:
        if role['role_name'] == role_name:
            return role['role_id']
    logger.warning(f"未匹配到身分组[{role_name}]")
    return None


async def set_role(active: bool, role_id: str, user_id: str):
    await get_bot().set_guild_member_role(
        guild_id=get_active_guild_id(), set=active, role_id=role_id, users=[user_id])
