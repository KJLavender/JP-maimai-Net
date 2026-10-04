# 🎵 全日本音遊機廳 · Arcade Finder

[English](README.md) | **繁體中文**

查詢日本與台灣有 maimai DX / CHUNITHM / オンゲキ / Project DIVA 等音遊的機廳。資料來自 SEGA 官方 ALL.Net 設置店舖檢索，整理成一個可離線使用、可安裝到手機桌面的單頁網站。

🔗 **正式版：https://maimai-japan-map.netlify.app**（`main`）

🧪 **測試版：https://test--maimai-japan-map.netlify.app**（`test`）

[![CI](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml/badge.svg)](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml)

## ✨ 功能

- 🕒 **營業狀態即時判斷**：營業中／快打烊／快開門倒數，依當地時間計算（日本 UTC+9、台灣 UTC+8）
- 🎮 **依遊戲篩選**：音遊按鈕＋其他 ALL.Net 遊戲下拉；國際版（International Version）與日版視為同一款
- 📍 **附近機廳**：GPS 定位或輸入地名，依距離排序，可限 5 / 10 / 20 km
- 🔎 **搜尋**：店名、地址、縣市、中文店名；日本新字體與繁體互通（輸入「沖繩」也找得到「沖縄」）
- 🌙 **營業到深夜**、⭐ **收藏**（存在瀏覽器）
- 🧭 **機廳巡迴路線**：最多 9 站，一鍵開 Google Maps 多點導航
- 🗺️ **清單／地圖雙檢視**：叢集標記，綠＝營業中
- 📱 **PWA**：可加到主畫面，離線也能看清單

## 🔄 資料流程

| 步驟 | 指令 | 說明 |
|---|---|---|
| 1 | `python maimai_detail.py` | 爬 [ALL.Net](https://location.am-all.net/alm/location?gm=96) 47 都道府縣：店名、地址、營業時間、遊戲清單 → `maimai_full.csv`（分縣在 `by_pref2/`） |
| 2 | `python add_coords.py` | 補經緯度 |
| 3 | `python maimai_tw.py` | 併入台灣機廳（gm=98 國際版） |
| 4 | `python add_coords_tw.py` | 補台灣經緯度 |
| 5 | `python add_tw_names.py` | 從 [Music Game Map](https://mgm.wind-chime.info) 對應中文店名（距離＋品牌比對；`--scan 400` 重新抓快取） |
| 6 | `python add_google_ids.py` | 用 Google Places API 找每間店的 Google place ID，讓「店家資訊」「導航」直接開到那間店（需 `.env` 內 `GOOGLE_MAPS_API_KEY`；只存 place ID，符合 Google 快取規定） |
| 7 | `python make_index.py` | 讀 `maimai_full.csv`，產生 `site/`（資料內嵌的單檔 HTML + PWA） |

需求：Python 3.10+、`pip install requests beautifulsoup4`

## 🌿 分支與部署

| 分支 | 網址 | 規則 |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | 協作者可以直接 push，push 後自動部署 |
| `main` | https://maimai-japan-map.netlify.app | 只能透過 PR 合併：CI 通過＋維護者 approve，合併後自動部署 |

流程：改東西 → push 到 `test` → 在測試版網址確認 → 開 PR `test → main` → review 通過後合併 → 正式版更新。

**CI**（GitHub Actions，`push` / PR 到 `main`、`test` 時執行）：
1. 重新執行 `make_index.py`，確認 commit 進來的 `site/` 與資料、程式同步
2. 用 Playwright 開 Chromium 跑 `tests/test_site.py`（搜尋、篩選、收藏、定位、路線、地圖、手機版面等 33 項）

**CD**：Netlify 直接發佈 `site/`（見 `netlify.toml`），不在雲端建置，所以請在本機跑完 `make_index.py` 後，把 `site/` 一起 commit。

本機跑測試：

```
pip install playwright && python -m playwright install chromium
cd site && python -m http.server 8765      # 另開一個終端機
BROWSER_CHANNEL= python tests/test_site.py
```

改了頁面內容時，把 `make_index.py` 裡 Service Worker 的快取名稱（`maimai-vN`）加一，已安裝 PWA 的使用者才會拿到新版。

## 📝 備註

- 店家資料版權屬 SEGA；地圖 © OpenStreetMap 貢獻者
- 營業時間：日本取自 SEGA 官方；官方沒登記的會提示改看 Google 地圖。台灣以 Music Game Map 為準（SEGA 國際版的時間常是預設值），標示「僅供參考」
