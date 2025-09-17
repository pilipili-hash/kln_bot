import re
import logging
import asyncio
from typing import Optional, List, Dict
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from utils.group_forward_msg import send_group_forward_msg_ws
from utils.config_manager import get_config
from PluginManager.plugin_manager import feature_required
from .pixiv_utils import initialize_pixiv_api, fetch_illusts, fetch_ranking, format_illusts, get_illust_detail

bot = CompatibleEnrollment
_log = logging.getLogger(__name__)

class PixivPlugin(BasePlugin):
    name = "PixivPlugin"
    version = "2.0.0"

    async def on_load(self):
        # 初始化插件属性
        self.search_count = 0
        self.ranking_count = 0
        self.error_count = 0
        self.last_search_time = 0
        self.rate_limit_delay = 2.0  # 请求间隔限制

        _log.info(f"{self.name} v{self.version} 插件已加载")

        # 初始化Pixiv API
        try:
            proxy = get_config("proxy")
            refresh_token = get_config("pixiv_refresh_token")
            if not refresh_token:
                _log.error("Pixiv refresh_token 未配置，请检查配置文件")
                raise ValueError("Pixiv refresh_token 未配置，请检查配置文件")

            self.pixiv_api = await initialize_pixiv_api(proxy, refresh_token)
            _log.info("Pixiv插画搜索功能已启用")

        except Exception as e:
            _log.error(f"Pixiv API初始化失败: {e}")
            raise

    async def _check_rate_limit(self):
        """检查请求频率限制"""
        import time
        current_time = time.time()
        if current_time - self.last_search_time < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - (current_time - self.last_search_time)
            await asyncio.sleep(wait_time)
        self.last_search_time = time.time()

    async def get_statistics(self) -> str:
        """获取使用统计"""
        total_requests = self.search_count + self.ranking_count
        success_rate = 0
        if total_requests > 0:
            success_rate = ((total_requests - self.error_count) / total_requests) * 100

        return f"""📊 Pixiv插画统计

🔍 搜索次数: {self.search_count}
📈 榜单查询: {self.ranking_count}
🎯 总请求数: {total_requests}
❌ 失败次数: {self.error_count}
✅ 成功率: {success_rate:.1f}%
⏱️ 请求间隔: {self.rate_limit_delay}秒"""

    @bot.group_event()
    async def handle_search(self, event: GroupMessage):
        """处理 Pixiv 搜索和榜单"""
        raw_message = event.raw_message.strip()

        try:
            if re.match(r"^/pixs", raw_message):
                await self._check_rate_limit()
                parts = re.sub(r"^/pixs", "", raw_message).strip().split()
                query = parts[0] if parts else ""
                page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

                if not query:
                    await self.api.post_group_msg(event.group_id, text="❌ 请输入搜索关键词\n💡 格式：/pixs 关键词 [页码]\n📝 示例：/pixs 原神 2")
                    return

                _log.info(f"用户 {event.user_id} 在群 {event.group_id} 搜索Pixiv: {query}, 页码: {page}")
                await self.api.post_group_msg(event.group_id, text=f"🔍 正在搜索「{query}」第 {page} 页，请稍候...")

                self.search_count += 1
                illusts = await fetch_illusts(self.pixiv_api, query, page)

                if illusts:
                    messages = await format_illusts(illusts)
                    await send_group_forward_msg_ws(event.group_id, messages)
                    _log.info(f"成功返回 {len(illusts)} 个搜索结果")
                else:
                    await self.api.post_group_msg(event.group_id, text=f"❌ 未找到「{query}」相关插画\n💡 尝试使用其他关键词或检查拼写")

            elif re.match(r"^/pixb", raw_message):
                await self._check_rate_limit()
                parts = re.sub(r"^/pixb", "", raw_message).strip().split()
                mode_map = {"日": "day", "周": "week", "月": "month"}
                mode = mode_map.get(parts[0], "day") if parts else "day"
                page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

                if mode not in ["day", "week", "month"]:
                    await self.api.post_group_msg(event.group_id, text="❌ 无效的榜单类型\n💡 可用类型：日、周、月\n📝 示例：/pixb 日 2")
                    return

                _log.info(f"用户 {event.user_id} 在群 {event.group_id} 查询Pixiv榜单: {mode}, 页码: {page}")
                await self.api.post_group_msg(event.group_id, text=f"📈 正在获取{parts[0] if parts else '日'}榜第 {page} 页，请稍候...")

                self.ranking_count += 1
                illusts = await fetch_ranking(self.pixiv_api, mode, page)

                if illusts:
                    messages = await format_illusts(illusts)
                    await send_group_forward_msg_ws(event.group_id, messages)
                    _log.info(f"成功返回 {len(illusts)} 个榜单结果")
                else:
                    await self.api.post_group_msg(event.group_id, text="❌ 未找到相关榜单信息\n💡 请稍后重试或联系管理员")

            elif raw_message == "/pixiv统计":
                try:
                    stats = await self.get_statistics()
                    await self.api.post_group_msg(event.group_id, text=stats)
                except Exception as e:
                    _log.error(f"获取统计信息时出错: {e}")
                    await self.api.post_group_msg(event.group_id, text="❌ 获取统计信息失败")

            elif raw_message == "/pixiv帮助":
                help_text = """🎨 Pixiv插画搜索帮助

📝 基本命令：
• /pixs 关键词 [页码] - 搜索插画
• /pixb [类型] [页码] - 查看榜单
• /pixiv统计 - 查看使用统计
• /pixiv帮助 - 显示此帮助信息

💡 使用示例：
/pixs 原神
/pixs 初音未来 2
/pixb 日
/pixb 周 3
/pixiv统计

📈 榜单类型：
• 日 - 日榜（默认）
• 周 - 周榜
• 月 - 月榜

⚠️ 注意事项：
• 每次请求间隔2秒，避免频繁调用
• 每页显示5个结果
• 需要稳定的网络连接
• 图片可能需要一些时间加载"""

                await self.api.post_group_msg(event.group_id, text=help_text)

        except Exception as e:
            self.error_count += 1
            _log.error(f"处理Pixiv请求时出错: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 系统错误，请稍后再试")
