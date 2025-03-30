import aiosqlite
import random
from PIL import Image, ImageDraw, ImageFont  # 添加依赖
import os
import html  # 用于处理实体转义
DB_PATH = "data.db"  # 数据库文件路径

async def init_db():
    """初始化数据库，创建表"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS poke_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                content TEXT NOT NULL
            )
        """)
        await db.commit()

async def add_poke_reply(group_id: int, content: str):
    """添加戳一戳回复内容"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO poke_replies (group_id, content) VALUES (?, ?)", (group_id, content))
        await db.commit()

async def get_random_poke_reply(group_id: int) -> str:
    """随机获取指定群组的戳一戳回复内容"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT content FROM poke_replies WHERE group_id = ?", (group_id,)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                return random.choice(rows)[0]  # 随机选择一条内容
            return None
# ...existing code...

async def get_all_poke_replies(group_id: int) -> list[str]:
    """获取指定群组的所有戳一戳回复内容"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT content FROM poke_replies WHERE group_id = ?", (group_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows] if rows else []
        
        
async def delete_poke_reply(group_id: int, index: int) -> bool:
    """根据序号删除指定群组的戳一戳回复内容"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 获取所有内容
        async with db.execute("SELECT id FROM poke_replies WHERE group_id = ?", (group_id,)) as cursor:
            rows = await cursor.fetchall()
            if not rows or index < 1 or index > len(rows):
                return False  # 序号无效
            # 获取对应的内容 ID
            content_id = rows[index - 1][0]
            # 删除对应内容
            await db.execute("DELETE FROM poke_replies WHERE id = ?", (content_id,))
            await db.commit()
            return True        


async def generate_replies_image(replies: list[str]) -> str:
    """生成包含所有回复内容的图片，支持渲染 CQ:image 图片"""
    font_path = os.path.join("static", "font.ttf")
    font_size = 18
    title_font_size = 24
    padding = 20
    line_height = font_size + 10
    image_width = 500
    max_text_width = image_width - 2 * padding - 50

    font = ImageFont.truetype(font_path, font_size)
    title_font = ImageFont.truetype(font_path, title_font_size)

    # 计算图片高度
    total_height = padding + title_font_size + 20
    for reply in replies:
        if "[CQ:image" in reply:
            total_height += 100
        else:
            total_height += line_height
        total_height += 5
    total_height += padding

    # 创建图片
    image = Image.new("RGB", (image_width, total_height), "#ffffff")  # 使用RGB，白色背景
    draw = ImageDraw.Draw(image)

    # 绘制标题背景
    draw.rectangle([0, 0, image_width, padding + title_font_size + 10], fill="#f0f0f0")
    # 绘制标题
    title = "本群戳一戳"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (image_width - title_width) // 2
    draw.text((title_x, padding), title, fill="black", font=title_font)

    # 绘制表格内容
    y = padding + title_font_size + 20
    for idx, reply in enumerate(replies, start=1):
        row_top = y - 5
        row_bottom = y + (90 if "[CQ:image" in reply else line_height)

        # 绘制交替背景色
        bg_color = "#f9f9f9" if idx % 2 == 0 else "#ffffff"  # 交替背景色
        draw.rectangle(
            (padding, row_top, image_width - padding, row_bottom),
            fill=bg_color
        )

        # 绘制序号
        serial_number = f"{idx}."
        draw.text((padding + 10, y), serial_number, fill="black", font=font)

        # 绘制内容
        if "[CQ:image" in reply:
            image_url = None  # 初始化 image_url
            # 提取图片 URL
            start = reply.find("url=") + len("url=")
            end = reply.find(",", start)
            if end == -1:
                end = reply.find("]", start)
            if start != -1 and end != -1:
                image_url = reply[start:end]
            
            if image_url:
                image_url = html.unescape(image_url)

                # 下载图片
                try:
                    from io import BytesIO
                    import requests
                    response = requests.get(image_url)
                    img = Image.open(BytesIO(response.content))
                    img = img.convert("RGBA")  # 转换为RGB

                    # 动态调整图片大小
                    max_height = 90
                    img.thumbnail((max_text_width, max_height))
                    img_width, img_height = img.size

                    # 垂直居中对齐
                    vertical_offset = (line_height - img_height) // 2 if img_height < line_height else 0
                    image.paste(img, (padding + 40, y + vertical_offset))
                    y += max(img_height, line_height) + 10
                except Exception as e:
                    draw.text((padding + 40, y), f"图片加载失败: {image_url}", fill="red", font=font)
                    y += line_height
            else:
                draw.text((padding + 40, y), "图片 URL 提取失败", fill="red", font=font)
                y += line_height
        else:
            # 绘制文字
            draw.text((padding + 40, y), reply, fill="black", font=font)
            y += line_height

        y += 5

    # 保存图片
    image_path = "replies.png"
    image.save(image_path)
    return image_path