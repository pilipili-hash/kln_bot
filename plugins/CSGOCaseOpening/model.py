from typing import List, Literal, Optional
from pydantic import BaseModel

class Rarity(BaseModel):
    id: str
    name: str
    # color: str

class Contains(BaseModel):
    id: str
    name: str
    rarity: Rarity
    image: str

class Crate(BaseModel):
    id: str
    name: str
    description: Optional[str]
    type: Literal["Case", "Souvenir"]
    first_sale_date: Optional[str]
    contains: List[Contains]
    contains_rare: List[Contains]
    image: str

class Weapon(BaseModel):
    id: str
    name: Optional[str]

class Category(BaseModel):
    id: Optional[str]
    name: Optional[str]

class Pattern(BaseModel):
    id: str
    name: str

class Wear(BaseModel):
    id: str
    name: str

class Collections(BaseModel):
    id: str
    name: str
    image: str

class Crates(BaseModel):
    id: str
    name: str
    image: str

class Skin(BaseModel):
    id: str
    name: str
    description: Optional[str]
    weapon: Optional[Weapon]
    category: Category
    pattern: Optional[Pattern]
    min_float: Optional[float]
    max_float: Optional[float]
    rarity: Rarity
    stattrak: bool
    souvenir: Optional[bool] = False  # 设置为可选字段，默认值为 False
    paint_index: Optional[str]
    wears: Optional[List[Wear]] = []  # 设置为可选字段，默认值为空列表
    collection: Optional[str] = None  # 设置为可选字段，默认值为 None
    crates: Optional[List[Crates]]
    image: str

class SelectedSkin(BaseModel):
    id: str
    name: str
    image: str
    rarity: str
    wear: Optional[str]

class Config(BaseModel):
    csgo_user_cd: int = 0
    csgo_group_cd: int = 0
