import aiohttp
import re
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
bot = CompatibleEnrollment

class BiliVideoInfo(BasePlugin):
    name = "BiliVideoInfo"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def fetch_video_info(self, bvid: str) -> dict:
        """
        调用 B站 API 获取视频信息。
        """
        api_url = f"http://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        print(f"API request failed with status: {response.status}")
                        try:
                            error_message = await response.text()
                            print(f"Error message: {error_message}")
                        except Exception as e:
                            print(f"Failed to read error message: {e}")
                        return None
        except aiohttp.ClientError as e:
            print(f"API request failed: {e}")
            return None

    def format_video_info(self, data: dict) -> MessageChain:
        """
        提取视频信息并格式化为 MessageChain。
        """
        if not data or data.get("code") != 0:
            return MessageChain([Text("获取视频信息失败，请检查 BV 号是否正确。")])

        video_data = data["data"]
        title = video_data["title"]
        pic_url = video_data["pic"]
        owner_name = video_data["owner"]["name"]
        view_count = video_data["stat"]["view"]
        danmaku_count = video_data["stat"]["danmaku"]
        like_count = video_data["stat"]["like"]
        desc = video_data["desc"]

        message = MessageChain([
            Text(f"视频标题: {title}\n"),
            Text(f"UP主: {owner_name}\n"),
            Text(f"播放量: {view_count}\n"),
            Text(f"弹幕数: {danmaku_count}\n"),
            Text(f"点赞数: {like_count}\n"),
            Text(f"简介: {desc}\n"),
            Image(pic_url)
        ])
        return message

    @bot.group_event()
    @feature_required("提取BV封面", raw_message_filter="BV")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件，匹配 BV 号并发送视频信息。
        """
        raw_message = event.raw_message.strip()
        match = re.search(r"BV([a-zA-Z0-9]{10})", raw_message)
        if match:
            bvid = match.group(0)
            print(bvid)
            await self.api.post_group_msg(event.group_id, text="正在获取视频信息，请稍候...")
            video_data = await self.fetch_video_info(bvid)
            if video_data:
                message_chain = self.format_video_info(video_data)
                await self.api.post_group_msg(event.group_id, rtf=message_chain)
            else:
                await self.api.post_group_msg(event.group_id, text="获取视频信息失败，请稍后再试。")
