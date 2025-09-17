import logging
import os
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .niuniu_utils import (
    init_database,
    register_player,
    apply_glue,
    jj_battle,
    use_item,
    query_player,
    get_leaderboard,
    reset_player
)

# 设置日志
_log = logging.getLogger("PassionateCowPlugin.main")

class PassionateCowPlugin(BasePlugin):
    name = "PassionateCowPlugin"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        self.db_path = os.path.join("data", "passionate_cow.db")

    async def __onload__(self):
        """插件加载时初始化"""
        try:
            # 确保数据目录存在
            os.makedirs("data", exist_ok=True)

            # 初始化数据库
            await init_database(self.db_path)
            _log.info(f"PassionateCowPlugin v{self.version} 插件已加载")
            _log.info(f"数据库路径: {self.db_path}")

        except Exception as e:
            _log.error(f"插件加载失败: {e}")
            raise

    @CompatibleEnrollment.group_event()
    async def on_group_message(self, msg: GroupMessage):
        """处理群聊消息"""
        try:
            message = msg.raw_message.strip()

            # 注册相关命令
            if message == "注册牛子":
                await register_player(self.db_path, msg, self)
            elif message == "重置牛子":
                await reset_player(self.db_path, msg, self)

            # 游戏操作命令
            elif message == "打胶":
                await apply_glue(self.db_path, msg, self)
            elif message.startswith("jj") and len(message) > 2:
                await jj_battle(self.db_path, msg, self)

            # 道具相关命令
            elif message.startswith("使用道具"):
                await use_item(self.db_path, msg, self)

            # 查询相关命令
            elif message == "我的牛子":
                await query_player(self.db_path, msg, self)
            elif message == "牛子排行" or message == "牛子排行榜":
                await get_leaderboard(self.db_path, msg, self)

            # 帮助命令
            elif message == "牛子帮助" or message == "激情牛子帮助":
                await self._show_help(msg)

        except Exception as e:
            _log.error(f"处理群消息失败: {e}")
            await self.api.post_group_msg(
                group_id=msg.group_id,
                text="处理命令时发生错误，请稍后再试。"
            )

    async def _show_help(self, msg: GroupMessage):
        """显示帮助信息"""
        help_text = """🐂 激情牛子游戏帮助 v2.0.0

📝 基础命令：
• 注册牛子 - 注册并开始游戏
• 重置牛子 - 重置你的牛子数据
• 我的牛子 - 查看个人信息
• 牛子排行 - 查看排行榜

🎮 游戏操作：
• 打胶 - 进行打胶操作（3小时冷却）
• jj @某人 - 与其他玩家进行对战（3小时冷却）

🎒 道具系统：
• 使用道具 [道具名] - 使用背包中的道具

📊 角色系统：
根据牛子长度自动分配角色，每个角色都有独特技能！

⚠️ 注意事项：
• 打胶和对战都有3小时冷却时间
• 对战会触发双方的角色技能
• 合理使用道具可以改变战局

发送 "牛子帮助" 查看此帮助信息"""

        await self.api.post_group_msg(group_id=msg.group_id, text=help_text)