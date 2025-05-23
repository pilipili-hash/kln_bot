import json
import random
from os.path import dirname
from typing import List, Optional
import logging
import httpx
from .model import Contains, Crate

JSON_DIR = dirname(__file__) + "/json"
class Crates:
    def __init__(self):
        self.cases: List[Crate] = []
        self.souvenirs: List[Crate] = []

        self.rarity_list = [
            "消费级",
            "工业级",
            "军规级",
            "受限",
            "保密",
            "隐秘",
            "非凡",
            "违禁",
        ]
        self.cases: List[Crate] = [Crate(**item) for item in self.get_cases_json()]
        self.souvenirs: List[Crate] = [
            Crate(**item) for item in self.get_souvenirs_json()
        ]

    def get_cases_json(self):
        with open(f"{JSON_DIR}/cases.json", "rb") as f:
            data = f.read()
            return json.loads(data)

    def get_souvenirs_json(self):
        with open(f"{JSON_DIR}/souvenir.json", "rb") as f:
            data = f.read()
            return json.loads(data)

    # def get_case_name_list(self) -> list:
    #     return [f"{idx+1}. {case.name}" for idx, case in enumerate(self.cases)]
    def get_case_name_list(self) -> list:
    # 获取所有 case 的名称列表，索引从 40 开始
        name_list = [f"{case.name}" for idx, case in enumerate(self.cases)]
    
    # 将名称列表转换为字典格式
        name_dict = {idx + 1: name for idx, name in enumerate(name_list)}
    
    # 将字典写入 c.json 文件
        with open('c.json', 'w', encoding='utf-8') as f:
            json.dump(name_dict, f, ensure_ascii=False, indent=4)

        return name_list
    # def get_souvenir_name_list(self) -> list:
    #     return [f"{idx+41}. {souvenir.name}" for idx, souvenir in enumerate(self.souvenirs)]
    def get_souvenir_name_list(self) -> list:
    # 获取所有 souvenir 的名称列表
     name_list = [souvenir.name for souvenir in self.souvenirs]
    
    # 将名称列表转换为字典格式
     name_dict = {idx+41: name for idx, name in enumerate(name_list)}
    
    # 将字典写入 s.json 文件
     with open('s.json', 'w', encoding='utf-8') as f:
            json.dump(name_dict, f, ensure_ascii=False, indent=4)

     return name_list
    def get_random_case(self) -> dict:
        return random.choice(self.cases)

    def get_case_by_name(self, case_name: str) -> Crate:
        # raw_name = case_name.replace("武器箱", "")
        for case in self.cases:
            if case_name in case.name:
                return case
        return None

    def get_souvenir_by_name(self, sv_name: str) -> Crate:
        # raw_name = sv_name.replace("纪念包", "")
        for sv in self.souvenirs:
            if sv_name in sv.name:
                return sv
        return None
    # def get_case_by_name(self, name: str) -> Optional[Crate]:
        
    #     for case in self.cases:
    #         if case.name == name:
    #          print(f"Found case: {case.name}")
    #         return case
    
    #     return None

    # def get_souvenir_by_name(self, name: str) -> Optional[Crate]:
    #     print(f"Trying to get souvenir with name: {name}")
    #     for souvenir in self.souvenirs:
    #      if souvenir.name == name:
    #         print(f"Found souvenir: {souvenir.name}")
    #         return souvenir
    #     print(f"Souvenir not found: {name}")
    #     return None
    
    def open_case(
        self, case: Crate, probability_list, has_rare: bool, rare_item_prob=0
    ) -> Contains:
        if has_rare and random.random() > rare_item_prob:
            return random.choices(case.contains, probability_list, k=1)[0]
        else:
            return random.choices(case.contains_rare, k=1)[0]

    def open_souvenir(self, sv: Crate, probability_list) -> Contains:
        return random.choices(sv.contains, probability_list, k=1)[0]

    def open_crate_multiple(self, crate: Crate, amount: int) -> List[Contains]:
        items: List[Contains] = []
        result = self.calculate_prob_list(crate)
        for _ in range(amount):
            if crate.type == "Case":
                items.append(
                    self.open_case(
                        crate,
                        result["contains_prob_list"],
                        result["has_rare"],
                        result["rare_item_prob"],
                    )
                )
            else:
                items.append(
                    self.open_souvenir(
                        crate,
                        result["contains_prob_list"],
                    )
                )
        return items

    def calculate_prob_list(self, crate: Crate):
        all_rarities = [key.rarity for key in crate.contains]
        rare_amount_dict = {}
        for rarity in all_rarities:
            rare_amount_dict[rarity.name] = (
                rare_amount_dict[rarity.name] + 1
                if rarity.name in rare_amount_dict
                else 1
            )
        # 箱子内存在的稀有度集合
        unique_rarities = []
        [
            unique_rarities.append(x.name)
            for x in all_rarities
            if x.name not in unique_rarities
        ]
        # 箱子的稀有度概率字典
        rare_prob_dict = {key: 0 for key in unique_rarities}

        has_mil_ind = False
        has_rare = False
        # 罕见的特殊物品物品的概率
        rare_item_prob = 0
        if "军规级" in unique_rarities and "工业" in unique_rarities:
            has_mil_ind = True
        if "隐秘" in unique_rarities:
            has_rare = True
        x = 1
        for i in range(len(unique_rarities)):
            if i == 0:
                rare_prob_dict[unique_rarities[i]] = 1
                continue
            elif has_mil_ind and unique_rarities[i] == "工业级":
                rare_prob_dict[unique_rarities[i]] = rare_prob_dict[
                    unique_rarities[i - 1]
                ] * (5 / 24)
                continue
            else:
                rare_prob_dict[unique_rarities[i]] = (
                    rare_prob_dict[unique_rarities[i - 1]] / 5
                )
        if has_rare:
            rare_item_prob = rare_prob_dict["隐秘"] * (2 / 5)

        # 箱子内的物品按顺序对应的概率列表
        contains_prob_list = []
        # 计算箱子品质的概率 / 计算箱子内品质的数量
        for item in crate.contains:
            contains_prob_list.append(
                rare_prob_dict[item.rarity.name] / rare_amount_dict[item.rarity.name]
            )
        return {
            "contains_prob_list": contains_prob_list,
            "has_rare": has_rare,
            "rare_item_prob": rare_item_prob,
        }
