# -*- coding: utf-8 -*-
"""
一鍵更新資料（給每週排程的 GitHub Actions 用，本機也能跑）：
  1. 重爬 SEGA ALL.Net：日本 47 都道府縣（gm=96）＋台灣（gm=98），含營業時間、遊戲、座標
  2. 用 sid 對回舊的 data/arcades.csv，保留舊資料才有的欄位（中文名、Google place ID、
     Google 營業時間、機台資訊…）；SEGA 這次沒附座標的店用國土地理院補
  3. （--mgm）重抓 Music Game Map，更新台灣中文名與機台資訊
  4. 寫回 data/arcades.csv，並輸出變動摘要 data/update_summary.md（PR 內文用）

不會呼叫 Google API（不花錢）；新開的店要有 Google 連結／時間，請在本機另外跑 google_place_ids.py。

執行:
  python scripts/update_data.py            # 完整更新（約 15–20 分鐘）
  python scripts/update_data.py --mgm      # 連 Music Game Map 一起更新（多約 3 分鐘）
  python scripts/update_data.py --limit 2  # 只爬前 2 個縣＋台灣，測試用，不寫檔
"""
import paths
import argparse, csv, datetime, re, sys, time
import requests

import scrape_jp as jp
import scrape_tw as tw
from coords_jp import parse_list_coords as jp_coords
from coords_tw import parse_list_coords as tw_coords
from coords_gsi import GSI, clean as gsi_clean

CSV = paths.ARCADES
HEAD = ["名稱", "地址", "都道府縣", "營業時間", "遊戲", "郵遞區號", "地圖連結", "詳細連結", "緯度", "經度",
        "中文名", "google_place_id", "營業時間來源", "週營業時間", "機台", "mgm_id"]
# 這些欄位 SEGA 沒有，只能從舊資料帶過來
CARRY = ["中文名", "google_place_id", "營業時間來源", "週營業時間", "機台", "mgm_id"]
SID = re.compile(r"sid=(\d+)")
log = lambda *a: print(*a, flush=True)


def sid_of(row):
    m = SID.search(row.get("詳細連結", ""))
    return m.group(1) if m else ""


def load_old():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    return {sid_of(r) or (r["名稱"], r["地址"]): r for r in rows}


def scrape_jp(s, limit):
    out = []
    prefs = jp.PREFS[:limit] if limit else jp.PREFS
    for at, pref in enumerate(prefs):
        html = jp.get(s, params={"gm": jp.GM, "at": at, "ct": 1000})
        coords, _ = jp_coords(html)
        venues = jp.parse_list(html)
        log(f"[{at+1}/{len(prefs)}] {pref} {len(venues)} 間")
        for v in venues:
            d = jp.parse_detail(jp.get(s, url=v["detail"])) if v["detail"] else {"zip": "", "hours": "", "games": []}
            time.sleep(jp.SLEEP)
            sid = (SID.search(v["detail"]) or [None, ""])[1]
            lat, lng = coords.get(sid, ("", ""))
            out.append({"名稱": v["name"], "地址": v["address"], "都道府縣": pref, "營業時間": d["hours"],
                        "遊戲": "、".join(d["games"]), "郵遞區號": d["zip"], "地圖連結": "",
                        "詳細連結": v["detail"], "緯度": lat, "經度": lng})
    return out


def scrape_tw(s, limit):
    at, label = tw.find_region_code(tw.get(s, params={"gm": tw.GM}))
    if not at:
        log("！找不到台灣的地區代碼，略過台灣"); return None
    html = tw.get(s, params={"gm": tw.GM, "at": at, "ct": 1000})
    coords = tw_coords(html)
    venues = tw.parse_list(html)
    if limit:
        venues = venues[:5]
    log(f"台灣 {len(venues)} 間")
    out = []
    for v in venues:
        d = tw.parse_detail(tw.get(s, url=v["detail"])) if v["detail"] else {"hours": "", "games": []}
        time.sleep(tw.SLEEP)
        sid = (SID.search(v["detail"]) or [None, ""])[1]
        lat, lng = coords.get(sid, ("", ""))
        out.append({"名稱": v["name"], "地址": v["address"], "都道府縣": "台灣", "營業時間": d["hours"],
                    "遊戲": "、".join(d["games"]), "郵遞區號": "", "地圖連結": "",
                    "詳細連結": v["detail"], "緯度": lat, "經度": lng})
    return out


def merge(new, old):
    """新資料為主，補上舊資料才有的欄位；營業時間依來源優先序決定。"""
    for r in new:
        o = old.get(sid_of(r)) or old.get((r["名稱"], r["地址"])) or {}
        for k in CARRY:
            r[k] = o.get(k, "")
        if not r["緯度"] and o.get("緯度"):          # SEGA 沒附座標 → 沿用之前（GSI 補的）
            r["緯度"], r["經度"] = o["緯度"], o["經度"]
        # 營業時間優先序：日本 SEGA 官方 → Google；台灣 Google → MGM → SEGA（國際版常填預設值）
        src = o.get("營業時間來源", "")
        keep_old = src in ("Google", "MGM") if r["都道府縣"] == "台灣" else (src == "Google" and not r["營業時間"])
        if keep_old:
            r["營業時間"] = o.get("營業時間", "")
        else:
            r["營業時間來源"] = r["週營業時間"] = ""
    return new


def geocode_missing(rows):
    s = requests.Session()
    for r in rows:
        if r["緯度"] or r["都道府縣"] == "台灣":
            continue
        try:
            res = s.get(GSI, params={"q": gsi_clean(r["地址"])}, timeout=20).json()
        except Exception:
            res = []
        if res:
            lng, lat = res[0]["geometry"]["coordinates"]
            r["緯度"], r["經度"] = f"{lat:.7f}", f"{lng:.7f}"
            log(f"  GSI 補座標：{r['名稱']}")
        time.sleep(0.3)


def summary(old, new):
    o = {sid_of(r) or (r["名稱"], r["地址"]): r for r in old.values()}
    n = {sid_of(r) or (r["名稱"], r["地址"]): r for r in new}
    added = [n[k] for k in n if k not in o]
    removed = [o[k] for k in o if k not in n]
    games, hours, renamed = [], [], []
    for k in n.keys() & o.keys():
        a, b = o[k], n[k]
        ga, gb = set(filter(None, a["遊戲"].split("、"))), set(filter(None, b["遊戲"].split("、")))
        if ga != gb:
            games.append((b, sorted(gb - ga), sorted(ga - gb)))
        if a["營業時間"] != b["營業時間"]:
            hours.append((b, a["營業時間"], b["營業時間"]))
        if a["名稱"] != b["名稱"]:
            renamed.append((a["名稱"], b["名稱"]))
    name = lambda r: f"{r.get('中文名') or r['名稱']}（{r['都道府縣']}）"
    L = [f"## 資料更新摘要", "",
         f"共 {len(new)} 間（原本 {len(old)} 間）：新增 {len(added)}、消失 {len(removed)}、"
         f"遊戲變動 {len(games)}、營業時間變動 {len(hours)}、改名 {len(renamed)}", ""]
    if added:
        L += ["### 🆕 新增"] + [f"- {name(r)} {r['地址']}" for r in added] + [""]
    if removed:
        L += ["### ❌ 消失（官方已下架）"] + [f"- {name(r)}" for r in removed] + [""]
    if games:
        L += ["### 🎮 遊戲變動"] + [f"- {name(r)}：" + "、".join([f"＋{g}" for g in a] + [f"－{g}" for g in d])
                                     for r, a, d in games[:80]] + [""]
    if hours:
        L += ["### 🕒 營業時間變動"] + [f"- {name(r)}：{a or '（無）'} → {b or '（無）'}" for r, a, b in hours[:80]] + [""]
    if renamed:
        L += ["### ✏️ 改名"] + [f"- {a} → {b}" for a, b in renamed] + [""]
    if added:
        L += ["> 新增的店還沒有 Google 連結／營業時間：本機跑 `google_place_ids.py`、`google_hours.py` 可補（需 API key）。"]
    return "\n".join(L) + "\n", len(added) + len(removed) + len(games) + len(hours) + len(renamed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只爬前 N 個縣＋台灣前 5 間，不寫檔")
    ap.add_argument("--mgm", action="store_true", help="一併重抓 Music Game Map")
    args = ap.parse_args()

    old = load_old()
    s = requests.Session()
    jp.get(s, params={"gm": jp.GM})
    new_jp = scrape_jp(s, args.limit)
    new_tw = scrape_tw(s, args.limit)
    if not args.limit and len(new_jp) < 0.8 * sum(1 for r in old.values() if r["都道府縣"] != "台灣"):
        sys.exit(f"日本只爬到 {len(new_jp)} 間，比上次少太多，可能是官網改版或連線失敗 → 不寫檔")
    if new_tw is None:   # 台灣爬失敗就沿用舊的，不要整批刪掉
        new_tw = [r for r in old.values() if r["都道府縣"] == "台灣"]
    rows = merge(new_jp + new_tw, old)
    geocode_missing(rows)

    if args.limit:
        for r in rows[:8]:
            log(" ", r["名稱"][:24], "|", r["營業時間"], "|", r["遊戲"][:40], "|", r["緯度"], r["中文名"])
        log("(--limit 測試模式，未寫檔)"); return

    with open(CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=HEAD, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    import mgm_tw as names
    if args.mgm:
        names.save_cache(names.scan(requests.Session(), 400))
    names.merge_names(names.load_cache())   # 台灣中文名／機台資訊（沒加 --mgm 就只用快取）

    jst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()
    open(paths.DATA_DATE, "w", encoding="utf-8").write(jst.isoformat() + "\n")
    text, n = summary(old, list(csv.DictReader(open(CSV, encoding="utf-8-sig"))))
    open(paths.SUMMARY, "w", encoding="utf-8").write(text)
    log(text)
    log(f"變動 {n} 項")


if __name__ == "__main__":
    main()
