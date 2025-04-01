import aiohttp
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
from urllib.parse import quote
from utils.group_forward_msg import send_group_forward_msg_ws
import re

bot = CompatibleEnrollment

class ComicSearch(BasePlugin):
    name = "ComicSearch"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def fetch_comics(self, query: str):
        """调用漫画搜索 API"""
        base_url = "https://www.copy-manga.com/api/kb/web/searchbd/comics"
        params = {
            "offset": 0,
            "platform": 2,
            "limit": 6,
            "q": query,
            "q_type": ""
        }
        url = f"{base_url}?{'&'.join([f'{k}={quote(str(v))}' for k, v in params.items()])}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return None

    def format_comics_data(self, data):
        """格式化漫画数据"""
        if not data or data.get("code") != 200 or not data.get("results"):
            return []

        comics = []
        for item in data["results"]["list"]:
            comic_info = {
                "name": item["name"],
                "alias": item["alias"],
                "cover": item["cover"],
                "author": ", ".join([author["name"] for author in item["author"]]),
                "popular": item["popular"],
                "path_word": item["path_word"]
            }
            comics.append(comic_info)
        return comics

    async def send_comics_forward(self, event: GroupMessage, comics):
        """合并转发漫画信息"""
        messages = []
        for comic in comics:
            comic_url = f"https://www.copy-manga.com/comic/{comic['path_word']}"
            content = (
                f"漫画名称: {comic['name']}\n"
                f"别名: {comic['alias']}\n"
                f"作者: {comic['author']}\n"
                f"人气: {comic['popular']}\n"
                f"链接: {comic_url}\n"
                f"[CQ:image,file={comic['cover']}]"
            )

            messages.append({
                "type": "node",
                "data": {
                    "nickname": "漫画搜索",
                    "user_id": event.self_id,
                    "content": content
                }
            })

        await send_group_forward_msg_ws(
            group_id=event.group_id,
            content=messages
        )

    @bot.group_event()
    @feature_required("漫画搜索","/漫画搜索")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        match = re.match(r"^/漫画搜索\s*(.*)$", raw_message)
        if match:
            query = match.group(1).strip()  # 提取搜索关键词
            if not query:
                await self.api.post_group_msg(event.group_id, text="请输入漫画名称")
                return

            await self.api.post_group_msg(event.group_id, text="正在搜索中~请稍等")

            data = await self.fetch_comics(query)
            if data:
                comics = self.format_comics_data(data)
                if comics:
                    await self.send_comics_forward(event, comics)
                else:
                    await self.api.post_group_msg(event.group_id, text="未找到相关漫画")
            else:
                await self.api.post_group_msg(event.group_id, text="漫画搜索失败，请稍后再试")
