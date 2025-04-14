import os
import random
from ncatbot.core.element import MessageChain, Text, Image, At

# 祝福词列表
BLESSINGS = [
    "可喜可贺！",
    "祝你们幸福！",
    "真是天作之合！",
    "愿你们永远快乐！",
    "真是令人羡慕的一对！",
    "祝福你们的美好未来！"
]

async def get_daily_wife_message(event):
    """
    生成每日老婆消息
    """
    group_id = event.group_id
    user_id = event.user_id
    nickname = event.sender.card if event.sender.card else event.sender.nickname

    # 获取图片路径
    folder_path = os.path.join(os.getcwd(), "static", "dailywife")
    if not os.path.exists(folder_path):
        return MessageChain([Text("抱歉，未找到每日老婆图片资源。")])

    # 随机选择图片
    images = [img for img in os.listdir(folder_path) if img.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not images:
        return MessageChain([Text("抱歉，未找到每日老婆图片资源。")])

    selected_image = random.choice(images)
    image_name = os.path.splitext(selected_image)[0]  # 去除后缀
    image_path = os.path.join(folder_path, selected_image)

    # 构建消息
    blessing = random.choice(BLESSINGS)
    message = MessageChain([
        At(user_id),
        Text(f" {nickname}，你今天的二次元老婆是：{image_name}\n"),
        Image(image_path),
        Text(f"{blessing}")
    ])
    return message
