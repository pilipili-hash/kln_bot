from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .utils import Utils

bot = CompatibleEnrollment
utils = Utils()

class CSGOCaseOpening(BasePlugin):
    name = "CSGOCaseOpening"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        """
        raw_message = event.raw_message.strip()

        if raw_message == "/武器箱":
            await utils.send_case_list(event, case_type="weapon")

        elif raw_message == "/皮肤箱":
            await utils.send_case_list(event, case_type="souvenir")

        elif raw_message.startswith("/开箱"):
            try:
                parts = raw_message.split()
                if len(parts) != 2 or not parts[1].isdigit():
                    await self.api.post_group_msg(event.group_id, text="格式错误，请使用 /开箱 序号")
                    return

                index = int(parts[1])
                await utils.handle_open_case(event, index)

            except Exception as e:
                await self.api.post_group_msg(event.group_id, text=f"开箱失败: {str(e)}")
