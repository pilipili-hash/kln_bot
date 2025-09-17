import os
import hashlib
import logging
from datetime import datetime
from typing import Optional
from ncatbot.core.element import MessageChain, Text, Image, At

# 设置日志
_log = logging.getLogger(__name__)

# 祝福词列表
BLESSINGS = [
    "可喜可贺！",
    "祝你们幸福！",
    "真是天作之合！",
    "愿你们永远快乐！",
    "真是令人羡慕的一对！",
    "祝福你们的美好未来！",
    "恭喜你找到了命中注定的她！",
    "这就是传说中的缘分吧！",
    "愿你们的爱情长长久久！",
    "真是郎才女貌的一对！",
    "祝愿你们白头偕老！",
    "这份爱情真让人感动！"
]

def get_daily_seed(user_id: int) -> int:
    """
    基于用户ID和当前日期生成每日固定种子
    确保同一用户在同一天总是得到相同的结果
    """
    today = datetime.now().strftime("%Y-%m-%d")
    seed_string = f"{user_id}_{today}"
    # 使用MD5哈希生成固定种子
    hash_object = hashlib.md5(seed_string.encode())
    return int(hash_object.hexdigest(), 16) % (2**32)

def clean_image_name(filename: str) -> str:
    """
    清理图片文件名，提取角色名称
    """
    # 去除文件扩展名
    name = os.path.splitext(filename)[0]

    # 处理特殊格式的文件名
    if "さんと相性の良いウマ娘は【" in name and "】です。" in name:
        # 提取ウマ娘角色名
        start = name.find("【") + 1
        end = name.find("】")
        if start > 0 and end > start:
            return name[start:end]

    # 移除常见的数字前缀（如 "51160511博丽灵梦" -> "博丽灵梦"）
    import re
    name = re.sub(r'^\d+', '', name)

    # 移除特殊字符和括号内容
    name = re.sub(r'\([^)]*\)', '', name)  # 移除括号内容
    name = re.sub(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>?]', '', name)  # 移除特殊字符

    return name.strip() or "神秘角色"

async def get_daily_wife_message(event) -> Optional[MessageChain]:
    """
    生成每日老婆消息
    基于用户ID和日期确保每天结果固定
    """
    try:
        user_id = event.user_id
        nickname = event.sender.card if event.sender.card else event.sender.nickname

        # 获取图片路径
        folder_path = os.path.join(os.getcwd(), "static", "dailywife")
        if not os.path.exists(folder_path):
            _log.error(f"每日老婆图片目录不存在: {folder_path}")
            return MessageChain([Text("❌ 抱歉，未找到每日老婆图片资源。")])

        # 获取所有图片文件
        try:
            all_files = os.listdir(folder_path)
            images = [img for img in all_files if img.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
        except Exception as e:
            _log.error(f"读取图片目录失败: {e}")
            return MessageChain([Text("❌ 读取图片资源时发生错误。")])

        if not images:
            _log.warning(f"每日老婆图片目录为空: {folder_path}")
            return MessageChain([Text("❌ 抱歉，未找到每日老婆图片资源。")])

        # 使用固定种子确保每日结果一致
        daily_seed = get_daily_seed(user_id)
        import random
        random.seed(daily_seed)

        # 选择图片和祝福语
        selected_image = random.choice(images)
        blessing = random.choice(BLESSINGS)

        # 重置随机种子
        random.seed()

        # 清理图片名称
        image_name = clean_image_name(selected_image)
        image_path = os.path.join(folder_path, selected_image)

        # 检查图片文件是否存在
        if not os.path.exists(image_path):
            _log.error(f"图片文件不存在: {image_path}")
            return MessageChain([Text("❌ 图片文件丢失，请联系管理员。")])

        # 构建消息
        message = MessageChain([
            At(user_id),
            Text(f" {nickname}，你今天的二次元老婆是：\n💕 {image_name} 💕\n"),
            Image(image_path),
            Text(f"\n🎊 {blessing}")
        ])

        _log.info(f"用户 {user_id}({nickname}) 抽到了老婆: {image_name}")
        return message

    except Exception as e:
        _log.error(f"生成每日老婆消息时发生错误: {e}")
        return MessageChain([Text("❌ 生成老婆信息时发生错误，请稍后再试。")])
