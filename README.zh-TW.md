# 音GO（OtoGO）— 找日本與台灣的音遊機廳

[English](README.md) | **繁體中文**

音GO 是一個網站，可以查日本和台灣哪些機廳有 maimai DX、CHUNITHM、オンゲキ、Project DIVA 等音樂遊戲，以及現在有沒有營業。名單來自 SEGA 官方的機廳檢索（ALL.Net）。腳本把資料抓下來，整理成一個可以離線使用、也能加到手機桌面的單頁網站。

正式版：<https://maimai-japan-map.netlify.app>（`main` 分支）
測試版：<https://test--maimai-japan-map.netlify.app>（`test` 分支）

[![CI](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml/badge.svg)](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml)

網站介面是繁體中文。機廳名稱和地址照 SEGA 的原樣顯示（日文或英文），台灣的店在有資料時會加上中文名。

## 網站有什麼功能

機廳：

- 依當地時間和星期幾，顯示營業中、快打烊、快開門或今日公休（日本 UTC+9、台灣 UTC+8）。平日和假日時間不同的店，會顯示一週摘要。
- 依遊戲篩選。同一款遊戲的國際版和日版算同一款。
- 用 GPS 或輸入地名找附近的機廳，依距離排序，範圍可選 5、10、20 公里。
- 可搜尋店名、地址、都道府縣或中文名。日文漢字和繁體中文字會互相對得上，所以搜「沖繩」找得到「沖縄」。
- 有「深夜還開」篩選、收藏（存在你的瀏覽器），以及清單和地圖兩種檢視。
- 機廳巡禮路線：最多選 9 站，一次在 Google 地圖開成多站路線。
- 行程規劃：選日期、出發時間和末班車時間。它依當天的營業時間替你的路線（或目前的搜尋結果）排順序，估算移動時間，並告訴你最晚幾點要離開才趕得上末班車。
- 台灣的機台資訊（台數、版本、投幣方式、排隊方式、玩家備註），來自 Music Game Map。
- 篩選條件會放進網址，所以分享連結的人會看到一樣的結果。分享時只會帶「搜尋這個地點」的位置，不會帶你的 GPS 位置。

制霸紀錄：

- 可以把機廳標成「去過」。47 個都道府縣的方塊地圖會隨著你去過的地方填色，也能匯出成圖片。紀錄存在你的瀏覽器裡。登入（Google 或 Email 加密碼）後，紀錄會在不同裝置間同步，也可以用備份碼搬移。
- 有排行榜，需要自己選擇加入（預設關閉）。只會公開你的名字和數量，也能用好友連結加好友。
- 統計頁：各遊戲的機廳數量隨時間的變化（每週更新多一個點），以及各都道府縣的排名。

maimai DX：

- B50：登入後輸入好友代碼、接受機器人的好友申請，再按一個按鈕就能抓到你的成績。也可以在登入 maimai DX NET（國際版）的狀態下執行書籤小工具。兩種方式都會用譜面定數算出你的 Best 35 + New 15。你的 SEGA 密碼不會經過這個網站。成績存在你的瀏覽器裡，登入後也會同步到你的帳號。
- 推分建議：列出差一點就到下個評級、最能拉高 rating 的譜面。
- 目標 Rating 計畫：例如「推這 5 首就能到 15000」，從最容易的開始。
- 用分享連結和朋友比較，不經過伺服器，連結裡帶的是你 rating 最高的 300 個譜面。
- Rating 紀錄。
- 曲庫，仿照 [arcade-songs](https://arcade-songs.zetaraku.dev/maimai/)：可用歌名、藝術家、譜師或羅馬拼音搜尋，依版本、難度、類型、等級、定數、分類等篩選和排序，也能隨機抽 1 到 10 首。點歌曲看它的譜面，點譜面看各評級能拿多少 Rating。
- 日版限定：日版有、國際版沒有的歌和譜面，去日本前可以加進「我的清單」。
- 各版本的段位認定和友人對戰（オトモダチ対戦）課題曲，有 B50 成績時會顯示你自己的達成率。

## 怎麼做的

網站是純 HTML、CSS 和 JavaScript，沒有用前端建置框架，由 Python 腳本產生：

- `scripts/update_data.py` 爬 SEGA 並寫入 `data/arcades.csv`。
- `scripts/build_site.py` 讀 `data/` 和 `templates/`，輸出到 `site/`。機廳資料直接寫進 `index.html`，旁邊另外有一份 `data.json`。
- Netlify 每次部署都會執行 `build_site.py`，再發佈 `site/`（見 `netlify.toml`）。`site/` 不進 git。

帳號與同步用 Firebase（登入和 Firestore）。其他都在瀏覽器裡執行。

## 在本機執行

需要 Python 3.10 以上。

```bash
python scripts/build_site.py
cd site
python -m http.server 8765
```

然後打開 <http://localhost:8765/index.html>。`build_site.py` 只用標準函式庫。

## 更新資料

```bash
pip install requests beautifulsoup4
python scripts/update_data.py --mgm
```

日常更新只要這一個指令。它會爬 SEGA 的日本和台灣資料，把 SEGA 沒有的欄位（Google place ID、中文名、機台資訊）從舊資料帶過來，用日本國土地理院補缺的座標，加上 `--mgm` 時重抓 Music Game Map，並把變動摘要寫到 `data/update_summary.md`。完整跑一次約 15 到 20 分鐘，`--mgm` 再多約 3 分鐘。`--limit 2` 是快速測試，只爬兩個縣，不寫檔。

| 腳本 | 做什麼 |
|---|---|
| `scripts/songs.py` | 下載 arcade-songs 資料集，瘦身成 `data/songs.json`（約 740 KB），並把小張封面存到 `data/covers/`（約 15 MB，只下載新的）。兩者都會提交，由這個網站自己提供，所以來源消失時 maimai 頁面也能用。來源連不上或歌曲數量明顯變少時，會保留舊檔。需要 `pip install pykakasi pyyaml` |
| `scripts/google_place_ids.py` | 用 Places API 查每間機廳的 Google place ID，讓「店家資訊」和導航能開到正確的店。需要在 `.env` 設定 `GOOGLE_MAPS_API_KEY`（不要提交）。依 Google 的快取規定，只存 place ID |
| `scripts/google_hours.py` | 從 Google Place Details 補營業時間（含每天不同的時段），對象是所有台灣機廳，以及日本沒有官方時間的機廳。不會超過每日配額和每月 1,000 次免費額度 |
| `scripts/history.py` | 記錄統計頁用的機廳數量快照。`--backfill` 會從 git 歷史重建早期的快照 |
| `scripts/mgm_tw.py`、`scrape_*.py`、`coords_*.py` | 由 `update_data.py` 呼叫。除錯時也可以單獨執行（`--test`） |

每支腳本都會自己找檔案位置，從哪個資料夾執行都可以。

## 每週更新、測試與部署

每週資料更新（`.github/workflows/update-data.yml`）：每週一日本時間 03:00，GitHub Actions 重爬資料並執行 `songs.py`。有變動時，會先跑端對端測試，再對 `test` 分支開一個 PR，列出新增和移除的機廳，以及遊戲或營業時間的變動。也可以在 Actions 頁面手動觸發。Music Game Map 會擋 GitHub Actions，所以每週的工作沿用 `data/mgm_cache.csv`。要更新台灣中文名和機台資訊，請偶爾在自己的電腦執行 `python scripts/update_data.py --mgm`。掃描失敗時會保留舊的快取。

CI（`.github/workflows/ci.yml`，推送或對 `main`、`test` 開 PR 時執行）：用 Prettier 檢查 `templates/` 的排版、建置網站，再用 Playwright 在 Chromium 裡執行 `tests/test_site.py`。測試會實際操作搜尋、篩選、收藏、定位、路線、地圖、機台資訊、分享連結、制霸紀錄、統計、帳號與同步、營業狀態和手機版面。

自己執行測試：

```bash
pip install playwright && python -m playwright install chromium
python scripts/build_site.py
cd site && python -m http.server 8765      # 保持執行，另開一個終端機：
BROWSER_CHANNEL= python tests/test_site.py
```

`BROWSER_CHANNEL=`（空值）會讓測試使用 Playwright 內建的 Chromium。不設的話，測試會找已安裝的 Chrome。

排版：`templates/` 用 Prettier 排版（設定在 `.prettierrc.json`），CI 會檢查。改完前端後執行：

```bash
npx prettier@3.9.10 --write templates/
```

分支：

| 分支 | 網址 | 規則 |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | 協作者可以直接推送，每次推送都會部署 |
| `main` | https://maimai-japan-map.netlify.app | 變更要從 `test` 開 PR 進來，CI 要通過，且 `.github/CODEOWNERS` 列的維護者要核准。合併後部署 |

Service Worker 的快取名稱是整個網站內容的雜湊值，所以只要有任何變動就會產生新的快取，裝了這個 App 的人會自動拿到新版，不用手動改版本號。

## 設定登入（Firebase）

只需要做一次。在 `templates/account.js` 的 `FIREBASE_CONFIG` 填好之前，登入按鈕不會顯示。

1. 到 [Firebase 控制台](https://console.firebase.google.com/)建立專案（選既有的 Google Cloud 專案，用 Spark 免費方案）。
2. Authentication > Sign-in method：開啟 Email/Password 和 Google。在 Settings > Authorized domains 加入 `maimai-japan-map.netlify.app` 和 `test--maimai-japan-map.netlify.app`（`localhost` 預設就有）。
3. Firestore Database：用正式模式建立資料庫（例如區域選 `asia-east1`）。在 Rules 貼上 [`firestore.rules`](firestore.rules) 並發佈。
4. Project settings > Your apps：新增 Web app，把 `apiKey`、`authDomain`、`projectId`、`appId` 複製到 `templates/account.js` 的 `FIREBASE_CONFIG`。
5. 到 Google Cloud 控制台的 Google Auth Platform > Audience，把應用程式發佈。還在 Testing 狀態時，只有列出的測試使用者能用 Google 登入。

Firebase 的網頁設定會跟著頁面一起送出，不是機密。存取權限由 `firestore.rules` 控制：每位使用者只能讀寫 `users/{自己的 uid}`；`board/{uid}`（排行榜）任何人都能讀，但只有本人能寫，而且只能寫名字和數量。Firebase SDK 只有在有人打開登入視窗，或之前登入過時才會載入。

## 用好友代碼抓 B50

登入的使用者在 maimai 頁面輸入好友代碼，依序按三個按鈕：送出好友申請、我已接受、更新 B50。每次按下去都會在 Firestore 的 `jobs/{uid}` 寫入一筆工作。規則只允許排隊中的工作，抓成績每 10 分鐘最多一次，好友申請每分鐘最多一次。[maimai-dc-bot](https://github.com/KJLavender/maimai-dc-bot) repo 裡的 `otogo_worker.py` 跑在機器人的伺服器上，用機器人的 maimai DX NET 帳號完成工作，再把成績寫到 `users/{uid}/mai/b50`。設定方式請看那個 repo 的 README。

## 資料 API

網站也提供 `https://maimai-japan-map.netlify.app/data.json`，給機器人或其他程式讀取（已開啟 CORS），快取一小時。

```json
{"updated": "2026-10-19", "count": 1104, "shops": [{
  "id": "…", "name": "ＧｉＧＯすすきの", "name_zh": "", "region": "北海道", "address": "…",
  "hours": "10:00〜23:30", "hours_week": null, "hours_source": "SEGA", "timezone": "Asia/Tokyo",
  "games": ["CHUNITHM", "maimai でらっくす", …], "lat": 43.05, "lng": 141.35,
  "google_place_id": "…", "google_maps_url": "…", "official_url": "…", "machines": [ …只有台灣… ]
}]}
```

`hours_week` 有七筆，從週日到週六，只有各天時間不同時才會出現。上面的值只是範例，實際檔案的 `updated` 和 `count` 是目前資料的值。

## 資料夾

```
data/         arcades.csv（所有機廳）、mgm_cache.csv（Music Game Map 快取）、songs.json 與 covers/（maimai 歌曲）、
              history.json（每次更新的機廳數量）、data_date.txt
scripts/      爬蟲與資料處理；paths.py 集中放所有檔案路徑
templates/    前端原始檔：index.html、style.css、每個功能一支 JS（app、mai、b50、vs、plan、
              conquest、board、stats、account）、bookmarklet.js、sw.js 與離線 App 用的 manifest
tests/        test_site.py，Playwright 端對端測試
site/         產生出來的網站（不進 git）
firestore.rules   資料庫的存取規則
```

## 資料來源與版權

機廳資料 © SEGA。地圖資料 © OpenStreetMap contributors。台灣的中文名和機台資訊來自 [Music Game Map](https://mgm.wind-chime.info)，由玩家回報。額外的座標來自日本國土地理院。

營業時間依這個順序取用。日本：SEGA 官方，再來是 Google 地圖。台灣：Google 地圖，再來是 Music Game Map，最後是 SEGA（國際版的資料常常只是佔位用的時間）。來自 Google 的時間會標示「Google 地圖」，台灣其他來源的時間會標示為大約時間。
