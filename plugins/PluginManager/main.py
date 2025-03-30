from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from PluginManager.plugin_manager import master_required
from DatabasePlugin.main import DatabaseManager
bot = CompatibleEnrollment

class PluginManager(BasePlugin):
    name = "PluginManager"  # 插件名称
    version = "1.0.0"   # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    @master_required(commands=["/开启", "/关闭"])# 检查是否为管理员
    async def handle_group_message(self, event: GroupMessage):
        db_manager = DatabaseManager()
        raw_message = event.raw_message.strip()
        if raw_message.startswith("/开启"):
            title = raw_message[3:].strip()
            if await db_manager.update_feature_status(event.group_id, title, "1"):
                await self.api.post_group_msg(event.group_id, text=f"功能 '{title}' 已开启")
            else:
                await self.api.post_group_msg(event.group_id, text=f"功能 '{title}' 开启失败，请检查功能名称是否正确")
        elif raw_message.startswith("/关闭"):
            title = raw_message[3:].strip()
            if await db_manager.update_feature_status(event.group_id, title, "0"):
                await self.api.post_group_msg(event.group_id, text=f"功能 '{title}' 已关闭")
            else:
                await self.api.post_group_msg(event.group_id, text=f"功能 '{title}' 关闭失败，请检查功能名称是否正确")
