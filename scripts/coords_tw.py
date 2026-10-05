# -*- coding: utf-8 -*-
"""
補齊台灣機廳的經緯度 → 併回 data/arcades.csv
資料來源: SEGA ALL.Net設置店舗検索 gm=98（maimai DX International Version）
跟 coords_jp.py 同邏輯：抓清單頁的 GoogleMap 座標，用 sid（詳細連結裡）對應寫回。
只更新台灣那些列，日本資料不受影響。

需求: pip install requests beautifulsoup4
執行: python scripts/coords_tw.py
"""
import paths
import csv, re, sys, time
import requests
from bs4 import BeautifulSoup

BASE = "https://location.am-all.net/alm/location"
GM = 98
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")}
SLEEP = 0.6
COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")
SID_RE = re.compile(r"sid=(\d+)")


def get(session, params=None, retries=3):
    for i in range(retries):
        try:
            r = session.get(BASE, params=params, headers=HEADERS, timeout=20)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
        except requests.RequestException as e:
            print(f"  ! {e} 重試{i+1}", file=sys.stderr)
        time.sleep(SLEEP * 2)
    return ""


def find_region_code(html, keywords=("Taiwan", "台灣", "台湾")):
    soup = BeautifulSoup(html, "html.parser")
    for sel in soup.find_all("select"):
        opts = sel.find_all("option")
        texts = [o.get_text(strip=True) for o in opts]
        if any(("Taiwan" in t) or ("Hong Kong" in t) for t in texts):
            for o in opts:
                t = o.get_text(strip=True)
                if any(k in t for k in keywords):
                    return o.get("value", ""), t
    return "", ""


def parse_list_coords(html):
    soup = BeautifulSoup(html, "html.parser")
    by_sid = {}
    for nm in soup.select(".store_name"):
        li = nm.find_parent("li")
        if not li:
            continue
        gm = li.select_one(".store_bt_google_map")
        mc = COORD_RE.search(gm.get("onclick", "") if gm else "")
        if not mc:
            continue
        db = li.select_one(".bt_details")
        ms = SID_RE.search(db.get("onclick", "") if db else "")
        if ms:
            by_sid[ms.group(1)] = (mc.group(1), mc.group(2))
    return by_sid


def main():
    if not os.path.exists(paths.ARCADES):
        print("找不到 data/arcades.csv，請先在同資料夾跑過 scrape_tw.py。"); return
    s = requests.Session()
    top_html = get(s, {"gm": GM})
    time.sleep(SLEEP)
    at_code, at_label = find_region_code(top_html)
    if not at_code:
        print("找不到 Taiwan 選項，無法補座標。"); return
    print(f"地區代碼：{at_label} → at={at_code}")

    html = get(s, {"gm": GM, "at": at_code, "ct": 1000})
    by_sid = parse_list_coords(html)
    print(f"清單座標：{len(by_sid)} 筆")

    with open(paths.ARCADES, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    head = [h.lstrip("\ufeff").strip() for h in rows[0]]
    for col in ("緯度", "經度"):
        if col not in head:
            head.append(col)
    iL, iLng = head.index("緯度"), head.index("經度")
    iP = head.index("都道府縣") if "都道府縣" in head else -1
    iDet = head.index("詳細連結") if "詳細連結" in head else -1

    hit, out = 0, []
    for row in rows[1:]:
        row = row + [""] * (len(head) - len(row))
        is_tw = (iP >= 0 and row[iP].strip() == "台灣")
        if is_tw and iDet >= 0:
            m = SID_RE.search(row[iDet])
            sid = m.group(1) if m else ""
            c = by_sid.get(sid)
            if c:
                row[iL], row[iLng] = c[0], c[1]; hit += 1
        out.append(row)

    with open(paths.ARCADES, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(out)
    print(f"完成：{hit} 間台灣機廳補上座標 → data/arcades.csv（日本資料未變動）")


if __name__ == "__main__":
    import os
    main()
