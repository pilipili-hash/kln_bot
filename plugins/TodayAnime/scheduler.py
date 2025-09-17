import aiohttp
from datetime import datetime
from .database import AnimeDB
from utils.group_forward_msg import send_group_forward_msg_ws, cq_img

class AnimeScheduler:
    def __init__(self, bot_api):
        self.db = AnimeDB()
        self.api = bot_api
    
    async def fetch_anime_data(self):
        """获取番剧数据"""
        url = "https://api.bgm.tv/calendar"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return None

    def format_anime_data(self, data):
        """格式化番剧数据"""
        today = datetime.now().strftime("%A")  # 获取当天的英文星期
        weekday_map = {
            "Monday": "星期一", "Tuesday": "星期二", "Wednesday": "星期三",
            "Thursday": "星期四", "Friday": "星期五", "Saturday": "星期六", "Sunday": "星期日"
        }
        today_cn = weekday_map.get(today, "")
        today_anime = []
        
        for weekday in data:
            if weekday["weekday"]["cn"] == today_cn:
                for item in weekday["items"]:
                    # 检查 item["images"] 是否为 None
                    if not item["images"]:
                        continue
                    image_url = item["images"]["large"]
                    anime_info = {
                        "title": item.get("name_cn", item["name"]),
                        "image": image_url,
                        "air_date": item["air_date"]
                    }
                    today_anime.append(anime_info)
        return today_anime

    async def create_forward_messages(self, anime_list, bot_id):
        """创建转发消息"""
        messages = []
        for anime in anime_list:
            content = (
                f"番剧名称: {anime['title']}\n"
                f"{cq_img(anime['image'])}\n"
                f"更新时间: {anime['air_date']}"
            )
            messages.append({
                "type": "node",
                "data": {
                    "nickname": "今日番剧推送",
                    "user_id": str(bot_id),  # 确保user_id是字符串类型
                    "content": content
                }
            })
        return messages

    async def send_daily_anime(self, bot_id):
        """发送每日番剧到所有订阅群组"""
        # 获取番剧数据
        data = await self.fetch_anime_data()
        if not data:
            print("获取番剧数据失败")
            return
        
        # 格式化番剧数据
        anime_list = self.format_anime_data(data)
        if not anime_list:
            print("今日没有番剧更新")
            return
        
        # 创建消息
        messages = await self.create_forward_messages(anime_list, bot_id)
        
        # 获取所有订阅的群组
        subscribed_groups = await self.db.get_all_subscriptions()
        
        # 向每个订阅的群组发送消息
        for group_id in subscribed_groups:
            try:
                await send_group_forward_msg_ws(group_id=group_id, content=messages)
                print(f"已向群组 {group_id} 推送今日番剧")
            except Exception as e:
                print(f"向群组 {group_id} 推送番剧失败: {e}")