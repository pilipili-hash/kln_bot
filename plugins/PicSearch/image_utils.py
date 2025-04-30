from PicImageSearch import Network, Yandex, Iqdb, SauceNAO
from utils.config_manager import get_config

async def search_image(image_url: str):
    """使用 PicImageSearch 搜索图片"""
    proxy=get_config("proxy")
    try:
        async with Network(proxies=proxy) as client:
            yandex = Yandex(client=client)
            iqdb = Iqdb(client=client)
            
            saucenao_api_key = get_config("saucenao_api_key")
            saucenao_results = None
            if saucenao_api_key:
                saucenao = SauceNAO(api_key=saucenao_api_key, hide=3, client=client)
                saucenao_resp = await saucenao.search(url=image_url)
                saucenao_results = []
                for i in saucenao_resp.raw:
                    saucenao_results.append({
                        "similarity": i.similarity,
                        "url": i.url,
                        "title": i.title,
                        "thumbnail": i.thumbnail if hasattr(i, 'thumbnail') else None  # 获取缩略图
                    })
            
            yandex_results = []
            try:
                yandex_resp = await yandex.search(url=image_url)
                for i in yandex_resp.raw:
                    yandex_results.append({
                        "similarity": i.similarity,
                        "url": i.url,
                        "title": i.title,
                        "thumbnail": i.thumbnail if hasattr(i, 'thumbnail') else None  # 获取缩略图
                    })
            except Exception as e:
                print(f"Yandex 搜图失败: {e}")
                yandex_results = None
            
            iqdb_resp = await iqdb.search(url=image_url)
            
            iqdb_results = []
            for i in iqdb_resp.raw:
                iqdb_results.append({
                    "similarity": i.similarity,
                    "url": i.url,
                    "title": i.content,
                    "thumbnail": i.thumbnail if hasattr(i, 'thumbnail') else None  # 获取缩略图
                })
            
            results = {"Yandex": yandex_results, "Iqdb": iqdb_results}
            if saucenao_results:
                results["SauceNAO"] = saucenao_results
            else:
                results["SauceNAO"] = None
            return results
    except Exception as e:
        print(f"搜图失败: {e}")
        return None

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
