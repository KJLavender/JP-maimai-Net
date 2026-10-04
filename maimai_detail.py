# -*- coding: utf-8 -*-
"""
maimai 機廳「詳細資料」補抓爬蟲  (v3)
在原本的店名/地址之外，跟著每間店的「詳細」連結進去，補抓：
  營業時間、該店 ALL.Net 遊戲清單（有哪些機台）、郵遞區號。
輸出 by_pref2/*.csv（分縣）與 maimai_full.csv（合併）。

需求:  pip install requests beautifulsoup4
執行:
  python maimai_detail.py --test    # 只跑北海道前幾間 + dump debug，約 1 分鐘，先確認抓得到
  python maimai_detail.py           # 全國（約 1000+ 間，含逐店詳細頁，約 15–20 分鐘）
  python maimai_detail.py --split-only  # 只重輸出，不重抓（若已有 by_pref2）
"""
import csv, re, sys, time, argparse, os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urljoin

BASE = "https://location.am-all.net/alm/location"
ALM = "https://location.am-all.net/alm/"
GM = 96
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
           "Accept-Language": "ja,en;q=0.8"}
PREFS = ["北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県","茨城県","栃木県",
         "群馬県","埼玉県","千葉県","東京都","神奈川県","新潟県","富山県","石川県","福井県",
         "山梨県","長野県","岐阜県","静岡県","愛知県","三重県","滋賀県","京都府","大阪府",
         "兵庫県","奈良県","和歌山県","鳥取県","島根県","岡山県","広島県","山口県","徳島県",
         "香川県","愛媛県","高知県","福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県",
         "鹿児島県","沖縄県"]
PREF_RE = re.compile("^(" + "|".join(PREFS) + ")")
UI_RE = re.compile(r"(GoogleMap|詳細|Details|見る|公式|Official|戻る|Back|Search|検索|Language|©|SEGA)")
# ALL.Net 遊戲白名單（長/具體者在前，減少子字串誤判）
KNOWN_GAMES = ["maimai DX International Version","maimai でらっくす",
               "CHUNITHM International Version","CHUNITHM","頭文字D THE ARCADE","オンゲキ",
               "HOUSE OF THE DEAD: SCARLET DAWN","Wonderland Wars",
               "初音ミク Project DIVA Arcade Future Tone","セガNET麻雀 MJ Arcade","英傑大戦",
               "StarHorse4","StarHorseParty","ALL.Net P-ras MULTI バージョン３",
               "ALL.Net P-ras MULTI","That's PARADiCE","占いコレクション トロッテ"]
SLEEP = 0.6


def get(session, url=None, params=None, retries=3):
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


def parse_list(html):
    """從清單頁抽出每間店。實際結構：<li> 內含 .store_name / .store_address /
    .bt_details 按鈕（onclick 含 sid=）。詳細頁為 /alm/shop?gm=..&astep=0&sid=.."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for nm in soup.select(".store_name"):
        li = nm.find_parent("li") or nm.parent
        name = nm.get_text(strip=True)
        if not name:
            continue
        ad = li.select_one(".store_address") if li else None
        addr = ad.get_text(strip=True) if ad else ""
        sid = ""
        db = li.select_one(".bt_details") if li else None
        src = (db.get("onclick", "") if db else "") or (str(li) if li else "")
        m = re.search(r"sid=(\d+)", src)
        if m:
            sid = m.group(1)
        detail = f"{ALM}shop?gm={GM}&astep=0&sid={sid}" if sid else ""
        out.append({"name": name, "address": addr, "gmap": "", "detail": detail})
    seen, uniq = set(), []
    for v in out:
        k = (v["name"], v["address"])
        if k not in seen:
            seen.add(k); uniq.append(v)
    return uniq


def parse_detail(html):
    """從詳細頁抽出 郵遞區號、營業時間、遊戲清單。
    實際結構：ul.title_list > li > a 為遊戲；ul.info_list > li 為地址/營業時間。
    直接讀官方清單（不用白名單），可完整涵蓋所有 ALL.Net título。"""
    soup = BeautifulSoup(html, "html.parser")
    # 遊戲：官方 title_list，有什麼抓什麼
    games = [a.get_text(strip=True) for a in soup.select("ul.title_list li a")]
    if not games:
        games = [re.sub(r"^[◆\s]+", "", li.get_text(" ", strip=True))
                 for li in soup.select("ul.title_list li")]
    games = [g for g in dict.fromkeys(games) if g]

    text = soup.get_text("\n").replace("：", ":")
    zip_ = ""
    mz = re.search(r"〒?\s*(\d{3}-\d{4})", text)
    if mz:
        zip_ = mz.group(1)
    # 營業時間：優先取 info_list 內含「営業時間 / business hours」那行
    seg = text
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
    return {"zip": zip_, "hours": hours, "games": games}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    s = requests.Session()
    get(s, params={"gm": GM}); time.sleep(SLEEP)

    prefs = PREFS[:1] if args.test else PREFS
    os.makedirs("by_pref2", exist_ok=True)
    allrows = []
    for at, pref in enumerate(prefs):
        print(f"[{at+1}/{len(prefs)}] {pref} 清單…", end=" ", flush=True)
        list_html = get(s, params={"gm": GM, "at": at, "ct": 1000})
        if args.test:
            open("debug_list.html", "w", encoding="utf-8").write(list_html)
        venues = parse_list(list_html)
        if args.test:
            venues = venues[:6]
        print(f"{len(venues)} 間，逐店抓詳細…")
        rows = []
        for j, v in enumerate(venues):
            dh = get(s, url=v["detail"]); time.sleep(SLEEP)
            if args.test and j == 0:
                open("debug_detail.html", "w", encoding="utf-8").write(dh)
            d = parse_detail(dh)
            row = {"name": v["name"], "address": v["address"] or "", "pref": pref,
                   "hours": d["hours"], "games": "、".join(d["games"]),
                   "zip": d["zip"], "gmap": v["gmap"], "detail": v["detail"]}
            rows.append(row)
            if args.test:
                print(f"   - {row['name']} | 時間:{row['hours'] or '—'} | "
                      f"遊戲:{row['games'] or '—'} | 〒{row['zip'] or '—'}")
        write_csv(os.path.join("by_pref2", f"{at:02d}_{pref}.csv"), rows)
        allrows += rows
    write_csv("maimai_full.csv", allrows)
    print(f"\n完成：{len(allrows)} 間 → maimai_full.csv（分縣在 by_pref2/）")
    if args.test:
        print("↑ 上面每間有印出『時間/遊戲』就代表解析成功，可跑完整版；"
              "若多數是『—』，把 debug_detail.html 傳我。")


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["名稱","地址","都道府縣","營業時間","遊戲","郵遞區號","地圖連結","詳細連結"])
        for v in rows:
            w.writerow([v["name"], v["address"], v["pref"], v["hours"], v["games"],
                        v["zip"], v["gmap"], v["detail"]])


if __name__ == "__main__":
    main()
