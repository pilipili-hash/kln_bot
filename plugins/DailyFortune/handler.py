import aiosqlite
import aiohttp
from datetime import datetime

DB_PATH = "data.db"

async def handle_daily_fortune(event, api):
    user_id = event.user_id
    group_id = getattr(event, "group_id", None)  # 获取群号（如果是群消息）
    today = datetime.now().date()

    # 检查用户是否已请求过
    if await has_requested_today(user_id):
        message = "你今天已经抽取过运势了，请明天再试！"
        await send_message(api, group_id, user_id, message)
        return

    # 更新用户请求日期
    await update_request_date(user_id, today)

    # 调用 API 获取运势图片
    api_url = "https://www.hhlqilongzhu.cn/api/tu_yunshi.php"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as response:
            if response.status == 200:
                image_url = str(response.url)
                await send_message(api, group_id, user_id, image_url, is_image=True)
            else:
                message = "获取运势失败，请稍后再试！"
                await send_message(api, group_id, user_id, message)

async def has_requested_today(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_requests (
                user_id INTEGER PRIMARY KEY,
                last_request_date TEXT
            )
        """)
        await db.commit()

        async with db.execute("SELECT last_request_date FROM user_requests WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                last_request_date = datetime.strptime(row[0], "%Y-%m-%d").date()
                return last_request_date == datetime.now().date()
    return False

async def update_request_date(user_id, today):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("REPLACE INTO user_requests (user_id, last_request_date) VALUES (?, ?)", (user_id, today))
        await db.commit()

async def send_message(api, group_id, user_id, content, is_image=False):
    if group_id:
        if is_image:
            await api.post_group_msg(group_id, image=content)
        else:
            await api.post_group_msg(group_id, text=content)

