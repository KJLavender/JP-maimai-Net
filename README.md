# 🎵 Japan Rhythm Game Arcade Finder

**English** | [繁體中文](README.zh-TW.md)

Find arcades in Japan and Taiwan that have maimai DX, CHUNITHM, ONGEKI, Project DIVA and other rhythm games. The data comes from SEGA's official ALL.Net location search and is packed into a single-page site that works offline and can be installed to your phone's home screen.

🔗 **Production: https://maimai-japan-map.netlify.app** (`main`)

🧪 **Staging: https://test--maimai-japan-map.netlify.app** (`test`)

[![CI](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml/badge.svg)](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml)

> The site UI is in Traditional Chinese; arcade names and addresses are shown as listed by SEGA (Japanese / English), with Chinese names added for Taiwan where available.

## ✨ Features

- 🕒 **Live open/closed status**: open, closing soon, opening soon countdowns, calculated in local time (Japan UTC+9, Taiwan UTC+8)
- 🎮 **Filter by game**: rhythm-game buttons plus a dropdown for every other ALL.Net title; International Versions count as the same game as the Japanese ones
- 📍 **Nearby arcades**: use GPS or type a place name, sort by distance, limit to 5 / 10 / 20 km
- 🔎 **Search** by name, address, prefecture or Chinese name; Japanese shinjitai and Traditional Chinese characters match each other (「沖繩」 finds 「沖縄」)
- 🌙 **Open late** filter, ⭐ **favorites** (saved in the browser)
- 🧭 **Arcade crawl route**: pick up to 9 stops and open them as one multi-stop Google Maps route
- 🗺️ **List / map views**: clustered markers, green = open now
- 📱 **PWA**: add to home screen; the list works offline

## 🔄 Data pipeline

| Step | Command | What it does |
|---|---|---|
| 1 | `python maimai_detail.py` | Scrapes [ALL.Net](https://location.am-all.net/alm/location?gm=96) for all 47 prefectures: name, address, hours, game list → `maimai_full.csv` (per-prefecture files in `by_pref2/`) |
| 2 | `python add_coords.py` | Adds latitude / longitude |
| 3 | `python maimai_tw.py` | Merges in Taiwan arcades (gm=98, International Version) |
| 4 | `python add_coords_tw.py` | Adds coordinates for Taiwan |
| 5 | `python add_tw_names.py` | Matches Chinese names from [Music Game Map](https://mgm.wind-chime.info) by distance + brand (`--scan 400` refreshes the cache) |
| 6 | `python add_google_ids.py` | Looks up each arcade's Google place ID with the Places API so "store info" and navigation open the exact place (needs `GOOGLE_MAPS_API_KEY` in `.env`; only place IDs are stored, per Google's caching rules) |
| 7 | `python add_google_hours.py` | Fills opening hours from Google Place Details: all Taiwan arcades plus Japanese ones with no official hours (1,000 free calls/month; the script caps itself at 600) |
| 8 | `python make_index.py` | Reads `maimai_full.csv` and generates `site/` (single HTML file with the data inlined, plus PWA files) |

Requirements: Python 3.10+, `pip install requests beautifulsoup4`

## 🌿 Branches & deployment

| Branch | URL | Rules |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | Collaborators can push directly; every push deploys automatically |
| `main` | https://maimai-japan-map.netlify.app | Changes only arrive through a PR: CI must pass and the maintainer must approve; merging deploys automatically |

Workflow: make a change → push to `test` → check it on the staging URL → open a PR `test → main` → merge after review → production updates.

**CI** (GitHub Actions, on push / PR to `main` or `test`):
1. Re-runs `make_index.py` and checks that the committed `site/` is in sync with the data and code
2. Runs `tests/test_site.py` in Chromium with Playwright (33 checks: search, filters, favorites, geolocation, routes, map, mobile layout)

**CD**: Netlify publishes `site/` as-is (see `netlify.toml`) with no cloud build, so run `make_index.py` locally and commit `site/` with your changes.

Run the tests locally:

```
pip install playwright && python -m playwright install chromium
cd site && python -m http.server 8765      # in another terminal
BROWSER_CHANNEL= python tests/test_site.py
```

When you change the page, bump the Service Worker cache name (`maimai-vN`) in `make_index.py` so users who installed the PWA get the new version.

## 📝 Notes

- Arcade data © SEGA; map data © OpenStreetMap contributors
- Opening hours, in order of preference: Japan — SEGA official → Google Maps; Taiwan — Google Maps → Music Game Map → SEGA (International listings often carry placeholder hours). Hours from Google are labelled "Google Maps"; other Taiwan sources are marked as approximate
