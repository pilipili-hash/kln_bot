import aiohttp
import logging
import re
import os
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Record, Image
from utils.config_manager import get_config
from .characters import CHARACTERS, generate_character_list_image

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class VitsTTS(BasePlugin):
    name = "VitsTTS"
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
        self.request_interval = 3.0  # 3秒间隔

    async def on_load(self):
        """插件加载时初始化"""
        try:
            self.vits_url = get_config("VITS_url")
            self.proxy = get_config("proxy")

            if not self.vits_url:
                _log.error("VITS_url 配置未找到，请检查配置文件")
            else:
                _log.info(f"VitsTTS v{self.version} 插件已加载，VITS服务地址: {self.vits_url}")
                _log.info(f"支持 {len(CHARACTERS)} 个语音角色")
        except Exception as e:
            _log.error(f"VitsTTS插件加载失败: {e}")

    def _check_frequency_limit(self, user_id: int) -> tuple[bool, float]:
        """检查用户请求频率限制"""
        import time
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
        help_text = """🎤 VitsTTS语音合成插件帮助

🎯 功能说明：
使用AI语音合成技术，让各种角色为你朗读文字内容

🔍 使用方法：
• /语音列表 - 查看所有可用的语音角色
• /序号说语言 内容 - 生成语音
• /语音帮助 - 显示此帮助信息
• /语音统计 - 查看使用统计

💡 使用示例：
/1说中文 你好世界
/25说日语 こんにちは
/100说中文 今天天气真不错

📊 支持语言：
• 中文 - 支持中文语音合成
• 日语 - 支持日语语音合成

🎭 角色特色：
• 🏇 赛马娘角色：特别周、无声铃鹿、东海帝皇等
• 🎮 原神角色：神里绫华、琴、空、荧等
• 🌟 崩坏3角色：丽塔、伊甸、布洛妮娅等
• 📺 其他角色：各种动漫和游戏角色

⚠️ 注意事项：
• 请求间隔为3秒，避免频繁调用
• 角色编号从1开始，请查看语音列表确认
• 内容长度建议控制在100字以内
• 需要配置VITS服务地址才能使用

🔧 版本: v2.0.0
💡 提示：发送"/语音列表"查看所有可用角色！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0

        stats_text = f"""📊 VitsTTS语音合成插件统计

🎤 支持角色: {len(CHARACTERS)} 个
📈 生成成功: {self.success_count} 次
📋 生成请求: {self.request_count} 次
❌ 生成失败: {self.error_count} 次
❓ 查看帮助: {self.help_count} 次
📊 成功率: {success_rate:.1f}%

⏱️ 请求间隔: {self.request_interval} 秒

💡 使用提示：
• 发送"/语音列表"查看角色列表
• 发送"/语音帮助"查看详细帮助
• 支持中文和日语两种语言"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def send_error_message(self, group_id, message):
        """发送错误消息的辅助方法"""
        await self.api.post_group_msg(group_id, text=f"❌ {message}")
        self.error_count += 1

    async def generate_audio_url(self, content, language, char_name):
        """生成音频 URL 的辅助方法"""
        try:
            payload = {
                "fn_index": 0,
                "session_hash": "",
                "data": [content, language, char_name, 0.6, 0.668, 1.2]
            }

            timeout = aiohttp.ClientTimeout(total=30)  # 30秒超时
            async with aiohttp.ClientSession(proxy=self.proxy, timeout=timeout) as session:
                async with session.post(f"{self.vits_url.rstrip('/')}/api/generate", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result and "data" in result and len(result["data"]) > 1 and isinstance(result["data"][1], dict):
                            audio_name = result["data"][1].get("name")
                            if isinstance(audio_name, str):
                                return f"{self.vits_url.rstrip('/')}/file={audio_name}"
                    else:
                        _log.error(f"VITS服务返回错误状态码: {response.status}")
                        return None
        except Exception as e:
            _log.error(f"生成音频URL时出错: {e}")
            return None

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        raw_message = event.raw_message.strip()
        user_id = event.user_id
        group_id = event.group_id

        # 帮助命令
        if raw_message in ["/语音帮助", "/vits帮助", "/tts帮助", "语音帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/语音统计", "/vits统计", "/tts统计", "语音统计"]:
            await self.show_statistics(group_id)
            return

        # 语音列表命令
        if raw_message == "/语音列表":
            try:
                # 图片路径设置为与 main.py 相同的文件夹
                module_path = os.path.dirname(__file__)
                image_path = os.path.join(module_path, "character_list.png")

                # 检查图片是否存在，不存在则生成
                if not os.path.exists(image_path):
                    image = generate_character_list_image()
                    image.save(image_path)

                await self.api.post_group_msg(
                    event.group_id,
                    rtf=MessageChain([Image(path=image_path)])
                )
                _log.info(f"用户 {user_id} 在群 {group_id} 查看了语音列表")
            except Exception as e:
                _log.error(f"生成人物列表图片失败: {e}")
                await self.send_error_message(event.group_id, f"生成人物列表图片失败: {str(e)}")
            return

        # 语音生成命令
        try:
            # 使用正则表达式解析输入
            match = re.match(r"^/(\d+)说(中文|日语)\s+(.+)$", raw_message)
            if not match:
                return

            # 频率控制检查
            can_request, remaining_time = self._check_frequency_limit(user_id)
            if not can_request:
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
                )
                return

            # 提取编号、语言和内容
            char_index = int(match.group(1)) - 1
            language = match.group(2)
            content = match.group(3).strip()

            # 验证输入
            if not content:
                await self.send_error_message(group_id, "请输入要合成的文字内容")
                return

            if len(content) > 200:
                await self.send_error_message(group_id, "文字内容过长，请控制在200字以内")
                return

            char_name = CHARACTERS[char_index] if 0 <= char_index < len(CHARACTERS) else None

            if not char_name:
                await self.send_error_message(group_id, f"人物编号无效，请输入1-{len(CHARACTERS)}之间的数字")
                return

            if not self.vits_url:
                await self.send_error_message(group_id, "VITS服务未配置，请联系管理员")
                return

            # 更新统计
            self.request_count += 1

            # 发送处理提示
            await self.api.post_group_msg(group_id, text=f"🎤 正在生成语音，角色：{char_name}，请稍候...")

            # 生成音频 URL
            audio_url = await self.generate_audio_url(content, language, char_name)
            if audio_url:
                await self.api.post_group_msg(group_id, rtf=MessageChain([Record(audio_url)]))
                self.success_count += 1
                _log.info(f"成功生成语音: 用户{user_id}, 群{group_id}, 角色{char_name}, 语言{language}")
            else:
                await self.send_error_message(group_id, "语音生成失败，请检查VITS服务状态或稍后重试")

        except Exception as e:
            _log.error(f"语音生成时出错: {e}")
            await self.send_error_message(group_id, f"语音生成时发生错误: {str(e)}")

    async def on_unload(self):
        """插件卸载时清理资源"""
        try:
            _log.info("VitsTTS插件正在卸载...")
            _log.info("VitsTTS插件卸载完成")
        except Exception as e:
            _log.error(f"插件卸载时出错: {e}")
