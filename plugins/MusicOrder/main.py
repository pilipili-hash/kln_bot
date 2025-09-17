import aiohttp
import re
import asyncio
import time
from typing import Dict, List, Optional, Any, Union
from urllib.parse import quote
from dataclasses import dataclass
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import Music, CustomMusic, MessageChain
from utils.group_forward_msg import send_group_msg_cq
from PluginManager.plugin_manager import feature_required

# 尝试导入pyncm，如果没有安装则使用备用API
try:
    from pyncm.apis import cloudsearch, track
    from pyncm.apis.cloudsearch import GetSearchResult
    from pyncm.apis.track import GetTrackAudio, GetTrackDetail
    PYNCM_AVAILABLE = True
except ImportError:
    PYNCM_AVAILABLE = False
    print("pyncm未安装，将使用备用API")

bot = CompatibleEnrollment

@dataclass
class SongInfo:
    """歌曲信息数据类"""
    id: int
    name: str
    artists: List[str]
    album: str
    duration: int
    cover_url: str
    play_url: str
    platform: str = "netease"

    @property
    def display_artists(self) -> str:
        return "、".join(self.artists)

    @property
    def display_duration(self) -> str:
        minutes = self.duration // 60000
        seconds = (self.duration % 60000) // 1000
        return f"{minutes:02d}:{seconds:02d}"

class MusicOrder(BasePlugin):
    name = "MusicOrder"
    version = "3.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_states: Dict[int, Dict[str, Any]] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=15)  # 15秒超时
        self.search_cache: Dict[str, List[SongInfo]] = {}  # 搜索结果缓存

    async def on_load(self):
        """插件加载时初始化"""
        # 创建HTTP会话
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def on_unload(self):
        """插件卸载时清理资源"""
        if self.session:
            await self.session.close()
        self.user_states.clear()
        print(f"{self.name} 插件已卸载")

    async def _search_songs_pyncm(self, keyword: str, limit: int = 6) -> List[SongInfo]:
        """使用pyncm搜索歌曲"""
        try:
            # 修正pyncm API调用方式
            def search_sync():
                return GetSearchResult(
                    keyword=keyword,
                    limit=limit,
                    offset=0,
                    stype=cloudsearch.SONG
                )

            result = await asyncio.get_event_loop().run_in_executor(None, search_sync)

            if not result or result.get("code") != 200:
                return []

            songs_data = result.get("result", {}).get("songs", [])
            if not songs_data:
                return []

            # 直接使用搜索结果，不需要再次获取详细信息
            songs = []
            for song_data in songs_data[:limit]:
                try:
                    song_info = SongInfo(
                        id=song_data["id"],
                        name=song_data["name"],
                        artists=[ar["name"] for ar in song_data.get("ar", [])],
                        album=song_data.get("al", {}).get("name", ""),
                        duration=song_data.get("dt", 0),
                        cover_url=song_data.get("al", {}).get("picUrl", ""),
                        play_url="",  # 稍后获取
                        platform="netease"
                    )
                    songs.append(song_info)
                except (KeyError, TypeError) as e:
                    print(f"解析歌曲信息失败: {e}")
                    continue

            return songs
        except Exception as e:
            print(f"pyncm搜索失败: {e}")
            return []

    async def _get_song_url_pyncm(self, song_id: int) -> str:
        """使用pyncm获取歌曲播放链接"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, GetTrackAudio, [song_id], 999999
            )

            if not result or result.get("code") != 200:
                return ""

            data = result.get("data", [])
            if data and len(data) > 0:
                return data[0].get("url", "")

            return ""
        except Exception as e:
            print(f"获取播放链接失败: {e}")
            return ""

    async def _search_songs_fallback(self, keyword: str, platform: str = "netease") -> List[SongInfo]:
        """备用API搜索歌曲"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=self.timeout)

            # 使用备用API（这里可以添加其他可用的音乐API）
            if platform == "qq":
                # QQ音乐API已失效，返回空列表
                return []
            else:
                # 网易云音乐API已失效，返回空列表
                return []

        except Exception as e:
            print(f"备用API搜索失败: {e}")
            return []

    async def search_songs(self, keyword: str, platform: str = "netease") -> List[SongInfo]:
        """搜索歌曲的统一入口"""
        # 检查缓存
        cache_key = f"{platform}:{keyword}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]

        songs = []

        # 优先使用pyncm
        if PYNCM_AVAILABLE and platform == "netease":
            songs = await self._search_songs_pyncm(keyword)

        # 如果pyncm失败或不可用，使用备用API
        if not songs:
            songs = await self._search_songs_fallback(keyword, platform)

        # 缓存结果
        if songs:
            self.search_cache[cache_key] = songs

        return songs

    async def get_song_play_url(self, song_info: SongInfo) -> str:
        """获取歌曲播放链接"""
        if song_info.play_url:
            return song_info.play_url

        # 优先使用pyncm
        if PYNCM_AVAILABLE and song_info.platform == "netease":
            url = await self._get_song_url_pyncm(song_info.id)
            if url:
                song_info.play_url = url
                return url

        # 备用方案：返回空字符串，表示无法获取
        return ""

    def _clean_user_state(self, user_id: int) -> None:
        """清理用户状态"""
        if user_id in self.user_states:
            del self.user_states[user_id]

    def _is_state_expired(self, user_id: int, timeout: int = 300) -> bool:
        """检查用户状态是否过期（默认5分钟）"""
        if user_id not in self.user_states:
            return True
        return time.time() - self.user_states[user_id].get("timestamp", 0) > timeout

    async def _send_help(self, group_id: int) -> None:
        """发送帮助信息"""
        pyncm_status = "✅ 已安装" if PYNCM_AVAILABLE else "❌ 未安装"
        help_text = f"""🎵 音乐点歌帮助 v3.0.0

📝 基本命令：
• /点歌 <歌名> - 网易云音乐点歌
• /取消点歌 - 取消当前点歌操作
• /点歌帮助 - 显示此帮助

🎮 使用方式：
1. 发送点歌命令后，系统会返回歌曲列表
2. 回复对应数字选择要播放的歌曲
3. 系统会发送音乐卡片到群聊

💡 使用示例：
/点歌 告白气球
/点歌 周杰伦 稻香
2
/取消点歌

🔧 技术状态：
• pyncm库：{pyncm_status}
• 搜索缓存：已启用
• 高音质支持：已启用

⚠️ 注意事项：
• 选择操作5分钟内有效，超时自动取消
• 每次只能进行一个点歌操作
• 部分歌曲可能因版权无法播放
• 基于pyncm库，提供更稳定的服务"""

        await self.api.post_group_msg(group_id, text=help_text)



    async def _handle_music_search(self, group_id: int, user_id: int, song_name: str, platform: str) -> None:
        """处理音乐搜索"""
        if not song_name:
            platform_name = "QQ音乐" if platform == "qq" else "网易云音乐"
            await self.api.post_group_msg(group_id, text=f"请在命令后输入歌曲名\n例如：/点歌 告白气球")
            return

        # 检查用户是否已有进行中的操作
        if user_id in self.user_states and not self._is_state_expired(user_id):
            await self.api.post_group_msg(group_id, text="❌ 您还有未完成的点歌操作，请先完成或发送 /取消点歌")
            return

        # 清理过期状态
        if user_id in self.user_states:
            self._clean_user_state(user_id)

        await self.api.post_group_msg(group_id, text="🔍 正在搜索歌曲，请稍候...")

        # 使用新的搜索方法
        songs = await self.search_songs(song_name, platform)

        if not songs:
            if platform == "qq":
                await self.api.post_group_msg(group_id, text="❌ QQ音乐搜索暂不可用，请尝试网易云音乐：/点歌 歌曲名")
            else:
                await self.api.post_group_msg(group_id, text="❌ 未找到相关歌曲，请检查歌曲名称或稍后再试")
            return

        # 构建歌曲选项列表
        song_options = []
        for i, song in enumerate(songs[:6]):
            song_options.append(f"{i+1}. {song.name} - {song.display_artists}")

        # 保存用户状态
        platform_name = "QQ音乐" if platform == "qq" else "网易云音乐"
        self.user_states[user_id] = {
            "songs": songs[:6],  # 保存歌曲信息列表
            "platform": platform,
            "timestamp": time.time()
        }

        response = f"🎵 {platform_name}搜索结果：\n\n" + "\n".join(song_options)
        response += "\n\n💡 请回复数字选择歌曲，或发送 /取消点歌 取消操作"
        await self.api.post_group_msg(group_id, text=response)

    async def _handle_music_selection(self, group_id: int, user_id: int, index: int) -> None:
        """处理音乐选择"""
        # 检查状态是否过期
        if self._is_state_expired(user_id):
            self._clean_user_state(user_id)
            await self.api.post_group_msg(group_id, text="❌ 操作已超时，请重新点歌")
            return

        if not (1 <= index <= 6):
            await self.api.post_group_msg(group_id, text="❌ 请选择1-6之间的数字")
            return

        user_state = self.user_states[user_id]
        songs = user_state.get("songs", [])
        platform = user_state.get("platform", "netease")

        if not songs or index > len(songs):
            await self.api.post_group_msg(group_id, text="❌ 选择的歌曲不存在")
            self._clean_user_state(user_id)
            return

        selected_song = songs[index - 1]
        await self.api.post_group_msg(group_id, text="🎵 正在获取歌曲链接，请稍候...")

        # 获取播放链接
        play_url = await self.get_song_play_url(selected_song)

        if not play_url:
            await self.api.post_group_msg(group_id, text="❌ 无法获取歌曲播放链接，可能因版权问题无法播放")
            self._clean_user_state(user_id)
            return

        try:
            # 创建音乐卡片
            custom_music = CustomMusic(
                audio=play_url,
                title=selected_song.name,
                url=f"https://music.163.com/song?id={selected_song.id}",
                image=selected_song.cover_url,
                singer=selected_song.display_artists
            )

            # 发送音乐卡片
            await self.api.post_group_msg(group_id, rtf=MessageChain([custom_music]))

            # # 发送成功提示
            # platform_name = "QQ音乐" if platform == "qq" else "网易云音乐"
            # await self.api.post_group_msg(
            #     group_id,
            #     text=f"✅ 已为您播放：{selected_song.name} - {selected_song.display_artists}\n"
            #          f"🎵 平台：{platform_name} | 时长：{selected_song.display_duration}"
            # )

        except Exception as e:
            print(f"发送音乐卡片失败: {e}")
            await self.api.post_group_msg(group_id, text="❌ 音乐卡片发送失败")
        finally:
            # 清理用户状态
            self._clean_user_state(user_id)

    @bot.group_event()
    async def on_message(self, event: GroupMessage):
        """处理群消息事件"""
        user_id = event.user_id
        group_id = event.group_id
        message = event.raw_message.strip()

        # 帮助命令
        if message in ["/点歌帮助", "/音乐帮助"]:
            await self._send_help(group_id)
            return

        # 取消点歌
        if message == "/取消点歌":
            if user_id in self.user_states:
                self._clean_user_state(user_id)
                await self.api.post_group_msg(group_id, text="✅ 已取消点歌操作")
            else:
                await self.api.post_group_msg(group_id, text="❌ 当前没有进行中的点歌操作")
            return

        # 网易云音乐点歌
        if message.startswith("/点歌"):
            await self._handle_music_search(group_id, user_id, message[3:].strip(), "netease")
            return

        # 处理数字选择
        if user_id in self.user_states and message.isdigit():
            await self._handle_music_selection(group_id, user_id, int(message))
            return

