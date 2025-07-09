import aiosqlite
import os

class AnimeDB:
    def __init__(self, db_path="data.db"):
        # 确保数据目录存在
        # os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path

    async def init_db(self):
        """初始化数据库，创建订阅表"""
        async with aiosqlite.connect("data.db") as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS anime_subscriptions (
                    group_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.commit()

    async def add_subscription(self, group_id):
        """添加群组订阅"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT OR REPLACE INTO anime_subscriptions (group_id, enabled) VALUES (?, 1)",
                    (str(group_id),)
                )
                await db.commit()
                return True
            except Exception as e:
                print(f"添加订阅失败: {e}")
                return False

    async def remove_subscription(self, group_id):
        """移除群组订阅"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "UPDATE anime_subscriptions SET enabled = 0 WHERE group_id = ?",
                    (str(group_id),)
                )
                await db.commit()
                return True
            except Exception as e:
                print(f"移除订阅失败: {e}")
                return False

    async def get_all_subscriptions(self):
        """获取所有已订阅的群组ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT group_id FROM anime_subscriptions WHERE enabled = 1"
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def is_subscribed(self, group_id):
        """检查群组是否已订阅"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT enabled FROM anime_subscriptions WHERE group_id = ?",
                (str(group_id),)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None and row[0] == 1