from jmcomic import create_option_by_file
from ncatbot.core.element import MessageChain, At, Text
import os
from utils.group_forward_msg import send_group_forward_msg_ws
import aiohttp
import random
import string
import base64
from utils.config_manager import get_config
def create_client(config_path: str):
    """创建禁漫客户端"""
    option = create_option_by_file(config_path)
    client = option.new_jm_client()
    return option, client

async def fetch_and_modify_image(image_url: str) -> str:
    """
    下载图片并在末尾添加随机字符串以修改 MD5
    :param image_url: 图片 URL
    :return: 修改后的图片数据的 Base64 编码
    """
    proxy=get_config("proxy",None)  # 从全局配置获取代理配置
    try:
        async with aiohttp.ClientSession(proxy=proxy) as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    image_data = await response.read()

                    # 添加随机字符串
                    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                    modified_image_data = image_data + random_string.encode('utf-8')

                    # 返回 Base64 编码
                    base64_data = base64.b64encode(modified_image_data).decode('utf-8')
                    return base64_data
                else:
                    print(f"Image download failed with status: {response.status}")
                    return None
    except Exception as e:
        print(f"Image processing error: {e}")
        return None

async def search_jm(client, query: str, page: int):
    """调用禁漫 API 搜索本子"""
    search_page = client.search_site(search_query=query, page=page)
    results = []
    for album_id, title in search_page.iter_id_title():
        img_url = f"https://cdn-msp3.jmapiproxy1.cc/media/albums/{album_id}_3x4.jpg"
        # 使用 fetch_and_modify_image 修改图片 MD5 并获取 Base64 数据
        modified_image_data = await fetch_and_modify_image(img_url)
        if modified_image_data:
            cq_content = (
                f"{title}\n"
                f"[CQ:image,file=base64://{modified_image_data}]\n"
                f"发送: /jm下载 {album_id} 进行下载"
            )
        else:
            cq_content = (
                f"{title}\n"
                f"图片获取失败\n"
                f"发送: /jm下载 {album_id} 进行下载"
            )
        results.append(cq_content)
    return results[:10]  # 每次最多返回10个结果

async def handle_search_request(api, client, group_id: int, query: str, page: int):
    """处理搜索请求"""
    await api.post_group_msg(group_id, text="正在搜索，请稍候...")
    try:
        results = await search_jm(client, query, page)
        if results:
            messages = [
                {
                    "type": "node",
                    "data": {
                        "nickname": "禁漫搜索",
                        "user_id": 1234567,
                        "content": result  # 使用 CQ 码内容
                    }
                }
                for result in results
            ]
            try:
                await send_group_forward_msg_ws(group_id, messages)
            except Exception as e:
                print(f"合并转发消息失败: {e}")
                # 如果合并转发失败，发送不带图片的文本消息
                fallback_messages = "\n\n".join(
                    f"标题: {result.splitlines()[0]}\n发送: {result.splitlines()[-1]}"
                    for result in results
                )
                await api.post_group_msg(group_id, text=f"以下是搜索结果（不含图片）：\n\n{fallback_messages}")
        else:
            await api.post_group_msg(group_id, text="未找到相关本子。")
    except Exception as e:
        await api.post_group_msg(group_id, text=f"搜索失败: {e}")

def download_album(option, album_id: str):
    """下载本子并返回 PDF 文件路径"""
    option.download_album(album_id)
    pdf_dir = option.plugins['after_album'][0]['kwargs']['pdf_dir']
    if not os.path.exists(pdf_dir):
        raise FileNotFoundError(f"PDF 目录不存在: {pdf_dir}")

    # 查找对应的 PDF 文件
    for file in os.listdir(pdf_dir):
        if file.endswith(".pdf") and album_id in file:
            return os.path.join(pdf_dir, file)
    return None

async def handle_download_request(api, option, group_id: int, album_id: str, user_id: int):
    """处理下载请求"""
    await api.post_group_msg(group_id, text=f"正在下载本子 {album_id}，请稍候...")
    try:
        pdf_file = download_album(option, album_id)
        if pdf_file:
            # 发送 PDF 文件
            await api.post_group_file(group_id, file=pdf_file)
            # 使用消息链发送完成消息并 @ 用户
            message_chain = MessageChain([
                At(user_id),
                Text(f" 本子 {album_id} 下载完成并已发送。")
            ])
            await api.post_group_msg(group_id, rtf=message_chain)
        else:
            await api.post_group_msg(group_id, text=f"下载失败，未找到对应的 PDF 文件: {album_id}")
    except Exception as e:
        await api.post_group_msg(group_id, text=f"下载失败: {e}")
