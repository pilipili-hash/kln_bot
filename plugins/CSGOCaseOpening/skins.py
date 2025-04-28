import json
import random
from os.path import dirname
from typing import List
from .model import SelectedSkin, Skin

JSON_DIR = dirname(__file__) + "/json"

class Skins:
    def __init__(self):
        self.skins: List[Skin] = []
        self.skins: List[Skin] = [
            Skin(**self.add_missing_fields(item)) for item in self.get_skins_json()
        ]

    def get_skins_json(self):
        with open(f"{JSON_DIR}/skins.json", "rb") as f:
            data = f.read()
            return json.loads(data)

    def add_missing_fields(self, item: dict) -> dict:
        """为缺失字段提供默认值"""
        if "collection" not in item:
            item["collection"] = None  # 如果缺少 collection 字段，设置为 None
        return item

    def get_skins(self, name: str) -> SelectedSkin:
        for skin in self.skins:
            if skin.name == name:
                return SelectedSkin(
                    id=skin.id,
                    name=skin.name,
                    image=skin.image,
                    rarity=skin.rarity.name,  # 将 Rarity 对象转换为字符串
                    wear=random.choice(skin.wears).name if skin.wears else None,  # 将 Wear 对象转换为字符串
                )

    def search_skin(self, skin_name: str) -> List[Skin]:
        found_skin_list = []
        for skin in self.skins:
            if skin.pattern and skin_name.lower() in skin.pattern.name:
                found_skin_list.append(skin)
        return found_skin_list
