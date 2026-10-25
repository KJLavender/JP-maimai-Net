# -*- coding: utf-8 -*-
"""maimai DX 歌曲定數：arcade-songs 資料集（約 5MB）→ 瘦身成 data/songs.json，給網站 🎵 B50 頁用。
來源：https://arcade-songs.zetaraku.dev（與 mai-bot 相同）
格式：{"updated", "new": [新曲版本], "songs": [[歌名, "dx"|"std", 版本, 封面檔名, [5 難度定數], 估計遮罩]]}
      定數依序 BASIC～Re:MASTER，沒有該難度為 null；估計遮罩第 i 位是 1 表示該難度定數還沒公布、用等級估的。
用法：python scripts/songs.py
"""
import paths
import json, os
import requests

URL = "https://dp4p6x0xfi5o9.cloudfront.net/maimai/data.json"
OUT = os.path.join(paths.DATA, "songs.json")
DIFFS = ["basic", "advanced", "expert", "master", "remaster"]


def main():
    d = requests.get(URL, timeout=60).json()
    # 新曲枠＝國際版最新的兩個版本（例：CiRCLE 與 CiRCLE PLUS）；書籤工具讀得到官網新曲清單時以官網為準
    intl = {s["version"] for s in d["songs"] for sh in s["sheets"] if (sh.get("regions") or {}).get("intl")}
    new = [v["version"] for v in d["versions"] if v["version"] in intl][-2:]
    songs = []
    for s in d["songs"]:
        for kind in ("dx", "std"):
            sheets = {sh["difficulty"]: sh for sh in s["sheets"] if sh["type"] == kind}
            if not sheets:
                continue
            consts, est = [], 0
            for i, diff in enumerate(DIFFS):
                sh = sheets.get(diff)
                consts.append(sh["internalLevelValue"] if sh else None)
                if sh and sh.get("internalLevel") is None:
                    est |= 1 << i
            songs.append([s["title"], kind, s["version"], s.get("imageName") or "", consts, est])
    out = {"updated": d.get("updateTime", "")[:10], "new": new, "songs": songs}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(songs)} 個譜面組（歌名×DX/STD）；新曲版本 {new}；{os.path.getsize(OUT) // 1024} KB → data/songs.json")


if __name__ == "__main__":
    main()
