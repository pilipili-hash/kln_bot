from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .utils import create_client, handle_search_request, handle_download_request
import re,os

bot = CompatibleEnrollment

class JmSearch(BasePlugin):
    name = "JmSearch"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        # 初始化客户端
        self.option, self.client = create_client('jmoption.yml')

        # 检查并创建 static/jm 文件夹
        static_jm_path = os.path.join("static/jm")
        if not os.path.exists(static_jm_path):
            os.makedirs(static_jm_path)

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        group_id = event.group_id
        user_id = event.user_id

        # 处理 /jm搜索 命令
        match_search = re.match(r"^/jm搜索\s+(.+)$", raw_message)
        if match_search:
            query = match_search.group(1).strip()
            page = 1  # 默认搜索第一页
            await handle_search_request(self.api, self.client, group_id, query, page)
            return

        # 处理 /jm下载 命令
        match_download = re.match(r"^/jm下载\s+(\d+)$", raw_message)
        if match_download:
            album_id = match_download.group(1).strip()
            await handle_download_request(self.api, self.option, group_id, album_id, user_id)
