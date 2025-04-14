import aiohttp
import datetime
import io
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import base64
import aiosqlite

async def get_hitokoto() -> str:
    """获取一言"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://v1.hitokoto.cn/?c=f&encode=text", timeout=10) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"获取一言失败，状态码: {response.status}")
                    return "获取一言失败，请稍后再试。"
    except Exception as e:
        print(f"获取一言出错: {e}")
        return "获取一言出错，请稍后再试。"

async def get_random_image() -> bytes:
    """获取随机图片"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://t.alcy.cc/ycy", timeout=10) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    print(f"获取随机图片失败，状态码: {response.status}")
                    return b""
    except Exception as e:
        print(f"获取随机图片出错: {e}")
        return b""

def text_with_stroke(draw, xy, text, font, text_color, stroke_color, stroke_width):
    """绘制带描边的文字"""
    for offset_x in range(-stroke_width, stroke_width + 1):
        for offset_y in range(-stroke_width, stroke_width + 1):
            draw.text((xy[0] + offset_x, xy[1] + offset_y), text, font=font, fill=stroke_color)
    draw.text(xy, text, font=font, fill=text_color)

async def generate_signin_image(user_id: int, nickname: str) -> str:
    """生成签到图片"""
    try:
        # 获取数据
        hitokoto = await get_hitokoto()
        image_bytes = await get_random_image()

        if not image_bytes:
            return ""

        # 创建图片
        background = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((800, 600))
        image = Image.new("RGBA", (800, 600), (0, 0, 0, 0))  # 透明画布
        image.paste(background, (0, 0))

        draw = ImageDraw.Draw(image)

        # 加载字体
        font_path = os.path.join("static", "font.ttf")  # 替换为你的字体文件路径
        if not os.path.exists(font_path):
            print(f"字体文件不存在: {font_path}")
            font = ImageFont.truetype("arial.ttf", 24)  # 备用字体
        else:
            font = ImageFont.truetype(font_path, 32)  # 更大的字体
        title_font = ImageFont.truetype(font_path, 48)

        # 半透明边框
        overlay = Image.new("RGBA", (700, 400), (255, 255, 255, 128))  # 半透明白色
        image.paste(overlay, (50, 100), overlay)  # 使用 mask 参数实现半透明

        # 写入文字
        today = datetime.date.today()
        week = today.strftime("%A")
        date_str = today.strftime("%Y-%m-%d")

        text_color = (255, 255, 255)  # 白色文字
        stroke_color = (100, 100, 100)  # 灰色描边
        stroke_width = 1  # 描边宽度

        # 标题
        text_with_stroke(draw, (50, 120), "签到成功", title_font, text_color, stroke_color, stroke_width)

        text_with_stroke(draw, (50, 200), f"用户: {nickname}", font, text_color, stroke_color, stroke_width)
        text_with_stroke(draw, (50, 270), f"日期: {date_str} {week}", font, text_color, stroke_color, stroke_width)

        # 运势
        fortunes = [
            "宜出门，见好运。",
            "忌熬夜，伤身体。",
            "宜学习，有所得。",
            "忌懒惰，无所成。",
            "宜运动，精神佳。",
            "忌久坐，损健康。",
            "宜早睡，养精神。",
            "忌争吵，伤和气。",
            "宜读书，增智慧。",
            "忌拖延，误大事。",
            "宜微笑，心情好。",
            "忌抱怨，添烦恼。",
            "宜喝水，润喉咙。",
            "忌暴饮，伤肠胃。",
            "宜散步，舒心情。",
            "忌久视，护眼睛。",
            "宜倾诉，解烦忧。",
            "忌独处，添孤独。",
            "宜感恩，心态好。",
            "忌嫉妒，伤感情。",
            "宜尝试，增经验。",
            "忌冒险，防风险。",
            "宜规划，定目标。",
            "忌盲目，少成效。",
            "宜助人，得人心。",
            "忌冷漠，失人缘。",
            "宜倾听，增理解。",
            "忌固执，少沟通。",
            "宜整理，清思绪。",
            "忌拖沓，误时机。",
            "宜冥想，清内心。",
            "忌浮躁，少成事。",
            "宜分享，增快乐。",
            "忌独享，失人心。",
            "宜旅行，开眼界。",
            "忌闭门，少见闻。",
            "宜尝新，增乐趣。",
            "忌守旧，失良机。",
            "宜宽容，得人心。",
            "忌计较，添烦恼。",
        ]
        fortune = random.choice(fortunes)
        text_with_stroke(draw, (50, 340), f"今日运势: {fortune}", font, text_color, stroke_color, stroke_width)

        # 自动换行一言
        max_width = 600  # 限制一言的最大宽度
        words = hitokoto.split()
        lines = []
        current_line = ""
        for word in words:
            bbox = draw.textbbox((0, 0), current_line + word, font=font)
            if bbox[2] - bbox[0] < max_width:
                current_line += word + " "
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)

        y_position = 410
        x_position = 50  # 起始 x 坐标
        max_height = 500  # 限制一言的最大高度
        for line in lines:
            bbox = draw.textbbox((0, 0), line.strip(), font=font)
            if y_position + (bbox[3] - bbox[1]) < max_height + 100:  # 确保文字在边框内
                text_with_stroke(draw, (x_position, y_position), line.strip(), font, text_color, stroke_color, stroke_width)
                y_position += 40
            else:
                break  # 停止绘制，防止超出边框

        # 保存图片到内存
        output = io.BytesIO()
        image.save(output, format="PNG")
        image_bytes = output.getvalue()
        base64_str = f"[CQ:image,file=base64://{base64.b64encode(image_bytes).decode()}]"
        return base64_str
    except Exception as e:
        print(f"生成签到图片出错: {e}")
        return ""

async def initialize_database():
    """初始化数据库，创建签到表"""
    async with aiosqlite.connect("data.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sign_in (
                user_id INTEGER,
                group_id INTEGER,
                last_sign_in DATE,
                PRIMARY KEY (user_id, group_id)
            )
        """)
        await db.commit()

async def can_sign_in(user_id: int, group_id: int) -> bool:
    """检查用户今天是否已经签到"""
    async with aiosqlite.connect("data.db") as db:
        async with db.execute("SELECT last_sign_in FROM sign_in WHERE user_id = ? AND group_id = ?", (user_id, group_id)) as cursor:
            result = await cursor.fetchone()
            if result:
                last_sign_in = datetime.datetime.strptime(result[0], "%Y-%m-%d").date()
                return last_sign_in < datetime.date.today()
        return True

async def record_sign_in(user_id: int, group_id: int):
    """记录用户签到"""
    async with aiosqlite.connect("data.db") as db:
        today = datetime.date.today().strftime("%Y-%m-%d")
        await db.execute("""
            INSERT OR REPLACE INTO sign_in (user_id, group_id, last_sign_in)
            VALUES (?, ?, ?)
        """, (user_id, group_id, today))
        await db.commit()
