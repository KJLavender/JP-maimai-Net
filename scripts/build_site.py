# -*- coding: utf-8 -*-
# 「全日本音遊機廳」網站產生器：讀 data/arcades.csv → 產生 site/（單檔 HTML＋PWA＋data.json）。
# 功能：營業判斷（依星期幾）＋倒數、音遊按鈕(自動生成)、其他遊戲下拉、定位/距離/半徑、
#       深夜快篩、★收藏、精準導航、機廳巡り路線(多點導航)、台灣機台資訊、分享連結、
#       記住偏好(localStorage)、清單/地圖雙檢視、資料更新日。
# 用法：python scripts/build_site.py
import paths
import csv, os, re, json, datetime
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

data_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
rhythm_json = json.dumps(rhythm, ensure_ascii=False)
others_json = json.dumps([[g, cnt[g]] for g in others], ensure_ascii=False)

TEMPLATE_DIR = os.path.join(paths.ROOT, "templates")


def read_template(name):
    return open(os.path.join(TEMPLATE_DIR, name), encoding="utf-8").read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


HTML = read_template("index.html")

html_out = (HTML.replace("__TOTAL__", str(total))
                .replace("__DATE__", data_date)
                .replace("__RHYTHM__", rhythm_json)
                .replace("__OTHERS__", others_json)
                .replace("__DATA__", data_json))
os.makedirs(paths.SITE, exist_ok=True)
write_text(os.path.join(paths.SITE, "index.html"), html_out)


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


json.dump({"updated": data_date, "count": total,
           "notes": "hours_week: Sun..Sat. machines: Music Game Map (Taiwan only, player-reported).",
           "shops": [public(r) for r in rows]},
          open(os.path.join(paths.SITE, "data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
write_text(os.path.join(paths.SITE, "icon.svg"),
 '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
 '<rect width="512" height="512" rx="120" fill="#0d0b1a"/>'
 '<circle cx="256" cy="256" r="150" fill="none" stroke="#ff3d9a" stroke-width="26"/>'
 '<circle cx="256" cy="256" r="150" fill="none" stroke="#26e0e6" stroke-width="26" '
 'stroke-dasharray="140 800" stroke-linecap="round"/><circle cx="256" cy="256" r="46" fill="#26e0e6"/></svg>')
print("→ site/ 產生完成")
