from PicImageSearch import Network, Yandex, Iqdb, SauceNAO
from utils.config_manager import get_config
from typing import Dict, List, Optional, Any

async def search_image(image_url: str) -> Optional[Dict[str, Any]]:
    """
    使用 PicImageSearch 搜索图片

    Args:
        image_url: 图片URL

    Returns:
        Dict: 搜索结果字典，包含各个引擎的结果
    """
    proxy = get_config("proxy")

    try:
        async with Network(proxies=proxy) as client:
            # 初始化搜索引擎
            yandex = Yandex(client=client)
            iqdb = Iqdb(client=client)

            # 并行执行搜索任务
            import asyncio
            tasks = []

            # SauceNAO搜索（如果有API Key）
            saucenao_api_key = get_config("saucenao_api_key")
            if saucenao_api_key:
                saucenao = SauceNAO(api_key=saucenao_api_key, hide=3, client=client)
                tasks.append(("SauceNAO", _search_saucenao(saucenao, image_url)))

            # Yandex搜索
            tasks.append(("Yandex", _search_yandex(yandex, image_url)))

            # Iqdb搜索
            tasks.append(("Iqdb", _search_iqdb(iqdb, image_url)))

            # 等待所有搜索完成
            results = {}
            for engine_name, task in tasks:
                try:
                    results[engine_name] = await task
                except Exception:
                    results[engine_name] = None

            # 如果没有SauceNAO API Key，添加None结果
            if not saucenao_api_key:
                results["SauceNAO"] = None

            return results

    except Exception:
        return None

async def _search_saucenao(saucenao: SauceNAO, image_url: str) -> List[Dict[str, Any]]:
    """SauceNAO搜索"""
    resp = await saucenao.search(url=image_url)
    results = []

    for item in resp.raw:
        results.append({
            "similarity": item.similarity,
            "url": item.url,
            "title": item.title,
            "thumbnail": getattr(item, 'thumbnail', None)
        })

    return results

async def _search_yandex(yandex: Yandex, image_url: str) -> List[Dict[str, Any]]:
    """Yandex搜索"""
    resp = await yandex.search(url=image_url)
    results = []

    for item in resp.raw:
        thumbnail = getattr(item, 'thumbnail', None)
        if thumbnail == "":
            thumbnail = None

        results.append({
            "similarity": getattr(item, 'similarity', 0),
            "url": item.url,
            "title": item.title,
            "thumbnail": thumbnail
        })

    return results

async def _search_iqdb(iqdb: Iqdb, image_url: str) -> List[Dict[str, Any]]:
    """Iqdb搜索"""
    resp = await iqdb.search(url=image_url)
    results = []

    for item in resp.raw:
        results.append({
            "similarity": item.similarity,
            "url": item.url,
            "title": item.content,
            "thumbnail": getattr(item, 'thumbnail', None)
        })

    return results

async def format_results(results: dict, self_id: int):
    """格式化搜索结果为合并转发消息"""
    messages = []
    
    saucenao_key_missing = False
    if results["SauceNAO"] is None and get_config("saucenao_api_key") is None:
        saucenao_key_missing = True
    
    for engine, result_list in results.items():
        if engine == "Yandex" and result_list is None:
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "搜图结果",
                    "user_id": self_id,
                    "content": "Yandex 搜索暂时不可用，请稍后再试。"
                }
            })
            continue
        
        if engine == "SauceNAO" and saucenao_key_missing:
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "搜图结果",
                    "user_id": self_id,
                    "content": "SauceNAO 未配置 API Key，跳过搜索。"
                }
            })
            continue
            
        if result_list:
            content = f"{engine} 搜索结果:\n"
            for i, result in enumerate(result_list[:3]):  # 显示前3个结果
                content += f"[{i+1}] 相似度: {result['similarity']}\n"
                content += f"   链接: {result['url']}\n"
                content += f"   标题: {result['title']}\n" # 一些引擎可能没有标题
                
                # 添加缩略图
                if result.get('thumbnail'):
                    content += f"[CQ:image,file={result['thumbnail']}]\n"
                else:
                    content += "无缩略图\n"
                    
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "搜图结果",
                    "user_id": self_id,
                    "content": content
                }
            })
        else:
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "搜图结果",
                    "user_id": self_id,
                    "content": f"{engine} 未找到相关结果"
                }
            })
    return messages


def format_results_onebot(results, max_results=5):
    """格式化搜索结果为OneBot格式"""
    if not results:
        return "未找到相关图片"

    formatted_results = []
    result_count = 0

    # 遍历各个搜索引擎的结果
    for engine, result_list in results.items():
        if result_list is None:
            formatted_results.append(f"\n{engine}: 搜索失败")
            continue

        if not result_list:
            formatted_results.append(f"\n{engine}: 无结果")
            continue

        formatted_results.append(f"\n=== {engine} ===")
        for i, result in enumerate(result_list[:3]):  # 每个引擎最多显示3个结果
            if result_count >= max_results:
                break

            title = result.get('title', '未知标题')
            url = result.get('url', '')
            similarity = result.get('similarity', 0)

            formatted_results.append(f"{result_count + 1}. {title}")
            if similarity > 0:
                formatted_results.append(f"   相似度: {similarity:.1f}%")
            if url:
                formatted_results.append(f"   链接: {url}")

            result_count += 1

        if result_count >= max_results:
            break

    if not formatted_results or result_count == 0:
        return "未找到相关图片"

    return "\n".join(formatted_results)


def format_results_forward(results: Dict[str, Any], self_id: int, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    格式化搜索结果为合并转发消息格式，使用兼容的content格式

    Args:
        results: 搜索结果字典
        self_id: 机器人ID
        max_results: 每个引擎最大显示结果数

    Returns:
        List: 合并转发消息列表
    """
    if not results:
        return []

    messages = []

    # 定义引擎顺序和显示名称
    engine_order = ["Yandex", "SauceNAO", "Iqdb"]
    engine_names = {
        "Yandex": "Yandex 搜图",
        "SauceNAO": "SauceNAO 搜图",
        "Iqdb": "Iqdb 搜图"
    }

    for engine in engine_order:
        if engine not in results:
            continue

        result_list = results[engine]
        engine_display_name = engine_names.get(engine, f"{engine} 搜图")

        if result_list is None:
            # 搜索引擎失败
            messages.append({
                "type": "node",
                "data": {
                    "nickname": engine_display_name,
                    "user_id": str(self_id),
                    "content": f"❌ {engine} 搜索暂时不可用"
                }
            })
            continue

        if not result_list:
            # 搜索引擎无结果
            messages.append({
                "type": "node",
                "data": {
                    "nickname": engine_display_name,
                    "user_id": str(self_id),
                    "content": f"⚠️ {engine} 暂无搜索结果"
                }
            })
            continue

        # 创建content格式的消息内容
        content_parts = []

        for result in result_list[:max_results]:
            result_parts = []

            # 添加标题
            title = result.get('title', '未知标题')
            result_parts.append(f"📌 {title}")

            # 添加相似度
            similarity = result.get('similarity', 0)
            if similarity > 0:
                result_parts.append(f"🎯 相似度: {similarity:.1f}%")

            # 添加链接
            url = result.get('url', '')
            if url:
                result_parts.append(f"🔗 {url}")

            # 添加缩略图（使用CQ码）
            thumbnail = result.get('thumbnail')
            if thumbnail:
                if thumbnail.startswith('data:image'):
                    # base64格式
                    base64_data = thumbnail.split(',', 1)[1]
                    result_parts.append(f"[CQ:image,file=base64://{base64_data}]")
                else:
                    # URL格式
                    result_parts.append(f"[CQ:image,file={thumbnail}]")

            content_parts.append("\n".join(result_parts))

        # 创建消息节点
        messages.append({
            "type": "node",
            "data": {
                "nickname": engine_display_name,
                "user_id": str(self_id),
                "content": "\n\n".join(content_parts)
            }
        })

    return messages
