import httpx
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from ncatbot.core.element import Image, Text

# 设置日志
_log = logging.getLogger("TodayBirthday.utils")

class BirthdayCache:
    """生日数据缓存管理器"""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_hits = 0
        self._network_requests = 0

    def get_today_birthday(self) -> Optional[List[Dict[str, Any]]]:
        """获取今日生日缓存数据"""
        today = datetime.now().strftime("%Y-%m-%d")

        # 检查缓存是否有效（当天的数据且不超过6小时）
        if (self._cache_time and
            self._cache_time.date() == datetime.now().date() and
            datetime.now() - self._cache_time < timedelta(hours=6) and
            today in self._cache):

            self._cache_hits += 1
            _log.info("使用缓存的今日生日数据")
            return self._cache[today]

        return None

    def set_today_birthday(self, data: List[Dict[str, Any]]):
        """设置今日生日缓存数据"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._cache[today] = data
        self._cache_time = datetime.now()
        _log.info(f"缓存今日生日数据，共 {len(data)} 个角色")

    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._cache_hits + self._network_requests
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        today = datetime.now().strftime("%Y-%m-%d")
        cache_valid = (self._cache_time and
                      self._cache_time.date() == datetime.now().date() and
                      datetime.now() - self._cache_time < timedelta(hours=6))

        return {
            "cache_hits": self._cache_hits,
            "network_requests": self._network_requests,
            "hit_rate": hit_rate,
            "last_update": self._cache_time.strftime("%Y-%m-%d %H:%M:%S") if self._cache_time else "从未更新",
            "cache_valid": cache_valid,
            "today_count": len(self._cache.get(today, []))
        }

    def increment_network_requests(self):
        """增加网络请求计数"""
        self._network_requests += 1

async def fetch_birthday_data() -> Optional[str]:
    """从 Bangumi.tv 抓取今日生日数据"""
    url = "https://bangumi.tv/mono"

    try:
        _log.info(f"开始请求生日数据: {url}")

        # 配置HTTP客户端
        timeout = httpx.Timeout(30.0, connect=10.0)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

            _log.info(f"成功获取生日数据，响应大小: {len(response.text)} 字符")
            return response.text

    except httpx.TimeoutException:
        _log.error("请求超时")
        return None
    except httpx.HTTPStatusError as e:
        _log.error(f"HTTP错误: {e.response.status_code}")
        return None
    except httpx.RequestError as e:
        _log.error(f"请求错误: {e}")
        return None
    except Exception as e:
        _log.error(f"未知错误: {e}")
        return None

def parse_birthday_data(html_content: str) -> List[Dict[str, Any]]:
    """解析 HTML 内容，提取今日生日角色信息"""
    if not html_content:
        _log.warning("HTML内容为空")
        return []

    try:
        soup = BeautifulSoup(html_content, "lxml")
        character_list = []

        # 尝试多种方式来提取今日生日角色
        character_dl_list = []

        # 方法1: 原始选择器
        character_column = soup.find("div", {"id": "columnChlCrtB", "class": "column"})
        if character_column:
            character_div = character_column.find("div", class_="side clearit")
            if character_div:
                character_dl_list = character_div.find_all("dl", class_="side_port")


        # 方法2: 只通过ID查找
        if not character_dl_list:
            character_column = soup.find("div", {"id": "columnChlCrtB"})
            if character_column:
                character_dl_list = character_column.find_all("dl", class_="side_port")


        # 方法3: 直接查找所有side_port元素
        if not character_dl_list:
            character_dl_list = soup.find_all("dl", class_="side_port")


        # 方法4: 查找包含生日信息的其他可能结构
        if not character_dl_list:
            # 尝试查找其他可能的角色容器
            possible_containers = [
                soup.find("div", class_="column"),
                soup.find("div", {"id": "columnChlCrtB"}),
                soup.find("section", class_="character"),
                soup.find("div", class_="character-list")
            ]

            for container in possible_containers:
                if container:
                    # 查找各种可能的角色元素
                    possible_elements = [
                        container.find_all("dl"),
                        container.find_all("div", class_="character"),
                        container.find_all("li", class_="character"),
                        container.find_all("div", class_="item")
                    ]

                    for elements in possible_elements:
                        if elements:
                            character_dl_list = elements

                            break
                    if character_dl_list:
                        break

        if not character_dl_list:
            _log.warning("所有方法都未找到角色列表，可能网站结构已变化")
            # 输出HTML结构用于调试
            _log.info("尝试分析HTML结构...")

            # 查找所有可能包含"生日"、"birthday"、"今日"等关键词的元素
            keywords = ["生日", "birthday", "今日", "today", "character", "角色"]
            for keyword in keywords:
                elements = soup.find_all(text=lambda text: text and keyword in text.lower())
                if elements:

                    for elem in elements[:3]:  # 只显示前3个
                        parent = elem.parent if elem.parent else None
                        if parent:
                            _log.info(f"  父元素: {parent.name}, class: {parent.get('class')}, id: {parent.get('id')}")

            # 查找所有div元素的class和id
            divs = soup.find_all("div")
            _log.info(f"页面共有 {len(divs)} 个div元素")

            # 查找可能的角色相关元素
            possible_selectors = [
                "div[class*='character']",
                "div[class*='birthday']",
                "div[class*='today']",
                "section[class*='character']",
                "ul[class*='character']",
                "li[class*='character']"
            ]

            for selector in possible_selectors:
                try:
                    elements = soup.select(selector)
                    if elements:
                        character_dl_list = elements
                        break
                except:
                    continue

            if not character_dl_list:
                return []
        _log.info(f"找到 {len(character_dl_list)} 个角色元素")

        for i, element in enumerate(character_dl_list):
            try:
                name = None
                avatar_url = None

                # 尝试多种方式提取角色信息
                if element.name == "dl":
                    # 原始的dl结构
                    dt = element.find("dt")
                    dd = element.find("dd")

                    if dt and dd:
                        # 提取头像URL
                        avatar_span = dt.find("span", class_="avatarNeue")
                        if avatar_span and "style" in avatar_span.attrs:
                            style = avatar_span["style"]
                            if "url('" in style:
                                avatar_url = style.split("url('")[1].split("')")[0]

                        # 提取角色名称
                        name_link = dd.find("a")
                        if name_link:
                            name = name_link.text.strip()

                # 如果dl结构解析失败，尝试其他结构
                if not name or not avatar_url:
                    # 尝试查找img标签
                    img_tag = element.find("img")
                    if img_tag:
                        avatar_url = img_tag.get("src") or img_tag.get("data-src")
                        name = img_tag.get("alt") or img_tag.get("title")

                    # 尝试查找链接
                    if not name:
                        link_tag = element.find("a")
                        if link_tag:
                            name = link_tag.text.strip()

                    # 尝试查找背景图片
                    if not avatar_url:
                        style_elements = element.find_all(attrs={"style": True})
                        for style_elem in style_elements:
                            style = style_elem.get("style", "")
                            if "background-image" in style and "url(" in style:
                                try:
                                    avatar_url = style.split("url(")[1].split(")")[0].strip("'\"")
                                    break
                                except:
                                    continue

                # 验证提取的数据
                if not name:
                    _log.warning(f"元素 {i+1} 无法提取角色名称")
                    continue

                if not avatar_url:
                    _log.warning(f"元素 {i+1} 无法提取头像URL，使用默认头像")
                    avatar_url = "https://bangumi.tv/img/no_icon_subject.png"

                # 确保URL格式正确
                if avatar_url.startswith('//'):
                    avatar_url = 'https:' + avatar_url
                elif avatar_url.startswith('/'):
                    avatar_url = 'https://bangumi.tv' + avatar_url
                elif not avatar_url.startswith('http'):
                    avatar_url = 'https://bangumi.tv/' + avatar_url

                character_list.append({
                    "name": name,
                    "avatar_url": avatar_url
                })

            except Exception as e:
                _log.error(f"解析元素 {i+1} 时出错: {e}")
                continue

        _log.info(f"成功解析 {len(character_list)} 个生日角色")
        return character_list

    except Exception as e:
        _log.error(f"解析HTML内容失败: {e}")
        return []

async def format_birthday_message(character_list: List[Dict[str, Any]], user_id: int) -> List[Dict[str, Any]]:
    """格式化生日数据为合并转发消息，支持缩略图"""
    try:
        messages = []

        # 添加标题消息
        today = datetime.now().strftime("%Y年%m月%d日")
        title_message = {
            "type": "node",
            "data": {
                "nickname": "今日生日",
                "user_id": str(user_id),
                "content": f"🎂 {today} 今日生日角色\n📊 共找到 {len(character_list)} 个角色过生日"
            }
        }
        messages.append(title_message)

        # 限制角色数量避免消息过大，但保持较高的显示数量
        max_characters = min(len(character_list), 30)

        # 添加角色消息，每个角色都带缩略图
        for i, character in enumerate(character_list[:max_characters], 1):
            try:
                avatar_url = character['avatar_url']
                name = character['name']

                # 确保URL格式正确
                if not avatar_url.startswith('http'):
                    if avatar_url.startswith('//'):
                        avatar_url = 'https:' + avatar_url
                    else:
                        avatar_url = 'https://bangumi.tv' + avatar_url

                # 创建带缩略图的消息内容
                content = f"🎉 {i}. {name}"

                # 添加缩略图
                if avatar_url and ('bangumi.tv' in avatar_url or 'lain.bgm.tv' in avatar_url):
                    content += f"\n[CQ:image,file={avatar_url}]"

                messages.append({
                    "type": "node",
                    "data": {
                        "nickname": f"生日角色 #{i}",
                        "user_id": str(user_id),
                        "content": content
                    }
                })

            except Exception as e:
                _log.error(f"格式化角色 {i} 消息失败: {e}")
                # 添加纯文本消息作为备选
                messages.append({
                    "type": "node",
                    "data": {
                        "nickname": f"生日角色 #{i}",
                        "user_id": str(user_id),
                        "content": f"🎉 {i}. {character.get('name', '未知角色')}"
                    }
                })

        # 如果有更多角色，添加提示
        if len(character_list) > max_characters:
            remaining = len(character_list) - max_characters
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "更多角色",
                    "user_id": str(user_id),
                    "content": f"📝 还有 {remaining} 个角色未显示...\n💡 发送 '/今日生日统计' 查看完整数据"
                }
            })

        # 添加尾部消息
        footer_message = {
            "type": "node",
            "data": {
                "nickname": "数据来源",
                "user_id": str(user_id),
                "content": "🎊 生日快乐！\n📊 数据来源：Bangumi.tv\n💡 发送 '/今日生日帮助' 查看更多功能"
            }
        }
        messages.append(footer_message)


        return messages

    except Exception as e:
        _log.error(f"格式化生日消息失败: {e}")
        # 返回简化的错误消息
        return [{
            "type": "node",
            "data": {
                "nickname": "错误",
                "user_id": str(user_id),
                "content": "❌ 格式化消息时发生错误"
            }
        }]
