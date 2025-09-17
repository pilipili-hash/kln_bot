import aiohttp
import asyncio
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

# 延迟导入config_manager以避免循环导入
def get_config(key: str, default: str = "") -> str:
    """获取配置，如果导入失败则返回默认值"""
    try:
        from utils.config_manager import get_config as _get_config
        return _get_config(key, default)
    except Exception:
        return default

# 设置日志
_log = logging.getLogger(__name__)

async def fetch_steam_games(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    调用Steam搜索页面并解析结果

    Args:
        query: 搜索关键词
        max_results: 最大结果数量

    Returns:
        游戏信息列表
    """
    if not query or not query.strip():
        _log.warning("搜索关键词为空")
        return []

    # 构建搜索URL，添加更多参数优化搜索
    url = f"https://store.steampowered.com/search/?term={query.strip()}&category1=998"

    # 优化请求头，模拟真实浏览器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # 获取代理配置
    proxy = get_config("proxy", "")

    # 设置超时
    timeout = aiohttp.ClientTimeout(total=15, connect=5)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            _log.info(f"开始请求Steam搜索: {query}")

            async with session.get(url, headers=headers, proxy=proxy if proxy else None) as response:
                if response.status == 200:
                    html = await response.text()
                    results = parse_steam_results(html, max_results)
                    _log.info(f"Steam搜索完成: {query}, 找到 {len(results)} 个结果")
                    return results
                else:
                    _log.error(f"Steam搜索请求失败，状态码: {response.status}")
                    return []

    except asyncio.TimeoutError:
        _log.error(f"Steam搜索请求超时: {query}")
        return []
    except Exception as e:
        _log.error(f"Steam搜索请求异常: {query}, 错误: {e}")
        return []

def parse_steam_results(html: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    解析Steam搜索结果页面

    Args:
        html: HTML页面内容
        max_results: 最大结果数量

    Returns:
        解析后的游戏信息列表
    """
    if not html or not html.strip():
        _log.warning("HTML内容为空")
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # 查找搜索结果行
        search_rows = soup.find_all("a", class_="search_result_row")
        if not search_rows:
            _log.warning("未找到搜索结果行")
            return []

        _log.info(f"找到 {len(search_rows)} 个搜索结果行")

        for i, row in enumerate(search_rows[:max_results]):
            try:
                game_info = _parse_single_game(row)
                if game_info:
                    results.append(game_info)
                    _log.debug(f"成功解析游戏 {i+1}: {game_info.get('title', 'Unknown')}")
                else:
                    _log.warning(f"解析游戏 {i+1} 失败")

            except Exception as e:
                _log.error(f"解析第 {i+1} 个游戏时出错: {e}")
                continue

        _log.info(f"成功解析 {len(results)} 个游戏")
        return results

    except Exception as e:
        _log.error(f"解析HTML时发生错误: {e}")
        return []

def _parse_single_game(row) -> Optional[Dict[str, Any]]:
    """
    解析单个游戏信息

    Args:
        row: BeautifulSoup游戏行元素

    Returns:
        游戏信息字典或None
    """
    try:
        game_info = {}

        # 游戏标题
        title_elem = row.find("span", class_="title")
        if title_elem:
            game_info["title"] = title_elem.get_text(strip=True)
        else:
            _log.warning("未找到游戏标题")
            return None

        # 发布日期
        release_elem = row.find("div", class_="search_released")
        if release_elem:
            release_text = release_elem.get_text(strip=True)
            game_info["release_date"] = release_text if release_text else "未知发布日期"
        else:
            game_info["release_date"] = "未知发布日期"

        # 评价信息
        review_elem = row.find("span", class_="search_review_summary")
        if review_elem and review_elem.get("data-tooltip-html"):
            try:
                tooltip_html = review_elem["data-tooltip-html"]
                # 提取评价文本，去除HTML标签
                review_soup = BeautifulSoup(tooltip_html, "html.parser")
                review_text = review_soup.get_text().split('\n')[0].strip()
                game_info["review_summary"] = review_text if review_text else "无评价"
            except:
                game_info["review_summary"] = "无评价"
        else:
            game_info["review_summary"] = "无评价"

        # 价格信息
        price_elem = row.find("div", class_="discount_final_price")
        if not price_elem:
            price_elem = row.find("div", class_="search_price")

        if price_elem:
            price_text = price_elem.get_text(strip=True)
            if price_text:
                # 处理特殊价格情况
                if "免费" in price_text or "Free" in price_text.upper():
                    game_info["price"] = "免费开玩"
                else:
                    game_info["price"] = price_text
            else:
                game_info["price"] = "价格未知"
        else:
            game_info["price"] = "价格未知"

        # Steam链接
        if row.get("href"):
            game_info["link"] = row["href"]
        else:
            _log.warning(f"游戏 {game_info['title']} 缺少链接")
            game_info["link"] = ""

        # 游戏封面图片
        img_elem = row.find("img")
        if img_elem and img_elem.get("src"):
            game_info["image_url"] = img_elem["src"]
        else:
            _log.warning(f"游戏 {game_info['title']} 缺少封面图片")
            game_info["image_url"] = ""

        return game_info

    except Exception as e:
        _log.error(f"解析单个游戏信息时出错: {e}")
        return None

def _clean_text(text: str) -> str:
    """清理文本，移除多余的空白字符"""
    if not text:
        return ""
    return " ".join(text.split())
