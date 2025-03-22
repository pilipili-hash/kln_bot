import sqlite3
import json
import tempfile
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def load_menu_data(group_id, db_path="data.db"):
    """从数据库中加载菜单数据"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT menu_item FROM group_menus WHERE group_id = ?
        """, (group_id,))
        result = cursor.fetchone()
        conn.close()

        if result:
            # 将 JSON 文本解析为 Python 对象
            return json.loads(result[0])
        else:
            print(f"群号 {group_id} 的菜单数据不存在")
            return None
    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
        return None
    except json.JSONDecodeError:
        print(f"群号 {group_id} 的菜单数据格式错误")
        return None


def extract_members(menu_data):
    """提取成员信息"""
    info_list = menu_data.get("info", [])
    if not isinstance(info_list, list):
        return []

    return [
        {
            "title": item.get("title", "未定义标题"),
            "content": item.get("content", "未定义内容"),
            "status": item.get("status", "0"),
        }
        for item in info_list
    ]


def generate_temp_image(members):
    """生成临时图片并返回路径"""
    try:
        image_data = generate_image(members)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_file.write(image_data.getvalue())
            return temp_file.name
    except Exception as e:
        print(f"生成图片失败: {e}")
        return None


async def send_image(api, group_id, image_path):
    """发送图片并删除临时文件"""
    try:
       await api.post_group_msg(group_id, image=image_path)
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def generate_image(data: list) -> BytesIO:
    """
    根据数据生成图片，并返回图片的内存数据
    :param data: 包含成员信息的列表，每个成员是一个字典，包含 title、content 和 status
    :return: 图片的 BytesIO 对象
    """
    try:
        # 设置字体路径
        font_path = os.path.join("static", "font.ttf")  # 确保字体文件存在
        if not os.path.exists(font_path):
            font = ImageFont.load_default()
        else:
            font = ImageFont.truetype(font_path, 30)

        # 加载状态图标
        on_icon_path = os.path.join("static", "on.png")
        off_icon_path = os.path.join("static", "off.png")
        on_icon = Image.open(on_icon_path).convert("RGBA") if os.path.exists(on_icon_path) else None
        off_icon = Image.open(off_icon_path).convert("RGBA") if os.path.exists(off_icon_path) else None

        # 调整图标大小并保持比例
        icon_size = (50, 50)
        if on_icon:
            on_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)
        if off_icon:
            off_icon.thumbnail(icon_size, Image.Resampling.LANCZOS)

         # 加载背景图片
        bg_path = os.path.join("static", "bg.png")
        if os.path.exists(bg_path):
            bg_image = Image.open(bg_path).convert("RGBA")
        else:
            raise FileNotFoundError("背景图片 bg.png 不存在")

        # 布局参数
        padding = 20
        box_width = 600  # 每个成员框的宽度
        box_height = 150  # 每个成员框的高度

        # 根据背景图片的宽高比动态计算每行显示的成员数量
        bg_width, bg_height = bg_image.size
        items_per_row = max(1, bg_width // (box_width + padding))  # 确保至少有一列
        img_width = items_per_row * (box_width + padding) + padding  # 图片宽度
        rows = (len(data) + items_per_row - 1) // items_per_row  # 计算总行数
        img_height = rows * (box_height + padding) + padding  # 图片高度

        # 调整背景图片大小
        bg_image = bg_image.resize((img_width, img_height), Image.Resampling.LANCZOS)

        # 创建图片
        img = Image.new("RGBA", (img_width, img_height), color=(255, 255, 255, 0))
        img.paste(bg_image, (0, 0))  # 将背景图片粘贴到底图上
        draw = ImageDraw.Draw(img)

        # 创建一个半透明图层
        overlay = Image.new("RGBA", (img_width, img_height), (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # 绘制每个成员的信息
        for index, item in enumerate(data):
            row = index // items_per_row
            col = index % items_per_row

            # 计算框的位置
            box_x1 = padding + col * (box_width + padding)
            box_y1 = padding + row * (box_height + padding)
            box_x2 = box_x1 + box_width
            box_y2 = box_y1 + box_height

            # 绘制框背景到半透明图层
            overlay_draw.rectangle(
                [box_x1, box_y1, box_x2, box_y2],
                fill=(255, 255, 255, 100),  # 半透明白色背景
                outline=(150, 150, 150),  # 浅灰色边框
                width=2
            )

            # 获取成员信息
            title = item.get("title", "未定义标题")
            content = item.get("content", "未定义内容")
            status = item.get("status", 0)

            # 绘制序号
            text_x = box_x1 + 80  # 留出图标空间
            text_y = box_y1 + 20
            draw.text((text_x, text_y), f"{index + 1}:{title}", fill=(0, 0, 0), font=font)

            # 绘制内容，超出边框显示省略号
            max_content_width = box_width - 200  # 内容最大宽度
            content = truncate_text(content, font, max_content_width)
            draw.text((text_x, text_y + 40), f"内容: {content}", fill=(50, 50, 50), font=font)

            # 绘制状态图标
            icon = on_icon if status == "1" else off_icon
            if icon:
                img.paste(icon, (box_x1 + 10, box_y1 + 35), icon)

        # 将半透明图层叠加到主图层
        img = Image.alpha_composite(img, overlay)

        # 将图片保存到内存
        buffer = BytesIO()
        img = img.convert("RGB")  # 转换为 RGB 模式以保存为 PNG
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    except Exception as e:
        raise RuntimeError(f"生成图片时出错: {e}")

def truncate_text(text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    """
    如果文本宽度超出最大宽度，则截断并添加省略号
    :param text: 原始文本
    :param font: 字体对象
    :param max_width: 最大宽度
    :return: 截断后的文本
    """
    ellipsis = "..."
    ellipsis_width = font.getlength(ellipsis)  # 获取省略号的宽度

    # 如果文本宽度小于最大宽度，直接返回
    text_width = font.getlength(text)
    if text_width <= max_width:
        return text

    # 截断文本并添加省略号
    truncated_text = ""
    for char in text:
        if font.getlength(truncated_text + char) + ellipsis_width > max_width:
            break
        truncated_text += char

    return truncated_text + ellipsis

def update_menu_from_file(group_id):
    """从 static/menu.json 文件读取菜单数据并与数据库中的数据合并"""
    menu_file = os.path.join("static", "menu.json")
    if not os.path.exists(menu_file):
        print(f"菜单文件 '{menu_file}' 不存在")
        return False

    try:
        # 读取 menu.json 文件中的数据
        with open(menu_file, "r", encoding="utf-8") as file:
            new_menu_data = json.load(file)

        # 从数据库中加载现有菜单数据
        db_path = "data.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
        SELECT menu_item FROM group_menus WHERE group_id = ?
        """, (group_id,))
        result = cursor.fetchone()

        if result:
            # 将现有数据解析为 Python 对象
            existing_menu_data = json.loads(result[0])
            # 合并新数据和现有数据
            merged_menu_data = merge_menu_data(existing_menu_data, new_menu_data)
        else:
            # 如果数据库中没有数据，直接使用新数据
            merged_menu_data = new_menu_data

        # 将合并后的数据写回数据库
        cursor.execute("""
        INSERT OR REPLACE INTO group_menus (group_id, menu_item)
        VALUES (?, ?)
        """, (group_id, json.dumps(merged_menu_data, ensure_ascii=False)))

        conn.commit()
        conn.close()
        print(f"群号 {group_id} 的菜单已更新并合并")
        return True
    except FileNotFoundError:
        print(f"菜单文件 '{menu_file}' 未找到")
    except json.JSONDecodeError:
        print(f"菜单文件 '{menu_file}' 格式错误")
    except sqlite3.Error as e:
        print(f"数据库操作失败: {e}")
    return False
def merge_menu_data(existing_menu_data, new_menu_data):
    """合并现有菜单数据和新菜单数据"""
    if "info" in existing_menu_data and "info" in new_menu_data:
        # 合并 info 列表
        existing_info = existing_menu_data["info"]
        new_info = new_menu_data["info"]

        # 去重合并（假设以 title 为唯一标识）
        merged_info = {item["title"]: item for item in existing_info}
        for item in new_info:
            merged_info[item["title"]] = item

        # 将合并后的数据转换回列表
        existing_menu_data["info"] = list(merged_info.values())

    # 如果有其他字段需要合并，可以在这里处理
    return existing_menu_data