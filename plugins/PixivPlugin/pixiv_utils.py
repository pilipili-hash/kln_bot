import logging
from typing import List, Dict, Optional
from pixivpy3 import AppPixivAPI

_log = logging.getLogger(__name__)

async def initialize_pixiv_api(proxy, refresh_token):
    """初始化 Pixiv API 实例"""
    try:
        proxies = {'http': proxy, 'https': proxy} if proxy and isinstance(proxy, str) else None
        pixiv_api = AppPixivAPI(proxies=proxies, timeout=15)

        pixiv_api.auth(refresh_token=refresh_token)
        _log.info("Pixiv API 登录成功")
        return pixiv_api

    except Exception as e:
        _log.error(f"Pixiv API 登录失败: {e}")
        raise ValueError("Pixiv API 登录失败，请检查 refresh_token 是否正确")

async def fetch_illusts(pixiv_api, query: str, page: int = 1, per_page: int = 5) -> List:
    """搜索插画，支持分页"""
    try:
        offset = (page - 1) * per_page
        _log.debug(f"搜索插画: query={query}, page={page}, offset={offset}")

        response = pixiv_api.search_illust(word=query, offset=offset)

        if response and hasattr(response, 'illusts') and response.illusts:
            results = response.illusts[:per_page]
            _log.info(f"搜索成功，返回 {len(results)} 个结果")
            return results
        else:
            _log.warning(f"搜索无结果: {query}")
            return []

    except Exception as e:
        _log.error(f"搜索插画失败: {e}")
        return []

async def fetch_ranking(pixiv_api, mode: str, page: int = 1, per_page: int = 5) -> List:
    """获取排行榜，支持分页"""
    try:
        offset = (page - 1) * per_page
        _log.debug(f"获取榜单: mode={mode}, page={page}, offset={offset}")

        response = pixiv_api.illust_ranking(mode=mode, offset=offset)

        if response and hasattr(response, 'illusts') and response.illusts:
            results = response.illusts[:per_page]
            _log.info(f"榜单获取成功，返回 {len(results)} 个结果")
            return results
        else:
            _log.warning(f"榜单无结果: {mode}")
            return []

    except Exception as e:
        _log.error(f"获取排行榜失败: {e}")
        return []

async def get_illust_detail(pixiv_api, illust_id: int) -> Optional[Dict]:
    """获取插画详细信息"""
    try:
        response = pixiv_api.illust_detail(illust_id)
        if response and hasattr(response, 'illust'):
            return response.illust
        return None
    except Exception as e:
        _log.error(f"获取插画详情失败: {e}")
        return None

async def format_illusts(illusts: List) -> List[Dict]:
    """格式化插画信息为转发消息格式"""
    messages = []

    for i, illust in enumerate(illusts, 1):
        try:
            # 使用代理域名替换原始域名
            image_url = illust.image_urls.medium.replace("i.pximg.net", "i.pixiv.re")

            # 获取基本信息
            title = illust.title or "无标题"
            author = illust.user.name if hasattr(illust.user, 'name') else "未知作者"
            illust_id = illust.id

            # 获取额外信息
            view_count = getattr(illust, 'total_view', 0)
            bookmark_count = getattr(illust, 'total_bookmarks', 0)
            tags = []

            if hasattr(illust, 'tags') and illust.tags:
                tags = [tag.name for tag in illust.tags[:5]]  # 最多显示5个标签

            # 构建内容
            content_parts = [
                f"🎨 {title}",
                f"👤 作者: {author}",
                f"🔗 链接: https://www.pixiv.net/artworks/{illust_id}"
            ]

            if view_count > 0:
                content_parts.append(f"👀 浏览: {view_count:,}")

            if bookmark_count > 0:
                content_parts.append(f"❤️ 收藏: {bookmark_count:,}")

            if tags:
                content_parts.append(f"🏷️ 标签: {', '.join(tags)}")

            content_parts.append(f"[CQ:image,file={image_url}]")

            content = "\n".join(content_parts)

            messages.append({
                "type": "node",
                "data": {
                    "nickname": f"Pixiv 插画 #{i}",
                    "user_id": "0",  # 修复：user_id必须是字符串类型
                    "content": content
                }
            })

        except Exception as e:
            _log.error(f"格式化插画信息失败: {e}")
            # 添加错误信息节点
            messages.append({
                "type": "node",
                "data": {
                    "nickname": f"Pixiv 插画 #{i}",
                    "user_id": "0",  # 修复：user_id必须是字符串类型
                    "content": f"❌ 插画信息获取失败: {str(e)}"
                }
            })

    return messages

def get_search_suggestions(query: str) -> List[str]:
    """获取搜索建议"""
    suggestions = {
        "原神": ["genshin impact", "原神", "甘雨", "雷电将军"],
        "初音未来": ["初音ミク", "hatsune miku", "miku"],
        "东方": ["東方", "touhou", "博丽灵梦"],
        "舰娘": ["艦これ", "kantai collection", "舰队collection"],
        "明日方舟": ["アークナイツ", "arknights", "德克萨斯"],
        "碧蓝航线": ["アズールレーン", "azur lane", "企业"],
    }

    for key, values in suggestions.items():
        if key in query.lower():
            return values

    return []
