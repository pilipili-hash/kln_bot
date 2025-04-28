from pixivpy3 import AppPixivAPI

async def initialize_pixiv_api(proxy, refresh_token):
    """初始化 Pixiv API 实例"""
    proxies = {'http': proxy, 'https': proxy} if proxy and isinstance(proxy, str) else None
    pixiv_api = AppPixivAPI(proxies=proxies, timeout=15)
    try:
        pixiv_api.auth(refresh_token=refresh_token)
        print("Pixiv API 登录成功")
    except Exception as e:
        print(f"Pixiv API 登录失败: {e}")
        raise ValueError("Pixiv API 登录失败，请检查 refresh_token 是否正确")
    return pixiv_api

async def fetch_illusts(pixiv_api, query, page=1):
    """搜索插画，支持分页"""
    try:
        response = pixiv_api.search_illust(word=query, offset=(page - 1) * 5)
        return response.illusts[:5] if response.illusts else []
    except Exception as e:
        print(f"搜索插画失败: {e}")
        return []

async def fetch_ranking(pixiv_api, mode, page=1):
    """获取排行榜，支持分页"""
    try:
        response = pixiv_api.illust_ranking(mode=mode, offset=(page - 1) * 5)
        return response.illusts[:5] if response.illusts else []
    except Exception as e:
        print(f"获取排行榜失败: {e}")
        return []

async def format_illusts(illusts):
    """格式化插画信息"""
    messages = []
    for illust in illusts:
        image_url = illust.image_urls.medium.replace("i.pximg.net", "i.pixiv.re")
        content = (
            f"标题: {illust.title}\n"
            f"作者: {illust.user.name}\n"
            f"链接: https://www.pixiv.net/artworks/{illust.id}\n"
            f"[CQ:image,file={image_url}]"
        )
        messages.append({
            "type": "node",
            "data": {
                "nickname": "Pixiv 插画",
                "user_id": 0,
                "content": content
            }
        })
    return messages
