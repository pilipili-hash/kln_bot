import sqlite3
import json
from datetime import datetime

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage

bot = CompatibleEnrollment  # 兼容回调函数注册器


class DatabasePlugin(BasePlugin):
    name = "DatabasePlugin"  # 插件名称
    version = "0.0.1"  # 插件版本
    @bot.group_event()
    async def on_group_event(self, msg: GroupMessage):
        group_id = msg.group_id
        db_manager = DatabaseManager()
        try:
            # 检查是否已有菜单项
            existing_menus = db_manager.get_menus_by_group(group_id)
            if not existing_menus:
                db_manager.create_default_menu_for_group(group_id)
                print(f"群号 '{group_id}' 的默认菜单已创建。")
                # await self.api.post_group_msg(group_id, text="菜单已创建")
            
        finally:
            db_manager.close()

    async def on_load(self):
        db_manager = DatabaseManager()
        try:
            # 检查表是否存在
            if db_manager.table_exists("group_menus"):
                print("表 'group_menus' 已存在，跳过创建。")
            else:
                print("表 'group_menus' 不存在，正在创建...")
                db_manager._initialize_database()
        finally:
            db_manager.close()
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
class DatabaseManager:
    def __init__(self, db_path="data.db"):
        """初始化数据库连接"""
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._initialize_database()

    def _initialize_database(self):
        """初始化数据库的基础表"""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_menus (
            group_id TEXT PRIMARY KEY NOT NULL,
            menu_item TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()
    def table_exists(self, table_name):
        """检查表是否存在"""
        self.cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name=?
        """, (table_name,))
        return self.cursor.fetchone() is not None
    def create_default_menu_for_group(self, group_id, menu_file="static/menu.json"):
        """为指定群号创建默认菜单项"""
        try:
            with open(menu_file, "r", encoding="utf-8") as file:
                raw_menu_data = file.read()
            self.create_menu_for_group(group_id, raw_menu_data)
        except FileNotFoundError:
            print(f"默认菜单文件 '{menu_file}' 未找到。")
        except json.JSONDecodeError:
            print(f"默认菜单文件 '{menu_file}' 格式错误。")

    def create_menu_for_group(self, group_id, menu_item):
        """为指定群号创建菜单项"""
        self.cursor.execute("""
        INSERT INTO group_menus (group_id, menu_item)
        VALUES (?, ?)
        """, (group_id, menu_item))
        self.conn.commit()

    def get_menus_by_group(self, group_id):
        """获取指定群号的所有菜单项"""
        self.cursor.execute("""
        SELECT menu_item, created_at FROM group_menus
        WHERE group_id = ?
        """, (group_id,))
        return self.cursor.fetchall()

    def close(self):
        """关闭数据库连接"""
        self.conn.close()