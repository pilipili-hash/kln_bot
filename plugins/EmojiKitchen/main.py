import aiohttp
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
import re
from PluginManager.plugin_manager import feature_required
from .utils import mix_emoji

bot = CompatibleEnrollment

class EmojiKitchen(BasePlugin):
    name = "EmojiKitchen"
    version = "1.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs) 

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def get_emoji_combination(self, emoji1: str, emoji2: str) -> str:
        """
        调用 EmojiKitchen API 获取合成后的图片 URL。
        """
        base_url = "https://www.gstatic.com/android/keyboard/emojikitchen/"
        # 将emoji转换为unicode编码
        emoji1_unicode = ''.join([f'{ord(c):x}' for c in emoji1])
        emoji2_unicode = ''.join([f'{ord(c):x}' for c in emoji2])
        
        image_path = f"2020C/u{emoji1_unicode}/u{emoji1_unicode}_u{emoji2_unicode}.png"
        image_url = base_url + image_path

        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    return image_url
                else:
                    return None

    @bot.group_event()
    @feature_required("emoji合成")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件，仅在接收到两个 Emoji 时进行合成。
        """
        raw_message = event.raw_message.strip()
        # 修复正则表达式，确保只匹配两个有效的 Emoji
        match = re.match(r"^([\U0001F000-\U0001FFFF])\s*([\U0001F000-\U0001FFFF])$", raw_message)
        if match:
            emoji1 = match.group(1)
            emoji2 = match.group(2)

            # await self.api.post_group_msg(event.group_id, text="正在合成 Emoji，请稍候...")
            image_url = await mix_emoji(emoji1, emoji2)

            if image_url:
                await self.api.post_group_msg(event.group_id, image=image_url)
            else:
                await self.api.post_group_msg(event.group_id, text="Emoji 合成失败，请检查 Emoji 是否支持合成。")
