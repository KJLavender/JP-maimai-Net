# -*- coding: utf-8 -*-
"""maimai DX 曲庫：arcade-songs 資料集（約 5MB）→ 瘦身成 data/songs.json，給網站 🎵 maimai 頁（曲庫、B50）用。
來源：https://arcade-songs.zetaraku.dev（與 mai-bot 相同）
格式（用陣列省空間，索引指向 cats／vers／des）：
  {"updated", "new": [國際版新曲版本], "cats": [分類], "vers": [[版本, 簡稱, 日期]], "des": [譜師],
   "songs": [[歌名, 藝術家, 分類, 版本, BPM, 日期, 封面, 羅馬拼音, 未解禁, 備註, [譜面…]]]}
  譜面：[類型 0=DX 1=STD 2=宴, 難度 0～4（宴是「【宴】」這類字）, 等級, 定數, 估計, 譜師, 物量, 地區, 版本, 國際版]
    估計 1＝定數還沒公布、用等級估的；物量 [tap, hold, slide, touch, break, total]
    地區這些位元：1 日版、2 國際版、4 美國版、8 中國版；國際版和日版不同時是 [等級, 定數, 估計, 版本]，相同是 0
  羅馬拼音已正規化（與 mai-bot 相同、和 mai.js 的 normRomaji 一致），給搜尋用拼音找日文歌名。
  "dan": [[版本, "jp"|"intl", "dan"|"friend", [[標題, 說明, [[歌曲索引, 譜面索引, 備註]…]]…]]]
    段位認定／オトモダチ対戦的課題曲（來源 arcade-songs gallery.yaml）；對不到的譜面是 [-1, "歌名|類型|難度", 備註]
封面小圖存在 data/covers/（約 15 MB，只下載新的），網站從自己的網域讀。
來源連不上或資料明顯少了一大截時，沿用現有的 data/songs.json，不會把網站弄壞。
用法：pip install pykakasi pyyaml && python scripts/songs.py
"""
import paths
import json, os, re
import requests
import pykakasi
import yaml

# 統一黑本式／訓令式與長音（與 mai-bot song_data.py、templates/mai.js 相同）
ROMAJI_RULES = [
    ("jy", "j"), ("shi", "si"), ("sh", "sy"), ("chi", "ti"), ("ch", "ty"),
    ("tsu", "tu"), ("fu", "hu"), ("ji", "zi"), ("j", "zy"),
    ("ou", "o"), ("oo", "o"), ("uu", "u"), ("aa", "a"), ("ii", "i"), ("ee", "e"),
]
_kks = pykakasi.kakasi()


def romaji(title):
    text = re.sub(r"[^a-z0-9]", "", "".join(i["hepburn"] for i in _kks.convert(title)).lower())
    for old, new in ROMAJI_RULES:
        text = text.replace(old, new)
    return text

URL = "https://dp4p6x0xfi5o9.cloudfront.net/maimai/data.json"
GALLERY = "https://dp4p6x0xfi5o9.cloudfront.net/maimai/gallery.yaml"
COVER_URL = "https://dp4p6x0xfi5o9.cloudfront.net/maimai/img/cover-m/"
OUT = os.path.join(paths.DATA, "songs.json")
COVERS = os.path.join(paths.DATA, "covers")
DIFFS = ["basic", "advanced", "expert", "master", "remaster"]
TYPES = ["dx", "std", "utage"]
REGIONS = ["jp", "intl", "usa", "cn"]
DAN_TITLE = re.compile(r"^(.+?) (段位認定|オトモダチ対戦)(（海外版）)?$")


def dan_courses(d):
    """arcade-songs 的「段位歌單」→ 只留段位認定與オトモダチ対戦，譜面換成 songs 裡的索引"""
    idx = {}
    for i, s in enumerate(d["songs"]):
        for j, sh in enumerate(s["sheets"]):
            idx.setdefault(f"{s['songId']}|{sh['type']}|{sh['difficulty']}", (i, j))
    out = []
    for lst in yaml.safe_load(requests.get(GALLERY, timeout=60).text):
        m = DAN_TITLE.match(lst.get("title", ""))
        if not m or lst.get("isHidden"):
            continue
        sections = []
        for sec in lst.get("sections") or []:
            notes = sec.get("sheetDescriptions") or []
            sheets = []
            for k, expr in enumerate(sec.get("sheets") or []):
                note = notes[k] if k < len(notes) else ""
                sheets.append([*idx[expr], note] if expr in idx else [-1, expr, note])
            sections.append([sec.get("title", ""), sec.get("description", ""), sheets])
        out.append([m.group(1), "intl" if m.group(3) else "jp",
                    "dan" if m.group(2) == "段位認定" else "friend", sections])
    return out


def sync_covers(names):
    """只下載還沒有的封面；失敗的下次再試（網站會先用來源網址頂著）"""
    os.makedirs(COVERS, exist_ok=True)
    have = set(os.listdir(COVERS))
    got = fail = 0
    for n in sorted(names - have):
        if not re.fullmatch(r"[0-9A-Za-z_-]+\.(png|jpe?g|webp)", n):
            continue
        try:
            r = requests.get(COVER_URL + n, timeout=30)
            r.raise_for_status()
        except requests.RequestException:
            fail += 1
            continue
        with open(os.path.join(COVERS, n), "wb") as f:
            f.write(r.content)
        got += 1
    print(f"封面：新增 {got} 張、失敗 {fail} 張，共 {len(os.listdir(COVERS))} 張 → data/covers/")


def load_old():
    try:
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    old = load_old()
    try:
        d = requests.get(URL, timeout=60).json()
        if not d.get("songs"):
            raise ValueError("沒有歌曲")
    except (requests.RequestException, ValueError) as e:
        print(f"⚠️ 抓不到 arcade-songs（{e}），沿用現有的 data/songs.json")
        return
    cats = [c["category"] for c in d["categories"]]
    vers = [[v["version"], v["abbr"], v["releaseDate"]] for v in d["versions"]]
    vidx = {v[0]: i for i, v in enumerate(vers)}
    des, didx = [], {}

    def designer(name):
        if not name or name == "-":
            return -1
        if name not in didx:
            didx[name] = len(des)
            des.append(name)
        return didx[name]

    songs, intl_vers = [], set()
    for s in d["songs"]:
        sheets = []
        for sh in s["sheets"]:
            ver = vidx.get(sh.get("version") or s["version"], vidx.get(s["version"], -1))
            reg = sum(1 << i for i, r in enumerate(REGIONS) if (sh.get("regions") or {}).get(r))
            o = (sh.get("regionOverrides") or {}).get("intl") or {}
            io = 0
            if o:
                c, est = sh["internalLevelValue"], int(sh["internalLevel"] is None)
                if "internalLevelValue" in o:
                    c, est = o["internalLevelValue"], int(o.get("internalLevel") is None)
                elif "levelValue" in o:
                    c, est = o["levelValue"], 1
                io = [o.get("level", sh["level"]), c, est, vidx.get(o.get("version"), ver)]
            if reg & 2 and sh["type"] != "utage":
                intl_vers.add(io[3] if io else ver)
            n = sh.get("noteCounts") or {}
            notes = [n.get(k) for k in ("tap", "hold", "slide", "touch", "break", "total")]
            sheets.append([
                TYPES.index(sh["type"]),
                DIFFS.index(sh["difficulty"]) if sh["difficulty"] in DIFFS else sh["difficulty"],
                sh["level"], sh["internalLevelValue"], int(sh["internalLevel"] is None),
                designer(sh.get("noteDesigner")), notes if n.get("total") else 0, reg, ver, io,
            ])
        songs.append([
            s["title"], s.get("artist") or "", cats.index(s["category"]), vidx.get(s["version"], -1),
            s.get("bpm"), s.get("releaseDate") or "", s.get("imageName") or "", romaji(s["title"]),
            int(bool(s.get("isLocked"))), s.get("comment") or "", sheets,
        ])
    # 新曲枠＝國際版最新的兩個版本；書籤工具讀得到官網新曲清單時以官網為準
    new = [vers[i][0] for i in sorted(intl_vers)][-2:]
    # 來源壞掉只回傳一部分時不要蓋掉好的資料
    if old and len(songs) < len(old["songs"]) * 0.9:
        print(f"⚠️ 這次只有 {len(songs)} 首（原本 {len(old['songs'])} 首），沿用現有的 data/songs.json")
        return
    try:
        dan = dan_courses(d)
    except Exception as e:
        dan = (old or {}).get("dan", [])
        print(f"⚠️ 段位資料抓不到（{e}），沿用舊的")
    out = {"updated": d.get("updateTime", "")[:10], "new": new, "cats": cats, "vers": vers, "des": des,
           "songs": songs, "dan": dan}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    n_sheets = sum(len(s[10]) for s in songs)
    miss = sum(1 for c in dan for sec in c[3] for x in sec[2] if x[0] < 0)
    print(f"{len(songs)} 首、{n_sheets} 個譜面；新曲版本 {new}；段位／友人對戰 {len(dan)} 組"
          f"（{miss} 個譜面對不到）；{os.path.getsize(OUT) // 1024} KB → data/songs.json")
    sync_covers({s[6] for s in songs if s[6]})


if __name__ == "__main__":
    main()
