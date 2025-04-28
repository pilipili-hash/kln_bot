import re
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_forward_msg_ws
from utils.config_manager import get_config
from PluginManager.plugin_manager import feature_required
from .pixiv_utils import initialize_pixiv_api, fetch_illusts, fetch_ranking, format_illusts

bot = CompatibleEnrollment

class PixivPlugin(BasePlugin):
    name = "PixivPlugin"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        proxy = get_config("proxy")
        refresh_token = get_config("pixiv_refresh_token")
        if not refresh_token:
            raise ValueError("Pixiv refresh_token 未配置，请检查配置文件")
        self.pixiv_api = await initialize_pixiv_api(proxy, refresh_token)

   
    @bot.group_event()
    @feature_required(feature_name="pixiv", raw_message_filter=["/pixs", "/pixb"])
    async def handle_search(self, event: GroupMessage):
        """处理 Pixiv 搜索和榜单"""
        raw_message = event.raw_message.strip()
        if re.match(r"^/pixs", raw_message):
            parts = re.sub(r"^/pixs", "", raw_message).strip().split()
            query = parts[0] if parts else ""
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

            if not query:
                await self.api.post_group_msg(event.group_id, text="请输入搜索关键词，例如：/pixs 原神 2")
                return

            await self.api.post_group_msg(event.group_id, text=f"正在搜索第 {page} 页，请稍候...")
            illusts = await fetch_illusts(self.pixiv_api, query, page)
            if illusts:
                messages = await format_illusts(illusts)
                await send_group_forward_msg_ws(event.group_id, messages)
            else:
                await self.api.post_group_msg(event.group_id, text="未找到相关插画")

        elif re.match(r"^/pixb", raw_message):
            parts = re.sub(r"^/pixb", "", raw_message).strip().split()
            mode_map = {"日": "day", "周": "week", "月": "month"}
            mode = mode_map.get(parts[0], "day") if parts else "day"
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

            if mode not in ["day", "week", "month"]:
                await self.api.post_group_msg(event.group_id, text="无效的榜单类型，请输入 日, 周 或 月")
                return

            await self.api.post_group_msg(event.group_id, text=f"正在获取第 {page} 页榜单，请稍候...")
            illusts = await fetch_ranking(self.pixiv_api, mode, page)
            if illusts:
                messages = await format_illusts(illusts)
                await send_group_forward_msg_ws(event.group_id, messages)
            else:
                await self.api.post_group_msg(event.group_id, text="未找到相关榜单信息")
