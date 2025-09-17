"""
数据库管理插件 - 负责数据库初始化和管理
"""
import asyncio
import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.utils.logger import get_log

bot = CompatibleEnrollment
_log = get_log()

class DatabasePlugin(BasePlugin):
    """数据库管理插件"""
    
    name = "DatabasePlugin"
    version = "1.0.0"
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_manager = None
    
    async def on_load(self):
        """插件加载时初始化数据库"""
        try:
            self._db_manager = DatabaseManager()
            await self._db_manager.initialize()
            _log.info(f"{self.name} 插件已加载，版本: {self.version}")
        except Exception as e:
            _log.error(f"数据库插件初始化失败: {e}")
            raise
    
    @bot.group_event()
    async def on_group_event(self, msg: GroupMessage):
        """处理群组事件，确保群组有默认菜单"""
        try:
            group_id = msg.group_id
            if not await self._db_manager.group_menu_exists(group_id):
                await self._db_manager.create_default_menu_for_group(group_id)
                _log.info(f"为群组 {group_id} 创建了默认菜单")
        except Exception as e:
            _log.error(f"处理群组事件失败: {e}")

class DatabaseManager:
    """数据库管理器 - 统一管理所有数据库操作"""
    
    def __init__(self, db_path: str = "data.db"):
        self.db_path = Path(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化数据库和表结构"""
        async with self._lock:
            if self._initialized:
                return
            
            try:
                # 确保数据库文件存在
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiosqlite.connect(self.db_path) as conn:
                    # 检查并创建群组菜单表
                    await self._create_group_menus_table(conn)
                    
                    # 检查并创建用户表
                    await self._create_users_table(conn)
                    
                    # 检查并创建插件配置表
                    await self._create_plugin_configs_table(conn)
                    
                    await conn.commit()
                
                self._initialized = True
                _log.info("数据库初始化完成")
                
            except Exception as e:
                _log.error(f"数据库初始化失败: {e}")
                raise
    
    async def _create_group_menus_table(self, conn: aiosqlite.Connection) -> None:
        """创建群组菜单表"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER UNIQUE NOT NULL,
                menu_item TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_menus_group_id 
            ON group_menus(group_id)
        """)
    
    async def _create_users_table(self, conn: aiosqlite.Connection) -> None:
        """创建用户表"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                nickname TEXT,
                permissions TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_user_id 
            ON users(user_id)
        """)
    
    async def _create_plugin_configs_table(self, conn: aiosqlite.Connection) -> None:
        """创建插件配置表"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS plugin_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plugin_name TEXT NOT NULL,
                group_id INTEGER,
                config_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(plugin_name, group_id)
            )
        """)
        
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_plugin_configs_plugin_group 
            ON plugin_configs(plugin_name, group_id)
        """)
    
    async def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            result = await cursor.fetchone()
            return result is not None
    
    async def group_menu_exists(self, group_id: int) -> bool:
        """检查群组菜单是否存在"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT id FROM group_menus WHERE group_id = ?",
                (group_id,)
            )
            result = await cursor.fetchone()
            return result is not None
    
    async def get_menus_by_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """获取群组菜单配置"""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT menu_item FROM group_menus WHERE group_id = ?",
                (group_id,)
            )
            result = await cursor.fetchone()
            
            if result:
                try:
                    return json.loads(result[0])
                except json.JSONDecodeError as e:
                    _log.error(f"解析群组菜单JSON失败: {e}")
                    return None
            return None
    
    async def create_default_menu_for_group(self, group_id: int) -> bool:
        """为群组创建默认菜单配置"""
        default_menu = {
            "info": [
                {
                    "title": "HotSearchPlugin",
                    "status": "1",
                    "description": "热搜功能"
                },
                {
                    "title": "WeatherPlugin", 
                    "status": "1",
                    "description": "天气查询"
                },
                {
                    "title": "Setu",
                    "status": "0",
                    "description": "图片功能"
                },
                {
                    "title": "PixivPlugin",
                    "status": "0",
                    "description": "Pixiv图片搜索"
                },
                {
                    "title": "AIDrawing",
                    "status": "1",
                    "description": "AI绘图"
                },
                {
                    "title": "AnimeSearch",
                    "status": "1",
                    "description": "番剧搜索"
                },
                {
                    "title": "MusicOrder",
                    "status": "1",
                    "description": "点歌功能"
                }
            ],
            "created_at": datetime.now().isoformat()
        }
        
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO group_menus (group_id, menu_item, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (group_id, json.dumps(default_menu, ensure_ascii=False)))
                
                await conn.commit()
                return True
                
        except Exception as e:
            _log.error(f"创建默认菜单失败: {e}")
            return False
    
    async def update_feature_status(self, group_id: int, feature_name: str, status: str) -> bool:
        """更新功能开关状态"""
        try:
            # 获取现有菜单
            menu = await self.get_menus_by_group(group_id)
            
            if not menu:
                # 如果没有菜单，先创建默认菜单
                await self.create_default_menu_for_group(group_id)
                menu = await self.get_menus_by_group(group_id)
            
            if not menu:
                return False
            
            # 更新功能状态
            features = menu.get("info", [])
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
            
            menu["info"] = features
            menu["updated_at"] = datetime.now().isoformat()
            
            # 保存到数据库
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    UPDATE group_menus 
                    SET menu_item = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE group_id = ?
                """, (json.dumps(menu, ensure_ascii=False), group_id))
                
                await conn.commit()
                return True
                
        except Exception as e:
            _log.error(f"更新功能状态失败: {e}")
            return False
    
    async def get_plugin_config(self, plugin_name: str, group_id: Optional[int] = None) -> Dict[str, Any]:
        """获取插件配置"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute("""
                    SELECT config_data FROM plugin_configs 
                    WHERE plugin_name = ? AND group_id = ?
                """, (plugin_name, group_id))
                
                result = await cursor.fetchone()
                if result:
                    return json.loads(result[0])
                return {}
                
        except Exception as e:
            _log.error(f"获取插件配置失败: {e}")
            return {}
    
    async def save_plugin_config(self, plugin_name: str, config_data: Dict[str, Any], group_id: Optional[int] = None) -> bool:
        """保存插件配置"""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO plugin_configs 
                    (plugin_name, group_id, config_data, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (plugin_name, group_id, json.dumps(config_data, ensure_ascii=False)))
                
                await conn.commit()
                return True
                
        except Exception as e:
            _log.error(f"保存插件配置失败: {e}")
            return False
    
    async def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """备份数据库"""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data_backup_{timestamp}.db"
            
            backup_path = Path(backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用SQLite的backup功能
            async with aiosqlite.connect(self.db_path) as source:
                async with aiosqlite.connect(backup_path) as target:
                    await source.backup(target)
            
            _log.info(f"数据库已备份到: {backup_path}")
            return True
            
        except Exception as e:
            _log.error(f"数据库备份失败: {e}")
            return False
    
    async def close(self) -> None:
        """关闭数据库连接"""
        # 这里可以添加清理逻辑
        _log.info("数据库管理器已关闭")

    async def _initialize_database(self):
        """初始化数据库的基础表"""
        async with aiosqlite.connect(self.db_path) as conn:
            # 使用统一的表结构，包含id列
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER UNIQUE NOT NULL,
                menu_item TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            await conn.commit()

    async def table_exists(self, table_name):
        """检查表是否存在"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name=?
            """, (table_name,)) as cursor:
                return await cursor.fetchone() is not None

    async def create_default_menu_for_group(self, group_id, menu_file="static/menu.json"):
        """为指定群号创建默认菜单项"""
        try:
            with open(menu_file, "r", encoding="utf-8") as file:
                raw_menu_data = file.read()
            await self.create_menu_for_group(group_id, raw_menu_data)
        except FileNotFoundError:
            print(f"默认菜单文件 '{menu_file}' 未找到。")
        except json.JSONDecodeError:
            print(f"默认菜单文件 '{menu_file}' 格式错误。")

    async def create_menu_for_group(self, group_id, menu_item):
        """为指定群号创建菜单项"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
            INSERT INTO group_menus (group_id, menu_item)
            VALUES (?, ?)
            """, (group_id, menu_item))
            await conn.commit()

    async def get_menus_by_group(self, group_id):
        """获取指定群号的所有菜单项"""
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute("""
            SELECT menu_item, created_at FROM group_menus
            WHERE group_id = ?
            """, (group_id,)) as cursor:
                return await cursor.fetchall()
    async def update_feature_status(self, group_id, title, status):
        """
        更新指定群号的功能状态（开启/关闭）。

        :param group_id: 群号
        :param title: 功能标题
        :param status: 功能状态 ("1" 表示开启, "0" 表示关闭)
        :return: True 如果更新成功，否则 False
        """
        async with aiosqlite.connect(self.db_path) as conn:
            # 查询当前群的菜单配置
            async with conn.execute("SELECT menu_item FROM group_menus WHERE group_id = ?", (group_id,)) as cursor:
                result = await cursor.fetchone()

                if result:
                    # 解析菜单配置
                    menu_item = json.loads(result[0])
                    for item in menu_item.get("info", []):
                        if item.get("title") == title:
                            item["status"] = status  # 更新状态
                            break
                    else:
                        return False  # 如果未找到对应的功能标题，返回 False

                    # 更新数据库
                    updated_menu_item = json.dumps(menu_item)
                    await conn.execute(
                        "UPDATE group_menus SET menu_item = ? WHERE group_id = ?",
                        (updated_menu_item, group_id)
                    )
                    await conn.commit()
                    return True
                else:
                    return False  # 如果未找到群的菜单配置，返回 False

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            await self.conn.close()