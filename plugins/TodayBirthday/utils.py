import httpx
from bs4 import BeautifulSoup
from ncatbot.core.element import Image, Text

async def fetch_birthday_data():
    """
    从 Bangumi.tv 抓取今日生日数据。
    """
    url = "https://bangumi.tv/mono"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # 检查HTTP错误
            return response.text
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred")
        return None
    except httpx.RequestError as e:
        print(f"Request error occurred")
        return None

def parse_birthday_data(html_content: str):
    """
    解析 HTML 内容，提取今日生日角色信息。
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "lxml")
    
    # 提取今日生日角色
    character_list = []
    character_column = soup.find("div", {"id": "columnChlCrtB", "class": "column"})
    if character_column:
        character_div = character_column.find("div", class_="side clearit")
        if character_div:
            character_dl_list = character_div.find_all("dl", class_="side_port")
            for dl in character_dl_list:
                dt = dl.find("dt")
                dd = dl.find("dd")
                if dt and dd:
                    avatar_url = dt.find("span", class_="avatarNeue")["style"].split("url('")[1].split("')")[0]
                    name = dd.find("a").text
                    character_list.append({"name": name, "avatar_url": avatar_url})

    return character_list

async def format_birthday_message(character_list, user_id):
    """
    格式化生日数据为合并转发消息。
    """
    messages = []

    for character in character_list:
        avatar_url = character['avatar_url']
        if not avatar_url.startswith('http'):
            avatar_url = 'https:' + avatar_url  # 确保 URL 以 https: 开头
        messages.append({
            "type": "node",
            "data": {
                "nickname": "今日生日角色",
                "user_id": user_id,
                "content": f"{character['name']}\n[CQ:image,file={avatar_url}]"
            }
        })
    return messages
