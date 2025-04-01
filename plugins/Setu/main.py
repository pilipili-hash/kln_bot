import aiohttp
import json
import re
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from PluginManager.plugin_manager import feature_required
from utils.group_forward_msg import send_group_forward_msg_ws, cq_img
from utils.config_manager import get_config, load_config
from io import BytesIO
from PIL import Image
import random
import string
import base64

bot = CompatibleEnrollment

class Setu(BasePlugin):
    name = "Setu"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        await load_config()  # 加载全局配置

    async def fetch_setu(self, num: int = 1, r18: int = 0):
        """
        调用 Lolicon API 获取涩图
        :param num: 数量，范围 1-20
        :param r18: 0为非 R18，1为 R18，2为混合
        :return: list[dict] or None
        """
        api_url = "https://api.lolicon.app/setu/v2"
        params = {
            "num": num,
            "r18": r18
        }
        proxy = get_config("proxy")  # 从全局配置获取代理配置
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, proxy=proxy) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["error"]:
                        print(f"API error: {data['error']}")
                        return None
                    return data["data"]
                else:
                    print(f"API request failed with status: {response.status}")
                    return None

    async def fetch_and_modify_image(self, image_url: str) -> str:
        """
        下载图片并在末尾添加随机字符串以修改 MD5
        :param image_url: 图片 URL
        :return: 修改后的图片数据的 Base64 编码
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()

                        # 添加随机字符串
                        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                        modified_image_data = image_data + random_string.encode('utf-8')

                        # 返回 Base64 编码
                        base64_data = base64.b64encode(modified_image_data).decode('utf-8')
                        return base64_data
                    else:
                        print(f"Image download failed with status: {response.status}")
                        return None
        except Exception as e:
            print(f"Image processing error: {e}")
            return None

    async def send_setu(self, event: GroupMessage, num: int = 1, r18: int = 0):
        """
        发送涩图到群聊
        :param group_id: 群号
        :param num: 数量
        :param r18: r18
        """
        setu_data = await self.fetch_setu(num, r18)
        if not setu_data:
            await self.api.post_group_msg(event.group_id, text="获取涩图失败，请稍后再试。")
            return

        messages = []
        for item in setu_data:
            title = item["title"]
            author = item["author"]
            pid = item["pid"]
            image_url = item["urls"]["original"]
            tags = ", ".join(item["tags"])

            modified_image_data = await self.fetch_and_modify_image(image_url)
            if modified_image_data:
                content = (
                    f"标题: {title}\n"
                    f"作者: {author}\n"
                    f"PID: {pid}\n"
                    f"标签: {tags}\n"
                    f"[CQ:image,file=base64://{modified_image_data}]\n"  # 使用修改后的图片数据
                )
            else:
                content = (
                    f"标题: {title}\n"
                    f"作者: {author}\n"
                    f"PID: {pid}\n"
                    f"标签: {tags}\n"
                    f"图片获取失败\n"
                )

            messages.append({
                "type": "node",
                "data": {
                    "nickname": "涩图",
                    "user_id": event.user_id,
                    "content": content
                }
            })

        await send_group_forward_msg_ws(
            group_id=event.group_id,
            content=messages
        )

    @bot.group_event()
    @feature_required("setu","/涩图")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        """
        raw_message = event.raw_message.strip()
        match = re.match(r"^/涩图\s*(\d+)\s*(\d*)", raw_message)
        if match:
            num = int(match.group(1))
            r18 = int(match.group(2)) if match.group(2) else 0
            if 1 <= num <= 20:
                await self.api.post_group_msg(event.group_id, text="正在整理中~~")
                await self.send_setu(event, num, r18)
            else:
                await self.api.post_group_msg(event.group_id, text="数量必须在 1-20 之间。")

