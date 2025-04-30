import io
import os
import traceback
import base64
import requests
from PIL import Image, ImageDraw, ImageFont
from meme_generator import Image as MemeImage
from typing import Any, Optional
from meme_generator import Meme, TextNumberMismatch, ImageNumberMismatch, ImageAssetMissing, ImageDecodeError, ImageEncodeError, DeserializeError, MemeFeedback, TextOverLength

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
    except Exception as e:
        print(f"获取头像或下载图片失败: {e}")
        return None

async def generate_meme(meme: Meme, image_data: list[io.BytesIO], texts: list[str], options: dict[str, Any], names: list[str]) -> Optional[bytes]:
    """
    生成表情包
    """
    try:
        meme_images: list[MemeImage] = []
        for i, data in enumerate(image_data):
            name = names[i] if i < len(names) else f"image_{i}"  # 使用传入的名称或默认值
            meme_images.append(MemeImage(name=name, data=data.read()))  # 修改为使用传入的 name
        result = meme.generate(images=meme_images, texts=texts, options=options)
        if isinstance(result, TextNumberMismatch):
            error_message = f"文字数量不匹配: 需要 {result.min} ~ {result.max} 个，实际 {result.actual} 个"
            print(f"生成表情包失败: {error_message}")
            return error_message
        if isinstance(result, (ImageNumberMismatch, ImageAssetMissing, ImageDecodeError, ImageEncodeError, DeserializeError, MemeFeedback, TextOverLength)):
            print(f"生成表情包失败: {result}")
            return None
        return result
    except Exception as e:
        print(f"生成表情包失败: {e}")
        traceback.print_exc()
        return None

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
    member_info = await api.get_group_member_info(group_id=group_id, user_id=user_id, no_cache=False)
    card = member_info.get('data', {}).get('card', '').strip()
    nickname = member_info.get('data', {}).get('nickname', '').strip()
    return card if card else nickname if nickname else f"QQ_{user_id}"

async def handle_avatar_and_name(api, group_id: int, user_id: int) -> tuple:
    """
    获取用户头像和名称。
    """
    avatar_data = await get_avatar(user_id)
    if not avatar_data:
        return None, None
    name = await get_member_name(api, group_id, user_id)
    return avatar_data, name
