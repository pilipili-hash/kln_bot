import aiohttp
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from PluginManager.plugin_manager import feature_required
bot = CompatibleEnrollment

class TianGou(BasePlugin):
    name = "TianGou"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    @feature_required(feature_name="舔狗日记", raw_message_filter=["/舔狗"])
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        """
        if event.raw_message.strip() == "/舔狗":
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.oick.cn/dog/api.php") as response:
                        if response.status == 200:
                            dog_diary = await response.text()
                            await self.api.post_group_msg(event.group_id, text=dog_diary)
                        else:
                            await self.api.post_group_msg(event.group_id, text="获取舔狗日记失败，请稍后再试。")
            except Exception as e:
                print(f"获取舔狗日记时出错: {e}")
                await self.api.post_group_msg(event.group_id, text="获取舔狗日记失败，请稍后再试。")
