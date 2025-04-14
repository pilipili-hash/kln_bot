import httpx
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain
from utils.group_forward_msg import send_group_forward_msg_ws
from PluginManager.plugin_manager import feature_required
from .utils import fetch_birthday_data, parse_birthday_data, format_birthday_message

bot = CompatibleEnrollment

class TodayBirthday(BasePlugin):
    name = "TodayBirthday"
    version = "0.1.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    @feature_required("今日生日","/今日生日")
    async def birthday_command(self, event: GroupMessage):
        """
        处理 /今日生日 命令。
        """
        if event.raw_message.strip() == "/今日生日":
            group_id = event.group_id
            user_id = event.self_id

            await self.api.post_group_msg(group_id, text="正在获取今日生日数据，请稍候...")
            html_content = await fetch_birthday_data()

            if html_content:
                character_list = parse_birthday_data(html_content)
                if character_list:
                    messages = await format_birthday_message(character_list, user_id)
                    await send_group_forward_msg_ws(group_id=group_id, content=messages)
                else:
                    await self.api.post_group_msg(group_id, text="今日没有生日角色。")
            else:
                await self.api.post_group_msg(group_id, text="获取今日生日数据失败。")
