import logging
import random
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from PluginManager.plugin_manager import feature_required
from .data import DATA

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class DiseasePlugin(BasePlugin):
    name = "DiseasePlugin"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0

        # 频率控制
        self.last_request_time = {}
        self.request_interval = 5.0  # 5秒间隔

    async def on_load(self):
        _log.info(f"DiseasePlugin v{self.version} 插件已加载")
        _log.info(f"发病语录数量: {len(DATA)}")

    @bot.group_event()
    @feature_required("发病")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理发病相关命令
        """
        raw_message = event.raw_message.strip()
        user_id = event.user_id
        group_id = event.group_id

        # 帮助命令
        if raw_message in ["/发病帮助", "/发病help", "发病帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/发病统计", "发病统计"]:
            await self.show_statistics(group_id)
            return

        if not raw_message.startswith("/发病"):
            return

        # 频率控制
        import asyncio
        current_time = asyncio.get_event_loop().time()
        if user_id in self.last_request_time:
            time_diff = current_time - self.last_request_time[user_id]
            if time_diff < self.request_interval:
                remaining = self.request_interval - time_diff
                await self.api.post_group_msg(group_id=group_id, text=f"⏳ 发病过于频繁，请等待 {remaining:.1f} 秒后再试")
                return

        self.last_request_time[user_id] = current_time

        try:
            self.request_count += 1

            # 检查是否有@用户
            at_members = [segment for segment in event.message if segment["type"] == "at"]

            if not at_members:
                # 没有@用户，检查是否提供了名字
                nickname = raw_message[3:].strip()  # 获取 /发病 后面的文字
                if not nickname:
                    await self.api.post_group_msg(group_id, text="❌ 请@一个人或提供一个名字来发病！\n💡 使用方法：/发病 @用户 或 /发病 名字")
                    self.error_count += 1
                    return

                # 使用提供的名字发病
                msg = random.choice(DATA).format(target_name=nickname)
                await self.api.post_group_msg(group_id, text=msg)
                self.success_count += 1
                _log.info(f"用户 {user_id} 在群 {group_id} 对 '{nickname}' 发病")
                return

            # 对@的用户发病
            for at_member in at_members:
                target_user_id = at_member["data"]["qq"]

                try:
                    member_info = await self.api.get_group_member_info(group_id, target_user_id, no_cache=False)
                    nickname = member_info.get('data', {}).get('card', '') or member_info.get('data', {}).get('nickname', f'用户{target_user_id}')

                    msg = random.choice(DATA).format(target_name=nickname)
                    await self.api.post_group_msg(group_id, text=msg)

                    self.success_count += 1
                    _log.info(f"用户 {user_id} 在群 {group_id} 对用户 {target_user_id}({nickname}) 发病")

                except Exception as e:
                    _log.error(f"获取用户 {target_user_id} 信息失败: {e}")
                    # 使用默认名字
                    msg = random.choice(DATA).format(target_name=f"用户{target_user_id}")
                    await self.api.post_group_msg(group_id, text=msg)
                    self.success_count += 1

        except Exception as e:
            _log.error(f"处理发病请求时出错: {e}")
            await self.api.post_group_msg(group_id, text="❌ 发病失败，请稍后再试")
            self.error_count += 1

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """💔 发病语录插件帮助

📝 基本命令：
• /发病 @用户 - 对指定用户发病
• /发病 名字 - 对指定名字发病
• /发病帮助 - 显示此帮助信息
• /发病统计 - 查看使用统计

💡 使用示例：
/发病 @小明    # 对小明发病
/发病 张三     # 对张三发病
/发病帮助      # 查看帮助
/发病统计      # 查看统计

⚠️ 注意事项：
• 每次发病间隔5秒
• 语录内容来自网络，仅供娱乐
• 请理性使用，避免过度刷屏
• 语录数量：{len(DATA)}条"""

        await self.api.post_group_msg(group_id, text=help_text)

    async def show_statistics(self, group_id: int):
        """显示统计信息"""
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0

        stats_text = f"""📊 发病语录插件统计

💔 总请求数: {self.request_count}
✅ 成功次数: {self.success_count}
❌ 失败次数: {self.error_count}
📈 成功率: {success_rate:.1f}%
📚 语录总数: {len(DATA)}条
⏱️ 请求间隔: {self.request_interval}秒

💡 提示：发送"/发病帮助"查看详细帮助"""

        await self.api.post_group_msg(group_id, text=stats_text)
