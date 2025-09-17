import logging
import asyncio
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .utils import get_cos_images
from utils.group_forward_msg import send_group_forward_msg_ws

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class COSPlugin(BasePlugin):
    name = "COSPlugin"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_images = 0

        # 频率控制
        self.last_request_time = {}
        self.request_interval = 3.0  # 3秒间隔

    async def on_load(self):
        _log.info(f"COSPlugin v{self.version} 插件已加载")

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        raw_message = event.raw_message.strip()
        user_id = event.user_id
        group_id = event.group_id

        # 帮助命令
        if raw_message in ["/cos帮助", "/cos help", "cos帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/cos统计", "cos统计"]:
            await self.show_statistics(group_id)
            return

        if not raw_message.startswith("/cos"):
            return

        # 频率控制
        current_time = asyncio.get_event_loop().time()
        if user_id in self.last_request_time:
            time_diff = current_time - self.last_request_time[user_id]
            if time_diff < self.request_interval:
                remaining = self.request_interval - time_diff
                await self.api.post_group_msg(group_id=group_id, text=f"⏳ 请求过于频繁，请等待 {remaining:.1f} 秒后再试")
                return

        self.last_request_time[user_id] = current_time

        try:
            self.request_count += 1
            parts = raw_message.split()

            if len(parts) != 2 or not parts[1].isdigit():
                await self._send_error_message(event, "❌ 格式错误，请使用 /cos 数字 (1-10)")
                self.error_count += 1
                return

            num_images = int(parts[1])
            if not (1 <= num_images <= 10):
                await self._send_error_message(event, "❌ 数量必须在1到10之间")
                self.error_count += 1
                return

            _log.info(f"用户 {user_id} 在群 {group_id} 请求 {num_images} 张COS图片")

            # 发送处理中提示
            await self.api.post_group_msg(group_id=group_id, text="🎭 正在获取COS图片，请稍候...")

            image_urls = await get_cos_images(num_images)
            if not image_urls:
                await self._send_error_message(event, "❌ 获取图片失败，请稍后再试")
                self.error_count += 1
                return

            messages = self._build_forward_messages(event.self_id, image_urls)
            await send_group_forward_msg_ws(event.group_id, messages)

            # 更新统计
            self.success_count += 1
            self.total_images += len(image_urls)
            _log.info(f"成功发送 {len(image_urls)} 张COS图片给用户 {user_id}")

        except Exception as e:
            _log.error(f"处理COS请求时出错: {e}")
            await self._send_error_message(event, f"❌ 发生错误: {str(e)}")
            self.error_count += 1

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🎭 COS图片插件帮助

📝 基本命令：
• /cos 数字 - 获取指定数量的COS图片 (1-10张)
• /cos帮助 - 显示此帮助信息
• /cos统计 - 查看使用统计

💡 使用示例：
/cos 1    # 获取1张COS图片
/cos 5    # 获取5张COS图片
/cos 10   # 获取10张COS图片

⚠️ 注意事项：
• 每次请求间隔3秒
• 图片数量限制1-10张
• 图片通过合并转发发送"""

        await self.api.post_group_msg(group_id, text=help_text)

    async def show_statistics(self, group_id: int):
        """显示统计信息"""
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0
        avg_images = (self.total_images / self.success_count) if self.success_count > 0 else 0

        stats_text = f"""📊 COS图片插件统计

🎭 总请求数: {self.request_count}
✅ 成功次数: {self.success_count}
❌ 失败次数: {self.error_count}
📈 成功率: {success_rate:.1f}%
🖼️ 总图片数: {self.total_images}
📊 平均图片数: {avg_images:.1f}张/次
⏱️ 请求间隔: {self.request_interval}秒

💡 提示：发送"/cos帮助"查看详细帮助"""

        await self.api.post_group_msg(group_id, text=stats_text)

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
                    "user_id": str(user_id),  # 修复：user_id必须是字符串类型
                    "content": f"[CQ:image,file={url}]"
                }
            }
            for url in image_urls
        ]
