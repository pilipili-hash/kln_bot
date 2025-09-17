import aiosqlite
import random
import os
import html
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont

DB_PATH = "data.db"

async def init_db() -> None:
    """初始化数据库，创建戳一戳回复表"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS poke_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
    except Exception as e:
        print(f"[ERROR] 初始化戳一戳数据库失败: {e}")

async def add_poke_reply(group_id: int, content: str) -> bool:
    """添加戳一戳回复内容"""
    try:
        if not content.strip():
            return False

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO poke_replies (group_id, content) VALUES (?, ?)",
                (group_id, content.strip())
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"[ERROR] 添加戳一戳回复失败: {e}")
        return False

async def get_random_poke_reply(group_id: int) -> Optional[str]:
    """随机获取指定群组的戳一戳回复内容"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT content FROM poke_replies WHERE group_id = ?",
                (group_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    return random.choice(rows)[0]
                return None
    except Exception as e:
        print(f"[ERROR] 获取随机戳一戳回复失败: {e}")
        return None

async def get_all_poke_replies(group_id: int) -> List[str]:
    """获取指定群组的所有戳一戳回复内容"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT content FROM poke_replies WHERE group_id = ? ORDER BY id",
                (group_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows] if rows else []
    except Exception as e:
        print(f"[ERROR] 获取戳一戳回复列表失败: {e}")
        return []
async def delete_poke_reply(group_id: int, index: int) -> bool:
    """根据序号删除指定群组的戳一戳回复内容"""
    try:
        if index < 1:
            return False

        async with aiosqlite.connect(DB_PATH) as db:
            # 获取所有内容ID，按顺序排列
            async with db.execute(
                "SELECT id FROM poke_replies WHERE group_id = ? ORDER BY id",
                (group_id,)
            ) as cursor:
                rows = await cursor.fetchall()

                if not rows or index > len(rows):
                    return False

                # 获取对应的内容ID
                content_id = rows[index - 1][0]

                # 删除对应内容
                await db.execute("DELETE FROM poke_replies WHERE id = ?", (content_id,))
                await db.commit()
                return True

    except Exception as e:
        print(f"[ERROR] 删除戳一戳回复失败: {e}")
        return False

async def get_reply_count(group_id: int) -> int:
    """获取指定群组的戳一戳回复数量"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM poke_replies WHERE group_id = ?",
                (group_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
    except Exception as e:
        print(f"[ERROR] 获取戳一戳回复数量失败: {e}")
        return 0


async def generate_replies_image(replies: List[str]) -> str:
    """生成包含所有回复内容的图片，支持渲染CQ码图片"""
    try:
        # 字体配置
        font_path = os.path.join("static", "font.ttf")
        font_size = 18
        title_font_size = 24
        padding = 20
        line_height = font_size + 10
        image_width = 600
        max_text_width = image_width - 2 * padding - 60

        # 尝试加载字体，失败时使用默认字体
        try:
            font = ImageFont.truetype(font_path, font_size)
            title_font = ImageFont.truetype(font_path, title_font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # 计算图片高度
        total_height = padding + title_font_size + 30
        for reply in replies:
            if "[CQ:image" in reply:
                total_height += 120  # 图片行高度
            else:
                # 计算文本行数
                text_lines = len(reply) // 40 + 1  # 估算换行
                total_height += line_height * text_lines
            total_height += 10  # 行间距
        total_height += padding

        # 创建图片
        image = Image.new("RGB", (image_width, total_height), "#ffffff")
        draw = ImageDraw.Draw(image)

        # 绘制标题背景
        header_height = padding + title_font_size + 20
        draw.rectangle([0, 0, image_width, header_height], fill="#4a90e2")

        # 绘制标题
        title = f"🎯 戳一戳回复列表 (共{len(replies)}条)"
        try:
            title_bbox = draw.textbbox((0, 0), title, font=title_font)
            title_width = title_bbox[2] - title_bbox[0]
        except:
            title_width = len(title) * title_font_size // 2

        title_x = (image_width - title_width) // 2
        draw.text((title_x, padding), title, fill="white", font=title_font)

        # 绘制内容列表
        y = header_height + 10
        for idx, reply in enumerate(replies, start=1):
            # 计算当前行高度
            if "[CQ:image" in reply:
                row_height = 110
            else:
                text_lines = len(reply) // 50 + 1
                row_height = max(line_height * text_lines, 30)

            # 绘制交替背景色
            bg_color = "#f8f9fa" if idx % 2 == 0 else "#ffffff"
            draw.rectangle(
                (padding, y - 5, image_width - padding, y + row_height),
                fill=bg_color,
                outline="#e9ecef",
                width=1
            )

            # 绘制序号
            serial_number = f"{idx:2d}."
            draw.text((padding + 10, y + 5), serial_number, fill="#6c757d", font=font)

            # 绘制内容
            content_x = padding + 50
            if "[CQ:image" in reply:
                _draw_image_content(draw, reply, content_x, y, max_text_width, font)
            else:
                # 绘制文字内容，支持换行
                _draw_text_content(draw, reply, content_x, y + 5, max_text_width, font)

            y += row_height + 10

        # 绘制底部信息
        footer_text = f"💡 使用 /cyc帮助 查看更多命令"
        draw.text((padding, y), footer_text, fill="#6c757d", font=font)

        # 保存图片
        image_path = f"poke_replies_{hash(str(replies)) % 10000}.png"
        image.save(image_path, "PNG", quality=95)
        return image_path

    except Exception as e:
        print(f"[ERROR] 生成戳一戳回复图片失败: {e}")
        # 返回一个简单的文本图片
        return await _generate_simple_text_image(replies)

def _draw_text_content(draw, text: str, x: int, y: int, max_width: int, font):
    """绘制文本内容，支持自动换行"""
    try:
        words = text
        if len(words) <= 50:
            draw.text((x, y), words, fill="#212529", font=font)
        else:
            # 简单换行处理
            lines = [words[i:i+50] for i in range(0, len(words), 50)]
            for i, line in enumerate(lines[:3]):  # 最多显示3行
                if i == 2 and len(lines) > 3:
                    line = line[:47] + "..."
                draw.text((x, y + i * 20), line, fill="#212529", font=font)
    except Exception:
        draw.text((x, y), text[:50] + "..." if len(text) > 50 else text, fill="#212529", font=font)

def _draw_image_content(draw, reply: str, x: int, y: int, max_width: int, font):
    """绘制图片内容"""
    try:
        # 简化处理，只显示图片标识
        image_url = _extract_image_url(reply)
        if image_url:
            # 截取URL显示部分信息
            url_display = image_url[:30] + "..." if len(image_url) > 30 else image_url
            draw.text((x, y + 5), f"📷 [图片] {url_display}", fill="#28a745", font=font)
        else:
            draw.text((x, y + 5), "📷 [图片]", fill="#6c757d", font=font)
    except Exception:
        draw.text((x, y + 5), "📷 [图片]", fill="#6c757d", font=font)

def _extract_image_url(cq_code: str) -> Optional[str]:
    """从CQ码中提取图片URL"""
    try:
        # 查找url参数
        if "url=" in cq_code:
            start = cq_code.find("url=") + 4
            end = cq_code.find(",", start)
            if end == -1:
                end = cq_code.find("]", start)
            if start != -1 and end != -1:
                return html.unescape(cq_code[start:end])

        # 查找file参数
        if "file=" in cq_code:
            start = cq_code.find("file=") + 5
            end = cq_code.find(",", start)
            if end == -1:
                end = cq_code.find("]", start)
            if start != -1 and end != -1:
                return html.unescape(cq_code[start:end])

        return None
    except Exception:
        return None

async def _generate_simple_text_image(replies: List[str]) -> str:
    """生成简单的文本图片作为备用方案"""
    try:
        image_width, image_height = 600, 400
        image = Image.new("RGB", (image_width, image_height), "#ffffff")
        draw = ImageDraw.Draw(image)

        font = ImageFont.load_default()

        # 绘制标题
        title = f"戳一戳回复列表 (共{len(replies)}条)"
        draw.text((20, 20), title, fill="black", font=font)

        # 绘制回复列表
        y = 60
        for idx, reply in enumerate(replies[:15], 1):  # 最多显示15条
            text = f"{idx}. {reply[:60]}{'...' if len(reply) > 60 else ''}"
            draw.text((20, y), text, fill="black", font=font)
            y += 25

        if len(replies) > 15:
            draw.text((20, y), f"... 还有 {len(replies) - 15} 条回复", fill="gray", font=font)

        image_path = "simple_replies.png"
        image.save(image_path)
        return image_path

    except Exception as e:
        print(f"[ERROR] 生成简单文本图片失败: {e}")
        # 如果连简单图片都生成失败，创建一个最基本的图片
        image = Image.new("RGB", (400, 200), "#ffffff")
        draw = ImageDraw.Draw(image)
        draw.text((20, 20), "戳一戳回复列表生成失败", fill="black")
        image_path = "error_replies.png"
        image.save(image_path)
        return image_path