from PIL import Image, ImageDraw, ImageFont
import os

async def generate_qa_image(qa_list: list[dict[str, str]]) -> str:
    """生成包含问答列表的图片，并添加序号。"""
    font_path = os.path.join("static", "font.ttf")  # 确保字体文件存在
    font_size = 22  # 增大字体
    title_font_size = 26 # 标题字体大小
    text_color = (50, 50, 50)  # 颜色
    background_color = (240, 240, 240)  # 浅灰色背景
    line_height = font_size + 8  # 增加行高
    padding = 20  # 增加padding
    image_width = 700  # 增加图片宽度
    
    try:
        font = ImageFont.truetype(font_path, font_size)
        title_font = ImageFont.truetype(font_path, title_font_size)
    except IOError:
        print(f"无法加载字体文件: {font_path}")
        return ""

    # 计算图片高度
    title_height = title_font_size + padding * 2
    image_height = title_height + padding + line_height * len(qa_list) + padding

    # 创建图片
    image = Image.new("RGB", (image_width, image_height), background_color)
    draw = ImageDraw.Draw(image)

    # 绘制标题背景
    draw.rectangle((0, 0, image_width, title_height), fill=(220, 220, 220))

    # 绘制标题
    title_text = "本群问答词条"
    title_width = draw.textlength(title_text, font=title_font)
    title_x = (image_width - title_width) / 2
    draw.text((title_x, padding), title_text, font=title_font, fill=text_color)

    # 绘制文本
    y = title_height + padding
    for index, qa in enumerate(qa_list):
        text = f"{index + 1}. Q: {qa['question']}  A: {qa['answer']}"
        draw.text((padding, y), text, font=font, fill=text_color)
        y += line_height

    # 保存图片
    image_path = "qa_list.png"
    try:
        image.save(image_path)
        return image_path
    except OSError as e:
        print(f"保存图片失败: {e}")
        return ""
