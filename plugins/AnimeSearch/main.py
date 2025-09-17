import aiohttp
import asyncio
import time
import hashlib
from typing import List, Dict, Any, Optional
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import Image, MessageChain, Text
from utils.group_forward_msg import get_cqimg, _message_sender
from PluginManager.plugin_manager import feature_required
from urllib.parse import quote
from utils.config_manager import get_config
from ncatbot.utils.logger import get_log

bot = CompatibleEnrollment

class AnimeSearch(BasePlugin):
    name = "AnimeSearch"
    version = "3.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session: Optional[aiohttp.ClientSession] = None
        self.search_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 600  # 缓存10分钟
        self.logger = get_log()

        # 请求限制
        self.last_request_time = {}
        self.request_interval = 2  # 2秒间隔

        # 统计信息
        self.stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "successful_searches": 0,
            "failed_searches": 0
        }

    async def on_load(self):
        """插件加载时初始化"""
        print(f"{self.name} 插件已加载，版本: {self.version}")

        # 创建HTTP会话，配置超时和连接池
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(
            limit=15,  # 总连接池大小
            limit_per_host=8,  # 每个主机的连接数
            ttl_dns_cache=600,  # DNS缓存10分钟
            use_dns_cache=True,
            enable_cleanup_closed=True
        )

        # 设置请求头
        headers = {
            'User-Agent': 'AnimeSearch Bot/3.0.0 (NCatBot)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        )

        self.pending_search = {}
        self.bot_name = get_config("bot_name", "NCatBot")
        self.bot_uin = get_config("bt_uin", 123456)

        self.logger.info(f"AnimeSearch v{self.version} 初始化完成")

    async def on_unload(self):
        """插件卸载时清理资源"""
        if self.session:
            await self.session.close()
        self.search_cache.clear()
        self.logger.info(f"{self.name} 插件已卸载")
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否有效"""
        return time.time() - cache_entry.get("timestamp", 0) < self.cache_ttl

    def _get_cache_key(self, image_url: str) -> str:
        """生成缓存键"""
        return hashlib.md5(image_url.encode()).hexdigest()

    def _check_rate_limit(self, user_id: int) -> bool:
        """检查用户请求频率限制"""
        current_time = time.time()
        if user_id in self.last_request_time:
            if current_time - self.last_request_time[user_id] < self.request_interval:
                return False
        self.last_request_time[user_id] = current_time
        return True

    async def search_anime(self, image_url: str, user_id: int = None) -> Dict[str, Any]:
        """调用 Trace.moe API 搜索番剧并返回结果"""
        self.stats["total_searches"] += 1

        # 检查缓存
        cache_key = self._get_cache_key(image_url)
        if cache_key in self.search_cache:
            cache_entry = self.search_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                self.stats["cache_hits"] += 1
                self.logger.info(f"使用缓存结果: {image_url[:50]}...")
                return cache_entry["data"]

        # 检查请求频率限制
        if user_id and not self._check_rate_limit(user_id):
            return {"success": False, "error": "请求过于频繁，请稍后再试"}

        encoded_url = quote(image_url, safe="")
        api_url = f"https://api.trace.moe/search?cutBorders&anilistInfo&url={encoded_url}"

        try:
            if not self.session:
                self.stats["failed_searches"] += 1
                return {"success": False, "error": "HTTP会话未初始化"}

            async with self.session.get(api_url) as response:
                if response.status == 429:  # 速率限制
                    self.logger.warning("API速率限制，等待重试")
                    await asyncio.sleep(2)
                    self.stats["failed_searches"] += 1
                    return {"success": False, "error": "请求过于频繁，请稍后再试"}

                if response.status != 200:
                    error_message = await response.text()
                    self.logger.error(f"API 错误信息: {error_message}")
                    self.stats["failed_searches"] += 1
                    return {"success": False, "error": f"搜索失败，状态码：{response.status}"}

                data = await response.json()

                # 验证返回数据
                if not isinstance(data, dict) or "result" not in data:
                    self.stats["failed_searches"] += 1
                    return {"success": False, "error": "API返回数据格式错误"}

                result = {"success": True, "data": data}
                self.stats["successful_searches"] += 1

                # 缓存结果
                self.search_cache[cache_key] = {
                    "data": result,
                    "timestamp": time.time()
                }

                # 清理过期缓存
                self._cleanup_cache()

                return result

        except asyncio.TimeoutError:
            self.logger.error("搜索请求超时")
            self.stats["failed_searches"] += 1
            return {"success": False, "error": "搜索请求超时，请稍后再试"}
        except aiohttp.ClientError as e:
            self.logger.error(f"网络请求错误: {e}")
            self.stats["failed_searches"] += 1
            return {"success": False, "error": "网络请求失败，请检查网络连接"}
        except Exception as e:
            self.logger.exception(f"搜索过程中发生未知错误: {e}")
            self.stats["failed_searches"] += 1
            return {"success": False, "error": "搜索过程中发生未知错误，请稍后再试"}

    def _cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.search_cache.items()
            if current_time - entry.get("timestamp", 0) > self.cache_ttl
        ]
        for key in expired_keys:
            del self.search_cache[key]

    def format_results_for_forward(self, data: dict) -> List[Dict[str, Any]]:
        """格式化 API 返回的结果为合并转发消息格式"""
        if not data.get("result"):
            return [{
                "type": "node",
                "data": {
                    "nickname": f"{self.bot_name}助手",
                    "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                    "content": "❌ 未找到相关番剧信息"
                }
            }]

        results = data["result"]
        forward_messages = []

        # 添加标题消息
        forward_messages.append({
            "type": "node",
            "data": {
                "nickname": f"{self.bot_name}助手",
                "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                "content": f"🔍 以图搜番结果\n\n找到 {len(results)} 个相关结果，显示前5个最相似的："
            }
        })

        for i, result in enumerate(results[:5], 1):  # 显示前5个结果
            try:
                # 安全地提取数据，避免KeyError
                anilist_data = result.get("anilist", {})
                title_data = anilist_data.get("title", {})

                title = title_data.get("native") or title_data.get("romaji") or title_data.get("english") or "未知"
                romaji = title_data.get("romaji", "")
                english = title_data.get("english", "")

                episode = result.get("episode")
                if episode is None:
                    episode = "未知"
                elif isinstance(episode, (int, float)):
                    episode = str(int(episode))

                similarity = round(result.get("similarity", 0) * 100, 2)
                image_url = result.get("image", "")

                if not image_url:
                    self.logger.warning(f"结果 {i} 缺少图片URL")
                    continue

                # 构建标题显示
                title_display = title
                if romaji and romaji != title:
                    title_display += f"\n({romaji})"
                if english and english != title and english != romaji:
                    title_display += f"\n[{english}]"

                # 获取额外信息
                start_date = anilist_data.get("startDate", {})
                year = start_date.get("year", "未知") if isinstance(start_date, dict) else "未知"
                format_type = anilist_data.get("format", "未知")

                # 构建文字内容
                text_content = f"📺 结果 {i}\n\n" \
                              f"🎬 番剧名称：{title_display}\n" \
                              f"📅 集数：第 {episode} 集\n" \
                              f"🎯 相似度：{similarity}%\n" \
                              f"📆 年份：{year}\n" \
                              f"📋 类型：{format_type}\n" \
                              f"🖼️ 截图预览："

                # 使用OneBot消息段格式，将文字和图片组合在一个消息中
                content = [
                    {
                        "type": "text",
                        "data": {"text": text_content}
                    },
                    {
                        "type": "image",
                        "data": {"file": image_url}
                    }
                ]

                forward_messages.append({
                    "type": "node",
                    "data": {
                        "nickname": f"{self.bot_name}助手",
                        "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                        "content": content
                    }
                })

            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(f"解析搜索结果 {i} 失败: {e}")
                continue
            except Exception as e:
                self.logger.error(f"处理搜索结果 {i} 时发生未知错误: {e}")
                continue

        # 添加使用提示
        forward_messages.append({
            "type": "node",
            "data": {
                "nickname": f"{self.bot_name}助手",
                "user_id": str(self.bot_uin),  # 修复：使用user_id字段且确保是字符串
                "content": "💡 使用提示：\n\n" \
                          "• 相似度越高表示匹配度越好\n" \
                          "• 建议选择相似度80%以上的结果\n" \
                          "• 如需更多帮助，请发送 /搜番帮助"
            }
        })

        return forward_messages

    async def handle_image_search(self, group_id: int, image_url: str, user_id: int = None):
        """处理图片搜索逻辑"""
        try:
            await self.api.post_group_msg(group_id, text="🔍 正在搜索番剧，请稍候...")

            # 调用搜索API
            result = await self.search_anime(image_url, user_id)

            if not result["success"]:
                await self.api.post_group_msg(group_id, text=f"❌ {result['error']}")
                return

            # 格式化为合并转发消息
            forward_messages = self.format_results_for_forward(result["data"])

            # 发送合并转发消息
            success = await _message_sender.send_group_forward_msg(group_id, forward_messages)

            if not success:
                # 如果合并转发失败，发送简化版本
                await self.send_simple_results(group_id, result["data"])

        except Exception as e:
            self.logger.error(f"搜索过程中发生错误: {e}")
            await self.api.post_group_msg(group_id, text=f"❌ 搜索失败，发生错误：{str(e)[:100]}")

    async def send_simple_results(self, group_id: int, data: dict):
        """发送简化版搜索结果（当合并转发失败时使用）"""
        if not data.get("result"):
            await self.api.post_group_msg(group_id, text="❌ 未找到相关番剧信息")
            return

        results = data["result"]
        message = f"🔍 以图搜番结果（找到 {len(results)} 个结果）：\n\n"

        for i, result in enumerate(results[:3], 1):  # 简化版只显示前3个
            try:
                # 安全地提取数据
                anilist_data = result.get("anilist", {})
                title_data = anilist_data.get("title", {})
                title = title_data.get("native") or title_data.get("romaji") or title_data.get("english") or "未知"

                episode = result.get("episode", "未知")
                if isinstance(episode, (int, float)):
                    episode = str(int(episode))

                similarity = round(result.get("similarity", 0) * 100, 2)

                message += f"{i}. {title}\n"
                message += f"   集数：第 {episode} 集\n"
                message += f"   相似度：{similarity}%\n\n"

            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(f"解析简化结果 {i} 失败: {e}")
                continue

        message += "💡 发送 /搜番帮助 查看详细使用说明"
        await self.api.post_group_msg(group_id, text=message)

    async def _send_help(self, group_id: int):
        """发送帮助信息"""
        help_text = """📖 以图搜番 帮助 v3.0.0
==============================

🎯 功能说明：
通过上传动漫截图来识别番剧信息，基于Trace.moe数据库

📝 使用方法：
• /搜番 [图片] - 直接搜索（图片和命令一起发送）
• /搜番 - 发送命令后再发送图片
• /取消 - 取消当前搜番操作
• /搜番统计 - 查看使用统计信息

🎮 使用示例：
1. 发送 "/搜番" 然后发送动漫截图
2. 或者直接发送 "/搜番" + 图片

📊 结果说明：
• 相似度：匹配准确度（建议选择80%以上）
• 集数：对应的动漫集数
• 年份：动漫发布年份
• 类型：TV/Movie/OVA等

⚠️ 注意事项：
• 支持常见图片格式（jpg、png、gif等）
• 建议使用清晰的动漫截图
• 搜索结果基于Trace.moe数据库
• 部分冷门番剧可能搜索不到
• 请求间隔2秒，避免频繁搜索

💡 小贴士：
• 人物特写比风景图效果更好
• 避免使用有水印的图片
• 如果搜索不到，可以尝试其他截图
• 支持智能缓存，重复搜索更快

🔧 技术特性：
• 智能缓存系统（10分钟）
• 请求频率限制保护
• 详细的搜索统计
• 优化的网络连接池"""

        await self.api.post_group_msg(group_id, text=help_text)

    async def _send_stats(self, group_id: int):
        """发送统计信息"""
        cache_size = len(self.search_cache)
        cache_hit_rate = (self.stats["cache_hits"] / max(self.stats["total_searches"], 1)) * 100
        success_rate = (self.stats["successful_searches"] / max(self.stats["total_searches"], 1)) * 100

        stats_text = f"""📊 AnimeSearch 统计信息
==============================

🔍 搜索统计：
• 总搜索次数：{self.stats["total_searches"]}
• 成功搜索：{self.stats["successful_searches"]}
• 失败搜索：{self.stats["failed_searches"]}
• 成功率：{success_rate:.1f}%

💾 缓存统计：
• 缓存命中：{self.stats["cache_hits"]}
• 缓存大小：{cache_size} 条
• 命中率：{cache_hit_rate:.1f}%

⚙️ 系统信息：
• 插件版本：{self.version}
• 缓存TTL：{self.cache_ttl}秒
• 请求间隔：{self.request_interval}秒"""

        await self.api.post_group_msg(group_id, text=stats_text)

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        group_id = event.group_id
        user_id = event.user_id
        raw_message = event.raw_message.strip()

        # 帮助命令
        if raw_message in ["/搜番帮助", "/以图搜番帮助"]:
            await self._send_help(group_id)
            return

        # 统计命令
        if raw_message == "/搜番统计":
            await self._send_stats(group_id)
            return

        # 如果消息以 "/搜番" 开头
        if raw_message.startswith("/搜番"):
            if "[CQ:image" in raw_message:  # 检查是否包含图片
                image_url = get_cqimg(raw_message)
                if image_url:
                    await self.handle_image_search(group_id, image_url, user_id)
            else:
                # 记录用户状态，等待后续图片
                self.pending_search[group_id] = user_id
                await self.api.post_group_msg(group_id, text="📷 请发送图片以完成搜索，或发送 /取消 取消操作")
            return

        # 处理取消搜番（优先处理取消命令）
        if raw_message == "/取消" and group_id in self.pending_search:
            if self.pending_search[group_id] == user_id:
                del self.pending_search[group_id]
                await self.api.post_group_msg(group_id, text="✅ 已取消搜番操作")
            return

        # 如果消息是图片，且用户之前发送了 "/搜番"
        if group_id in self.pending_search and self.pending_search[group_id] == user_id:
            image_url = None
            for segment in event.message:
                if segment["type"] == "image":
                    image_url = segment["data"].get("url")
                    break

            if image_url:
                # 清除用户状态
                del self.pending_search[group_id]
                await self.handle_image_search(group_id, image_url, user_id)
            else:
                # 没有图片，提示用户
                await self.api.post_group_msg(group_id, text="❌ 请发送包含图片的消息，或发送 /取消 取消搜番")
            return