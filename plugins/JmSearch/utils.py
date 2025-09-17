from jmcomic import create_option_by_file
from ncatbot.core.element import MessageChain, At, Text
import os
import logging
import asyncio
import concurrent.futures
from utils.group_forward_msg import send_group_forward_msg_ws
# import aiohttp  # 暂时不需要，图片功能已注释
# import random   # 暂时不需要，图片功能已注释
# import string   # 暂时不需要，图片功能已注释
# import base64   # 暂时不需要，图片功能已注释
# from utils.config_manager import get_config  # 暂时不需要，图片功能已注释

# 设置日志
_log = logging.getLogger(__name__)
def create_client(config_path: str):
    """创建禁漫客户端"""
    try:
        option = create_option_by_file(config_path)
        client = option.new_jm_client()
        _log.info(f"禁漫客户端创建成功，配置文件: {config_path}")
        return option, client
    except Exception as e:
        _log.error(f"创建禁漫客户端失败: {e}")
        raise

# 暂时注释掉图片处理功能，避免风控问题
# async def fetch_and_modify_image(image_url: str) -> str:
#     """
#     下载图片并在末尾添加随机字符串以修改 MD5
#     :param image_url: 图片 URL
#     :return: 修改后的图片数据的 Base64 编码
#     """
#     proxy = get_config("proxy", None)  # 从全局配置获取代理配置
#
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#         'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
#         'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
#     }
#
#     try:
#         timeout = aiohttp.ClientTimeout(total=30)
#         async with aiohttp.ClientSession(proxy=proxy, timeout=timeout) as session:
#             async with session.get(image_url, headers=headers) as response:
#                 if response.status == 200:
#                     image_data = await response.read()
#
#                     # 添加随机字符串
#                     random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
#                     modified_image_data = image_data + random_string.encode('utf-8')
#
#                     # 返回 Base64 编码
#                     base64_data = base64.b64encode(modified_image_data).decode('utf-8')
#                     _log.debug(f"图片下载成功: {image_url}")
#                     return base64_data
#                 else:
#                     _log.warning(f"图片下载失败，状态码: {response.status}, URL: {image_url}")
#                     return None
#     except Exception as e:
#         _log.error(f"图片处理错误: {e}, URL: {image_url}")
#         return None

async def search_jm(client, query: str, page: int):
    """调用禁漫 API 搜索本子（无图片版本）"""
    try:
        _log.info(f"开始搜索禁漫: 关键词'{query}', 页码{page}")
        search_page = client.search_site(search_query=query, page=page)
        results = []

        count = 0
        for album_id, title in search_page.iter_id_title():
            if count >= 5:  # 限制最多10个结果
                break

            # 限制标题长度
            if len(title) > 50:
                title = title[:50] + "..."

            # 不包含图片的内容，避免风控
            cq_content = (
                f"📚 {title}\n"
                f"🆔 ID: {album_id}\n"
                # f"🔗 封面: [CQ:image,file=https://cdn-msp3.jmapiproxy1.cc/media/albums/{album_id}_3x4.jpg]\n"
                f"💡 发送: /jm下载 {album_id}"
            )
            results.append(cq_content)
            count += 1

        _log.info(f"搜索完成，找到 {len(results)} 个结果")
        return results

    except Exception as e:
        _log.error(f"搜索禁漫时出错: {e}")
        raise

async def handle_search_request(api, client, group_id: int, query: str, page: int):
    """处理搜索请求（无图片版本）"""
    await api.post_group_msg(group_id, text=f"🔍 正在搜索'{query}'，请稍候...")

    try:
        results = await search_jm(client, query, page)
        if results:
            # 添加标题消息
            title_message = {
                "type": "node",
                "data": {
                    "nickname": "🔍 禁漫搜索",
                    "user_id": "1234567",
                    "content": f"📚 搜索结果: '{query}'\n📊 共找到 {len(results)} 个结果\n⏰ 搜索时间: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}\n\n💡 提示: 为避免风控，已移除图片预览\n🔗 可通过提供的链接查看封面"
                }
            }

            messages = [title_message]

            # 添加搜索结果（无图片）
            for i, result in enumerate(results, 1):
                messages.append({
                    "type": "node",
                    "data": {
                        "nickname": f"📚 漫画 {i}",
                        "user_id": "1234567",
                        "content": result
                    }
                })

            try:
                await send_group_forward_msg_ws(group_id, messages)
                _log.info(f"搜索结果发送成功: 关键词'{query}', 结果数{len(results)}")
            except Exception as e:
                _log.error(f"合并转发消息失败: {e}")
                # 如果合并转发失败，发送普通文本消息
                fallback_messages = []
                for i, result in enumerate(results, 1):
                    lines = result.splitlines()
                    title_line = lines[0] if lines else "未知标题"
                    id_line = lines[1] if len(lines) > 1 else "未知ID"
                    link_line = lines[2] if len(lines) > 2 else ""
                    download_line = lines[-1] if lines else "无下载信息"

                    item_text = f"{i}. {title_line}\n{id_line}"
                    if link_line:
                        item_text += f"\n{link_line}"
                    item_text += f"\n{download_line}"
                    fallback_messages.append(item_text)

                fallback_text = f"🔍 搜索结果: '{query}' (共{len(results)}个)\n\n" + "\n\n".join(fallback_messages)

                # 如果文本太长，分批发送
                if len(fallback_text) > 4000:
                    # 发送标题
                    await api.post_group_msg(group_id, text=f"🔍 搜索结果: '{query}' (共{len(results)}个)")

                    # 分批发送结果
                    batch_size = 3
                    for i in range(0, len(fallback_messages), batch_size):
                        batch = fallback_messages[i:i+batch_size]
                        batch_text = "\n\n".join(batch)
                        await api.post_group_msg(group_id, text=batch_text)
                else:
                    await api.post_group_msg(group_id, text=fallback_text)
        else:
            await api.post_group_msg(
                group_id,
                text=f"❌ 未找到关键词'{query}'的相关漫画\n\n💡 尝试使用其他关键词搜索"
            )
    except Exception as e:
        _log.error(f"搜索请求处理失败: {e}")
        await api.post_group_msg(
            group_id,
            text=f"❌ 搜索失败: {str(e)}\n\n💡 请稍后再试或检查关键词"
        )

async def download_album_async(option, album_id: str):
    """异步下载本子并返回 PDF 文件路径"""
    try:
        _log.info(f"开始异步下载漫画: ID={album_id}")

        # 使用线程池执行同步的下载操作
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # 在线程池中执行下载
            await loop.run_in_executor(executor, option.download_album, album_id)

        pdf_dir = option.plugins['after_album'][0]['kwargs']['pdf_dir']
        if not os.path.exists(pdf_dir):
            _log.error(f"PDF 目录不存在: {pdf_dir}")
            raise FileNotFoundError(f"PDF 目录不存在: {pdf_dir}")

        # 查找对应的 PDF 文件
        for file in os.listdir(pdf_dir):
            if file.endswith(".pdf") and album_id in file:
                pdf_path = os.path.join(pdf_dir, file)
                _log.info(f"异步下载完成: {pdf_path}")
                return pdf_path

        _log.warning(f"未找到对应的PDF文件: ID={album_id}")
        return None

    except Exception as e:
        _log.error(f"异步下载漫画失败: {e}, ID={album_id}")
        raise

async def handle_download_request(api, option, group_id: int, album_id: str, user_id: int):
    """处理异步下载请求"""
    # 调试API对象信息
    _log.info(f"API对象类型: {type(api)}")
    api_methods = [method for method in dir(api) if not method.startswith('_')]
    _log.info(f"API对象可用方法: {api_methods}")

    # 检查是否有其他文件相关方法
    file_methods = [method for method in api_methods if 'file' in method.lower()]
    _log.info(f"文件相关方法: {file_methods}")

    # 检查是否有群相关方法
    group_methods = [method for method in api_methods if 'group' in method.lower()]
    _log.info(f"群相关方法: {group_methods}")

    await api.post_group_msg(group_id, text=f"📥 正在异步下载漫画 {album_id}，下载期间可以继续使用其他命令...")

    try:
        pdf_file = await download_album_async(option, album_id)
        if pdf_file:
            # 检查文件是否存在和可读
            if not os.path.exists(pdf_file):
                _log.error(f"PDF文件不存在: {pdf_file}")
                await api.post_group_msg(group_id, text=f"❌ PDF文件不存在: {album_id}")
                return

            if not os.path.isfile(pdf_file):
                _log.error(f"路径不是文件: {pdf_file}")
                await api.post_group_msg(group_id, text=f"❌ 路径不是文件: {album_id}")
                return

            # 检查文件大小
            file_size = os.path.getsize(pdf_file)
            file_size_mb = file_size / (1024 * 1024)

            _log.info(f"准备上传文件: {pdf_file}")
            _log.info(f"文件大小: {file_size} bytes ({file_size_mb:.2f} MB)")
            _log.info(f"文件是否可读: {os.access(pdf_file, os.R_OK)}")

            if file_size_mb > 100:  # 如果文件大于100MB，提醒用户
                await api.post_group_msg(
                    group_id,
                    text=f"⚠️ 文件较大 ({file_size_mb:.1f}MB)，正在上传，请耐心等待..."
                )

            # 上传 PDF 文件到群文件
            try:
                _log.info(f"开始上传群文件: {pdf_file} 到群 {group_id}")

                # 使用 upload_group_file 方法上传到群文件
                file_name = os.path.basename(pdf_file)
                # 确保使用绝对路径
                abs_file_path = os.path.abspath(pdf_file)
                _log.info(f"文件绝对路径: {abs_file_path}")

                upload_result = await api.upload_group_file(
                    group_id=group_id,
                    file=abs_file_path,
                    name=file_name,
                    folder_id=""
                )

                _log.info(f"群文件上传结果: {upload_result}")
                _log.info(f"群文件上传结果类型: {type(upload_result)}")

                # 检查上传结果
                if isinstance(upload_result, dict):
                    _log.info(f"群文件上传结果字典: {upload_result}")
                    if upload_result.get('retcode') == 0 or upload_result.get('status') == 'ok':
                        _log.info("群文件上传成功")
                    else:
                        _log.warning(f"群文件上传可能失败: {upload_result}")
                else:
                    _log.info(f"群文件上传结果: {str(upload_result)}")

            except Exception as upload_error:
                _log.error(f"群文件上传失败: {upload_error}")
                _log.error(f"上传错误类型: {type(upload_error)}")

                # 如果群文件上传失败，尝试作为消息发送
                try:
                    _log.info("尝试作为消息发送文件...")
                    # 使用绝对路径
                    abs_file_path = os.path.abspath(pdf_file)
                    message_result = await api.post_group_file(group_id, file=abs_file_path)
                    _log.info(f"消息文件发送结果: {message_result}")
                except Exception as msg_error:
                    _log.error(f"消息文件发送也失败: {msg_error}")
                    await api.post_group_msg(
                        group_id,
                        text=f"❌ 文件上传失败: {str(upload_error)}\n🆔 漫画ID: {album_id}\n📁 文件路径: {pdf_file}\n📊 文件大小: {file_size_mb:.1f}MB"
                    )
                    return
            # 使用消息链发送完成消息并 @ 用户
            file_name = os.path.basename(pdf_file)
            message_chain = MessageChain([
                At(user_id),
                Text(f" 📚 漫画 {album_id} 异步下载完成\n📁 文件大小: {file_size_mb:.1f}MB\n📂 文件名: {file_name}\n📤 已上传到群文件\n⏰ 下载期间其他命令正常可用")
            ])
            await api.post_group_msg(group_id, rtf=message_chain)
            _log.info(f"异步下载请求完成: ID={album_id}, 用户={user_id}, 文件大小={file_size_mb:.1f}MB, 文件名={file_name}")
        else:
            await api.post_group_msg(
                group_id,
                text=f"❌ 异步下载失败，未找到对应的PDF文件\n🆔 漫画ID: {album_id}\n\n💡 请检查ID是否正确或稍后再试"
            )
    except Exception as e:
        _log.error(f"异步下载请求处理失败: {e}, ID={album_id}")
        await api.post_group_msg(
            group_id,
            text=f"❌ 异步下载失败: {str(e)}\n🆔 漫画ID: {album_id}\n\n💡 请检查ID是否正确或稍后再试"
        )
