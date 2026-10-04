# 全日本音遊機廳 · Arcade Finder

查詢全日本有 maimai DX / CHUNITHM / オンゲキ / Project DIVA 等音遊的機廳：營業中判斷、距離排序、清單 / 地圖檢視、收藏、多點巡迴導航，可安裝成 PWA。

網站：https://maimai-japan-map.netlify.app

## 資料流程

| 步驟 | 指令 | 說明 |
|---|---|---|
| 1 | `python maimai_detail.py` | 從 [ALL.Net 設置店舖檢索](https://location.am-all.net/alm/location?gm=96) 爬 47 都道府縣的店家、營業時間、遊戲清單 → `maimai_full.csv`（分縣存在 `by_pref2/`） |
| 2 | `python add_coords.py` | 補經緯度 |
| 3（選用） | `python maimai_tw.py` → `add_coords_tw.py` → `add_tw_names.py` | 併入台灣機廳（gm=98）＋座標＋中文店名（Music Game Map） |
| 4 | `python make_index.py` | 讀 `maimai_full.csv`，產生 `site/`（單檔 HTML + PWA） |

需求：`pip install requests beautifulsoup4`

## 部署

Netlify，發佈目錄為 `site/`（見 `netlify.toml`）：

```
netlify deploy --prod --dir site
```

改了頁面內容時，記得把 `make_index.py` 裡 Service Worker 的快取名稱（`maimai-vN`）加一，已安裝 PWA 的使用者才會拿到新版。
