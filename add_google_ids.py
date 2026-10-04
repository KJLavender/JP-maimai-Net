# -*- coding: utf-8 -*-
"""
用 Google Places API (New) 找出每間店的 Google place ID → 寫回 maimai_full.csv 的「google_place_id」欄。
網頁的「店家資訊」會用 place ID 組 Google 地圖連結，直接開到那間店（不會跳出一串搜尋結果）。

只儲存 place ID：Google 條款允許永久保存 place ID，其他內容（店名、座標、營業時間…）不能快取，
所以比對時用到的 displayName / location 只在記憶體裡用，不寫檔。

計費：每間店 1 次 Text Search（欄位 id/displayName/location → Pro 等級，每月免費 5,000 次）。
本腳本另外在 google_usage.json 記錄每月用量，超過 MONTHLY_CAP 就停（再加上 Cloud Console 的每日配額）。

需求: .env 內 GOOGLE_MAPS_API_KEY=...
執行:
  python add_google_ids.py --test 5     # 只跑 5 間（含新竹巨城店）印出結果，不寫檔
  python add_google_ids.py              # 只補還沒有 place ID 的店
  python add_google_ids.py --redo       # 全部重找
"""
import argparse, csv, json, math, os, re, sys, time, unicodedata, datetime
import requests

URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.id,places.displayName,places.location"
MONTHLY_CAP = 1150          # Text Search Pro 每月免費 5,000；保守設在一次跑完全部店的量
MAX_DIST_M = 300            # Google 座標與 SEGA 座標超過這距離就不採用
USAGE = "google_usage.json"
# 人工確認過 Google 配錯的店（配到商場、KTV、餐廳…）：不給 place ID，網頁退回用店名搜尋
SKIP = {"キッズランド", "星狩物語岸和田店", "HURO WORLD(CITY LINK@NANGANG)", "TOM'S WORLD(GLOBALMALL-NANGANG)"}


def load_key():
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            if line.startswith("GOOGLE_MAPS_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("GOOGLE_MAPS_API_KEY", "")


def haversine_m(a, b):
    r = math.radians
    dla, dlo = r(b[0] - a[0]), r(b[1] - a[1])
    s = math.sin(dla / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(dlo / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(s))


def norm(s):
    """全形→半形、去空白與符號、小寫，用來比對店名。"""
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s\-‐ー－・･'’()（）\[\]【】@&.,、。!！/]", "", s)


def similarity(a, b):
    """兩個店名共有的字元比例（不用外部套件，夠用來挑候選）。"""
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    common = sum(min(a.count(c), b.count(c)) for c in set(a))
    return common / max(len(a), len(b))


class Usage:
    def __init__(self):
        self.month = datetime.date.today().strftime("%Y-%m")
        self.data = json.load(open(USAGE, encoding="utf-8")) if os.path.exists(USAGE) else {}

    @property
    def used(self):
        return self.data.get(self.month, 0)

    def add(self):
        self.data[self.month] = self.used + 1
        json.dump(self.data, open(USAGE, "w", encoding="utf-8"), indent=1)


def search(session, key, query, lat, lng, lang):
    body = {"textQuery": query, "pageSize": 5, "languageCode": lang,
            "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 200.0}}}
    r = session.post(URL, json=body, timeout=20,
                     headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS})
    if r.status_code == 429:
        raise SystemExit("Google 回 429：今天的配額用完了，明天再跑（已找到的會保留）")
    r.raise_for_status()
    return r.json().get("places", [])


def pick(cands, names, lat, lng):
    """在 MAX_DIST_M 內挑店名最像的；同分取近的。回傳 (place, 距離, 相似度) 或 None。"""
    best = None
    for p in cands:
        loc = p.get("location", {})
        d = haversine_m((lat, lng), (loc.get("latitude", 0), loc.get("longitude", 0)))
        if d > MAX_DIST_M:
            continue
        sim = max(similarity(n, p.get("displayName", {}).get("text", "")) for n in names if n)
        score = (round(sim, 2), -d)
        if best is None or score > best[0]:
            best = (score, p, d, sim)
    return best and best[1:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", type=int, default=0)
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args()
    key = load_key()
    if not key:
        sys.exit("找不到 GOOGLE_MAPS_API_KEY（放在 .env）")

    rows = list(csv.reader(open("maimai_full.csv", encoding="utf-8-sig")))
    head = [h.lstrip("﻿").strip() for h in rows[0]]
    if "google_place_id" not in head:
        head.append("google_place_id")
    col = {h: i for i, h in enumerate(head)}
    body = [r + [""] * (len(head) - len(r)) for r in rows[1:]]

    for r in body:
        if r[col["名稱"]] in SKIP:
            r[col["google_place_id"]] = ""
    todo = [r for r in body if r[col["緯度"]] and r[col["名稱"]] not in SKIP
            and (args.redo or not r[col["google_place_id"]])]
    if args.test:
        first = [r for r in todo if "GIANT CITY" in r[col["名稱"]]]
        todo = first + [r for r in todo if r not in first][: args.test - len(first)]
    usage = Usage()
    print(f"要找 {len(todo)} 間；本月已用 {usage.used}/{MONTHLY_CAP} 次")

    s = requests.Session()
    hit = miss = 0
    for i, r in enumerate(todo):
        if usage.used >= MONTHLY_CAP:
            print(f"已達本月上限 {MONTHLY_CAP} 次，停止（下個月再跑會接著補）"); break
        name, zh = r[col["名稱"]], r[col["中文名"]] if "中文名" in col else ""
        lat, lng = float(r[col["緯度"]]), float(r[col["經度"]])
        query = zh or re.sub(r"[()@]+", " ", name).strip()
        lang = "zh-TW" if r[col["都道府縣"]] == "台灣" else "ja"   # 店名用當地語言回傳才比對得到
        cands = search(s, key, query, lat, lng, lang); usage.add()
        got = pick(cands, [name, zh], lat, lng)
        if got:
            p, d, sim = got
            r[col["google_place_id"]] = p["id"]; hit += 1
            if args.test or sim < 0.5:   # 相似度低的印出來人工看
                print(f"  {'OK ' if sim >= 0.5 else '?? '}{query[:28]:28} → {p['displayName']['text'][:28]:28} {d:5.0f}m sim={sim:.2f}")
        else:
            miss += 1
            if args.test:
                print(f"  -- {query[:28]:28} → （{MAX_DIST_M}m 內沒有候選）")
        if (i + 1) % 100 == 0:
            print(f"  … {i+1}/{len(todo)}", flush=True)
        time.sleep(0.05)

    print(f"找到 {hit}、找不到 {miss}；本月累計 {usage.used} 次")
    if args.test:
        print("(--test 模式，未寫回)"); return
    with open("maimai_full.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(body)
    print("已寫回 maimai_full.csv")


if __name__ == "__main__":
    main()
