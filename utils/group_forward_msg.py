import json
import asyncio
import websockets
from ncatbot.utils.config import config

async def send_group_forward_msg_ws(group_id, nickname, user_id, msg_type, content):
    """
    使用 WebSocket 发送群组转发消息，支持动态构建消息内容。

    :param group_id: 群组 ID
    :param nickname: 用户昵称
    :param user_id: 用户 ID
    :param msg_type: 消息类型（如 "text", "image", "record", "reply" 等）
    :param content: 消息内容（根据类型传入对应的数据）
    """
    # 获取 WebSocket URI
    ws_uri = config.ws_uri
    if not ws_uri:
        raise ValueError("WebSocket URI 未配置，请检查 config.set_ws_uri()")

    # 根据类型构建消息内容
    if msg_type == "text":
        message_content = [{"type": "text", "data": {"text": content}}]
    elif msg_type == "image":
        message_content = [{"type": "image", "data": {"file": content}}]
    elif msg_type == "record":
        message_content = [{"type": "record", "data": {"content": content}}]
    elif msg_type == "reply":
        message_content = [{"type": "reply", "data": {"id": content}}]
    elif msg_type == "forward":
        message_content = [{"type": "forward", "data": {"id": content}}]
    else:
        raise ValueError(f"不支持的消息类型: {msg_type}")

    # 构造请求数据
    payload = {
        "action": "send_group_forward_msg",  # WebSocket 通信的动作类型
        "params": {
            "group_id": group_id,
            "messages": [
                {
                    "type": "node",
                    "data": {
                        "user_id": user_id,
                        "nickname": nickname,
                        "content": message_content
                    }
                }
            ]
        }
    }

    # 通过 WebSocket 发送消息
    async with websockets.connect(ws_uri) as websocket:
        await websocket.send(json.dumps(payload))
        response = await websocket.recv()
        print("收到响应:", response)

