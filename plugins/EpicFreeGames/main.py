import aiohttp
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
bot = CompatibleEnrollment

class EpicFreeGames(BasePlugin):
    name = "EpicFreeGames"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def fetch_free_games(self):
        """从 Epic API 获取喜加一内容"""
        url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions?locale=zh-CN&country=CN&allowCountries=CN"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return self.parse_free_games(data)
                else:
                    return None

    def parse_free_games(self, data):
        """解析 API 返回的内容"""
        games = []
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
        for game in elements:
            title = game.get("title", "未知标题")
            # description = game.get("description", "无描述")
            image_url = next((img["url"] for img in game.get("keyImages", []) if img["type"] == "OfferImageWide"), None)
            
            # 优先使用 productSlug，其次使用 urlSlug，最后使用 catalogNs.mappings 的 pageSlug
            link = None
            if game.get("productSlug"):
                link = f"https://store.epicgames.com/zh-CN/p/{game['productSlug']}"
            elif game.get("urlSlug"):
                link = f"https://store.epicgames.com/zh-CN/p/{game['urlSlug']}"
            elif game.get("catalogNs", {}).get("mappings"):
                page_slug = game["catalogNs"]["mappings"][0].get("pageSlug")
                if page_slug:
                    link = f"https://store.epicgames.com/zh-CN/p/{page_slug}"

            games.append({
                "title": title,
                # "description": description,
                "image_url": image_url,
                "link": link
            })
        return games

    async def fetch_image(self, url):
        """处理图片 URL 重定向"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=False) as response:
                if response.status == 302:  # 检查是否为重定向
                    return response.headers.get("Location")  # 返回重定向后的 URL
                return url  

    async def send_free_games(self, group_id):
        """发送喜加一内容到群聊"""
        games = await self.fetch_free_games()
        if not games:
            await self.api.post_group_msg(group_id, text="获取 Epic 喜加一内容失败，请稍后再试。")
            return

        message_chain = MessageChain()
        for game in games:
            image_url = await self.fetch_image(game['image_url']) if game['image_url'] else None
            message_chain += MessageChain([
                Text(f"游戏名称: {game['title']}\n"),
                # Text(f"描述: {game['description']}\n"),
                Text(f"链接: {game['link']}\n") if game['link'] else Text("无链接\n"),
                Image(image_url) if image_url else Text("无图片\n"),
                Text("\n")
            ])
        await self.api.post_group_msg(group_id, rtf=message_chain)

    @bot.group_event()
    @feature_required("喜加一","/喜加一")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        if event.raw_message.strip() == "/喜加一":
            await self.send_free_games(event.group_id)

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
