import re
import base64
from meme_generator import get_memes, Meme,search_memes
from meme_generator.tools import MemeProperties, MemeSortBy, render_meme_list
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .meme_utils import get_avatar, generate_meme, generate_keywords_image, get_member_name, handle_avatar_and_name
from utils.group_forward_msg import send_group_msg_cq

bot = CompatibleEnrollment

class MemeCreator(BasePlugin):
    name = "MemeCreator"
    version = "1.0.0"

    async def on_load(self):
        self.memes = {meme.key: meme for meme in get_memes()}

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        raw_message = event.raw_message
        # print(event.message)
        if (raw_message.strip() == "/m ls"):
            try:

                keywords_image = render_meme_list(sort_by=MemeSortBy.Key, add_category_icon=True)
                base64_image = base64.b64encode(keywords_image).decode("utf-8")
                cq_image = f"[CQ:image,file=base64://{base64_image}]"
                await send_group_msg_cq(event.group_id, cq_image)
            except Exception as e:
                await self.api.post_group_msg(group_id=event.group_id, text=f"生成关键词图片失败: {e}")
            return

        # 从 event.message 提取关键词和 @ 信息
        keyword = None
        qq_numbers = []
        text_segments = []

        for segment in event.message:
            if segment["type"] == "text":
                if not keyword:
                    keyword = segment["data"]["text"].strip().split()[0]  # 提取第一个单词作为关键词
                    remaining_text = segment["data"]["text"].strip()[len(keyword):].strip()
                    if remaining_text:
                        text_segments.append(remaining_text)  # 保存剩余的文本
                else:
                    text_segments.append(segment["data"]["text"].strip())  # 保存其他文本段
            elif segment["type"] == "at":
                qq_numbers.append(segment["data"]["qq"])  # 提取所有 @ 的 QQ 号

        text = " ".join(text_segments)  # 合并所有文本段
        text_list = text.split() if text else []

        if not keyword:
            return  # 如果没有关键词，直接返回

        # 检查是否是 /m 指令
        if keyword.startswith("/m"):
            match = re.match(r"/m\s+(\d+)", keyword)
            if not match:
                return
            index = int(match.group(1)) - 1
        else:
            # 查找关键词对应的表情包
            memes = search_memes(keyword)
            if not memes:
                # await self.api.post_group_msg(group_id=event.group_id, text="未找到对应的表情包关键词")
                return

            # 如果返回的是字符串列表，将其转换为表情包对象
            if isinstance(memes, list) and all(isinstance(m, str) for m in memes):
                memes = [self.memes.get(m) for m in memes if m in self.memes]

            # 默认选择第一个表情包
            meme = memes[0] if isinstance(memes, list) else memes

            # 验证表情包是否有效
            if not meme or meme.key not in self.memes:
                await self.api.post_group_msg(group_id=event.group_id, text="表情包未在加载的列表中")
                return

            index = list(self.memes.keys()).index(meme.key)

        if index < 0 or index >= len(self.memes):
            await self.api.post_group_msg(group_id=event.group_id, text="无效的表情序号或关键词")
            return

        meme = list(self.memes.values())[index]
        image_data = []
        names = []

        # 检查是否有用户发送的图片
        image_segments = [segment for segment in event.message if segment["type"] == "image"]
        if image_segments:
            for segment in image_segments:
                image_url = segment["data"]["url"]
                try:
                    # 使用 get_avatar 函数下载图片数据
                    image_data_io = await get_avatar(image_url)
                    if image_data_io:
                        image_data.append(image_data_io)
                    else:
                        await self.api.post_group_msg(group_id=event.group_id, text="下载用户图片失败")
                        return
                except Exception as e:
                    await self.api.post_group_msg(group_id=event.group_id, text=f"处理用户图片失败: {e}")
                    return

        # 如果没有用户图片，处理多个 @ 的头像和名称
        if not image_data and qq_numbers:
            for qq_number in qq_numbers:
                avatar_data, name = await handle_avatar_and_name(self.api, event.group_id, int(qq_number))
                if not avatar_data:
                    await self.api.post_group_msg(group_id=event.group_id, text="获取头像失败")
                    return
                image_data.append(avatar_data)
                names.append(name)

        # 如果需要的图片数量大于已提供的头像或用户图片数量，用发送者的头像补充
        while len(image_data) < meme.info.params.min_images:
            avatar_data, name = await handle_avatar_and_name(self.api, event.group_id, event.user_id)
            if not avatar_data:
                await self.api.post_group_msg(group_id=event.group_id, text="获取头像失败，无法生成表情包")
                return
            image_data.append(avatar_data)
            names.append(name)

        if len(text_list) < meme.info.params.min_texts or len(text_list) > meme.info.params.max_texts:
            await self.api.post_group_msg(
                group_id=event.group_id,
                text=f"文字数量不匹配: 需要 {meme.info.params.min_texts} ~ {meme.info.params.max_texts} 个，实际 {len(text_list)} 个"
            )
            return

        if meme.info.params.min_texts == 0 and meme.info.params.max_texts == 0:
            text_list = []

        if len(image_data) < meme.info.params.min_images or len(image_data) > meme.info.params.max_images:
            await self.api.post_group_msg(
                group_id=event.group_id,
                text=f"图片数量不匹配: 需要 {meme.info.params.min_images} ~ {meme.info.params.max_images} 张，实际 {len(image_data)} 张"
            )
            return

        if len(image_data) == 0 and meme.info.params.min_images > 0:
            avatar_data, name = await handle_avatar_and_name(self.api, event.group_id, event.user_id)
            if not avatar_data:
                await self.api.post_group_msg(group_id=event.group_id, text="获取头像失败，无法生成表情包")
                return
            image_data.append(avatar_data)
            names.append(name)

        try:
            meme_image = await generate_meme(meme, image_data, text_list, {}, names)
            if isinstance(meme_image, str):
                await self.api.post_group_msg(group_id=event.group_id, text=f"生成表情包失败: {meme_image}")
                return
            if not meme_image:
                await self.api.post_group_msg(group_id=event.group_id, text="生成表情包失败")
                return

            base64_image = base64.b64encode(meme_image).decode('utf-8')
            cq_image = f"[CQ:image,file=base64://{base64_image}]"
            await send_group_msg_cq(event.group_id, cq_image)

        except Exception as e:
            await self.api.post_group_msg(group_id=event.group_id, text=f"生成表情包失败: {e}")
