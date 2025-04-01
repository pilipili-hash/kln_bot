import websockets
from ncatbot.utils.config import config
import html,re,json
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
        # print("收到响应:", response)
async def send_group_forward_msg_cq(group_id, content):
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
        "action": "send_group_msg",  # WebSocket 通信的动作类型
        "params": {
            "group_id": group_id,
            "message": content
        }
    }
    # print(payload)
    # 通过 WebSocket 发送消息
    async with websockets.connect(ws_uri) as websocket:
        await websocket.send(json.dumps(payload))
        response = await websocket.recv()
        # print("收到响应:", response)


async def cq_img(url):
    """
    返回 CQ 码格式的图片消息
    :param url: 图片的 URL
    :return: CQ 码格式的字符串
    """
    return f"[CQ:image,file={url}]"


def get_cqimg(cq_code):
    """
    从 CQ 码格式的图片消息中提取 URL 并进行 HTML 实体解码。
    :param cq_code: CQ 码格式的字符串，例如 [CQ:image,file=...,url=...]
    :return: 解码后的图片的 URL，如果未找到则返回 None
    """
    # 使用正则表达式匹配 CQ 码中的 url 部分
    match = re.search(r"url=([^,]+)", cq_code)
    if match:
        # 提取匹配到的 URL 并进行 HTML 实体解码
        encoded_url = match.group(1)
        decoded_url = html.unescape(encoded_url)
        return decoded_url
    return None