"""
消息发送工具模块 - 统一管理各种消息发送功能
"""
import asyncio
import websockets
import json
import html
import re
from typing import Union, List, Dict, Any, Optional
from contextlib import asynccontextmanager

from ncatbot.utils.config import config
from ncatbot.utils.logger import get_log
from ncatbot.core.element import MessageChain

_log = get_log()

class MessageSender:
    """统一消息发送器"""
    
    def __init__(self):
        self._connection_pool = {}
        self._max_retries = 3
        self._retry_delay = 1.0
    
    @asynccontextmanager
    async def _get_websocket_connection(self):
        """获取WebSocket连接的上下文管理器"""
        ws_uri = config.ws_uri
        if not ws_uri:
            raise ValueError("WebSocket URI 未配置，请检查 config.set_ws_uri()")
        
        connection = None
        try:
            connection = await websockets.connect(ws_uri)
            yield connection
        except Exception as e:
            _log.error(f"WebSocket连接失败: {e}")
            raise
        finally:
            if connection:
                await connection.close()
    
    async def _send_with_retry(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """带重试机制的消息发送"""
        last_exception = None
        
        for attempt in range(self._max_retries):
            try:
                async with self._get_websocket_connection() as websocket:
                    await websocket.send(json.dumps(payload))
                    
                    # 循环接收响应，跳过元事件（心跳、生命周期等）
                    max_responses = 15  # 增加最大响应数
                    timeout = 5.0 if payload.get("action") == "send_group_forward_msg" else 2.0  # 合并转发用更长超时

                    for i in range(max_responses):
                        try:
                            # 合并转发消息需要更长的等待时间
                            response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                            result = json.loads(response)

                            # 跳过所有元事件，包括心跳和生命周期事件
                            if result.get("post_type") == "meta_event":
                                _log.debug(f"跳过元事件: {result.get('meta_event_type', 'unknown')}")
                                continue

                            # 记录收到的响应
                            _log.debug(f"收到响应 ({i+1}/{max_responses}): {result}")

                            # 对于合并转发消息，响应可能不同，更宽松地处理
                            if result.get("status") == "ok" or "retcode" in result:
                                _log.debug(f"找到有效响应: {result}")
                                return result
                            else:
                                # 继续等待更多响应
                                continue

                        except asyncio.TimeoutError:
                            _log.debug(f"等待响应超时 ({i+1}/{max_responses})")
                            continue

                    # 如果收到太多无关响应，返回空结果
                    _log.debug("接收响应超时或收到过多无关响应，停止等待")
                    return None
                        
            except Exception as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    _log.warning(f"发送消息失败 (尝试 {attempt + 1}/{self._max_retries}): {e}")
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                else:
                    _log.error(f"发送消息最终失败: {e}")
        
        raise last_exception or Exception("发送消息失败")
    
    async def send_group_forward_msg(self, group_id: int, messages: List[Dict[str, Any]]) -> bool:
        """
        发送群组转发消息
        
        Args:
            group_id: 群组ID
            messages: 消息列表，每个消息包含 nickname, user_id, content
            
        Returns:
            bool: 发送是否成功
        """
        try:
            payload = {
                "action": "send_group_forward_msg",
                "params": {
                    "group_id": group_id,
                    "messages": messages
                }
            }
            
            result = await self._send_with_retry(payload)

            # 对于合并转发，采用更宽松的成功判断
            if result is not None:
                status = result.get("status")
                retcode = result.get("retcode")

                # 记录详细的响应信息
                _log.info(f"合并转发响应: status={status}, retcode={retcode}")

                # 明确的失败状态才认为失败
                if status == "failed" or (retcode is not None and retcode != 0):
                    _log.warning(f"合并转发明确失败: status={status}, retcode={retcode}")
                    return False
                else:
                    _log.info("合并转发成功（有响应）")
                    return True
            else:
                # 对于合并转发，无响应也可能是成功的（消息已发送）
                _log.info("合并转发无响应，但可能已成功发送，等待3秒后假设成功")
                await asyncio.sleep(3)  # 等待3秒让消息有时间发送
                return True
            
        except Exception as e:
            _log.error(f"发送群组转发消息失败: {e}")
            return False
    
    async def send_group_msg(self, group_id: int, content: Union[str, MessageChain]) -> bool:
        """
        发送群组消息
        
        Args:
            group_id: 群组ID
            content: 消息内容
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 如果是MessageChain对象，转换为字符串
            if isinstance(content, MessageChain):
                content = str(content)
            
            payload = {
                "action": "send_group_msg",
                "params": {
                    "group_id": group_id,
                    "message": content
                }
            }
            
            result = await self._send_with_retry(payload)
            return result is not None and result.get("status") == "ok"
            
        except Exception as e:
            _log.error(f"发送群组消息失败: {e}")
            return False
    
    async def send_private_msg(self, user_id: int, content: Union[str, MessageChain]) -> bool:
        """
        发送私聊消息
        
        Args:
            user_id: 用户ID
            content: 消息内容
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 如果是MessageChain对象，转换为字符串
            if isinstance(content, MessageChain):
                content = str(content)
            
            payload = {
                "action": "send_private_msg",
                "params": {
                    "user_id": user_id,
                    "message": content
                }
            }
            
            result = await self._send_with_retry(payload)
            return result is not None and result.get("status") == "ok"
            
        except Exception as e:
            _log.error(f"发送私聊消息失败: {e}")
            return False

# 全局消息发送器实例
_message_sender = MessageSender()

# 兼容旧版本的函数
async def send_group_forward_msg_ws(group_id: int, content: List[Dict[str, Any]]) -> None:
    """发送群组转发消息（兼容旧版本）"""
    await _message_sender.send_group_forward_msg(group_id, content)

async def send_group_msg_cq(group_id: int, content: str) -> None:
    """发送群组消息（兼容旧版本）"""
    await _message_sender.send_group_msg(group_id, content)

def cq_img(url: str) -> str:
    """
    生成CQ码格式的图片消息
    
    Args:
        url: 图片URL
        
    Returns:
        str: CQ码格式的图片消息
    """
    return f"[CQ:image,file={url}]"

def cq_at(user_id: int) -> str:
    """
    生成CQ码格式的@消息
    
    Args:
        user_id: 要@的用户ID
        
    Returns:
        str: CQ码格式的@消息
    """
    return f"[CQ:at,qq={user_id}]"

def cq_face(face_id: int) -> str:
    """
    生成CQ码格式的表情消息
    
    Args:
        face_id: 表情ID
        
    Returns:
        str: CQ码格式的表情消息
    """
    return f"[CQ:face,id={face_id}]"

def get_cqimg(cq_code: str) -> Optional[str]:
    """
    从CQ码格式的图片消息中提取URL
    
    Args:
        cq_code: CQ码格式的字符串
        
    Returns:
        Optional[str]: 解码后的图片URL，如果未找到则返回None
    """
    # 使用正则表达式匹配CQ码中的url部分
    match = re.search(r"url=([^,\]]+)", cq_code)
    if match:
        # 提取匹配到的URL并进行HTML实体解码
        encoded_url = match.group(1)
        decoded_url = html.unescape(encoded_url)
        return decoded_url
    return None

def extract_cq_data(cq_code: str, param: str) -> Optional[str]:
    """
    从CQ码中提取指定参数的值
    
    Args:
        cq_code: CQ码字符串
        param: 要提取的参数名
        
    Returns:
        Optional[str]: 参数值，如果未找到则返回None
    """
    pattern = rf"{param}=([^,\]]+)"
    match = re.search(pattern, cq_code)
    if match:
        return html.unescape(match.group(1))
    return None

class MessageBuilder:
    """消息构建器"""
    
    def __init__(self):
        self.parts = []
    
    def text(self, text: str) -> 'MessageBuilder':
        """添加文本"""
        self.parts.append(text)
        return self
    
    def image(self, url: str) -> 'MessageBuilder':
        """添加图片"""
        self.parts.append(cq_img(url))
        return self
    
    def at(self, user_id: int) -> 'MessageBuilder':
        """添加@用户"""
        self.parts.append(cq_at(user_id))
        return self
    
    def face(self, face_id: int) -> 'MessageBuilder':
        """添加表情"""
        self.parts.append(cq_face(face_id))
        return self
    
    def newline(self) -> 'MessageBuilder':
        """添加换行"""
        self.parts.append("\n")
        return self
    
    def build(self) -> str:
        """构建最终消息"""
        return "".join(self.parts)
    
    def clear(self) -> 'MessageBuilder':
        """清空消息"""
        self.parts.clear()
        return self

# 便捷的消息构建函数
def build_message() -> MessageBuilder:
    """创建新的消息构建器"""
    return MessageBuilder()