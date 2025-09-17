import aiohttp
import asyncio
import logging
import random
import time
from typing import List, Optional, Dict, Any
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
# MessageChain, Text, Image 不再需要，直接使用image参数发送图片
# re模块不再需要，使用字符级别的emoji识别

# 尝试导入插件管理器
try:
    from PluginManager.plugin_manager import feature_required
except ImportError:
    def feature_required(feature_name=None, commands=None, require_admin=False):
        """简单的装饰器替代版本"""
        def decorator(func):
            async def wrapper(self, *args, **kwargs):
                return await func(self, *args, **kwargs)
            return wrapper
        return decorator

from .utils import mix_emoji
from .emoji_data import emojis

bot = CompatibleEnrollment
_log = logging.getLogger("EmojiKitchen.main")

class EmojiKitchen(BasePlugin):
    name = "EmojiKitchen"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 缓存系统
        self.emoji_cache = {}
        self.cache_expire_time = 3600  # 1小时缓存

        # 请求限制
        self.last_request_time = {}
        self.request_interval = 2  # 2秒间隔

        # 统计信息
        self.mix_count = 0
        self.success_count = 0

    async def on_load(self):
        """插件加载时初始化"""
        try:
            print(f"EmojiKitchen 插件已加载")
            print(f"插件版本: {self.version}")
            _log.info(f"EmojiKitchen v{self.version} 插件已加载")
            _log.info("Emoji合成功能已启用")
        except Exception as e:
            _log.error(f"插件加载失败: {e}")

    async def __onload__(self):
        """插件加载时初始化（新版本）"""
        await self.on_load()

    def _is_cache_valid(self, cache_time: float) -> bool:
        """检查缓存是否有效"""
        return time.time() - cache_time < self.cache_expire_time

    def _should_rate_limit(self, group_id: int) -> bool:
        """检查是否需要限流"""
        current_time = time.time()
        last_time = self.last_request_time.get(group_id, 0)
        return current_time - last_time < self.request_interval

    def get_random_emoji(self) -> str:
        """获取随机emoji"""
        try:
            emoji_codes = random.choice(emojis)
            if isinstance(emoji_codes, list):
                return ''.join(chr(code) for code in emoji_codes)
            else:
                return chr(emoji_codes)
        except Exception as e:
            _log.error(f"获取随机emoji失败: {e}")
            return "😀"

    def extract_emojis(self, text: str) -> List[str]:
        """从文本中提取emoji，逐个字符识别"""

        emojis = []
        i = 0
        while i < len(text):
            char = text[i]

            # 检查是否是emoji字符
            if self._is_emoji_char(char):
                emoji = char

                # 检查是否有修饰符或组合字符
                j = i + 1
                while j < len(text):
                    next_char = text[j]
                    if (ord(next_char) >= 0x1F3FB and ord(next_char) <= 0x1F3FF) or \
                       (ord(next_char) >= 0x200D and ord(next_char) <= 0x200D) or \
                       (ord(next_char) >= 0xFE0F and ord(next_char) <= 0xFE0F):
                        emoji += next_char
                        j += 1
                    else:
                        break

                emojis.append(emoji)
                i = j
            else:
                i += 1

        return emojis

    def _is_emoji_char(self, char: str) -> bool:
        """检查单个字符是否是emoji"""
        code = ord(char)
        return (
            (0x1F600 <= code <= 0x1F64F) or  # emoticons
            (0x1F300 <= code <= 0x1F5FF) or  # symbols & pictographs
            (0x1F680 <= code <= 0x1F6FF) or  # transport & map symbols
            (0x1F1E0 <= code <= 0x1F1FF) or  # flags
            (0x2700 <= code <= 0x27BF) or    # dingbats
            (0x1F900 <= code <= 0x1F9FF) or  # supplemental symbols
            (0x2600 <= code <= 0x26FF) or    # miscellaneous symbols
            (0x1F018 <= code <= 0x1F270) or  # various symbols
            (0x1F400 <= code <= 0x1F4FF) or  # animals & nature
            (0x1F000 <= code <= 0x1F02F) or  # mahjong tiles
            (0x1F0A0 <= code <= 0x1F0FF)     # playing cards
        )

    async def get_emoji_combination(self, emoji1: str, emoji2: str) -> Optional[str]:
        """
        获取emoji合成结果，优先使用本地数据，支持缓存
        """
        # 检查缓存
        cache_key = f"{emoji1}_{emoji2}"
        if cache_key in self.emoji_cache:
            cache_data, cache_time = self.emoji_cache[cache_key]
            if self._is_cache_valid(cache_time):
                _log.info(f"使用缓存数据: {emoji1} + {emoji2}")
                return cache_data

        try:
            # 使用本地数据获取合成结果
            result = await mix_emoji(emoji1, emoji2)

            # 缓存结果
            self.emoji_cache[cache_key] = (result, time.time())

            if result and not result.startswith("不支持"):
                _log.info(f"成功合成emoji: {emoji1} + {emoji2}")
                return result
            else:
                _log.warning(f"emoji合成失败: {result}")
                return None

        except Exception as e:
            _log.error(f"获取emoji合成时发生错误: {e}")
            return None

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🍳 Emoji厨房插件帮助

🎯 功能说明：
将两个emoji合成为一个全新的创意emoji

🔍 使用方法：
1. 直接发送两个emoji：😀😍 (直接返回合成图片)
2. 相同emoji也可以：🤨🤨 (直接返回合成图片)
3. 随机合成：/emoji随机
4. 查看帮助：/emoji帮助

� 静默模式特性：
• 只在恰好两个emoji时进行合成
• 单个emoji时不会有任何提示
• 多个emoji时不会有任何提示
• 合成失败时也不会提示
• 保持聊天环境清爽，不打扰正常聊天

✨ 极简体验：
• 直接发送合成图片，无多余文字
• 不会误判普通文本为emoji
• 智能识别emoji边界
• 支持emoji修饰符和组合字符

📝 可用命令：
• /emoji帮助 - 显示此帮助信息
• /emoji随机 - 随机合成两个emoji
• /emoji统计 - 查看使用统计

🎨 技术特色：
• 📱 本地数据库：快速响应，无需网络请求
• ⚡ 智能缓存：1小时缓存，提升性能
• 🛡️ 请求限制：防止频繁调用
• 🎯 精确识别：字符级emoji分析

🔧 版本：v2.0.0
💡 提示：静默合成，只在需要时响应！"""

        await self.api.post_group_msg(group_id, text=help_text)

    async def show_statistics(self, group_id: int):
        """显示统计信息"""
        success_rate = (self.success_count / max(self.mix_count, 1)) * 100
        stats_text = f"""📊 Emoji厨房统计信息

🔢 总合成次数: {self.mix_count}
✅ 成功次数: {self.success_count}
📈 成功率: {success_rate:.1f}%
💾 缓存数量: {len(self.emoji_cache)}

🎯 插件状态: 正常运行
⚡ 缓存时长: 1小时
🛡️ 请求间隔: 2秒"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def random_emoji_mix(self, group_id: int):
        """随机emoji合成"""
        try:
            emoji1 = self.get_random_emoji()
            emoji2 = self.get_random_emoji()

            image_url = await self.get_emoji_combination(emoji1, emoji2)

            if image_url:
                # 直接发送合成图片
                await self.api.post_group_msg(group_id, image=image_url)
                self.success_count += 1
            else:
                await self.api.post_group_msg(group_id, text=f"❌ 随机合成失败，{emoji1} 和 {emoji2} 无法合成")

            self.mix_count += 1

        except Exception as e:
            _log.error(f"随机emoji合成失败: {e}")
            await self.api.post_group_msg(group_id, text="随机合成时发生错误，请稍后再试。")

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件，支持多种emoji合成方式
        """
        raw_message = event.raw_message.strip()

        # 检查命令
        if raw_message in ["/emoji帮助", "/emoji help", "/表情帮助"]:
            await self.show_help(event.group_id)
            return
        elif raw_message in ["/emoji统计", "/emoji stats", "/表情统计"]:
            await self.show_statistics(event.group_id)
            return
        elif raw_message in ["/emoji随机", "/emoji random", "/表情随机"]:
            await self.random_emoji_mix(event.group_id)
            return

        # 检查限流
        if self._should_rate_limit(event.group_id):
            _log.info(f"群 {event.group_id} 请求过于频繁，跳过处理")
            return

        # 提取emoji
        emojis_found = self.extract_emojis(raw_message)

        # 如果没有找到emoji，直接返回，避免误判
        if not emojis_found:
            return

        # 检查是否恰好有两个emoji
        if len(emojis_found) == 2:
            emoji1, emoji2 = emojis_found[0], emojis_found[1]

            _log.info(f"检测到emoji合成请求: {emoji1} + {emoji2}")

            # 更新请求时间
            self.last_request_time[event.group_id] = time.time()
            self.mix_count += 1

            try:
                image_url = await self.get_emoji_combination(emoji1, emoji2)

                if image_url:
                    # 直接发送合成图片，不显示文本
                    await self.api.post_group_msg(event.group_id, image=image_url)
                    self.success_count += 1
                    _log.info(f"emoji合成成功: {emoji1} + {emoji2}")
                # 合成失败时保持静默，不提示用户

            except Exception as e:
                _log.error(f"处理emoji合成时发生错误: {e}")
                # 发生错误时也保持静默，不提示用户

        # 其他情况（1个emoji、多个emoji等）都保持静默，不进行任何提示
