"""
OneBotV11 消息处理工具 - 支持合并转发和消息链处理
"""
import asyncio
import json
import base64
from typing import List, Dict, Any, Optional, Union
from io import BytesIO

from ncatbot.core.element import MessageChain, Text, Image, At, Reply
from ncatbot.core.message import GroupMessage, PrivateMessage
from ncatbot.utils.logger import get_log
from utils.group_forward_msg import MessageSender

_log = get_log()

class OneBotV11MessageHandler:
    """OneBotV11 消息处理器"""
    
    def __init__(self, api=None):
        self.message_sender = MessageSender()
        self.api = api
    
    def extract_images_from_message_chain(self, message_chain: MessageChain) -> List[str]:
        """
        从消息链中提取图片URL
        
        Args:
            message_chain: 消息链对象
            
        Returns:
            List[str]: 图片URL列表
        """
        image_urls = []
        
        try:
            for element in message_chain:
                # 处理 Image 对象
                if isinstance(element, Image):
                    # 从 Image 元素中提取 URL
                    if hasattr(element, 'url') and element.url:
                        image_urls.append(element.url)
                    elif hasattr(element, 'file') and element.file:
                        # 处理 file 字段，可能是 URL 或 base64
                        file_data = element.file
                        if file_data.startswith('http'):
                            image_urls.append(file_data)
                        elif file_data.startswith('base64://'):
                            # 这里可以保存 base64 图片到临时文件或直接使用
                            image_urls.append(file_data)
                    elif hasattr(element, 'data') and element.data:
                        # 处理 data 字段
                        image_data = element.data
                        if 'url' in image_data:
                            image_urls.append(image_data['url'])
                        elif 'file' in image_data:
                            file_path = image_data['file']
                            if file_path.startswith('http'):
                                image_urls.append(file_path)
                            elif file_path.startswith('base64://'):
                                image_urls.append(file_path)
                
                # 处理字典格式的消息元素 (OneBotV11格式)
                elif isinstance(element, dict):
                    if element.get('type') == 'image':
                        data = element.get('data', {})
                        # 提取 URL
                        if 'url' in data:
                            image_urls.append(data['url'])
                        elif 'file' in data:
                            file_data = data['file']
                            if isinstance(file_data, str) and file_data.startswith('http'):
                                image_urls.append(file_data)
                                
        except Exception as e:
            _log.error(f"从消息链提取图片失败: {e}")
        
        return image_urls
    
    def extract_images_from_event(self, event: Union[GroupMessage, PrivateMessage]) -> List[str]:
        """
        从事件中提取图片URL

        Args:
            event: 群消息或私聊消息事件

        Returns:
            List[str]: 图片URL列表
        """
        image_urls = []

        try:
            _log.debug(f"开始提取图片，事件类型: {type(event)}")

            # 方法1: 从 event.message 提取图片（OneBotV11格式）
            if hasattr(event, 'message') and event.message:
                _log.debug(f"事件消息类型: {type(event.message)}, 长度: {len(event.message) if hasattr(event.message, '__len__') else 'N/A'}")

                for i, segment in enumerate(event.message):
                    _log.debug(f"处理消息段 {i}: {type(segment)}")

                    if isinstance(segment, dict) and segment.get('type') == 'image':
                        data = segment.get('data', {})
                        _log.debug(f"图片数据键: {list(data.keys()) if isinstance(data, dict) else 'data不是字典'}")

                        # 优先获取URL字段
                        if isinstance(data, dict):
                            # 尝试多种可能的URL字段
                            url = data.get('url') or data.get('file') or data.get('path')
                            if url:
                                # 处理不同格式的URL
                                if url.startswith('http'):
                                    image_urls.append(url)
                                    _log.debug(f"找到HTTP图片URL: {url}")
                                elif url.startswith('base64://'):
                                    # 对于base64图片，可以考虑转换为临时URL或直接使用
                                    image_urls.append(url)
                                    _log.debug(f"找到base64图片: {url[:50]}...")
                                elif url.startswith('file://'):
                                    # 本地文件路径
                                    image_urls.append(url)
                                    _log.debug(f"找到本地文件: {url}")
                                else:
                                    # 其他格式，尝试作为URL使用
                                    image_urls.append(url)
                                    _log.debug(f"找到其他格式图片: {url}")

            # 方法2: 从消息链中提取（备用方案）
            if hasattr(event, 'message_chain') and event.message_chain:
                chain_images = self.extract_images_from_message_chain(event.message_chain)
                image_urls.extend(chain_images)
                _log.debug(f"从消息链提取到 {len(chain_images)} 张图片")

            # 方法3: 从raw_message中提取CQ码格式的图片（兼容性方案）
            if hasattr(event, 'raw_message') and event.raw_message and not image_urls:
                from utils.cq_to_onebot import extract_images_from_message
                cq_images = extract_images_from_message(event.raw_message)
                image_urls.extend(cq_images)
                _log.debug(f"从CQ码提取到 {len(cq_images)} 张图片")

            _log.debug(f"最终提取到 {len(image_urls)} 张图片: {image_urls}")

        except Exception as e:
            _log.error(f"从事件提取图片失败: {e}")
            import traceback
            _log.error(f"错误详情: {traceback.format_exc()}")

        return image_urls
    
    def create_forward_message_node(
        self, 
        nickname: str, 
        user_id: int, 
        content: Union[str, MessageChain, List]
    ) -> Dict[str, Any]:
        """
        创建合并转发消息节点
        
        Args:
            nickname: 用户昵称
            user_id: 用户ID
            content: 消息内容
            
        Returns:
            Dict: 消息节点
        """
        # 处理不同类型的content
        if isinstance(content, MessageChain):
            # 将 MessageChain 转换为 OneBotV11 格式
            message_data = self._convert_message_chain_to_onebot(content)
        elif isinstance(content, list):
            # 已经是消息段列表
            message_data = content
        else:
            # 纯文本消息
            message_data = [{"type": "text", "data": {"text": str(content)}}]
        
        return {
            "type": "node",
            "data": {
                "name": nickname,
                "uin": str(user_id),
                "content": message_data
            }
        }
    
    def _convert_message_chain_to_onebot(self, message_chain: MessageChain) -> List[Dict[str, Any]]:
        """
        将 MessageChain 转换为 OneBotV11 消息段格式
        
        Args:
            message_chain: 消息链
            
        Returns:
            List[Dict]: OneBotV11 消息段列表
        """
        message_segments = []
        
        try:
            for element in message_chain:
                if isinstance(element, Text):
                    message_segments.append({
                        "type": "text",
                        "data": {"text": element.text}
                    })
                elif isinstance(element, Image):
                    image_data = {"file": element.file} if hasattr(element, 'file') else {}
                    if hasattr(element, 'url') and element.url:
                        image_data["url"] = element.url
                    message_segments.append({
                        "type": "image",
                        "data": image_data
                    })
                elif isinstance(element, At):
                    message_segments.append({
                        "type": "at",
                        "data": {"qq": str(element.target)}
                    })
                elif isinstance(element, Reply):
                    message_segments.append({
                        "type": "reply",
                        "data": {"id": str(element.id)}
                    })
                else:
                    # 处理其他类型的元素，转换为文本
                    message_segments.append({
                        "type": "text",
                        "data": {"text": str(element)}
                    })
                    
        except Exception as e:
            _log.error(f"转换消息链失败: {e}")
            # 降级处理：转换为纯文本
            message_segments = [{
                "type": "text",
                "data": {"text": str(message_chain)}
            }]
        
        return message_segments
    
    async def send_forward_message(
        self, 
        group_id: int, 
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        发送合并转发消息
        
        Args:
            group_id: 群号
            messages: 消息节点列表
            
        Returns:
            bool: 发送是否成功
        """
        try:
            return await self.message_sender.send_group_forward_msg(group_id, messages)
        except Exception as e:
            _log.error(f"发送合并转发消息失败: {e}")
            return False
    
    async def create_forward_message(
        self, 
        group_id: int, 
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        创建合并转发消息（用于与现有插件兼容）
        
        Args:
            group_id: 群号
            messages: 消息节点列表
            
        Returns:
            Dict: 合并转发消息对象
        """
        return {
            "type": "forward",
            "data": {
                "messages": messages
            }
        }
    
    def create_image_message_segment(self, image_data: Union[str, bytes]) -> Dict[str, Any]:
        """
        创建图片消息段
        
        Args:
            image_data: 图片数据（URL、文件路径或base64数据）
            
        Returns:
            Dict: 图片消息段
        """
        if isinstance(image_data, bytes):
            # 字节数据转base64
            b64_data = base64.b64encode(image_data).decode('utf-8')
            return {
                "type": "image",
                "data": {"file": f"base64://{b64_data}"}
            }
        elif isinstance(image_data, str):
            if image_data.startswith('http'):
                # URL图片
                return {
                    "type": "image",
                    "data": {"file": image_data}
                }
            elif image_data.startswith('base64://'):
                # base64图片
                return {
                    "type": "image",
                    "data": {"file": image_data}
                }
            else:
                # 文件路径
                return {
                    "type": "image",
                    "data": {"file": f"file:///{image_data}"}
                }
        else:
            raise ValueError(f"不支持的图片数据类型: {type(image_data)}")
    
    def create_text_message_segment(self, text: str) -> Dict[str, Any]:
        """
        创建文本消息段
        
        Args:
            text: 文本内容
            
        Returns:
            Dict: 文本消息段
        """
        return {
            "type": "text",
            "data": {"text": text}
        }
    
    def create_at_message_segment(self, user_id: int) -> Dict[str, Any]:
        """
        创建@用户消息段
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: @消息段
        """
        return {
            "type": "at",
            "data": {"qq": str(user_id)}
        }
    
    async def send_mixed_message(
        self, 
        group_id: int, 
        message_segments: List[Dict[str, Any]]
    ) -> bool:
        """
        发送混合消息（包含文本、图片等）
        
        Args:
            group_id: 群号
            message_segments: 消息段列表
            
        Returns:
            bool: 发送是否成功
        """
        try:
            return await self.message_sender.send_group_msg(group_id, message_segments)
        except Exception as e:
            _log.error(f"发送混合消息失败: {e}")
            return False

# 全局消息处理器实例
onebot_handler = OneBotV11MessageHandler()

# 便捷函数
def extract_images(event: Union[GroupMessage, PrivateMessage]) -> List[str]:
    """从事件中提取图片URL的便捷函数"""
    return onebot_handler.extract_images_from_event(event)

def create_forward_node(nickname: str, user_id: int, content: Any) -> Dict[str, Any]:
    """创建转发消息节点的便捷函数"""
    return onebot_handler.create_forward_message_node(nickname, user_id, content)

async def send_forward_msg(group_id: int, messages: List[Dict[str, Any]]) -> bool:
    """发送合并转发消息的便捷函数"""
    return await onebot_handler.send_forward_message(group_id, messages)

def create_image_segment(image_data: Union[str, bytes]) -> Dict[str, Any]:
    """创建图片消息段的便捷函数"""
    return onebot_handler.create_image_message_segment(image_data)

def create_text_segment(text: str) -> Dict[str, Any]:
    """创建文本消息段的便捷函数"""
    return onebot_handler.create_text_message_segment(text)

def create_at_segment(user_id: int) -> Dict[str, Any]:
    """创建@消息段的便捷函数"""
    return onebot_handler.create_at_message_segment(user_id)
