import httpx
import hashlib
import logging
from typing import List, Optional
from io import BytesIO

_log = logging.getLogger(__name__)

async def get_cos_images(num: int) -> List[str]:
    """
    从API获取COS图片URL列表并修改图片MD5

    Args:
        num: 请求的图片数量 (1-10)

    Returns:
        图片URL列表，失败时返回空列表
    """
    if not (1 <= num <= 10):
        _log.warning(f"无效的图片数量: {num}")
        return []

    api_url = f"https://az.bilili.tk/?n={num}&type=json"

    try:
        _log.info(f"请求COS图片API: {api_url}")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list):
                _log.error(f"API返回数据格式错误: {type(data)}")
                return []

            if not data:
                _log.warning("API返回空数据")
                return []

            image_urls = []
            for item in data:
                if isinstance(item, dict) and "pic" in item:
                    image_urls.append(item["pic"])
                else:
                    _log.warning(f"跳过无效数据项: {item}")

            if not image_urls:
                _log.warning("未找到有效的图片URL")
                return []

            # 修改图片数据的MD5，避免缓存问题
            modified_urls = []
            for url in image_urls:
                try:
                    # 使用URL和当前时间戳生成唯一MD5
                    import time
                    unique_string = f"{url}_{time.time()}_cos_plugin"
                    md5_hash = hashlib.md5(unique_string.encode('utf-8')).hexdigest()
                    modified_url = f"{url}?md5={md5_hash[:8]}"
                    modified_urls.append(modified_url)
                except Exception as e:
                    _log.warning(f"处理图片URL时出错: {e}, 使用原始URL")
                    modified_urls.append(url)

            _log.info(f"成功获取 {len(modified_urls)} 张COS图片")
            return modified_urls

    except httpx.HTTPStatusError as e:
        _log.error(f"HTTP请求错误: {e.response.status_code} - {e}")
        return []
    except httpx.TimeoutException as e:
        _log.error(f"请求超时: {e}")
        return []
    except httpx.RequestError as e:
        _log.error(f"网络请求错误: {e}")
        return []
    except ValueError as e:
        _log.error(f"JSON解析错误: {e}")
        return []
    except KeyError as e:
        _log.error(f"数据字段缺失: {e}")
        return []
    except Exception as e:
        _log.error(f"获取COS图片时发生未知错误: {e}")
        return []
