# -*- coding: utf-8 -*-
"""
用 Google Places API (New) Place Details 補營業時間 → 寫回 data/arcades.csv「營業時間」，
並在「營業時間來源」欄標 Google（網頁會顯示「Google 地圖」字樣）。

對象：有 google_place_id 的店中，台灣全部（SEGA/MGM 時間不可靠）＋日本官方沒登記時間的，
      以及之前已用 Google 時間、但還沒有「週營業時間」（一週七天各自的時段）的。
台灣沒有中文名的店，順便用 Google 的店名補（同一次查詢，不另外計費）。
注意：Google 條款不允許長期快取 place ID 以外的內容，這是使用者知情後選擇的一次性補資料。

計費：每間 1 次 Place Details，欄位 regularOpeningHours → Enterprise 等級，每月免費 1,000 次。
本腳本上限 MAX_CALLS 次，並與 google_place_ids.py 共用 data/google_usage.json 記帳。

執行:
  python scripts/google_hours.py --test 3   # 只查 3 間印出來，不寫檔
  python scripts/google_hours.py            # 正式補
"""
import paths
import argparse, collections, csv, datetime, json, os, sys, time
import requests
from google_place_ids import load_key

MAX_CALLS = 600             # 與 Cloud Console 的 GetPlaceRequest per day 配額一致
MONTHLY_FREE = 1000         # Place Details Enterprise 每月免費次數：本腳本不會超過，確保 0 元
USAGE = paths.GOOGLE_USAGE


def fmt(m):
    """分鐘 → HH:MM；跨夜的結束時間照官方資料慣例寫成 24:00 以內的鐘點（parseHours 會自動 +24h）。"""
    if m == 1440:
        return "24:00"
    m %= 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def to_hours(oh):
    """regularOpeningHours → 「10:00〜22:00」/「24時間」；一週各天不同時取最常見的那組。"""
    periods = (oh or {}).get("periods", [])
    if not periods:
        return ""
    if len(periods) == 1 and "close" not in periods[0]:
        return "24時間"
    spans = collections.Counter()
    for p in periods:
        o, c = p["open"], p.get("close")
        if not c:
            continue
        st = o.get("hour", 0) * 60 + o.get("minute", 0)
        en = c.get("hour", 0) * 60 + c.get("minute", 0) + ((c["day"] - o["day"]) % 7) * 1440
        if en - st >= 1440:
            spans["24時間"] += 1
        else:
            spans[f"{fmt(st)}〜{fmt(en)}"] += 1
    return spans.most_common(1)[0][0] if spans else ""


def to_week(oh):
    """regularOpeningHours → 日～六 7 個時段字串（Google 的 day 0 = 星期日，跟 JS getDay 一樣）；沒開的天是空字串。"""
    periods = (oh or {}).get("periods", [])
    if len(periods) == 1 and "close" not in periods[0]:
        return ["24時間"] * 7
    week = [""] * 7
    for p in periods:
        o, c = p["open"], p.get("close")
        if not c or week[o["day"]]:      # 一天分兩段（午休）時只取第一段
            continue
        st = o.get("hour", 0) * 60 + o.get("minute", 0)
        en = c.get("hour", 0) * 60 + c.get("minute", 0) + ((c["day"] - o["day"]) % 7) * 1440
        week[o["day"]] = "24時間" if en - st >= 1440 else f"{fmt(st)}〜{fmt(en)}"
    return week


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", type=int, default=0)
    args = ap.parse_args()
    key = load_key()
    if not key:
        sys.exit("找不到 GOOGLE_MAPS_API_KEY（放在 .env）")

    rows = list(csv.reader(open(paths.ARCADES, encoding="utf-8-sig")))
    head = [h.lstrip("﻿").strip() for h in rows[0]]
    for c in ("營業時間來源", "週營業時間", "中文名"):
        if c not in head:
            head.append(c)
    col = {h: i for i, h in enumerate(head)}
    body = [r + [""] * (len(head) - len(r)) for r in rows[1:]]

    def need(r):
        if not r[col["google_place_id"]]:
            return False
        if r[col["營業時間來源"]] == "Google":
            return not r[col["週營業時間"]]                  # 之前補過，但只有單一時段
        return r[col["都道府縣"]] == "台灣" or not r[col["營業時間"]]
    # 先補完全沒時間的、台灣的；已有 Google 時間只差「每天各自時段」的排最後（額度不夠時下次再補）
    todo = sorted((r for r in body if need(r)), key=lambda r: r[col["營業時間來源"]] == "Google")
    if args.test:
        todo = todo[: args.test]
    month = datetime.date.today().strftime("%Y-%m")
    usage = json.load(open(USAGE, encoding="utf-8")) if os.path.exists(USAGE) else {}
    used = usage.get(month + ":details", 0)
    cap = min(MAX_CALLS, MONTHLY_FREE - used)
    print(f"要查 {len(todo)} 間；本月 Place Details 已用 {used} 次，本次上限 {cap}（不超過每日配額與每月免費額度）")
    if len(todo) > cap:
        print(f"超過上限，只查前 {cap} 間（剩下的下次再跑會接著補）")
        todo = todo[:max(cap, 0)]

    s = requests.Session()
    got = empty = 0
    for i, r in enumerate(todo):
        lang = "zh-TW" if r[col["都道府縣"]] == "台灣" else "ja"
        res = s.get(f"https://places.googleapis.com/v1/places/{r[col['google_place_id']]}",
                    params={"languageCode": lang}, timeout=20,
                    headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "regularOpeningHours,displayName"})
        used += 1
        usage[month + ":details"] = used
        json.dump(usage, open(USAGE, "w", encoding="utf-8"), indent=1)
        if res.status_code == 429:
            print("Google 回 429：今天的配額用完了，明天再跑"); break
        if res.status_code != 200:
            print(f"  ! {r[col['名稱']]}: HTTP {res.status_code}"); continue
        js = res.json()
        h = to_hours(js.get("regularOpeningHours"))
        if r[col["都道府縣"]] == "台灣" and not r[col["中文名"]] and js.get("displayName", {}).get("text"):
            r[col["中文名"]] = js["displayName"]["text"]
        if args.test or (i < 5):
            print(f"  {r[col['名稱']][:28]:28} 原本「{r[col['營業時間']]}」→ Google「{h or '（無）'}」")
        if h:
            r[col["營業時間"]], r[col["營業時間來源"]] = h, "Google"; got += 1
            r[col["週營業時間"]] = "|".join(to_week(js.get("regularOpeningHours")))
        else:
            empty += 1
        if (i + 1) % 100 == 0:
            print(f"  … {i+1}/{len(todo)}", flush=True)
        time.sleep(0.05)

    print(f"補上 {got} 間、Google 也沒有 {empty} 間；本月 Place Details 累計 {used} 次")
    if args.test:
        print("(--test 模式，未寫回)"); return
    with open(paths.ARCADES, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(body)
    print("已寫回 data/arcades.csv")


if __name__ == "__main__":
    main()
