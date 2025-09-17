from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .utils import create_client, handle_search_request, handle_download_request
import re
import os
import time
import asyncio
import logging

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class JmSearch(BasePlugin):
    name = "JmSearch"  # 插件名称
    version = "2.0.0"  # 插件版本

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 统计信息
        self.request_count = 0
        self.search_count = 0
        self.download_count = 0
        self.success_count = 0
        self.error_count = 0
        self.help_count = 0

        # 频率控制
        self.last_request_time = {}
        self.request_interval = 5.0  # 5秒间隔

        # 客户端初始化标志
        self.client_initialized = False

        # 下载状态管理
        self.active_downloads = set()  # 正在下载的漫画ID

    def _check_frequency_limit(self, user_id: int) -> tuple[bool, float]:
        """检查用户请求频率限制"""
        current_time = time.time()
        last_time = self.last_request_time.get(user_id, 0)
        time_diff = current_time - last_time

        if time_diff < self.request_interval:
            remaining_time = self.request_interval - time_diff
            return False, remaining_time

        self.last_request_time[user_id] = current_time
        return True, 0.0

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        self.help_count += 1
        help_text = """🔍 禁漫搜索插件帮助 v2.0.0

🎯 功能说明：
搜索和下载禁漫天堂的漫画资源

🔍 使用方法：
• /jm搜索 [关键词] - 搜索漫画
• /jm下载 [ID] - 下载指定漫画
• /jm帮助 - 显示此帮助信息
• /jm统计 - 查看使用统计

💡 使用示例：
/jm搜索 恋爱
/jm下载 123456

🎨 功能特色：
• 🔍 智能搜索：支持关键词搜索漫画
• 📚 批量显示：一次显示多个搜索结果
• 📥 快速下载：支持PDF格式下载
• 🖼️ 图片预览：显示漫画封面图片
• ⚡ 智能缓存：优化下载速度
• 📊 详细统计：搜索和下载统计
• ⏱️ 智能频率控制（5秒间隔）

📥 下载功能：
• 支持PDF格式下载
• 自动文件管理和存储
• 下载完成后自动@用户
• 支持群文件直接发送

⚠️ 注意事项：
• 请求间隔为5秒，避免频繁调用
• 下载的内容请遵守相关法律法规
• 仅供学习和研究使用
• 请尊重版权和作者权益
• 下载文件会保存在服务器上

🔧 版本: v2.0.0
💡 提示：发送"/jm搜索 关键词"开始搜索漫画！"""

        await self.api.post_group_msg(group_id, text=help_text)

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        success_rate = (self.success_count / max(self.request_count, 1)) * 100
        active_downloads_count = len(self.active_downloads)

        stats_text = f"""📊 禁漫搜索插件统计 v2.0.0

📈 使用统计：
🔢 总请求数: {self.request_count}
🔍 搜索次数: {self.search_count}
📥 下载次数: {self.download_count}
✅ 成功次数: {self.success_count}
❌ 失败次数: {self.error_count}
📈 成功率: {success_rate:.1f}%
📖 帮助查看: {self.help_count}次
⏱️ 请求间隔: {self.request_interval}秒

📥 下载状态：
🔄 正在下载: {active_downloads_count}个任务
⚡ 异步下载: 不阻塞其他命令

💡 提示：发送"/jm帮助"查看详细帮助"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def on_load(self):
        """插件加载时的初始化逻辑"""
        try:
            _log.info(f"JmSearch v{self.version} 插件已加载")

            # 初始化客户端
            try:
                self.option, self.client = create_client('jmoption.yml')
                self.client_initialized = True
                _log.info("禁漫客户端初始化成功")
            except Exception as e:
                _log.error(f"禁漫客户端初始化失败: {e}")
                self.client_initialized = False

            # 检查并创建 static/jm 文件夹
            static_jm_path = os.path.join("static/jm")
            if not os.path.exists(static_jm_path):
                os.makedirs(static_jm_path)
                _log.info("创建static/jm文件夹成功")

        except Exception as e:
            _log.error(f"JmSearch插件加载失败: {e}")

    async def _handle_async_download(self, group_id: int, album_id: str, user_id: int):
        """处理异步下载任务"""
        try:
            await handle_download_request(self.api, self.option, group_id, album_id, user_id)
            self.success_count += 1
            _log.info(f"禁漫异步下载成功: 用户{user_id}, 群{group_id}, ID{album_id}")
        except Exception as e:
            self.error_count += 1
            _log.error(f"禁漫异步下载失败: {e}")
            await self.api.post_group_msg(
                group_id,
                text=f"❌ 异步下载失败: {str(e)}\n🆔 漫画ID: {album_id}\n\n💡 请检查漫画ID是否正确"
            )
        finally:
            # 无论成功失败，都从下载队列移除
            self.active_downloads.discard(album_id)
            _log.debug(f"从下载队列移除: {album_id}")

    async def on_unload(self):
        """插件卸载时清理资源"""
        try:
            _log.info("JmSearch插件正在卸载...")
            # 清理客户端连接
            if hasattr(self, 'client') and self.client:
                self.client = None
            # 清理下载队列
            self.active_downloads.clear()
            _log.info("JmSearch插件卸载完成")
        except Exception as e:
            _log.error(f"插件卸载时出错: {e}")

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        group_id = event.group_id
        user_id = event.user_id
        # 帮助命令
        if raw_message in ["/jm帮助", "/禁漫帮助", "jm帮助", "禁漫帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/jm统计", "jm统计"]:
            await self.show_statistics(group_id)
            return

        # 检查客户端是否初始化
        if not self.client_initialized:
            await self.api.post_group_msg(
                group_id,
                text="❌ 禁漫客户端未初始化，请检查配置文件\n\n💡 请确保jmoption.yml配置文件存在且正确"
            )
            return

        # 处理 /jm搜索 命令
        match_search = re.match(r"^/jm搜索\s+(.+)$", raw_message)
        if match_search:
            # 频率控制检查
            can_request, remaining_time = self._check_frequency_limit(user_id)
            if not can_request:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
                )
                return

            query = match_search.group(1).strip()
            if not query:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 搜索关键词不能为空\n\n💡 例如：/jm搜索 恋爱"
                )
                return

            # 更新统计
            self.request_count += 1
            self.search_count += 1

            page = 1  # 默认搜索第一页
            try:
                await handle_search_request(self.api, self.client, group_id, query, page)
                self.success_count += 1
                _log.info(f"禁漫搜索成功: 用户{user_id}, 群{group_id}, 关键词'{query}'")
            except Exception as e:
                self.error_count += 1
                _log.error(f"禁漫搜索失败: {e}")
                await self.api.post_group_msg(
                    group_id,
                    text=f"❌ 搜索失败: {str(e)}\n\n💡 请稍后再试或检查关键词"
                )
            return

        # 处理 /jm下载 命令
        match_download = re.match(r"^/jm下载\s+(\d+)$", raw_message)
        if match_download:
            # 频率控制检查
            can_request, remaining_time = self._check_frequency_limit(user_id)
            if not can_request:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
                )
                return

            album_id = match_download.group(1).strip()
            if not album_id:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 漫画ID不能为空\n\n💡 例如：/jm下载 123456"
                )
                return

            # 检查是否已经在下载
            if album_id in self.active_downloads:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⚠️ 漫画 {album_id} 正在下载中，请等待完成\n\n💡 异步下载不会阻塞其他命令"
                )
                return

            # 更新统计
            self.request_count += 1
            self.download_count += 1

            # 添加到下载队列
            self.active_downloads.add(album_id)

            try:
                # 创建异步任务，不等待完成
                asyncio.create_task(self._handle_async_download(group_id, album_id, user_id))
                _log.info(f"禁漫异步下载任务创建: 用户{user_id}, 群{group_id}, ID{album_id}")
            except Exception as e:
                # 如果创建任务失败，从下载队列移除
                self.active_downloads.discard(album_id)
                self.error_count += 1
                _log.error(f"禁漫下载任务创建失败: {e}")
                await self.api.post_group_msg(
                    group_id,
                    text=f"❌ 下载任务创建失败: {str(e)}\n\n💡 请检查漫画ID是否正确"
                )
