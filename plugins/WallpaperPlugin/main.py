import re
import logging
import time
import asyncio
from typing import Dict, List, Optional
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_forward_msg_ws
from PluginManager.plugin_manager import feature_required
from .wallpaper_utils import fetch_wallpapers, WallpaperCategoryType, WallpaperOrderType

bot = CompatibleEnrollment
_log = logging.getLogger(__name__)

class WallpaperPlugin(BasePlugin):
    name = "WallpaperPlugin"
    version = "2.0.0"

    async def on_load(self):
        # 初始化插件属性
        self.request_count = 0
        self.pc_request_count = 0
        self.mobile_request_count = 0
        self.error_count = 0
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # 请求间隔限制
        self.category_stats = {}  # 分类统计

        _log.info(f"{self.name} v{self.version} 插件已加载")
        _log.info("壁纸获取功能已启用")

    async def on_unload(self):
        _log.info(f"{self.name} 插件已卸载")

    async def _check_rate_limit(self):
        """检查请求频率限制"""
        current_time = time.time()
        if current_time - self.last_request_time < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - (current_time - self.last_request_time)
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()

    def _get_category_display_name(self, category: WallpaperCategoryType) -> str:
        """获取分类的中文显示名称"""
        category_map = {
            WallpaperCategoryType.landscape: "风景",
            WallpaperCategoryType.girl: "美女",
            WallpaperCategoryType.game: "游戏",
            WallpaperCategoryType.anime: "动漫",
            WallpaperCategoryType.mechanics: "汽车",
            WallpaperCategoryType.animal: "动物",
            WallpaperCategoryType.drawn: "植物",
            WallpaperCategoryType.boy: "美食",
            WallpaperCategoryType.text: "其他"
        }
        return category_map.get(category, category.value)

    async def get_statistics(self) -> str:
        """获取使用统计"""
        success_rate = 0
        if self.request_count > 0:
            success_rate = ((self.request_count - self.error_count) / self.request_count) * 100

        # 获取最热门的分类
        popular_category = "暂无数据"
        if self.category_stats:
            most_used = max(self.category_stats.items(), key=lambda x: x[1])
            popular_category = f"{self._get_category_display_name(most_used[0])} ({most_used[1]}次)"

        return f"""📊 壁纸获取统计

🖥️ 电脑壁纸: {self.pc_request_count}次
📱 手机壁纸: {self.mobile_request_count}次
🎯 总请求数: {self.request_count}次
❌ 失败次数: {self.error_count}次
✅ 成功率: {success_rate:.1f}%
🔥 热门分类: {popular_category}
⏱️ 请求间隔: {self.rate_limit_delay}秒"""

    @bot.group_event()
    async def handle_wallpaper(self, event: GroupMessage):
        """处理壁纸获取"""
        raw_message = event.raw_message.strip()

        try:
            # 处理统计命令
            if raw_message == "/壁纸统计":
                try:
                    stats = await self.get_statistics()
                    await self.api.post_group_msg(event.group_id, text=stats)
                except Exception as e:
                    _log.error(f"获取统计信息时出错: {e}")
                    await self.api.post_group_msg(event.group_id, text="❌ 获取统计信息失败")
                return

            # 处理帮助命令
            if raw_message == "/壁纸帮助":
                help_text = """🖼️ 壁纸获取帮助

📝 基本命令：
• /电脑壁纸 分类 [页码] - 获取电脑壁纸
• /手机壁纸 分类 [页码] - 获取手机壁纸
• /壁纸统计 - 查看使用统计
• /壁纸帮助 - 显示此帮助信息

🎨 分类列表：
1 - 风景 🌄  2 - 美女 👩  3 - 游戏 🎮
4 - 动漫 🎭  5 - 汽车 🚗  6 - 动物 🐾
7 - 植物 🌿  8 - 美食 🍕  9 - 其他 📦

💡 使用示例：
/电脑壁纸 1
/手机壁纸 4 2
/壁纸统计

⚠️ 注意事项：
• 每页显示10张壁纸
• 请求间隔1秒，避免频繁调用
• 图片加载可能需要一些时间
• 支持高清壁纸下载"""

                await self.api.post_group_msg(event.group_id, text=help_text)
                return

            # 只处理以 /电脑壁纸 或 /手机壁纸 开头的消息
            if not (raw_message.startswith("/电脑壁纸") or raw_message.startswith("/手机壁纸")):
                return

            await self._check_rate_limit()

            parts = re.sub(r"^/(电脑壁纸|手机壁纸)", "", raw_message).strip().split()

            # 检查命令格式是否正确
            if not parts or len(parts) < 1 or not parts[0].isdigit():
                await self.api.post_group_msg(event.group_id, text="❌ 请输入正确格式\n💡 格式：/电脑壁纸 分类数字 [页码]\n📝 示例：/电脑壁纸 1 或 /手机壁纸 4 2\n\n🎨 分类：1-风景 2-美女 3-游戏 4-动漫 5-汽车 6-动物 7-植物 8-美食 9-其他")
                return

            # 验证分类是否有效
            if int(parts[0]) not in range(1, 10):
                await self.api.post_group_msg(event.group_id, text="❌ 无效的分类，请输入 1-9 对应分类\n💡 发送 /壁纸帮助 查看详细分类说明")
                return

            # 获取分类和页码
            category = list(WallpaperCategoryType)[int(parts[0]) - 1]
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            mobile = "手机壁纸" in raw_message

            # 更新统计
            self.request_count += 1
            if mobile:
                self.mobile_request_count += 1
            else:
                self.pc_request_count += 1

            # 更新分类统计
            if category not in self.category_stats:
                self.category_stats[category] = 0
            self.category_stats[category] += 1

            # 提示用户正在获取壁纸
            device_type = "手机" if mobile else "电脑"
            category_name = self._get_category_display_name(category)

            _log.info(f"用户 {event.user_id} 在群 {event.group_id} 请求{device_type}壁纸: {category_name}, 页码: {page}")
            await self.api.post_group_msg(event.group_id, text=f"🔍 正在获取「{category_name}」分类的{device_type}壁纸，第 {page} 页，请稍候...")

            # 请求壁纸数据
            wallpapers = await fetch_wallpapers(
                category=category,
                skip=(page - 1) * 10,  # 每页 10 个
                mobile=mobile,
            )
            key = "vertical" if mobile else "wallpaper"

            # 发送壁纸或提示未找到
            if wallpapers and key in wallpapers and wallpapers[key]:
                messages = [
                    {
                        "type": "node",
                        "data": {
                            "nickname": f"{category_name}壁纸",
                            "user_id": str(event.self_id),  # 修复：使用user_id字段且确保是字符串
                            "content": f"[CQ:image,file={item['img']}]",
                        },
                    }
                    for item in wallpapers[key]
                ]
                await send_group_forward_msg_ws(event.group_id, messages)
                _log.info(f"成功返回 {len(wallpapers[key])} 张{device_type}壁纸")
            else:
                self.error_count += 1
                await self.api.post_group_msg(
                    event.group_id,
                    text=f"❌ 未找到「{category_name}」分类的{device_type}壁纸\n💡 请尝试其他分类或稍后再试\n📝 发送 /壁纸帮助 查看所有分类"
                )

        except Exception as e:
            self.error_count += 1
            _log.error(f"处理壁纸请求时出错: {e}")
            await self.api.post_group_msg(event.group_id, text="❌ 系统错误，请稍后再试")
