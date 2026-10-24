# -*- coding: utf-8 -*-
"""台灣機廳連鎖品牌：SEGA 英文店名 ↔ Music Game Map 中文店名，以及人工確認過的個別店對應。
mgm_tw.py 配對中文名、google_place_ids.py 比對 Google 店名、build_site.py 顯示用（只用標準函式庫）。"""
import re

# 自動配對會配錯的店（人工對過 Google 地圖）：SEGA 店名 → MGM id／Google place ID／中文名（MGM 沒有時）
MANUAL = {
    # 搬到信陽街 9 號，現在叫抓抓族；舊址旁的「哈啦星球-信陽店」不是這間
    "HALA(XINYANG)": {"mgm": "182", "pid": "ChIJywFzmpypQjQRh4NTM6lu5N0"},
    # 公館有一店、二店；SEGA 登記的遊戲有 Project DIVA，MGM 上只有二店有 DIVA
    "HALA PLANET": {"mgm": "222", "pid": "ChIJFwkUFACpQjQRAV1k9zdWuzQ"},
    "TOM'S WORLD (HANSHIN@KAOHSIUNG)": {"zh": "湯姆熊漢神巨蛋店", "pid": "ChIJWYPGBEoFbjQRWFYYqw5t2Z0"},
    # SEGA 登記成 HURO WORLD，實際是同地址（忠孝東路七段 369 號 C 棟 6F）的奇樂多
    "HURO WORLD(CITY LINK@NANGANG)": {"mgm": "133", "pid": "ChIJl_iiaWerQjQRN7cqEb0bM4Y"},
    "TOM'S WORLD(GLOBALMALL-NANGANG)": {"pid": "ChIJq5GIRROrQjQRKsUwmBspP7Q"},
    "KILEDO-XIN△YI": {"mgm": "296", "pid": "ChIJRxj6FGGrQjQR_wGpsQU5SZA"},
    "LIBAO COMPANY": {"zh": "力堡台北店", "pid": "ChIJ7axBX16pQjQRdt9QD7XFjeY"},
    "CATCH BUFFET(DA-NAN@SHLIN)": {"mgm": "189", "pid": "ChIJhb5qVKGvQjQRKPl0EGuKjxg"},
    "TOM'S WORLD (CITY PLAZA@TAMSUI)": {"zh": "湯姆熊淡水大都會店", "pid": "ChIJQ0m3WA6VbjQRhemhBvuGLqY"},
    "TOM'S WORLD(HONHUI PLAZA@NEW TAIPEI)": {"zh": "湯姆熊新莊宏匯店", "pid": "ChIJAyeVIuKpQjQRZxNWqZEvBss"},
    "TOM'S WORLD (YULON CITY@XINDIAN)": {"zh": "湯姆熊新店裕隆城店", "pid": "ChIJw12hkPQBaDQR-XevxnmT7Ks"},
    "TOM'S WORLD MITSUI OUTLET PARK-LINKOU": {"zh": "湯姆熊林口三井店", "pid": "ChIJWYpqZgCnQjQRU9eMUxoFojo"},
    "TIGER'S WORLD-CARREFOUR ZHONGYUAN": {"zh": "老虎歡樂世界中原店", "pid": "ChIJQ2KuZAAjaDQRtjbP390X6sM"},
    "TOM'S WORLD (CHUNGYO@TAICHUNG)": {"zh": "湯姆熊台中中友店", "pid": "ChIJa9PFImY9aTQRUTWWmS9lpEw"},
    "HALA (FENGJIA)": {"zh": "哈啦星球台中逢甲店", "pid": "ChIJB3SXREIXaTQRUD4wg1PN0U4"},
    "TOM'S WORLD MITSUI OUTLET PARK-TAICHUNG": {"mgm": "281", "pid": "ChIJqdFXHwBraTQRXnVoyj64lMc"},
    "TOM'S WORLD(CARREFOUR@CHANGHUA)": {"mgm": "249", "pid": "ChIJm5-rBxw5aTQR61u88fj4Xf4"},
    "TOM'S WORLD (HAIDIAN-LI@TAINAN))": {"zh": "湯姆熊台南海佃店", "pid": "ChIJP3zB17J3bjQRYJpIz1_qGuM"},
    "HAPPY100 (E DA)": {"mgm": "52", "pid": "ChIJM9GG6RsRbjQRBZZ1YhEqsu0"},
    "TOM'S WORLD (SHOWTIME@KONG-SAN)": {"mgm": "237", "pid": "ChIJrf-jirwPbjQRp2rNpZ6JaFU"},
    # 只確定中文名：Google 上找不到同地址的店（可能已搬家或用別的名字）
    "RED HAT ELEPHANT (TAOYUAN)": {"zh": "紅帽象桃園統領店"},
    "GUOBIN AMUSEMENT PARK": {"zh": "太鼓歡樂園"},
}

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
