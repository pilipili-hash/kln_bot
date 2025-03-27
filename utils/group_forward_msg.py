import json
import asyncio
import websockets
from ncatbot.core.element import (
    MessageChain,  # 消息链，用于组合多个消息元素
    Text,          # 文本消息
    At,            # @某人
    Face,          # QQ表情
    Image,         # 图片
)
from ncatbot.utils.config import config

async def send_group_forward_msg_ws(group_id, content):
    """
    使用 WebSocket 发送群组转发消息，支持动态构建消息内容。

    :param group_id: 群组 ID
    :param nickname: 用户昵称
    :param user_id: 用户 ID
    :param content: 消息内容（MessageChain 类型）
    """
    # 获取 WebSocket URI
    ws_uri = config.ws_uri
    if not ws_uri:
        raise ValueError("WebSocket URI 未配置，请检查 config.set_ws_uri()")

    # 如果 content 是 MessageChain 对象，转换为字典

    # 构造请求数据
    payload = {
        "action": "send_group_forward_msg",  # WebSocket 通信的动作类型
        "params": {
            "group_id": group_id,
            "messages": content
        }
    }

    # 通过 WebSocket 发送消息
    async with websockets.connect(ws_uri) as websocket:
        await websocket.send(json.dumps(payload))
        response = await websocket.recv()
        print("收到响应:", response)


async def cq_img(url):
    """
    返回 CQ 码格式的图片消息
    :param url: 图片的 URL
    :return: CQ 码格式的字符串
    """
    return f"[CQ:image,file={url}]"