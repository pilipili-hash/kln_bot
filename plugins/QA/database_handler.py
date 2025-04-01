import aiosqlite
from ncatbot.utils.logger import get_log
import random
from fuzzywuzzy import fuzz

_log = get_log()

class QADatabaseHandler:
    def __init__(self, db_path="data.db"):
        self.db_path = db_path

    async def create_table(self, group_id: int) -> bool:
        """为指定群创建一个新的问答表，表名为 ck_群号。"""
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        match_type TEXT NOT NULL DEFAULT 'exact'
                    )
                """)
                await db.commit()
            _log.info(f"表 {table_name} 创建成功。")
            return True
        except aiosqlite.Error as e:
            _log.error(f"创建表 {table_name} 失败: {e}")
            return False

    async def table_exists(self, group_id: int) -> bool:
        """检查指定群的问答表是否存在。"""
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                ) as cursor:
                    result = await cursor.fetchone()
                    return result is not None
        except aiosqlite.Error as e:
            _log.error(f"检查表 {table_name} 是否存在时出错: {e}")
            return False

    async def save_qa(self, group_id: int, question: str, answer: str, match_type: str = 'exact') -> bool:
        """保存问答到指定群的问答表中。"""
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    f"INSERT INTO {table_name} (question, answer, match_type) VALUES (?, ?, ?)", (question, answer, match_type)
                )
                await db.commit()
            _log.info(f"问答已保存到表 {table_name}。")
            return True
        except aiosqlite.Error as e:
            _log.error(f"保存问答到表 {table_name} 失败: {e}")
            return False

    async def get_answers(self, group_id: int, question: str, match_type: str = 'exact') -> list[str]:
        """从指定群的问答表中查找匹配的答案列表。"""
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    f"SELECT answer FROM {table_name} WHERE question = ? AND match_type = ?", (question, match_type)
                ) as cursor:
                    results = await cursor.fetchall()
                    return [row[0] for row in results] if results else []
        except aiosqlite.Error as e:
            _log.error(f"从表 {table_name} 获取答案失败: {e}")
            return []

    async def get_answer(self, group_id: int, question: str) -> str | None:
        """从指定群的问答表中查找精确匹配的答案，并随机返回一个。"""
        answers = await self.get_answers(group_id, question, match_type='exact')
        return random.choice(answers) if answers else None

    async def get_answer_fuzzy(self, group_id: int, question: str, threshold: int = 60) -> str | None:
        """
        从指定群的问答表中查找模糊匹配的答案，并随机返回一个。
        使用 fuzzywuzzy 库进行模糊匹配。
        :param threshold: 匹配阈值，默认为 60。
        """
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    f"SELECT question, answer FROM {table_name} WHERE match_type = 'fuzzy'"
                ) as cursor:
                    results = await cursor.fetchall()
                    
                    # 使用 fuzzywuzzy 进行模糊匹配
                    best_match = None
                    best_ratio = 0
                    for qa in results:
                        ratio = fuzz.partial_ratio(question, qa[0])
                        if ratio > best_ratio and ratio >= threshold:
                            best_ratio = ratio
                            best_match = qa[1]  # 答案

                    return best_match if best_match else None
        except aiosqlite.Error as e:
            _log.error(f"从表 {table_name} 获取模糊匹配答案失败: {e}")
            return None

    async def get_all_qa(self, group_id: int) -> list[dict[str, str]]:
        """获取指定群的所有问答。"""
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(f"SELECT question, answer FROM {table_name}") as cursor:
                    results = await cursor.fetchall()
                    return [{"question": row[0], "answer": row[1]} for row in results]
        except aiosqlite.Error as e:
            _log.error(f"从表 {table_name} 获取所有问答失败: {e}")
            return []

    async def delete_qa(self, group_id: int, index: int) -> bool:
        """删除指定群的指定序号的问答。"""
        table_name = f"ck_{group_id}"
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 获取所有问答
                qa_list = await self.get_all_qa(group_id)
                if not qa_list or index <= 0 or index > len(qa_list):
                    return False  # 序号无效

                # 获取要删除的问答的id
                qa_to_delete = qa_list[index - 1]
                
                # 删除问答
                await db.execute(
                    f"DELETE FROM {table_name} WHERE question = ? AND answer = ?", (qa_to_delete["question"], qa_to_delete["answer"])
                )
                await db.commit()
                _log.info(f"从表 {table_name} 删除问答成功。")
                return True
        except aiosqlite.Error as e:
            _log.error(f"从表 {table_name} 删除问答失败: {e}")
            return False
