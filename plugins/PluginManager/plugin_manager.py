import aiosqlite
import json
from functools import wraps
import yaml
import os
import aiofiles
from ncatbot.utils.logger import get_log

_log = get_log()

async def load_yaml_file(file_path, default=None):
    """
    异步加载 YAML 文件并返回其内容。
    
    :param file_path: 文件路径
    :param default: 如果文件不存在或解析失败，返回的默认值
    :return: 文件内容或默认值
    """
    try:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as file:
            content = await file.read()
            return yaml.safe_load(content)
    except FileNotFoundError:
        _log.info(f"文件未找到: {file_path}")
    except yaml.YAMLError as e:
        _log.info(f"解析 YAML 文件出错: {e}")
    return default

async def get_config_value(key, default=None):
    """
    异步从配置文件中获取指定配置项的值。
    
    :param key: 配置项的名称
    :param default: 如果配置项不存在，返回的默认值
    :return: 配置项的值，如果未找到则返回 default
    """
    config_path = os.path.join(os.getcwd(), "config.yaml")
    config_data = await load_yaml_file(config_path, {})
    return config_data.get(key, default)

async def fetch_from_db(query, params=()):
    """
    异步执行数据库查询并返回结果。
    
    :param query: SQL 查询语句
    :param params: 查询参数
    :return: 查询结果
    """
    db_path = "data.db"  # 数据库路径
    try:
        async with aiosqlite.connect(db_path) as conn:
            async with conn.execute(query, params) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        _log.info(f"数据库操作出错: {e}")
        return None

async def is_feature_enabled(group_id, title):
    """
    根据群号和功能标题判断功能是否开启（异步版本）。
    
    :param group_id: 群号
    :param title: 功能标题
    :return: True 如果功能开启 (status 为 "1")，否则 False
    """
    query = "SELECT menu_item FROM group_menus WHERE group_id = ?"
    result = await fetch_from_db(query, (group_id,))
    if result:
        try:
            menu_item = json.loads(result[0])
            return any(item.get("title") == title and item.get("status") == "1" for item in menu_item.get("info", []))
        except json.JSONDecodeError as e:
            _log.info(f"解析 JSON 数据出错: {e}")
    return False

def feature_required(title):
    """
    装饰器：检查功能是否开启。
    如果功能未开启，则在函数内部返回提示消息。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, event, *args, **kwargs):
            # 检查是否需要执行功能检查
            if event.raw_message == title:  # 仅在匹配消息时检查功能
                group_id = getattr(event, "group_id", None) or getattr(event, "user_id", None)
                if not await is_feature_enabled(group_id, title):
                    # 如果功能未开启，发送提示消息并终止执行
                    message = f"功能 '{title}' 未开启"
                    if hasattr(event, "group_id"):
                        await self.api.post_group_msg(event.group_id, text=message)
                    elif hasattr(event, "user_id"):
                        await self.api.post_private_msg(event.user_id, text=message)
                    return
            # 功能已开启或不需要检查，继续执行原函数
            return await func(self, event, *args, **kwargs)
        return wrapper
    return decorator

async def is_master(user_id):
    """
    检查用户是否为管理员。
    
    :param user_id: 用户 QQ 号
    :return: True 如果是管理员，否则 False
    """
    master_list = await get_config_value("master", [])
    return user_id in master_list

def master_required(commands=None):
    """
    装饰器：检查用户是否为管理员，并仅在特定消息触发时执行。
    
    :param commands: 触发检查的特定消息列表（如 ['/开启', '/关闭']）。
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, event, *args, **kwargs):
            # 获取消息内容
            raw_message = getattr(event, "raw_message", "").strip()
            
            # 如果指定了 commands，则仅在消息匹配时触发
            if commands and not any(raw_message.startswith(cmd) for cmd in commands):
                return await func(self, event, *args, **kwargs)
            
            # 检查是否为管理员
            user_id = getattr(event, "user_id", None)
            if not user_id or not await is_master(user_id):
                # 如果不是管理员，发送提示消息并终止执行
                message = "您没有权限执行此操作"
                if hasattr(event, "group_id"):
                    await self.api.post_group_msg(event.group_id, text=message)
                elif hasattr(event, "user_id"):
                    await self.api.post_private_msg(event.user_id, text=message)
                return
            
            # 如果是管理员，继续执行原函数
            return await func(self, event, *args, **kwargs)
        return wrapper
    return decorator