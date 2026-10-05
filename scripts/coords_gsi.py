# -*- coding: utf-8 -*-
"""
SEGA 清單頁沒有 GoogleMap 座標的店 → 用國土地理院（GSI）地址檢索把日本地址轉成經緯度。
免費、不需 API key。只處理「緯度」為空的日本店。

執行: python scripts/coords_gsi.py
"""
import paths
import csv, re, time, unicodedata
import requests

GSI = "https://msearch.gsi.go.jp/address-search/AddressSearch"


def clean(addr):
    """全形→半形，去掉建物名/樓層（GSI 只認到番地），例：「…１−３−１イオン３階」→「…1-3-1」"""
    a = unicodedata.normalize("NFKC", addr).replace("ー", "-").replace("−", "-").replace("‐", "-")
    m = re.match(r"(.+?\d+(?:-\d+){0,3}(?:番地?\d*)?(?:号)?)", a)
    return m.group(1) if m else a


def main():
    rows = list(csv.reader(open(paths.ARCADES, encoding="utf-8-sig")))
    head = [h.lstrip("﻿").strip() for h in rows[0]]
    c = {h: i for i, h in enumerate(head)}
    s = requests.Session()
    hit = 0
    for r in rows[1:]:
        if r[c["緯度"]] or r[c["都道府縣"]] == "台灣":
            continue
        q = clean(r[c["地址"]])
        res = s.get(GSI, params={"q": q}, timeout=20).json()
        if res:
            lng, lat = res[0]["geometry"]["coordinates"]
            r[c["緯度"]], r[c["經度"]] = f"{lat:.7f}", f"{lng:.7f}"
            hit += 1
            print(f"  {r[c['名稱']][:24]:24} {q[:30]:30} → {lat:.5f},{lng:.5f} ({res[0]['properties']['title'][:20]})")
        else:
            print(f"  ?? {r[c['名稱']][:24]:24} {q}")
        time.sleep(0.3)
    with open(paths.ARCADES, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows[1:])
    print(f"補上座標 {hit} 間")


if __name__ == "__main__":
    main()
