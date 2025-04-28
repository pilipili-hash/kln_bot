from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import At, MessageChain, Text
from PluginManager.plugin_manager import feature_required
from .data import DATA
import random
bot = CompatibleEnrollment

class DiseasePlugin(BasePlugin):
    name = "DiseasePlugin"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    @feature_required("发病", raw_message_filter="/发病")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理 /发病 命令
        """
        raw_message = event.raw_message.strip()
        if raw_message.startswith("/发病"):
            at_members = [segment for segment in event.message if segment["type"] == "at"]
            if not at_members:
                nickname = raw_message[3:].strip()  # 获取 /发病 后面的文字
                if not nickname:
                    await self.api.post_group_msg(event.group_id, text="请@一个人或提供一个名字来发病！")
                    return
                msg = random.choice(DATA).format(target_name=nickname)
                await self.api.post_group_msg(event.group_id, text=msg)
                return

            for at_member in at_members:
                user_id = at_member["data"]["qq"]
                member_info = await self.api.get_group_member_info(event.group_id, user_id, no_cache=False)        
                nickname = member_info.get('data', {}).get('card', '') or member_info.get('data', {}).get('nickname', '')
                msg = random.choice(DATA).format(target_name=nickname)
                await self.api.post_group_msg(event.group_id, text=msg)
