import re
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
from .utils import fetch_steam_games

bot = CompatibleEnrollment

class SteamGameSearch(BasePlugin):
    name = "SteamGameSearch"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    @feature_required("steam搜索", raw_message_filter="/steam")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件，搜索 Steam 游戏。
        """
        raw_message = event.raw_message
        match = re.match(r"^/steam\s*(.+)$", raw_message)  # 支持 "/steam dota2" 和 "/steamdota2"
        if match:
            query = match.group(1).strip()
            if not query:
                await self.api.post_group_msg(event.group_id, text="请输入游戏名称，例如：/steam Dota 2")
                return

            await self.api.post_group_msg(event.group_id, text="正在搜索，请稍候...")
            games = await fetch_steam_games(query)  # 确保正确使用 await
            if games:
                combined_message = MessageChain()  # 合并所有消息
                for game in games[:5]:  # 限制最多返回 5 个结果
                    combined_message += MessageChain([
                        Text(f"游戏名称: {game['title']}\n"),
                        Text(f"发布日期: {game['release_date']}\n"),
                        Text(f"评价: {game['review_summary']}\n"),
                        Text(f"价格: {game['price']}\n"),
                        Text(f"链接: {game['link']}\n"),
                        Image(game['image_url']),
                        Text("\n")  # 添加换行分隔不同游戏
                    ])
                await self.api.post_group_msg(event.group_id, rtf=combined_message)
            else:
                await self.api.post_group_msg(event.group_id, text="未找到相关游戏，请稍后再试。")
