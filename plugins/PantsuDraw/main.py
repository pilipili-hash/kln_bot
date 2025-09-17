import aiohttp
import random
import logging
import asyncio
from typing import Optional
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
from utils.config_manager import get_config

bot = CompatibleEnrollment
_log = logging.getLogger(__name__)

class PantsuDraw(BasePlugin):
    name = "PantsuDraw"  # 插件名称
    version = "2.0.0"  # 插件版本

    async def on_load(self):
        # 初始化插件属性
        self.api_urls = [
            "http://api.siyangyuan.tk/API/pc.php",
            "https://api.lolicon.app/setu/v2?tag=pantsu&r18=0",  # 备用API
        ]
        self.request_count = 0
        self.error_count = 0
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # 请求间隔限制

        _log.info(f"{self.name} v{self.version} 插件已加载")
        _log.info("胖次抽取功能已启用")

    async def _check_rate_limit(self):
        """检查请求频率限制"""
        import time
        current_time = time.time()
        if current_time - self.last_request_time < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - (current_time - self.last_request_time)
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()

    async def fetch_pantsu_image(self) -> Optional[str]:
        """调用 API 获取胖次图片 URL"""
        await self._check_rate_limit()

        # 获取代理配置
        try:
            config = get_config()
            proxy_url = config.get('proxy', '')
        except Exception as e:
            _log.warning(f"获取代理配置失败: {e}")
            proxy_url = None

        for api_url in self.api_urls:
            try:
                _log.debug(f"尝试API: {api_url}")
                timeout = aiohttp.ClientTimeout(total=10)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        api_url,
                        proxy=proxy_url if proxy_url else None
                    ) as response:
                        if response.status == 200:
                            self.request_count += 1
                            _log.debug(f"API请求成功: {api_url}")

                            # 根据不同API处理响应
                            if "siyangyuan" in api_url:
                                return str(response.url)
                            elif "lolicon" in api_url:
                                data = await response.json()
                                if data.get('data') and len(data['data']) > 0:
                                    return data['data'][0]['urls']['original']

                        else:
                            _log.warning(f"API请求失败: {api_url}, 状态码: {response.status}")

            except Exception as e:
                _log.error(f"API请求异常: {api_url}, 错误: {e}")
                continue

        self.error_count += 1
        _log.error("所有API都请求失败")
        return None

    def generate_caption(self) -> str:
        """随机生成胖次文案"""
        captions = [
            "如你所愿！收下吧献祭叔叔获得的神物:",
            "给你,给你,拿了赶紧导去吧",
            "咦你这个hentai,拿去爬",
            "欧尼?你变了,看了我的还不够吗.呜呜呜再给你就是了",
            "好吧,这次就依你吧。少看一会儿哦",
            "啊咧咧,果然你是个大变态呢!(￢︿☆)",
            "欧尼你个大hentai",
            "这可是稀有的神物哦，拿去珍藏吧！",
            "真是拿你没办法，给你就是了！",
            "哼，变态！不过还是给你吧。",
            "你这家伙，真是个无可救药的绅士呢！",
            "好啦好啦，别闹了，给你就是了。",
            "这可是我珍藏的哦，别弄丢了！",
            "你这个大笨蛋，拿去吧！",
            "这可是限量版的胖次哦，拿去好好珍惜吧！",
            "哎呀，真是没办法呢，给你就是了！",
            "你这个绅士，果然对胖次情有独钟呢！",
            "好啦好啦，别再撒娇了，给你吧！",
            "这可是我从天上摘下来的胖次哦！",
            "你真是个奇怪的人呢，不过还是给你吧！",
            "这可是传说中的胖次，拿去炫耀吧！",
            "哼，真是个麻烦的家伙，给你吧！",
            "胖次之神眷顾了你，快接住吧！",
            "这可是我珍藏的宝贝，千万别弄丢了！",
        ]
        return random.choice(captions)

    async def get_statistics(self) -> str:
        """获取使用统计"""
        success_rate = 0
        if self.request_count > 0:
            success_rate = ((self.request_count - self.error_count) / self.request_count) * 100

        return f"""📊 胖次抽取统计

🎯 总请求次数: {self.request_count}
❌ 失败次数: {self.error_count}
✅ 成功率: {success_rate:.1f}%
⏱️ 请求间隔: {self.rate_limit_delay}秒"""

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        message = event.raw_message.strip()

        if message == "抽胖次":
            try:
                _log.info(f"用户 {event.user_id} 在群 {event.group_id} 请求抽胖次")
                await self.api.post_group_msg(event.group_id, text="🎲 正在为你抽取胖次，请稍候...")

                image_url = await self.fetch_pantsu_image()
                if image_url:
                    caption = self.generate_caption()
                    message = MessageChain([
                        Text(f"{caption}\n"),
                        Image(image_url)
                    ])
                    await self.api.post_group_msg(event.group_id, rtf=message)
                    _log.info(f"成功为用户 {event.user_id} 提供胖次")
                else:
                    error_msg = "❌ 抽取失败，请稍后再试"
                    if self.error_count > 5:
                        error_msg += "\n💡 提示：API可能暂时不可用，请联系管理员"
                    await self.api.post_group_msg(event.group_id, text=error_msg)
                    _log.warning(f"为用户 {event.user_id} 抽取胖次失败")

            except Exception as e:
                _log.error(f"处理抽胖次请求时出错: {e}")
                await self.api.post_group_msg(event.group_id, text="❌ 系统错误，请稍后再试")

        elif message == "/胖次统计":
            try:
                stats = await self.get_statistics()
                await self.api.post_group_msg(event.group_id, text=stats)
            except Exception as e:
                _log.error(f"获取统计信息时出错: {e}")
                await self.api.post_group_msg(event.group_id, text="❌ 获取统计信息失败")

        elif message == "/胖次帮助":
            help_text = """🎭 胖次抽取插件帮助

📝 基本命令：
• 抽胖次 - 随机抽取一张胖次图片
• /胖次统计 - 查看使用统计
• /胖次帮助 - 显示此帮助信息

💡 使用说明：
• 每次请求间隔1秒，避免频繁调用
• 支持多个API源，自动切换
• 图片来源于公开API，内容健康

⚠️ 注意事项：
• 请合理使用，避免刷屏
• 图片加载可能需要一些时间
• 如遇问题请联系管理员"""

            await self.api.post_group_msg(event.group_id, text=help_text)
