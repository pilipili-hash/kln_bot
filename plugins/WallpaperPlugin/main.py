import re
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_forward_msg_ws
from PluginManager.plugin_manager import feature_required
from .wallpaper_utils import fetch_wallpapers, WallpaperCategoryType, WallpaperOrderType

bot = CompatibleEnrollment

class WallpaperPlugin(BasePlugin):
    name = "WallpaperPlugin"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def on_unload(self):
        print(f"{self.name} 插件已卸载")

    @bot.group_event()
    @feature_required(feature_name="wallpaper", raw_message_filter=["/电脑壁纸", "/手机壁纸"])
    async def handle_wallpaper(self, event: GroupMessage):
        """处理壁纸获取"""
        raw_message = event.raw_message.strip()
        parts = re.sub(r"^/(电脑壁纸|手机壁纸)", "", raw_message).strip().split()

        # 检查命令格式是否正确
        if not parts or len(parts) < 1 or not parts[0].isdigit():
            return  # 不处理无效命令

        # 验证分类是否有效
        if int(parts[0]) not in range(1, 10):
            await self.api.post_group_msg(event.group_id, text="无效的分类，请输入 1-9 对应分类")
            return

        # 获取分类和页码
        category = list(WallpaperCategoryType)[int(parts[0]) - 1]
        page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        mobile = "手机壁纸" in raw_message

        # 提示用户正在获取壁纸
        device_type = "手机" if mobile else "电脑"
        await self.api.post_group_msg(event.group_id, text=f"正在获取 {category.value} 分类的{device_type}壁纸，第 {page} 页，请稍候...")

        # 请求壁纸数据
        wallpapers = await fetch_wallpapers(
            category=category,
            skip=(page - 1) * 10,  # 每页 10 个
            mobile=mobile,
        )
        key = "vertical" if mobile else "wallpaper"

        # 发送壁纸或提示未找到
        if wallpapers and key in wallpapers:
            messages = [
                {
                    "type": "node",
                    "data": {
                        "name": "壁纸",
                        "uin": event.self_id,
                        "content": f"[CQ:image,file={item['img']}]",
                    },
                }
                for item in wallpapers[key]
            ]
            await send_group_forward_msg_ws(event.group_id, messages)
        else:
            await self.api.post_group_msg(
                event.group_id,
                text=f"未找到 {category.value} 分类的{device_type}壁纸，请尝试其他分类或稍后再试"
            )
