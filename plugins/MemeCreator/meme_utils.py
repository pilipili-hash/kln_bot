import io
import os
import traceback
import base64
import requests
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
from meme_generator import Image as MemeImage
from typing import Any, Optional
from meme_generator import Meme, TextNumberMismatch, ImageNumberMismatch, ImageAssetMissing, ImageDecodeError, ImageEncodeError, DeserializeError, MemeFeedback, TextOverLength

_log = logging.getLogger(__name__)

# 创建线程池用于执行同步的表情包生成
_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="meme_generator")

def cleanup_thread_pool():
    """清理线程池资源"""
    global _thread_pool
    if _thread_pool:
        _log.info("正在关闭表情包生成线程池...")
        _thread_pool.shutdown(wait=True)
        _log.info("表情包生成线程池已关闭")

async def get_avatar(identifier: Any) -> Optional[io.BytesIO]:
    """
    获取QQ头像或从URL下载图片
    """
    try:
        if isinstance(identifier, str) and identifier.startswith("http"):  # 如果是URL
            response = requests.get(identifier, stream=True, timeout=10)
        else:  # 如果是QQ号
            url = f"https://q.qlogo.cn/g?b=qq&nk={identifier}&s=640"
            response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        return io.BytesIO(response.content)
    except Exception:
        return None

def _sync_generate_meme(meme: Meme, meme_images: list[MemeImage], texts: list[str], options: dict[str, Any]):
    """
    同步生成表情包的内部函数，在线程池中执行
    """
    import threading
    try:
        thread_name = threading.current_thread().name
        _log.info(f"[{thread_name}] 开始同步生成表情包: {meme.key}")
        result = meme.generate(images=meme_images, texts=texts, options=options)
        _log.info(f"[{thread_name}] 同步生成表情包完成: {meme.key}")
        return result
    except Exception as e:
        _log.error(f"[{thread_name}] 同步生成表情包异常: {e}")
        raise

async def generate_meme(meme: Meme, image_data: list[io.BytesIO], texts: list[str], options: dict[str, Any], names: list[str]) -> Optional[bytes]:
    """
    异步生成表情包
    """
    try:
        _log.info(f"准备生成表情包: {meme.key}, 图片数量: {len(image_data)}, 文本数量: {len(texts)}")

        # 准备图片数据
        meme_images: list[MemeImage] = []
        for i, data in enumerate(image_data):
            name = names[i] if i < len(names) else f"image_{i}"
            # 读取数据并重置指针
            data.seek(0)
            image_bytes = data.read()
            meme_images.append(MemeImage(name=name, data=image_bytes))

        _log.info(f"图片数据准备完成，开始异步生成表情包: {meme.key}")

        # 在线程池中执行同步的表情包生成
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _thread_pool,
            _sync_generate_meme,
            meme,
            meme_images,
            texts,
            options
        )

        _log.info(f"异步生成表情包完成: {meme.key}")

        # 处理各种错误类型
        if isinstance(result, TextNumberMismatch):
            error_message = f"文字数量不匹配: 需要 {result.min} ~ {result.max} 个，实际 {result.actual} 个"
            return error_message
        if isinstance(result, ImageNumberMismatch):
            error_message = f"图片数量不匹配: 需要 {result.min} ~ {result.max} 张，实际 {result.actual} 张"
            return error_message
        if isinstance(result, ImageAssetMissing):
            return f"图片资源缺失: 表情包所需的资源文件不存在，请稍后重试"
        if isinstance(result, (ImageDecodeError, ImageEncodeError)):
            return f"图片解码错误: 无法解析用户头像或上传的图片，请检查图片格式是否正确"
        if isinstance(result, DeserializeError):
            return f"数据反序列化错误: {result}"
        if isinstance(result, MemeFeedback):
            return f"表情包生成反馈: {result}"
        if isinstance(result, TextOverLength):
            return f"文字过长: {result}"

        return result

    except Exception as e:
        _log.error(f"生成表情包时发生异常: {str(e)}")
        return f"生成表情包时发生异常: {str(e)}"

async def generate_keywords_image(memes: dict) -> io.BytesIO:
    """
    生成表情包关键词图片
    """
    keywords = [
        f"{i + 1}. {', '.join(meme.info.keywords)}"
        for i, meme in enumerate(memes.values())
    ]

    import math
    num_keywords = len(keywords)
    num_cols = int(math.ceil(math.sqrt(num_keywords)))

    columns = [keywords[i::num_cols] for i in range(num_cols)]

    font_path = os.path.join("static", "font.ttf")
    font = ImageFont.truetype(font_path, size=20)
    max_width = 0
    for col in columns:
        for keyword in col:
            width = font.getlength(keyword)
            max_width = max(max_width, width)

    col_width = int(max_width + 20)
    row_height = 30
    margin = 20

    width = num_cols * col_width + 2 * margin
    height = max(len(col) for col in columns) * row_height + 2 * margin

    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)

    x, y = margin, margin
    for col in columns:
        y = margin
        for keyword in col:
            draw.text((x, y), keyword, fill="black", font=font)
            y += row_height
        x += col_width

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output

async def get_member_name(api, group_id: int, user_id: int) -> str:
    """
    获取群成员的名称（优先使用群名片，其次是昵称，最后是默认值）。
    """
    try:
        member_info = await api.get_group_member_info(group_id=group_id, user_id=user_id, no_cache=False)
        if not member_info or 'data' not in member_info:
            return f"QQ_{user_id}"

        data = member_info.get('data', {})
        card = data.get('card') or ''
        nickname = data.get('nickname') or ''

        # 安全地处理可能为None的值
        card = card.strip() if card else ''
        nickname = nickname.strip() if nickname else ''

        return card if card else nickname if nickname else f"QQ_{user_id}"
    except Exception:
        return f"QQ_{user_id}"

async def handle_avatar_and_name(api, group_id: int, user_id: int) -> tuple:
    """
    获取用户头像和名称。
    """
    avatar_data = await get_avatar(user_id)
    if not avatar_data:
        return None, None
    name = await get_member_name(api, group_id, user_id)
    return avatar_data, name
