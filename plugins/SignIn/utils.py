import aiohttp
import datetime
import io
import os
import random
import logging
import math
from typing import Optional, List, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import base64
import aiosqlite

_log = logging.getLogger("SignIn.utils")

async def get_inspirational_quote() -> str:
    """获取励志语录，优先使用本地语录库，网络获取作为补充"""

    # 本地语录库 - 更自然有趣的内容
    local_quotes = [
        "今天也要做个有趣的人呀～",
        "咖啡可以续命，但快乐才是真正的能量源泉",
        "每天进步一点点，就像给生活充电一样",
        "今天的心情由你决定，选择开心吧！",
        "做自己喜欢的事，时间过得特别快",
        "偶尔偷个懒也没关系，毕竟你已经很棒了",
        "生活就像打游戏，每一关都有新的惊喜",
        "今天适合做点让自己开心的小事",
        "别忘了给自己一个大大的拥抱",
        "世界这么大，总有人会欣赏你的独特",
        "今天的烦恼，明天就是小事一桩",
        "保持好奇心，世界会变得更有趣",
        "做个温暖的人，像小太阳一样发光",
        "今天也要记得多喝水，多笑笑哦",
        "每个人都有自己的节奏，不用着急",
        "今天的你比昨天的你更棒一点点",
        "生活需要仪式感，哪怕只是好好吃顿饭",
        "遇到困难时，先深呼吸，然后想想解决办法",
        "今天适合听喜欢的歌，做喜欢的事",
        "别太在意别人的看法，你的感受最重要",
        "今天也要记得夸夸自己哦",
        "慢慢来，比较快。急什么呢～",
        "今天的小确幸是什么呢？",
        "做个有趣的大人，保持童心",
        "今天也要好好爱自己呀",
        "生活虽然平凡，但你很特别",
        "今天适合发现生活中的小美好",
        "别忘了，你是独一无二的存在",
        "今天也要元气满满哦！",
        "慢慢变好，是给自己最好的礼物"
    ]

    # 首先尝试从网络获取
    try:
        async with aiohttp.ClientSession() as session:
            # 尝试获取励志类一言
            async with session.get("https://v1.hitokoto.cn/?c=i&encode=text", timeout=5) as response:
                if response.status == 200:
                    quote = await response.text()
                    if quote and len(quote.strip()) > 0:
                        return quote.strip()
    except Exception as e:
        _log.warning(f"获取网络励志语录失败: {e}")

    # 网络获取失败，使用本地语录
    return random.choice(local_quotes)

async def get_background_image() -> bytes:
    """获取高质量背景图片"""

    # 多个图片源，提高成功率
    image_sources = [
        "https://api.dujin.org/bing/1920.php",  # 必应每日图片
        "https://api.ixiaowai.cn/gqapi/gqapi.php",  # 高清壁纸
        "https://api.ixiaowai.cn/mcapi/mcapi.php",  # 风景图片
        "https://t.alcy.cc/ycy",  # 备用源
    ]

    for source in image_sources:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(source, timeout=10) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        if len(image_data) > 1000:  # 确保图片有效
                            _log.info(f"成功获取背景图片，大小: {len(image_data)} bytes")
                            return image_data
        except Exception as e:
            _log.warning(f"从 {source} 获取图片失败: {e}")
            continue

    _log.error("所有图片源都失败，使用默认背景")
    return b""

def create_default_background() -> Image.Image:
    """创建默认渐变背景"""
    # 创建渐变背景
    width, height = 800, 600
    image = Image.new('RGB', (width, height))

    # 创建渐变效果
    for y in range(height):
        # 从深蓝到浅蓝的渐变
        ratio = y / height
        r = int(30 + (135 - 30) * ratio)  # 30 -> 135
        g = int(60 + (206 - 60) * ratio)  # 60 -> 206
        b = int(120 + (235 - 120) * ratio)  # 120 -> 235

        for x in range(width):
            image.putpixel((x, y), (r, g, b))

    return image

def draw_text_with_shadow(draw: ImageDraw.Draw, xy: Tuple[int, int], text: str,
                         font: ImageFont.FreeTypeFont, text_color: Tuple[int, int, int],
                         shadow_color: Tuple[int, int, int] = (0, 0, 0),
                         shadow_offset: Tuple[int, int] = (2, 2),
                         stroke_width: int = 0, stroke_color: Tuple[int, int, int] = (0, 0, 0)):
    """绘制带阴影和描边的高质量文字"""
    x, y = xy
    shadow_x, shadow_y = shadow_offset

    # 绘制阴影
    if shadow_offset != (0, 0):
        draw.text((x + shadow_x, y + shadow_y), text, font=font, fill=shadow_color)

    # 绘制描边
    if stroke_width > 0:
        for offset_x in range(-stroke_width, stroke_width + 1):
            for offset_y in range(-stroke_width, stroke_width + 1):
                if offset_x != 0 or offset_y != 0:
                    draw.text((x + offset_x, y + offset_y), text, font=font, fill=stroke_color)

    # 绘制主文字
    draw.text(xy, text, font=font, fill=text_color)

def create_rounded_rectangle(size: Tuple[int, int], radius: int,
                           fill_color: Tuple[int, int, int, int]) -> Image.Image:
    """创建圆角矩形"""
    width, height = size
    rectangle = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(rectangle)

    # 绘制圆角矩形
    draw.rounded_rectangle([0, 0, width-1, height-1], radius=radius, fill=fill_color)

    return rectangle

def apply_glass_effect(image: Image.Image, opacity: int = 180) -> Image.Image:
    """应用毛玻璃效果"""
    # 创建模糊效果
    blurred = image.filter(ImageFilter.GaussianBlur(radius=3))

    # 创建半透明遮罩
    overlay = Image.new('RGBA', image.size, (255, 255, 255, opacity))

    # 混合图像
    result = Image.alpha_composite(blurred.convert('RGBA'), overlay)

    return result

def get_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """安全地获取字体"""
    try:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except Exception as e:
        _log.warning(f"加载字体失败 {font_path}: {e}")

    # 尝试系统字体
    try:
        # Windows系统字体
        system_fonts = [
            "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",  # 宋体
        ]

        for font in system_fonts:
            if os.path.exists(font):
                return ImageFont.truetype(font, size)

    except Exception as e:
        _log.warning(f"加载系统字体失败: {e}")

    # 使用默认字体
    try:
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

async def generate_signin_image(user_id: int, nickname: str, streak: int = 0) -> str:
    """生成高质量签到图片"""
    try:
        _log.info(f"开始生成签到图片: 用户{user_id}, 昵称{nickname}, 连续{streak}天")

        # 获取励志语录和背景图片
        quote = await get_inspirational_quote()
        image_bytes = await get_background_image()

        # 创建背景
        if image_bytes:
            try:
                background = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                # 调整背景大小并保持比例
                background = background.resize((800, 600), Image.Resampling.LANCZOS)
            except Exception as e:
                _log.warning(f"处理背景图片失败: {e}")
                background = create_default_background()
        else:
            background = create_default_background()

        # 应用轻微的模糊效果，让文字更突出
        background = background.filter(ImageFilter.GaussianBlur(radius=1))

        # 创建主画布
        canvas = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
        canvas.paste(background, (0, 0))

        # 加载字体
        font_path = os.path.join("static", "font.ttf")
        title_font = get_font(font_path, 48)
        subtitle_font = get_font(font_path, 32)
        content_font = get_font(font_path, 24)
        small_font = get_font(font_path, 20)

        # 创建主要内容区域的毛玻璃背景
        main_card = create_rounded_rectangle((720, 520), 20, (255, 255, 255, 200))
        main_card = apply_glass_effect(main_card, 160)
        canvas.paste(main_card, (40, 40), main_card)

        # 创建绘制对象
        draw = ImageDraw.Draw(canvas)

        # 获取当前时间信息
        now = datetime.datetime.now()
        today = now.date()
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[today.weekday()]
        date_str = today.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M")

        # 定义颜色方案
        primary_color = (45, 55, 72)      # 深蓝灰
        secondary_color = (74, 85, 104)   # 中蓝灰
        accent_color = (56, 178, 172)     # 青色
        success_color = (72, 187, 120)    # 绿色
        text_light = (255, 255, 255)      # 白色
        text_dark = (26, 32, 44)          # 深色

        # 绘制标题区域
        title_y = 70
        draw_text_with_shadow(draw, (60, title_y), "✨ 签到成功", title_font,
                            success_color, (0, 0, 0), (3, 3), 2, primary_color)

        # 绘制用户信息
        user_y = 140
        draw_text_with_shadow(draw, (60, user_y), f"🎯 {nickname}", subtitle_font,
                            primary_color, (255, 255, 255), (2, 2), 1, (200, 200, 200))

        # 绘制日期时间
        date_y = 190
        draw_text_with_shadow(draw, (60, date_y), f"📅 {date_str} {weekday} {time_str}", content_font,
                            secondary_color, (255, 255, 255), (1, 1))

        # 绘制连续签到信息
        if streak > 0:
            streak_y = 240
            streak_text = f"🔥 连续签到 {streak} 天"
            if streak >= 30:
                streak_text += " (签到达人!)"
            elif streak >= 7:
                streak_text += " (坚持不懈!)"
            elif streak >= 3:
                streak_text += " (继续加油!)"

            draw_text_with_shadow(draw, (60, streak_y), streak_text, content_font,
                                accent_color, (255, 255, 255), (1, 1))

        # 获取今日运势
        fortune = get_daily_fortune()
        fortune_y = 290 if streak > 0 else 240
        draw_text_with_shadow(draw, (60, fortune_y), f"✨ 今日提醒: {fortune}", content_font,
                            (138, 43, 226), (255, 255, 255), (1, 1))  # 紫色

        # 创建励志语录区域
        quote_y = 350
        quote_card = create_rounded_rectangle((680, 160), 15, (255, 255, 255, 220))
        canvas.paste(quote_card, (60, quote_y), quote_card)

        # 绘制语录标题
        draw_text_with_shadow(draw, (80, quote_y + 20), "💭 今日分享", content_font,
                            accent_color, (255, 255, 255), (1, 1))

        # 自动换行处理励志语录
        max_width = 600
        wrapped_lines = wrap_text(quote, content_font, max_width, draw)

        quote_text_y = quote_y + 60
        for i, line in enumerate(wrapped_lines[:3]):  # 最多显示3行
            if line.strip():
                draw_text_with_shadow(draw, (80, quote_text_y + i * 30), line.strip(),
                                    small_font, primary_color, (255, 255, 255), (1, 1))

        # 添加装饰性元素
        add_decorative_elements(draw, canvas)

        # 保存图片到内存
        output = io.BytesIO()
        canvas.save(output, format="PNG", quality=95)
        image_bytes = output.getvalue()
        base64_str = f"[CQ:image,file=base64://{base64.b64encode(image_bytes).decode()}]"

        _log.info(f"签到图片生成成功，大小: {len(image_bytes)} bytes")
        return base64_str

    except Exception as e:
        _log.error(f"生成签到图片失败: {e}")
        return ""

def get_daily_fortune() -> str:
    """获取今日运势 - 更有趣自然的版本"""
    fortunes = [
        "今天适合做自己喜欢的事情",
        "会遇到让你开心的小惊喜",
        "今天的你特别有魅力哦",
        "适合尝试新的事物或想法",
        "今天的运气值比平时高一点",
        "会收到来自朋友的好消息",
        "今天适合好好休息放松一下",
        "工作/学习效率会比较高",
        "今天的心情会特别好",
        "适合整理房间或清理思绪",
        "会有意想不到的收获",
        "今天适合多喝水多运动",
        "可能会遇到有趣的人或事",
        "今天的创意和灵感比较丰富",
        "适合和重要的人聊聊天",
        "今天做事情会比较顺利",
        "适合学习新的技能或知识",
        "今天的食欲会特别好",
        "会发现生活中的小美好",
        "今天适合早点休息养精神",
        "可能会收到意外的小礼物",
        "今天的笑容会特别灿烂",
        "适合听音乐或看喜欢的内容",
        "今天做决定的直觉比较准",
        "会有温暖的小瞬间出现"
    ]
    return random.choice(fortunes)

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int,
              draw: ImageDraw.Draw) -> List[str]:
    """智能文本换行"""
    lines = []
    words = text.split()
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font)

        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return lines

def add_decorative_elements(draw: ImageDraw.Draw, canvas: Image.Image):
    """添加装饰性元素"""
    # 添加一些装饰性的小图标或线条

    # 绘制装饰性圆点
    for i in range(5):
        x = 700 + i * 15
        y = 80 + i * 8
        draw.ellipse([x, y, x+6, y+6], fill=(56, 178, 172, 150))

    # 绘制装饰性线条
    draw.line([(60, 130), (740, 130)], fill=(56, 178, 172), width=2)
    draw.line([(60, 530), (740, 530)], fill=(56, 178, 172), width=2)

async def initialize_database():
    """初始化数据库，创建签到表"""
    async with aiosqlite.connect("data.db") as db:
        # 创建签到记录表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sign_in_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                sign_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, group_id, sign_date)
            )
        """)

        # 创建用户统计表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sign_in_stats (
                user_id INTEGER,
                group_id INTEGER,
                total_days INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                max_streak INTEGER DEFAULT 0,
                last_sign_date DATE,
                first_sign_date DATE,
                PRIMARY KEY (user_id, group_id)
            )
        """)

        await db.commit()
        _log.info("签到数据库表初始化完成")

async def can_sign_in(user_id: int, group_id: int) -> bool:
    """检查用户今天是否已经签到"""
    today = datetime.date.today()
    async with aiosqlite.connect("data.db") as db:
        async with db.execute(
            "SELECT COUNT(*) FROM sign_in_records WHERE user_id = ? AND group_id = ? AND sign_date = ?",
            (user_id, group_id, today)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] == 0

async def record_sign_in(user_id: int, group_id: int):
    """记录用户签到并更新统计"""
    today = datetime.date.today()

    async with aiosqlite.connect("data.db") as db:
        # 记录签到
        await db.execute("""
            INSERT OR IGNORE INTO sign_in_records (user_id, group_id, sign_date)
            VALUES (?, ?, ?)
        """, (user_id, group_id, today))

        # 获取当前统计
        async with db.execute(
            "SELECT total_days, current_streak, max_streak, last_sign_date, first_sign_date FROM sign_in_stats WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        ) as cursor:
            stats = await cursor.fetchone()

        if stats:
            total_days, current_streak, max_streak, last_sign_date, first_sign_date = stats
            last_date = datetime.datetime.strptime(last_sign_date, "%Y-%m-%d").date() if last_sign_date else None

            # 计算连续签到
            if last_date and (today - last_date).days == 1:
                current_streak += 1
            elif last_date and (today - last_date).days == 0:
                # 今天已经签到过了，不应该到这里
                return
            else:
                current_streak = 1

            max_streak = max(max_streak, current_streak)
            total_days += 1

            # 更新统计
            await db.execute("""
                UPDATE sign_in_stats
                SET total_days = ?, current_streak = ?, max_streak = ?, last_sign_date = ?
                WHERE user_id = ? AND group_id = ?
            """, (total_days, current_streak, max_streak, today, user_id, group_id))
        else:
            # 首次签到
            await db.execute("""
                INSERT INTO sign_in_stats (user_id, group_id, total_days, current_streak, max_streak, last_sign_date, first_sign_date)
                VALUES (?, ?, 1, 1, 1, ?, ?)
            """, (user_id, group_id, today, today))

        await db.commit()
        _log.info(f"用户 {user_id} 在群 {group_id} 签到成功")

async def get_user_signin_stats(user_id: int, group_id: int) -> Dict[str, Any]:
    """获取用户签到统计"""
    async with aiosqlite.connect("data.db") as db:
        async with db.execute(
            "SELECT total_days, current_streak, max_streak, last_sign_date, first_sign_date FROM sign_in_stats WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            total_days, current_streak, max_streak, last_sign_date, first_sign_date = result

            # 计算从首次签到到现在的天数
            if first_sign_date:
                first_date = datetime.datetime.strptime(first_sign_date, "%Y-%m-%d").date()
                days_since_first = (datetime.date.today() - first_date).days + 1
            else:
                days_since_first = 1

            return {
                'total_days': total_days,
                'current_streak': current_streak,
                'max_streak': max_streak,
                'last_signin': last_sign_date,
                'first_signin': first_sign_date,
                'days_since_first': days_since_first
            }
        else:
            return {
                'total_days': 0,
                'current_streak': 0,
                'max_streak': 0,
                'last_signin': None,
                'first_signin': None,
                'days_since_first': 0
            }

async def get_user_signin_streak(user_id: int, group_id: int) -> int:
    """获取用户连续签到天数"""
    async with aiosqlite.connect("data.db") as db:
        async with db.execute(
            "SELECT current_streak FROM sign_in_stats WHERE user_id = ? AND group_id = ?",
            (user_id, group_id)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def get_group_signin_ranking(group_id: int, limit: int = 10) -> List[Tuple[int, int, int]]:
    """获取群签到排行榜"""
    async with aiosqlite.connect("data.db") as db:
        async with db.execute("""
            SELECT user_id, total_days, current_streak
            FROM sign_in_stats
            WHERE group_id = ?
            ORDER BY total_days DESC, current_streak DESC
            LIMIT ?
        """, (group_id, limit)) as cursor:
            return await cursor.fetchall()
