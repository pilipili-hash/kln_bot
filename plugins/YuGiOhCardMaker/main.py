import os
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text
import httpx
import urllib.parse
from utils.group_forward_msg import get_cqimg,send_group_msg_cq
import ssl
from textwrap import wrap  
bot = CompatibleEnrollment

class YuGiOhCardMaker(BasePlugin):
    name = "YuGiOhCardMaker"
    version = "1.0.0"

    user_states = {}
    title_font: ImageFont.FreeTypeFont | None = None
    text_font: ImageFont.FreeTypeFont | None = None
    # 插件配置
    CARD_TYPES = {"1", "2", "3"}
    MAGIC_TRAP_TYPES = {"2", "3"}
    ATTRIBUTE_TYPES = {"1", "2", "3", "4", "5", "6", "7"}
    MAX_LEVEL = 12
    STATIC_PATH = os.path.join(os.getcwd(), "static", "gamecard")
    FONT_PATH = os.path.join("static", "font.ttf")
    CARD_TYPE_MAP = {"1": "normal.png", "2": "spell.png", "3": "trap.png"}
    ATTRIBUTE_MAP = {"1": "1.png", "2": "2.png", "3": "3.png", "4": "4.png", "5": "5.png", "6": "6.png", "7": "7.png"}
    IMAGE_SIZE = (1055, 1055)
    EFFECT_TEXT_RECT = {
        "width": 1160,
        "height": 290,
        "left": 114,
        "top": 1580
    }
    LEVEL_ICON_POSITION_X = 1245
    LEVEL_ICON_POSITION_Y = 253
    LEVEL_ICON_OFFSET = 90
    TITLE_POSITION = (90, 105)
    RACE_POSITION = (130, 1520)
    USER_IMAGE_POSITION = (170, 374)
    ATTRIBUTE_ICON_POSITION = (1167, 96)
    
    http_client: httpx.AsyncClient | None = None

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        if not os.path.exists(self.FONT_PATH):
            print("字体文件不存在: font.ttf", flush=True)
            return
        self.title_font = ImageFont.truetype(self.FONT_PATH, 108)
        self.text_font = ImageFont.truetype(self.FONT_PATH, 54)
        self.http_client = httpx.AsyncClient()

    async def on_unload(self):
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        user_id = event.user_id
        group_id = event.group_id
        raw_message = event.raw_message.strip()

        if (raw_message == "游戏王卡片制作"):
            self.user_states[user_id] = {"step": 1}
            await self.api.post_group_msg(group_id, text="请回复数字选择卡片类型:\n1:普通卡\n2:魔法卡\n3:陷阱卡")
        elif user_id in self.user_states:
            state = self.user_states[user_id]
            step = state["step"]

            if step == 1:
                if raw_message in self.CARD_TYPES:
                    state["type"] = raw_message
                    # 如果是魔法卡或陷阱卡，直接跳过属性、星星和种族的步骤
                    if raw_message in self.MAGIC_TRAP_TYPES:
                        state["attribute"] = "0"  # 设置默认值
                        state["level"] = 0  # 设置默认值
                        state["race"] = ""  # 种族为空
                        state["step"] = 5  # 跳到标题步骤
                        await self.api.post_group_msg(group_id, text="请发送卡片标题")
                        
                    else:
                        state["step"] = 2
                        await self.api.post_group_msg(group_id, text="请回复数字选择属性:\n1:暗 2:炎 3:光 4:水 5:风 6:神 7:地")
                else:
                    await self.api.post_group_msg(group_id, text="无效输入，请回复数字选择卡片类型:\n1:普通卡\n2:魔法卡\n3:陷阱卡")
            elif step == 2:
                if raw_message in self.ATTRIBUTE_TYPES:
                    state["attribute"] = raw_message
                    state["step"] = 3
                    await self.api.post_group_msg(group_id, text="请发送星星等级数量:最大12")
                else:
                    await self.api.post_group_msg(group_id, text="无效输入，请回复数字选择属性:\n1:暗 2:炎 3:光 4:水 5:风 6:神 7:地")
            elif step == 3:
                if raw_message.isdigit() and 1 <= int(raw_message) <= self.MAX_LEVEL:
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
                    await send_group_msg_cq(group_id, card_image_cq)
                else:
                    await self.api.post_group_msg(group_id, text="卡片制作失败，请稍后再试")
                del self.user_states[user_id]

    async def generate_card(self, state: dict) -> str | None:
        try:
            card_template = await self._load_card_template(state["type"])
            attribute_icon = await self._load_attribute_icon(state)
            level_icon = await self._load_level_icon()
            user_image = await self._load_user_image(state["image_path"])

            if not all([card_template, attribute_icon, level_icon, user_image]):
                return None

            # 合成卡片
            draw = ImageDraw.Draw(card_template)

            # 标题
            if self.title_font:
                draw.text(self.TITLE_POSITION, state["title"], font=self.title_font, fill="black")

            # 属性图标和星星等级
            await self._paste_attribute_and_level(card_template, attribute_icon, level_icon, state)

            # 用户图片
            card_template.paste(user_image, self.USER_IMAGE_POSITION, user_image)

            # 种族和效果文本
            await self._draw_race_and_effect(card_template, draw, state)

            # 转换图片为 Base64
            buffer = BytesIO()
            card_template.save(buffer, format="PNG")
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"[CQ:image,file=base64://{base64_image}]"
        except Exception as e:
            print(f"生成卡片失败: {e}", flush=True)
            return None

    async def _load_card_template(self, card_type: str) -> Image.Image | None:
        """加载卡片模板."""
        template_path = os.path.join(self.STATIC_PATH, self.CARD_TYPE_MAP[card_type])
        if not os.path.exists(template_path):
            print(f"卡片模板文件不存在: {self.CARD_TYPE_MAP[card_type]}", flush=True)
            return None
        return Image.open(template_path).convert("RGBA")

    async def _load_attribute_icon(self, state: dict) -> Image.Image | None:
        """加载属性图标."""
        if state["type"] == "2":  # 魔法卡
            attribute_icon_path = os.path.join(self.STATIC_PATH, "attribute-spell.png")
        elif state["type"] == "3":  # 陷阱卡
            attribute_icon_path = os.path.join(self.STATIC_PATH, "attribute-trap.png")
        else:
            attribute_icon_path = os.path.join(self.STATIC_PATH, self.ATTRIBUTE_MAP.get(state["attribute"], "default.png"))

        if not os.path.exists(attribute_icon_path):
            print(f"属性图标文件不存在: {attribute_icon_path}", flush=True)
            return None
        return Image.open(attribute_icon_path).convert("RGBA")

    async def _load_level_icon(self) -> Image.Image | None:
        """加载星星等级图标."""
        level_icon_path = os.path.join(self.STATIC_PATH, "level.png")
        if not os.path.exists(level_icon_path):
            print("星星等级图标文件不存在: level.png", flush=True)
            return None
        return Image.open(level_icon_path).convert("RGBA")

    async def _load_user_image(self, image_url: str) -> Image.Image | None:
        """加载用户图片."""
        try:
            image_url = image_url.replace("https://", "http://")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
            }
            # 对 URL 进行编码
            encoded_url = urllib.parse.quote(image_url, safe=':/&?=@+')
            response = await self.http_client.get(encoded_url, headers=headers, timeout=10)
            response.raise_for_status()  # 检查状态码

            # 读取图片内容到 BytesIO
            image_data = BytesIO(response.content)
            return Image.open(image_data).convert("RGBA").resize(self.IMAGE_SIZE)

        except httpx.HTTPError as e:
            print(f"图片下载失败: {e}", flush=True)
            return None

    async def _paste_attribute_and_level(self, card_template: Image.Image, attribute_icon: Image.Image, level_icon: Image.Image, state: dict):
        """粘贴属性图标和等级."""
        # 如果是魔法卡或陷阱卡，则使用对应的属性图标
        if state["type"] == "2":
            attribute_icon = Image.open(os.path.join(self.STATIC_PATH, "attribute-spell.png")).convert("RGBA")
            card_template.paste(attribute_icon, self.ATTRIBUTE_ICON_POSITION, attribute_icon)
        elif state["type"] == "3":
            attribute_icon = Image.open(os.path.join(self.STATIC_PATH, "attribute-trap.png")).convert("RGBA")
            card_template.paste(attribute_icon, self.ATTRIBUTE_ICON_POSITION, attribute_icon)
        else:
            # 否则，使用默认的属性图标并绘制星星等级
            card_template.paste(attribute_icon, self.ATTRIBUTE_ICON_POSITION, attribute_icon)

            # 星星等级
            for i in range(state["level"]):
                x = self.LEVEL_ICON_POSITION_X - i * self.LEVEL_ICON_OFFSET
                card_template.paste(level_icon, (x, self.LEVEL_ICON_POSITION_Y), level_icon)

    async def _draw_race_and_effect(self, card_template: Image.Image, draw: ImageDraw.Draw, state: dict):
        """绘制种族和效果文本."""
        if self.text_font:
            # 如果不是魔法卡或陷阱卡，则绘制种族
            if state["type"] not in ["2", "3"]:
                draw.text(self.RACE_POSITION, f"【{state['race']}】", font=self.text_font, fill="black")

            # 获取效果文本矩形框参数
            effect_rect_width = self.EFFECT_TEXT_RECT["width"]
            effect_rect_height = self.EFFECT_TEXT_RECT["height"]
            effect_rect_left = self.EFFECT_TEXT_RECT["left"]
            effect_rect_top = self.EFFECT_TEXT_RECT["top"]

            # 获取单个字符的宽度和高度
            char_width, char_height = self.text_font.getbbox("测")[2], self.text_font.getbbox("测")[3]

            # 将效果文本按矩形宽度换行
            max_chars_per_line = effect_rect_width // char_width  # 每行最多字符数
            wrapped_text = wrap(state["effect"], width=max_chars_per_line)

            # 确保文本不会超出矩形高度
            max_lines = effect_rect_height // char_height  # 矩形内最多行数
            wrapped_text = wrapped_text[:max_lines]

            # 在矩形内绘制多行文本
            y_offset = effect_rect_top
            for line in wrapped_text:
                draw.text((effect_rect_left, y_offset), line, font=self.text_font, fill="black")
                y_offset += char_height  # 行高