import aiosqlite
import json
import tempfile
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from ncatbot.utils.logger import get_log

_log = get_log()

async def load_menu_data(group_id, db_path="data.db"):
    """从数据库中加载菜单数据"""
    try:
        async with aiosqlite.connect(db_path) as conn:
            async with conn.execute("""
            SELECT menu_item FROM group_menus WHERE group_id = ?
            """, (group_id,)) as cursor:
                result = await cursor.fetchone()

        if result:
            # 将 JSON 文本解析为 Python 对象
            return json.loads(result[0])
        else:
            _log.info(f"群号 {group_id} 的菜单数据不存在")
            return None
    except aiosqlite.Error as e:
        _log.info(f"数据库操作失败: {e}")
        return None
    except json.JSONDecodeError:
        _log.info(f"群号 {group_id} 的菜单数据格式错误")
        return None


async def update_menu_from_file(group_id):
    """从 static/menu.json 文件读取菜单数据并与数据库中的数据智能合并

    返回格式：
    {
        "success": bool,
        "error": str,  # 仅在失败时存在
        "stats": {
            "existing_count": int,
            "new_count": int,
            "merged_count": int,
            "added_count": int,
            "removed_count": int,
            "kept_count": int,
            "added_items": list,
            "removed_items": list
        }
    }
    """
    menu_file = os.path.join("static", "menu.json")
    if not os.path.exists(menu_file):
        _log.info(f"菜单文件 '{menu_file}' 不存在")
        return {
            "success": False,
            "error": f"菜单文件 '{menu_file}' 不存在"
        }

    try:
        # 读取 menu.json 文件中的数据
        with open(menu_file, "r", encoding="utf-8") as file:
            new_menu_data = json.load(file)

        # 验证新数据格式
        if "info" not in new_menu_data or not isinstance(new_menu_data["info"], list):
            return {
                "success": False,
                "error": "menu.json 格式错误：缺少 'info' 字段或 'info' 不是列表"
            }

        # 从数据库中加载现有菜单数据
        db_path = "data.db"
        async with aiosqlite.connect(db_path) as conn:
            async with conn.execute("""
            SELECT menu_item FROM group_menus WHERE group_id = ?
            """, (group_id,)) as cursor:
                result = await cursor.fetchone()

            existing_menu_data = None
            if result:
                # 将现有数据解析为 Python 对象
                existing_menu_data = json.loads(result[0])

            # 记录合并前的统计信息
            existing_count = len(existing_menu_data.get("info", [])) if existing_menu_data else 0
            new_count = len(new_menu_data.get("info", []))

            # 合并数据并获取详细统计
            if existing_menu_data:
                merged_result = merge_menu_data_with_stats(existing_menu_data, new_menu_data)
                merged_menu_data = merged_result["data"]
                stats = merged_result["stats"]
            else:
                # 如果数据库中没有数据，直接使用新数据
                merged_menu_data = new_menu_data
                stats = {
                    "existing_count": 0,
                    "new_count": new_count,
                    "merged_count": new_count,
                    "added_count": new_count,
                    "removed_count": 0,
                    "kept_count": 0,
                    "added_items": [item["title"] for item in new_menu_data["info"]],
                    "removed_items": []
                }

            # 将合并后的数据写回数据库
            await conn.execute("""
            INSERT OR REPLACE INTO group_menus (group_id, menu_item)
            VALUES (?, ?)
            """, (group_id, json.dumps(merged_menu_data, ensure_ascii=False)))

            await conn.commit()

        _log.info(f"群号 {group_id} 的菜单已更新并合并")
        return {
            "success": True,
            "stats": stats
        }

    except FileNotFoundError:
        error_msg = f"菜单文件 '{menu_file}' 未找到"
        _log.info(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except json.JSONDecodeError as e:
        error_msg = f"菜单文件 '{menu_file}' JSON格式错误: {str(e)}"
        _log.info(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except aiosqlite.Error as e:
        error_msg = f"数据库操作失败: {str(e)}"
        _log.info(error_msg)
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"更新菜单时发生未知错误: {str(e)}"
        _log.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


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
        _log.info(f"生成图片失败: {e}")
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
        icon_size = (80, 80)
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

           
            title_font_size = 80# 增大标题字体大小
            # 获取成员信息
            title = item.get("title", "未定义标题")
            status = item.get("status", 0)
                      
            # 绘制序号和标题（带描边）
            text_x = box_x1 + 100  # 留出图标空间
            text_y = box_y1 + (box_height - title_font_size) // 2  # 垂直居中

            # 深色描边，浅色文字
            stroke_width = 2  # 增加描边宽度
            stroke_color = (0,0,0)  # 更深的灰色
            text_color = (255, 255, 255)  # 浅灰色

            # 使用更大的字体绘制标题

            title_font = ImageFont.truetype(font_path, title_font_size) if os.path.exists(font_path) else ImageFont.load_default()

            for offset in [(-stroke_width, -stroke_width), (-stroke_width, stroke_width), (stroke_width, -stroke_width), (stroke_width, stroke_width)]:
                draw.text((text_x + offset[0], text_y + offset[1]), f"{index + 1}:{title}", fill=stroke_color, font=title_font)

            # 绘制文字本体（浅色）
            draw.text((text_x, text_y), f"{index + 1}:{title}", fill=text_color, font=title_font)

            # 绘制状态图标
            icon = on_icon if status == "1" else off_icon
            if icon:
                img.paste(icon, (box_x1 + 10, box_y1 + 55), icon)

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

def merge_menu_data_with_stats(existing_menu_data, new_menu_data):
    """智能合并现有菜单数据和新菜单数据，并返回详细统计信息

    返回格式：
    {
        "data": merged_menu_data,
        "stats": {
            "existing_count": int,
            "new_count": int,
            "merged_count": int,
            "added_count": int,
            "removed_count": int,
            "kept_count": int,
            "added_items": list,
            "removed_items": list
        }
    }
    """
    if "info" not in existing_menu_data or "info" not in new_menu_data:
        # 如果任一数据缺少info字段，直接返回新数据
        new_count = len(new_menu_data.get("info", []))
        return {
            "data": new_menu_data,
            "stats": {
                "existing_count": 0,
                "new_count": new_count,
                "merged_count": new_count,
                "added_count": new_count,
                "removed_count": 0,
                "kept_count": 0,
                "added_items": [item["title"] for item in new_menu_data.get("info", [])],
                "removed_items": []
            }
        }

    existing_info = existing_menu_data["info"]
    new_info = new_menu_data["info"]

    # 统计信息
    existing_count = len(existing_info)
    new_count = len(new_info)

    # 创建新数据的title集合，用于快速查找
    new_titles = {item["title"] for item in new_info}

    # 创建现有数据的title到item的映射
    existing_items_map = {item["title"]: item for item in existing_info}

    merged_info = []
    added_items = []
    kept_items = []

    # 遍历新数据中的所有项目
    for new_item in new_info:
        title = new_item["title"]

        if title in existing_items_map:
            # 如果项目在原有数据中存在，保持原有的状态和内容
            existing_item = existing_items_map[title]
            merged_item = {
                "title": title,
                "status": existing_item.get("status", new_item.get("status", "0")),  # 保持原有状态
                "content": existing_item.get("content", new_item.get("content", ""))  # 保持原有内容，如果没有则使用新内容
            }
            merged_info.append(merged_item)
            kept_items.append(title)
            _log.debug(f"保持现有项目: {title} (状态: {merged_item['status']})")
        else:
            # 如果是新项目，直接添加
            merged_info.append(new_item)
            added_items.append(title)
            _log.info(f"添加新项目: {title} (状态: {new_item.get('status', '0')})")

    # 记录被删除的项目
    removed_items = []
    for existing_item in existing_info:
        if existing_item["title"] not in new_titles:
            removed_items.append(existing_item["title"])

    if removed_items:
        _log.info(f"删除的项目: {', '.join(removed_items)}")

    # 更新合并后的数据
    result_data = existing_menu_data.copy()
    result_data["info"] = merged_info

    # 统计信息
    merged_count = len(merged_info)
    added_count = len(added_items)
    removed_count = len(removed_items)
    kept_count = len(kept_items)

    _log.info(f"菜单合并完成: 原有{existing_count}项, 新数据{new_count}项, "
              f"合并后{merged_count}项 (新增{added_count}项, 删除{removed_count}项, 保持{kept_count}项)")

    return {
        "data": result_data,
        "stats": {
            "existing_count": existing_count,
            "new_count": new_count,
            "merged_count": merged_count,
            "added_count": added_count,
            "removed_count": removed_count,
            "kept_count": kept_count,
            "added_items": added_items,
            "removed_items": removed_items
        }
    }

def merge_menu_data(existing_menu_data, new_menu_data):
    """智能合并现有菜单数据和新菜单数据

    合并策略：
    1. 保持原有项目的状态和内容不变
    2. 删除在新数据中不存在的项目
    3. 添加新数据中的新项目
    """
    if "info" not in existing_menu_data or "info" not in new_menu_data:
        # 如果任一数据缺少info字段，直接返回新数据
        return new_menu_data

    existing_info = existing_menu_data["info"]
    new_info = new_menu_data["info"]

    # 创建新数据的title集合，用于快速查找
    new_titles = {item["title"] for item in new_info}

    # 创建新数据的title到item的映射
    new_items_map = {item["title"]: item for item in new_info}

    # 创建现有数据的title到item的映射
    existing_items_map = {item["title"]: item for item in existing_info}

    merged_info = []

    # 遍历新数据中的所有项目
    for new_item in new_info:
        title = new_item["title"]

        if title in existing_items_map:
            # 如果项目在原有数据中存在，保持原有的状态和内容
            existing_item = existing_items_map[title]
            merged_item = {
                "title": title,
                "status": existing_item.get("status", new_item.get("status", "0")),  # 保持原有状态
                "content": existing_item.get("content", new_item.get("content", ""))  # 保持原有内容，如果没有则使用新内容
            }
            merged_info.append(merged_item)
            _log.debug(f"保持现有项目: {title} (状态: {merged_item['status']})")
        else:
            # 如果是新项目，直接添加
            merged_info.append(new_item)
            _log.info(f"添加新项目: {title} (状态: {new_item.get('status', '0')})")

    # 记录被删除的项目
    removed_items = []
    for existing_item in existing_info:
        if existing_item["title"] not in new_titles:
            removed_items.append(existing_item["title"])

    if removed_items:
        _log.info(f"删除的项目: {', '.join(removed_items)}")

    # 更新合并后的数据
    result_data = existing_menu_data.copy()
    result_data["info"] = merged_info

    # 记录合并统计
    existing_count = len(existing_info)
    new_count = len(new_info)
    merged_count = len(merged_info)
    added_count = len([item for item in new_info if item["title"] not in existing_items_map])
    removed_count = len(removed_items)

    _log.info(f"菜单合并完成: 原有{existing_count}项, 新数据{new_count}项, "
              f"合并后{merged_count}项 (新增{added_count}项, 删除{removed_count}项)")

    return result_data


async def get_plugin_by_index(group_id, index):
    """通过索引获取插件信息"""
    try:
        menu_data = await load_menu_data(group_id)
        if not menu_data or "info" not in menu_data:
            return None

        info_list = menu_data["info"]
        if 0 <= index < len(info_list):
            return info_list[index]
        return None
    except Exception as e:
        _log.error(f"通过索引获取插件信息失败: {e}")
        return None


async def get_plugin_by_name(group_id, name):
    """通过名称获取插件信息"""
    try:
        menu_data = await load_menu_data(group_id)
        if not menu_data or "info" not in menu_data:
            return None

        info_list = menu_data["info"]
        for item in info_list:
            if item.get("title", "") == name:
                return item
        return None
    except Exception as e:
        _log.error(f"通过名称获取插件信息失败: {e}")
        return None


async def toggle_plugin_status(group_id, plugin_name, new_status):
    """切换插件状态"""
    try:
        menu_data = await load_menu_data(group_id)
        if not menu_data or "info" not in menu_data:
            return False

        info_list = menu_data["info"]
        updated = False

        for item in info_list:
            if item.get("title", "") == plugin_name:
                item["status"] = new_status
                updated = True
                break

        if updated:
            # 保存更新后的数据到数据库
            async with aiosqlite.connect("data.db") as conn:
                await conn.execute("""
                INSERT OR REPLACE INTO group_menus (group_id, menu_item)
                VALUES (?, ?)
                """, (group_id, json.dumps(menu_data, ensure_ascii=False)))
                await conn.commit()

            _log.info(f"群 {group_id} 的插件 {plugin_name} 状态已更新为 {new_status}")
            return True

        return False
    except Exception as e:
        _log.error(f"切换插件状态失败: {e}")
        return False


# 详细帮助信息字典
PLUGIN_HELP_CONTENT = {
    "智能聊天": """🤖 智能聊天功能

📋 基本使用：
• @机器人 [消息] - AI智能回复
• 机器人 [消息] - 直接对话
• 发送图片 - 自动分析图片内容
• /分析图片 - 专门的图片分析功能

🔧 管理命令：
• /修改设定 [设定内容] - 修改AI角色设定
• /查看设定 - 查看当前设定
• /清空上下文 - 清空对话历史

🌐 联网功能：
• 机器人 联网 [问题] - 联网搜索回答

💡 特色功能：
• 支持多模态对话（文字+图片）
• 智能上下文记忆
• 可自定义AI角色设定""",

    "搜图": """🔍 图片搜索功能

📋 基本使用：
• /搜图 [图片] - 综合搜图
• 发送 /搜图 然后发送图片 - 等待模式搜图

🌐 搜索引擎：
• Google图片搜索 - 通用图片搜索
• SauceNAO - 二次元图片搜索
• IQDB - 动漫图片数据库
• ASCII2D - 备用搜索引擎

📊 搜索结果：
• 相似度百分比
• 原图链接
• 来源信息
• 缩略图预览""",

    "签到": """✅ 签到功能

📋 基本使用：
• 发送 签到 - 每日签到
• /查询 - 查看酥酥数量
• /签到排行 - 查看排行榜

🎁 奖励系统：
• 每日签到获得随机酥酥
• 连续签到有额外奖励
• 特殊日期双倍奖励

👑 管理命令：
• /增加 [数量] @用户 - 增加酥酥
• /减少 [数量] @用户 - 减少酥酥
• 添加彩蛋文本 - 自定义签到图片文字""",

    "点歌": """🎵 点歌功能

📋 基本使用：
• 点歌 [歌名] - 网易云音乐点歌
• QQ点歌 [歌名] - QQ音乐点歌

🎼 支持平台：
• 网易云音乐（默认）
• QQ音乐
• 酷狗音乐
• 酷我音乐

📊 搜索功能：
• 歌曲名搜索
• 歌手名搜索
• 专辑搜索""",

    "以图搜番": """🎬 以图搜番功能

📋 基本使用：
• /搜番 [图片] - 通过截图搜索番剧
• 以图搜番 [图片] - 识别动画截图

📊 搜索信息：
• 番剧名称和集数
• 时间戳信息
• 相似度百分比
• 番剧详细信息

💡 使用技巧：
• 需要清晰的动画截图
• 避免有字幕遮挡的图片
• 支持大部分主流动画""",

    "今日番剧": """📺 今日番剧功能

📋 基本使用：
• 今日番剧 - 查看今天更新的番剧
• 开启番剧推送 - 开启自动推送
• 关闭番剧推送 - 关闭自动推送

⏰ 推送设置：
• 每天上午9点自动推送
• 显示当日更新番剧列表
• 包含播出时间信息

📊 番剧信息：
• 番剧名称和集数
• 播出时间
• 更新状态""",

    "喜加一": """🎮 喜加一功能

📋 基本使用：
• 今日喜加一 - 查看Epic免费游戏
• 开启喜加一推送 - 开启自动推送
• 关闭喜加一推送 - 关闭自动推送

🎁 游戏信息：
• 免费游戏名称
• 游戏简介和截图
• 免费时间期限
• 领取链接

⏰ 推送设置：
• 每天上午9点自动推送
• 新游戏上架及时通知""",

    "帮你bing": """🔍 Bing搜索功能

📋 基本使用：
• /bing [搜索内容] - Bing搜索
• 帮你bing [内容] - 搜索并返回结果

🌐 搜索功能：
• 网页搜索
• 图片搜索
• 新闻搜索

📊 搜索结果：
• 相关网页链接
• 搜索结果摘要
• 相关建议""",

    "setu": """🔞 随机图片功能

📋 使用方法：
• 涩图 [数量] - 获取随机图片（最大20张）

⚠️ 注意事项：
• 仅管理员可用
• 请合理使用
• 注意群规和法律法规

💡 提示：
• 数量范围：1-20张
• 图片质量随机
• 内容分级管理"""
}


async def get_plugin_help_content(plugin_name):
    """获取插件的详细帮助内容"""
    return PLUGIN_HELP_CONTENT.get(plugin_name, None)

