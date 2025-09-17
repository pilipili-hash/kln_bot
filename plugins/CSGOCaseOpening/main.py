import logging
import asyncio
from typing import Optional
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from .utils import Utils
from .database import CSGODatabase
from utils.config_manager import get_config

bot = CompatibleEnrollment
_log = logging.getLogger(__name__)

class CSGOCaseOpening(BasePlugin):
    name = "CSGOCaseOpening"  # 插件名称
    version = "2.0.0"  # 插件版本

    async def on_load(self):
        # 初始化工具类和数据库
        self.utils = Utils()
        self.database = CSGODatabase()
        self.request_count = 0
        self.error_count = 0
        self.total_opened_cases = 0

        _log.info(f"{self.name} v{self.version} 插件已加载")
        _log.info("CSGO开箱模拟器已启用")

    async def get_user_statistics(self, user_id: str) -> str:
        """获取用户个人开箱统计"""
        try:
            stats = self.database.get_user_statistics(user_id)

            if stats['total_openings'] == 0:
                return "📊 你还没有开过箱子哦！\n💡 发送 /武器箱 或 /皮肤箱 查看可开启的箱子"

            return f"""📊 你的开箱统计

🎯 开箱次数: {stats['total_openings']}次
📦 开出箱子: {stats['total_cases']}个
🏆 稀有物品: {stats['rare_items']}个 ({stats['rare_rate']:.1f}%)
💎 传说物品: {stats['legendary_items']}个 ({stats['legendary_rate']:.1f}%)

🎨 最佳物品: {stats['best_item'] or '暂无'}
⭐ 最高稀有度: {stats['best_rarity'] or '暂无'}
⏰ 上次开箱: {stats['last_opening'][:16] if stats['last_opening'] else '暂无'}

💡 稀有物品包括：受限、保密、隐秘、违禁、非凡
💎 传说物品包括：隐秘、违禁、非凡"""

        except Exception as e:
            _log.error(f"获取用户统计失败: {e}")
            return "❌ 获取统计信息失败"

    async def get_global_statistics(self) -> str:
        """获取全局开箱统计"""
        try:
            stats = self.database.get_global_statistics()

            return f"""📊 全服开箱统计

👥 参与用户: {stats['total_users']}人
🎯 总开箱次数: {stats['total_openings']}次
📦 总开出箱子: {stats['total_cases']}个
🏆 稀有物品: {stats['total_rare_items']}个 ({stats['global_rare_rate']:.1f}%)
💎 传说物品: {stats['total_legendary_items']}个 ({stats['global_legendary_rate']:.1f}%)

📈 全服出金率: {stats['global_rare_rate']:.1f}%
🌟 传说出货率: {stats['global_legendary_rate']:.1f}%

💡 数据统计自插件启用以来的所有开箱记录"""

        except Exception as e:
            _log.error(f"获取全局统计失败: {e}")
            return "❌ 获取统计信息失败"

    async def get_ranking(self) -> str:
        """获取开箱排行榜"""
        try:
            top_users = self.database.get_top_users(10)

            if not top_users:
                return "📊 暂无排行榜数据"

            ranking_text = "🏆 开箱排行榜 TOP10\n\n"

            for i, (user_id, total_cases, rare_items, legendary_items, rare_rate) in enumerate(top_users, 1):
                # 隐藏用户ID的部分字符
                masked_id = user_id[:3] + "*" * (len(user_id) - 6) + user_id[-3:] if len(user_id) > 6 else user_id

                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

                ranking_text += f"{medal} {masked_id}\n"
                ranking_text += f"   📦 开箱: {total_cases}个 | 🏆 稀有: {rare_items}个 ({rare_rate}%)\n\n"

            return ranking_text

        except Exception as e:
            _log.error(f"获取排行榜失败: {e}")
            return "❌ 获取排行榜失败"

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()

        try:
            if raw_message == "/武器箱":
                _log.info(f"用户 {event.user_id} 在群 {event.group_id} 查看武器箱列表")
                await self.utils.send_case_list(event, case_type="weapon")

            elif raw_message == "/皮肤箱":
                _log.info(f"用户 {event.user_id} 在群 {event.group_id} 查看皮肤箱列表")
                await self.utils.send_case_list(event, case_type="souvenir")

            elif raw_message == "/开箱统计":
                try:
                    stats = await self.get_user_statistics(str(event.user_id))
                    await self.api.post_group_msg(event.group_id, text=stats)
                except Exception as e:
                    _log.error(f"获取用户统计信息时出错: {e}")
                    await self.api.post_group_msg(event.group_id, text="❌ 获取统计信息失败")

            elif raw_message == "/全服统计":
                try:
                    stats = await self.get_global_statistics()
                    await self.api.post_group_msg(event.group_id, text=stats)
                except Exception as e:
                    _log.error(f"获取全服统计信息时出错: {e}")
                    await self.api.post_group_msg(event.group_id, text="❌ 获取统计信息失败")

            elif raw_message == "/开箱排行":
                try:
                    ranking = await self.get_ranking()
                    await self.api.post_group_msg(event.group_id, text=ranking)
                except Exception as e:
                    _log.error(f"获取排行榜时出错: {e}")
                    await self.api.post_group_msg(event.group_id, text="❌ 获取排行榜失败")

            elif raw_message == "/开箱帮助":
                help_text = """🎮 CSGO开箱模拟器帮助

📝 基本命令：
• /武器箱 - 查看武器箱列表
• /皮肤箱 - 查看皮肤箱列表
• /开箱 序号 [数量] - 开启指定箱子
• /开箱统计 - 查看个人开箱统计
• /全服统计 - 查看全服开箱统计
• /开箱排行 - 查看开箱排行榜
• /开箱帮助 - 显示此帮助信息

💡 使用示例：
/武器箱
/开箱 1
/开箱 5 10
/开箱统计
/全服统计
/开箱排行

📊 统计说明：
• 稀有物品：受限、保密、隐秘、违禁、非凡
• 传说物品：隐秘、违禁、非凡
• 出金率：稀有物品占总开箱的比例

⚠️ 注意事项：
• 序号请参考箱子列表
• 开箱数量范围：1-50个
• 默认开箱数量：20个
• 仅为娱乐模拟，非真实开箱"""

                await self.api.post_group_msg(event.group_id, text=help_text)

            elif raw_message.startswith("/开箱"):
                try:
                    parts = raw_message.split()
                    if len(parts) < 2:
                        await self.api.post_group_msg(event.group_id, text="❌ 格式错误，请使用：/开箱 序号 [数量]\n💡 示例：/开箱 1 或 /开箱 1 10")
                        return

                    if not parts[1].isdigit():
                        await self.api.post_group_msg(event.group_id, text="❌ 序号必须是数字")
                        return

                    index = int(parts[1])
                    amount = 20  # 默认开20个

                    # 检查是否指定了数量
                    if len(parts) >= 3:
                        if not parts[2].isdigit():
                            await self.api.post_group_msg(event.group_id, text="❌ 数量必须是数字")
                            return
                        amount = int(parts[2])
                        if amount < 1 or amount > 50:
                            await self.api.post_group_msg(event.group_id, text="❌ 开箱数量必须在1-50之间")
                            return

                    _log.info(f"用户 {event.user_id} 在群 {event.group_id} 开箱: 序号{index}, 数量{amount}")
                    await self.api.post_group_msg(event.group_id, text=f"🎲 正在为你开启 {amount} 个箱子，请稍候...")

                    self.request_count += 1
                    self.total_opened_cases += amount

                    # 开箱并记录结果
                    case_name, case_type, results = await self.utils.handle_open_case(event, index, amount)

                    # 记录到数据库
                    if case_name and results:
                        self.database.record_opening(
                            str(event.user_id),
                            str(event.group_id),
                            case_name,
                            case_type,
                            amount,
                            results
                        )

                    _log.info(f"用户 {event.user_id} 开箱成功: {case_name}, 数量: {amount}")

                except Exception as e:
                    self.error_count += 1
                    _log.error(f"开箱失败: {e}")
                    await self.api.post_group_msg(event.group_id, text=f"❌ 开箱失败: {str(e)}")

        except Exception as e:
            _log.error(f"处理消息时出错: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 系统错误，请稍后再试")
