import aiohttp
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import Image, MessageChain, Text
from utils.group_forward_msg import get_cqimg  # 导入 get_cqimg 函数
from PluginManager.plugin_manager import feature_required
from urllib.parse import quote

bot = CompatibleEnrollment


class AnimeSearch(BasePlugin):
    name = "AnimeSearch"  # 插件名称
    version = "1.0.0"  # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self.pending_search = {}
    async def search_anime(self, image_url: str) -> MessageChain:
        """调用 Trace.moe API 搜索番剧并返回结果"""
        encoded_url = quote(image_url, safe="")
        api_url = f"https://api.trace.moe/search?cutBorders&anilistInfo&url={encoded_url}"
        # print(f"请求的 API URL: {api_url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                # print(f"API 响应状态码: {response.status}")
                if response.status != 200:
                    error_message = await response.text()
                    print(f"API 错误信息: {error_message}")
                    return MessageChain([Text("搜索失败，请稍后再试。")])
                data = await response.json()
                return self.format_results(data)

    def format_results(self, data: dict) -> MessageChain:
        """格式化 API 返回的结果为 MessageChain 类型"""
        if not data.get("result"):
            return MessageChain([Text("未找到相关番剧信息。")])

        results = data["result"]
        message_chain = MessageChain()

        for result in results[:3]:  # 仅显示前三个结果
            title = result["anilist"]["title"]["native"]
            romaji = result["anilist"]["title"]["romaji"]
            english = result["anilist"]["title"]["english"]
            episode = result.get("episode", "未知")
            similarity = round(result["similarity"] * 100, 2)
            image_url = result["image"]

            # 添加文本信息到消息链
            message_chain += MessageChain([
                Text(f"番剧名称: {title} ({romaji} / {english})\n"),
                Text(f"集数: {episode}\n"),
                Text(f"相似度: {similarity}%\n")
            ])

            # 添加图片到消息链
            message_chain += Image(image_url)

        return message_chain

    async def handle_image_search(self, group_id: int, image_url: str):
        """处理图片搜索逻辑"""
        await self.api.post_group_msg(group_id, text="正在搜索，请稍候...")
        result = await self.search_anime(image_url)
        await self.api.post_group_msg(group_id, rtf=result)

    @bot.group_event()
    @feature_required("以图搜番",raw_message_filter="/搜番")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        group_id = event.group_id
        user_id = event.user_id
        raw_message = event.raw_message

        # 如果消息以 "/搜番" 开头
        if raw_message.startswith("/搜番"):
            if "[CQ:image" in raw_message:  # 检查是否包含图片
                image_url = get_cqimg(raw_message)
                if image_url:
                    await self.handle_image_search(group_id, image_url)
            else:
                # 记录用户状态，等待后续图片
                self.pending_search[group_id] = user_id
                await self.api.post_group_msg(group_id, text="请发送图片以完成搜索。")
            return

        # 如果消息是图片，且用户之前发送了 "/搜番"
        if group_id in self.pending_search and self.pending_search[group_id] == user_id:
            for segment in event.message:  # 确保这里访问的是正确的属性
                if segment["type"] == "image":  # 检查消息类型是否为图片
                    image_url = segment["data"].get("url")  # 提取图片的 URL
                    if image_url:
                        # 清除用户状态
                        del self.pending_search[group_id]
                        await self.handle_image_search(group_id, image_url)