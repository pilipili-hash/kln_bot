import httpx
import hashlib
from typing import List
from io import BytesIO

async def get_cos_images(num: int) -> List[str]:
    """从API获取cos图片URL列表并修改图片MD5"""
    api_url = f"https://az.bilili.tk/?n={num}&type=json"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                image_urls = [item["pic"] for item in data]
                modified_urls = []
                for url in image_urls:
                    # 修改图片数据的 MD5,避免下载图片
                    md5_hash = hashlib.md5(url.encode('utf-8') + b"random_salt").hexdigest()
                    modified_url = f"{url}?md5={md5_hash[:8]}"
                    modified_urls.append(modified_url)

                return modified_urls
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e}")
    except httpx.TimeoutException as e:
        print(f"Timeout error: {e}")
    except KeyError as e:
        print(f"KeyError: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return []
