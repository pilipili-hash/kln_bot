import random
import json
import os
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from PluginManager.plugin_manager import feature_required

bot = CompatibleEnrollment

class KfcThursday(BasePlugin):
    name = "KfcThursday"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        # 使用 os 模块加载文案数据
        quotes_path = os.path.join(os.getcwd(), "static", "kfc/v50.json")
        with open(quotes_path, "r", encoding="utf-8") as file:
            self.kfc_quotes = json.load(file)

    @bot.group_event()
    @feature_required(feature_name="疯狂星期四", raw_message_filter=["/kfc"])
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        if "/kfc" in event.raw_message:
            random_quote = random.choice(self.kfc_quotes)
            await self.api.post_group_msg(event.group_id, text=random_quote)
