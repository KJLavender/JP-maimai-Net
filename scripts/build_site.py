# -*- coding: utf-8 -*-
# 「音GO · 找機廳」網站產生器：data/arcades.csv ＋ templates/（前端原始檔）→ site/。
# site/ 是產生出來的結果，不進 repo；Netlify 部署時會執行本腳本（見 netlify.toml）。
# 功能：營業判斷（依星期幾）＋倒數、音遊按鈕(自動生成)、其他遊戲下拉、定位/距離/半徑、
#       深夜快篩、★收藏、精準導航、機廳巡り路線(多點導航)、台灣機台資訊、分享連結、
#       記住偏好(localStorage)、清單/地圖雙檢視、資料更新日。
# 用法：python scripts/build_site.py
import paths
import csv, os, re, json, datetime, hashlib
from collections import Counter
from urllib.parse import quote
from tw_brands import brand_zh, MANUAL

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
# 台灣店的英文地址 → 縣市（制霸地圖、搜尋用）。依順序比對：New Taipei 要在 Taipei 前面
TW_COUNTY = [
    ("NEWTAIPEI", "新北市"), ("TAIPEI", "台北市"), ("KEELUNG", "基隆市"),
    ("TAOYUAN", "桃園市"),
    ("HSINCHUCOUNTY", "新竹縣"), ("HSINCHU", "新竹市"), ("MIAOLI", "苗栗縣"),
    ("TAICHUNG", "台中市"), ("CHANGHUA", "彰化縣"), ("NANTOU", "南投縣"), ("YUNLIN", "雲林縣"),
    ("CHIAYICOUNTY", "嘉義縣"), ("CHIAYI", "嘉義市"), ("TAINAN", "台南市"), ("KAOHSIUNG", "高雄市"),
    ("PINGTUNG", "屏東縣"), ("YILAN", "宜蘭縣"), ("HUALIEN", "花蓮縣"), ("TAITUNG", "台東縣"),
    ("PENGHU", "澎湖縣"), ("KINMEN", "金門縣"), ("LIENCHIANG", "連江縣"),
    ("NANGANGDIST", "台北市"), ("SANMINDIST", "高雄市"),   # 地址沒寫縣市、只有區名的
]


def tw_county(addr):
    a = re.sub(r"[^A-Z]", "", addr.upper())
    return next((c for k, c in TW_COUNTY if k in a), "")

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
                if MANUAL.get(name, {}).get("closed"):
                    print("略過已歇業：", name)
                    continue
                key = (name, addr)
                if key in seen:
                    continue
                seen.add(key)
                games = [GAME_ALIAS.get(x.strip(), x.strip()) for x in re.split(r"[、,]", g("遊戲")) if x.strip()]
                games = list(dict.fromkeys(games))
                zh = g("中文名")
                county = tw_county(addr) if g("都道府縣") == "台灣" else ""
                bz = brand_zh(name) if county else ""
                # 台灣店的英文名丟給 Google 常配到別縣市的分店；有中文名就搜中文名，沒有就搜「中文品牌＋地址」
                if g("都道府縣") == "台灣":
                    q = zh or f"{bz or name} {addr}"
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
                elif bz:   # 沒有正式中文名：顯示「品牌（縣市）」幫助辨認，不猜分店名
                    rec["zg"] = f"{bz}（{county}）"
                if rec["p"] == "台灣":
                    rec["c"] = county
                    if not rec["c"]:
                        print("⚠ 地址看不出台灣縣市（請補到 TW_COUNTY）：", name, addr)
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
STATIC = ["style.css", "account.js", "conquest.js", "stats.js", "b50.js", "app.js", "manifest.webmanifest",
          "icon.svg", "privacy.html", "bookmarklet.js"]   # 原樣複製的前端檔案


def read_template(name):
    return open(os.path.join(paths.TEMPLATES, name), encoding="utf-8").read()


def write_text(name, text):
    with open(os.path.join(paths.SITE, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def inline_json(obj):
    """塞進 <script type="application/json"> 的 JSON：跳脫「</」，資料裡出現 </script 才不會截斷頁面。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# 統計頁的歷史（只留圖表用得到的：日期、各遊戲店數、總數）
HISTORY = os.path.join(paths.DATA, "history.json")
history = [{"date": h["date"], **{k: {"total": h[k]["total"], "games": h[k]["games"]} for k in ("jp", "tw") if k in h}}
           for h in (json.load(open(HISTORY, encoding="utf-8")) if os.path.exists(HISTORY) else [])]
config = {"rhythm": rhythm, "others": [[g, cnt[g]] for g in others], "history": history}
html_out = (read_template("index.html")
            .replace("__TOTAL__", str(total))
            .replace("__DATE__", data_date)
            .replace("__CONFIG__", inline_json(config))
            .replace("__DATA__", inline_json(rows)))
os.makedirs(paths.SITE, exist_ok=True)
# CSS／JS 網址加上內容雜湊（style.css?v=…）：新版上線時舊的 Service Worker 快取對不到，一定拿新檔，
# 不會出現「新的 HTML 配舊的 CSS」排版跑掉
VERSIONED = [n for n in STATIC if n.endswith((".css", ".js"))]
ver = {n: hashlib.sha256(read_template(n).encode()).hexdigest()[:8] for n in VERSIONED}
for n, h in ver.items():
    html_out = html_out.replace(f'"{n}"', f'"{n}?v={h}"')
write_text("index.html", html_out)
for name in STATIC:
    write_text(name, read_template(name))
SONGS = os.path.join(paths.DATA, "songs.json")   # 🎵 B50 用的定數（scripts/songs.py 產生）
if os.path.exists(SONGS):
    write_text("songs.json", open(SONGS, encoding="utf-8").read())

# Service Worker 快取名稱 = 網站內容的雜湊：任何檔案改了就換新快取，不用再手動改版本號
digest = hashlib.sha256("".join([html_out] + [read_template(n) for n in STATIC]).encode()).hexdigest()[:10]
sw = read_template("sw.js").replace("__CACHE__", digest)
for n, h in ver.items():
    sw = sw.replace(f"'./{n}'", f"'./{n}?v={h}'")
write_text("sw.js", sw)


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
