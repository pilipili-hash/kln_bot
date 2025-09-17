import aiohttp
import asyncio
import time
import random
import string
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from PluginManager.plugin_manager import feature_required
from urllib.parse import quote
from utils.group_forward_msg import send_group_forward_msg_ws
from utils.group_forward_msg import MessageBuilder, cq_img
import re
from typing import Dict, List, Any, Optional

bot = CompatibleEnrollment

class ComicSearch(BasePlugin):
    name = "ComicSearch"
    version = "2.0.0"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 缓存系统
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存
        # 请求限制
        self.last_request_time = {}
        self.request_interval = 2  # 2秒间隔

    async def __onload__(self):
        """插件加载时调用"""
        await self.on_load()

    async def on_load(self):
        print(f"{self.name} 插件已加载，版本: {self.version}")

    def _get_cache_key(self, query: str, limit: int = 6) -> str:
        """生成缓存键"""
        return f"comic_search:{query}:{limit}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False
        timestamp, _ = self.cache[cache_key]
        return time.time() - timestamp < self.cache_ttl

    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        if self._is_cache_valid(cache_key):
            _, result = self.cache[cache_key]
            return result
        return None

    def _set_cache(self, cache_key: str, result: Dict[str, Any]):
        """设置缓存"""
        self.cache[cache_key] = (time.time(), result)

    def _check_request_limit(self, user_id: int) -> bool:
        """检查请求频率限制"""
        current_time = time.time()
        if user_id in self.last_request_time:
            if current_time - self.last_request_time[user_id] < self.request_interval:
                return False
        self.last_request_time[user_id] = current_time
        return True

    async def fetch_comics(self, query: str, limit: int = 6, offset: int = 0) -> Optional[Dict[str, Any]]:
        """
        调用漫画搜索 API

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            offset: 偏移量

        Returns:
            Dict: API响应数据，或None
        """
        # 检查缓存
        cache_key = self._get_cache_key(query, limit)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            print("返回缓存的漫画搜索结果")
            return cached_result

        base_url = "https://www.mangacopy.com/api/kb/web/searchcc/comics"
        params = {
            "offset": offset,
            "platform": 2,
            "limit": limit,
            "q": query,
            "q_type": ""
        }

        # 构建URL
        url = f"{base_url}?{'&'.join([f'{k}={quote(str(v))}' for k, v in params.items()])}"

        # 重试机制
        for attempt in range(3):
            try:
                timeout = aiohttp.ClientTimeout(total=15, connect=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            # 缓存结果
                            self._set_cache(cache_key, data)
                            return data
                        else:
                            print(f"漫画搜索API请求失败，状态码: {response.status}")
                            return None

            except aiohttp.ClientError as e:
                print(f"漫画搜索API网络请求失败 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                continue
            except Exception as e:
                print(f"漫画搜索API请求异常 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                continue

        return None

    def format_comics_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        格式化漫画数据

        Args:
            data: API响应数据

        Returns:
            List[Dict]: 格式化后的漫画信息列表
        """
        if not data or data.get("code") != 200 or not data.get("results"):
            return []

        comics: List[Dict[str, Any]] = []
        results = data.get("results", {})
        comic_list = results.get("list", [])

        for item in comic_list:
            try:
                # 安全获取作者信息
                authors = item.get("author", [])
                author_names = []
                if isinstance(authors, list):
                    for author in authors:
                        if isinstance(author, dict) and "name" in author:
                            author_names.append(author["name"])
                        elif isinstance(author, str):
                            author_names.append(author)

                # 格式化人气数字
                popular = item.get("popular", 0)
                if isinstance(popular, (int, float)):
                    if popular >= 10000:
                        popular_str = f"{popular/10000:.1f}万"
                    else:
                        popular_str = str(int(popular))
                else:
                    popular_str = str(popular)

                comic_info = {
                    "name": item.get("name", "未知漫画"),
                    "alias": item.get("alias", ""),
                    "cover": item.get("cover", ""),
                    "author": ", ".join(author_names) if author_names else "未知作者",
                    "popular": popular_str,
                    "path_word": item.get("path_word", ""),
                    "brief": item.get("brief", ""),
                    "datetime_updated": item.get("datetime_updated", ""),
                    "status": item.get("status", {}).get("display", "未知状态") if item.get("status") else "未知状态"
                }
                comics.append(comic_info)

            except Exception as e:
                print(f"格式化漫画数据时出错: {e}")
                continue

        return comics

    async def send_comics_forward(self, event: GroupMessage, comics: List[Dict[str, Any]], query: str):
        """
        发送漫画搜索结果（合并转发格式）

        Args:
            event: 群消息事件
            comics: 漫画信息列表
            query: 搜索关键词
        """
        try:
            # 创建转发消息列表
            forward_messages = []

            # 创建标题消息
            current_time = time.strftime("%H:%M:%S", time.localtime())
            title_content = (
                f"📚 漫画搜索结果\n"
                f"🔍 搜索关键词: {query}\n"
                f"📊 找到 {len(comics)} 部漫画\n"
                f"⏰ 搜索时间: {current_time}"
            )

            forward_messages.append({
                "type": "node",
                "data": {
                    "nickname": "漫画搜索",
                    "user_id": str(event.self_id),
                    "content": title_content
                }
            })

            # 处理每部漫画
            for i, comic in enumerate(comics):
                try:
                    # 构建漫画信息
                    comic_url = f"https://www.mangacopy.com/comic/{comic['path_word']}"
                    content_parts = [f"📖 {comic['name']}"]

                    if comic['alias']:
                        content_parts.append(f"📝 别名: {comic['alias']}")

                    content_parts.extend([
                        f"👤 作者: {comic['author']}",
                        f"🔥 人气: {comic['popular']}",
                        f"📊 状态: {comic['status']}"
                    ])

                    # 简介
                    if comic['brief']:
                        brief = comic['brief'][:100] + "..." if len(comic['brief']) > 100 else comic['brief']
                        content_parts.append(f"📄 简介: {brief}")

                    content_parts.append(f"🔗 链接: {comic_url}")

                    # 封面图片
                    if comic['cover']:
                        content_parts.append(f"🖼️ 封面: {cq_img(comic['cover'])}")

                    content = "\n".join(content_parts)

                    forward_messages.append({
                        "type": "node",
                        "data": {
                            "nickname": f"漫画 {i+1}",
                            "user_id": str(event.self_id),
                            "content": content
                        }
                    })

                except Exception as e:
                    print(f"处理漫画 {i} 失败: {e}")
                    # 添加错误节点
                    error_content = f"❌ 处理第 {i+1} 部漫画时出错: {str(e)}"
                    forward_messages.append({
                        "type": "node",
                        "data": {
                            "nickname": f"错误 {i+1}",
                            "user_id": str(event.self_id),
                            "content": error_content
                        }
                    })

            # 发送合并转发消息
            await send_group_forward_msg_ws(event.group_id, forward_messages)

        except Exception as e:
            print(f"发送漫画搜索结果失败: {e}")
            await self.send_fallback_comics_info(event.group_id, comics, query)

    async def send_fallback_comics_info(self, group_id: int, comics: List[Dict[str, Any]], query: str):
        """
        发送降级的漫画信息（当合并转发失败时）

        Args:
            group_id: 群号
            comics: 漫画信息列表
            query: 搜索关键词
        """
        try:
            for i, comic in enumerate(comics[:3]):  # 降级时只显示前3个
                comic_url = f"https://www.mangacopy.com/comic/{comic['path_word']}"
                text = (
                    f"📚 漫画搜索结果 {i+1}\n"
                    f"📖 名称: {comic['name']}\n"
                    f"👤 作者: {comic['author']}\n"
                    f"🔥 人气: {comic['popular']}\n"
                    f"📊 状态: {comic['status']}\n"
                    f"🔗 链接: {comic_url}"
                )
                await self.api.post_group_msg(group_id, text=text)
                await asyncio.sleep(0.5)  # 避免发送过快

        except Exception as e:
            print(f"发送降级漫画信息失败: {e}")

    def _parse_comic_command(self, message: str) -> Optional[Dict[str, Any]]:
        """
        解析漫画搜索命令

        Args:
            message: 原始消息

        Returns:
            Dict: 解析后的参数，或None
        """
        # 基础命令格式: /漫画搜索 关键词
        basic_match = re.match(r"^/漫画搜索\s+(.+)$", message.strip())
        if basic_match:
            return {
                "query": basic_match.group(1).strip(),
                "limit": 6
            }

        # 高级命令格式: /漫画搜索 关键词 数量
        advanced_match = re.match(r"^/漫画搜索\s+(.+?)\s+(\d+)$", message.strip())
        if advanced_match:
            query = advanced_match.group(1).strip()
            limit = int(advanced_match.group(2))
            limit = min(max(limit, 1), 20)  # 限制在1-20之间
            return {
                "query": query,
                "limit": limit
            }

        # 帮助命令
        if message.strip() in ["/漫画搜索", "/漫画搜索 帮助", "/漫画搜索 help"]:
            return {"help": True}

        return None

    async def _show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """📚 漫画搜索功能帮助

🔍 基础命令：
• /漫画搜索 <关键词> - 搜索漫画（默认6个结果）
• /漫画搜索 <关键词> <数量> - 搜索指定数量的漫画

💡 使用示例：
/漫画搜索 进击的巨人
/漫画搜索 海贼王 10
/漫画搜索 鬼灭之刃 3

📊 功能特点：
• 🚀 基于漫画拷贝API，资源丰富
• 💾 智能缓存机制，快速响应
• 🎯 精准搜索，支持中文关键词
• 📱 美观展示，合并转发格式
• 🔗 直接提供漫画链接

⚠️ 使用限制：
• 搜索间隔：2秒
• 结果数量：1-20个
• 缓存时间：5分钟

💡 小贴士：
• 使用准确的漫画名称获得更好结果
• 支持别名和作者名搜索
• 结果按人气排序"""

        await self.api.post_group_msg(group_id, text=help_text)

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        try:
            raw_message = event.raw_message.strip()

            # 解析命令
            parsed = self._parse_comic_command(raw_message)
            if not parsed:
                return

            # 显示帮助
            if parsed.get("help"):
                await self._show_help(event.group_id)
                return

            # 检查请求频率限制
            if not self._check_request_limit(event.user_id):
                await self.api.post_group_msg(
                    event.group_id,
                    text="⏰ 请求过于频繁，请等待2秒后再试"
                )
                return

            query = parsed["query"]
            limit = parsed.get("limit", 6)

            # 发送搜索提示
            await self.api.post_group_msg(
                event.group_id,
                text=f"🔍 正在搜索「{query}」，请稍等..."
            )

            # 搜索漫画
            data = await self.fetch_comics(query, limit=limit)
            if not data:
                await self.api.post_group_msg(
                    event.group_id,
                    text="❌ 漫画搜索失败，请稍后再试"
                )
                return

            # 格式化数据
            comics = self.format_comics_data(data)
            if not comics:
                await self.api.post_group_msg(
                    event.group_id,
                    text=f"📚 未找到与「{query}」相关的漫画"
                )
                return

            # 发送结果
            await self.send_comics_forward(event, comics, query)

        except Exception as e:
            print(f"处理漫画搜索命令失败: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="❌ 处理搜索请求时出错，请稍后再试"
            )
