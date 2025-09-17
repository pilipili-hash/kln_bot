"""
插件管理器 - 统一管理插件功能开关和权限控制
"""
import asyncio
import aiosqlite
import json
import re
from functools import wraps
from typing import List, Dict, Any, Optional, Union, Callable
from pathlib import Path

from ncatbot.utils.logger import get_log
from utils.config_manager import get_config

_log = get_log()

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data.db"):
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
    
    async def execute_query(self, query: str, params: tuple = ()) -> Optional[Any]:
        """执行数据库查询"""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as conn:
                    async with conn.execute(query, params) as cursor:
                        return await cursor.fetchone()
            except Exception as e:
                _log.error(f"数据库查询失败: {e}")
                return None
    
    async def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """批量执行数据库操作"""
        async with self._lock:
            try:
                async with aiosqlite.connect(self.db_path) as conn:
                    await conn.executemany(query, params_list)
                    await conn.commit()
                    return True
            except Exception as e:
                _log.error(f"批量数据库操作失败: {e}")
                return False

class PermissionManager:
    """权限管理器"""
    
    @staticmethod
    async def is_master(user_id: int) -> bool:
        """
        检查用户是否为管理员
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            bool: 是否为管理员
        """
        try:
            master_list = get_config("master", [])
            return user_id in master_list
        except Exception as e:
            _log.error(f"检查管理员权限失败: {e}")
            return False
    
    @staticmethod
    async def is_group_admin(group_id: int, user_id: int) -> bool:
        """
        检查用户是否为群管理员（需要通过API查询）
        
        Args:
            group_id: 群号
            user_id: 用户QQ号
            
        Returns:
            bool: 是否为群管理员
        """
        # TODO: 实现群管理员检查逻辑
        # 这里需要调用机器人API来获取群成员信息
        return False

class FeatureManager:
    """功能管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def is_feature_enabled(self, group_id: int, feature_name: str) -> bool:
        """
        检查群组中指定功能是否开启
        
        Args:
            group_id: 群号
            feature_name: 功能名称
            
        Returns:
            bool: 功能是否开启
        """
        try:
            query = "SELECT menu_item FROM group_menus WHERE group_id = ?"
            result = await self.db_manager.execute_query(query, (group_id,))
            
            if result:
                try:
                    menu_item = json.loads(result[0])
                    features = menu_item.get("info", [])
                    
                    for feature in features:
                        if feature.get("title") == feature_name:
                            return feature.get("status") == "1"
                    
                    # 如果没有找到该功能，默认开启
                    return True
                    
                except json.JSONDecodeError as e:
                    _log.error(f"解析功能配置JSON失败: {e}")
                    
            # 如果没有配置记录，默认开启
            return True
            
        except Exception as e:
            _log.error(f"检查功能状态失败: {e}")
            return True  # 出错时默认开启
    
    async def set_feature_status(self, group_id: int, feature_name: str, enabled: bool) -> bool:
        """
        设置群组中指定功能的开关状态
        
        Args:
            group_id: 群号
            feature_name: 功能名称
            enabled: 是否开启
            
        Returns:
            bool: 操作是否成功
        """
        try:
            status = "1" if enabled else "0"
            
            # 获取现有配置
            query = "SELECT menu_item FROM group_menus WHERE group_id = ?"
            result = await self.db_manager.execute_query(query, (group_id,))
            
            if result:
                try:
                    menu_item = json.loads(result[0])
                    features = menu_item.get("info", [])
                    
                    # 查找并更新功能状态
                    feature_found = False
                    for feature in features:
                        if feature.get("title") == feature_name:
                            feature["status"] = status
                            feature_found = True
                            break
                    
                    # 如果功能不存在，添加新功能
                    if not feature_found:
                        features.append({
                            "title": feature_name,
                            "status": status,
                            "description": f"{feature_name}功能"
                        })
                    
                    # 更新数据库
                    menu_item["info"] = features
                    update_query = "UPDATE group_menus SET menu_item = ? WHERE group_id = ?"
                    await self.db_manager.execute_query(
                        update_query, 
                        (json.dumps(menu_item, ensure_ascii=False), group_id)
                    )
                    
                    return True
                    
                except json.JSONDecodeError as e:
                    _log.error(f"解析功能配置JSON失败: {e}")
                    return False
            else:
                # 创建新的配置记录
                menu_item = {
                    "info": [{
                        "title": feature_name,
                        "status": status,
                        "description": f"{feature_name}功能"
                    }]
                }
                
                insert_query = "INSERT INTO group_menus (group_id, menu_item) VALUES (?, ?)"
                await self.db_manager.execute_query(
                    insert_query,
                    (group_id, json.dumps(menu_item, ensure_ascii=False))
                )
                
                return True
                
        except Exception as e:
            _log.error(f"设置功能状态失败: {e}")
            return False

# 全局实例
_db_manager = DatabaseManager()
_permission_manager = PermissionManager()
_feature_manager = FeatureManager(_db_manager)

def feature_required(
    feature_name: str, 
    commands: Optional[Union[str, List[str], re.Pattern]] = None,
    require_admin: bool = False
):
    """
    功能权限装饰器
    
    Args:
        feature_name: 功能名称
        commands: 触发命令（字符串、列表或正则表达式）
        require_admin: 是否需要管理员权限
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, event, *args, **kwargs):
            try:
                group_id = getattr(event, "group_id", None)
                user_id = getattr(event, "user_id", None)
                raw_message = getattr(event, "raw_message", "").strip()
                
                # 检查命令匹配
                if commands:
                    command_matched = False
                    
                    if isinstance(commands, str):
                        command_matched = raw_message.startswith(commands)
                    elif isinstance(commands, list):
                        command_matched = any(raw_message.startswith(cmd) for cmd in commands)
                    elif isinstance(commands, re.Pattern):
                        command_matched = bool(commands.match(raw_message))
                    
                    if not command_matched:
                        return
                
                # 检查管理员权限
                if require_admin and user_id:
                    if not await _permission_manager.is_master(user_id):
                        error_msg = "您没有权限执行此操作"
                        if hasattr(self, "api"):
                            if group_id:
                                await self.api.post_group_msg(group_id, text=error_msg)
                            else:
                                await self.api.post_private_msg(user_id, text=error_msg)
                        return
                
                # 检查功能是否开启
                if group_id and not await _feature_manager.is_feature_enabled(group_id, feature_name):
                    error_msg = f"功能 '{feature_name}' 未开启"
                    if hasattr(self, "api"):
                        await self.api.post_group_msg(group_id, text=error_msg)
                    return
                
                # 执行原函数
                return await func(self, event, *args, **kwargs)
                
            except Exception as e:
                _log.error(f"装饰器执行失败: {e}")
                return
                
        return wrapper
    return decorator

def master_required(commands: Optional[Union[str, List[str]]] = None):
    """
    管理员权限装饰器
    
    Args:
        commands: 需要管理员权限的命令列表
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, event, *args, **kwargs):
            try:
                user_id = getattr(event, "user_id", None)
                raw_message = getattr(event, "raw_message", "").strip()
                
                # 检查是否为指定命令
                if commands:
                    command_matched = False
                    if isinstance(commands, str):
                        command_matched = raw_message.startswith(commands)
                    elif isinstance(commands, list):
                        command_matched = any(raw_message.startswith(cmd) for cmd in commands)
                    
                    if not command_matched:
                        return await func(self, event, *args, **kwargs)
                
                # 检查管理员权限
                if not user_id or not await _permission_manager.is_master(user_id):
                    error_msg = "您没有权限执行此操作"
                    if hasattr(self, "api"):
                        if hasattr(event, "group_id"):
                            await self.api.post_group_msg(event.group_id, text=error_msg)
                        else:
                            await self.api.post_private_msg(user_id, text=error_msg)
                    return
                
                # 执行原函数
                return await func(self, event, *args, **kwargs)
                
            except Exception as e:
                _log.error(f"管理员权限检查失败: {e}")
                return
                
        return wrapper
    return decorator

# 向后兼容的函数
async def fetch_from_db(query: str, params: tuple = ()) -> Optional[Any]:
    """向后兼容的数据库查询函数"""
    return await _db_manager.execute_query(query, params)

async def is_feature_enabled(group_id: int, title: str) -> bool:
    """向后兼容的功能检查函数"""
    return await _feature_manager.is_feature_enabled(group_id, title)

async def is_master(user_id: int) -> bool:
    """向后兼容的管理员检查函数"""
    return await _permission_manager.is_master(user_id)
