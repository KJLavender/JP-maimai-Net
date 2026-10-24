# -*- coding: utf-8 -*-
"""台灣機廳連鎖品牌：SEGA 英文店名 ↔ Music Game Map 中文店名。
mgm_tw.py 配對中文名、google_place_ids.py 比對 Google 店名、build_site.py 顯示用（只用標準函式庫）。"""
import re

# (英文店名 regex, 中文店名 regex, 顯示用中文品牌；空字串＝不確定中文名，不顯示)
BRANDS = [
    (r"TOM'?S\s*WORLD", r"湯姆熊", "湯姆熊"),
    (r"HALA", r"哈啦", "哈啦星球"),
    (r"SHIRONEKOYA", r"白喵", "白喵一番屋"),
    (r"GiGO", r"GiGO", "GiGO"),
    (r"SIN\s*YI\s*CITY", r"新藝城", "新藝城"),
    (r"HAPPY\s*100", r"HAPPY\s*100", "Happy100"),
    (r"YOUNG\s*KEY", r"永淇", "永淇"),
    (r"VAN'?S", r"小凡", "小凡樂園"),
    (r"X50", r"X50", "X50"),
    (r"HURO", r"湖若|HURO", ""),
    (r"RED\s*HAT", r"紅帽象", "紅帽象"),
    (r"CATCH\s*BUFFET", r"夾到飽", "夾到飽"),
    (r"WAWA", r"娃娃帝國", "娃娃帝國"),
    (r"TIGER'?S\s*WORLD", r"老虎", "老虎歡樂世界"),
    (r"CARTOONNI", r"卡通尼", "卡通尼樂園"),
    (r"KILEDO", r"奇樂多", "奇樂多"),
    (r"RHYTHM\s*ARENA", r"Rhythm\s*Arena|競音殿堂", "競音殿堂"),
    (r"CHAMELEON", r"變色龍", "變色龍歡樂世界"),
]


def brand(name, zh=False):
    """店名屬於哪個品牌（BRANDS 的索引），認不出來回 None。zh=True 表示 name 是中文店名。"""
    for i, pair in enumerate(BRANDS):
        if re.search(pair[1 if zh else 0], name, re.I):
            return i
    return None


def brand_zh(name):
    """英文店名 → 中文品牌名（認不出來或不確定回空字串）。"""
    i = brand(name)
    return BRANDS[i][2] if i is not None else ""
