from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_forward_msg_ws
from PluginManager.plugin_manager import feature_required
from utils.group_forward_msg import get_cqimg  # 导入 get_cqimg 函数
import re
from .image_utils import search_image, format_results  # 导入图片处理函数
from utils.priority_handler import register_handler
bot = CompatibleEnrollment

class PicSearch(BasePlugin):
    name = "PicSearch"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self.pending_search = {}

    async def send_search_results(self, event: GroupMessage, image_url: str):
        """发送搜图结果"""
        await self.api.post_group_msg(event.group_id, text="正在搜图中，请稍候...")
        results = await search_image(image_url)
        if results:
            messages = format_results(results, event.self_id)
            await send_group_forward_msg_ws(
                group_id=event.group_id,
                content=messages
            )
        else:
            await self.api.post_group_msg(event.group_id, text="搜图失败，请稍后再试。")
#    @register_handler(10)
    @bot.group_event()
#    @feature_required("搜图", raw_message_filter="/搜图")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        group_id = event.group_id
        user_id = event.user_id
        raw_message = event.raw_message

        if re.match(r"^/搜图", raw_message):
            image_url = get_cqimg(raw_message)            
            if image_url:
                await self.send_search_results(event, image_url)
            else:
                self.pending_search[group_id] = user_id
                await self.api.post_group_msg(group_id, text="请发送图片以完成搜索。")
            return

        if group_id in self.pending_search and self.pending_search[group_id] == user_id:
            image_url = get_cqimg(raw_message) 
            if image_url:
                del self.pending_search[group_id]
                await self.send_search_results(event, image_url)
            else:
                await self.api.post_group_msg(group_id, text="未检测到图片，请重新发送。")
