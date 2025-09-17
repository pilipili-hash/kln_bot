from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, CustomMusic, Image
from utils.group_forward_msg import send_group_forward_msg_ws
from .utils import fetch_asmr_data, fetch_audio_data, format_asmr_data, generate_audio_list_image
import re
import tempfile
import os
import logging
import time

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class AsmrSearch(BasePlugin):
    name = "AsmrSearch"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.help_count = 0
        self.audio_play_count = 0

        # 频率控制
        self.last_request_time = {}
        self.request_interval = 3.0  # 3秒间隔

        # 等待状态管理
        self.pending_search = {}

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
        help_text = """🎵 ASMR搜索插件帮助 v2.0.0

🎯 功能说明：
搜索和播放ASMR音频资源，支持在线试听和下载

🔍 使用方法：
• /asmr [页码] - 搜索ASMR资源列表
• /听 [RJID] - 获取指定ASMR的音频列表
• [数字] - 播放音频列表中的指定音频
• /asmr帮助 - 显示此帮助信息
• /asmr统计 - 查看使用统计

💡 使用示例：
/asmr 1
/听 RJ123456
3

🎨 功能特色：
• 🔍 智能搜索：支持分页浏览ASMR资源
• 🎵 在线试听：直接在群内播放音频
• 📊 详细信息：显示评分、标签等详细信息
• 🖼️ 可视化列表：生成美观的音频列表图片
• ⚡ 快速响应：优化的API调用和缓存机制

🎵 音频格式：
• 支持MP3和WAV格式音频
• 自动筛选可播放的音频文件
• 提供高质量的音频流

⚠️ 注意事项：
• 请求间隔为3秒，避免频繁调用
• 音频播放需要支持的客户端
• 部分资源可能需要特殊权限
• 请遵守相关法律法规

🔧 版本: v2.0.0
💡 提示：发送"/asmr 1"开始搜索ASMR资源！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0

        stats_text = f"""📊 ASMR搜索插件统计

🔍 搜索请求: {self.request_count} 次
✅ 成功次数: {self.success_count} 次
❌ 失败次数: {self.error_count} 次
🎵 音频播放: {self.audio_play_count} 次
❓ 查看帮助: {self.help_count} 次
📊 成功率: {success_rate:.1f}%

⏱️ 请求间隔: {self.request_interval} 秒

💡 使用提示：
• 发送"/asmr帮助"查看详细帮助
• 发送"/asmr 1"开始搜索ASMR资源
• 支持MP3和WAV格式音频播放"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def handle_audio_request(self, group_id: int, audio_id: int):
        """处理音频请求"""
        try:
            await self.api.post_group_msg(group_id, text="🔍 正在获取音频列表，请稍候...")

            data = await fetch_audio_data(audio_id)
            if not data:
                await self.api.post_group_msg(group_id, text="❌ 未找到相关音频数据，请检查RJID是否正确")
                self.error_count += 1
                return

            # 提取 MP3 和 WAV 格式的音频
            audio_list = []
            for folder in data:
                if folder.get("type") == "folder":
                    for child in folder.get("children", []):
                        if (child.get("type") == "audio" and
                            (".mp3" in child.get("title", "").lower() or
                             ".wav" in child.get("title", "").lower())):
                            audio_list.append({
                                "title": child["title"],
                                "stream_url": child["mediaStreamUrl"]
                            })

            if not audio_list:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 未找到MP3或WAV格式的音频文件\n\n💡 该资源可能不包含可播放的音频格式"
                )
                self.error_count += 1
                return

            # 生成音频列表图片
            try:
                image_data = generate_audio_list_image(audio_list)

                # 将 BytesIO 对象保存为临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                    temp_file.write(image_data.getvalue())
                    temp_file_path = temp_file.name

                try:
                    # 使用临时文件路径发送图片
                    await self.api.post_group_msg(
                        group_id,
                        rtf=MessageChain([
                            Text(f"🎵 找到 {len(audio_list)} 个音频文件\n\n💡 发送数字选择要播放的音频："),
                            Image(temp_file_path)
                        ])
                    )

                    # 保存音频列表到上下文
                    self.pending_search[group_id] = audio_list
                    self.success_count += 1
                    _log.info(f"成功获取音频列表: RJID={audio_id}, 群{group_id}, 音频数量={len(audio_list)}")

                finally:
                    # 删除临时文件
                    if os.path.exists(temp_file_path):
                        os.remove(temp_file_path)

            except Exception as e:
                _log.error(f"生成音频列表图片失败: {e}")
                # 如果图片生成失败，发送文本列表
                text_list = f"🎵 找到 {len(audio_list)} 个音频文件：\n\n"
                for idx, audio in enumerate(audio_list[:10], 1):  # 限制显示前10个
                    text_list += f"{idx}. {audio['title']}\n"
                if len(audio_list) > 10:
                    text_list += f"\n... 还有 {len(audio_list) - 10} 个音频文件"
                text_list += "\n\n💡 发送数字选择要播放的音频"

                await self.api.post_group_msg(group_id, text=text_list)
                self.pending_search[group_id] = audio_list
                self.success_count += 1

        except Exception as e:
            _log.error(f"处理音频请求时出错: {e}")
            await self.api.post_group_msg(
                group_id,
                text="❌ 获取音频列表时发生错误，请稍后再试"
            )
            self.error_count += 1

    async def handle_audio_play_request(self, group_id: int, user_id: int, user_input: int):
        """处理播放音频请求"""
        try:
            if group_id not in self.pending_search:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 请先发送 /听 [RJID] 获取音频列表\n\n💡 例如：/听 RJ123456"
                )
                return

            audio_list = self.pending_search[group_id]
            if user_input < 1 or user_input > len(audio_list):
                await self.api.post_group_msg(
                    group_id,
                    text=f"❌ 无效的音频编号，请输入 1-{len(audio_list)} 之间的数字"
                )
                return

            audio = audio_list[user_input - 1]

            # 发送处理中提示
            await self.api.post_group_msg(group_id, text="🎵 正在准备音频播放...")

            custom_music = CustomMusic(
                audio=audio["stream_url"],
                title=f"🎵 点击右边的播放按钮播放音频",
                url=audio["stream_url"],
                image=f"https://q.qlogo.cn/g?b={user_id}&nk=&s=640",
                singer="ASMR音频"
            )

            await self.api.post_group_msg(group_id, rtf=MessageChain([custom_music]))

            # 更新统计
            self.audio_play_count += 1
            _log.info(f"音频播放成功: 用户{user_id}, 群{group_id}, 音频: {audio['title']}")

            # 音频发送后删除记录
            del self.pending_search[group_id]

        except Exception as e:
            _log.error(f"处理音频播放请求时出错: {e}")
            await self.api.post_group_msg(
                group_id,
                text="❌ 音频播放失败，请稍后再试"
            )
    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        group_id = event.group_id
        user_id = event.user_id

        # 帮助命令
        if raw_message in ["/asmr帮助", "/asmr help", "asmr帮助", "asmr help"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/asmr统计", "asmr统计"]:
            await self.show_statistics(group_id)
            return

        # ASMR搜索命令
        match = re.match(r"^/asmr\s+(\d+)$", raw_message)
        match_list = re.match(r"^/听\s+(\d+)$", raw_message)

        if match:
            # 频率控制检查
            can_request, remaining_time = self._check_frequency_limit(user_id)
            if not can_request:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
                )
                return

            page = int(match.group(1))
            if page < 1:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 页码必须大于0\n\n💡 例如：/asmr 1"
                )
                return

            # 更新统计
            self.request_count += 1

            await self.api.post_group_msg(group_id, text="🔍 正在搜索ASMR资源，请稍候...")

            try:
                # 计算页码和范围
                api_page = (page + 1) // 2  # 每两次 /asmr 请求对应 API 的一个页码
                start = 0 if page % 2 == 1 else 10  # 奇数页取前 10 个，偶数页取后 10 个
                end = start + 10

                data = await fetch_asmr_data(api_page)
                if data:
                    messages = format_asmr_data(data, start, end)
                    if messages:
                        await send_group_forward_msg_ws(group_id, messages)
                        self.success_count += 1
                        _log.info(f"ASMR搜索成功: 用户{user_id}, 群{group_id}, 页码{page}")
                    else:
                        await self.api.post_group_msg(
                            group_id,
                            text="❌ 该页面没有找到数据\n\n💡 尝试搜索其他页码"
                        )
                        self.error_count += 1
                else:
                    await self.api.post_group_msg(
                        group_id,
                        text="❌ 搜索失败，请稍后再试\n\n💡 可能是网络问题或API暂时不可用"
                    )
                    self.error_count += 1
            except Exception as e:
                _log.error(f"ASMR搜索时出错: {e}")
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 搜索时发生错误，请稍后再试"
                )
                self.error_count += 1

        elif match_list:
            # 频率控制检查
            can_request, remaining_time = self._check_frequency_limit(user_id)
            if not can_request:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
                )
                return

            audio_id = int(match_list.group(1))
            self.request_count += 1
            await self.handle_audio_request(group_id, audio_id)

        elif group_id in self.pending_search:
            try:
                user_input = int(raw_message)
                await self.handle_audio_play_request(group_id, user_id, user_input)
            except ValueError:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 请输入有效的音频编号\n\n💡 发送数字选择要播放的音频"
                )

    async def on_load(self):
        """插件加载时的初始化逻辑"""
        try:
            _log.info(f"AsmrSearch v{self.version} 插件已加载")
        except Exception as e:
            _log.error(f"AsmrSearch插件加载失败: {e}")

    async def on_unload(self):
        """插件卸载时清理资源"""
        try:
            _log.info("AsmrSearch插件正在卸载...")
            # 清理等待状态
            self.pending_search.clear()
            _log.info("AsmrSearch插件卸载完成")
        except Exception as e:
            _log.error(f"插件卸载时出错: {e}")
