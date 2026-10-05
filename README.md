# 🎵 Japan Rhythm Game Arcade Finder

**English** | [繁體中文](README.zh-TW.md)

Find arcades in Japan and Taiwan that have maimai DX, CHUNITHM, ONGEKI, Project DIVA and other rhythm games. The data comes from SEGA's official ALL.Net location search and is packed into a single-page site that works offline and can be installed to your phone's home screen.

🔗 **Production: https://maimai-japan-map.netlify.app** (`main`)

🧪 **Staging: https://test--maimai-japan-map.netlify.app** (`test`)

[![CI](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml/badge.svg)](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml)

> The site UI is in Traditional Chinese; arcade names and addresses are shown as listed by SEGA (Japanese / English), with Chinese names added for Taiwan where available.

## ✨ Features

- 🕒 **Live open/closed status**: open, closing soon, opening soon, closed today — calculated from local time **and day of week** (Japan UTC+9, Taiwan UTC+8); arcades with different weekday/weekend hours show a weekly summary
- 🎮 **Filter by game**: rhythm-game buttons plus a dropdown for every other ALL.Net title; International Versions count as the same game as the Japanese ones
- 📍 **Nearby arcades**: use GPS or type a place name, sort by distance, limit to 5 / 10 / 20 km
- 🔎 **Search** by name, address, prefecture or Chinese name; Japanese shinjitai and Traditional Chinese characters match each other (「沖繩」 finds 「沖縄」)
- 🌙 **Open late** filter, ⭐ **favorites** (saved in the browser)
- 🧭 **Arcade crawl route**: pick up to 9 stops and open them as one multi-stop Google Maps route
- 🎰 **Taiwan machine details**: machine count, version/cabinet, coin type, queueing style and player notes (from Music Game Map)
- 🔗 **Shareable links**: filters are stored in the URL, so a friend opening the link sees the same results (only "search this place" locations are shared, never your GPS position)
- 🗺️ **List / map views**: clustered markers, green = open now
- 📱 **PWA**: add to home screen; the list works offline

## 📁 Project layout

```
├── data/                 Data
│   ├── arcades.csv       All arcades (main dataset)
│   ├── mgm_cache.csv     Music Game Map cache (Taiwan Chinese names, machine details)
│   └── data_date.txt     Data date
├── scripts/              Scrapers and data processing
│   ├── update_data.py    ⭐ One-command update (calls most of the other scripts)
│   ├── build_site.py     Generates the site/ folder
│   ├── scrape_jp.py      Scrapes Japanese arcades (SEGA ALL.Net gm=96)
│   ├── scrape_tw.py      Scrapes Taiwan arcades (gm=98)
│   ├── coords_jp.py      Japan coordinates (SEGA list pages)
│   ├── coords_tw.py      Taiwan coordinates (SEGA list pages)
│   ├── coords_gsi.py     Fills coordinates SEGA doesn't provide, via GSI Japan
│   ├── mgm_tw.py         Taiwan Chinese names + machine details (Music Game Map)
│   ├── google_place_ids.py  Google place IDs (needs an API key)
│   ├── google_hours.py   Google opening hours (needs an API key)
│   └── paths.py          All file paths
├── site/                 The website (Netlify publishes this folder as-is)
├── tests/test_site.py    E2E tests (Playwright)
└── .github/workflows/    CI and the weekly data update
```

## 🔄 Data pipeline

| Command | What it does |
|---|---|
| `python scripts/update_data.py --mgm` | **The only command you need for routine updates**: re-scrapes SEGA (Japan + Taiwan), carries over the Google / Chinese-name / machine columns from the previous data, fills missing coordinates via GSI, refreshes Music Game Map and writes a change summary to `data/update_summary.md`. GitHub Actions runs it every Monday (without `--mgm`, see below) |
| `python scripts/build_site.py` | Reads `data/arcades.csv` and generates `site/` (single HTML file with the data inlined, PWA files and `data.json`) |
| `python scripts/google_place_ids.py` | Looks up each arcade's Google place ID with the Places API so "store info" and navigation open the exact place (needs `GOOGLE_MAPS_API_KEY` in `.env`; only place IDs are stored, per Google's caching rules) |
| `python scripts/google_hours.py` | Fills opening hours (including per-weekday hours) from Google Place Details: all Taiwan arcades plus Japanese ones with no official hours; never exceeds the daily quota or the 1,000 free calls per month |

The other scripts (`scrape_*`, `coords_*`, `mgm_tw.py`) are called by `update_data.py` and can also be run on their own for debugging (`--test`). Every script works from any directory.

Requirements: Python 3.10+, `pip install requests beautifulsoup4`

## 🌿 Branches & deployment

| Branch | URL | Rules |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | Collaborators can push directly; every push deploys automatically |
| `main` | https://maimai-japan-map.netlify.app | Changes only arrive through a PR: CI must pass and the maintainer must approve; merging deploys automatically |

Workflow: make a change → push to `test` → check it on the staging URL → open a PR `test → main` → merge after review → production updates.

**CI** (GitHub Actions, on push / PR to `main` or `test`):
1. Re-runs `scripts/build_site.py` and checks that the committed `site/` is in sync with the data and code
2. Runs `tests/test_site.py` in Chromium with Playwright (33 checks: search, filters, favorites, geolocation, routes, map, mobile layout)

**Weekly data update** (`.github/workflows/update-data.yml`): every Monday at 03:00 JST the data is re-scraped; if anything changed, a PR is opened against `test` listing new/removed arcades and game/hours changes. E2E tests run inside the job first. It can also be triggered by hand from the Actions tab. Music Game Map blocks requests from GitHub Actions, so the weekly job reuses `data/mgm_cache.csv`; refresh Taiwan Chinese names / machine details by running `--mgm` locally now and then (a failed scan automatically keeps the old cache).

**CD**: Netlify publishes `site/` as-is (see `netlify.toml`) with no cloud build, so run `scripts/build_site.py` locally and commit `site/` with your changes.

Run the tests locally:

```
pip install playwright && python -m playwright install chromium
cd site && python -m http.server 8765      # in another terminal
BROWSER_CHANNEL= python tests/test_site.py
```

When you change the page, bump the Service Worker cache name (`maimai-vN`) in `scripts/build_site.py` so users who installed the PWA get the new version.

## 🤖 Data API

The site also serves `https://maimai-japan-map.netlify.app/data.json` (CORS enabled) for bots and other programs:

```json
{"updated": "2026-10-05", "count": 1115, "shops": [{
  "name": "ＧｉＧＯすすきの", "name_zh": "", "region": "北海道", "address": "…",
  "hours": "10:00〜23:30", "hours_week": null, "hours_source": "SEGA", "timezone": "Asia/Tokyo",
  "games": ["CHUNITHM", "maimai でらっくす", …], "lat": 43.05, "lng": 141.35,
  "google_maps_url": "…", "official_url": "…", "machines": [ …Taiwan only… ]
}]}
```

`hours_week` holds seven entries, Sunday to Saturday (present only when the days differ).

## 📝 Notes

- Arcade data © SEGA; map data © OpenStreetMap contributors; Taiwan Chinese names and machine details from [Music Game Map](https://mgm.wind-chime.info) (player-reported); extra coordinates from GSI Japan
- Opening hours, in order of preference: Japan — SEGA official → Google Maps; Taiwan — Google Maps → Music Game Map → SEGA (International listings often carry placeholder hours). Hours from Google are labelled "Google Maps"; other Taiwan sources are marked as approximate
