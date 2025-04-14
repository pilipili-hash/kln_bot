import aiosqlite
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
            existing_menus = await db_manager.get_menus_by_group(group_id)
            if not existing_menus:
                await db_manager.create_default_menu_for_group(group_id)
                print(f"群号 '{group_id}' 的默认菜单已创建。")
                # await self.api.post_group_msg(group_id, text="菜单已创建")
            
        finally:
            await db_manager.close()

    async def on_load(self):
        db_manager = DatabaseManager()
        try:
            # 检查表是否存在
            if await db_manager.table_exists("group_menus"):
                print("表 'group_menus' 已存在，跳过创建。")
            else:
                print("表 'group_menus' 不存在，正在创建...")
                await db_manager._initialize_database()
        finally:
            await db_manager.close()
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")


class DatabaseManager:
    def __init__(self, db_path="data.db"):
        """初始化数据库连接"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    async def _initialize_database(self):
        """初始化数据库的基础表"""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS group_menus (
                group_id TEXT PRIMARY KEY NOT NULL,
                menu_item TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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