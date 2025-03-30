import aiohttp
import json
from datetime import datetime
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage, PrivateMessage
from PluginManager.plugin_manager import feature_required
from utils.group_forward_msg import send_group_forward_msg_ws,cq_img
from ncatbot.core.element import (
    MessageChain,  # 消息链，用于组合多个消息元素
    Text,          # 文本消息
    At,            # @某人
    Face,          # QQ表情
    Image,         # 图片
)
bot = CompatibleEnrollment

class TodayAnime(BasePlugin):
    name = "TodayAnime"  # 插件名称
    version = "1.0.1"   # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def fetch_today_anime(self):
        url = "https://api.bgm.tv/calendar"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return None

    def format_anime_data(self, data):
        today = datetime.now().strftime("%A")  # 获取当天的英文星期
        weekday_map = {
            "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
            "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六", "Sunday": "星期日"
        }
        today_cn = weekday_map.get(today, "")
        today_anime = []
        for weekday in data:
            if weekday["weekday"]["cn"] == today_cn:
                for item in weekday["items"]:
                   
                    image_url = item["images"]["large"]
                    anime_info = {
                        "title": item.get("name_cn", item["name"]),
                        "image": image_url,
                        "air_date": item["air_date"]
                    }
                    today_anime.append(anime_info)
        return today_anime


    async def send_merged_forward(self, event, data, user_id, is_group=True):
        messages = []
        for anime in data:
            # 构建字符串格式的内容
            content = (
                f"番剧名称: {anime['title']}\n"
                f"{await cq_img(anime['image'])}\n"  # 使用 cq_img 转换图片 URL
                f"更新时间: {anime['air_date']}"
            )
            # 构建消息节点
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "今日番剧",
                    "user_id": user_id,  # 使用传递的 user_id
                    "content": content
                }
            })
        
        # 调用 send_group_forward_msg_ws，发送整个消息列表
        if is_group:
            await send_group_forward_msg_ws(
                group_id=event.group_id,
                content=messages
            )
        else:
            await send_group_forward_msg_ws(
                group_id=event.user_id,
                content=messages
            )
    @bot.group_event()
    @feature_required("今日番剧")
    async def handle_group_message(self, event: GroupMessage):
        if event.raw_message == "今日番剧":
            data = await self.fetch_today_anime()
            if data:
                formatted_data = self.format_anime_data(data)
                if formatted_data:
                    await self.send_merged_forward(event, formatted_data,event.self_id, is_group=True)
                else:
                    await self.api.post_group_msg(event.group_id, text="今天没有番剧更新")
            else:
                await self.api.post_group_msg(event.group_id, text="获取今日番剧信息失败")

    @bot.private_event()
    async def handle_private_message(self, event: PrivateMessage):
        if event.raw_message == "今日番剧":
            data = await self.fetch_today_anime()
            if data:
                formatted_data = self.format_anime_data(data)
                if formatted_data:
                    await self.send_merged_forward(event, formatted_data,event.self_id, is_group=False)
                else:
                    await self.api.post_private_msg(event.user_id, text="今天没有番剧更新")
            else:
                await self.api.post_private_msg(event.user_id, text="获取今日番剧信息失败")