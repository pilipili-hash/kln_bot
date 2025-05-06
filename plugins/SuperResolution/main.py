import aiohttp
import base64
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Image
from PluginManager.plugin_manager import feature_required
from utils.config_manager import get_config  # 导入 get_config 函数

bot = CompatibleEnrollment

class SuperResolution(BasePlugin):
    name = "SuperResolution"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self.pending_super_resolution = {}

    async def request_super_resolution(self, image_url: str) -> str:
        """
        调用超分辨率 API 并返回处理后的图片 URL。
        """
        api_base_url = get_config("chaofen_url")  # 从配置中获取基础 URL
        api_url = f"{api_base_url}/api/predict"  # 拼接完整的 API URL
        session_hash = ""  # 固定的 session_hash
        model_name = "up2x-latest-denoise2x.pth"  # 固定的模型名称

        # 下载图片并转换为 Base64 编码
        async with aiohttp.ClientSession() as session:
            image_url = image_url.replace("https://", "http://")
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    image_base64 = base64.b64encode(image_data).decode("utf-8")
                else:
                    return None

        payload = {
            "fn_index": 0,
            "data": [
                f"data:image/jpeg;base64,{image_base64}",
                model_name,
                2
            ],
            "session_hash": session_hash
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result and "data" in result and len(result["data"]) > 0:
                        return result["data"][0]  # 返回处理后的图片 URL
                return None

    async def handle_super_resolution(self, group_id: int, image_url: str, message_id: int):
        """
        处理超分辨率逻辑。
        """
        await self.api.post_group_msg(group_id, text="正在处理图片超分辨率，请稍候...")
        result_url = await self.request_super_resolution(image_url)
        if result_url:
            await self.api.post_group_msg(group_id, rtf=MessageChain([Image(result_url)]), reply=message_id)
        else:
            await self.api.post_group_msg(group_id, text="超分辨率处理失败，请稍后再试。")

    @bot.group_event()
    # @feature_required("超分辨率", "/超")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件。
        """
        group_id = event.group_id
        user_id = event.user_id
        raw_message = event.raw_message

        if raw_message.startswith("/超"):
            for segment in event.message:
                if segment["type"] == "image":  # 检查消息类型是否为图片
                    image_url = segment["data"].get("url")  # 提取图片的 URL
                    if image_url:
                        await self.handle_super_resolution(group_id, image_url, event.message_id)
                        return
            # 记录用户状态，等待后续图片
            self.pending_super_resolution[group_id] = user_id
            await self.api.post_group_msg(group_id, text="请发送图片以完成超分辨率处理。")
            return

        if group_id in self.pending_super_resolution and self.pending_super_resolution[group_id] == user_id:
            for segment in event.message:
                if segment["type"] == "image":  # 检查消息类型是否为图片
                    image_url = segment["data"].get("url")  # 提取图片的 URL
                    if image_url:
                        del self.pending_super_resolution[group_id]  # 清除用户状态
                        await self.handle_super_resolution(group_id, image_url, event.message_id)
