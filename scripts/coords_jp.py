# -*- coding: utf-8 -*-
# 只抓 47 個清單頁（約 1 分鐘），把每間店的經緯度併回現有 data/arcades.csv。
# 不需重跑 20 分鐘的詳細補抓。用 sid（詳細連結內）對應，抓不到再用店名+地址。
# 需求: pip install requests beautifulsoup4 ；執行: python scripts/coords_jp.py
import paths
import csv, re, sys, time, os
import requests
from bs4 import BeautifulSoup

BASE = "https://location.am-all.net/alm/location"
GM = 96
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")}
SLEEP = 0.6
COORD_RE = re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)")
SID_RE = re.compile(r"sid=(\d+)")


def parse_list_coords(html):
    """回傳 {sid:(lat,lng)} 與 {(name,addr):(lat,lng)}。"""
    soup = BeautifulSoup(html, "html.parser")
    by_sid, by_na = {}, {}
    for nm in soup.select(".store_name"):
        li = nm.find_parent("li")
        if not li:
            continue
        name = nm.get_text(strip=True)
        ad = li.select_one(".store_address")
        addr = ad.get_text(strip=True) if ad else ""
        gm = li.select_one(".store_bt_google_map")
        mc = COORD_RE.search(gm.get("onclick", "") if gm else "")
        if not mc:
            continue
        lat, lng = mc.group(1), mc.group(2)
        db = li.select_one(".bt_details")
        ms = SID_RE.search(db.get("onclick", "") if db else "")
        if ms:
            by_sid[ms.group(1)] = (lat, lng)
        by_na[(name, addr)] = (lat, lng)
    return by_sid, by_na


def get(session, params, retries=3):
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


def build_lookup():
    s = requests.Session()
    get(s, {"gm": GM}); time.sleep(SLEEP)
    by_sid, by_na = {}, {}
    for at in range(47):
        print(f"清單頁 {at+1}/47 …", end="\r", flush=True)
        html = get(s, {"gm": GM, "at": at, "ct": 1000})
        a, b = parse_list_coords(html)
        by_sid.update(a); by_na.update(b)
        time.sleep(SLEEP)
    print(f"\n座標庫：sid {len(by_sid)} 筆、名址 {len(by_na)} 筆")
    return by_sid, by_na


def main():
    if not os.path.exists(paths.ARCADES):
        print("找不到 data/arcades.csv，請先在同資料夾執行。"); return
    by_sid, by_na = build_lookup()

    with open(paths.ARCADES, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    head = [h.lstrip("\ufeff").strip() for h in rows[0]]
    for col in ("緯度", "經度"):
        if col not in head:
            head.append(col)
    iL, iLng = head.index("緯度"), head.index("經度")
    iN, iA = head.index("名稱"), head.index("地址")
    iDet = head.index("詳細連結") if "詳細連結" in head else -1

    hit, out = 0, []
    for row in rows[1:]:
        row = row + [""] * (len(head) - len(row))
        sid = ""
        if iDet >= 0:
            m = SID_RE.search(row[iDet]); sid = m.group(1) if m else ""
        c = by_sid.get(sid) or by_na.get((row[iN].strip(), row[iA].strip()))
        if c:
            row[iL], row[iLng] = c[0], c[1]; hit += 1
        out.append(row)

    with open(paths.ARCADES, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(out)
    print(f"完成：{hit}/{len(out)} 間補上座標 → data/arcades.csv")
    if hit < len(out):
        print(f"（{len(out)-hit} 間對不到座標，通常是已下架或名稱異動，網頁會照常顯示只是沒距離）")


if __name__ == "__main__":
    main()
