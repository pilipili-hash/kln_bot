import re
import time
import logging
from typing import Dict, List, Any
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from .utils import fetch_steam_games
from utils.group_forward_msg import send_group_forward_msg_ws
from utils.config_manager import get_config

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class SteamGameSearch(BasePlugin):
    name = "SteamGameSearch"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        # 缓存系统
        self.game_cache: Dict[str, tuple] = {}  # {query: (results, timestamp)}
        self.cache_duration = 3600  # 1小时缓存

        # 请求限制
        self.last_request_time: Dict[int, float] = {}  # {group_id: timestamp}
        self.request_interval = 3.0  # 3秒间隔

        # 统计信息
        self.search_count = 0
        self.cache_hit_count = 0
        self.success_count = 0

    async def on_load(self):
        """插件加载时初始化"""
        _log.info(f"SteamGameSearch v{self.version} 插件已加载")

    async def __onload__(self):
        """插件加载时初始化（新版本）"""
        await self.on_load()

    def _is_cache_valid(self, cache_time: float) -> bool:
        """检查缓存是否有效"""
        return time.time() - cache_time < self.cache_duration

    def _should_rate_limit(self, group_id: int) -> bool:
        """检查是否应该限流"""
        current_time = time.time()
        if group_id in self.last_request_time:
            if current_time - self.last_request_time[group_id] < self.request_interval:
                return True
        self.last_request_time[group_id] = current_time
        return False

    def _clean_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, cache_time) in self.game_cache.items()
            if current_time - cache_time >= self.cache_duration
        ]
        for key in expired_keys:
            del self.game_cache[key]

    def _format_game_info(self, games: List[Dict[str, Any]]) -> MessageChain:
        """格式化游戏信息为美观的消息"""
        if not games:
            return MessageChain([Text("❌ 未找到相关游戏，请尝试其他关键词")])

        message_elements = []
        message_elements.append(Text(f"🎮 Steam游戏搜索结果 (共找到 {len(games)} 款游戏)\n\n"))

        for i, game in enumerate(games, 1):
            # 游戏标题
            message_elements.append(Text(f"🎯 {i}. {game['title']}\n"))

            # 发布日期
            if game.get('release_date'):
                message_elements.append(Text(f"� 发布日期: {game['release_date']}\n"))

            # 评价信息
            if game.get('review_summary') and game['review_summary'] != "无评价":
                message_elements.append(Text(f"⭐ 评价: {game['review_summary']}\n"))

            # 价格信息
            if game.get('price'):
                price_text = game['price']
                if price_text == "免费开玩" or "Free" in price_text:
                    message_elements.append(Text(f"� 价格: 🆓 {price_text}\n"))
                elif price_text != "无价格信息":
                    message_elements.append(Text(f"💰 价格: {price_text}\n"))

            # Steam链接
            if game.get('link'):
                message_elements.append(Text(f"🔗 链接: {game['link']}\n"))

            # 游戏封面图片
            if game.get('image_url'):
                message_elements.append(Image(game['image_url']))

            # 分隔线（除了最后一个游戏）
            if i < len(games):
                message_elements.append(Text("\n" + "─" * 30 + "\n\n"))

        return MessageChain(message_elements)

    def _format_game_info_for_forward(self, games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化游戏信息为合并转发消息"""
        # 获取机器人user_id
        bot_user_id = get_config("bt_uin", "123456")

        if not games:
            return [{
                "type": "node",
                "data": {
                    "nickname": "Steam搜索",
                    "user_id": str(bot_user_id),
                    "content": "❌ 未找到相关游戏，请尝试其他关键词"
                }
            }]

        forward_messages = []

        # 添加搜索结果标题
        forward_messages.append({
            "type": "node",
            "data": {
                "nickname": "Steam游戏搜索",
                "user_id": str(bot_user_id),
                "content": f"🎮 Steam游戏搜索结果\n📊 共找到 {len(games)} 款游戏"
            }
        })

        # 为每个游戏创建单独的转发节点
        for i, game in enumerate(games, 1):
            game_info_parts = []

            # 游戏标题
            game_info_parts.append(f"🎯 {i}. {game['title']}")

            # 发布日期
            if game.get('release_date'):
                game_info_parts.append(f"📅 发布日期: {game['release_date']}")

            # 评价信息
            if game.get('review_summary') and game['review_summary'] != "无评价":
                game_info_parts.append(f"⭐ 评价: {game['review_summary']}")

            # 价格信息
            if game.get('price'):
                price_text = game['price']
                if price_text == "免费开玩" or "Free" in price_text:
                    game_info_parts.append(f"💰 价格: 🆓 {price_text}")
                elif price_text != "无价格信息":
                    game_info_parts.append(f"💰 价格: {price_text}")

            # Steam链接
            if game.get('link'):
                game_info_parts.append(f"🔗 链接: {game['link']}")

            # 构建消息内容（使用CQ码格式）
            content = "\n".join(game_info_parts)

            # 添加游戏封面图片（使用CQ码）
            if game.get('image_url'):
                content += f"\n[CQ:image,file={game['image_url']}]"

            # 添加游戏节点
            forward_messages.append({
                "type": "node",
                "data": {
                    "nickname": f"Steam游戏 #{i}",
                    "user_id": str(bot_user_id),
                    "content": content
                }
            })

        return forward_messages

    async def _send_forward_message(self, group_id: int, forward_messages: List[Dict[str, Any]]):
        """发送合并转发消息"""
        try:
            # 使用专门的合并转发函数
            success = await send_group_forward_msg_ws(group_id, forward_messages)

            # 检查是否成功：True 或 None 都认为是成功（None表示发送成功但无明确返回值）
            if success is True or success is None:
                return  # 成功发送，直接返回，不执行降级逻辑

        except Exception as e:
            _log.error(f"发送合并转发消息失败: {e}")

        # 只有在失败或异常时才执行降级逻辑
        fallback_text = f"🎮 Steam搜索结果 (共 {len(forward_messages)-1} 款游戏)\n\n"
        fallback_text += "⚠️ 合并转发失败，已降级为普通消息显示"
        await self.api.post_group_msg(group_id, text=fallback_text)

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🎮 Steam游戏搜索插件帮助

🎯 功能说明：
搜索Steam平台上的游戏信息，包括价格、评价、发布日期等

🔍 使用方法：
1. 基础搜索：/steam 游戏名称
2. 英文搜索：/steam Counter-Strike
3. 中文搜索：/steam 反恐精英
4. 查看帮助：/steam帮助
5. 查看统计：/steam统计

📊 搜索结果包含：
• 🎯 游戏名称和封面图片
• 📅 发布日期信息
• ⭐ 用户评价摘要
• 💰 当前价格（支持免费游戏标识）
• 🔗 Steam商店链接

✨ 特色功能：
• ⚡ 智能缓存：1小时缓存，提升响应速度
• 🛡️ 请求限制：3秒间隔，避免频繁调用
• 📋 合并转发：使用合并转发展示搜索结果
• 🎨 美观展示：emoji装饰和清晰排版
• 🔍 精确搜索：支持中英文游戏名称

💡 使用技巧：
• 使用准确的游戏名称获得更好结果
• 支持部分匹配，如"CS"可以找到Counter-Strike
• 每次最多显示5个搜索结果
• 缓存机制避免重复搜索相同内容
• 搜索结果通过合并转发发送，点击查看详情

🔧 版本：v2.0.0
💡 提示：直接输入游戏名称开始搜索！"""

        await self.api.post_group_msg(group_id, text=help_text)

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        cache_hit_rate = (self.cache_hit_count / max(self.search_count, 1)) * 100
        success_rate = (self.success_count / max(self.search_count, 1)) * 100

        stats_text = f"""📊 Steam搜索插件统计

🔢 使用数据：
• 总搜索次数: {self.search_count}
• 成功搜索次数: {self.success_count}
• 缓存命中次数: {self.cache_hit_count}

📈 效率指标：
• 成功率: {success_rate:.1f}%
• 缓存命中率: {cache_hit_rate:.1f}%
• 当前缓存数量: {len(self.game_cache)}

⚡ 性能优化：
• 智能缓存减少重复请求
• 请求限制保护服务稳定性
• 异步处理提升响应速度

🔧 版本: v2.0.0"""

        await self.api.post_group_msg(group_id, text=stats_text)

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件，搜索Steam游戏"""
        raw_message = event.raw_message.strip()

        # 帮助命令
        if raw_message in ["/steam帮助", "/steam help", "/steam", "/steam "]:
            await self.show_help(event.group_id)
            return
        elif raw_message in ["/steam统计", "/steam stats"]:
            await self.show_statistics(event.group_id)
            return

        # 搜索命令匹配
        match = re.match(r"^/steam\s+(.+)$", raw_message)
        if not match:
            return

        query = match.group(1).strip()
        if not query:
            await self.api.post_group_msg(event.group_id, text="❌ 请输入游戏名称\n💡 例如：/steam Counter-Strike")
            return

        # 检查请求限制
        if self._should_rate_limit(event.group_id):
            return

        # 清理过期缓存
        self._clean_expired_cache()

        # 检查缓存
        cache_key = query.lower()
        if cache_key in self.game_cache:
            cached_results, cache_time = self.game_cache[cache_key]
            if self._is_cache_valid(cache_time):
                self.cache_hit_count += 1
                forward_messages = self._format_game_info_for_forward(cached_results)
                await self._send_forward_message(event.group_id, forward_messages)
                return

        # 更新统计
        self.search_count += 1

        try:
            # 搜索游戏
            games = await fetch_steam_games(query)

            if games:
                # 缓存结果
                self.game_cache[cache_key] = (games, time.time())
                self.success_count += 1

                # 格式化并发送结果（使用合并转发）
                forward_messages = self._format_game_info_for_forward(games)
                await self._send_forward_message(event.group_id, forward_messages)
            else:
                await self.api.post_group_msg(event.group_id, text=f"❌ 未找到游戏: {query}\n💡 请尝试使用更准确的游戏名称")

        except Exception as e:
            _log.error(f"Steam搜索时发生错误: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 搜索时发生错误，请稍后再试")
