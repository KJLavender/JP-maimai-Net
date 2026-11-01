# 🎵 OtoGO — Rhythm Game Arcade Finder (音GO · 找機廳)

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
- 🗓️ **Trip planner**: pick a date, start time and last-train time; it orders your selected route (or the current filter results) by that day's opening hours (waiting for doors to open, skipping closed days), estimates travel time, and tells you when you must leave for the last train
- 🎰 **Taiwan machine details**: machine count, version/cabinet, coin type, queueing style and player notes (from Music Game Map)
- 🔗 **Shareable links**: filters are stored in the URL, so a friend opening the link sees the same results (only "search this place" locations are shared, never your GPS position)
- 🏆 **Arcade conquest**: tap "🏁 Mark visited" on any arcade; a tile map of the 47 prefectures fills in by how much you've covered and can be exported as an image to share. Records live in your own browser; optionally **sign in** (Google or email + password, top right) to sync them between phone and computer automatically, or move them with a backup / restore code. 🏅 **Leaderboard**: opt in (off by default) to publish only your name and counts, see the site-wide ranking, and add friends with a friend link
- 📊 **Stats**: how many arcades carry each rhythm game over time (one more point every weekly update) and a ranking by prefecture, switchable by game, with a table view
- 🎵 **maimai DX B50**: when signed in, enter your friend code and accept the bot's friend request, then one button fetches your scores; or run a bookmarklet on maimai DX NET (International) while logged in; it reads *your own* scores and brings them back to compute Best 35 + New 15 with chart constants. Your SEGA password never passes through this site; scores stay in the browser and sync to your account when signed in. Also shows 📈 score-push suggestions (charts close to the next rank that would raise your rating), 🎯 a target-rating plan ("push these 5 charts to reach 15000", easiest first, recomputing B15/B35 after every step), 🆚 a side-by-side comparison with a friend via a share link (no server; the link carries your top 300 scores), and 📉 rating history
- 📚 **maimai song library** (modeled on [arcade-songs](https://arcade-songs.zetaraku.dev/maimai/), all buttons): search by title, artist, chart designer or romaji; filter by International / Japanese version, difficulty, type (DX / STD / 宴), level and constant range, category, version, designer, BPM, new songs and ⭐ my list; sort by constant, level, release date, BPM, note count or title; chart list, cover grid and summary views; 🎲 draw 1–10 random charts from the results. Tap a song for all its charts (designer, note counts, regions); tap a chart for the rating at each rank (SSS+…AAA)
- ✈️ **Japan-only songs**: songs and charts in the Japanese version but not International, filter by level, add them all to ⭐ my list before a trip
- 🎖️ **Dan courses**: 段位認定 and オトモダチ対戦 (friend battle) course songs for every version, International or Japanese version, with life / damage / recovery, the opponent's rank and your own score from B50
- 🗺️ **List / map views**: clustered markers, green = open now
- 📱 **PWA**: add to home screen; the list works offline

## 📁 Project layout

```
├── data/                 Data
│   ├── arcades.csv       All arcades (main dataset)
│   ├── mgm_cache.csv     Music Game Map cache (Taiwan Chinese names, machine details)
│   ├── history.json      Arcade-count snapshot per update (for the stats page)
│   └── data_date.txt     Data date
├── scripts/              Scrapers and data processing
│   ├── update_data.py    ⭐ One-command update (calls most of the other scripts)
│   ├── history.py        Records history snapshots; `--backfill` rebuilds them from git history
│   ├── build_site.py     data/ + templates/ → generates site/
│   ├── scrape_jp.py      Scrapes Japanese arcades (SEGA ALL.Net gm=96)
│   ├── scrape_tw.py      Scrapes Taiwan arcades (gm=98)
│   ├── coords_jp.py      Japan coordinates (SEGA list pages)
│   ├── coords_tw.py      Taiwan coordinates (SEGA list pages)
│   ├── coords_gsi.py     Fills coordinates SEGA doesn't provide, via GSI Japan
│   ├── mgm_tw.py         Taiwan Chinese names + machine details (Music Game Map)
│   ├── google_place_ids.py  Google place IDs (needs an API key)
│   ├── google_hours.py   Google opening hours (needs an API key)
│   └── paths.py          All file paths
├── templates/            Front-end sources (edit these to change the page)
│   ├── index.html        Page skeleton (__DATA__ etc. are filled in by build_site.py)
│   ├── style.css / app.js
│   ├── conquest.js / stats.js   🏆 Conquest, 📊 Stats
│   ├── board.js / plan.js       🏅 Conquest leaderboard, 🗓️ Trip planner
│   ├── account.js / privacy.html   👤 Sign-in & sync (Firebase), privacy notice
│   ├── mai.js                      🎵 maimai page: sub-tabs, song library (filters, views, draw, my list), per-rank rating
│   ├── b50.js / bookmarklet.js     🎵 B50 page (incl. 🎯 target rating), and the bookmarklet that runs on maimai DX NET
│   ├── vs.js                       🆚 Compare B50 with a friend (share links)
│   └── sw.js / manifest.webmanifest / icon.svg   PWA
├── site/                 Generated website (not committed; built by Netlify on deploy)
├── tests/test_site.py    E2E tests (Playwright)
└── .github/workflows/    CI and the weekly data update
```

## 🔄 Data pipeline

| Command | What it does |
|---|---|
| `python scripts/update_data.py --mgm` | **The only command you need for routine updates**: re-scrapes SEGA (Japan + Taiwan), carries over the Google / Chinese-name / machine columns from the previous data, fills missing coordinates via GSI, refreshes Music Game Map and writes a change summary to `data/update_summary.md`. GitHub Actions runs it every Monday (without `--mgm`, see below) |
| `python scripts/build_site.py` | Reads `data/arcades.csv` and `templates/` and generates `site/` (arcade data inlined in `index.html`, plus `data.json`); the Service Worker cache version is derived from the content automatically |
| `python scripts/google_place_ids.py` | Looks up each arcade's Google place ID with the Places API so "store info" and navigation open the exact place (needs `GOOGLE_MAPS_API_KEY` in `.env`; only place IDs are stored, per Google's caching rules) |
| `python scripts/google_hours.py` | Fills opening hours (including per-weekday hours) from Google Place Details: all Taiwan arcades plus Japanese ones with no official hours; never exceeds the daily quota or the 1,000 free calls per month |
| `python scripts/songs.py` | Downloads the [arcade-songs](https://arcade-songs.zetaraku.dev) dataset and slims it into `data/songs.json` (~740 KB, ~280 KB gzipped: every chart with level, constant, designer, note counts, regions and International-version overrides, dan / friend-battle courses, plus romaji from `pykakasi`), and saves small cover images to `data/covers/` (~15 MB, only new ones are downloaded). Everything is committed and served from this site, so the maimai page keeps working if the source goes away; if the source is down or returns far fewer songs, the existing files are kept. The weekly update workflow also runs it |

The other scripts (`scrape_*`, `coords_*`, `mgm_tw.py`) are called by `update_data.py` and can also be run on their own for debugging (`--test`). Every script works from any directory.

Requirements: Python 3.10+, `pip install requests beautifulsoup4`

## 🌿 Branches & deployment

| Branch | URL | Rules |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | Collaborators can push directly; every push deploys automatically |
| `main` | https://maimai-japan-map.netlify.app | Changes only arrive through a PR: CI must pass and the maintainer must approve; merging deploys automatically |

Workflow: make a change → push to `test` → check it on the staging URL → open a PR `test → main` → merge after review → production updates.

**CI** (GitHub Actions, on push / PR to `main` or `test`):
Checks the formatting of `templates/` (Prettier), builds the site with `scripts/build_site.py`, then runs `tests/test_site.py` in Chromium with Playwright (search, filters, favorites, geolocation, routes, map, machine details, share links, conquest, stats, accounts & sync, opening status, mobile layout)

**Weekly data update** (`.github/workflows/update-data.yml`): every Monday at 03:00 JST the data is re-scraped; if anything changed, a PR is opened against `test` listing new/removed arcades and game/hours changes. E2E tests run inside the job first. It can also be triggered by hand from the Actions tab. Music Game Map blocks requests from GitHub Actions, so the weekly job reuses `data/mgm_cache.csv`; refresh Taiwan Chinese names / machine details by running `--mgm` locally now and then (a failed scan automatically keeps the old cache).

**CD**: on deploy, Netlify runs `python3 scripts/build_site.py` to generate `site/` and publishes it (see `netlify.toml`). `site/` is not committed: change `templates/` to change the page, `data/` to change the data.

**Accounts setup (Firebase)** (one time; until `FIREBASE_CONFIG` in `templates/account.js` is filled in, the sign-in button is hidden):

1. [Firebase console](https://console.firebase.google.com/) → *Create a project* → pick the existing Google Cloud project (Spark / free plan)
2. *Authentication* → *Sign-in method*: enable **Email/Password** and **Google**. *Settings* → *Authorized domains*: add `maimai-japan-map.netlify.app` and `test--maimai-japan-map.netlify.app` (`localhost` is there by default)
3. *Firestore Database* → *Create database* (production mode, region e.g. `asia-east1`) → *Rules*: paste [`firestore.rules`](firestore.rules) and publish
4. *Project settings* → *Your apps* → add a **Web** app → copy `apiKey`, `authDomain`, `projectId`, `appId` into `FIREBASE_CONFIG` in `templates/account.js`
5. Google Cloud console → *Google Auth Platform* → *Audience* → **Publish app** (in *Testing* only listed test users can use Google sign-in)

The Firebase web config is public (it ships in the page) and is not a secret; access is enforced by `firestore.rules`, where each user can only read and write `users/{their uid}`; `board/{uid}` (the opt-in leaderboard) is public to read but only its owner can write it, and only a name plus counts. The Firebase SDK is loaded only when someone opens the sign-in dialog or was signed in before.

**Friend-code B50 fetching**: signed-in users enter their friend code on the 🎵 maimai page and press buttons (🤝 send friend request → ✅ I accepted → 🔄 update B50). Each press writes a job to `jobs/{uid}` (rules allow only queued jobs, at most one per 10 minutes for score fetching / 1 minute for friend requests); the `otogo_worker.py` in [maimai-dc-bot](https://github.com/KJLavender/maimai-dc-bot) runs on the bot's VM, does the job with the bot's maimai DX NET account and writes the scores back to `users/{uid}/mai/b50`. See that repo's README for setup.

Run the tests locally:

```
pip install playwright && python -m playwright install chromium
python scripts/build_site.py
cd site && python -m http.server 8765      # in another terminal
BROWSER_CHANNEL= python tests/test_site.py
```

**Formatting**: `templates/` is formatted with [Prettier](https://prettier.io) (config in `.prettierrc.json`) and CI checks it. After editing the front end, run:

```
npx prettier@3.9.10 --write templates/
```

The Service Worker cache name is a hash of the whole site, so any change automatically produces a new cache and users who installed the PWA get the new version — no manual version bump needed.

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
