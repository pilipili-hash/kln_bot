from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_forward_msg_cq
from .utils import generate_signin_image, initialize_database, can_sign_in, record_sign_in
from PluginManager.plugin_manager import feature_required

bot = CompatibleEnrollment

class SignIn(BasePlugin):
    name = "SignIn"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        await initialize_database()

    @bot.group_event()
    @feature_required("签到", raw_message_filter="签到")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        if event.raw_message.strip() == "签到":
            user_id = event.user_id
            group_id = event.group_id
            nickname = event.sender.card if event.sender.card else event.sender.nickname

            if await can_sign_in(user_id, group_id):
                await record_sign_in(user_id, group_id)
                image_data = await generate_signin_image(user_id, nickname)
                if image_data:
                    await send_group_forward_msg_cq(group_id,image_data)
                else:
                    await self.api.post_group_msg(group_id, text="签到图片生成失败，请稍后再试。")
            else:
                await self.api.post_group_msg(group_id, text="你今天已经签到过了！")
