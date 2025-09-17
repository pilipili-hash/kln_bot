import aiohttp
import asyncio
import aiosqlite
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
from utils.group_forward_msg import _message_sender
from utils.config_manager import get_config
from ncatbot.utils.logger import get_log

bot = CompatibleEnrollment

class EpicFreeGames(BasePlugin):
    name = "EpicFreeGames"  # 插件名称
    version = "2.0.0"  # 插件版本

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = get_log()
        self.bot_name = get_config("bot_name", "NCatBot")
        self.bot_uin = get_config("bt_uin", 123456)
        self.db_path = "data.db"

    async def init_db(self):
        """初始化数据库，创建订阅表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS epic_subscriptions (
                    group_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    async def add_subscription(self, group_id: int) -> bool:
        """添加群组订阅"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO epic_subscriptions (group_id, enabled) VALUES (?, 1)",
                    (str(group_id),)
                )
                await db.commit()
                return True
            except Exception as e:
                self.logger.error(f"添加Epic推送订阅失败: {e}")
                return False

    async def remove_subscription(self, group_id: int) -> bool:
        """移除群组订阅"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "DELETE FROM epic_subscriptions WHERE group_id = ?",
                    (str(group_id),)
                )
                await db.commit()
                return True
            except Exception as e:
                self.logger.error(f"移除Epic推送订阅失败: {e}")
                return False

    async def get_all_subscriptions(self) -> List[int]:
        """获取所有订阅的群组"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    "SELECT group_id FROM epic_subscriptions WHERE enabled = 1"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [int(row[0]) for row in rows]
            except Exception as e:
                self.logger.error(f"获取Epic订阅群组失败: {e}")
                return []

    async def fetch_free_games(self):
        """从 Epic API 获取喜加一内容"""
        url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions?locale=zh-CN&country=CN&allowCountries=CN"

        try:
            # 优化超时设置，减少等待时间
            timeout = aiohttp.ClientTimeout(total=20, connect=5, sock_read=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self.parse_free_games(data)
                    else:
                        self.logger.error(f"Epic API请求失败，状态码: {response.status}")
                        return None
        except Exception as e:
            self.logger.error(f"获取Epic免费游戏失败: {e}")
            return None

    def parse_free_games(self, data):
        """解析 API 返回的内容"""
        games = []
        elements = data.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])

        for game in elements:
            # 检查是否为免费游戏
            promotions = game.get("promotions")
            if not promotions:
                continue

            promotional_offers = promotions.get("promotionalOffers", [])
            upcoming_offers = promotions.get("upcomingPromotionalOffers", [])

            # 检查当前是否有免费促销或即将有免费促销
            is_free_now = any(
                offer.get("discountSetting", {}).get("discountPercentage") == 0
                for offer_group in promotional_offers
                for offer in offer_group.get("promotionalOffers", [])
            )

            is_free_upcoming = any(
                offer.get("discountSetting", {}).get("discountPercentage") == 0
                for offer_group in upcoming_offers
                for offer in offer_group.get("promotionalOffers", [])
            )

            if not (is_free_now or is_free_upcoming):
                continue

            title = game.get("title", "未知标题")
            description = game.get("description", "")

            # 获取图片URL
            image_url = None
            key_images = game.get("keyImages", [])
            for img in key_images:
                if img.get("type") == "OfferImageWide":
                    image_url = img.get("url")
                    break

            # 构建商店链接
            link = None
            if game.get("productSlug"):
                link = f"https://store.epicgames.com/zh-CN/p/{game['productSlug']}"
            elif game.get("urlSlug"):
                link = f"https://store.epicgames.com/zh-CN/p/{game['urlSlug']}"
            elif game.get("catalogNs", {}).get("mappings"):
                mappings = game["catalogNs"]["mappings"]
                if mappings:
                    page_slug = mappings[0].get("pageSlug")
                    if page_slug:
                        link = f"https://store.epicgames.com/zh-CN/p/{page_slug}"

            # 获取促销时间信息
            promo_info = ""
            if is_free_now and promotional_offers:
                for offer_group in promotional_offers:
                    for offer in offer_group.get("promotionalOffers", []):
                        start_date = offer.get("startDate")
                        end_date = offer.get("endDate")
                        if end_date:
                            promo_info = f"免费至: {end_date[:10]}"
                        break
                    if promo_info:
                        break
            elif is_free_upcoming and upcoming_offers:
                for offer_group in upcoming_offers:
                    for offer in offer_group.get("promotionalOffers", []):
                        start_date = offer.get("startDate")
                        if start_date:
                            promo_info = f"免费开始: {start_date[:10]}"
                        break
                    if promo_info:
                        break

            games.append({
                "title": title,
                "description": description[:100] + "..." if len(description) > 100 else description,
                "image_url": image_url,
                "link": link,
                "promo_info": promo_info,
                "is_free_now": is_free_now,
                "is_free_upcoming": is_free_upcoming
            })

        return games

    async def fetch_image(self, url):
        """处理图片 URL 重定向"""
        if not url:
            return url

        try:
            # 为了避免事件循环冲突，创建临时会话
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, allow_redirects=False) as response:
                    if response.status == 302:  # 检查是否为重定向
                        return response.headers.get("Location")  # 返回重定向后的 URL
                    return url
        except Exception as e:
            self.logger.warning(f"处理图片URL失败: {e}")
            return url

    def format_games_for_forward(self, games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化游戏信息为合并转发消息格式"""
        if not games:
            return [{
                "type": "node",
                "data": {
                    "nickname": f"{self.bot_name}助手",
                    "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                    "content": "❌ 当前没有免费游戏"
                }
            }]

        forward_messages = []

        # 添加标题消息
        current_free = [g for g in games if g.get("is_free_now")]
        upcoming_free = [g for g in games if g.get("is_free_upcoming")]

        title_text = "🎮 Epic Games 喜加一\n\n"
        if current_free:
            title_text += f"🔥 当前免费: {len(current_free)} 款游戏\n"
        if upcoming_free:
            title_text += f"⏰ 即将免费: {len(upcoming_free)} 款游戏\n"
        title_text += f"📅 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        forward_messages.append({
            "type": "node",
            "data": {
                "nickname": f"{self.bot_name}助手",
                "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                "content": title_text
            }
        })

        # 添加游戏信息
        for i, game in enumerate(games, 1):
            try:
                status_emoji = "🔥" if game.get("is_free_now") else "⏰"
                status_text = "正在免费" if game.get("is_free_now") else "即将免费"

                text_content = f"{status_emoji} 游戏 {i}\n\n" \
                              f"🎮 游戏名称：{game['title']}\n" \
                              f"📝 游戏描述：{game.get('description', '暂无描述')}\n" \
                              f"🎯 状态：{status_text}\n"

                if game.get('promo_info'):
                    text_content += f"⏰ 时间：{game['promo_info']}\n"

                if game.get('link'):
                    text_content += f"🔗 商店链接：{game['link']}\n"

                text_content += "🖼️ 游戏截图："

                # 使用OneBot消息段格式，将文字和图片组合
                content = [
                    {
                        "type": "text",
                        "data": {"text": text_content}
                    }
                ]

                if game.get('image_url'):
                    content.append({
                        "type": "image",
                        "data": {"file": game['image_url']}
                    })

                forward_messages.append({
                    "type": "node",
                    "data": {
                        "nickname": f"{self.bot_name}助手",
                        "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                        "content": content
                    }
                })

            except Exception as e:
                self.logger.error(f"格式化游戏信息失败: {e}")
                continue

        # 添加使用提示
        forward_messages.append({
            "type": "node",
            "data": {
                "nickname": f"{self.bot_name}助手",
                "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                "content": "💡 使用提示：\n\n" \
                          "• 🔥 表示当前正在免费\n" \
                          "• ⏰ 表示即将免费\n" \
                          "• 点击链接可直接前往Epic商店\n" \
                          "• 发送 /Epic推送开启 可开启每日自动推送\n" \
                          "• 发送 /Epic推送关闭 可关闭自动推送"
            }
        })

        return forward_messages

    async def send_free_games(self, group_id: int):
        """发送喜加一内容到群聊（使用合并转发）"""
        try:
            await self.api.post_group_msg(group_id, text="🔍 正在获取Epic免费游戏信息，请稍候...")

            games = await self.fetch_free_games()
            if not games:
                await self.api.post_group_msg(group_id, text="❌ 获取Epic喜加一内容失败，请稍后再试")
                return

            # 格式化为合并转发消息
            forward_messages = self.format_games_for_forward(games)

            # 发送合并转发消息
            success = await _message_sender.send_group_forward_msg(group_id, forward_messages)

            if not success:
                # 如果合并转发失败，发送简化版本
                await self.send_simple_games(group_id, games)

        except Exception as e:
            self.logger.error(f"发送Epic免费游戏失败: {e}")
            await self.api.post_group_msg(group_id, text=f"❌ 发送失败，发生错误：{e}")

    async def send_simple_games(self, group_id: int, games: List[Dict[str, Any]]):
        """发送简化版游戏信息（当合并转发失败时使用）"""
        if not games:
            await self.api.post_group_msg(group_id, text="❌ 当前没有免费游戏")
            return

        current_free = [g for g in games if g.get("is_free_now")]
        upcoming_free = [g for g in games if g.get("is_free_upcoming")]

        message = "🎮 Epic Games 喜加一\n\n"

        if current_free:
            message += "🔥 当前免费游戏：\n"
            for i, game in enumerate(current_free[:3], 1):  # 只显示前3个
                message += f"{i}. {game['title']}\n"
                if game.get('promo_info'):
                    message += f"   {game['promo_info']}\n"
                if game.get('link'):
                    message += f"   {game['link']}\n"
                message += "\n"

        if upcoming_free:
            message += "⏰ 即将免费游戏：\n"
            for i, game in enumerate(upcoming_free[:3], 1):  # 只显示前3个
                message += f"{i}. {game['title']}\n"
                if game.get('promo_info'):
                    message += f"   {game['promo_info']}\n"
                message += "\n"

        message += "💡 发送 /喜加一 查看完整信息"
        await self.api.post_group_msg(group_id, text=message)

    async def daily_push(self):
        """每日Epic免费游戏推送定时任务"""
        try:
            # 使用asyncio.wait_for设置总超时时间，避免定时任务超时
            await asyncio.wait_for(self._execute_daily_push(), timeout=50.0)
        except asyncio.TimeoutError:
            self.logger.warning("Epic免费游戏推送执行超时，但可能已部分完成")
        except Exception as e:
            self.logger.error(f"Epic免费游戏每日推送失败: {e}")

    async def _execute_daily_push(self):
        """执行每日推送的核心逻辑"""
        self.logger.info("开始执行Epic免费游戏每日推送")

        # 获取免费游戏信息
        games = await self.fetch_free_games()
        if not games:
            self.logger.warning("没有获取到Epic免费游戏信息")
            return

        # 格式化消息
        forward_messages = self.format_games_for_forward(games)

        # 获取所有订阅的群组
        subscribed_groups = await self.get_all_subscriptions()

        if not subscribed_groups:
            self.logger.info("没有群组订阅Epic推送")
            return

        # 向每个订阅的群组发送消息
        success_count = 0
        for group_id in subscribed_groups:
            try:
                success = await _message_sender.send_group_forward_msg(group_id, forward_messages)
                if success:
                    success_count += 1
                    self.logger.info(f"已向群组 {group_id} 推送Epic免费游戏")
                else:
                    # 合并转发失败，尝试简化版本
                    await self.send_simple_games(group_id, games)
                    success_count += 1
                    self.logger.info(f"已向群组 {group_id} 推送Epic免费游戏（简化版）")

                # 避免发送过快，减少延迟
                await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.error(f"向群组 {group_id} 推送Epic免费游戏失败: {e}")

        self.logger.info(f"Epic免费游戏推送完成，成功推送到 {success_count}/{len(subscribed_groups)} 个群组")

    @bot.group_event()
    @feature_required("喜加一", "/喜加一")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        group_id = event.group_id

        # 查询免费游戏
        if raw_message == "/喜加一":
            await self.send_free_games(group_id)
            return

        # 开启推送 - 使用不冲突的命令
        if raw_message in ["/Epic推送开启", "/epic推送开启", "/喜加一推送开启"]:
            success = await self.add_subscription(group_id)
            if success:
                await self.api.post_group_msg(
                    group_id,
                    text="✅ 已开启Epic免费游戏每日推送\n"
                         "📅 推送时间：每天上午10:00\n"
                         "🎮 将自动推送Epic商店的免费游戏信息\n"
                         "💡 发送 /Epic推送关闭 可关闭推送"
                )
            else:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 开启Epic推送失败，请稍后再试"
                )
            return

        # 关闭推送 - 使用不冲突的命令
        if raw_message in ["/Epic推送关闭", "/epic推送关闭", "/喜加一推送关闭"]:
            success = await self.remove_subscription(group_id)
            if success:
                await self.api.post_group_msg(
                    group_id,
                    text="✅ 已关闭Epic免费游戏每日推送\n"
                         "💡 发送 /Epic推送开启 可重新开启推送"
                )
            else:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 关闭Epic推送失败，请稍后再试"
                )
            return

    async def on_load(self):
        # 初始化数据库
        await self.init_db()

        # 注册定时任务，每天上午10点推送Epic免费游戏
        self.add_scheduled_task(
            job_func=self.daily_push,
            name="epic_daily_push",
            interval="13:37",  # 每天10点执行
        )

        self.logger.info(f"{self.name} 插件已加载")
        self.logger.info(f"插件版本: {self.version}")

    async def on_unload(self):
        """插件卸载时清理资源"""
        # 由于我们现在使用临时会话，不需要清理持久会话
        self.logger.info(f"{self.name} 插件已卸载")
