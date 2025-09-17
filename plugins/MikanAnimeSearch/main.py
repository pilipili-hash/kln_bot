import aiohttp
import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from urllib.parse import quote
import re
# 尝试导入插件管理器，如果失败则提供默认实现
try:
    from PluginManager.plugin_manager import feature_required
except ImportError:
    def feature_required(feature_name=None, commands=None, require_admin=False):
        """简单的装饰器替代版本"""
        def decorator(func):
            return func
        return decorator
from utils.group_forward_msg import send_group_forward_msg_ws
from utils.config_manager import get_config, load_config
from utils.logger_config import get_logger

# 获取日志记录器
_log = get_logger(__name__)

bot = CompatibleEnrollment

class MikanAnimeSearch(BasePlugin):
    name = "MikanAnimeSearch"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        # 缓存系统
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 600  # 10分钟缓存

        # 频率限制
        self._user_last_request: Dict[int, float] = {}
        self._rate_limit_interval = 2.0  # 2秒间隔

        # 统计数据
        self._stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

        # HTTP连接器配置
        self._connector = None
        self._session = None

    async def on_load(self):
        """插件加载时的初始化"""
        try:
            # 创建优化的HTTP连接器
            connector = aiohttp.TCPConnector(
                limit=15,  # 总连接数
                limit_per_host=8,  # 单主机连接数
                ttl_dns_cache=600,  # DNS缓存10分钟
                use_dns_cache=True,
                enable_cleanup_closed=True
            )

            # 创建HTTP会话
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )

            _log.info(f"{self.name} v{self.version} 插件已加载")
            _log.info("HTTP连接池已初始化，缓存系统已启动")

        except Exception as e:
            _log.error(f"插件加载失败: {e}")
            raise

    async def on_unload(self):
        """插件卸载时的清理"""
        try:
            if self._session:
                await self._session.close()
            _log.info(f"{self.name} 插件已卸载，资源已清理")
        except Exception as e:
            _log.error(f"插件卸载时出错: {e}")

    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否有效"""
        return time.time() - cache_entry['timestamp'] < self._cache_ttl

    def _cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time - entry['timestamp'] >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            _log.debug(f"清理了 {len(expired_keys)} 个过期缓存条目")

    def _check_rate_limit(self, user_id: int) -> bool:
        """检查用户请求频率限制"""
        current_time = time.time()
        last_request = self._user_last_request.get(user_id, 0)

        if current_time - last_request < self._rate_limit_interval:
            return False

        self._user_last_request[user_id] = current_time
        return True

    async def search_mikan_anime(self, query: str) -> Optional[str]:
        """访问 Mikanani 搜索并解析结果"""
        try:
            # 检查缓存
            cache_key = self._get_cache_key(query)
            self._cleanup_cache()

            if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
                _log.info(f"缓存命中: {query}")
                self._stats["cache_hits"] += 1
                return self._cache[cache_key]['data']

            self._stats["cache_misses"] += 1

            # 构建搜索URL
            base_url = "https://mikanani.me/Home/Search"
            search_url = f"{base_url}?searchstr={quote(query)}"

            # 获取代理配置
            proxy_config = get_config("proxy", {})
            proxy = None
            if isinstance(proxy_config, dict) and proxy_config.get("enabled", False):
                proxy = proxy_config.get("http", "")
            elif isinstance(proxy_config, str) and proxy_config:
                proxy = proxy_config

            _log.info(f"搜索番剧: {query}, URL: {search_url}")

            # 发送HTTP请求
            async with self._session.get(search_url, proxy=proxy) as response:
                if response.status == 200:
                    html_content = await response.text()

                    # 缓存结果
                    self._cache[cache_key] = {
                        'data': html_content,
                        'timestamp': time.time()
                    }

                    _log.info(f"搜索成功: {query}, 响应大小: {len(html_content)} 字符")
                    return html_content
                else:
                    _log.warning(f"HTTP请求失败: 状态码 {response.status}")
                    await self.api.post_group_msg(
                        self.event.group_id,
                        text=f"搜索失败，服务器返回状态码: {response.status}"
                    )
                    return None

        except asyncio.TimeoutError:
            _log.warning(f"搜索超时: {query}")
            await self.api.post_group_msg(
                self.event.group_id,
                text="搜索超时，请检查网络连接或稍后重试"
            )
            return None

        except aiohttp.ClientError as e:
            _log.error(f"网络请求失败: {e}")
            await self.api.post_group_msg(
                self.event.group_id,
                text=f"网络请求失败: {str(e)[:100]}..."
            )
            return None

        except Exception as e:
            _log.error(f"搜索过程中发生未知错误: {e}")
            await self.api.post_group_msg(
                self.event.group_id,
                text="搜索过程中发生错误，请稍后重试"
            )
            return None

    def parse_mikan_results(self, html_content: str) -> List[Dict[str, str]]:
        """解析 Mikanani 搜索结果页面"""
        results = []

        try:
            soup = BeautifulSoup(html_content, "lxml")
            search_result_elements = soup.find_all("tr", class_="js-search-results-row")

            if not search_result_elements:
                _log.info("未找到搜索结果元素")
                return []

            _log.info(f"找到 {len(search_result_elements)} 个搜索结果")

            for i, result_element in enumerate(search_result_elements[:6]):  # 限制最多返回 6 个结果
                try:
                    # 提取番剧信息
                    title_element = result_element.find("a", class_="magnet-link-wrap")
                    title = title_element.get_text(strip=True) if title_element else "无标题"
                    link = "https://mikanani.me" + title_element["href"] if title_element and title_element.has_attr("href") else "无链接"

                    magnet_element = result_element.find("a", class_="js-magnet")
                    magnet_link_full = magnet_element["data-clipboard-text"] if magnet_element and magnet_element.has_attr("data-clipboard-text") else "无磁力链接"
                    magnet_link = magnet_link_full.split('&')[0] if '&' in magnet_link_full else magnet_link_full

                    # 提取文件大小信息
                    size_element = result_element.find("td", class_="size")
                    file_size = size_element.get_text(strip=True) if size_element else "未知大小"

                    # 提取发布时间
                    date_element = result_element.find("td", class_="date")
                    publish_date = date_element.get_text(strip=True) if date_element else "未知时间"

                    # 格式化结果
                    result_data = {
                        "title": title,
                        "link": link,
                        "magnet": magnet_link,
                        "size": file_size,
                        "date": publish_date
                    }

                    results.append(result_data)
                    _log.debug(f"解析结果 {i+1}: {title[:50]}...")

                except Exception as e:
                    _log.warning(f"解析第 {i+1} 个结果失败: {e}")
                    continue

            _log.info(f"成功解析 {len(results)} 个结果")
            return results

        except Exception as e:
            _log.error(f"解析HTML内容失败: {e}")
            return []

    async def _send_stats(self, event: GroupMessage):
        """发送统计信息"""
        try:
            cache_hit_rate = 0
            if self._stats["cache_hits"] + self._stats["cache_misses"] > 0:
                cache_hit_rate = self._stats["cache_hits"] / (self._stats["cache_hits"] + self._stats["cache_misses"]) * 100

            success_rate = 0
            if self._stats["total_searches"] > 0:
                success_rate = self._stats["successful_searches"] / self._stats["total_searches"] * 100

            stats_text = (
                f"📊 蜜柑番剧搜索统计\n\n"
                f"🔍 总搜索次数: {self._stats['total_searches']}\n"
                f"✅ 成功次数: {self._stats['successful_searches']}\n"
                f"❌ 失败次数: {self._stats['failed_searches']}\n"
                f"📈 成功率: {success_rate:.1f}%\n\n"
                f"💾 缓存统计:\n"
                f"🎯 缓存命中: {self._stats['cache_hits']}\n"
                f"🔄 缓存未命中: {self._stats['cache_misses']}\n"
                f"📊 缓存命中率: {cache_hit_rate:.1f}%\n\n"
                f"⚙️ 系统信息:\n"
                f"🕒 缓存TTL: {self._cache_ttl}秒\n"
                f"📦 当前缓存条目: {len(self._cache)}\n"
                f"⏱️ 请求间隔限制: {self._rate_limit_interval}秒"
            )

            await self.api.post_group_msg(event.group_id, text=stats_text)

        except Exception as e:
            _log.error(f"发送统计信息失败: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="获取统计信息失败，请稍后重试"
            )

    async def send_comics_forward(self, event: GroupMessage, comics: List[Dict[str, str]]):
        """合并转发番剧信息"""
        try:
            messages = []
            bot_name = get_config("bot_name", "蜜柑搜索助手")

            # 添加搜索结果头部信息
            header_content = (
                f"🔍 蜜柑番剧搜索结果\n\n"
                f"📊 找到 {len(comics)} 个结果\n"
                f"🕒 搜索时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"💡 点击磁力链接可直接下载"
            )

            messages.append({
                "type": "node",
                "data": {
                    "nickname": f"{bot_name}",
                    "user_id": str(event.self_id),
                    "content": header_content
                }
            })

            # 添加每个搜索结果
            for i, comic in enumerate(comics, 1):
                content = (
                    f"📺 番剧 {i}: {comic['title']}\n\n"
                    f"🔗 详情页面: {comic['link']}\n"
                    f"🧲 磁力链接: {comic['magnet']}\n"
                    f"📦 文件大小: {comic.get('size', '未知')}\n"
                    f"📅 发布时间: {comic.get('date', '未知')}"
                )

                messages.append({
                    "type": "node",
                    "data": {
                        "nickname": f"{bot_name} - 结果{i}",
                        "user_id": str(event.self_id),
                        "content": content
                    }
                })

            # 添加使用提示
            footer_content = (
                "💡 使用提示:\n"
                "• 复制磁力链接到下载工具\n"
                "• 点击详情页面查看更多信息\n"
                "• 发送 /番剧统计 查看搜索统计\n"
                "• 发送 /番剧帮助 查看详细帮助"
            )

            messages.append({
                "type": "node",
                "data": {
                    "nickname": f"{bot_name} - 提示",
                    "user_id": str(event.self_id),
                    "content": footer_content
                }
            })

            await send_group_forward_msg_ws(
                group_id=event.group_id,
                content=messages
            )

            _log.info(f"成功发送 {len(comics)} 个搜索结果的合并转发消息")

        except Exception as e:
            _log.error(f"发送合并转发消息失败: {e}")
            # 降级为普通文本消息
            await self._send_results_as_text(event, comics)

    async def _send_results_as_text(self, event: GroupMessage, comics: List[Dict[str, str]]):
        """降级发送普通文本结果"""
        try:
            if not comics:
                await self.api.post_group_msg(event.group_id, text="未找到相关番剧")
                return

            text_results = f"🔍 找到 {len(comics)} 个番剧结果:\n\n"

            for i, comic in enumerate(comics[:3], 1):  # 文本模式只显示前3个
                text_results += (
                    f"{i}. {comic['title']}\n"
                    f"   大小: {comic.get('size', '未知')}\n"
                    f"   时间: {comic.get('date', '未知')}\n\n"
                )

            if len(comics) > 3:
                text_results += f"... 还有 {len(comics) - 3} 个结果\n\n"

            text_results += "💡 发送 /番剧统计 查看搜索统计"

            await self.api.post_group_msg(event.group_id, text=text_results)
            _log.info("已降级为文本消息发送搜索结果")

        except Exception as e:
            _log.error(f"发送文本结果失败: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="发送搜索结果失败，请稍后重试"
            )

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        self.event = event
        raw_message = event.raw_message.strip()

        try:
            # 番剧搜索命令
            search_match = re.match(r"^/番剧搜索\s*(.*)$", raw_message)
            if search_match:
                await self._handle_search_command(event, search_match.group(1).strip())
                return

            # 统计命令
            if raw_message in ["/番剧统计", "/蜜柑统计"]:
                await self._send_stats(event)
                return

            # 帮助命令
            if raw_message in ["/番剧帮助", "/蜜柑帮助"]:
                await self._send_help(event)
                return

        except Exception as e:
            _log.error(f"处理群消息时发生错误: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="处理命令时发生错误，请稍后重试"
            )

    async def _handle_search_command(self, event: GroupMessage, query: str):
        """处理搜索命令"""
        try:
            # 检查搜索内容
            if not query:
                await self.api.post_group_msg(
                    event.group_id,
                    text="请输入搜索内容，例如：/番剧搜索 异世界"
                )
                return

            # 检查频率限制
            if not self._check_rate_limit(event.user_id):
                await self.api.post_group_msg(
                    event.group_id,
                    text=f"请求过于频繁，请等待 {self._rate_limit_interval} 秒后再试"
                )
                return

            # 更新统计
            self._stats["total_searches"] += 1

            _log.info(f"用户 {event.user_id} 搜索番剧: {query}")
            await self.api.post_group_msg(event.group_id, text="🔍 正在搜索，请稍候...")

            # 执行搜索
            results = await self.search_mikan_anime(query)
            if results is None:
                self._stats["failed_searches"] += 1
                return

            # 解析结果
            parsed_results = self.parse_mikan_results(results)
            if parsed_results:
                self._stats["successful_searches"] += 1
                await self.send_comics_forward(event, parsed_results)
                _log.info(f"搜索成功: {query}, 返回 {len(parsed_results)} 个结果")
            else:
                self._stats["failed_searches"] += 1
                await self.api.post_group_msg(
                    event.group_id,
                    text="😔 未找到相关番剧，请尝试其他关键词"
                )
                _log.info(f"搜索无结果: {query}")

        except Exception as e:
            self._stats["failed_searches"] += 1
            _log.error(f"搜索命令处理失败: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="搜索过程中发生错误，请稍后重试"
            )

    async def _send_help(self, event: GroupMessage):
        """发送帮助信息"""
        try:
            help_text = (
                f"🍊 蜜柑番剧搜索 v{self.version}\n\n"
                "📋 可用命令:\n"
                "• /番剧搜索 <关键词> - 搜索番剧资源\n"
                "• /番剧统计 - 查看搜索统计\n"
                "• /番剧帮助 - 显示此帮助\n\n"
                "💡 使用示例:\n"
                "• /番剧搜索 异世界\n"
                "• /番剧搜索 鬼灭之刃\n"
                "• /番剧搜索 进击的巨人\n\n"
                "⚠️ 注意事项:\n"
                f"• 请求间隔: {self._rate_limit_interval}秒\n"
                f"• 缓存时间: {self._cache_ttl//60}分钟\n"
                "• 支持中文和日文搜索\n"
                "• 结果包含磁力链接和详情页面"
            )

            await self.api.post_group_msg(event.group_id, text=help_text)

        except Exception as e:
            _log.error(f"发送帮助信息失败: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="获取帮助信息失败，请稍后重试"
            )
