"""
自动通过好友请求和拉群请求
"""

from nonebot import on_request
from nonebot.adapters.onebot.v11 import Bot, GroupRequestEvent, FriendRequestEvent, RequestEvent
from nonebot.log import logger

friendRequest = on_request(priority=1, block=True)


@friendRequest.handle()
async def _(bot: Bot, event: RequestEvent):
    if isinstance(event, FriendRequestEvent):
        await event.approve(bot)
        logger.info(f"已通过好友申请：[{event.user_id}]")
    elif isinstance(event, GroupRequestEvent):
        if event.sub_type != 'invite':
            logger.info(f"跳过意外的群申请类型：[{event.sub_type}]，群[{event.group_id}]")
            return
        await event.approve(bot)
        logger.info(f"已通过加群申请：[{event.group_id}]")
