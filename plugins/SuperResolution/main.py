import aiohttp
import base64
import logging
import time
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Image
from PluginManager.plugin_manager import feature_required
from utils.config_manager import get_config

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class SuperResolution(BasePlugin):
    name = "SuperResolution"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.help_count = 0

        # 频率控制
        self.last_request_time = {}
        self.request_interval = 5.0  # 5秒间隔

        # 等待状态管理
        self.pending_super_resolution = {}

    async def on_load(self):
        """插件加载时初始化"""
        try:
            self.chaofen_url = get_config("chaofen_url")

            if not self.chaofen_url:
                _log.error("chaofen_url 配置未找到，请检查配置文件")
            else:
                _log.info(f"SuperResolution v{self.version} 插件已加载，超分辨率服务地址: {self.chaofen_url}")
        except Exception as e:
            _log.error(f"SuperResolution插件加载失败: {e}")

    def _check_frequency_limit(self, user_id: int) -> tuple[bool, float]:
        """检查用户请求频率限制"""
        current_time = time.time()

        if user_id in self.last_request_time:
            time_diff = current_time - self.last_request_time[user_id]
            if time_diff < self.request_interval:
                remaining_time = self.request_interval - time_diff
                return False, remaining_time

        self.last_request_time[user_id] = current_time
        return True, 0.0

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🔍 SuperResolution超分辨率插件帮助

🎯 功能说明：
使用AI技术对图片进行超分辨率处理，提升图片清晰度和分辨率

🔍 使用方法：
• /超 [图片] - 对图片进行超分辨率处理
• /超分辨率帮助 - 显示此帮助信息
• /超分辨率统计 - 查看使用统计
• /取消 - 取消当前超分辨率操作

💡 使用示例：
/超 [发送图片]
或
/超
[等待提示后发送图片]

🎨 处理效果：
• 📈 分辨率提升：图片分辨率提升2倍
• 🔧 降噪处理：自动去除图片噪点
• 🎯 细节增强：增强图片细节和清晰度
• 🖼️ 保持质量：保持原图色彩和风格

⚙️ 技术特性：
• 🤖 AI驱动：基于深度学习的超分辨率算法
• ⚡ 快速处理：通常在10-30秒内完成
• 🔄 自动处理：自动下载、处理、上传
• 🛡️ 错误恢复：完善的错误处理机制

⚠️ 注意事项：
• 请求间隔为5秒，避免频繁调用
• 支持常见图片格式（jpg、png、gif等）
• 图片大小建议在10MB以内
• 处理时间取决于图片大小和服务器负载
• 需要配置超分辨率服务地址才能使用

🔧 版本: v2.0.0
💡 提示：发送"/超"命令后上传图片即可开始处理！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0

        stats_text = f"""📊 SuperResolution超分辨率插件统计

🔍 处理成功: {self.success_count} 次
📋 处理请求: {self.request_count} 次
❌ 处理失败: {self.error_count} 次
❓ 查看帮助: {self.help_count} 次
📊 成功率: {success_rate:.1f}%

⏱️ 请求间隔: {self.request_interval} 秒

💡 使用提示：
• 发送"/超"命令开始超分辨率处理
• 发送"/超分辨率帮助"查看详细帮助
• 支持2倍分辨率提升和降噪处理"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def request_super_resolution(self, image_url: str) -> str:
        """
        调用超分辨率 API 并返回处理后的图片 URL。
        """
        try:
            if not self.chaofen_url:
                _log.error("超分辨率服务未配置")
                return None

            api_url = f"{self.chaofen_url}/api/predict"
            session_hash = ""
            model_name = "up2x-latest-denoise2x.pth"

            # 下载图片并转换为 Base64 编码
            timeout = aiohttp.ClientTimeout(total=60)  # 60秒超时
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # 保持原始协议，不强制转换为http
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        # 检查图片大小
                        if len(image_data) > 10 * 1024 * 1024:  # 10MB限制
                            _log.warning(f"图片过大: {len(image_data)} bytes")
                            return None
                        image_base64 = base64.b64encode(image_data).decode("utf-8")
                    else:
                        _log.error(f"下载图片失败，状态码: {response.status}")
                        return None

            payload = {
                "fn_index": 0,
                "data": [
                    f"data:image/jpeg;base64,{image_base64}",
                    model_name,
                    2
                ],
                "session_hash": session_hash
            }

            # 处理超分辨率请求
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(api_url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result and "data" in result and len(result["data"]) > 0:
                            _log.info("超分辨率处理成功")
                            return result["data"][0]
                        else:
                            _log.error("API返回数据格式错误")
                            return None
                    else:
                        _log.error(f"超分辨率API请求失败，状态码: {response.status}")
                        return None
        except Exception as e:
            _log.error(f"超分辨率处理时出错: {e}")
            return None

    async def handle_super_resolution(self, group_id: int, image_url: str, message_id: int, user_id: int):
        """
        处理超分辨率逻辑。
        """
        try:
            # 更新统计
            self.request_count += 1

            await self.api.post_group_msg(group_id, text="🔍 正在处理图片超分辨率，请稍候...")

            result_url = await self.request_super_resolution(image_url)
            if result_url:
                await self.api.post_group_msg(
                    group_id,
                    rtf=MessageChain([Image(result_url)]),
                    reply=message_id
                )
                self.success_count += 1
                _log.info(f"超分辨率处理成功: 用户{user_id}, 群{group_id}")
            else:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 超分辨率处理失败，请检查图片格式或稍后再试"
                )
                self.error_count += 1
        except Exception as e:
            _log.error(f"处理超分辨率时出错: {e}")
            await self.api.post_group_msg(
                group_id,
                text="❌ 超分辨率处理时发生错误，请稍后再试"
            )
            self.error_count += 1

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件。
        """
        group_id = event.group_id
        user_id = event.user_id
        raw_message = event.raw_message.strip()

        # 帮助命令
        if raw_message in ["/超分辨率帮助", "/超帮助", "超分辨率帮助", "超帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/超分辨率统计", "/超统计", "超分辨率统计", "超统计"]:
            await self.show_statistics(group_id)
            return
        elif raw_message in ["/取消", "取消"] and group_id in self.pending_super_resolution:
            if self.pending_super_resolution[group_id] == user_id:
                del self.pending_super_resolution[group_id]
                await self.api.post_group_msg(group_id, text="✅ 已取消超分辨率操作")
            return

        # 超分辨率命令
        if raw_message.startswith("/超"):
            # 频率控制检查
            can_request, remaining_time = self._check_frequency_limit(user_id)
            if not can_request:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
                )
                return

            # 检查是否配置了服务
            if not self.chaofen_url:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 超分辨率服务未配置，请联系管理员"
                )
                return

            # 检查消息中是否包含图片
            for segment in event.message:
                if segment["type"] == "image":
                    image_url = segment["data"].get("url")
                    if image_url:
                        await self.handle_super_resolution(group_id, image_url, event.message_id, user_id)
                        return

            # 没有图片，记录用户状态等待后续图片
            self.pending_super_resolution[group_id] = user_id
            await self.api.post_group_msg(
                group_id,
                text="📷 请发送图片以完成超分辨率处理，或发送\"取消\"退出操作"
            )
            return

        # 处理等待中的图片
        if group_id in self.pending_super_resolution and self.pending_super_resolution[group_id] == user_id:
            for segment in event.message:
                if segment["type"] == "image":
                    image_url = segment["data"].get("url")
                    if image_url:
                        del self.pending_super_resolution[group_id]
                        await self.handle_super_resolution(group_id, image_url, event.message_id, user_id)
                        return

    async def on_unload(self):
        """插件卸载时清理资源"""
        try:
            _log.info("SuperResolution插件正在卸载...")
            # 清理等待状态
            self.pending_super_resolution.clear()
            _log.info("SuperResolution插件卸载完成")
        except Exception as e:
            _log.error(f"插件卸载时出错: {e}")
