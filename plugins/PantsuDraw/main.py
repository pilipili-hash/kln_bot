import aiohttp
import random
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image
from PluginManager.plugin_manager import feature_required
bot = CompatibleEnrollment

class PantsuDraw(BasePlugin):
    name = "PantsuDraw"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def fetch_pantsu_image(self) -> str:
        """调用 API 获取胖次图片 URL"""
        api_url = "http://api.siyangyuan.tk/API/pc.php"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    return str(response.url)
                else:
                    return None

    def generate_caption(self) -> str:
        """随机生成胖次文案"""
        captions = [
            "如你所愿！收下吧献祭叔叔获得的神物:",
            "给你,给你,拿了赶紧导去吧",
            "咦<del>你这个hentai,拿去爬</del>",
            "欧尼?你变了,看了我的还不够吗.呜呜呜<del>再给你就是了</del>",
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

    @bot.group_event()
    @feature_required("抽胖次","抽胖次")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        if event.raw_message.strip() == "抽胖次":
            await self.api.post_group_msg(event.group_id, text="正在为你抽取胖次，请稍候...")
            image_url = await self.fetch_pantsu_image()
            if image_url:
                caption = self.generate_caption()
                message = MessageChain([
                    Text(f"{caption}\n"),
                    Image(image_url)
                ])
                await self.api.post_group_msg(event.group_id, rtf=message)
            else:
                await self.api.post_group_msg(event.group_id, text="抽取失败，请稍后再试。")
