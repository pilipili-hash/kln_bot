from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, CustomMusic, Image
from utils.group_forward_msg import send_group_forward_msg_ws
from .utils import fetch_asmr_data, fetch_audio_data, format_asmr_data, generate_audio_list_image  # 导入处理函数
import re
import tempfile  # 用于创建临时文件
import os  # 用于删除临时文件

bot = CompatibleEnrollment

class AsmrSearch(BasePlugin):
    name = "AsmrSearch"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def handle_audio_request(self, group_id: int, audio_id: int):
        """处理音频请求"""
        data = await fetch_audio_data(audio_id)
        if not data:
            await self.api.post_group_msg(group_id, text="未找到相关音频数据。")
            return

        # 提取 MP3 和 WAV 格式的音频
        audio_list = []
        for folder in data:
            if folder["type"] == "folder":
                for child in folder["children"]:
                    if child["type"] == "audio" and (".mp3" in child["title"] or ".wav" in child["title"]):
                        audio_list.append({
                            "title": child["title"],
                            "stream_url": child["mediaStreamUrl"]
                        })

        if not audio_list:
            await self.api.post_group_msg(group_id, text="未找到 MP3 或 WAV 格式的音频。")
            return

        # 生成音频列表图片
        image_data = generate_audio_list_image(audio_list)

        # 将 BytesIO 对象保存为临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            temp_file.write(image_data.getvalue())
            temp_file_path = temp_file.name

        try:
            # 使用临时文件路径发送图片
            await self.api.post_group_msg(group_id, rtf=MessageChain([Text("音频列表如下："), Image(temp_file_path)]))
        finally:
            # 删除临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        # 保存音频列表到上下文
        self.pending_search[group_id] = audio_list

    async def handle_audio_play_request(self, group_id: int, user_id: int, user_input: int):
        """处理播放音频请求"""
        if group_id not in self.pending_search:
            await self.api.post_group_msg(group_id, text="请先发送 /听 id 获取音频列表。")
            return

        audio_list = self.pending_search[group_id]
        if user_input < 1 or user_input > len(audio_list):
            await self.api.post_group_msg(group_id, text="无效的音频编号，请重新输入。")
            return

        audio = audio_list[user_input - 1]
        custom_music = CustomMusic(
            audio=audio["stream_url"],  # 音频链接
            title="点击右侧播放按钮",  # 标题
            url=audio["stream_url"],  # 跳转链接
            image=f"https://q.qlogo.cn/g?b={user_id}&nk=&s=640",  # 可选封面图，留空
            singer="别点卡片！"  # 可选歌手名
        )

        await self.api.post_group_msg(group_id, rtf=MessageChain([custom_music]))
        
        # 音频发送后再删除记录
        del self.pending_search[group_id]
    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        raw_message = event.raw_message.strip()
        group_id = event.group_id
        user_id = event.user_id

        match = re.match(r"^/asmr\s+(\d+)$", raw_message)
        match_list = re.match(r"^/听\s+(\d+)$", raw_message)

        if match:
            page = int(match.group(1))
            await self.api.post_group_msg(group_id, text="正在搜索，请稍候...")

            # 计算页码和范围
            api_page = (page + 1) // 2  # 每两次 /asmr 请求对应 API 的一个页码
            start = 0 if page % 2 == 1 else 10  # 奇数页取前 10 个，偶数页取后 10 个
            end = start + 10

            data = await fetch_asmr_data(api_page)
            if data:
                messages = format_asmr_data(data, start, end)
                if messages:
                    await send_group_forward_msg_ws(group_id, messages)
                else:
                    await self.api.post_group_msg(group_id, text="未找到相关数据。")
            else:
                await self.api.post_group_msg(group_id, text="搜索失败，请稍后再试。")
        elif match_list:
            audio_id = int(match_list.group(1))
            await self.handle_audio_request(group_id, audio_id)
        elif group_id in self.pending_search:
            try:
                user_input = int(raw_message)
                await self.handle_audio_play_request(group_id, user_id, user_input)
            except ValueError:
                await self.api.post_group_msg(group_id, text="请输入有效的音频编号。")

    async def on_load(self):
        """插件加载时的初始化逻辑"""
        self.pending_search = {}  # 用于记录用户的音频请求状态
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
