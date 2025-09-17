import aiohttp
import logging
from PIL import Image, ImageDraw, ImageFont
import io

# 设置日志
_log = logging.getLogger(__name__)

async def fetch_asmr_data(page: int):
    """调用 ASMR API 获取数据"""
    api_url = f"https://api.asmr-200.com/api/works?order=create_date&sort=desc&page={page}&subtitle=0"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    _log.info(f"成功获取ASMR数据: 页码{page}")
                    return data
                else:
                    _log.error(f"ASMR API请求失败: 状态码{response.status}")
                    return None
    except Exception as e:
        _log.error(f"获取ASMR数据时出错: {e}")
        return None

async def fetch_audio_data(audio_id: int):
    """调用 ASMR API 获取音频数据"""
    api_url = f"https://api.asmr-200.com/api/tracks/{audio_id}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    _log.info(f"成功获取音频数据: RJID={audio_id}")
                    return data
                else:
                    _log.error(f"音频API请求失败: 状态码{response.status}, RJID={audio_id}")
                    return None
    except Exception as e:
        _log.error(f"获取音频数据时出错: {e}, RJID={audio_id}")
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
        tags = ", ".join(tag["name"] for tag in work.get("tags", [])[:5])  # 限制标签数量
        if len(work.get("tags", [])) > 5:
            tags += "..."
        source_id = work.get("id", "未知ID")
        thumbnail_url = work.get("thumbnailCoverUrl", "")

        # 限制标题长度
        if len(title) > 50:
            title = title[:50] + "..."

        content = (
            f"🎵 {title}\n"
            f"⭐ 评分: {rate_average}\n"
            f"🏷️ 标签: {tags}\n"
            f"🆔 RJID: {source_id}\n"
            f"💡 发送: /听 {source_id}\n"
        )

        # 添加缩略图
        if thumbnail_url:
            content += f"[CQ:image,file={thumbnail_url}]"

        messages.append({
            "type": "node",
            "data": {
                "nickname": "🎵 ASMR搜索",
                "user_id": "1234567",  # 修复：使用字符串类型
                "content": content
            }
        })

    return messages

def generate_audio_list_image(audio_list):
    """生成音频列表图片"""
    try:
        # 动态计算图片高度
        base_height = 120
        item_height = 35
        max_items = min(len(audio_list), 20)  # 最多显示20个
        height = base_height + (max_items * item_height) + 50

        width = 900
        background_color = (248, 249, 250)  # 浅灰背景
        font_color = (33, 37, 41)  # 深灰文字
        header_color = (52, 58, 64)  # 标题颜色
        number_color = (108, 117, 125)  # 序号颜色

        font_path = "static/font.ttf"

        # 创建图片
        image = Image.new("RGB", (width, height), background_color)
        draw = ImageDraw.Draw(image)

        # 尝试加载字体
        try:
            title_font = ImageFont.truetype(font_path, 28)
            content_font = ImageFont.truetype(font_path, 18)
            number_font = ImageFont.truetype(font_path, 16)
        except IOError:
            _log.warning(f"字体文件未找到: {font_path}，使用默认字体")
            title_font = ImageFont.load_default()
            content_font = ImageFont.load_default()
            number_font = ImageFont.load_default()

        # 绘制标题背景
        draw.rectangle([0, 0, width, 80], fill=(255, 255, 255))
        draw.line([0, 80, width, 80], fill=(222, 226, 230), width=2)

        # 写入标题
        title_text = f"🎵 音频列表 (共 {len(audio_list)} 个)"
        draw.text((30, 25), title_text, fill=header_color, font=title_font)

        # 写入提示
        tip_text = "💡 发送数字选择要播放的音频"
        draw.text((30, 55), tip_text, fill=number_color, font=number_font)

        # 写入音频信息
        y_offset = 100
        for idx, audio in enumerate(audio_list[:20], start=1):  # 最多显示20个
            # 序号背景
            number_bg_color = (108, 117, 125) if idx <= 9 else (52, 58, 64)
            draw.rectangle([20, y_offset, 50, y_offset + 25], fill=number_bg_color)

            # 序号
            number_text = str(idx)
            number_bbox = draw.textbbox((0, 0), number_text, font=number_font)
            number_width = number_bbox[2] - number_bbox[0]
            draw.text((35 - number_width // 2, y_offset + 3), number_text, fill=(255, 255, 255), font=number_font)

            # 音频标题（限制长度）
            title = audio['title']
            if len(title) > 60:
                title = title[:60] + "..."

            draw.text((65, y_offset + 3), title, fill=font_color, font=content_font)

            # 分隔线
            if idx < min(len(audio_list), 20):
                draw.line([20, y_offset + 30, width - 20, y_offset + 30], fill=(222, 226, 230), width=1)

            y_offset += item_height

        # 如果有更多音频，显示提示
        if len(audio_list) > 20:
            more_text = f"... 还有 {len(audio_list) - 20} 个音频文件"
            draw.text((30, y_offset + 10), more_text, fill=number_color, font=content_font)

        # 保存到内存
        output = io.BytesIO()
        image.save(output, format="PNG", quality=95, optimize=True)
        output.seek(0)
        return output

    except Exception as e:
        _log.error(f"生成音频列表图片失败: {e}")
        raise
