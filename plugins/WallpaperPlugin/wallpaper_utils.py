import logging
from enum import Enum
from typing import Any, Optional, Dict
import aiohttp
from utils.config_manager import get_config

_log = logging.getLogger(__name__)

class WallpaperCategoryType(str, Enum):
    """壁纸分类枚举"""
    landscape = "landscape"  # 1-风景
    girl = "girl"           # 2-美女
    game = "game"           # 3-游戏
    anime = "anime"         # 4-动漫
    mechanics = "mechanics" # 5-汽车
    animal = "animal"       # 6-动物
    drawn = "drawn"         # 7-植物
    boy = "boy"             # 8-美食
    text = "text"           # 9-其他

class WallpaperOrderType(str, Enum):
    """壁纸排序方式枚举"""
    hot = "hot"  # 热门
    new = "new"  # 最新

# API配置
BASE_URL_PC = "https://gpt.bilili.tk:5208/api/wallpaper/wallpaper"
BASE_URL_MOBILE = "https://gpt.bilili.tk:5208/api/wallpaper/vertical"

async def fetch_wallpapers(
    category: WallpaperCategoryType,
    limit: int = 10,  # 每页壁纸数量
    skip: int = 0,  # 跳过的壁纸数量，用于分页
    order: WallpaperOrderType = WallpaperOrderType.hot,  # 排序方式，默认按热度
    mobile: bool = False,  # 是否为手机壁纸
) -> Dict[str, Any]:
    """
    请求壁纸数据

    Args:
        category: 壁纸分类
        limit: 每页壁纸数量
        skip: 跳过的壁纸数量，用于分页
        order: 排序方式
        mobile: 是否为手机壁纸

    Returns:
        包含壁纸数据的字典
    """
    try:
        base_url = BASE_URL_MOBILE if mobile else BASE_URL_PC
        params = {
            "category": category.value,  # 分类
            "limit": limit,  # 每页数量
            "skip": skip,  # 分页偏移量
            "order": order.value,  # 排序方式
        }

        # 获取代理配置
        proxy = get_config("proxy")
        connector = None
        if proxy:
            connector = aiohttp.TCPConnector()

        timeout = aiohttp.ClientTimeout(total=30)  # 30秒超时

        _log.debug(f"请求壁纸: category={category.value}, limit={limit}, skip={skip}, mobile={mobile}")

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            # 设置代理
            proxy_url = proxy if proxy else None

            async with session.get(
                base_url,
                params=params,
                proxy=proxy_url
            ) as response:

                if response.status != 200:
                    _log.error(f"API请求失败，状态码: {response.status}")
                    return {}

                data = await response.json()

                if data.get("code") == 0:
                    result = data.get("res", {})
                    key = "vertical" if mobile else "wallpaper"
                    count = len(result.get(key, []))
                    _log.info(f"成功获取 {count} 张壁纸")
                    return result
                else:
                    _log.warning(f"API返回错误: {data.get('msg', '未知错误')}")
                    return {}

    except aiohttp.ClientError as e:
        _log.error(f"网络请求失败: {e}")
        return {}
    except Exception as e:
        _log.error(f"获取壁纸时发生未知错误: {e}")
        return {}

def get_category_suggestions() -> Dict[str, str]:
    """获取分类建议"""
    return {
        "风景": "自然风光、山川河流、城市景观",
        "美女": "人物写真、时尚摄影、艺术人像",
        "游戏": "游戏截图、游戏角色、游戏场景",
        "动漫": "动漫角色、二次元、卡通插画",
        "汽车": "跑车、摩托车、经典车型",
        "动物": "可爱动物、野生动物、宠物",
        "植物": "花卉、树木、自然植被",
        "美食": "精美料理、甜品、饮品",
        "其他": "抽象艺术、纹理、创意设计"
    }
