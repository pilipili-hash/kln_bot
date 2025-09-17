import aiohttp
import asyncio
import logging
import time
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage

bot = CompatibleEnrollment
_log = logging.getLogger(__name__)

class TianGou(BasePlugin):
    name = "TianGou"  # 插件名称
    version = "2.0.0"  # 插件版本

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        # 统计数据
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_request_time = 0
        self.request_interval = 1.0  # 请求间隔（秒）

        # API配置
        self.api_urls = [
            "https://api.oick.cn/dog/api.php",
            "https://api.uomg.com/api/rand.qinghua",
            "https://api.btstu.cn/yan/api.php?charset=utf-8&encode=text"
        ]
        self.current_api_index = 0

    async def on_load(self):
        _log.info(f"{self.name} v{self.version} 插件已加载")
        _log.info("舔狗日记插件初始化完成")

    async def get_statistics(self) -> str:
        """获取插件统计信息"""
        success_rate = (self.success_count / max(self.request_count, 1)) * 100

        return f"""📊 舔狗日记统计
📝 总请求数: {self.request_count}
✅ 成功次数: {self.success_count}
❌ 失败次数: {self.error_count}
📈 成功率: {success_rate:.1f}%
⏱️ 请求间隔: {self.request_interval}秒
🔗 当前API: {self.api_urls[self.current_api_index]}"""

    async def rate_limit_check(self) -> bool:
        """检查请求频率限制"""
        current_time = time.time()
        if current_time - self.last_request_time < self.request_interval:
            return False
        self.last_request_time = current_time
        return True

    async def fetch_tiangou_content(self) -> tuple[str, bool]:
        """获取舔狗日记内容"""
        for _ in range(len(self.api_urls)):
            try:
                api_url = self.api_urls[self.current_api_index]
                _log.info(f"尝试从API获取舔狗日记: {api_url}")

                timeout = aiohttp.ClientTimeout(total=15)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(api_url) as response:
                        if response.status == 200:
                            content = await response.text()
                            if content and len(content.strip()) > 0:
                                _log.info(f"成功获取舔狗日记，长度: {len(content)}")
                                return content.strip(), True
                            else:
                                _log.warning(f"API返回空内容: {api_url}")
                        else:
                            _log.warning(f"API请求失败，状态码: {response.status}")

            except asyncio.TimeoutError:
                _log.error(f"API请求超时: {self.api_urls[self.current_api_index]}")
            except Exception as e:
                _log.error(f"API请求异常: {e}")

            # 切换到下一个API
            self.current_api_index = (self.current_api_index + 1) % len(self.api_urls)

        return "获取舔狗日记失败，所有API都无法访问", False

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        message = event.raw_message.strip()

        # 舔狗日记命令
        if message in ["/舔狗", "舔狗", "舔狗日记", "/舔狗日记"]:
            await self.handle_tiangou_request(event)

        # 统计命令
        elif message in ["舔狗统计", "/舔狗统计", "tiangou统计"]:
            await self.handle_statistics_request(event)

        # 帮助命令
        elif message in ["舔狗帮助", "/舔狗帮助", "tiangou帮助"]:
            await self.handle_help_request(event)

    async def handle_tiangou_request(self, event: GroupMessage):
        """处理舔狗日记请求"""
        try:
            # 频率限制检查
            if not await self.rate_limit_check():
                await self.api.post_group_msg(
                    event.group_id,
                    text=f"⏳ 请求过于频繁，请等待 {self.request_interval} 秒后再试"
                )
                return

            self.request_count += 1
            _log.info(f"用户 {event.user_id} 在群 {event.group_id} 请求舔狗日记")

            # 获取舔狗日记
            content, success = await self.fetch_tiangou_content()

            if success:
                self.success_count += 1
                await self.api.post_group_msg(
                    event.group_id,
                    text=f"🐕 舔狗日记：\n\n{content}"
                )
            else:
                self.error_count += 1
                await self.api.post_group_msg(
                    event.group_id,
                    text="❌ 获取舔狗日记失败，请稍后再试\n💡 可能是网络问题或API服务异常"
                )

        except Exception as e:
            self.error_count += 1
            _log.error(f"处理舔狗日记请求时出错: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="❌ 服务异常，请稍后再试"
            )

    async def handle_statistics_request(self, event: GroupMessage):
        """处理统计请求"""
        try:
            stats = await self.get_statistics()
            await self.api.post_group_msg(event.group_id, text=stats)
        except Exception as e:
            _log.error(f"获取统计信息时出错: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 获取统计信息失败")

    async def handle_help_request(self, event: GroupMessage):
        """处理帮助请求"""
        help_text = """🐕 舔狗日记插件帮助 v2.0.0

📝 基本命令：
• /舔狗 - 获取随机舔狗日记
• 舔狗日记 - 获取随机舔狗日记
• 舔狗统计 - 查看使用统计
• 舔狗帮助 - 显示此帮助

💡 使用示例：
/舔狗
舔狗日记
舔狗统计

🎯 功能特色：
• 多API源自动切换
• 智能频率控制
• 详细使用统计
• 完善错误处理

⚠️ 注意事项：
• 请求间隔1秒，避免频繁调用
• 内容来源于网络API
• 仅供娱乐，请理性对待"""

        try:
            await self.api.post_group_msg(event.group_id, text=help_text)
        except Exception as e:
            _log.error(f"发送帮助信息时出错: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 获取帮助信息失败")
