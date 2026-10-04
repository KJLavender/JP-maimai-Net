# -*- coding: utf-8 -*-
"""
用 Google Places API (New) Place Details 補營業時間 → 寫回 maimai_full.csv「營業時間」，
並在「營業時間來源」欄標 Google（網頁會顯示「Google 地圖」字樣）。

對象：有 google_place_id 的店中，台灣全部（SEGA/MGM 時間不可靠）＋日本官方沒登記時間的。
注意：Google 條款不允許長期快取 place ID 以外的內容，這是使用者知情後選擇的一次性補資料。

計費：每間 1 次 Place Details，欄位 regularOpeningHours → Enterprise 等級，每月免費 1,000 次。
本腳本上限 MAX_CALLS 次，並與 add_google_ids.py 共用 google_usage.json 記帳。

執行:
  python add_google_hours.py --test 3   # 只查 3 間印出來，不寫檔
  python add_google_hours.py            # 正式補
"""
import argparse, collections, csv, datetime, json, os, sys, time
import requests
from add_google_ids import load_key

MAX_CALLS = 600             # 與 Cloud Console 的 GetPlaceRequest per day 配額一致
USAGE = "google_usage.json"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", type=int, default=0)
    args = ap.parse_args()
    key = load_key()
    if not key:
        sys.exit("找不到 GOOGLE_MAPS_API_KEY（放在 .env）")

    rows = list(csv.reader(open("maimai_full.csv", encoding="utf-8-sig")))
    head = [h.lstrip("﻿").strip() for h in rows[0]]
    if "營業時間來源" not in head:
        head.append("營業時間來源")
    col = {h: i for i, h in enumerate(head)}
    body = [r + [""] * (len(head) - len(r)) for r in rows[1:]]

    todo = [r for r in body if r[col["google_place_id"]] and r[col["營業時間來源"]] != "Google"
            and (r[col["都道府縣"]] == "台灣" or not r[col["營業時間"]])]
    if args.test:
        todo = todo[: args.test]
    month = datetime.date.today().strftime("%Y-%m")
    usage = json.load(open(USAGE, encoding="utf-8")) if os.path.exists(USAGE) else {}
    used = usage.get(month + ":details", 0)
    print(f"要查 {len(todo)} 間；本月 Place Details 已用 {used} 次，本次上限 {MAX_CALLS}")
    if len(todo) > MAX_CALLS:
        print(f"超過上限，只查前 {MAX_CALLS} 間（剩下的明天再跑會接著補）")
        todo = todo[:MAX_CALLS]

    s = requests.Session()
    got = empty = 0
    for i, r in enumerate(todo):
        lang = "zh-TW" if r[col["都道府縣"]] == "台灣" else "ja"
        res = s.get(f"https://places.googleapis.com/v1/places/{r[col['google_place_id']]}",
                    params={"languageCode": lang}, timeout=20,
                    headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "regularOpeningHours"})
        used += 1
        usage[month + ":details"] = used
        json.dump(usage, open(USAGE, "w", encoding="utf-8"), indent=1)
        if res.status_code == 429:
            print("Google 回 429：今天的配額用完了，明天再跑"); break
        if res.status_code != 200:
            print(f"  ! {r[col['名稱']]}: HTTP {res.status_code}"); continue
        h = to_hours(res.json().get("regularOpeningHours"))
        if args.test or (i < 5):
            print(f"  {r[col['名稱']][:28]:28} 原本「{r[col['營業時間']]}」→ Google「{h or '（無）'}」")
        if h:
            r[col["營業時間"]], r[col["營業時間來源"]] = h, "Google"; got += 1
        else:
            empty += 1
        if (i + 1) % 100 == 0:
            print(f"  … {i+1}/{len(todo)}", flush=True)
        time.sleep(0.05)

    print(f"補上 {got} 間、Google 也沒有 {empty} 間；本月 Place Details 累計 {used} 次")
    if args.test:
        print("(--test 模式，未寫回)"); return
    with open("maimai_full.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(body)
    print("已寫回 maimai_full.csv")


if __name__ == "__main__":
    main()
