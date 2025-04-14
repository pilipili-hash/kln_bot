import aiohttp
from bs4 import BeautifulSoup
from utils.config_manager import get_config  # 导入配置加载工具

async def fetch_steam_games(query: str):
    """
    调用 Steam 搜索页面并解析结果。
    """
    url = f"https://store.steampowered.com/search/?term={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    }

    # 异步加载代理配置
    proxy = get_config("proxy","")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, proxy=proxy) as response:  # 使用代理
                if response.status == 200:
                    html = await response.text()
                    return parse_steam_results(html)
                else:
                    print(f"请求失败，状态码: {response.status}")
                    return []
        except Exception as e:
            print(f"请求 Steam 搜索页面时出错: {e}")
            return []

def parse_steam_results(html: str):
    """
    解析 Steam 搜索结果页面。
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.find_all("a", class_="search_result_row")[:5]:  # 限制最多返回 5 个结果
        try:
            title = row.find("span", class_="title").get_text(strip=True)
            release_date = row.find("div", class_="search_released").get_text(strip=True)
            review_summary = row.find("span", class_="search_review_summary")
            review_summary = review_summary["data-tooltip-html"].split("<br>")[0] if review_summary else "无评价"
            price = row.find("div", class_="discount_final_price")
            price = price.get_text(strip=True) if price else "无价格信息"
            link = row["href"]
            image_url = row.find("img")["src"]

            results.append({
                "title": title,
                "release_date": release_date,
                "review_summary": review_summary,
                "price": price,
                "link": link,
                "image_url": image_url
            })
        except Exception as e:
            print(f"解析游戏信息时出错: {e}")
            continue
    return results
