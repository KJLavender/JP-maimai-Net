# -*- coding: utf-8 -*-
"""
機廳數量的歷史紀錄 → data/history.json（網站「統計」頁的折線圖用）。

每筆快照：{"date": "YYYY-MM-DD", "jp": {"total": N, "games": {遊戲: 店數}, "regions": {縣: 店數}}, "tw": {...}}
日本、台灣分開記：台灣資料是 2026-10 才開始有的，混在一起總數會突然跳一截。

- update_data.py 每次更新完會呼叫 record()，以 data_date.txt 的日期新增（或覆蓋同一天的）一筆
- python scripts/history.py --backfill：從 archive/ 與 git 歷史重建早期的快照（只需要跑一次）
"""
import csv, io, json, os, subprocess, sys
import paths

HISTORY = os.path.join(paths.DATA, "history.json")
ALIAS = {"maimai DX International Version": "maimai でらっくす",   # 與 build_site.py 的 GAME_ALIAS 一致
         "CHUNITHM International Version": "CHUNITHM"}


def summarize(rows):
    """rows：CSV 的 dict 列 → {"jp": {...}, "tw": {...}}（沒有台灣店就不含 tw）。"""
    out = {}
    for r in rows:
        if not r.get("名稱"):
            continue
        side = "tw" if r.get("都道府縣") == "台灣" else "jp"
        s = out.setdefault(side, {"total": 0, "games": {}, "regions": {}})
        s["total"] += 1
        s["regions"][r["都道府縣"]] = s["regions"].get(r["都道府縣"], 0) + 1
        for g in {ALIAS.get(x.strip(), x.strip()) for x in r.get("遊戲", "").split("、") if x.strip()}:
            s["games"][g] = s["games"].get(g, 0) + 1
    return out


def load():
    return json.load(open(HISTORY, encoding="utf-8")) if os.path.exists(HISTORY) else []


def save(hist):
    hist.sort(key=lambda h: h["date"])
    with open(HISTORY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def put(hist, date, summary):
    """同一天只留一筆；新資料只覆蓋它有的部分（例如只有台灣）。"""
    for h in hist:
        if h["date"] == date:
            h.update(summary)
            return
    hist.append({"date": date, **summary})


def record(date):
    """把目前的 data/arcades.csv 記成 date 那天的快照。"""
    hist = load()
    put(hist, date, summarize(csv.DictReader(open(paths.ARCADES, encoding="utf-8-sig"))))
    save(hist)


def git_csv(rev, path):
    out = subprocess.run(["git", "-C", paths.ROOT, "show", f"{rev}:{path}"], capture_output=True)
    return list(csv.DictReader(io.StringIO(out.stdout.decode("utf-8-sig")))) if out.returncode == 0 else None


def backfill():
    hist = []
    # 2026-07-15：第一版爬蟲的分縣檔（只有日本）
    arch = os.path.join(paths.ROOT, "archive", "by_pref2")
    if os.path.isdir(arch):
        rows = [r for f in sorted(os.listdir(arch)) if f.endswith(".csv")
                for r in csv.DictReader(open(os.path.join(arch, f), encoding="utf-8-sig"))]
        put(hist, "2026-07-15", summarize(rows))
    # repo 第一個 commit 的日本資料（檔案日期 9/17）其實就是 7/15 那次爬的、只是補了座標，
    # 各項數字完全相同，不另記一筆。台灣是 2026-10-04 才併進來
    tw = git_csv("554717f", "maimai_full.csv")
    if tw:
        put(hist, "2026-10-04", {k: v for k, v in summarize(tw).items() if k == "tw"})
    # 之後的每次更新都有 data/data_date.txt，用它當日期
    revs = subprocess.run(["git", "-C", paths.ROOT, "log", "--reverse", "--format=%H", "--", "data/data_date.txt"],
                          capture_output=True, text=True).stdout.split()
    for rev in revs:
        d = subprocess.run(["git", "-C", paths.ROOT, "show", f"{rev}:data/data_date.txt"],
                           capture_output=True, text=True).stdout.strip()
        rows = git_csv(rev, "data/arcades.csv") or git_csv(rev, "maimai_full.csv")
        if d and rows:
            put(hist, d, summarize(rows))
    save(hist)
    for h in sorted(hist, key=lambda h: h["date"]):
        print(h["date"], "日本", h.get("jp", {}).get("total", "-"), "台灣", h.get("tw", {}).get("total", "-"))


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        backfill()
    else:
        print(__doc__)
