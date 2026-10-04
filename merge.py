# -*- coding: utf-8 -*-
# 合併 by_pref/ 內各縣 CSV。可在 by_pref 資料夾內或其上層執行皆可。
# 用法：python merge.py
import csv, glob, os, re

# 同時找目前資料夾與 by_pref/ 底下、檔名為「NN_縣名.csv」的分縣檔（跳過自己的輸出）
files = sorted({f for f in glob.glob("*.csv") + glob.glob("by_pref/*.csv")
                if re.match(r"\d\d_", os.path.basename(f))})
print(f"找到 {len(files)} 個分縣檔")

header = ["名稱", "地址", "都道府縣", "地圖連結"]   # 預設，讀到檔案會覆寫
rows, seen = [], set()
for fp in files:
    with open(fp, encoding="utf-8-sig") as f:
        r = csv.reader(f)
        h = next(r, None)
        if h:
            header = h
        for row in r:
            if not row:
                continue
            k = tuple(row[:2])          # 名稱+地址 去重
            if k not in seen:
                seen.add(k)
                rows.append(row)

print(f"總計 {len(rows)} 筆")

def dump(path, data):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(data)

if not rows:
    print("0 筆：確認你在含有 by_pref 的位置，或直接進 by_pref 資料夾再跑。")
elif len(rows) <= 2000:
    dump("maimai_all.csv", rows)
    print("→ maimai_all.csv（可一次匯入單一圖層）")
else:
    os.makedirs("chunks", exist_ok=True)
    n = -(-len(rows) // 2000)
    for i in range(0, len(rows), 2000):
        dump(f"chunks/chunk_{i // 2000 + 1}.csv", rows[i:i + 2000])
    print(f"→ 已切成 {n} 塊在 chunks/，每塊≤2000，各匯一個圖層")