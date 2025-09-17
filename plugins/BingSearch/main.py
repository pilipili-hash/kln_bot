import aiohttp
import asyncio
import time
from bs4 import BeautifulSoup
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from urllib.parse import quote
from PluginManager.plugin_manager import feature_required
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

# 导入日志和配置
try:
    from ncatbot.utils.logger import get_log
except ImportError:
    try:
        from ncatbot.utils import get_log
    except ImportError:
        import logging
        def get_log():
            return logging.getLogger(__name__)

try:
    from utils.config_manager import get_config
except ImportError:
    def get_config(key, default=None):
        config_defaults = {
            "bot_name": "NCatBot",
            "bt_uin": 123456
        }
        return config_defaults.get(key, default)

bot = CompatibleEnrollment

class BingSearch(BasePlugin):
    name = "BingSearch"  # 插件名称
    version = "2.0.0"  # 插件版本

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = get_log()
        self.bot_name = get_config("bot_name", "NCatBot")
        self.bot_uin = get_config("bt_uin", 123456)

        # 缓存机制
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存

        # 请求限制
        self.last_request_time = {}
        self.request_interval = 2  # 2秒间隔

    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return f"bing_search_{hash(query.lower())}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False

        cache_time, _ = self.cache[cache_key]
        return time.time() - cache_time < self.cache_ttl

    def _get_cached_result(self, cache_key: str) -> Optional[str]:
        """获取缓存结果"""
        if self._is_cache_valid(cache_key):
            _, result = self.cache[cache_key]
            return result
        return None

    def _set_cache(self, cache_key: str, result: str):
        """设置缓存"""
        self.cache[cache_key] = (time.time(), result)

        # 清理过期缓存
        current_time = time.time()
        expired_keys = [
            key for key, (cache_time, _) in self.cache.items()
            if current_time - cache_time > self.cache_ttl
        ]
        for key in expired_keys:
            del self.cache[key]

    async def fetch_bing_results(self, query: str) -> str:
        """访问 Bing 搜索并解析结果"""
        # 检查缓存
        cache_key = self._get_cache_key(query)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            self.logger.info(f"返回缓存的搜索结果: {query}")
            return cached_result

        search_url = f"https://cn.bing.com/search?q={quote(query)}"
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.6099.110 Safari/537.36"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://www.bing.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        try:
            # 使用异步HTTP请求
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(search_url, headers=headers) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        result = self.parse_bing_results(html_content)

                        # 缓存结果
                        self._set_cache(cache_key, result)
                        return result
                    else:
                        error_msg = f"❌ Bing搜索请求失败，状态码: {response.status}"
                        self.logger.error(error_msg)
                        return error_msg

        except asyncio.TimeoutError:
            error_msg = "❌ Bing搜索请求超时，请稍后再试"
            self.logger.error(f"Bing搜索超时: {query}")
            return error_msg
        except Exception as e:
            error_msg = f"❌ Bing搜索请求失败: {str(e)}"
            self.logger.error(f"Bing搜索异常: {e}")
            return error_msg

    def _extract_title_and_link(self, result_element):
        """提取标题和链接的通用方法"""
        title = "无标题"
        link = "无链接"

        title_element = result_element.find("h2")
        if title_element:
            a_tag = title_element.find("a")
            if a_tag and a_tag.get("href"):
                title = a_tag.get_text(strip=True)
                link = a_tag.get("href").strip()
        else:
            a_tag = result_element.find("a", class_="tilk")
            if a_tag and a_tag.get("href"):
                title = a_tag.get_text(strip=True)
                link = a_tag.get("href").strip()
            else:
                a_tag = result_element.find("a", href=True)
                if a_tag:
                    title = a_tag.get_text(strip=True)
                    link = a_tag.get("href").strip()

        return title, link

    def _extract_description(self, result_element):
        """提取描述的通用方法"""
        description = "无描述"
        description_found = False

        paragraph_tags = result_element.find_all("p")
        for p_tag in paragraph_tags:
            classes = p_tag.get("class", [])
            if any("b_lineclamp" in cls for cls in classes):
                description = p_tag.get_text(strip=True)
                description_found = True
                break

        if not description_found:
            caption_div = result_element.find("div", class_="b_caption")
            if caption_div:
                p_tag = caption_div.find("p")
                if p_tag:
                    description = p_tag.get_text(strip=True)
                    description_found = True

        if not description_found:
            attribution_div = result_element.find("div", class_="b_attribution")
            if attribution_div:
                description = attribution_div.get_text(strip=True)
                description_found = True

        return description

    def parse_bing_results(self, html_content: str) -> str:
        """解析 Bing 搜索结果页面"""
        try:
            results = []
            soup = BeautifulSoup(html_content, "lxml")
            search_result_elements = soup.find_all("li", class_="b_algo")

            if not search_result_elements:
                self.logger.warning("未找到Bing搜索结果")
                return "❌ 未找到相关搜索结果"

            max_results = 5  # 限制最多返回 5 个结果
            for index, result_element in enumerate(search_result_elements[:max_results], start=1):
                try:
                    # 提取标题和链接
                    title, link = self._extract_title_and_link(result_element)

                    # 提取描述
                    description = self._extract_description(result_element)

                    # 验证结果有效性
                    if title != "无标题" and link != "无链接":
                        results.append({
                            "index": index,
                            "title": title,
                            "link": link,
                            "description": description
                        })

                except Exception as e:
                    self.logger.error(f"解析第{index}个搜索结果失败: {e}")
                    continue

            if not results:
                return "❌ 搜索结果解析失败，请稍后再试"

            return self._format_search_results(results)

        except Exception as e:
            self.logger.error(f"解析Bing搜索结果失败: {e}")
            return "❌ 搜索结果解析失败，请稍后再试"

    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化搜索结果为美观的文本"""
        if not results:
            return "❌ 未找到相关搜索结果"

        # 构建标题
        header = f"🔍 Bing搜索结果 (共{len(results)}条)\n"
        header += f"📅 搜索时间: {datetime.now().strftime('%H:%M:%S')}\n"
        header += "=" * 40 + "\n\n"

        # 构建结果列表
        result_lines = []
        for result in results:
            result_text = f"📌 {result['index']}. {result['title']}\n"
            result_text += f"🔗 {result['link']}\n"

            # 处理描述，限制长度
            description = result['description']
            if len(description) > 100:
                description = description[:100] + "..."
            result_text += f"📝 {description}\n"

            result_lines.append(result_text)

        # 添加使用提示
        footer = "\n" + "=" * 40 + "\n"
        footer += "💡 点击链接查看详细内容\n"
        footer += "🔄 发送 /bing [关键词] 进行新搜索"

        return header + "\n".join(result_lines) + footer

    def _check_request_limit(self, user_id: int) -> bool:
        """检查用户请求频率限制"""
        current_time = time.time()
        if user_id in self.last_request_time:
            time_diff = current_time - self.last_request_time[user_id]
            if time_diff < self.request_interval:
                return False

        self.last_request_time[user_id] = current_time
        return True

    def _get_remaining_cooldown(self, user_id: int) -> int:
        """获取剩余冷却时间"""
        if user_id not in self.last_request_time:
            return 0

        current_time = time.time()
        time_diff = current_time - self.last_request_time[user_id]
        remaining = self.request_interval - time_diff
        return max(0, int(remaining))

    @bot.group_event()
    @feature_required("Bing搜索", "/bing")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        user_id = event.user_id
        group_id = event.group_id

        # 匹配搜索命令
        match = re.match(r"^/bing\s*(.*)$", raw_message, re.IGNORECASE)
        if not match:
            return

        query = match.group(1).strip()

        # 检查搜索内容
        if not query:
            help_text = (
                "🔍 Bing搜索使用说明\n\n"
                "📝 命令格式：/bing [搜索内容]\n"
                "💡 使用示例：\n"
                "• /bing 李白\n"
                "• /bing Python教程\n"
                "• /bing 今日新闻\n\n"
                "⚠️ 注意：搜索间隔为2秒"
            )
            await self.api.post_group_msg(group_id, text=help_text)
            return

        # 检查请求频率限制
        if not self._check_request_limit(user_id):
            remaining = self._get_remaining_cooldown(user_id)
            await self.api.post_group_msg(
                group_id,
                text=f"⏰ 搜索请求过于频繁，请等待 {remaining} 秒后再试"
            )
            return

        # 验证搜索内容长度
        if len(query) > 100:
            await self.api.post_group_msg(
                group_id,
                text="❌ 搜索内容过长，请控制在100字符以内"
            )
            return

        try:
            # 发送搜索提示
            await self.api.post_group_msg(
                group_id,
                text=f"🔍 正在搜索「{query}」，请稍候..."
            )

            # 执行搜索
            results = await self.fetch_bing_results(query)

            # 发送搜索结果
            await self.api.post_group_msg(group_id, text=results)

            self.logger.info(f"用户 {user_id} 在群 {group_id} 搜索: {query}")

        except Exception as e:
            self.logger.error(f"处理Bing搜索请求失败: {e}")
            await self.api.post_group_msg(
                group_id,
                text="❌ 搜索服务暂时不可用，请稍后再试"
            )

    async def on_load(self):
        """插件加载时的初始化"""
        self.logger.info(f"{self.name} 插件已加载")
        self.logger.info(f"插件版本: {self.version}")
        self.logger.info("Bing搜索功能已启用")

        # 清理缓存和请求记录
        self.cache.clear()
        self.last_request_time.clear()

    async def on_unload(self):
        """插件卸载时的清理"""
        self.cache.clear()
        self.last_request_time.clear()
        self.logger.info(f"{self.name} 插件已卸载")
