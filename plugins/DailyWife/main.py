from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .wife_handler import get_daily_wife_message
from ncatbot.core.element import MessageChain, Text, Image, At
bot = CompatibleEnrollment

class DailyWife(BasePlugin):
    name = "DailyWife"  # 插件名称
    version = "1.0.0"  # 插件版本

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        """
        if event.raw_message.strip() == "抽老婆":
            message = await get_daily_wife_message(event)
            if message:
                await self.api.post_group_msg(event.group_id, rtf=message)
                # await self.api.post_group_msg(event.group_id,rtf=MessageChain([At(event.user_id),Text("测试")]))

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
