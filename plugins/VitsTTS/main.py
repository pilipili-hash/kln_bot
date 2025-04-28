import aiohttp
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Record, Image
from utils.config_manager import get_config
from .characters import CHARACTERS, generate_character_list_image
import re
import os

bot = CompatibleEnrollment

class VitsTTS(BasePlugin):
    name = "VitsTTS"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self.vits_url = get_config("VITS_url")  # 缓存配置到实例变量
        self.proxy = get_config("proxy")  # 缓存代理配置
        if not self.vits_url:
            print("VITS_url 配置未找到，请检查配置文件。")

    async def send_error_message(self, group_id, message):
        """发送错误消息的辅助方法"""
        await self.api.post_group_msg(group_id, text=message)

    async def generate_audio_url(self, content, language, char_name):
        """生成音频 URL 的辅助方法"""
        payload = {
            "fn_index": 0,
            "session_hash": "",
            "data": [content, language, char_name, 0.6, 0.668, 1.2]
        }
        async with aiohttp.ClientSession(proxy=self.proxy) as session:
            async with session.post(f"{self.vits_url.rstrip('/')}/api/generate", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result and "data" in result and len(result["data"]) > 1 and isinstance(result["data"][1], dict):
                        audio_name = result["data"][1].get("name")
                        if isinstance(audio_name, str):
                            return f"{self.vits_url.rstrip('/')}/file={audio_name}"
                return None

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        raw_message = event.raw_message.strip()
        if raw_message == "/语音列表":
            try:
                # 图片路径设置为与 main.py 相同的文件夹
                module_path = os.path.dirname(__file__)
                image_path = os.path.join(module_path, "character_list.png")

                # 检查图片是否存在，不存在则生成
                if not os.path.exists(image_path):
                    image = generate_character_list_image()
                    image.save(image_path)

                await self.api.post_group_msg(
                    event.group_id,
                    rtf=MessageChain([Image(path=image_path)])
                )
            except Exception as e:
                await self.api.post_group_msg(event.group_id, text=f"生成人物列表图片失败: {str(e)}")
            return


        try:
            # 使用正则表达式解析输入
            match = re.match(r"^/(\d+)说(中文|日语)\s+(.+)$", raw_message)
            if not match:
                return

            # 提取编号、语言和内容
            char_index = int(match.group(1)) - 1
            language = match.group(2)
            content = match.group(3)
            char_name = CHARACTERS[char_index] if 0 <= char_index < len(CHARACTERS) else None

            if not char_name:
                await self.send_error_message(event.group_id, "人物编号无效，请检查输入。")
                return

            if not self.vits_url:
                await self.send_error_message(event.group_id, "VITS_url 配置未找到，请检查配置文件。")
                return

            # 生成音频 URL
            audio_url = await self.generate_audio_url(content, language, char_name)
            if audio_url:
                await self.api.post_group_msg(event.group_id, rtf=MessageChain([Record(audio_url)]))
            else:
                await self.send_error_message(event.group_id, "语音生成失败，请稍后重试。")
        except Exception as e:
            # 输出详细错误信息
            import traceback
            error_details = traceback.format_exc()
            print(f"发生错误: {error_details}")
            await self.send_error_message(event.group_id, f"发生错误: {str(e)}")
