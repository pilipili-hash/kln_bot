import requests
from bs4 import BeautifulSoup
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text
from urllib.parse import quote
from PluginManager.plugin_manager import feature_required
import re

bot = CompatibleEnrollment

class BingSearch(BasePlugin):
    name = "BingSearch"  # 插件名称
    version = "1.0.0"  # 插件版本

    def fetch_bing_results(self, query: str) -> str:
        """访问 Bing 搜索并解析结果"""
        search_url = f"https://cn.bing.com/search?q={quote(query)}"
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/108.0.5359.95 Safari/537.36"),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Referer": "https://www.bing.com/"
        }

        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()  # 检查 HTTP 状态码
        except requests.RequestException as e:
            return f"HTTP 请求失败: {e}"

        return self.parse_bing_results(response.text)

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
        results = []
        soup = BeautifulSoup(html_content, "lxml")
        search_result_elements = soup.find_all("li", class_="b_algo")

        if not search_result_elements:
            print("未找到搜索结果")
            return "未找到相关信息。"

        max_results = 5  # 限制最多返回 5 个结果
        for index, result_element in enumerate(search_result_elements[:max_results], start=1):
            try:
                # 提取标题和链接
                title, link = self._extract_title_and_link(result_element)

                # 提取描述
                description = self._extract_description(result_element)

                # 记录结果
                results.append({
                    "title": title,
                    "link": link,
                    "description": description
                })

            except Exception as e:
                error_message = f"b_algo 块 {index}: 解析失败 - {e}"
                print(error_message)
                results.append({
                    "title": "解析失败",
                    "link": "解析失败",
                    "description": error_message
                })
                continue

        # 将 results 列表中的字典转换为字符串
        result_strings = [f"标题: {r['title']}\n链接: {r['link']}\n描述: {r['description']}\n" for r in results]
        return "\n".join(result_strings) if result_strings else "未找到相关信息。"

    @bot.group_event()
    @feature_required(feature_name="帮你bing", raw_message_filter="/bing")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        match = re.match(r"^/bing\s*(.*)$", raw_message)  # 使用正则表达式匹配命令
        if match:
            query = match.group(1).strip()
            if not query:
                await self.api.post_group_msg(event.group_id, text="请输入搜索内容，例如：/bing 李白")
                return

            await self.api.post_group_msg(event.group_id, text="正在搜索，请稍候...")
            results = self.fetch_bing_results(query)
            await self.api.post_group_msg(event.group_id, rtf=MessageChain([Text(results)]))

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
