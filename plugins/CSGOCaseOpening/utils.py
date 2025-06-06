import asyncio
import base64
from io import BytesIO
import math
import os
from os.path import dirname
from typing import List, Union
from PIL import Image, ImageFont, ImageDraw, ImageFilter
import httpx
from .model import SelectedSkin
from utils.config_manager import get_config  # 导入 load_config
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_msg_cq
from .crates import Crates
from .skins import Skins
from .model import SelectedSkin
import base64

crates = Crates()
skins = Skins()

PATH = dirname(__file__)
ASSSETS_DIR = PATH + "/assets"
FONT_DIR = PATH + "/font/NotoSansSC-Bold.otf"


class Utils:
    def __init__(self):
        self.client = httpx.Client()
        self.rarity_color = {
            "消费级": {"bg": "#5D6884", "stroke": "#4C556D"},
            "工业级": {"bg": "#3869E8", "stroke": "#2E5AC9"},
            "军规级": {"bg": "#3B38E8", "stroke": "#2827A7"},
            "受限": {"bg": "#9033D9", "stroke": "#6C26A7"},
            "保密": {"bg": "#DE55EA", "stroke": "#A842B3"},
            "隐秘": {"bg": "#8D1F3B", "stroke": "#6C1531"},
            "违禁": {"bg": "#C7B61F", "stroke": "#AD9F1E"},
            "非凡": {"bg": "#C7B61F", "stroke": "#AD9F1E"},
        }


    async def merge_images(
        self, items: List[SelectedSkin], case_name: str, case_img: str, user_name: str
    ):
        image_list = []

        image_tasks = [self.download_image(item.image) for item in items]
        image_list: List[Image.Image] = await asyncio.gather(*image_tasks)

        main_img = self.generate_main_img(image_list, items)

        main_img = self.generate_info(main_img, case_name, user_name)
        case_img = await self.download_image(case_img)
        case_img = case_img.resize((173, 134), Image.LANCZOS)
        main_img.paste(case_img, (128, 505), case_img)

        statistic_dict = {}
        rare_sorted = sorted([item.rarity for item in items], key=self.rare_sorted_func)
        for i in range(len(rare_sorted)):
            statistic_dict[rare_sorted[i]] = rare_sorted.count(rare_sorted[i])
        sorted_counts = sorted(
            statistic_dict.keys(), key=self.rare_sorted_func, reverse=True
        )

        top_three = {}
        for i in range(len(sorted_counts) if len(sorted_counts) < 3 else 3):
            top_three[sorted_counts[i]] = statistic_dict[sorted_counts[i]]

        self.generate_statistic(main_img, top_three)

        return self.img_from_PIL(main_img)

    def generate_main_img(self, skins: List[Image.Image], items: List[SelectedSkin]):
        for i in range(len(skins)):
            skins[i] = self.generate_item_card(
                skins[i], items[i].rarity, items[i].name, items[i].wear
            )
        main = Image.open(ASSSETS_DIR + "/main_template.png")
        columns = 5
        rows = (len(skins) - 1) // columns + 1
        if rows == 1:
            columns = len(skins)
        for i in range(rows):
            for j in range(columns):
                index = i * columns + j
                main.paste(
                    skins[index], (455 + j * 164, 101 + 151 * i), skins[i * columns + j]
                )
        return main

    def generate_statistic(self, main_img: Image.Image, top_three: dict):
        main_draw = ImageDraw.Draw(main_img)
        info_font = ImageFont.truetype(FONT_DIR, 32)
        i = 0
        for rare, count in top_three.items():
            main_draw.rounded_rectangle(
                (25, 246 + 80 * i, 405, 313 + 80 * i),
                radius=2,
                fill=self.rarity_color[rare]["bg"],
            )
            main_draw.text((35, 255 + 80 * i), rare, font=info_font, fill="#FFFFFF")
            main_draw.text(
                (345, 255 + 80 * i), f"x{count}", font=info_font, fill="#FFFFFF"
            )
            i += 1

    def generate_info(self, main_img: Image.Image, case_name: str, user_name: str):
        info_font = ImageFont.truetype(FONT_DIR, 32)
        text_width, text_height = info_font.getbbox(user_name[:12])[2:4]
        rank_img = Image.open(ASSSETS_DIR + "/rank.png").resize((71, 43), Image.LANCZOS)
        main_img.paste(rank_img, ((500 - text_width) // 2 - 75, 160), rank_img)

        main_draw = ImageDraw.Draw(main_img)
        main_draw.text(
            ((500 - text_width) // 2, 155), user_name[:12], font=info_font, fill="white"
        )

        text_width, text_height = info_font.getbbox(case_name[:12])[2:4]
        main_draw.text(
            ((430 - text_width) // 2, 645), case_name[:12], font=info_font, fill="white"
        )

        return main_img

    def generate_item_card(
        self, skin: Image.Image, rarity: str, name: str, wear: Union[str, None]
    ):
        image = Image.new("RGBA", (500, 500), "#D4D2D5")
        image = self.generate_item_card_band(
            image, self.rarity_color[rarity]["bg"], self.rarity_color[rarity]["stroke"]
        )
        background_img = Image.open(ASSSETS_DIR + "/bg.png").resize(
            (500, 379), Image.LANCZOS
        )
        image.paste(background_img, (0, 0), background_img)
        skin = skin.resize((500, 394), Image.LANCZOS)
        image.paste(skin, (0, 0), skin)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(FONT_DIR, 35)
        draw.text((20, 390), "\n".join(name.split(" | ")), font=font, fill="white")
        if wear != None:
            draw.text((480 - font.getbbox(wear)[2], 435), wear, font=font, fill="white")
        image = image.resize((128, 128), Image.LANCZOS)
        return image

    def generate_item_card_band(
        self, image: Image.Image, color: str, stoke_color
    ) -> Image.Image:
        band_bg = Image.new("RGBA", (500, 121), color)
        image.paste(band_bg, (0, 379), band_bg)
        band = Image.new("RGBA", (300, 20), stoke_color)
        band = band.rotate(45, expand=1)
        for i in range(7):
            image.paste(band, (-130 + i * 80, 350), band)
        return image

    async def download_image(self, url) -> Image.Image:
        """
        下载图片，支持通过 HTTP 代理
        """
        try:
            proxy = get_config("proxy", None)  # 从配置中获取代理
            async with httpx.AsyncClient(verify=False, proxy=proxy) as client:
                response = await client.get(url, timeout=10)
                img = Image.open(BytesIO(response.content))
                return img
        except Exception as e:
            print(f"图片下载失败")
            return Image.open(os.path.join(ASSSETS_DIR, "error.png"))

    def img_from_PIL(self, pic: Image.Image) -> str:
        buf = BytesIO()
        pic.save(buf, format="PNG")
        return buf.getvalue()

    async def img_from_url(self, url: str) -> str:
        proxy = get_config("proxy", None)     
        async with httpx.AsyncClient(verify=False,proxy=proxy) as client:
            response = await client.get(url, timeout=10)
            return response.content

    def generate_case_list_img(self, case_list: list, start_index: int = 1):
        """
        根据箱子列表生成图片，并为每个箱子添加序号。
        :param case_list: 箱子名称列表
        :param start_index: 序号起始值
        """
        ttf_path = FONT_DIR
        font = ImageFont.truetype(ttf_path, 25)

        # 计算每行的高度
        line_height = font.getbbox("A")[3] + 2

        # 行数
        rows = len(case_list) // 2 + 1
        width = len(case_list[0]) * 100
        height = (rows + 1) * line_height

        # 设置每列的宽度
        column_width = width // 2
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)

        # 遍历列表并绘制文本
        for i, item in enumerate(case_list):
            # 计算文本所在列的坐标
            if i % 2 == 0:
                x = 40
            else:
                x = column_width + 10

            # 计算文本所在行的坐标
            y = (i // 2) * line_height + 15

            # 绘制文本，添加序号
            draw.text((x, y), f"{start_index + i}. {item}", font=font, fill="#272829")
        return self.img_from_PIL(image)

    def rare_sorted_func(self, x):
        order = [
            "消费级",
            "工业级",
            "军规级",
            "受限",
            "保密",
            "隐秘",
            "及其罕见的特殊物品",
            "非凡",
        ]
        return order.index(x)

    async def send_case_list(self, event: GroupMessage, case_type: str):
        """
        发送箱子列表图片
        :param event: 群消息事件
        :param case_type: 箱子类型 ("weapon" 或 "souvenir")
        """
        if case_type == "weapon":
            cases = crates.get_case_name_list()
            start_index = 1
            title = "武器箱列表"
        elif case_type == "souvenir":
            cases = crates.get_souvenir_name_list()
            start_index = len(crates.get_case_name_list()) + 1
            title = "皮肤箱列表"
        else:
            return

        cases_list_img_bytes = self.generate_case_list_img(cases, start_index=start_index)
        base64_img = base64.b64encode(cases_list_img_bytes).decode("utf-8")
        cq_image = f"[CQ:image,file=base64://{base64_img}]"
        message = f"以下是{title}：\n" + cq_image
        await send_group_msg_cq(event.group_id, message)

    async def handle_open_case(self, event: GroupMessage, index: int):
        """
        处理开箱逻辑
        :param event: 群消息事件
        :param index: 箱子序号
        """
        weapon_cases = crates.get_case_name_list()
        skin_cases = crates.get_souvenir_name_list()
        all_cases = weapon_cases + skin_cases

        # 检查序号是否有效
        if index < 1 or index > len(all_cases):
            await event.api.post_group_msg(event.group_id, text="无效的序号，请检查列表")
            return

        # 获取箱子名称
        crate_name = all_cases[index - 1]
        crate = crates.get_case_by_name(crate_name) or crates.get_souvenir_by_name(crate_name)
        if not crate:
            await event.api.post_group_msg(event.group_id, text="未找到对应的箱子")
            return

        # 获取用户名称
        user_name = event.sender.card or event.sender.nickname

        # 开箱逻辑
        items = crates.open_crate_multiple(crate, amount=20)  # 默认开20箱子
        opened_skins: List[SelectedSkin] = []
        for item in items:
            opened_skins.append(skins.get_skins(item.name))

        # 合成图片
        image_bytes = await self.merge_images(opened_skins, crate.name, crate.image, user_name)

        # 发送图片
        cq_image = f"[CQ:image,file=base64://{base64.b64encode(image_bytes).decode('utf-8')}]"
        await send_group_msg_cq(event.group_id, cq_image)
