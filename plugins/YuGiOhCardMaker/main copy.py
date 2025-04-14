import os
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text
from utils.group_forward_msg import get_cqimg,send_group_forward_msg_cq
import asyncio
import re

bot = CompatibleEnrollment

class YuGiOhCardMaker(BasePlugin):
    name = "YuGiOhCardMaker"
    version = "1.0.0"

    user_states = {}

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        user_id = event.user_id
        group_id = event.group_id
        raw_message = event.raw_message.strip()

        if raw_message == "游戏王卡片制作":
            self.user_states[user_id] = {"step": 1}
            await self.api.post_group_msg(group_id, text="请回复数字选择卡片类型:\n1:普通卡\n2:魔法卡\n3:陷阱卡")
        elif user_id in self.user_states:
            state = self.user_states[user_id]
            step = state["step"]

            if step == 1:
                if raw_message in ["1", "2", "3"]:
                    state["type"] = raw_message
                    state["step"] = 2
                    await self.api.post_group_msg(group_id, text="请回复数字选择属性:\n1:暗 2:炎 3:光 4:水 5:风 6:神 7:地")
                else:
                    await self.api.post_group_msg(group_id, text="无效输入，请回复数字选择卡片类型:\n1:普通卡\n2:魔法卡\n3:陷阱卡")
            elif step == 2:
                if raw_message in ["1", "2", "3", "4", "5", "6", "7"]:
                    state["attribute"] = raw_message
                    state["step"] = 3
                    await self.api.post_group_msg(group_id, text="请发送星星等级数量:最大12")
                else:
                    await self.api.post_group_msg(group_id, text="无效输入，请回复数字选择属性:\n1:暗 2:炎 3:光 4:水 5:风 6:神 7:地")
            elif step == 3:
                if raw_message.isdigit() and 1 <= int(raw_message) <= 12:
                    state["level"] = int(raw_message)
                    state["step"] = 4
                    await self.api.post_group_msg(group_id, text="请发送种族")
                else:
                    await self.api.post_group_msg(group_id, text="无效输入，请发送星星等级数量:最大12")
            elif step == 4:
                state["race"] = raw_message
                state["step"] = 5
                await self.api.post_group_msg(group_id, text="请发送卡片标题")
            elif step == 5:
                state["title"] = raw_message
                state["step"] = 6
                await self.api.post_group_msg(group_id, text="请发送一张图片")
            elif step == 6:
                cq_image = get_cqimg(raw_message)
                if cq_image:
                    state["image_path"] = cq_image
                    state["step"] = 7
                    await self.api.post_group_msg(group_id, text="请发送效果文本")
                else:
                    await self.api.post_group_msg(group_id, text="无效图片，请重新发送一张图片")
            elif step == 7:
                state["effect"] = raw_message
                await self.api.post_group_msg(group_id, text="正在制作中~")
                card_image_cq = await self.generate_card(state)
                if card_image_cq:
                    await send_group_forward_msg_cq(group_id, card_image_cq)
                else:
                    await self.api.post_group_msg(group_id, text="卡片制作失败，请稍后再试")
                del self.user_states[user_id]

    async def generate_card(self, state):
        try:
            static_path = os.path.join(os.getcwd(), "static", "gamecard")
            card_type_map = {"1": "normal.png", "2": "spell.png", "3": "trap.png"}
            attribute_map = {"1": "1.png", "2": "2.png", "3": "3.png", "4": "4.png", "5": "5.png", "6": "6.png", "7": "7.png"}

            # 加载卡片模板
            card_template = Image.open(os.path.join(static_path, card_type_map[state["type"]])).convert("RGBA")
            attribute_icon = Image.open(os.path.join(static_path, attribute_map[state["attribute"]])).convert("RGBA")
            level_icon = Image.open(os.path.join(static_path, "level.png")).convert("RGBA")

            # 从 Base64 数据创建用户图片
            user_image_cqcode = state["image_path"]
            match = re.search(r"base64://(.*?)\]", user_image_cqcode)
            if match:
                user_image_data = match.group(1)
                try:
                    image_data = base64.b64decode(user_image_data)
                    user_image = Image.open(BytesIO(image_data)).convert("RGBA").resize((370, 370))
                except Exception as e:
                    print(f"解析用户图片失败: {e}")
                    return None
            else:
                print("无法获取用户图片数据")
                return None

            # 合成卡片
            card_template.paste(attribute_icon, (30, 30), attribute_icon)
            for i in range(state["level"]):
                card_template.paste(level_icon, (40 + i * 40, 100), level_icon)
            card_template.paste(user_image, (60, 200), user_image)

            # 绘制文字
            draw = ImageDraw.Draw(card_template)
            font_path = os.path.join(static_path, "font.ttf")
            title_font = ImageFont.truetype(font_path, 40)
            text_font = ImageFont.truetype(font_path, 30)
            draw.text((50, 600), state["title"], font=title_font, fill="black")
            draw.text((50, 650), f"种族: {state['race']}", font=text_font, fill="black")
            draw.text((50, 700), state["effect"], font=text_font, fill="black")

            # 转换图片为 Base64
            buffer = BytesIO()
            card_template.save(buffer, format="PNG")
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"[CQ:image,file=base64://{base64_image}]"
        except Exception as e:
            print(f"生成卡片失败: {e}")
            return None
