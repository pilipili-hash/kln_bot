from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage, PrivateMessage
from .handler import handle_daily_fortune

bot = CompatibleEnrollment

class DailyFortune(BasePlugin):
    name = "DailyFortune"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def handle_message(self, event):
        if event.raw_message.strip() == "今日运势":
            await handle_daily_fortune(event, self.api)

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        await self.handle_message(event)

