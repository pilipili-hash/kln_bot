import aiohttp
import re
from urllib.parse import quote
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import Music, CustomMusic, MessageChain
from utils.group_forward_msg import send_group_msg_cq
from PluginManager.plugin_manager import feature_required

bot = CompatibleEnrollment

class MusicOrder(BasePlugin):
    name = "MusicOrder"
    version = "1.0.0"
    user_states = {}

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def fetch_music_list(self, song_name: str):
        """
        调用API获取歌曲列表
        """
        api_url = f"https://ecyapi.cn/API//wyy_music/?msg={quote(song_name)}&type=json"
        print(f"fetch_music_list: 请求 API - {api_url}")  # 添加日志
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    print(f"fetch_music_list: API 响应状态码 - {response.status}")  # 添加日志
                    if response.status == 200:
                        content = await response.text()
                        # 尝试解析为 JSON，如果失败则直接返回文本
                        try:
                            data = await response.json()
                            print(f"fetch_music_list: API 响应内容 - {data}")  # 添加日志
                            return data
                        except aiohttp.ContentTypeError:
                            print("fetch_music_list: 响应内容不是 JSON")  # 添加日志
                            return {"text": content}
                    else:
                        print(f"API request failed with status: {response.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"API request failed: {e}")
            return None

    async def fetch_music_url(self, song_name: str, index: int):
        """
        调用API获取歌曲URL
        """
        api_url = f"https://ecyapi.cn/API//wyy_music/?msg={quote(song_name)}&type=json&n={index}"
        print(f"fetch_music_url: 请求 API - {api_url}")  # 添加日志
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    print(f"fetch_music_url: API 响应状态码 - {response.status}")  # 添加日志
                    if response.status == 200:
                        data = await response.json()
                        print(f"fetch_music_url: API 响应内容 - {data}")  # 打印 API 响应
                        return data
                    else:
                        print(f"API request failed with status: {response.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"API request failed: {e}")
            return None

    @bot.group_event()
    @feature_required("点歌", raw_message_filter="/点歌")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        """
        user_id = event.user_id
        group_id = event.group_id
        raw_message = event.raw_message.strip()

        print(f"handle_group_message: 收到消息 - {raw_message}")  # 添加日志

        if (raw_message.startswith("/点歌")):
            print("handle_group_message: 消息以 /点歌 开头")  # 添加日志
            song_name = raw_message[3:].strip()
            if not song_name:
                await self.api.post_group_msg(group_id, text="请在/点歌后输入歌曲名")
                return

            music_list = await self.fetch_music_list(song_name)
            if music_list:
                print(f"handle_group_message: 获取到歌曲列表 - {music_list}")  # 添加日志
                if isinstance(music_list, dict) and "text" in music_list:
                    # 解析歌曲列表
                    song_options = []
                    for i, line in enumerate(music_list["text"].splitlines()[:6]):
                        match = re.match(r"^\d+\.\s*(.+?)——(.+)$", line)
                        if match:
                            song_name = match.group(1).strip()
                            artist_name = match.group(2).strip()
                            song_options.append(f"{i+1}. {song_name}——{artist_name}")

                    if song_options:
                        self.user_states[user_id] = {"song_name": song_name}
                        await self.api.post_group_msg(group_id, text="请回复数字选择歌曲:\n" + "\n".join(song_options))
                    else:
                        await self.api.post_group_msg(group_id, text="未找到歌曲列表，请稍后再试")
                    return
                
                song_options = []
                for i in range(min(6, len(music_list))):
                    song = music_list[i]
                    song_options.append(f"{i+1}. {song['name']}——{song['namex']}")

                self.user_states[user_id] = {"song_name": song_name}
                await self.api.post_group_msg(group_id, text="请回复数字选择歌曲:\n" + "\n".join(song_options))
            else:
                await self.api.post_group_msg(group_id, text="获取歌曲列表失败，请稍后再试")
        elif user_id in self.user_states and raw_message.isdigit():
            # print("handle_group_message: 消息是数字，且用户在 user_states 中")  # 添加日志
            index = int(raw_message)
            print(f"handle_group_message: 用户选择的序号 - {index}")  # 添加日志
            if 1 <= index <= 6:
                song_name = self.user_states[user_id]["song_name"]
                print(f"handle_group_message: 歌曲名称 - {song_name}")  # 添加日志
                music_data = await self.fetch_music_url(song_name, index)
                if music_data and music_data["code"] == 0:
                    if "data" in music_data and music_data["data"]:
                        try:
                            music_info = music_data["data"][0]
                            music_url = music_info["url"]
                            music_name = music_info["name"]
                            music_image = music_info["image"]

                            custom_music = CustomMusic(
                                audio=music_url,  # 音频链接
                                title=music_name,  # 标题
                                url=music_url,  # 跳转链接
                                image=music_image,  # 可选封面图
                                singer=""  # 可选歌手名
                            )

                            await self.api.post_group_msg(group_id, rtf=MessageChain([custom_music]))
                        except KeyError as e:
                            print(f"KeyError: {e}")
                            await self.api.post_group_msg(group_id, text=f"获取歌曲信息失败，KeyError: {e}")
                    else:
                        await self.api.post_group_msg(group_id, text="获取歌曲信息失败，返回数据为空")
                else:
                    print(f"获取歌曲信息失败: {music_data}")
                    await self.api.post_group_msg(group_id, text="获取歌曲信息失败，请稍后再试")
                del self.user_states[user_id]
            else:
                await self.api.post_group_msg(group_id, text="无效选项，请重新选择")
