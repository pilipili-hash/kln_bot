from ncatbot.core.element import (
    MessageChain,  # 消息链，用于组合多个消息元素
    Text,          # 文本消息
    At,            # @某人
    Face,          # QQ表情
    Image,         # 图片
    Reply          # 回复消息
)


import json
from ncatbot.core.element import (
    MessageChain,  # 消息链，用于组合多个消息元素
    Text,          # 文本消息
    At,            # @某人
    Face,          # QQ表情
    Image,         # 图片
    Reply          # 回复消息
)

def build_message_chain_from_json(message: list) -> MessageChain:
    """
    根据消息内容列表构建 MessageChain
    :param message: 包含消息片段的列表
    :return: MessageChain 对象
    """
    try:
        # 确保输入是列表
        if not isinstance(message, list):
            raise ValueError("消息格式错误，必须是包含消息片段的列表")
    except Exception as e:
        raise ValueError(f"无法处理消息内容: {e}")

    elements = []
    for item in message:
        msg_type = item.get("type", "unknown")
        data = item.get("data", {})

        if msg_type == "text":
            elements.append(Text(data.get("text", "")))
        elif msg_type == "at":
            elements.append(At(data.get("target", 0)))
        elif msg_type == "face":
            elements.append(Face(data.get("id", 0)))
        elif msg_type == "image":
            elements.append(Image(data.get("file", "")))
        elif msg_type == "reply":
            elements.append(Reply(data.get("id", 0)))
        else:
            elements.append(item)  # 未知类型直接添加原始数据

    return MessageChain(elements)