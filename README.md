# OtoGO (音GO) — Find Rhythm Game Arcades in Japan and Taiwan

**English** | [繁體中文](README.zh-TW.md)

OtoGO is a website that shows which arcades in Japan and Taiwan have rhythm games such as maimai DX, CHUNITHM, ONGEKI and Project DIVA, and whether they are open right now. The list comes from SEGA's official arcade search (ALL.Net). A script collects it and packs it into one page that works offline and can be added to a phone's home screen.

Production: <https://maimai-japan-map.netlify.app> (branch `main`)
Staging: <https://test--maimai-japan-map.netlify.app> (branch `test`)

[![CI](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml/badge.svg)](https://github.com/KJLavender/JP-maimai-Net/actions/workflows/ci.yml)

The page is in Traditional Chinese. Arcade names and addresses are shown as SEGA lists them (Japanese or English), with Chinese names added for Taiwan where we have them.

## What the site does

Arcades:

- Shows open, closing soon, opening soon or closed today, based on local time and day of the week (Japan UTC+9, Taiwan UTC+8). Arcades with different weekday and weekend hours show a weekly summary.
- Filters by game. The International Version of a game counts as the same game as the Japanese one.
- Finds arcades near you by GPS or by a place name, sorted by distance, within 5, 10 or 20 km.
- Searches by name, address, prefecture or Chinese name. Japanese and Traditional Chinese forms of a character match each other, so 沖繩 finds 沖縄.
- Has an "open late" filter and favorites (saved in your browser), and a list view and a map view.
- Builds an arcade crawl route of up to 9 stops and opens it as one multi-stop Google Maps route.
- Plans a trip: you pick a date, a start time and the last train time. It orders your route (or the current results) by that day's opening hours, estimates travel time and tells you when to leave for the last train.
- Shows machine details for Taiwan (machine count, version, coin type, queueing style, player notes) from Music Game Map.
- Puts filters in the URL, so a shared link shows the same results. Only a "search this place" location is shared, never your GPS position.

Visit tracking:

- Lets you mark an arcade as visited. A tile map of the 47 prefectures fills in as you go, and you can export it as an image. Records stay in your browser. If you sign in (Google, or email and password), they sync between devices, or you can move them with a backup code.
- Has an opt-in leaderboard (off by default). It publishes only your name and counts, and you can add friends with a friend link.
- Has a stats page: how many arcades carry each game over time (one more point per weekly update) and a ranking by prefecture.

maimai DX:

- B50: when signed in, you enter your friend code, accept the bot's friend request and press a button to fetch your scores. Or you run a bookmarklet on maimai DX NET (International) while logged in. Either way the site computes your Best 35 + New 15 with chart constants. Your SEGA password never passes through this site. Scores stay in your browser, and sync to your account if you are signed in.
- Score-push suggestions: charts close to the next rank that would raise your rating the most.
- Target rating plan: for example "push these 5 charts to reach 15000", easiest first.
- Compare with a friend through a share link. There is no server involved; the link carries your top 300 scores.
- Rating history.
- Song library, modeled on [arcade-songs](https://arcade-songs.zetaraku.dev/maimai/): search by title, artist, chart designer or romaji; filter by version, difficulty, type, level, constant, category and more; sort; draw 1 to 10 random charts. Tap a song to see its charts and a chart to see the rating at each rank.
- Japan-only songs: songs and charts that are in the Japanese version but not the International one, which you can add to "my list" before a trip.
- Dan courses and friend-battle (オトモダチ対戦) courses for every version, with your own score from B50.

## How it is built

The site is plain HTML, CSS and JavaScript with no build framework. A Python script generates it:

- `scripts/update_data.py` scrapes SEGA and writes `data/arcades.csv`.
- `scripts/build_site.py` reads `data/` and `templates/` and writes `site/`. The arcade data is inlined in `index.html`, and a `data.json` file is written next to it.
- Netlify runs `build_site.py` on every deploy and publishes `site/` (see `netlify.toml`). `site/` is not in git.

User accounts and sync use Firebase (sign-in and Firestore). Everything else runs in the browser.

## Run it locally

You need Python 3.10 or newer.

```bash
python scripts/build_site.py
cd site
python -m http.server 8765
```

Then open <http://localhost:8765/index.html>. `build_site.py` uses only the standard library.

## Update the data

```bash
pip install requests beautifulsoup4
python scripts/update_data.py --mgm
```

This is the one command for a routine update. It scrapes SEGA for Japan and Taiwan, keeps the columns SEGA does not provide (Google place ID, Chinese name, machine info) from the previous data, fills missing coordinates from GSI Japan, refreshes Music Game Map with `--mgm`, and writes a summary of changes to `data/update_summary.md`. A full run takes about 15 to 20 minutes, plus about 3 minutes for `--mgm`. `--limit 2` is a quick test that scrapes two prefectures and writes nothing.

| Script | What it does |
|---|---|
| `scripts/songs.py` | Downloads the arcade-songs dataset and slims it into `data/songs.json` (about 740 KB). Saves small cover images to `data/covers/` (about 15 MB, only new ones are downloaded). Both are committed and served by this site, so the maimai page keeps working if the source goes away. If the source is down or returns far fewer songs, the old files are kept. Needs `pip install pykakasi pyyaml` |
| `scripts/google_place_ids.py` | Looks up each arcade's Google place ID with the Places API, so store info and navigation open the exact place. Needs `GOOGLE_MAPS_API_KEY` in `.env` (never committed). Only place IDs are stored, following Google's caching rules |
| `scripts/google_hours.py` | Fills opening hours, including per-weekday hours, from Google Place Details for all Taiwan arcades and for Japanese ones with no official hours. It stays under the daily quota and the 1,000 free calls per month |
| `scripts/history.py` | Records the arcade-count snapshot for the stats page. `--backfill` rebuilds early snapshots from git history |
| `scripts/mgm_tw.py`, `scrape_*.py`, `coords_*.py` | Called by `update_data.py`. You can also run them alone for debugging (`--test`) |

Every script finds its files by itself, so you can run it from any folder.

## Weekly update, tests and deployment

Weekly data update (`.github/workflows/update-data.yml`): every Monday at 03:00 JST, GitHub Actions re-scrapes the data and runs `songs.py`. If anything changed, it runs the end-to-end tests and opens a pull request against `test` that lists new and removed arcades and game or hours changes. You can also start it by hand from the Actions tab. Music Game Map blocks GitHub Actions, so the weekly job reuses `data/mgm_cache.csv`. Run `python scripts/update_data.py --mgm` on your own computer now and then to refresh Taiwan Chinese names and machine details. If that scan fails, the old cache is kept.

CI (`.github/workflows/ci.yml`, on push and pull request to `main` or `test`): checks the formatting of `templates/` with Prettier, builds the site, and runs `tests/test_site.py` in Chromium with Playwright. The tests click through search, filters, favorites, geolocation, routes, the map, machine details, share links, visit tracking, stats, accounts and sync, opening status and the mobile layout.

Run the tests yourself:

```bash
pip install playwright && python -m playwright install chromium
python scripts/build_site.py
cd site && python -m http.server 8765      # leave this running, then in another terminal:
BROWSER_CHANNEL= python tests/test_site.py
```

`BROWSER_CHANNEL=` (empty) makes the tests use Playwright's own Chromium. Without it they look for installed Chrome.

Formatting: `templates/` follows Prettier (settings in `.prettierrc.json`) and CI checks it. After editing the front end, run:

```bash
npx prettier@3.9.10 --write templates/
```

Branches:

| Branch | URL | Rules |
|---|---|---|
| `test` | https://test--maimai-japan-map.netlify.app | Collaborators push directly. Every push deploys |
| `main` | https://maimai-japan-map.netlify.app | Changes arrive by pull request from `test`. CI must pass and the maintainer listed in `.github/CODEOWNERS` must approve. Merging deploys |

The service worker cache name is a hash of the whole site, so any change produces a new cache and people who installed the app get the new version without a manual version bump.

## Set up sign-in (Firebase)

You do this once. Until `FIREBASE_CONFIG` in `templates/account.js` is filled in, the sign-in button is hidden.

1. In the [Firebase console](https://console.firebase.google.com/), create a project (pick the existing Google Cloud project, Spark free plan).
2. Authentication, Sign-in method: turn on Email/Password and Google. Under Settings, Authorized domains, add `maimai-japan-map.netlify.app` and `test--maimai-japan-map.netlify.app` (`localhost` is there by default).
3. Firestore Database: create a database in production mode (for example region `asia-east1`). Under Rules, paste [`firestore.rules`](firestore.rules) and publish.
4. Project settings, Your apps: add a Web app. Copy `apiKey`, `authDomain`, `projectId` and `appId` into `FIREBASE_CONFIG` in `templates/account.js`.
5. In the Google Cloud console, go to Google Auth Platform, Audience, and publish the app. While it is in Testing, only listed test users can sign in with Google.

The Firebase web config ships in the page, so it is not a secret. Access is controlled by `firestore.rules`. Each user can read and write only `users/{their uid}`. `board/{uid}` (the leaderboard) is public to read, but only its owner can write it, and only a name and counts. The Firebase SDK loads only when someone opens the sign-in dialog or was signed in before.

## Fetching B50 by friend code

A signed-in user enters their friend code on the maimai page and presses three buttons in order: send friend request, I accepted, update B50. Each press writes a job to Firestore `jobs/{uid}`. The rules allow only queued jobs, at most one per 10 minutes for score fetching and one per minute for friend requests. `otogo_worker.py` from the [maimai-dc-bot](https://github.com/KJLavender/maimai-dc-bot) repo runs on the bot's server, does the job with the bot's maimai DX NET account, and writes the scores to `users/{uid}/mai/b50`. That repo's README explains how to set it up.

## Data API

The site also serves `https://maimai-japan-map.netlify.app/data.json` for bots and other programs (CORS is on). It is cached for one hour.

```json
{"updated": "2026-10-19", "count": 1104, "shops": [{
  "id": "…", "name": "ＧｉＧＯすすきの", "name_zh": "", "region": "北海道", "address": "…",
  "hours": "10:00〜23:30", "hours_week": null, "hours_source": "SEGA", "timezone": "Asia/Tokyo",
  "games": ["CHUNITHM", "maimai でらっくす", …], "lat": 43.05, "lng": 141.35,
  "google_place_id": "…", "google_maps_url": "…", "official_url": "…", "machines": [ …Taiwan only… ]
}]}
```

`hours_week` has seven entries, Sunday to Saturday, and is only present when the days differ. The values shown above are an example. The real file has `updated` and `count` set to the current data.

## Folders

```
data/         arcades.csv (all arcades), mgm_cache.csv (Music Game Map cache), songs.json and covers/ (maimai songs),
              history.json (arcade counts per update), data_date.txt
scripts/      scrapers and data processing; paths.py holds all file paths
templates/    front-end sources: index.html, style.css and one JS file per feature (app, mai, b50, vs, plan,
              conquest, board, stats, account), bookmarklet.js, sw.js and manifest for the offline app
tests/        test_site.py, the Playwright end-to-end tests
site/         generated website (not in git)
firestore.rules   access rules for the database
```

## Credits

Arcade data © SEGA. Map data © OpenStreetMap contributors. Taiwan Chinese names and machine details come from [Music Game Map](https://mgm.wind-chime.info) and are reported by players. Extra coordinates come from GSI Japan.

Opening hours use these sources, in order. Japan: SEGA official, then Google Maps. Taiwan: Google Maps, then Music Game Map, then SEGA (International listings often carry placeholder hours). Hours from Google are labelled "Google Maps". Other Taiwan sources are marked as approximate.
