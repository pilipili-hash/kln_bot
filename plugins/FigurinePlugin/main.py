import aiohttp
import base64
import json
import re
import random
import time
import os
import asyncio
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Image, Text, At
from PluginManager.plugin_manager import feature_required

bot = CompatibleEnrollment

class FigurinePlugin(BasePlugin):
    name = "FigurinePlugin"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        """插件加载时执行"""
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        
        # 确保图片缓存目录存在
        os.makedirs("static/figurine_cache", exist_ok=True)
    async def fetch_image(self, url, max_retries=3):
        """获取图片并转换为base64编码"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://qq.com/'
        }
        
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=30) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            if len(image_data) < 100:  # 检查是否是有效图片
                                continue
                            return base64.b64encode(image_data).decode('utf-8')
                        elif attempt < max_retries - 1:  # 不是最后一次尝试
                            await asyncio.sleep(1)  # 等待1秒后重试
            except Exception:
                if attempt < max_retries - 1:  # 不是最后一次尝试
                    await asyncio.sleep(1)  # 等待1秒后重试
        
        # 所有尝试都失败，返回备用头像
        return await self.get_fallback_avatar()
    async def get_fallback_avatar(self):
        """获取备用头像"""
        fallback_urls = [
            "https://thirdqq.qlogo.cn/g?b=qq&nk=10000&s=640",
            "https://q1.qlogo.cn/g?b=qq&nk=10000&s=640",
            "https://q2.qlogo.cn/g?b=qq&nk=10000&s=640"
        ]
        
        # 尝试从网络获取备用头像
        for url in fallback_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=30) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            if len(image_data) > 100:
                                return base64.b64encode(image_data).decode('utf-8')
            except:
                continue
        
        # 尝试使用本地默认头像
        try:
            with open("static/default_avatar.png", "rb") as f:
                image_data = f.read()
                return base64.b64encode(image_data).decode('utf-8')
        except:
            pass
        
        # 使用1x1像素透明PNG作为最后的备用方案
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    async def download_image(self, url, save_path=None):
        """下载图片并保存或返回字节数据"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://eb2.siyangyuan.gq:5208/'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # 保存图片如果提供了路径
                        if save_path:
                            with open(save_path, 'wb') as f:
                                f.write(image_data)
                            return save_path
                        
                        return image_data
            return None
        except Exception:
            return None
    async def extract_full_url(self, url_text):
        """从文本中提取完整URL，包括所有参数"""
        # 尝试提取带 X-Amz 参数的URL (Cloudflare R2和S3链接)
        if 'X-Amz-' in url_text:
            full_url_match = re.search(r'(https?://[^\s"\']+X-Amz[^\s"\'\)]+)', url_text)
            if full_url_match:
                return full_url_match.group(1)
        
        # 尝试提取普通图片URL
        url_match = re.search(r'(https?://[^\s"\']+\.(?:jpg|jpeg|png|gif|webp)[^\s"\'\)]*)', url_text)
        if url_match:
            return url_match.group(1)
        
        return url_text
    async def generate_figurine_from_image(self, image_data=None, image_url=None, avatar_base64=None):
        """从提供的图像生成手办图片"""
        try:
            # 准备图像数据
            if not avatar_base64:
                if image_data:
                    # 直接提供的图像数据
                    avatar_base64 = base64.b64encode(image_data).decode('utf-8')
                elif image_url:
                    # 从URL获取图像
                    avatar_base64 = await self.fetch_image(image_url)
            
            if not avatar_base64:
                return None
            
            # 构建API请求
            prompt_text = "Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it"
            
            payload = {
                "model": "nano-banana",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{avatar_base64}"}}
                        ]
                    }
                ],
                "stream": False
            }
            
            # 发送请求到API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://eb2.siyangyuan.gq:5208/v1/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=300
                ) as response:
                    if response.status != 200:
                        return None
                    
                    result = await response.json()
                    
                    # 处理响应
                    if "choices" in result and len(result["choices"]) > 0:
                        message_content = result["choices"][0]["message"]["content"]
                        timestamp = int(time.time())
                        
                        # 1. 尝试从Markdown语法中提取图片
                        md_url_match = re.search(r'!\[.*?\]\((.*?)(?:\s.*?)?\)', message_content)
                        if md_url_match:
                            full_url = await self.extract_full_url(message_content)
                            image_path = f"static/figurine_cache/figurine_{timestamp}.png"
                            if await self.download_image(full_url, image_path):
                                return image_path
                        
                        # 2. 尝试提取base64图像
                        base64_pattern = r'data:image\/[^;]+;base64,([^"]+)'
                        base64_matches = re.findall(base64_pattern, message_content)
                        if base64_matches:
                            return f"data:image/png;base64,{base64_matches[0]}"
                        
                        # 3. 尝试提取普通图像URL
                        image_urls = re.findall(r'(https?:\/\/\S+\.(?:jpg|jpeg|png|gif|webp))', message_content)
                        if image_urls:
                            url = image_urls[0]
                            full_url = await self.extract_full_url(message_content)
                            if full_url != url:
                                url = full_url
                            
                            image_path = f"static/figurine_cache/figurine_{timestamp}.png"
                            if await self.download_image(url, image_path):
                                return image_path
                        
                        # 4. 如果无法提取图像，返回文本内容
                        return message_content[:500]  # 限制长度
            return None
        except Exception as e:
            print(f"生成手办图片时出错: {str(e)}")
            return None
    async def generate_figurine(self, user_id):
        """根据用户QQ号生成手办图片"""
        try:
            # QQ头像URL列表
            avatar_urls = [
                f"https://q.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                f"https://q2.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                f"https://q3.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                f"https://q4.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                f"https://thirdqq.qlogo.cn/g?b=qq&nk={user_id}&s=640"
            ]
            
            # 随机打乱URL顺序，增加成功率
            random.shuffle(avatar_urls)
            
            # 尝试获取头像
            for url in avatar_urls:
                avatar_base64 = await self.fetch_image(url)
                if avatar_base64:
                    return await self.generate_figurine_from_image(avatar_base64=avatar_base64)
            
            return None
        except Exception as e:
            print(f"获取用户头像时出错: {str(e)}")
            return None
    async def extract_image_from_message(self, message):
        """从消息中提取图片元素"""
        try:
            # 从消息链中提取图片
            if hasattr(message, 'message_chain') and message.message_chain:
                for element in message.message_chain:
                    if isinstance(element, Image):
                        if hasattr(element, 'url') and element.url:
                            return {'url': element.url}
                        elif hasattr(element, 'base64') and element.base64:
                            return {'base64': element.base64}
                        elif hasattr(element, 'path') and element.path:
                            with open(element.path, 'rb') as f:
                                return {'data': f.read()}
            
            # 从CQ码中提取图片
            if hasattr(message, 'raw_message'):
                raw_msg = message.raw_message
                
                # 提取URL型图片
                url_patterns = [
                    r'\[CQ:image,[^]]*?url=([^,\]&]+(?:&amp;[^,\]]+)*)',
                    r'url=([^,\]&]+(?:&amp;[^,\]]+)*)',
                    r'url=(https?://[^,\]]+)'
                ]
                
                for pattern in url_patterns:
                    matches = re.findall(pattern, raw_msg)
                    if matches:
                        url = matches[0]
                        # 替换HTML转义字符
                        return {'url': url.replace('&amp;', '&')}
                
                # 提取文件型图片
                file_matches = re.findall(r'\[CQ:image,(?:[^,\]]*,)?file=([^,\]]+)', raw_msg)
                if file_matches:
                    file_id = file_matches[0]
                    # 尝试多个可能的路径
                    for path in [
                        os.path.join("data", "images", file_id),
                        os.path.join("data", "image", file_id),
                        file_id
                    ]:
                        if os.path.exists(path):
                            with open(path, 'rb') as f:
                                return {'data': f.read()}
            
            return None
        except Exception as e:
            print(f"提取图片时出错: {str(e)}")
            return None
    async def extract_at_from_message(self, message):
        """从消息中提取@的用户"""
        try:
            # 从消息链中提取@
            if hasattr(message, 'message_chain') and message.message_chain:
                for element in message.message_chain:
                    if isinstance(element, At):
                        return element.target
            
            # 从CQ码中提取@
            if hasattr(message, 'raw_message'):
                cq_matches = re.findall(r'\[CQ:at,qq=(\d+)\]', message.raw_message)
                if cq_matches:
                    return cq_matches[0]
            
            return None
        except Exception as e:
            print(f"提取At时出错: {str(e)}")
            return None
    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件，支持@用户和附带图片"""
        if not event.raw_message.strip().startswith("/手办"):
            return
            
        await self.api.post_group_msg(event.group_id, text="正在为您生成手办图片，请稍候...(可能需要1-3分钟)")
        
        try:
            # 确定图像源（优先级：附带图片 > @用户头像 > 发送者头像）
            image_info = await self.extract_image_from_message(event)
            at_user_id = await self.extract_at_from_message(event)
            
            # 根据不同来源生成手办图片
            result = None
            if image_info:
                # 使用附带的图片
                if 'url' in image_info:
                    result = await self.generate_figurine_from_image(image_url=image_info['url'])
                elif 'base64' in image_info:
                    result = await self.generate_figurine_from_image(
                        image_data=base64.b64decode(image_info['base64'])
                    )
                elif 'data' in image_info:
                    result = await self.generate_figurine_from_image(image_data=image_info['data'])
            elif at_user_id:
                # 使用@的用户头像
                result = await self.generate_figurine(at_user_id)
            else:
                # 使用发送者自己的头像
                result = await self.generate_figurine(event.user_id)
            
            # 处理并发送结果
            if not result:
                await self.api.post_group_msg(event.group_id, text="生成手办图片失败，请稍后再试。")
                return
                
            # 根据结果类型处理
            if os.path.exists(result):
                # 本地文件
                await self.api.post_group_msg(event.group_id, image=os.path.abspath(result))
            elif result.startswith("http"):
                # 远程URL
                timestamp = int(time.time())
                cache_path = f"static/figurine_cache/temp_{timestamp}.png"
                if await self.download_image(result, cache_path):
                    await self.api.post_group_msg(event.group_id, image=os.path.abspath(cache_path))
                else:
                    await self.api.post_group_msg(event.group_id, text="图片下载失败，请稍后再试。")
            elif result.startswith("data:image"):
                # Base64图像
                image_data = re.sub(r'^data:image/\w+;base64,', '', result)
                image_bytes = base64.b64decode(image_data)
                
                timestamp = int(time.time())
                temp_path = f"static/figurine_cache/temp_{timestamp}.png"
                with open(temp_path, "wb") as f:
                    f.write(image_bytes)
                
                await self.api.post_group_msg(event.group_id, image=os.path.abspath(temp_path))
            else:
                # 文本内容
                await self.api.post_group_msg(event.group_id, text=f"AI生成的是文本描述而非图像:\n{result}")
        except Exception as e:
            await self.api.post_group_msg(event.group_id, text=f"生成手办图片时出错: {str(e)}")
