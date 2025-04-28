from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .utils import get_cos_images
from utils.group_forward_msg import send_group_forward_msg_ws
from PluginManager.plugin_manager import feature_required

bot = CompatibleEnrollment

class COSPlugin(BasePlugin):
    name = "COSPlugin"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")

    @bot.group_event()
    @feature_required("cos", raw_message_filter="/cos")
    async def handle_group_message(self, event: GroupMessage):
        raw_message = event.raw_message.strip()

        if not raw_message.startswith("/cos"):
            return

        try:
            parts = raw_message.split()
            if len(parts) != 2 or not parts[1].isdigit():
                await self._send_error_message(event, "格式错误，请使用 /cos 数字")
                return

            num_images = int(parts[1])
            if not (1 <= num_images <= 10):
                await self._send_error_message(event, "数量必须在1到10之间")
                return

            image_urls = await get_cos_images(num_images)
            if not image_urls:
                await self._send_error_message(event, "获取图片失败")
                return

            messages = self._build_forward_messages(event.self_id, image_urls)
            await send_group_forward_msg_ws(event.group_id, messages)

        except Exception as e:
            await self._send_error_message(event, f"发生错误: {str(e)}")

    async def _send_error_message(self, event: GroupMessage, message: str):
        """发送错误消息"""
        await event.api.post_group_msg(event.group_id, text=message)

    def _build_forward_messages(self, user_id: int, image_urls: list) -> list:
        """构造合并转发消息格式"""
        return [
            {
                "type": "node",
                "data": {
                    "nickname": "COS图片",
                    "user_id": user_id,
                    "content": f"[CQ:image,file={url}]"
                }
            }
            for url in image_urls
        ]
