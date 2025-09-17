import aiohttp
import asyncio
import re
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image

# 尝试导入插件管理器
try:
    from PluginManager.plugin_manager import feature_required
except ImportError:
    def feature_required(feature_name=None, commands=None, require_admin=False):
        """简单的装饰器替代版本"""
        def decorator(func):
            async def wrapper(self, *args, **kwargs):
                return await func(self, *args, **kwargs)
            return wrapper
        return decorator

bot = CompatibleEnrollment
_log = logging.getLogger("BiliVideoInfo.main")

class BiliVideoInfo(BasePlugin):
    name = "BiliVideoInfo"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # API配置
        self.BILIBILI_API_URL = "http://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        self.BILIBILI_AV_API_URL = "http://api.bilibili.com/x/web-interface/view?aid={aid}"
        self.HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
            "Referer": "https://www.bilibili.com/"
        }

        # 缓存系统
        self.video_cache = {}
        self.cache_expire_time = 3600  # 1小时缓存

        # 请求限制
        self.last_request_time = {}
        self.request_interval = 1  # 1秒间隔

    async def on_load(self):
        """插件加载时初始化"""
        try:
            print(f"BiliVideoInfo 插件已加载")
            print(f"插件版本: {self.version}")
            _log.info(f"BiliVideoInfo v{self.version} 插件已加载")
            _log.info("B站视频信息获取功能已启用")
        except Exception as e:
            _log.error(f"插件加载失败: {e}")

    async def __onload__(self):
        """插件加载时初始化（新版本）"""
        await self.on_load()

    def _is_cache_valid(self, cache_time: float) -> bool:
        """检查缓存是否有效"""
        return time.time() - cache_time < self.cache_expire_time

    def _should_rate_limit(self, group_id: int) -> bool:
        """检查是否需要限流"""
        current_time = time.time()
        last_time = self.last_request_time.get(group_id, 0)
        return current_time - last_time < self.request_interval

    async def fetch_video_info(self, video_id: str, is_bv: bool = True) -> Optional[Dict]:
        """
        调用 B站 API 获取视频信息
        支持BV号和AV号
        """
        # 检查缓存
        cache_key = video_id
        if cache_key in self.video_cache:
            cache_data, cache_time = self.video_cache[cache_key]
            if self._is_cache_valid(cache_time):
                _log.info(f"使用缓存数据: {video_id}")
                return cache_data

        try:
            # 选择API URL
            if is_bv:
                url = self.BILIBILI_API_URL.format(bvid=video_id)
            else:
                url = self.BILIBILI_AV_API_URL.format(aid=video_id)

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url, headers=self.HEADERS) as response:
                    if response.status == 200:
                        data = await response.json()

                        # 缓存数据
                        self.video_cache[cache_key] = (data, time.time())

                        _log.info(f"成功获取视频信息: {video_id}")
                        return data
                    else:
                        _log.warning(f"API请求失败，状态码: {response.status}")
                        try:
                            error_message = await response.text()
                            _log.warning(f"错误信息: {error_message}")
                        except Exception as e:
                            _log.warning(f"无法读取错误信息: {e}")
                        return None

        except asyncio.TimeoutError:
            _log.error(f"请求超时: {video_id}")
            return None
        except aiohttp.ClientError as e:
            _log.error(f"网络请求失败: {e}")
            return None
        except Exception as e:
            _log.error(f"获取视频信息时发生未知错误: {e}")
            return None

    def format_number(self, num: int) -> str:
        """格式化数字显示"""
        if num >= 100000000:  # 1亿
            return f"{num / 100000000:.1f}亿"
        elif num >= 10000:  # 1万
            return f"{num / 10000:.1f}万"
        else:
            return str(num)

    def format_duration(self, duration: int) -> str:
        """格式化视频时长"""
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def truncate_text(self, text: str, max_length: int = 100) -> str:
        """截断过长的文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def format_video_info(self, data: Dict) -> MessageChain:
        """
        提取视频信息并格式化为 MessageChain
        """
        if not data or data.get("code") != 0:
            error_msg = "获取视频信息失败"
            if data and data.get("message"):
                error_msg += f": {data['message']}"
            return MessageChain([Text(error_msg)])

        try:
            video_data = data["data"]

            # 基本信息
            title = video_data.get("title", "未知标题")
            pic_url = video_data.get("pic", "")
            bvid = video_data.get("bvid", "")
            aid = video_data.get("aid", "")

            # UP主信息
            owner = video_data.get("owner", {})
            owner_name = owner.get("name", "未知UP主")
            owner_mid = owner.get("mid", "")

            # 统计信息
            stat = video_data.get("stat", {})
            view_count = self.format_number(stat.get("view", 0))
            danmaku_count = self.format_number(stat.get("danmaku", 0))
            like_count = self.format_number(stat.get("like", 0))
            coin_count = self.format_number(stat.get("coin", 0))
            favorite_count = self.format_number(stat.get("favorite", 0))
            share_count = self.format_number(stat.get("share", 0))

            # 视频信息
            duration = video_data.get("duration", 0)
            duration_str = self.format_duration(duration)
            pubdate = video_data.get("pubdate", 0)
            pub_time = datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d %H:%M")

            # 简介
            desc = video_data.get("desc", "暂无简介")
            desc = self.truncate_text(desc, 150)

            # 分区信息
            tname = video_data.get("tname", "未知分区")

            # 构建消息
            message_text = f"📺 B站视频信息\n\n"
            message_text += f"🎬 标题: {title}\n"
            message_text += f"👤 UP主: {owner_name}\n"
            message_text += f"🏷️ 分区: {tname}\n"
            message_text += f"⏱️ 时长: {duration_str}\n"
            message_text += f"📅 发布: {pub_time}\n\n"
            message_text += f"📊 数据统计:\n"
            message_text += f"▶️ 播放: {view_count}\n"
            message_text += f"💬 弹幕: {danmaku_count}\n"
            message_text += f"👍 点赞: {like_count}\n"
            message_text += f"🪙 投币: {coin_count}\n"
            message_text += f"⭐ 收藏: {favorite_count}\n"
            message_text += f"📤 分享: {share_count}\n\n"
            message_text += f"📝 简介: {desc}\n\n"
            message_text += f"🔗 链接: https://www.bilibili.com/video/{bvid}"

            # 构建消息链
            message_elements = [Text(message_text)]

            # 添加封面图片
            if pic_url:
                message_elements.append(Image(pic_url))

            return MessageChain(message_elements)

        except Exception as e:
            _log.error(f"格式化视频信息失败: {e}")
            return MessageChain([Text("视频信息格式化失败，请稍后再试。")])

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """📺 B站视频信息插件帮助

🎯 功能说明：
自动识别群聊中的B站视频链接，获取并展示详细的视频信息

🔍 支持格式：
• BV号：BV1xx4y1x7xx
• AV号：av123456
• 完整链接：https://www.bilibili.com/video/BVxxx
• 短链接：b23.tv/xxx

📊 显示信息：
• 视频标题、UP主、分区
• 播放量、点赞、投币、收藏等数据
• 视频时长、发布时间
• 视频简介和封面图片

💡 使用方法：
直接在群聊中发送包含B站视频链接的消息即可

⚡ 特色功能：
• 智能缓存：避免重复请求
• 批量处理：一次处理多个视频
• 数据美化：友好的数字格式显示
• 限流保护：避免频繁请求

📝 命令列表：
• /bili帮助 - 显示此帮助信息

🔧 版本：v2.0.0
💡 提示：插件会自动识别消息中的视频链接，无需手动触发"""

        await self.api.post_group_msg(group_id, text=help_text)

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件，匹配视频ID并发送视频信息
        """
        raw_message = event.raw_message.strip()

        # 检查是否是帮助命令
        if raw_message in ["/bili帮助", "/B站帮助", "/bilibili帮助"]:
            await self.show_help(event.group_id)
            return

        # 检查限流
        if self._should_rate_limit(event.group_id):
            _log.info(f"群 {event.group_id} 请求过于频繁，跳过处理")
            return

        # 提取BV号和AV号
        bv_pattern = r"(BV[a-zA-Z0-9]{10})"
        av_pattern = r"av(\d+)"

        bvids = re.findall(bv_pattern, raw_message, re.IGNORECASE)
        avids = re.findall(av_pattern, raw_message, re.IGNORECASE)

        # 合并所有视频ID
        video_requests = []
        for bvid in bvids:
            video_requests.append((bvid, True))  # (id, is_bv)
        for avid in avids:
            video_requests.append((avid, False))  # (id, is_bv)

        if not video_requests:
            return

        # 限制单次处理的视频数量
        max_videos = 3
        if len(video_requests) > max_videos:
            video_requests = video_requests[:max_videos]
            _log.info(f"限制处理视频数量为 {max_videos} 个")

        _log.info(f"检测到视频: {[req[0] for req in video_requests]}")

        # 更新请求时间
        self.last_request_time[event.group_id] = time.time()

        # 并发获取视频信息
        try:
            tasks = [self.fetch_video_info(video_id, is_bv) for video_id, is_bv in video_requests]
            video_data_list = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = 0
            for i, video_data in enumerate(video_data_list):
                video_id, is_bv = video_requests[i]

                if isinstance(video_data, Exception):
                    _log.error(f"获取视频 {video_id} 信息时发生异常: {video_data}")
                    continue

                if video_data and video_data.get("code") == 0:
                    _log.info(f"视频 {video_id} 获取成功")
                    message_chain = self.format_video_info(video_data)
                    await self.api.post_group_msg(event.group_id, rtf=message_chain)
                    success_count += 1

                    # 添加延迟避免发送过快
                    if i < len(video_data_list) - 1:
                        await asyncio.sleep(0.5)
                else:
                    _log.warning(f"视频 {video_id} 获取失败")

            if success_count == 0 and len(video_requests) > 0:
                await self.api.post_group_msg(event.group_id, text="获取视频信息失败，请检查视频ID是否正确或稍后再试。")

        except Exception as e:
            _log.error(f"处理视频信息时发生错误: {e}")
            await self.api.post_group_msg(event.group_id, text="处理视频信息时发生错误，请稍后再试。")
