import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, date

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_msg_cq
from .utils import (
    generate_signin_image,
    initialize_database,
    can_sign_in,
    record_sign_in,
    get_user_signin_stats,
    get_group_signin_ranking,
    get_user_signin_streak
)

# 尝试导入插件管理器
try:
    from PluginManager.plugin_manager import feature_required
except ImportError:
    def feature_required(feature_name=None, commands=None, require_admin=False):
        """简单的装饰器替代版本"""
        def decorator(func):
            async def wrapper(self, *args, **kwargs):
                return await func(self, *args, **kwargs)
            return wrapper
        return decorator

bot = CompatibleEnrollment
_log = logging.getLogger("SignIn.main")

class SignIn(BasePlugin):
    name = "SignIn"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        self.signin_cache = {}  # 简单的内存缓存

    async def on_load(self):
        """插件加载时初始化（兼容旧版本）"""
        try:
            _log.info(f"SignIn v{self.version} 插件已加载")
            await initialize_database()
            _log.info("签到数据库初始化完成")
        except Exception as e:
            _log.error(f"插件加载失败: {e}")

    async def __onload__(self):
        """插件加载时初始化（新版本）"""
        await self.on_load()

    @bot.group_event()
    @feature_required(feature_name="签到系统", commands=["签到", "/签到帮助", "/签到统计", "/签到排行"])
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        try:
            message = event.raw_message.strip()

            if message == "签到":
                await self._handle_signin(event)
            elif message == "/签到帮助" or message == "签到帮助":
                await self._show_help(event)
            elif message == "/签到统计" or message == "签到统计":
                await self._show_user_stats(event)
            elif message == "/签到排行" or message == "签到排行":
                await self._show_group_ranking(event)

        except Exception as e:
            _log.error(f"处理签到命令失败: {e}")
            await self.api.post_group_msg(event.group_id, "处理命令时发生错误，请稍后再试。")

    async def _handle_signin(self, event: GroupMessage):
        """处理签到请求"""
        user_id = event.user_id
        group_id = event.group_id
        nickname = event.sender.card if event.sender.card else event.sender.nickname

        try:
            if await can_sign_in(user_id, group_id):
                # 记录签到
                await record_sign_in(user_id, group_id)

                # 获取连续签到天数
                streak = await get_user_signin_streak(user_id, group_id)

                # 生成签到图片
                image_data = await generate_signin_image(user_id, nickname, streak)
                if image_data:
                    await send_group_msg_cq(group_id, image_data)
                else:
                    await self.api.post_group_msg(group_id, "签到图片生成失败，请稍后再试。")
            else:
                # 获取用户今日签到信息
                stats = await get_user_signin_stats(user_id, group_id)
                streak = await get_user_signin_streak(user_id, group_id)

                message = f"🎯 {nickname}，你今天已经签到过了！\n"
                message += f"📅 连续签到：{streak} 天\n"
                message += f"📊 总签到次数：{stats['total_days']} 天"

                await self.api.post_group_msg(group_id, message)

        except Exception as e:
            _log.error(f"处理签到失败: {e}")
            await self.api.post_group_msg(group_id, "签到处理失败，请稍后再试。")

    async def _show_help(self, event: GroupMessage):
        """显示帮助信息"""
        help_text = """📝 签到系统帮助 v2.0.0

🎯 基础命令：
• 签到 - 每日签到，获得精美签到卡片
• /签到帮助 - 显示此帮助信息
• /签到统计 - 查看个人签到统计
• /签到排行 - 查看群内签到排行榜

✨ 功能特点：
• 🎨 精美的签到卡片设计，质感十足
• 💭 温暖有趣的日常分享
• ✨ 贴心的每日小提醒
• 📈 连续签到统计，激励坚持
• 🏆 群内排行榜，增加互动

🎁 签到奖励：
• 连续签到可获得特殊称号
• 每日都有温暖有趣的分享
• 贴心的生活小提醒

💡 使用提示：
• 每天只能签到一次
• 连续签到天数会累计
• 断签会重置连续天数

发送 "签到" 开始你的每日打卡之旅！"""

        await self.api.post_group_msg(event.group_id, help_text)

    async def _show_user_stats(self, event: GroupMessage):
        """显示用户签到统计"""
        try:
            user_id = event.user_id
            group_id = event.group_id
            nickname = event.sender.card if event.sender.card else event.sender.nickname

            stats = await get_user_signin_stats(user_id, group_id)
            streak = await get_user_signin_streak(user_id, group_id)

            if stats['total_days'] == 0:
                await self.api.post_group_msg(group_id, f"📊 {nickname}，你还没有签到记录哦！\n发送 \"签到\" 开始你的签到之旅吧！")
                return

            # 计算签到率（假设从第一次签到开始计算）
            signin_rate = min(100, (stats['total_days'] / max(1, stats['days_since_first'])) * 100)

            message = f"📊 {nickname} 的签到统计\n\n"
            message += f"📅 总签到天数：{stats['total_days']} 天\n"
            message += f"🔥 连续签到：{streak} 天\n"
            message += f"📈 签到率：{signin_rate:.1f}%\n"
            message += f"🗓️ 首次签到：{stats['first_signin']}\n"
            message += f"⏰ 最近签到：{stats['last_signin']}\n\n"

            # 根据签到天数给予称号
            if stats['total_days'] >= 365:
                message += "🏆 称号：签到大师 (365天+)"
            elif stats['total_days'] >= 100:
                message += "🥇 称号：签到达人 (100天+)"
            elif stats['total_days'] >= 30:
                message += "🥈 称号：签到能手 (30天+)"
            elif stats['total_days'] >= 7:
                message += "🥉 称号：签到新星 (7天+)"
            else:
                message += "🌱 称号：签到萌新"

            await self.api.post_group_msg(group_id, message)

        except Exception as e:
            _log.error(f"显示用户统计失败: {e}")
            await self.api.post_group_msg(event.group_id, "获取统计信息失败，请稍后再试。")

    async def _show_group_ranking(self, event: GroupMessage):
        """显示群签到排行榜"""
        try:
            group_id = event.group_id
            ranking = await get_group_signin_ranking(group_id)

            if not ranking:
                await self.api.post_group_msg(group_id, "📊 暂无签到排行数据，快来签到吧！")
                return

            message = "🏆 群签到排行榜 (Top 10)\n\n"

            medals = ["🥇", "🥈", "🥉"]
            for i, (user_id, total_days, streak) in enumerate(ranking[:10]):
                rank = i + 1
                medal = medals[i] if i < 3 else f"{rank}."

                # 这里可以尝试获取用户昵称，但简化处理
                user_display = f"用户{user_id}"

                message += f"{medal} {user_display}\n"
                message += f"   📅 总签到：{total_days}天 🔥 连续：{streak}天\n\n"

            message += "💡 发送 \"签到\" 参与排行榜竞争！"

            await self.api.post_group_msg(group_id, message)

        except Exception as e:
            _log.error(f"显示排行榜失败: {e}")
            await self.api.post_group_msg(event.group_id, "获取排行榜失败，请稍后再试。")
