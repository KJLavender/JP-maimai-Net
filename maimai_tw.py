# -*- coding: utf-8 -*-
"""
台灣 maimai DX 機廳爬蟲 → 併入 maimai_full.csv
資料來源: SEGA ALL.Net設置店舗検索 gm=98（maimai DX International Version，涵蓋日本以外地區）
會自動從頁面的「国／地域」下拉選單找出 Taiwan 對應代碼，不寫死猜測值，避免代碼錯誤。

需求: pip install requests beautifulsoup4
執行（跟 maimai_detail.py 放同一個資料夾）:
  python maimai_tw.py --test   # 只列出前幾間店，不寫檔，先確認抓得到、代碼找對了
  python maimai_tw.py          # 正式爬，新增進 maimai_full.csv（保留原本日本資料，不覆蓋）
"""
import csv, re, sys, time, argparse, os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

BASE = "https://location.am-all.net/alm/location"
ALM = "https://location.am-all.net/alm/"
GM = 98  # maimai DX International Version（日本以外地區）
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
           "Accept-Language": "ja,zh-TW;q=0.9,en;q=0.8"}
SLEEP = 0.6


def get(session, params=None, url=None, retries=3):
    for i in range(retries):
        try:
            r = session.get(url or BASE, params=params, headers=HEADERS, timeout=20)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
        except requests.RequestException as e:
            print(f"  ! {e} 重試{i+1}", file=sys.stderr)
        time.sleep(SLEEP * 2)
    return ""


def find_region_code(html, keywords=("Taiwan", "台灣", "台湾")):
    """從頁面的『国／地域』下拉選單自動找出符合關鍵字的 <option value>。
    不猜數字：先用選項文字（含 Taiwan/Hong Kong）認出哪個 select 是國家清單，
    再從裡面比對關鍵字，回傳 (value, 顯示文字)。找不到回傳 ("","")。"""
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


def parse_list(html):
    """跟日本版同一套模板：.store_name / .store_address / .bt_details(onclick 含 sid=)。"""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for nm in soup.select(".store_name"):
        li = nm.find_parent("li") or nm.parent
        name = nm.get_text(strip=True)
        if not name:
            continue
        ad = li.select_one(".store_address") if li else None
        addr = ad.get_text(strip=True) if ad else ""
        db = li.select_one(".bt_details") if li else None
        m = re.search(r"sid=(\d+)", (db.get("onclick", "") if db else "") or "")
        sid = m.group(1) if m else ""
        detail = f"{ALM}shop?gm={GM}&astep=0&sid={sid}" if sid else ""
        out.append({"name": name, "address": addr, "detail": detail})
    seen, uniq = set(), []
    for v in out:
        k = (v["name"], v["address"])
        if k not in seen:
            seen.add(k); uniq.append(v)
    return uniq


def parse_detail(html):
    """同日本版：抓營業時間與 ALL.Net 遊戲清單（title_list/info_list 通用解析）。"""
    soup = BeautifulSoup(html, "html.parser")
    games = [a.get_text(strip=True) for a in soup.select("ul.title_list li a")]
    if not games:
        games = [re.sub(r"^[◆\s]+", "", li.get_text(" ", strip=True))
                 for li in soup.select("ul.title_list li")]
    games = [g for g in dict.fromkeys(games) if g]
    text = soup.get_text("\n").replace("：", ":")
    seg = ""   # 只看「営業時間」那一欄；頁尾有「AM4:00～AM7:00 維護」之類的字，不能整頁亂抓
    for li in soup.select("ul.info_list li"):
        t = li.get_text(" ", strip=True).replace("：", ":")
        if re.search(r"営業時間|business hours", t, re.I):
            seg = t; break
    mh = re.search(r"\d{1,2}:\d{2}\s*[〜~～\-–]\s*\d{1,2}:\d{2}", seg)
    if mh:
        hours = re.sub(r"\s+", "", mh.group(0)).replace("~", "〜").replace("-", "〜").replace("～", "〜")
    elif re.search(r"24\s*(時間|hours?|hrs?)", seg, re.I):   # 「24時間」「24 hours」「24hrs」
        hours = "24時間"
    else:
        mo = re.search(r"\d{1,2}:\d{2}\s*[〜~～\-–]", seg)       # 只寫開門時間，例「10:00～」
        hours = re.sub(r"\s+", "", mo.group(0))[:-1] + "〜" if mo else ""
    return {"hours": hours, "games": games}


def follow_pages(session, params, limit=60):
    rows, p, page = [], dict(params), 1
    while True:
        html = get(session, params=p)
        if not html:
            break
        rows += parse_list(html)
        soup = BeautifulSoup(html, "html.parser")
        nxt = next((a["href"] for a in soup.find_all("a", href=True)
                    if re.search(r"次へ|次のページ|Next", a.get_text())), None)
        if not nxt:
            break
        p = {k: v[0] for k, v in parse_qs(urlparse(nxt).query).items()}
        page += 1
        if page > limit:
            break
        time.sleep(SLEEP)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="只列前 8 間，不寫檔，先確認抓得到")
    ap.add_argument("--out", default="maimai_full.csv")
    args = ap.parse_args()

    s = requests.Session()
    top_html = get(s, params={"gm": GM})
    time.sleep(SLEEP)
    at_code, at_label = find_region_code(top_html)
    if not at_code:
        open("debug_tw_top.html", "w", encoding="utf-8").write(top_html)
        print("找不到 Taiwan 選項。已存 debug_tw_top.html，把這個檔傳給我對照真實結構。")
        return
    print(f"找到地區代碼：{at_label} → at={at_code}")

    venues = follow_pages(s, {"gm": GM, "at": at_code, "ct": 1000})
    print(f"清單店數：{len(venues)}")
    if not venues:
        html = get(s, {"gm": GM, "at": at_code, "ct": 1000})
        open("debug_tw_list.html", "w", encoding="utf-8").write(html)
        print("店數為 0，已存 debug_tw_list.html，傳給我看實際結構。")
        return
    if args.test:
        for v in venues[:8]:
            print("  -", v["name"], "|", v["address"], "|", v["detail"])
        print("（--test 模式只列前 8 間，不寫檔／不抓詳細頁，確認沒問題再跑正式版）")
        return

    rows = []
    for i, v in enumerate(venues):
        dh = get(s, url=v["detail"]) if v["detail"] else ""
        time.sleep(SLEEP)
        d = parse_detail(dh) if dh else {"hours": "", "games": []}
        rows.append({"name": v["name"], "address": v["address"], "pref": "台灣",
                     "hours": d["hours"], "games": "、".join(d["games"]),
                     "zip": "", "gmap": "", "detail": v["detail"]})
        if (i + 1) % 20 == 0:
            print(f"  詳細頁 {i+1}/{len(venues)} …")

    header = ["名稱", "地址", "都道府縣", "營業時間", "遊戲", "郵遞區號", "地圖連結", "詳細連結"]
    existing = []
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig") as f:
            r = csv.reader(f)
            old_head = next(r, None)
            existing = list(r)
        if old_head and len(old_head) > len(header):
            header = old_head  # 保留舊檔可能已有的緯度/經度欄

    seen = {(row[0], row[1]) for row in existing if len(row) >= 2}
    new_rows = []
    for r_ in rows:
        key = (r_["name"], r_["address"])
        if key in seen:
            continue
        base = [r_["name"], r_["address"], r_["pref"], r_["hours"], r_["games"],
                r_["zip"], r_["gmap"], r_["detail"]]
        base += [""] * (len(header) - len(base))
        new_rows.append(base)

    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(existing)
        w.writerows(new_rows)
    print(f"完成：新增 {len(new_rows)} 間台灣機廳 → {args.out}（原有日本資料保留）")


if __name__ == "__main__":
    main()
