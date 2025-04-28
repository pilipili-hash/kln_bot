from enum import Enum
from typing import Any, Optional
import aiohttp  # 用于 HTTP 请求

class WallpaperCategoryType(str, Enum):
    girl = "girl"
    animal = "animal"
    landscape = "landscape"
    anime = "anime"
    drawn = "drawn"
    mechanics = "mechanics"
    boy = "boy"
    game = "game"
    text = "text"

class WallpaperOrderType(str, Enum):
    hot = "hot"
    new = "new"

BASE_URL_PC = "https://hibi.moecube.com/api/wallpaper/wallpaper"
BASE_URL_MOBILE = "https://hibi.moecube.com/api/wallpaper/vertical"

async def fetch_wallpapers(
    category: WallpaperCategoryType,
    limit: int = 10,  # 每页壁纸数量
    skip: int = 0,  # 跳过的壁纸数量，用于分页
    order: WallpaperOrderType = WallpaperOrderType.hot,  # 排序方式，默认按热度
    mobile: bool = False,  # 是否为手机壁纸
) -> dict[str, Any]:
    """请求壁纸数据"""
    base_url = BASE_URL_MOBILE if mobile else BASE_URL_PC
    params = {
        "category": category.value,  # 分类
        "limit": limit,  # 每页数量
        "skip": skip,  # 分页偏移量
        "order": order.value,  # 排序方式
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(base_url, params=params) as response:
            data = await response.json()
            if data.get("code") == 0:
                return data.get("res", {})
            return {}
