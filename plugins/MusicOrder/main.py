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

    async def _fetch_data(self, api_url: str):
        """
        封装API请求
        """
        print(f"_fetch_data: 请求 API - {api_url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    print(f"_fetch_data: API 响应状态码 - {response.status}")
                    if response.status == 200:
                        try:
                            data = await response.json()
                            print(f"_fetch_data: API 响应内容 - {data}")
                            return data
                        except aiohttp.ContentTypeError:
                            content = await response.text()
                            print("_fetch_data: 响应内容不是 JSON")
                            return {"text": content}
                    else:
                        print(f"API request failed with status: {response.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"API request failed: {e}")
            return None

    async def fetch_music_list(self, song_name: str):
        """
        调用API获取歌曲列表
        """
        api_url = f"https://ecyapi.cn/API//wyy_music/?msg={quote(song_name)}&type=json"
        return await self._fetch_data(api_url)

    async def fetch_music_url(self, song_name: str, index: int):
        """
        调用API获取歌曲URL
        """
        api_url = f"https://ecyapi.cn/API//wyy_music/?msg={quote(song_name)}&type=json&n={index}"
        return await self._fetch_data(api_url)

    @bot.group_event()
    # @feature_required("点歌", raw_message_filter="/点歌")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        """
        user_id = event.user_id
        group_id = event.group_id
        message = event.raw_message.strip()

        print(f"handle_group_message: 收到消息 - {message}")

        if message.startswith("/点歌"):
            song_name = message[3:].strip()
            if not song_name:
                await self.api.post_group_msg(group_id, text="请在/点歌后输入歌曲名")
                return

            music_list_data = await self.fetch_music_list(song_name)

            if not music_list_data:
                await self.api.post_group_msg(group_id, text="获取歌曲列表失败，请稍后再试")
                return

            song_options = []
            if isinstance(music_list_data, dict) and "text" in music_list_data:
                # 处理文本格式的歌曲列表
                for i, line in enumerate(music_list_data["text"].splitlines()[:6]):
                    match = re.match(r"^\d+\.\s*(.+?)——(.+)$", line)
                    if match:
                        song_name = match.group(1).strip()
                        artist_name = match.group(2).strip()
                        song_options.append(f"{i+1}. {song_name}——{artist_name}")
            elif isinstance(music_list_data, list):
                # 处理JSON格式的歌曲列表
                for i in range(min(6, len(music_list_data))):
                    song = music_list_data[i]
                    if isinstance(song, dict) and "name" in song and "namex" in song:
                        song_options.append(f"{i+1}. {song['name']}——{song['namex']}")
                    else:
                        print(f"handle_group_message: 歌曲数据格式不正确: {song}")
                        continue
            else:
                print(f"handle_group_message: 未知的数据格式: {music_list_data}")
                await self.api.post_group_msg(group_id, text="获取歌曲列表失败，返回数据格式不正确")
                return

            if not song_options:
                await self.api.post_group_msg(group_id, text="未找到歌曲列表，请稍后再试")
                return

            self.user_states[user_id] = {"song_name": song_name}
            await self.api.post_group_msg(group_id, text="请回复数字选择歌曲:\n" + "\n".join(song_options))

        elif user_id in self.user_states and message.isdigit():
            index = int(message)
            if 1 <= index <= 6:
                song_name = self.user_states[user_id]["song_name"]
                music_data = await self.fetch_music_url(song_name, index)

                if not music_data or music_data["code"] != 0 or "data" not in music_data or not music_data["data"]:
                    print(f"获取歌曲信息失败: {music_data}")
                    await self.api.post_group_msg(group_id, text="获取歌曲信息失败，请稍后再试")
                else:
                    try:
                        music_info = music_data["data"][0]
                        music_url = music_info["url"]
                        music_name = music_info["name"]
                        music_image = music_info["image"]

                        custom_music = CustomMusic(
                            audio=music_url,
                            title=music_name,
                            url=music_url,
                            image=music_image,
                            singer=""
                        )
                        await self.api.post_group_msg(group_id, rtf=MessageChain([custom_music]))

                    except KeyError as e:
                        print(f"KeyError: {e}")
                        await self.api.post_group_msg(group_id, text=f"获取歌曲信息失败，KeyError: {e}")

                del self.user_states[user_id]
            else:
                await self.api.post_group_msg(group_id, text="无效选项，请重新选择")
        else:
            print(f"handle_group_message: 未进入数字选择逻辑分支")  # 添加日志
            if user_id not in self.user_states:
                print(f"handle_group_message: 用户 {user_id} 不在 user_states 中")  # 添加日志
            if not message.isdigit():
                print(f"handle_group_message: 消息不是数字")  # 添加日志
