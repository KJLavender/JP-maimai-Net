# -*- coding: utf-8 -*-
# 「全日本音遊機廳」網站產生器：data/arcades.csv ＋ templates/（前端原始檔）→ site/。
# site/ 是產生出來的結果，不進 repo；Netlify 部署時會執行本腳本（見 netlify.toml）。
# 功能：營業判斷（依星期幾）＋倒數、音遊按鈕(自動生成)、其他遊戲下拉、定位/距離/半徑、
#       深夜快篩、★收藏、精準導航、機廳巡り路線(多點導航)、台灣機台資訊、分享連結、
#       記住偏好(localStorage)、清單/地圖雙檢視、資料更新日。
# 用法：python scripts/build_site.py
import paths
import csv, os, re, json, datetime, hashlib
from collections import Counter
from urllib.parse import quote

HEADER_KEYS = ["名稱","地址","都道府縣","營業時間","遊戲","郵遞區號","地圖連結","詳細連結","緯度","經度","中文名","google_place_id","營業時間來源","週營業時間","機台","mgm_id"]
RHYTHM_ORDER = [
    "maimai でらっくす", "CHUNITHM", "オンゲキ",
    "初音ミク Project DIVA Arcade Future Tone",
]
# 海外(台灣等)在官方系統裡登記的遊戲名稱跟日本不同字面，但其實是同一款遊戲，
# 篩選時應視為同一顆按鈕，否則玩家點「maimai DX」會漏掉台灣的店。
GAME_ALIAS = {
    "maimai DX International Version": "maimai でらっくす",
    "CHUNITHM International Version": "CHUNITHM",
}

def read_rows():
    if not os.path.exists(paths.ARCADES):
        return [], ""
    src = [paths.ARCADES]
    print("讀取：", os.path.relpath(paths.ARCADES, paths.ROOT))
    # 資料日期以 data_date.txt 為準（update_data.py 寫入），各機器重產生的結果才會一致；沒有就用檔案修改時間
    if os.path.exists(paths.DATA_DATE):
        date = open(paths.DATA_DATE, encoding="utf-8").read().strip()
    else:
        date = datetime.date.fromtimestamp(os.path.getmtime(src[0])).isoformat()
    rows, seen = [], set()
    for fp in src:
        with open(fp, encoding="utf-8-sig") as f:
            r = csv.reader(f); head = next(r, None) or []
            head = [h.lstrip("\ufeff").strip() for h in head]
            idx = {k: (head.index(k) if k in head else -1) for k in HEADER_KEYS}
            for row in r:
                def g(k):
                    i = idx[k]; return row[i].strip() if 0 <= i < len(row) else ""
                name, addr = g("名稱"), g("地址")
                if not name:
                    continue
                key = (name, addr)
                if key in seen:
                    continue
                seen.add(key)
                games = [GAME_ALIAS.get(x.strip(), x.strip()) for x in re.split(r"[、,]", g("遊戲")) if x.strip()]
                games = list(dict.fromkeys(games))
                zh = g("中文名")
                # 台灣店的英文名＋英文地址丟給 Google 常跑出一串結果；有中文名就只搜中文名，
                # 沒有就把「TOM'S WORLD(GIANT CITY@HSINCHU)」拆成一般字詞
                if g("都道府縣") == "台灣":
                    q = zh or re.sub(r"[()@]+", " ", name).strip()
                else:
                    q = f"{name} {addr}"
                url = g("地圖連結") or ("https://www.google.com/maps/search/?api=1&query=" + quote(q))
                gp = g("google_place_id")
                if gp:   # 有 Google place ID → 直接開到那間店
                    url = ("https://www.google.com/maps/search/?api=1&query=" + quote(zh or name)
                           + "&query_place_id=" + quote(gp))
                m = re.search(r"sid=(\d+)", g("詳細連結"))
                rec = {"n": name, "a": addr, "p": g("都道府縣") or "其他",
                       "h": g("營業時間"), "g": games, "u": url, "d": g("詳細連結"),
                       "i": m.group(1) if m else name + "|" + addr}
                if zh and zh != name:
                    rec["z"] = zh
                if gp:
                    rec["gp"] = gp
                if g("營業時間來源") in ("Google", "MGM"):
                    rec["hs"] = g("營業時間來源")
                wk = g("週營業時間").split("|")
                if len(wk) == 7 and len(set(wk)) > 1:   # 一週各天不同才需要（日→六）
                    rec["w"] = wk
                if g("機台"):
                    rec["m"] = json.loads(g("機台"))
                if g("mgm_id"):
                    rec["mg"] = g("mgm_id")
                try:
                    rec["y"], rec["x"] = round(float(g("緯度")), 6), round(float(g("經度")), 6)
                except ValueError:
                    pass
                rows.append(rec)
    return rows, date

rows, data_date = read_rows()
total = len(rows)
cnt = Counter(g for r in rows for g in r["g"])
rhythm = [g for g in RHYTHM_ORDER if cnt.get(g)]
others = sorted([g for g in cnt if g not in rhythm], key=lambda g: -cnt[g])
print(f"共 {total} 間；有座標 {sum(1 for r in rows if 'y' in r)}；資料日 {data_date}")
print("音遊按鈕：", "、".join(f"{g}({cnt[g]})" for g in rhythm) or "（無）")
print("其他遊戲（下拉）：", len(others), "款")

# ---------------- 輸出 site/ ----------------
STATIC = ["style.css", "app.js", "manifest.webmanifest", "icon.svg"]   # 原樣複製的前端檔案


def read_template(name):
    return open(os.path.join(paths.TEMPLATES, name), encoding="utf-8").read()


def write_text(name, text):
    with open(os.path.join(paths.SITE, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def inline_json(obj):
    """塞進 <script type="application/json"> 的 JSON：跳脫「</」，資料裡出現 </script 才不會截斷頁面。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


config = {"rhythm": rhythm, "others": [[g, cnt[g]] for g in others]}
html_out = (read_template("index.html")
            .replace("__TOTAL__", str(total))
            .replace("__DATE__", data_date)
            .replace("__CONFIG__", inline_json(config))
            .replace("__DATA__", inline_json(rows)))
os.makedirs(paths.SITE, exist_ok=True)
write_text("index.html", html_out)
for name in STATIC:
    write_text(name, read_template(name))

# Service Worker 快取名稱 = 網站內容的雜湊：任何檔案改了就換新快取，不用再手動改版本號
digest = hashlib.sha256("".join([html_out] + [read_template(n) for n in STATIC]).encode()).hexdigest()[:10]
write_text("sw.js", read_template("sw.js").replace("__CACHE__", digest))


def public(r):
    """data.json 用好讀的欄位名。"""
    o = {"id": r["i"], "name": r["n"], "name_zh": r.get("z", ""), "region": r["p"], "address": r["a"],
         "hours": r["h"], "hours_week": r.get("w"), "hours_source": r.get("hs", "SEGA" if r["h"] else ""),
         "timezone": "Asia/Taipei" if r["p"] == "台灣" else "Asia/Tokyo", "games": r["g"],
         "lat": r.get("y"), "lng": r.get("x"), "google_place_id": r.get("gp", ""),
         "google_maps_url": r["u"], "official_url": r["d"]}
    if r.get("m"):
        o["machines"] = r["m"]
    return o


write_text("data.json", json.dumps(
    {"updated": data_date, "count": total,
     "notes": "hours_week: Sun..Sat. machines: Music Game Map (Taiwan only, player-reported).",
     "shops": [public(r) for r in rows]},
    ensure_ascii=False, separators=(",", ":")))
print(f"→ site/ 產生完成（快取版本 {digest}）")
