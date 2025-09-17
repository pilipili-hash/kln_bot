import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain
from utils.onebot_v11_handler import OneBotV11MessageHandler
from .utils import (
    fetch_birthday_data,
    parse_birthday_data,
    format_birthday_message,
    BirthdayCache
)

# 设置日志
_log = logging.getLogger("TodayBirthday.main")

# 尝试导入权限管理
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

class TodayBirthday(BasePlugin):
    name = "TodayBirthday"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        self.cache = BirthdayCache()
        self.message_handler = None

    async def __onload__(self):
        """插件加载时初始化"""
        try:
            _log.info(f"TodayBirthday v{self.version} 插件已加载")

            # 初始化OneBotV11消息处理器
            self.message_handler = OneBotV11MessageHandler()
            _log.info("OneBotV11消息处理器初始化完成")

        except Exception as e:
            _log.error(f"插件加载失败: {e}")
            raise

    @bot.group_event()
    @feature_required("今日生日", "/今日生日")
    async def birthday_command(self, event: GroupMessage):
        """处理今日生日相关命令"""
        try:
            message = event.raw_message.strip()

            if message == "/今日生日" or message == "今日生日":
                await self._handle_today_birthday(event)
            elif message == "/今日生日帮助" or message == "今日生日帮助":
                await self._show_help(event)
            elif message == "/今日生日统计" or message == "今日生日统计":
                await self._show_statistics(event)


        except Exception as e:
            _log.error(f"处理今日生日命令失败: {e}")
            await self.api.post_group_msg(event.group_id, "处理命令时发生错误，请稍后再试。")

    async def _handle_today_birthday(self, event: GroupMessage):
        """处理今日生日查询"""
        group_id = event.group_id
        user_id = event.self_id

        try:
            # 发送加载提示
            await self.api.post_group_msg(group_id, "🎂 正在获取今日生日数据，请稍候...")

            # 尝试从缓存获取数据
            cached_data = self.cache.get_today_birthday()
            if cached_data:
                character_list = cached_data
            else:
                html_content = await fetch_birthday_data()
                if not html_content:
                    await self.api.post_group_msg(group_id, "❌ 获取今日生日数据失败，请稍后再试。")
                    return

                character_list = parse_birthday_data(html_content)
                if character_list:
                    self.cache.set_today_birthday(character_list)

            if character_list:
                # 格式化合并转发消息
                messages = await format_birthday_message(character_list, user_id)

                # 发送合并转发消息
                await self._send_birthday_messages(group_id, character_list, messages)
            else:
                await self.api.post_group_msg(group_id, "🎂 今日没有动漫角色生日哦~")

        except Exception as e:
            _log.error(f"处理今日生日查询失败: {e}")
            await self.api.post_group_msg(group_id, "❌ 获取今日生日数据时发生错误，请稍后再试。")

    async def _send_birthday_messages(self, group_id: int, character_list: List[Dict[str, Any]], messages: List[Dict[str, Any]]):
        """发送生日消息，优先使用合并转发"""
        try:
            # 策略1: 尝试合并转发（优先策略）
            if self.message_handler and len(character_list) > 0:
                try:
                    success = await self.message_handler.send_forward_message(
                        group_id=group_id,
                        messages=messages
                    )

                    if success:
                        return

                except Exception as e:
                    _log.warning(f"合并转发失败: {e}")
                    # 继续尝试其他策略

            # 策略2: 分批发送（降级策略）
            if len(character_list) > 8:
                try:
                    await self._send_birthday_in_batches(group_id, character_list)
                    return
                except Exception as e:
                    _log.warning(f"分批发送失败: {e}")

            # 策略3: 普通文本发送（兜底策略）
            await self._send_birthday_as_text(group_id, character_list)

        except Exception as e:
            _log.error(f"所有发送策略都失败: {e}")
            await self.api.post_group_msg(group_id, "❌ 发送生日信息时发生错误，请稍后再试。")

    async def _send_birthday_in_batches(self, group_id: int, character_list: List[Dict[str, Any]]):
        """分批发送生日信息"""
        try:
            today = datetime.now().strftime("%Y年%m月%d日")

            # 发送标题
            title_msg = f"🎂 {today} 今日生日角色\n📊 共找到 {len(character_list)} 个角色过生日"
            await self.api.post_group_msg(group_id, title_msg)
            await asyncio.sleep(0.3)  # 短暂延迟

            # 分批发送，每批6个角色
            batch_size = 6
            total_batches = (len(character_list) + batch_size - 1) // batch_size

            for batch_num, i in enumerate(range(0, len(character_list), batch_size), 1):
                batch = character_list[i:i + batch_size]

                # 构建批次消息
                batch_header = f"📋 第 {batch_num}/{total_batches} 批："
                batch_content = []

                for j, character in enumerate(batch, i + 1):
                    name = character['name']
                    # 添加一些装饰性emoji
                    emoji = "🎉" if j % 3 == 1 else "🎈" if j % 3 == 2 else "🎁"
                    batch_content.append(f"{emoji} {j}. {name}")

                batch_msg = batch_header + "\n" + "\n".join(batch_content)

                await self.api.post_group_msg(group_id, batch_msg)

                # 添加适当延迟避免发送过快
                if batch_num < total_batches:  # 最后一批不需要延迟
                    await asyncio.sleep(0.8)

            # 发送尾部信息
            await asyncio.sleep(0.5)
            footer_msg = "🎊 生日快乐！\n📊 数据来源：Bangumi.tv\n� 发送 '/今日生日帮助' 查看更多功能"
            await self.api.post_group_msg(group_id, footer_msg)



        except Exception as e:
            _log.error(f"分批发送失败: {e}")
            raise

    async def _send_birthday_as_text(self, group_id: int, character_list: List[Dict[str, Any]]):
        """以普通文本形式发送生日信息"""
        try:
            today = datetime.now().strftime("%Y年%m月%d日")
            text_message = f"🎂 {today} 今日生日角色：\n\n"

            # 限制显示数量避免消息过长
            display_count = min(len(character_list), 15)
            for i, character in enumerate(character_list[:display_count], 1):
                text_message += f"{i}. {character['name']}\n"

            if len(character_list) > display_count:
                text_message += f"\n还有 {len(character_list) - display_count} 个角色..."

            text_message += f"\n\n📊 数据来源：Bangumi.tv"

            await self.api.post_group_msg(group_id, text_message)


        except Exception as e:
            _log.error(f"发送文本生日信息失败: {e}")
            await self.api.post_group_msg(group_id, "❌ 发送生日信息失败。")

    async def _show_help(self, event: GroupMessage):
        """显示帮助信息"""
        help_text = """🎂 今日生日插件帮助 v2.0.0

📝 基础命令：
• /今日生日 - 查看今日生日的动漫角色
• 今日生日 - 查看今日生日的动漫角色
• /今日生日帮助 - 显示此帮助信息
• /今日生日统计 - 查看缓存统计信息

🎯 功能特点：
• 📊 数据来源：Bangumi.tv
• 🚀 智能缓存：避免重复请求
• 📱 合并转发：美观的消息展示，带缩略图
• 🔄 自动降级：转发失败时使用文本

⚠️ 注意事项：
• 数据每日自动更新
• 图片可能需要时间加载
• 网络异常时会显示错误提示

发送 "/今日生日" 开始查看今日生日角色！"""

        await self.api.post_group_msg(event.group_id, help_text)

    async def _show_statistics(self, event: GroupMessage):
        """显示统计信息"""
        try:
            stats = self.cache.get_statistics()
            stats_text = f"""📊 今日生日插件统计信息

🗄️ 缓存状态：
• 缓存命中次数：{stats['cache_hits']}
• 网络请求次数：{stats['network_requests']}
• 缓存命中率：{stats['hit_rate']:.1f}%

📅 数据状态：
• 最后更新时间：{stats['last_update']}
• 缓存是否有效：{'是' if stats['cache_valid'] else '否'}

🎂 今日角色数量：{stats['today_count']}"""

            await self.api.post_group_msg(event.group_id, stats_text)

        except Exception as e:
            _log.error(f"显示统计信息失败: {e}")
            await self.api.post_group_msg(event.group_id, "❌ 获取统计信息失败。")


