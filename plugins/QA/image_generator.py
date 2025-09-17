from PIL import Image, ImageDraw, ImageFont
import os
import time

async def generate_qa_image(qa_list: list[dict[str, str]]) -> str:
    """生成包含问答列表的图片，并添加序号和匹配类型。"""
    font_path = os.path.join("static", "font.ttf")  # 确保字体文件存在
    font_size = 20  # 字体大小
    title_font_size = 26  # 标题字体大小
    text_color = (50, 50, 50)  # 文字颜色
    exact_color = (0, 120, 0)  # 精确匹配颜色（绿色）
    fuzzy_color = (0, 0, 180)  # 模糊匹配颜色（蓝色）
    background_color = (248, 248, 248)  # 浅灰色背景
    line_height = font_size + 10  # 行高
    padding = 25  # 边距
    image_width = 800  # 图片宽度
    
    try:
        font = ImageFont.truetype(font_path, font_size)
        title_font = ImageFont.truetype(font_path, title_font_size)
    except IOError:
        print(f"无法加载字体文件: {font_path}")
        return ""

    # 计算图片高度（每个QA占用2行：问题行+答案行）
    title_height = title_font_size + padding * 2
    qa_lines = len(qa_list) * 2  # 每个QA占用2行
    image_height = title_height + padding + line_height * qa_lines + padding * 2

    # 创建图片
    image = Image.new("RGB", (image_width, image_height), background_color)
    draw = ImageDraw.Draw(image)

    # 绘制标题背景
    draw.rectangle((0, 0, image_width, title_height), fill=(230, 230, 230))

    # 绘制标题
    title_text = f"📚 本群问答词条 (共{len(qa_list)}条)"
    title_width = draw.textlength(title_text, font=title_font)
    title_x = (image_width - title_width) / 2
    draw.text((title_x, padding), title_text, font=title_font, fill=text_color)

    # 绘制问答内容
    y = title_height + padding
    for index, qa in enumerate(qa_list):
        # 获取匹配类型
        match_type = qa.get('match_type', 'exact')
        type_icon = "🎯" if match_type == "exact" else "🔍"
        type_color = exact_color if match_type == "exact" else fuzzy_color

        # 绘制问题行
        question_text = f"{index + 1}. {type_icon} Q: {qa['question']}"
        draw.text((padding, y), question_text, font=font, fill=type_color)
        y += line_height

        # 绘制答案行（缩进）
        answer_text = f"    A: {qa['answer']}"
        draw.text((padding + 20, y), answer_text, font=font, fill=text_color)
        y += line_height

    # 添加底部说明
    footer_y = y + padding // 2
    footer_text = "🎯 精确匹配  🔍 模糊匹配"
    footer_width = draw.textlength(footer_text, font=font)
    footer_x = (image_width - footer_width) / 2
    draw.text((footer_x, footer_y), footer_text, font=font, fill=(120, 120, 120))

    # 保存图片
    image_path = f"qa_list_{int(time.time())}.png"
    try:
        image.save(image_path)
        return image_path
    except OSError as e:
        print(f"保存QA图片失败: {e}")
        return ""
