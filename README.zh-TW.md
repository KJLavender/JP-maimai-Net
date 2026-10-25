# 🎵 音GO · 找機廳（OtoGO）

[English](README.md) | **繁體中文**

查詢日本與台灣有 maimai DX / CHUNITHM / オンゲキ / Project DIVA 等音遊的機廳。資料來自 SEGA 官方 ALL.Net 設置店舖檢索，整理成一個可離線使用、可安裝到手機桌面的單頁網站。

🔗 **正式版：https://maimai-japan-map.netlify.app**（`main`）

🧪 **測試版：https://test--maimai-japan-map.netlify.app**（`test`）

[![CI](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml/badge.svg)](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml)

## ✨ 功能

- 🕒 **營業狀態即時判斷**：營業中／快打烊／快開門倒數／今日公休，依當地時間與**星期幾**計算（日本 UTC+9、台灣 UTC+8）；平日、假日時間不同的店會顯示一週摘要
- 🎮 **依遊戲篩選**：音遊按鈕＋其他 ALL.Net 遊戲下拉；國際版（International Version）與日版視為同一款
- 📍 **附近機廳**：GPS 定位或輸入地名，依距離排序，可限 5 / 10 / 20 km
- 🔎 **搜尋**：店名、地址、縣市、中文店名；日本新字體與繁體互通（輸入「沖繩」也找得到「沖縄」）
- 🌙 **營業到深夜**、⭐ **收藏**（存在瀏覽器）
- 🧭 **機廳巡迴路線**：最多 9 站，一鍵開 Google Maps 多點導航
- 🎰 **台灣機台資訊**：台數、版本／框體、投幣方式、排隊方式、玩家備註（來自 Music Game Map）
- 🔗 **分享連結**：篩選條件存在網址裡，傳給朋友打開就是同樣的結果（只分享「搜尋此地」，不會分享你的 GPS 位置）
- 🏆 **機廳制霸**：店家按「🏁 標記去過」，47 都道府縣方格地圖依達成比例上色，可匯出成圖片分享；紀錄存在你自己的瀏覽器；可以從右上角**登入**（Google 或 Email＋密碼）讓手機和電腦自動同步，或用「備份／還原」代碼搬過去
- 📊 **統計**：各音遊設置店數的變化（每週更新多一個點）、各都道府縣機廳數排行，可切換遊戲、可看表格
- 🎵 **maimai DX B50**：登入 maimai DX NET（國際版）後點一下書籤工具，讀取*你自己的*成績帶回來，配上定數算舊曲 B35＋新曲 B15。SEGA 帳密不經過本站；成績存在瀏覽器，登入時同步到帳號。另有 📈 推分建議（差一點就到下個評級、推上去會漲 Rating 的譜面）和 📉 Rating 紀錄
- 🎵 **maimai 工具**（都是按鈕、不用打指令，mai-bot 的網頁版）：🔍 用歌名或羅馬拼音查歌、📋 依等級列定數表、🎲 依等級抽一首；點任何譜面看各評級（SSS+…AAA）能拿多少 Rating
- 🗺️ **清單／地圖雙檢視**：叢集標記，綠＝營業中
- 📱 **PWA**：可加到主畫面，離線也能看清單

## 📁 專案結構

```
├── data/                 資料
│   ├── arcades.csv       所有機廳（主資料）
│   ├── mgm_cache.csv     Music Game Map 快取（台灣中文名、機台資訊）
│   ├── history.json      每次更新的機廳數快照（統計頁用）
│   └── data_date.txt     資料更新日
├── scripts/              爬蟲與資料處理
│   ├── update_data.py    ⭐ 一鍵更新（其他腳本多半由它呼叫）
│   ├── history.py        記錄歷史快照；`--backfill` 從 git 歷史重建
│   ├── build_site.py     data/ ＋ templates/ → 產生網站 site/
│   ├── scrape_jp.py      爬日本機廳（SEGA ALL.Net gm=96）
│   ├── scrape_tw.py      爬台灣機廳（gm=98）
│   ├── coords_jp.py      日本座標（SEGA 清單頁）
│   ├── coords_tw.py      台灣座標（SEGA 清單頁）
│   ├── coords_gsi.py     SEGA 沒附座標時，用國土地理院補
│   ├── mgm_tw.py         台灣中文名＋機台資訊（Music Game Map）
│   ├── google_place_ids.py  Google place ID（需 API key）
│   ├── google_hours.py   Google 營業時間（需 API key）
│   └── paths.py          所有檔案路徑
├── templates/            前端原始檔（要改網頁就改這裡）
│   ├── index.html        頁面骨架（__DATA__ 等佔位符由 build_site.py 填入）
│   ├── style.css / app.js
│   ├── conquest.js / stats.js   🏆 制霸、📊 統計
│   ├── account.js / privacy.html   👤 登入與同步（Firebase）、隱私權說明
│   ├── mai.js                      🎵 maimai 頁：子分頁、查歌、定數表、抽一首、各評級 Rating
│   ├── b50.js / bookmarklet.js     🎵 B50 頁、在 maimai DX NET 上執行的書籤工具
│   └── sw.js / manifest.webmanifest / icon.svg   PWA
├── site/                 產生出來的網站（不進 repo，Netlify 部署時產生）
├── tests/test_site.py    E2E 測試（Playwright）
└── .github/workflows/    CI、每週自動更新
```

## 🔄 資料流程

| 指令 | 說明 |
|---|---|
| `python scripts/update_data.py --mgm` | **日常更新只要跑這個**：重爬 SEGA（日本＋台灣）、對回舊資料保留 Google／中文名／機台欄位、GSI 補座標、更新 Music Game Map，輸出變動摘要 `data/update_summary.md`。GitHub Actions 每週一自動執行（不含 `--mgm`，見下方） |
| `python scripts/build_site.py` | 讀 `data/arcades.csv` 與 `templates/`，產生 `site/`（店家資料內嵌在 `index.html`，另輸出 `data.json`）；Service Worker 的快取版本依內容自動計算 |
| `python scripts/google_place_ids.py` | 用 Google Places API 找每間店的 Google place ID，讓「店家資訊」「導航」直接開到那間店（需 `.env` 內 `GOOGLE_MAPS_API_KEY`；只存 place ID，符合 Google 快取規定） |
| `python scripts/google_hours.py` | 用 Google Place Details 補營業時間（含一週各天時段）：台灣全部＋日本官方沒登記的；不會超過每日配額與每月免費 1,000 次 |
| `python scripts/songs.py` | 從 [arcade-songs](https://arcade-songs.zetaraku.dev) 下載定數、瘦身成 `data/songs.json`（約 270 KB，含 `pykakasi` 轉的羅馬拼音供搜尋）給 maimai 頁用；每週資料更新也會跑 |

其他腳本（`scrape_*`、`coords_*`、`mgm_tw.py`）都會被 `update_data.py` 呼叫，也可以單獨執行除錯（加 `--test`）。所有腳本從哪個資料夾執行都可以。

需求：Python 3.10+、`pip install requests beautifulsoup4`

## 🌿 分支與部署

| 分支 | 網址 | 規則 |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | 協作者可以直接 push，push 後自動部署 |
| `main` | https://maimai-japan-map.netlify.app | 只能透過 PR 合併：CI 通過＋維護者 approve，合併後自動部署 |

流程：改東西 → push 到 `test` → 在測試版網址確認 → 開 PR `test → main` → review 通過後合併 → 正式版更新。

**CI**（GitHub Actions，`push` / PR 到 `main`、`test` 時執行）：
檢查 `templates/` 的排版（Prettier），並執行 `scripts/build_site.py` 產生網站，再用 Playwright 開 Chromium 跑 `tests/test_site.py`（搜尋、篩選、收藏、定位、路線、地圖、機台資訊、分享連結、制霸、統計、帳號與同步、營業狀態、手機版面等）

**每週自動更新**（`.github/workflows/update-data.yml`）：每週一 03:00（日本時間）重爬資料，有變動就開 PR 到 `test`，PR 內文列出新增／消失的店、遊戲與營業時間變動；E2E 測試會先在流程裡跑過。也可以在 Actions 頁面手動執行。Music Game Map 會擋 GitHub Actions 的連線，所以自動更新沿用 `data/mgm_cache.csv`；台灣中文名／機台資訊請偶爾在本機跑 `--mgm` 更新（掃描失敗時會自動保留舊快取）。

**CD**：Netlify 部署時執行 `python3 scripts/build_site.py` 產生 `site/` 再發佈（見 `netlify.toml`）。`site/` 不進 repo，改網頁只要改 `templates/`、改資料只要改 `data/`。

**帳號設定（Firebase）**（只要做一次；`templates/account.js` 裡的 `FIREBASE_CONFIG` 填好之前，登入按鈕不會出現）：

1. [Firebase 控制台](https://console.firebase.google.com/) →「建立專案」→ 選既有的 Google Cloud 專案（Spark 免費方案）
2. 「Authentication」→「Sign-in method」：開啟 **電子郵件／密碼** 和 **Google**。「設定」→「已授權網域」：加入 `maimai-japan-map.netlify.app`、`test--maimai-japan-map.netlify.app`（`localhost` 預設就有）
3. 「Firestore Database」→「建立資料庫」（正式環境模式，區域例如 `asia-east1` 台灣）→「規則」：貼上 [`firestore.rules`](firestore.rules) 的內容後發布
4. 「專案設定」→「你的應用程式」→ 新增 **網頁**應用程式 → 把 `apiKey`、`authDomain`、`projectId`、`appId` 填進 `templates/account.js` 的 `FIREBASE_CONFIG`
5. Google Cloud 控制台 →「Google Auth Platform」→「目標對象」→「**發布應用程式**」（停在「測試中」只有列出的測試使用者能用 Google 登入）

Firebase 的網頁設定是公開資訊（會出現在網頁裡），不是密鑰；誰能讀寫什麼由 `firestore.rules` 控管，每個人只能讀寫 `users/{自己的 uid}`。Firebase SDK 只有在有人打開登入視窗、或之前登入過時才會載入。

本機跑測試：

```
pip install playwright && python -m playwright install chromium
python scripts/build_site.py
cd site && python -m http.server 8765      # 另開一個終端機
BROWSER_CHANNEL= python tests/test_site.py
```

**排版**：`templates/` 用 [Prettier](https://prettier.io) 統一格式（設定在 `.prettierrc.json`），CI 會檢查。改完前端後執行：

```
npx prettier@3.9.10 --write templates/
```

Service Worker 的快取名稱是整個網站內容的雜湊值，任何檔案一改就會自動換新，已安裝 PWA 的使用者會拿到新版，不用手動改版本號。

## 🤖 資料 API

網站同時提供 `https://maimai-japan-map.netlify.app/data.json`（允許跨網域），給 Discord bot 等程式使用：

```json
{"updated": "2026-10-05", "count": 1115, "shops": [{
  "name": "ＧｉＧＯすすきの", "name_zh": "", "region": "北海道", "address": "…",
  "hours": "10:00〜23:30", "hours_week": null, "hours_source": "SEGA", "timezone": "Asia/Tokyo",
  "games": ["CHUNITHM", "maimai でらっくす", …], "lat": 43.05, "lng": 141.35,
  "google_maps_url": "…", "official_url": "…", "machines": [ …台灣才有… ]
}]}
```

`hours_week` 是星期日到星期六 7 個時段（只有各天不同的店才有）。

## 📝 備註

- 店家資料版權屬 SEGA；地圖 © OpenStreetMap 貢獻者；台灣中文名與機台資訊來自 [Music Game Map](https://mgm.wind-chime.info)（玩家回報）；座標補充來自國土地理院
- 營業時間來源依序：日本 SEGA 官方 → Google 地圖；台灣 Google 地圖 → Music Game Map → SEGA（國際版的時間常是預設值）。來自 Google 的標示「Google 地圖」，台灣其他來源標示「僅供參考」
