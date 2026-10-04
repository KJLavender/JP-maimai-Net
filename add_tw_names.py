# -*- coding: utf-8 -*-
"""
補台灣機廳中文店名 → 併回 maimai_full.csv 的「中文名」欄
資料來源: Music Game Map (https://mgm.wind-chime.info) 逐頁 game_center/{id}
對應方式: 用經緯度比對（兩邊都有座標），最近且在 THRESHOLD 公尺內視為同一間店。
          你的 SEGA 台灣資料需先跑過 add_coords_tw.py（有座標才能比對）。

需求: pip install requests beautifulsoup4
執行:
  python add_tw_names.py --scan 320   # 逐頁抓 MGM（id 1~320），存成 mgm_cache.csv，再比對併入
  python add_tw_names.py              # 若已有 mgm_cache.csv，直接用快取比對（不重抓）
  python add_tw_names.py --test 70    # 只抓前 70 頁測試比對命中率，不寫回主檔
"""
import csv, re, sys, time, math, argparse, os
import requests
from bs4 import BeautifulSoup

MGM = "https://mgm.wind-chime.info/game_center/"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")}
SLEEP = 0.4
THRESHOLD_M = 60           # 兩點在此公尺內才視為同一間店（寧嚴勿寬，避免誤配）
BRAND_THRESHOLD_M = 250    # 兩邊品牌對得上時放寬到這個距離（兩站座標常有百來公尺落差）
# (英文店名 regex, 中文店名 regex)：同品牌才放寬距離；兩邊都認得出品牌卻不同 → 不配對
BRANDS = [
    (r"TOM'?S\s*WORLD", r"湯姆熊"), (r"HALA", r"哈啦"), (r"SHIRONEKOYA", r"白喵"),
    (r"GiGO", r"GiGO"), (r"SIN\s*YI\s*CITY", r"新藝城"), (r"HAPPY\s*100", r"HAPPY\s*100"),
    (r"YOUNG\s*KEY", r"永淇"), (r"VAN'?S", r"小凡"), (r"X50", r"X50"), (r"HURO", r"湖若|HURO"),
    (r"RED\s*HAT", r"紅帽象"), (r"CATCH\s*BUFFET", r"夾到飽"), (r"WAWA", r"娃娃帝國"),
]


def brand(name, zh=False):
    for i, pair in enumerate(BRANDS):
        if re.search(pair[1 if zh else 0], name, re.I):
            return i
    return None


COORD_RE = re.compile(r"center=(-?\d+\.\d+),(-?\d+\.\d+)")
MAI_RE = re.compile(r"maimai", re.I)   # 只保留有 maimai 的店，減少誤配


def haversine_m(a, b):
    R = 6371000.0
    r = math.radians
    dLa, dLo = r(b[0] - a[0]), r(b[1] - a[1])
    s = math.sin(dLa/2)**2 + math.cos(r(a[0]))*math.cos(r(b[0]))*math.sin(dLo/2)**2
    return 2 * R * math.asin(math.sqrt(s))


def fetch(session, gid, retries=2):
    for i in range(retries):
        try:
            r = session.get(MGM + str(gid), headers=HEADERS, timeout=20)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return ""
        except requests.RequestException:
            time.sleep(SLEEP * 2)
    return ""


def parse_mgm(html):
    """回傳 (中文名, lat, lng, 有無maimai, 營業時間)；抓不到座標回 None。"""
    soup = BeautifulSoup(html, "html.parser")
    name = ""
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)
    if not name:
        og = soup.find("meta", property="og:title")
        if og:
            name = re.sub(r"\s*-\s*Music Game Map\s*$", "", og.get("content", "")).strip()
    m = COORD_RE.search(html)
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    has_mai = bool(MAI_RE.search(soup.get_text(" ")))
    mh = re.search(r"營業時間[:：]\s*([^\n]+)", soup.get_text("\n", strip=True))
    return name, lat, lng, has_mai, norm_hours(mh.group(1)) if mh else ""


def norm_hours(t):
    """MGM 的「10：00～22：00」→ 與官方資料同格式「10:00〜22:00」；全天 → 24時間。"""
    t = re.sub(r"\s+", "", t).replace("：", ":").replace("~", "〜").replace("～", "〜").replace("-", "〜")
    if re.fullmatch(r"0?0:00〜24:00|24(小時|時間|h|hrs?)", t, re.I):
        return "24時間"
    return t if re.search(r"\d", t) else ""      # 「未知」之類的不算


def scan(session, upto, test=False):
    rows = []
    miss = 0
    for gid in range(1, upto + 1):
        html = fetch(session, gid)
        if not html:
            miss += 1
            if miss > 25 and gid > 60:   # 連續大量 404 → 已到尾端
                print(f"  （連續空頁，於 id={gid} 停止）")
                break
            continue
        miss = 0
        rec = parse_mgm(html)
        if rec and rec[0]:
            rows.append({"name": rec[0], "lat": rec[1], "lng": rec[2], "mai": rec[3], "hours": rec[4]})
        if gid % 20 == 0:
            print(f"  掃描 {gid}/{upto} … 已收 {len(rows)} 間", flush=True)
        time.sleep(SLEEP)
    return rows


def load_cache():
    if not os.path.exists("mgm_cache.csv"):
        return []
    with open("mgm_cache.csv", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return [{"name": x["name"], "lat": float(x["lat"]), "lng": float(x["lng"]),
                 "mai": x.get("mai", "True") == "True", "hours": norm_hours(x.get("hours", ""))} for x in r]


def save_cache(rows):
    with open("mgm_cache.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["name", "lat", "lng", "mai", "hours"])
        for r in rows:
            w.writerow([r["name"], r["lat"], r["lng"], r["mai"], r["hours"]])


def merge_names(mgm_rows, test=False):
    if not os.path.exists("maimai_full.csv"):
        print("找不到 maimai_full.csv"); return
    with open("maimai_full.csv", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    head = [h.lstrip("\ufeff").strip() for h in rows[0]]
    if "中文名" not in head:
        head.append("中文名")
    iName, iP = head.index("名稱"), head.index("都道府縣")
    iZh = head.index("中文名")
    iH = head.index("營業時間")
    iLat = head.index("緯度") if "緯度" in head else -1
    iLng = head.index("經度") if "經度" in head else -1
    if iLat < 0:
        print("主檔沒有緯度/經度欄，請先跑 add_coords_tw.py"); return

    # 優先用有 maimai 的 MGM 點比對
    mai_pts = [r for r in mgm_rows if r["mai"]] or mgm_rows

    # 收集所有台灣店（有座標者）
    tw_idx = []
    for ri, row in enumerate(rows[1:], start=1):
        row = row + [""] * (len(head) - len(row))
        rows[ri] = row
        if row[iP].strip() == "台灣" and row[iLat].strip():
            try:
                tw_idx.append((ri, float(row[iLat]), float(row[iLng])))
            except ValueError:
                pass

    # 算出所有 (距離, sega列, mgm點) 夠近的候選，按距離排序，做一對一貪婪配對
    # 品牌相同者優先、其次距離近者；英文名認得出品牌時只配同品牌
    cand = []
    for ri, la, lo in tw_idx:
        bs = brand(rows[ri][iName])
        rows[ri][iZh] = ""          # 重算，不留上一輪的結果
        for mj, r in enumerate(mai_pts):
            d = haversine_m((la, lo), (r["lat"], r["lng"]))
            bm = brand(r["name"], zh=True)
            same = bs is not None and bs == bm
            if bs is not None and not same:   # 認得出品牌就一定要同品牌
                continue
            if d <= THRESHOLD_M or (same and d <= BRAND_THRESHOLD_M):
                cand.append((0 if same else 1, d, ri, mj))
    cand.sort(key=lambda x: (x[0], x[1]))
    cand = [(d, ri, mj) for _, d, ri, mj in cand]
    used_sega, used_mgm, assign = set(), set(), {}
    for d, ri, mj in cand:
        if ri in used_sega or mj in used_mgm:
            continue
        used_sega.add(ri); used_mgm.add(mj); assign[ri] = (mai_pts[mj], d)

    hit = hours_hit = 0; samples = []
    for ri, (m, d) in assign.items():
        zh = m["name"]
        rows[ri][iZh] = zh; hit += 1
        # 台灣營業時間以 MGM 為準：SEGA 國際版常填「24hrs」「00:00〜22:30」之類的預設值
        # （例：新竹巨城店 SEGA 寫 24hrs，MGM 11:00〜21:30，Google 22:00 打烊）
        if m.get("hours"):
            rows[ri][iH] = m["hours"]; hours_hit += 1
        if len(samples) < 15:
            samples.append((rows[ri][iName], zh, round(d)))
    out = rows[1:]

    tw_total = len(tw_idx)
    print(f"\n有座標的台灣店 {tw_total} 間，成功對到中文名 {hit} 間（門檻 {THRESHOLD_M}m、同品牌 {BRAND_THRESHOLD_M}m，一對一配對）；營業時間採用 MGM {hours_hit} 間")
    print("樣本（英文名 → 中文名 · 距離m）：")
    for a, b, dd in samples:
        print(f"  {a}  →  {b}  ({dd}m)")

    if test:
        print("\n(--test 模式，未寫回主檔)"); return
    with open("maimai_full.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(out)
    print(f"\n已寫回 maimai_full.csv（新增「中文名」欄，{hit} 間有值）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", type=int, default=0, help="逐頁抓 MGM 到指定 id 上限並更新快取")
    ap.add_argument("--test", type=int, default=0, help="只抓前 N 頁測比對，不寫回")
    args = ap.parse_args()
    s = requests.Session()

    if args.test:
        rows = scan(s, args.test, test=True)
        print(f"抓到 {len(rows)} 間 MGM 店")
        merge_names(rows, test=True); return

    if args.scan:
        rows = scan(s, args.scan)
        save_cache(rows)
        print(f"MGM 掃描完成 {len(rows)} 間 → mgm_cache.csv")
    else:
        rows = load_cache()
        if not rows:
            print("沒有 mgm_cache.csv，請先用 --scan 320 抓一次"); return
        print(f"使用快取 mgm_cache.csv（{len(rows)} 間）")
    merge_names(rows)


if __name__ == "__main__":
    main()
