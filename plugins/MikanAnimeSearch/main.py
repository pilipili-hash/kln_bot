import aiohttp
from bs4 import BeautifulSoup
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from urllib.parse import quote
import re
from PluginManager.plugin_manager import feature_required
from utils.group_forward_msg import send_group_forward_msg_ws
from utils.config_manager import get_config, load_config
bot = CompatibleEnrollment

class MikanAnimeSearch(BasePlugin):
    name = "MikanAnimeSearch"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def search_mikan_anime(self, query: str):
        """访问 Mikanani 搜索并解析结果"""
        base_url = "https://mikanani.me/Home/Search"
        search_url = f"{base_url}?searchstr={quote(query)}"

        proxy = get_config("proxy", "")  # 从配置中获取代理
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(search_url, proxy=proxy, timeout=30) as response:
                    response.raise_for_status()  # 检查 HTTP 状态码
                    return await response.text()
            except aiohttp.ClientError as e:
                if "Timeout" in str(e):
                    await self.api.post_group_msg(self.event.group_id, text="连接超时，请检查代理是否可用")
                    return None
                await self.api.post_group_msg(self.event.group_id, text=f"HTTP 请求失败: {e}")
                return None

    def parse_mikan_results(self, html_content: str):
        """解析 Mikanani 搜索结果页面"""
        results = []
        soup = BeautifulSoup(html_content, "lxml")
        search_result_elements = soup.find_all("tr", class_="js-search-results-row")

        if not search_result_elements:
            return []

        for result_element in search_result_elements[:6]:  # 限制最多返回 6 个结果
            try:
                # 提取番剧信息
                title_element = result_element.find("a", class_="magnet-link-wrap")
                title = title_element.get_text(strip=True) if title_element else "无标题"
                link = "https://mikanani.me" + title_element["href"] if title_element and title_element.has_attr("href") else "无链接"

                magnet_element = result_element.find("a", class_="js-magnet")
                magnet_link_full = magnet_element["data-clipboard-text"] if magnet_element and magnet_element.has_attr("data-clipboard-text") else "无磁力链接"
                magnet_link = magnet_link_full.split('&')[0] if '&' in magnet_link_full else magnet_link_full

                # 格式化结果
                results.append({
                    "title": title,
                    "link": link,
                    "magnet": magnet_link
                })

            except Exception as e:
                print(f"解析失败: {e}")
                continue

        return results

    async def send_comics_forward(self, event: GroupMessage, comics):
        """合并转发漫画信息"""
        messages = []
        for comic in comics:
            content = (
                f"番剧名: {comic['title']}\n"
                f"链接: {comic['link']}\n"
                f"磁力链接: {comic['magnet']}\n"
            )

            messages.append({
                "type": "node",
                "data": {
                    "nickname": "蜜柑计划搜索",
                    "user_id": event.self_id,
                    "content": content
                }
            })

        await send_group_forward_msg_ws(
            group_id=event.group_id,
            content=messages
        )

    @bot.group_event()
    @feature_required(feature_name="番剧搜索", raw_message_filter="/番剧搜索")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        self.event = event
        raw_message = event.raw_message.strip()
        match = re.match(r"^/番剧搜索\s*(.*)$", raw_message)  # 使用正则表达式匹配命令
        if match:
            query = match.group(1).strip()
            if not query:
                await self.api.post_group_msg(event.group_id, text="请输入搜索内容，例如：/番剧搜索 异世界")
                return

            await self.api.post_group_msg(event.group_id, text="正在搜索，请稍候...")
            results = await self.search_mikan_anime(query)
            if results is None:
                return

            parsed_results = self.parse_mikan_results(results)
            if parsed_results:
                await self.send_comics_forward(event, parsed_results)
            else:
                await self.api.post_group_msg(event.group_id, text="未找到相关信息")
