from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage, PrivateMessage
from PluginManager.plugin_manager import feature_required
from ncatbot.core.element import (
    MessageChain,
    Text,
    At
)
from .database import AnimeDB
from .scheduler import AnimeScheduler
import asyncio
from utils.onebot_v11_handler import OneBotV11MessageHandler

bot = CompatibleEnrollment

class TodayAnime(BasePlugin):
    name = "TodayAnime"
    version = "2.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        
        # 初始化数据库
        self.db = AnimeDB()
        await self.db.init_db()
        
        # 初始化调度器
        self.scheduler = AnimeScheduler(self.api)
        
        # 初始化OneBotV11消息处理器
        self.message_handler = OneBotV11MessageHandler()
        
        # 注册定时任务，每天9点推送番剧
        self.add_scheduled_task(
            job_func=self.daily_push,
            name="anime_daily_push",
            interval="21:30",  # 每天9点执行
            # args=(self.api.get,)  # 传入机器人ID作为参数
        )
    async def daily_push(self):
        """每日番剧推送定时任务"""
        # 如果没有提供bot_id，使用事件的self_id或尝试通过其他方式获取
            # 从当前正在处理的事件中获取bot_id，如果有的话
        bot_id = 123456789  # 替换为你的机器人ID
        
        await self.scheduler.send_daily_anime(bot_id)
    
    @bot.group_event()
    @feature_required("今日番剧", "开启番剧推送")
    async def handle_subscribe(self, event: GroupMessage):
        """处理订阅命令"""
        if event.raw_message == "开启番剧推送":
            # 添加订阅
            success = await self.db.add_subscription(event.group_id)
            if success:
                await self.api.post_group_msg(
                    event.group_id,
                    text="✅ 已开启今日番剧每日推送，将在每天早上9点推送"
                )
            else:
                await self.api.post_group_msg(
                    event.group_id,
                    text="❌ 开启推送失败，请稍后再试"
                )
    
    @bot.group_event()
    @feature_required("今日番剧", "关闭番剧推送")
    async def handle_unsubscribe(self, event: GroupMessage):
        """处理取消订阅命令"""
        if event.raw_message == "关闭番剧推送":
            # 移除订阅
            success = await self.db.remove_subscription(event.group_id)
            if success:
                await self.api.post_group_msg(
                    event.group_id,
                    text="✅ 已关闭今日番剧每日推送"
                )
            else:
                await self.api.post_group_msg(
                    event.group_id,
                    text="❌ 关闭推送失败，请稍后再试"
                )
    
    @bot.group_event()
    @feature_required("今日番剧", "今日番剧")
    async def handle_group_message(self, event: GroupMessage):
        """响应手动查询命令"""
        if event.raw_message == "今日番剧":
            # 获取番剧数据
            data = await self.scheduler.fetch_anime_data()
            if data:
                formatted_data = self.scheduler.format_anime_data(data)
                if formatted_data:
                    messages = await self.scheduler.create_forward_messages(formatted_data, str(event.self_id))
                    # 使用OneBotV11合并转发消息
                    try:
                        await self.message_handler.send_forward_message(
                            group_id=event.group_id,
                            messages=messages
                        )
                        # 不管返回值如何，都不发送额外的错误消息
                        # 因为合并转发可能有延迟或特殊的响应格式
                    except Exception as e:
                        # 只有在真正异常时才发送错误消息
                        await self.api.post_group_msg(event.group_id, text=f"发送今日番剧信息失败: {e}")
                else:
                    await self.api.post_group_msg(event.group_id, text="今天没有番剧更新")
            else:
                await self.api.post_group_msg(event.group_id, text="获取今日番剧信息失败")

    @bot.group_event()
    @feature_required("今日番剧", "番剧推送状态")
    async def handle_status(self, event: GroupMessage):
        """查询当前群组的订阅状态"""
        if event.raw_message == "番剧推送状态":
            is_subscribed = await self.db.is_subscribed(event.group_id)
            if is_subscribed:
                await self.api.post_group_msg(
                    event.group_id,
                    text="当前状态：已开启番剧推送"
                )
            else:
                await self.api.post_group_msg(
                    event.group_id,
                    text="当前状态：未开启番剧推送"
                )
    
    @bot.private_event()
    async def handle_private_message(self, event: PrivateMessage):
        """处理私聊消息"""
        if event.raw_message == "今日番剧":
            data = await self.scheduler.fetch_anime_data()
            if data:
                formatted_data = self.scheduler.format_anime_data(data)
                if formatted_data:
                    # 私聊不支持合并转发，改为发送文本摘要
                    summary_text = "今日番剧更新:\n"
                    for i, anime in enumerate(formatted_data[:5], 1):  # 只显示前5个
                        summary_text += f"{i}. {anime['title']} - {anime['air_date']}\n"
                    if len(formatted_data) > 5:
                        summary_text += f"... 还有{len(formatted_data) - 5}个番剧更新"
                    await self.api.post_private_msg(event.user_id, text=summary_text)
                else:
                    await self.api.post_private_msg(event.user_id, text="今天没有番剧更新")
            else:
                await self.api.post_private_msg(event.user_id, text="获取今日番剧信息失败")