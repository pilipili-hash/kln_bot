"""
CQ码到OneBotV11格式转换工具
用于将旧的CQ码格式转换为OneBotV11消息段格式
"""

import re
import html
from typing import List, Dict, Union, Any


def cq_to_onebot_segments(text: str) -> List[Dict[str, Any]]:
    """
    将包含CQ码的文本转换为OneBotV11消息段数组
    
    Args:
        text: 包含CQ码的文本
        
    Returns:
        OneBotV11消息段数组
    """
    segments = []
    
    # CQ码正则表达式
    cq_pattern = r'\[CQ:([^,\]]+)(?:,([^\]]+))?\]'
    
    last_end = 0
    
    for match in re.finditer(cq_pattern, text):
        # 添加CQ码前的文本
        before_text = text[last_end:match.start()]
        if before_text:
            segments.append({
                "type": "text",
                "data": {"text": before_text}
            })
        
        # 解析CQ码
        cq_type = match.group(1)
        cq_params_str = match.group(2) or ""
        
        # 解析参数
        cq_params = {}
        if cq_params_str:
            # 分割参数，考虑到参数值可能包含逗号
            for param in re.finditer(r'([^,=]+)=([^,]*?)(?=(?:[^,]*?=[^,]*?,)|$)', cq_params_str):
                key = param.group(1).strip()
                value = param.group(2).strip()
                # HTML解码
                value = html.unescape(value)
                cq_params[key] = value
        
        # 转换为OneBotV11格式
        onebot_segment = convert_cq_to_onebot(cq_type, cq_params)
        if onebot_segment:
            segments.append(onebot_segment)
        
        last_end = match.end()
    
    # 添加最后的文本
    remaining_text = text[last_end:]
    if remaining_text:
        segments.append({
            "type": "text", 
            "data": {"text": remaining_text}
        })
    
    return segments


def convert_cq_to_onebot(cq_type: str, params: Dict[str, str]) -> Dict[str, Any]:
    """
    将单个CQ码转换为OneBotV11消息段
    
    Args:
        cq_type: CQ码类型
        params: CQ码参数
        
    Returns:
        OneBotV11消息段
    """
    if cq_type == "image":
        # 图片消息段
        file_param = params.get("file", "")
        url_param = params.get("url", "")
        
        # 优先使用file参数，其次是url参数
        image_source = file_param or url_param
        
        return {
            "type": "image",
            "data": {"file": image_source}
        }
    
    elif cq_type == "at":
        # @提及消息段
        qq = params.get("qq", "")
        return {
            "type": "at",
            "data": {"qq": qq}
        }
    
    elif cq_type == "record":
        # 语音消息段
        file_param = params.get("file", "")
        return {
            "type": "record",
            "data": {"file": file_param}
        }
    
    elif cq_type == "reply":
        # 回复消息段
        id_param = params.get("id", "")
        return {
            "type": "reply",
            "data": {"id": id_param}
        }
    
    elif cq_type == "face":
        # 表情消息段
        id_param = params.get("id", "")
        return {
            "type": "face",
            "data": {"id": id_param}
        }
    
    # 其他类型的CQ码，转换为text
    return {
        "type": "text",
        "data": {"text": f"[{cq_type}]"}
    }


def create_image_segment(file_source: str) -> Dict[str, Any]:
    """
    创建图片消息段
    
    Args:
        file_source: 图片来源（URL、base64、文件路径等）
        
    Returns:
        OneBotV11图片消息段
    """
    return {
        "type": "image",
        "data": {"file": file_source}
    }


def create_text_segment(text: str) -> Dict[str, Any]:
    """
    创建文本消息段
    
    Args:
        text: 文本内容
        
    Returns:
        OneBotV11文本消息段
    """
    return {
        "type": "text",
        "data": {"text": text}
    }


def create_at_segment(user_id: Union[str, int]) -> Dict[str, Any]:
    """
    创建@提及消息段
    
    Args:
        user_id: 用户ID
        
    Returns:
        OneBotV11@提及消息段
    """
    return {
        "type": "at",
        "data": {"qq": str(user_id)}
    }


def create_forward_node(nickname: str, user_id: Union[str, int], content: Union[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    创建合并转发节点
    
    Args:
        nickname: 发送者昵称
        user_id: 发送者ID
        content: 消息内容（文本或消息段数组）
        
    Returns:
        OneBotV11合并转发节点
    """
    # 确保user_id是字符串
    user_id_str = str(user_id)
    
    # 处理内容
    if isinstance(content, str):
        # 如果是字符串，检查是否包含CQ码
        if "[CQ:" in content:
            content_segments = cq_to_onebot_segments(content)
        else:
            content_segments = [create_text_segment(content)]
    else:
        # 如果已经是消息段数组，直接使用
        content_segments = content
    
    return {
        "type": "node",
        "data": {
            "nickname": nickname,
            "user_id": user_id_str,
            "content": content_segments
        }
    }


def extract_images_from_message(raw_message: str) -> List[str]:
    """
    从消息中提取图片URL或文件路径
    
    Args:
        raw_message: 原始消息内容
        
    Returns:
        图片来源列表
    """
    images = []
    
    # 匹配CQ图片码
    cq_image_pattern = r'\[CQ:image,(?:[^,\]]*,)?(?:file=([^,\]]+)|url=([^,\]]+))'
    
    for match in re.finditer(cq_image_pattern, raw_message):
        file_param = match.group(1)
        url_param = match.group(2)
        
        # 优先使用file参数
        image_source = file_param or url_param
        if image_source:
            # HTML解码
            image_source = html.unescape(image_source)
            images.append(image_source)
    
    return images


def extract_at_users(raw_message: str) -> List[str]:
    """
    从消息中提取被@的用户ID

    Args:
        raw_message: 原始消息内容

    Returns:
        用户ID列表
    """
    users = []

    # 匹配CQ @码，支持带有name参数的格式
    at_pattern = r'\[CQ:at,qq=(\d+)(?:,name=[^\]]+)?\]'

    for match in re.finditer(at_pattern, raw_message):
        user_id = match.group(1)
        users.append(user_id)

    return users


def remove_cq_codes(text: str) -> str:
    """
    移除文本中的所有CQ码，保留纯文本
    
    Args:
        text: 包含CQ码的文本
        
    Returns:
        移除CQ码后的纯文本
    """
    # 移除所有CQ码
    cq_pattern = r'\[CQ:[^\]]+\]'
    clean_text = re.sub(cq_pattern, '', text)
    
    # 清理多余的空白字符
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text


def cq_image_to_onebot(cq_image: str) -> Dict[str, Any]:
    """
    将CQ图片码转换为OneBotV11图片消息段
    
    Args:
        cq_image: CQ图片码字符串
        
    Returns:
        OneBotV11图片消息段
    """
    # 提取file参数
    file_match = re.search(r'\[CQ:image,(?:[^,\]]*,)?file=([^,\]]+)', cq_image)
    url_match = re.search(r'\[CQ:image,(?:[^,\]]*,)?url=([^,\]]+)', cq_image)
    
    file_source = ""
    if file_match:
        file_source = html.unescape(file_match.group(1))
    elif url_match:
        file_source = html.unescape(url_match.group(1))
    
    return create_image_segment(file_source)


# 常用的CQ码转换函数别名
def cq_img(file_source: str) -> str:
    """
    生成CQ图片码（向后兼容）
    注意：建议使用create_image_segment创建OneBotV11格式
    """
    return f"[CQ:image,file={file_source}]"


def onebot_img(file_source: str) -> Dict[str, Any]:
    """
    创建OneBotV11图片消息段的便捷函数
    """
    return create_image_segment(file_source)