import random
import json
import os
import logging
import time
import datetime
from typing import List
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage

bot = CompatibleEnrollment
_log = logging.getLogger(__name__)

class KfcThursday(BasePlugin):
    name = "KfcThursday"  # 插件名称
    version = "2.0.0"  # 插件版本

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        # 文案数据
        self.kfc_quotes: List[str] = []

        # 统计数据
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.last_request_time = 0
        self.request_interval = 2.0  # 请求间隔（秒）

        # 特殊功能
        self.thursday_bonus_enabled = True  # 周四特殊模式
        self.custom_quotes: List[str] = []  # 自定义文案

    async def on_load(self):
        """插件加载时初始化"""
        try:
            _log.info(f"{self.name} v{self.version} 插件开始加载")

            # 加载KFC文案数据
            await self.load_kfc_quotes()

            # 加载自定义文案
            await self.load_custom_quotes()

            _log.info(f"KFC疯狂星期四插件加载完成，共加载 {len(self.kfc_quotes)} 条文案")

        except Exception as e:
            _log.error(f"插件加载失败: {e}")
            # 设置默认文案以防加载失败
            self.kfc_quotes = [
                "今天疯狂星期四，v我50吃KFC！",
                "KFC疯狂星期四，谁请我吃？",
                "疯狂星期四，不疯狂怎么行！"
            ]

    async def load_kfc_quotes(self) -> bool:
        """加载KFC文案数据"""
        try:
            quotes_path = os.path.join(os.getcwd(), "static", "kfc", "v50.json")

            if not os.path.exists(quotes_path):
                _log.warning(f"KFC文案文件不存在: {quotes_path}")
                return False

            with open(quotes_path, "r", encoding="utf-8") as file:
                self.kfc_quotes = json.load(file)

            if not self.kfc_quotes:
                _log.warning("KFC文案文件为空")
                return False

            _log.info(f"成功加载 {len(self.kfc_quotes)} 条KFC文案")
            return True

        except Exception as e:
            _log.error(f"加载KFC文案失败: {e}")
            return False

    async def load_custom_quotes(self) -> bool:
        """加载自定义文案"""
        try:
            custom_path = os.path.join(os.getcwd(), "static", "kfc", "custom.json")

            if os.path.exists(custom_path):
                with open(custom_path, "r", encoding="utf-8") as file:
                    self.custom_quotes = json.load(file)
                _log.info(f"成功加载 {len(self.custom_quotes)} 条自定义文案")
            else:
                _log.info("未找到自定义文案文件，跳过加载")

            return True

        except Exception as e:
            _log.error(f"加载自定义文案失败: {e}")
            return False

    def is_thursday(self) -> bool:
        """检查今天是否是星期四"""
        return datetime.datetime.now().weekday() == 3  # 0=Monday, 3=Thursday

    async def get_statistics(self) -> str:
        """获取插件统计信息"""
        success_rate = (self.success_count / max(self.request_count, 1)) * 100
        is_thursday_today = "是" if self.is_thursday() else "否"

        return f"""📊 KFC疯狂星期四统计
🍗 总请求数: {self.request_count}
✅ 成功次数: {self.success_count}
❌ 失败次数: {self.error_count}
📈 成功率: {success_rate:.1f}%
📅 今天是周四: {is_thursday_today}
📝 文案总数: {len(self.kfc_quotes)}
🎨 自定义文案: {len(self.custom_quotes)}
⏱️ 请求间隔: {self.request_interval}秒"""

    async def rate_limit_check(self) -> bool:
        """检查请求频率限制"""
        current_time = time.time()
        if current_time - self.last_request_time < self.request_interval:
            return False
        self.last_request_time = current_time
        return True

    async def get_random_quote(self) -> str:
        """获取随机KFC文案"""
        try:
            # 合并所有文案
            all_quotes = self.kfc_quotes + self.custom_quotes

            if not all_quotes:
                return "暂无KFC文案数据，请联系管理员检查配置"

            # 如果是周四且启用了特殊模式，增加周四相关文案的权重
            if self.is_thursday() and self.thursday_bonus_enabled:
                thursday_quotes = [q for q in all_quotes if any(keyword in q for keyword in ["星期四", "周四", "Thursday", "疯狂"])]
                if thursday_quotes:
                    # 70%概率选择周四相关文案
                    if random.random() < 0.7:
                        return random.choice(thursday_quotes)

            return random.choice(all_quotes)

        except Exception as e:
            _log.error(f"获取随机文案失败: {e}")
            return "获取KFC文案失败，请稍后再试"

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        message = event.raw_message.strip()

        # KFC文案命令
        if message in ["/kfc", "kfc", "疯狂星期四", "/疯狂星期四", "肯德基"]:
            await self.handle_kfc_request(event)

        # 统计命令
        elif message in ["kfc统计", "/kfc统计", "疯狂星期四统计"]:
            await self.handle_statistics_request(event)

        # 帮助命令
        elif message in ["kfc帮助", "/kfc帮助", "疯狂星期四帮助"]:
            await self.handle_help_request(event)

    async def handle_kfc_request(self, event: GroupMessage):
        """处理KFC文案请求"""
        try:
            # 频率限制检查
            if not await self.rate_limit_check():
                await self.api.post_group_msg(
                    event.group_id,
                    text=f"⏳ 请求过于频繁，请等待 {self.request_interval} 秒后再试"
                )
                return

            self.request_count += 1
            _log.info(f"用户 {event.user_id} 在群 {event.group_id} 请求KFC文案")

            # 获取随机文案
            quote = await self.get_random_quote()

            # 添加特殊标识
            if self.is_thursday():
                quote = f"🍗 疯狂星期四特供 🍗\n\n{quote}"
            else:
                quote = f"🍗 KFC文案 🍗\n\n{quote}"

            self.success_count += 1
            await self.api.post_group_msg(event.group_id, text=quote)

        except Exception as e:
            self.error_count += 1
            _log.error(f"处理KFC文案请求时出错: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="❌ 获取KFC文案失败，请稍后再试"
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
        help_text = """🍗 KFC疯狂星期四插件帮助 v2.0.0

📝 基本命令：
• /kfc - 获取随机KFC文案
• 疯狂星期四 - 获取随机KFC文案
• 肯德基 - 获取随机KFC文案
• kfc统计 - 查看使用统计
• kfc帮助 - 显示此帮助

💡 使用示例：
/kfc
疯狂星期四
kfc统计

🎯 特色功能：
• 周四特殊模式：周四时优先显示相关文案
• 丰富文案库：400+条精选文案
• 自定义文案：支持扩展自定义内容
• 智能频率控制：防止刷屏
• 详细统计信息：使用数据一目了然

⚠️ 注意事项：
• 请求间隔2秒，避免频繁调用
• 文案内容仅供娱乐，请理性对待
• 周四时会有特殊标识和优先文案"""

        try:
            await self.api.post_group_msg(event.group_id, text=help_text)
        except Exception as e:
            _log.error(f"发送帮助信息时出错: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 获取帮助信息失败")
