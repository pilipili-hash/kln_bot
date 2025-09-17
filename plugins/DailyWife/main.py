import logging
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .wife_handler import get_daily_wife_message
from ncatbot.core.element import MessageChain, Text

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class DailyWife(BasePlugin):
    name = "DailyWife"  # 插件名称
    version = "2.0.0"  # 插件版本

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        # 统计信息
        self.draw_count = 0
        self.help_count = 0

    async def on_load(self):
        """插件加载时初始化"""
        _log.info(f"DailyWife v{self.version} 插件已加载")

    async def __onload__(self):
        """插件加载时初始化（新版本）"""
        await self.on_load()

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🌸 今日老婆插件帮助

🎯 功能说明：
每日随机抽取二次元老婆，每天每个用户的老婆是固定的

🔍 使用方法：
• 抽老婆 - 获取今日专属老婆
• /今日老婆 - 同上
• /老婆帮助 - 显示此帮助信息

💡 使用示例：
抽老婆
/今日老婆

✨ 特色功能：
• 🎲 每日固定：基于用户ID和日期生成，每天结果固定
• 🖼️ 丰富图库：包含大量二次元角色图片
• 🎊 随机祝福：每次抽取都有不同的祝福语
• 📊 角色信息：显示角色名称和精美图片

⚠️ 注意事项：
• 每天每个用户的老婆是固定的
• 图片资源来自本地图库
• 仅供娱乐，请理性对待

🔧 版本: v2.0.0
💡 提示：快来抽取你的专属老婆吧！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()

        # 帮助命令
        if raw_message in ["/老婆帮助", "/今日老婆帮助", "老婆帮助"]:
            await self.show_help(event.group_id)
            return

        # 抽老婆命令
        if raw_message in ["抽老婆", "/今日老婆", "/老婆", "今日老婆"]:
            try:
                message = await get_daily_wife_message(event)
                if message:
                    await self.api.post_group_msg(event.group_id, rtf=message)
                    self.draw_count += 1
                else:
                    await self.api.post_group_msg(event.group_id, text="❌ 获取老婆信息失败，请稍后再试")
            except Exception as e:
                _log.error(f"抽老婆时发生错误: {e}")
                await self.api.post_group_msg(event.group_id, text="❌ 抽老婆时发生错误，请稍后再试")
