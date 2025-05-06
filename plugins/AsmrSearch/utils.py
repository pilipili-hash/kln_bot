import aiohttp
from PIL import Image, ImageDraw, ImageFont
import io

async def fetch_asmr_data(page: int):
    """调用 ASMR API 获取数据"""
    api_url = f"https://api.asmr-200.com/api/works?order=create_date&sort=desc&page={page}&subtitle=0"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None

async def fetch_audio_data(audio_id: int):
    """调用 ASMR API 获取音频数据"""
    api_url = f"https://api.asmr-200.com/api/tracks/{audio_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                return await response.json()
            else:
                return None

def format_asmr_data(data, start: int, end: int):
    """格式化 ASMR 数据为合并转发内容"""
    if not data or "works" not in data:
        return []

    works = data["works"][start:end]  # 根据起始和结束索引获取结果
    messages = []

    for work in works:
        title = work.get("title", "未知标题")
        rate_average = work.get("rate_average_2dp", "未知评分")
        tags = ", ".join(tag["name"] for tag in work.get("tags", []))
        source_id = work.get("id", "未知ID")
        thumbnail_url = work.get("thumbnailCoverUrl", "")

        content = (
            f"标题: {title}\n"
            f"评分: {rate_average}\n"
            f"标签: {tags}\n"
            f"发送:/听 {source_id}\n"
            f"[CQ:image,file={thumbnail_url}]\n" if thumbnail_url else ""
        )

        messages.append({
            "type": "node",
            "data": {
                "nickname": "ASMR搜索",
                "user_id": 1234567,  # 替换为机器人ID
                "content": content
            }
        })

    return messages

def generate_audio_list_image(audio_list):
    """生成音频列表图片"""
    width, height = 800, 600
    background_color = (255, 255, 255)
    font_color = (0, 0, 0)
    font_path = "static/font.ttf"  # 确保字体路径正确
    font_size = 20

    # 创建图片
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        raise FileNotFoundError(f"字体文件未找到: {font_path}")

    # 写入标题
    draw.text((10, 10), "音频列表", fill=font_color, font=font)

    # 写入音频信息
    y_offset = 50
    for idx, audio in enumerate(audio_list, start=1):
        text = f"{idx}: {audio['title']}"
        draw.text((10, y_offset), text, fill=font_color, font=font)
        y_offset += 30

    # 保存到内存
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
