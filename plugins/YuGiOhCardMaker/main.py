import os
import base64
import logging
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text
import httpx
import urllib.parse
from utils.group_forward_msg import send_group_msg_cq
from utils.onebot_v11_handler import extract_images
from textwrap import wrap
from typing import Dict, Optional, Any

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class YuGiOhCardMaker(BasePlugin):
    name = "YuGiOhCardMaker"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        # 用户状态管理
        self.user_states: Dict[int, Dict[str, Any]] = {}

        # 字体对象
        self.title_font: Optional[ImageFont.FreeTypeFont] = None
        self.text_font: Optional[ImageFont.FreeTypeFont] = None

        # HTTP客户端
        self.http_client: Optional[httpx.AsyncClient] = None

        # 统计信息
        self.card_created_count = 0
        self.help_count = 0
        self.cancel_count = 0

    # 插件配置常量
    CARD_TYPES = {"1", "2", "3"}
    MAGIC_TRAP_TYPES = {"2", "3"}
    ATTRIBUTE_TYPES = {"1", "2", "3", "4", "5", "6", "7"}
    MAX_LEVEL = 12
    STATIC_PATH = os.path.join(os.getcwd(), "static", "gamecard")
    FONT_PATH = os.path.join("static", "font.ttf")
    CARD_TYPE_MAP = {"1": "normal.png", "2": "spell.png", "3": "trap.png"}
    ATTRIBUTE_MAP = {"1": "1.png", "2": "2.png", "3": "3.png", "4": "4.png", "5": "5.png", "6": "6.png", "7": "7.png"}
    CARD_TYPE_NAMES = {"1": "普通卡", "2": "魔法卡", "3": "陷阱卡"}
    ATTRIBUTE_NAMES = {"1": "暗", "2": "炎", "3": "光", "4": "水", "5": "风", "6": "神", "7": "地"}

    # 图片和布局配置
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

    async def on_load(self):
        """插件加载时初始化"""
        try:
            # 检查字体文件
            if not os.path.exists(self.FONT_PATH):
                _log.error(f"字体文件不存在: {self.FONT_PATH}")
                return

            # 加载字体
            self.title_font = ImageFont.truetype(self.FONT_PATH, 108)
            self.text_font = ImageFont.truetype(self.FONT_PATH, 54)

            # 初始化HTTP客户端
            self.http_client = httpx.AsyncClient(timeout=30.0)

            _log.info(f"YuGiOhCardMaker v{self.version} 插件已加载")

        except Exception as e:
            _log.error(f"插件加载失败: {e}")

    async def __onload__(self):
        """插件加载时初始化（新版本）"""
        await self.on_load()

    async def on_unload(self):
        """插件卸载时清理资源"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        _log.info("YuGiOhCardMaker 插件已卸载")

    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🎴 游戏王卡片制作插件帮助

🎯 功能说明：
制作自定义游戏王卡片，支持普通卡、魔法卡、陷阱卡

🔍 使用方法：
• 游戏王卡片制作 - 开始制作卡片
• /游戏王帮助 - 显示此帮助信息
• /游戏王统计 - 查看使用统计
• /取消 - 取消当前制作过程

💡 制作流程：
1. 选择卡片类型（普通卡/魔法卡/陷阱卡）
2. 选择属性（普通卡需要）
3. 设置星级（普通卡需要，1-12级）
4. 输入种族（普通卡需要）
5. 输入卡片标题
6. 上传卡片图片
7. 输入效果描述

📊 卡片类型：
• 普通卡：需要属性、星级、种族
• 魔法卡：只需标题、图片、效果
• 陷阱卡：只需标题、图片、效果

🎨 属性类型：
• 1:暗 2:炎 3:光 4:水 5:风 6:神 7:地

✨ 特色功能：
• 🎨 高质量卡片模板
• 🖼️ 自动图片处理和缩放
• 📝 智能文本排版
• 🎯 多种卡片类型支持
• ⭐ 星级图标自动排列

⚠️ 注意事项：
• 图片建议使用清晰的正方形图片
• 效果文本会自动换行和截断
• 制作过程中可随时发送"/取消"退出
• 每次只能制作一张卡片

🔧 版本: v2.0.0
💡 提示：发送"游戏王卡片制作"开始制作你的专属卡片！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        active_users = len(self.user_states)
        stats_text = f"""📊 游戏王卡片制作插件统计

🔢 使用数据：
• 已制作卡片数量: {self.card_created_count}
• 帮助查看次数: {self.help_count}
• 取消制作次数: {self.cancel_count}
• 当前制作中用户: {active_users}

📈 功能状态：
• 字体加载: {'✅ 正常' if self.title_font and self.text_font else '❌ 异常'}
• HTTP客户端: {'✅ 正常' if self.http_client else '❌ 异常'}
• 资源目录: {'✅ 存在' if os.path.exists(self.STATIC_PATH) else '❌ 不存在'}

🎴 支持的卡片类型：
• 普通卡、魔法卡、陷阱卡
• 7种属性、12个星级
• 自定义图片和效果

🔧 版本: v2.0.0"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def cancel_user_process(self, user_id: int, group_id: int):
        """取消用户的制作过程"""
        if user_id in self.user_states:
            del self.user_states[user_id]
            self.cancel_count += 1
            await self.api.post_group_msg(group_id, text="✅ 已取消卡片制作过程")
        else:
            await self.api.post_group_msg(group_id, text="❌ 您当前没有进行中的卡片制作")

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        user_id = event.user_id
        group_id = event.group_id
        raw_message = event.raw_message.strip()

        # 帮助命令
        if raw_message in ["/游戏王帮助", "/yugioh帮助", "游戏王帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/游戏王统计", "/yugioh统计", "游戏王统计"]:
            await self.show_statistics(group_id)
            return

        # 取消命令
        if raw_message in ["/取消", "取消", "/cancel"]:
            await self.cancel_user_process(user_id, group_id)
            return

        # 开始制作命令
        if raw_message == "游戏王卡片制作":
            self.user_states[user_id] = {"step": 1}
            await self.api.post_group_msg(group_id, text="🎴 开始制作游戏王卡片！\n\n请回复数字选择卡片类型:\n1️⃣ 普通卡\n2️⃣ 魔法卡\n3️⃣ 陷阱卡\n\n💡 随时发送 \"/取消\" 可退出制作")
            return

        # 处理制作流程
        if user_id in self.user_states:
            try:
                await self._handle_card_creation_step(user_id, group_id, raw_message, event)
            except Exception as e:
                _log.error(f"处理卡片制作步骤时发生错误: {e}")
                await self.api.post_group_msg(group_id, text="❌ 处理过程中发生错误，请重新开始制作")
                if user_id in self.user_states:
                    del self.user_states[user_id]

    async def _handle_card_creation_step(self, user_id: int, group_id: int, raw_message: str, event: GroupMessage):
        """处理卡片制作的各个步骤"""
        state = self.user_states[user_id]
        step = state["step"]

        if step == 1:  # 选择卡片类型
            if raw_message in self.CARD_TYPES:
                state["type"] = raw_message
                card_type_name = self.CARD_TYPE_NAMES[raw_message]

                # 如果是魔法卡或陷阱卡，直接跳过属性、星星和种族的步骤
                if raw_message in self.MAGIC_TRAP_TYPES:
                    state["attribute"] = "0"
                    state["level"] = 0
                    state["race"] = ""
                    state["step"] = 5
                    await self.api.post_group_msg(group_id, text=f"✅ 已选择 {card_type_name}\n\n📝 请发送卡片标题")
                else:
                    state["step"] = 2
                    await self.api.post_group_msg(group_id, text=f"✅ 已选择 {card_type_name}\n\n🎨 请回复数字选择属性:\n1️⃣ 暗 2️⃣ 炎 3️⃣ 光 4️⃣ 水\n5️⃣ 风 6️⃣ 神 7️⃣ 地")
            else:
                await self.api.post_group_msg(group_id, text="❌ 无效输入，请回复数字选择卡片类型:\n1️⃣ 普通卡\n2️⃣ 魔法卡\n3️⃣ 陷阱卡")

        elif step == 2:  # 选择属性
            if raw_message in self.ATTRIBUTE_TYPES:
                state["attribute"] = raw_message
                attribute_name = self.ATTRIBUTE_NAMES[raw_message]
                state["step"] = 3
                await self.api.post_group_msg(group_id, text=f"✅ 已选择属性: {attribute_name}\n\n⭐ 请发送星星等级数量 (1-{self.MAX_LEVEL})")
            else:
                await self.api.post_group_msg(group_id, text="❌ 无效输入，请回复数字选择属性:\n1️⃣ 暗 2️⃣ 炎 3️⃣ 光 4️⃣ 水\n5️⃣ 风 6️⃣ 神 7️⃣ 地")

        elif step == 3:  # 设置星级
            if raw_message.isdigit() and 1 <= int(raw_message) <= self.MAX_LEVEL:
                state["level"] = int(raw_message)
                state["step"] = 4
                await self.api.post_group_msg(group_id, text=f"✅ 已设置星级: {raw_message}⭐\n\n🏷️ 请发送种族名称")
            else:
                await self.api.post_group_msg(group_id, text=f"❌ 无效输入，请发送1-{self.MAX_LEVEL}之间的数字")

        elif step == 4:  # 输入种族
            state["race"] = raw_message
            state["step"] = 5
            await self.api.post_group_msg(group_id, text=f"✅ 已设置种族: {raw_message}\n\n📝 请发送卡片标题")

        elif step == 5:  # 输入标题
            state["title"] = raw_message
            state["step"] = 6
            await self.api.post_group_msg(group_id, text=f"✅ 已设置标题: {raw_message}\n\n🖼️ 请发送一张图片")

        elif step == 6:  # 上传图片
            # 使用新的OneBotV11图片提取方法
            image_urls = extract_images(event)
            if image_urls:
                state["image_path"] = image_urls[0]  # 使用第一张图片
                state["step"] = 7
                await self.api.post_group_msg(group_id, text="✅ 图片已接收\n\n📄 请发送效果文本描述")
                _log.info(f"用户 {user_id} 上传了图片: {image_urls[0][:50]}...")
            else:
                await self.api.post_group_msg(group_id, text="❌ 未检测到图片，请重新发送一张图片")

        elif step == 7:  # 输入效果并生成卡片
            state["effect"] = raw_message
            await self.api.post_group_msg(group_id, text="🎨 正在制作卡片，请稍候...")

            card_image_cq = await self.generate_card(state)
            if card_image_cq:
                await send_group_msg_cq(group_id, card_image_cq)
                self.card_created_count += 1
                _log.info(f"用户 {user_id} 成功制作了一张{self.CARD_TYPE_NAMES.get(state['type'], '未知')}卡片: {state['title']}")
            else:
                await self.api.post_group_msg(group_id, text="❌ 卡片制作失败，请稍后再试")

            # 清理用户状态
            del self.user_states[user_id]

    async def generate_card(self, state: Dict[str, Any]) -> Optional[str]:
        """生成游戏王卡片"""
        try:
            # 加载所需资源
            card_template = await self._load_card_template(state["type"])
            attribute_icon = await self._load_attribute_icon(state)
            level_icon = await self._load_level_icon()
            user_image = await self._load_user_image(state["image_path"])

            if not all([card_template, attribute_icon, level_icon, user_image]):
                _log.error("加载卡片资源失败")
                return None

            # 合成卡片
            draw = ImageDraw.Draw(card_template)

            # 绘制标题
            if self.title_font:
                draw.text(self.TITLE_POSITION, state["title"], font=self.title_font, fill="black")

            # 粘贴属性图标和星星等级
            await self._paste_attribute_and_level(card_template, attribute_icon, level_icon, state)

            # 粘贴用户图片
            card_template.paste(user_image, self.USER_IMAGE_POSITION, user_image)

            # 绘制种族和效果文本
            await self._draw_race_and_effect(card_template, draw, state)

            # 转换图片为Base64
            buffer = BytesIO()
            card_template.save(buffer, format="PNG")
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

            _log.info(f"成功生成卡片: {state['title']}")
            return f"[CQ:image,file=base64://{base64_image}]"

        except Exception as e:
            _log.error(f"生成卡片失败: {e}")
            return None

    async def _load_card_template(self, card_type: str) -> Optional[Image.Image]:
        """加载卡片模板"""
        try:
            template_path = os.path.join(self.STATIC_PATH, self.CARD_TYPE_MAP[card_type])
            if not os.path.exists(template_path):
                _log.error(f"卡片模板文件不存在: {self.CARD_TYPE_MAP[card_type]}")
                return None
            return Image.open(template_path).convert("RGBA")
        except Exception as e:
            _log.error(f"加载卡片模板失败: {e}")
            return None

    async def _load_attribute_icon(self, state: Dict[str, Any]) -> Optional[Image.Image]:
        """加载属性图标"""
        try:
            if state["type"] == "2":  # 魔法卡
                attribute_icon_path = os.path.join(self.STATIC_PATH, "attribute-spell.png")
            elif state["type"] == "3":  # 陷阱卡
                attribute_icon_path = os.path.join(self.STATIC_PATH, "attribute-trap.png")
            else:
                attribute_icon_path = os.path.join(self.STATIC_PATH, self.ATTRIBUTE_MAP.get(state["attribute"], "1.png"))

            if not os.path.exists(attribute_icon_path):
                _log.error(f"属性图标文件不存在: {attribute_icon_path}")
                return None
            return Image.open(attribute_icon_path).convert("RGBA")
        except Exception as e:
            _log.error(f"加载属性图标失败: {e}")
            return None

    async def _load_level_icon(self) -> Optional[Image.Image]:
        """加载星星等级图标"""
        try:
            level_icon_path = os.path.join(self.STATIC_PATH, "level.png")
            if not os.path.exists(level_icon_path):
                _log.error("星星等级图标文件不存在: level.png")
                return None
            return Image.open(level_icon_path).convert("RGBA")
        except Exception as e:
            _log.error(f"加载星星等级图标失败: {e}")
            return None

    async def _load_user_image(self, image_url: str) -> Optional[Image.Image]:
        """加载用户图片"""
        try:
            if not self.http_client:
                _log.error("HTTP客户端未初始化")
                return None

            # 处理URL
            image_url = image_url.replace("https://", "http://")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
            }

            # 对URL进行编码
            encoded_url = urllib.parse.quote(image_url, safe=':/&?=@+')

            # 下载图片
            response = await self.http_client.get(encoded_url, headers=headers, timeout=15)
            response.raise_for_status()

            # 处理图片
            image_data = BytesIO(response.content)
            image = Image.open(image_data).convert("RGBA")

            # 调整图片大小
            resized_image = image.resize(self.IMAGE_SIZE, Image.Resampling.LANCZOS)

            _log.info(f"成功加载用户图片，大小: {resized_image.size}")
            return resized_image

        except httpx.HTTPError as e:
            _log.error(f"图片下载失败 (HTTP错误): {e}")
            return None
        except Exception as e:
            _log.error(f"加载用户图片失败: {e}")
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