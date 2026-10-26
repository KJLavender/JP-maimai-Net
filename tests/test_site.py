"""用真的 Chrome 把網頁每個功能點一遍。
用法: python tests/test_site.py [url]       （預設 http://localhost:8765/index.html）
環境變數: BROWSER_CHANNEL（預設 chrome；設成空字串用 Playwright 內建 Chromium）
          SCREENSHOT_DIR（手機截圖輸出位置，預設 tests/out）"""
import json, os, sys, re, html
from collections import Counter
from urllib.parse import urlparse, unquote
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765/index.html"
results = []
SHOTS = os.environ.get("SCREENSHOT_DIR", os.path.join(os.path.dirname(__file__), "out"))
os.makedirs(SHOTS, exist_ok=True)
SITE = urlparse(URL).netloc


def check(name, cond, info="", soft=False):
    """soft=True：外部服務（如 OSM 圖磚）造成的失敗只警告，不讓 CI 掛掉。"""
    if soft and not cond:
        print("WARN " + name + (f"  [{info}]" if info else ""), flush=True); return
    results.append((bool(cond), name, info))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{info}]" if info else ""), flush=True)


def count(page):
    m = re.search(r"顯示 (\d+) / (\d+)", page.inner_text("#count"))
    return int(m.group(1)), int(m.group(2))


def chip(page, text):
    return page.locator(".chip", has_text=text).first


with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL", "chrome") or None)

    # ---------- 桌機 ----------
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="zh-TW",
                        geolocation={"latitude": 35.6595, "longitude": 139.7005},  # 渋谷
                        permissions=["geolocation"])
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and not m.text.startswith("Failed to load resource")
            and errors.append(m.text))
    page.on("response", lambda r: r.status >= 400 and urlparse(r.url).netloc == SITE
            and errors.append(f"{r.status} {r.url}"))
    page.goto(URL, wait_until="networkidle")

    shown, total = count(page)
    check("載入：全部店家都顯示", shown == total and total > 1000, f"{shown}/{total}")
    check("載入：有分縣標題", page.locator(".prefhead").count() > 40, str(page.locator(".prefhead").count()))

    # 搜尋（新字體折疊：沖繩 → 沖縄）
    page.fill("#q", "沖繩")
    n, _ = count(page)
    check("搜尋：繁體『沖繩』找得到『沖縄県』", n > 0, str(n))
    page.fill("#q", "ラウンドワン")
    n, _ = count(page)
    check("搜尋：店名", n > 10, str(n))
    page.fill("#q", "zzzz不存在")
    check("搜尋：無結果顯示空狀態", page.locator(".empty").is_visible())
    page.fill("#q", "")

    # 音遊按鈕
    chip(page, "maimai DX").click()
    n_mai, _ = count(page)
    check("篩選：maimai DX", 0 < n_mai <= total, str(n_mai))
    chip(page, "Project DIVA").click()
    n_both, _ = count(page)
    check("篩選：maimai + DIVA 是交集（更少）", n_both < n_mai, f"{n_both}<{n_mai}")
    chip(page, "Project DIVA").click()

    # 其他遊戲下拉
    sel = page.locator("#gamerow select")
    opt = sel.locator("option").nth(1)
    val = opt.get_attribute("value")
    sel.select_option(val)
    n_other, _ = count(page)
    check("其他遊戲：下拉選了會變成按鈕並篩選", n_other <= n_mai and page.locator("#gamerow .chip").count() == 5,
          f"{val} → {n_other}")

    # 清除
    chip(page, "清除篩選").click()
    n, _ = count(page)
    check("清除篩選：回到全部", n == total, str(n))

    # 營業中 / 深夜
    chip(page, "只看營業中").click()
    n_open, _ = count(page)
    badges_ok = all("營業" in t or "打烊" in t for t in page.locator(".badge").all_inner_texts()[:50])
    check("只看營業中：卡片都是營業中", badges_ok, str(n_open))
    chip(page, "只看營業中").click()
    chip(page, "營業到深夜").click()
    n_late, _ = count(page)
    check("營業到深夜", 0 < n_late < total, str(n_late))
    chip(page, "營業到深夜").click()

    # 縣市
    page.locator("#statusrow select").select_option("大阪府")
    n, _ = count(page)
    heads = page.locator(".prefhead").all_inner_texts()
    check("縣市下拉：只剩大阪", n > 0 and len(heads) == 1 and heads[0].startswith("大阪府"), f"{n} {heads[:2]}")
    page.locator("#statusrow select").select_option("")

    # 收藏
    first = page.locator(".card").first
    fname = first.locator(".cname").inner_text()
    first.locator(".star").click()
    chip(page, "收藏").click()
    n, _ = count(page)
    check("收藏：加星後收藏篩選只剩 1 間", n == 1, fname[:20])
    page.reload(wait_until="networkidle")
    chip(page, "收藏").click()
    n, _ = count(page)
    check("收藏：重新整理後還在（localStorage）", n == 1)
    page.locator(".card .star").first.click()
    n, _ = count(page)
    check("收藏：取消後即時消失", n == 0)
    chip(page, "收藏").click()

    # 附近（定位：渋谷）
    chip(page, "附近").click()
    page.wait_for_selector(".dist")
    dists = page.locator(".dist").all_inner_texts()[:5]
    km = [float(re.search(r"([\d.]+)", d).group(1)) / (1000 if " m" in d else 1) for d in dists]
    check("附近：顯示距離且由近到遠", km == sorted(km) and km[0] < 2, ", ".join(dists))
    check("附近：定位標籤出現", page.locator("#locpill").is_visible())
    chip(page, "5km").click()
    n5, _ = count(page)
    chip(page, "20km").click()
    n20, _ = count(page)
    check("半徑：5km < 20km", 0 < n5 < n20, f"{n5} < {n20}")
    page.locator("#locpill button").click()
    n, _ = count(page)
    check("清除定位：回到全部", n == total)

    # 路線
    rbtns = page.locator(".card .rtbtn")
    for i in range(3):
        rbtns.nth(i).click()
    check("路線：底部列顯示 3 站", page.locator("#routebar").is_visible()
          and "3/9" in page.inner_text("#routebar .rcount"))
    with ctx.expect_page() as pi:
        page.click("#routestart")
    url = pi.value.url
    pi.value.close()
    check("路線：開始導覽開 Google Maps 多點路線", "google.com/maps/dir" in url and "waypoints" in url, url[:90])
    page.click("#routeclear")
    check("路線：清空後底部列消失", not page.locator("#routebar").is_visible())

    # 地圖
    page.locator(".viewtoggle button", has_text="地圖").click()
    page.wait_for_selector(".mc", timeout=15000)
    check("地圖：叢集圖示出現", page.locator(".mc").count() > 0, str(page.locator(".mc").count()))
    check("地圖：圖例出現", page.locator(".legend").is_visible())
    try: page.wait_for_selector(".leaflet-tile-loaded", timeout=10000)
    except Exception: pass
    tiles = page.locator(".leaflet-tile-loaded").count()
    check("地圖：底圖圖磚載入", tiles > 0, str(tiles), soft=True)
    # 捲動後 header 要在地圖上面
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(400)
    top_el = page.evaluate("""()=>{const h=document.querySelector('header').getBoundingClientRect();
        const el=document.elementFromPoint(innerWidth/2,h.bottom-6);return !!el.closest('header')}""")
    check("地圖：捲動時 header 蓋在地圖上面（朋友回報的 bug）", top_el)
    page.mouse.wheel(0, -2000)
    # 點叢集→放大→點圓點→彈窗
    page.locator("#statusrow select").select_option("沖縄県")
    page.wait_for_timeout(800)
    for _ in range(6):
        if page.locator(".leaflet-popup").count():
            break
        mc = page.locator(".mc")
        if mc.count():
            mc.first.click(); page.wait_for_timeout(700); continue
        # 沒叢集了 → 點 canvas 上的圓點
        pt = page.evaluate("""()=>{let r=null;map.eachLayer(l=>{if(!r&&l instanceof L.CircleMarker&&map.getBounds().contains(l.getLatLng())&&l._map){
            const p=map.latLngToContainerPoint(l.getLatLng());r=[p.x,p.y];}});
            const b=document.getElementById('map').getBoundingClientRect();return r&&[r[0]+b.left,r[1]+b.top];}""")
        if pt:
            page.mouse.click(pt[0], pt[1]); page.wait_for_timeout(500)
    check("地圖：點標記會開彈窗", page.locator(".leaflet-popup .pop").count() == 1,
          page.locator(".leaflet-popup .pn").first.inner_text()[:30] if page.locator(".leaflet-popup").count() else "")
    if page.locator(".leaflet-popup .pop").count():
        color = page.locator(".leaflet-popup a.btn").first.evaluate("e=>getComputedStyle(e).color")
        check("地圖：彈窗『導航前往』文字是白色", color == "rgb(255, 255, 255)", color)
        page.locator(".leaflet-popup .rtbtn").click()
        check("地圖：彈窗內加入路線", "1/9" in page.inner_text("#routebar .rcount"))
        page.click("#routeclear")
    page.locator("#statusrow select").select_option("")
    page.locator(".viewtoggle button", has_text="清單").click()

    # XSS：使用者輸入的地名會變成標題
    page.evaluate("""()=>setOrigin(35.68,139.76,'<img src=x onerror="window.__pwned=1">','search')""")
    page.wait_for_timeout(300)
    check("安全：地名含 HTML 不會被執行", page.evaluate("()=>!window.__pwned")
          and "<img" in page.locator(".prefhead").first.inner_text())
    page.evaluate("()=>clearOrigin()")

    # 機台資訊（台灣，MGM）
    page.locator("#statusrow select").select_option("台灣")
    mach = page.locator(".card .mach")
    check("機台資訊：台灣店家有機台清單", mach.count() > 20, str(mach.count()))
    if mach.count():
        mach.first.locator("summary").click()
        check("機台資訊：點開看得到各機台", mach.first.locator("li").first.is_visible(),
              mach.first.locator("li").first.inner_text()[:40])
    page.locator("#statusrow select").select_option("")

    # 分享連結：設定篩選 → 網址帶條件 → 朋友開同一個網址看到一樣的結果
    page.locator("#statusrow select").select_option("大阪府")
    chip(page, "營業到深夜").click()
    n_mine, _ = count(page)
    shared = page.url
    check("分享：篩選條件寫進網址", "pref=" in shared and "late=1" in shared, shared[-60:])
    check("分享：有分享按鈕", chip(page, "分享").is_visible())
    friend = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
    friend.goto(shared, wait_until="networkidle")
    n_friend, _ = count(friend)
    check("分享：朋友打開看到同樣結果", n_friend == n_mine and
          friend.locator("#statusrow select").input_value() == "大阪府", f"{n_friend} vs {n_mine}")
    friend.context.close()
    chip(page, "清除篩選").click()
    check("分享：清除篩選後網址也清掉", "#" not in page.url or page.url.endswith("#"), page.url[-30:])

    # data.json
    res = page.request.get(URL.rsplit("/", 1)[0] + "/data.json")
    dj = res.json() if res.ok else {}
    check("data.json：可讀且店數正確", dj.get("count") == total and len(dj.get("shops", [])) == total,
          f"{res.status} {dj.get('count')}")
    if dj.get("shops"):
        keys = set(dj["shops"][0])
        check("data.json：欄位齊全", {"name", "hours", "games", "lat", "lng", "google_maps_url"} <= keys)

    tw = page.evaluate("""()=>{const t=DATA.filter(d=>d.p==='台灣'), g=t.filter(d=>!d.gp);
      const q=d=>decodeURIComponent(d.u).split('query=')[1]||'';
      return {n:t.length, zh:t.filter(d=>d.z||d.zg).length, pid:t.length-g.length,
        bad:g.filter(d=>d.z?!q(d).startsWith(d.z):!q(d).includes(d.a)).map(d=>d.n)}}""")
    check("台灣：店名幾乎都有中文（正式中文名，或「品牌（縣市）」）", tw["zh"] >= tw["n"] - 3, f"{tw['zh']}/{tw['n']}")
    check("台灣：大部分店家有 Google place ID（店家資訊直接開到那間店）", tw["pid"] >= tw["n"] - 6, f"{tw['pid']}/{tw['n']}")
    check("台灣：沒有 place ID 的店用中文名或「品牌＋地址」搜 Google，不用英文店名", not tw["bad"], str(tw["bad"]))

    # 🏆 制霸
    def view(name):
        page.locator(".viewtoggle button", has_text=name).click()
        page.wait_for_timeout(200)

    def stat(i):
        return page.locator("#conquest .stat .sv").nth(i).inner_text().split("/")[0].strip()

    page.locator("#statusrow select").select_option("大阪府")
    vb = page.locator(".card .vbtn").first
    vb.click()
    check("制霸：店家卡片可以標記去過", "去過" in vb.inner_text() and vb.get_attribute("data-on") == "1")
    view("制霸")
    check("制霸：去過 1 間、制霸 1 縣", stat(0) == "1" and stat(1) == "1", f"{stat(0)} / {stat(1)}")
    tile = page.locator('.ctile[data-p="大阪府"]')
    check("制霸：方格地圖有 47 都道府縣，大阪有上色", page.locator(".ctile").count() == 47
          and "on" in (tile.get_attribute("class") or "") and tile.inner_text().split("\n")[-1].startswith("1/"),
          tile.inner_text().replace("\n", " "))
    page.reload(wait_until="networkidle")
    check("制霸：重新整理後紀錄還在（localStorage）", stat(0) == "1")
    check("制霸：網址記住目前檢視", "view=conquest" in page.url)

    page.locator(".cq-region button", has_text="台灣").click()
    n_tw = page.locator(".cq-map.tw .ctile").count()
    no_c = page.evaluate("()=>DATA.filter(d=>d.p==='台灣'&&!d.c).map(d=>d.n)")
    check("制霸：可以切換到台灣縣市地圖、每間台灣店都有縣市", n_tw == 22 and not no_c, f"{n_tw} 格；沒縣市：{no_c}")
    tc = page.evaluate("""()=>{const d=DATA.find(x=>x.c==='台中市');toggleVisited(d._idx);render();
      return DATA.filter(x=>x.c==='台中市').length}""")
    tct = page.locator('.ctile[data-p="台中市"]')
    check("制霸：台灣去過的店會在縣市地圖上色", "on" in (tct.get_attribute("class") or "") and stat(2) == "1",
          tct.inner_text().replace("\n", " "))
    tct.click()
    page.wait_for_timeout(300)
    n, _ = count(page)
    check("制霸：點台灣縣市會列出那個縣市的機廳", n == tc and page.locator("#q").input_value() == "台中市", f"{n}/{tc}")
    page.evaluate("()=>toggleVisited(DATA.find(x=>x.c==='台中市')._idx)")
    page.fill("#q", "")
    page.locator("#statusrow select").select_option("")
    view("制霸")
    page.locator(".cq-region button", has_text="日本").click()

    code = page.evaluate("()=>backupCode()")
    page.evaluate("()=>{localStorage.removeItem('maimai:visited')}")
    page.reload(wait_until="networkidle")
    check("備份：清掉之後是 0", stat(0) == "0")
    page.once("dialog", lambda d: d.accept(code))
    page.locator(".cq-more summary").click()   # 備份代碼收在「不用 Google 帳號？」裡
    page.locator("#cq-restore").click()
    page.wait_for_timeout(300)
    check("備份：貼上備份代碼可以還原", stat(0) == "1", code[:20] + "…")

    page.evaluate("()=>{navigator.canShare=undefined}")   # 桌機不跳系統分享，直接下載
    with page.expect_download() as dl:
        page.locator("#cq-export").click()
    png = os.path.join(SHOTS, "conquest.png")
    dl.value.save_as(png)
    check("制霸：匯出圖片（PNG）", os.path.getsize(png) > 20000 and open(png, "rb").read(4) == b"\x89PNG",
          f"{os.path.getsize(png) // 1024} KB")
    tile.click()
    page.wait_for_timeout(300)
    check("制霸：點縣名會跳到那個縣的清單", page.locator("#statusrow select").input_value() == "大阪府"
          and page.locator("#list").is_visible())

    # 📊 統計
    view("統計")
    hist = page.evaluate("()=>CONFIG.history.filter(h=>h.jp).length")
    lines = page.locator("#st-line path").count()
    check("統計：折線圖有 5 款遊戲", lines == 5 and hist >= 2, f"{lines} 條線、{hist} 筆歷史")
    page.locator("#st-hit").hover(position={"x": 20, "y": 40})
    check("統計：滑過折線圖有數值提示", page.locator("#st-line .ctip").is_visible())
    check("統計：長條圖預設前 15 名", page.locator("#st-bar .bar").count() == 15)
    page.locator("#st-more").click()
    n_all = page.locator("#st-bar .bar").count()
    check("統計：顯示全部地區", n_all >= 47, str(n_all))
    page.locator("#st-games .chip", has_text="cherrit").click()
    n_ch = page.locator("#st-bar .bar").count()
    check("統計：切換成 cherrit 只算有 cherrit 的地區", 0 < n_ch < n_all, f"{n_ch} < {n_all}")
    page.locator("#st-table").click()
    check("統計：表格檢視", page.locator("#st-line table tr").count() == hist + 1)
    page.locator("#st-table").click()
    page.evaluate("()=>{localStorage.removeItem('maimai:visited');location.hash=''}")

    bg = lambda: page.evaluate("()=>getComputedStyle(document.body).backgroundColor")
    light = bg()
    page.locator("#themebtn").click()
    dark = bg()
    page.reload(wait_until="networkidle")
    check("外觀：預設淺色，可切換深色並記住", light == "rgb(244, 245, 250)" and dark != light and bg() == dark,
          f"{light} → {dark}")
    page.locator("#themebtn").click()
    check("外觀：CSS／JS 網址帶版本號（新版上線不會拿到舊檔）",
          page.evaluate("()=>{const a=[...document.querySelectorAll('link[href^=\"style.css\"],script[src^=\"app.js\"]')];"
                        "return a.length===2&&a.every(e=>/\\?v=\\w{8}$/.test(e.href||e.src))}"))
    check("沒有 JS 錯誤", not errors, "; ".join(errors)[:200])
    ctx.close()

    # ---------- 👤 帳號與同步（假的 Firebase，兩個瀏覽器當兩台裝置） ----------
    cloud = {}   # 假的 Firestore：{"users/<uid>": 文件}
    FAKE_FB = {
        "firebase-app.js": "export const initializeApp = c => ({ c });",
        "firebase-auth.js": r"""
const K = 'fakeUser', subs = [];
const A = { currentUser: JSON.parse(localStorage.getItem(K) || 'null') };
const set = u => { A.currentUser = u; localStorage.setItem(K, JSON.stringify(u)); subs.forEach(f => f(u)); };
const err = code => Object.assign(new Error(code), { code });
export const getAuth = () => A;
export const onAuthStateChanged = (_, f) => { subs.push(f); setTimeout(() => f(A.currentUser), 0); };
export class GoogleAuthProvider {}
export const signInWithPopup = async () => {
  set({ uid: 'g1', displayName: '測試玩家', email: 'player@example.com', photoURL: null });
  return { user: A.currentUser };
};
export const createUserWithEmailAndPassword = async (_, email, pw) => {
  if (pw.length < 6) throw err('auth/weak-password');
  set({ uid: 'e-' + email, displayName: null, email, photoURL: null });
  return { user: A.currentUser };
};
export const signInWithEmailAndPassword = async (_, email, pw) => {
  if (pw !== 'secret1') throw err('auth/invalid-credential');
  set({ uid: 'e-' + email, displayName: null, email, photoURL: null });
  return { user: A.currentUser };
};
export const updateProfile = async (u, p) => Object.assign(u, p);
export const sendPasswordResetEmail = async () => {};
export const signOut = async () => set(null);
export const deleteUser = async () => set(null);
""",
        # 寫入時帶上目前登入者，假伺服器照 firestore.rules 檢查只能寫自己的文件
        "firebase-firestore.js": r"""
const U = 'https://fake-firestore.test/';
const me = () => (JSON.parse(localStorage.getItem('fakeUser') || 'null') || {}).uid;
export const getFirestore = () => ({});
export const doc = (_, ...p) => ({ path: p.join('/') });
const call = async (path, op, body) => {
  const r = await fetch(`${U}${path}?op=${op}&uid=${encodeURIComponent(me())}`, body ? { method: 'POST', body } : {});
  if (!r.ok) throw Object.assign(new Error('permission-denied'), { code: 'permission-denied' });
  return r.json();
};
export const runTransaction = async (_, fn) => {
  let w = null;
  const out = await fn({
    get: async ref => { const d = await call(ref.path, 'get'); return { exists: () => !!d, data: () => d }; },
    set: (ref, d) => { w = [ref, d]; },
  });
  if (w) await call(w[0].path, 'set', JSON.stringify(w[1]));
  return out;
};
export const deleteDoc = ref => call(ref.path, 'delete', '{}');
export const setDoc = (ref, d) => call(ref.path, 'set', JSON.stringify(d));
export const getDoc = async ref => { const d = await call(ref.path, 'get'); return { exists: () => !!d, data: () => d }; };
export const serverTimestamp = () => Date.now();
export const collection = (_, ...p) => ({ path: p.join('/') });
export const orderBy = (by, dir) => ({ by, dir });
export const limit = n => ({ n });
export const query = (c, ...q) => Object.assign({ path: c.path }, ...q);
export const getDocs = async q => {
  const r = await call(q.path, `list&by=${q.by}&n=${q.n}`);
  return { docs: r.map(([id, d]) => ({ id, data: () => d })) };
};
""",
    }
    CORS = {"Access-Control-Allow-Origin": "*"}

    def fake_fb(route):
        route.fulfill(body=FAKE_FB[route.request.url.rsplit("/", 1)[1]], content_type="text/javascript", headers=CORS)

    def fake_fs(route):
        u = urlparse(route.request.url)
        path, q = u.path.lstrip("/"), dict(x.split("=", 1) for x in u.query.split("&"))
        own = "users/" + unquote(q["uid"])
        job = "jobs/" + unquote(q["uid"])
        bd = "board/" + unquote(q["uid"])
        # 🏅 排行榜：任何人都能讀（含列表），只能寫自己的
        if path == "board" and q["op"] == "list":
            rows = sorted(((k[6:], v) for k, v in cloud.items() if k.startswith("board/")),
                          key=lambda x: -x[1][q["by"]])[:int(q["n"])]
            return route.fulfill(body=json.dumps(rows), content_type="application/json", headers=CORS)
        if path.startswith("board/") and q["op"] == "get":
            return route.fulfill(body=json.dumps(cloud.get(path)), content_type="application/json", headers=CORS)
        if path != own and not path.startswith(own + "/") and path != job and path != bd:
            return route.fulfill(status=403, body="{}", headers=CORS)
        # firestore.rules：工作還在排隊／進行中不能再送
        if path == job and q["op"] == "set" and (cloud.get(job) or {}).get("status") in ("queued", "running"):
            return route.fulfill(status=403, body="{}", headers=CORS)
        if q["op"] == "set":
            cloud[path] = json.loads(route.request.post_data)
        elif q["op"] == "delete":
            cloud.pop(path, None)
        route.fulfill(body=json.dumps(cloud.get(path)), content_type="application/json", headers=CORS)

    def device():
        c = b.new_context(viewport={"width": 1100, "height": 900})
        c.add_init_script("window.MJM_FIREBASE={apiKey:'test',authDomain:'test',projectId:'test',appId:'test'}")
        c.route("https://www.gstatic.com/firebasejs/**", fake_fb)
        c.route("https://fake-firestore.test/**", fake_fs)
        pg = c.new_page()
        pg.goto(URL + "#view=conquest", wait_until="networkidle")
        return pg

    def cloud_on(uid="g1"):
        return sorted(k for k, (on, _) in (cloud.get("users/" + uid) or {}).get("visited", {}).items() if on)

    def synced(pg):
        pg.wait_for_function("()=>localStorage.getItem('maimai:syncAt')&&!JSON.parse(localStorage.getItem('maimai:syncDirty'))")

    def user_btn(pg):
        return pg.locator("#userbtn").inner_text().strip()

    A = device()
    ids = A.evaluate("()=>[DATA[0].i, DATA[1].i]")
    check("帳號：右上角有登入按鈕、有隱私權說明", user_btn(A).endswith("登入")
          and A.request.get(URL.rsplit("/", 1)[0] + "/privacy.html").ok, user_btn(A))
    check("帳號：沒登入過不會載入 Firebase", not A.evaluate(
        "()=>performance.getEntriesByType('resource').some(r=>r.name.includes('firebasejs'))"))
    A.evaluate("()=>toggleVisited(0)")   # 登入前就有的紀錄
    A.locator("#userbtn").click()
    check("帳號：登入視窗有 Google 登入與 Email 登入／註冊", A.locator("#login[open] #lg-google").is_visible()
          and A.locator("#lg-email").is_visible() and A.locator(".dlg-tabs button").count() == 2)
    A.locator("#lg-google").click()
    synced(A)
    check("帳號：Google 登入後右上角顯示名字", user_btn(A).endswith("測試玩家") and not A.locator("#login").is_visible(),
          user_btn(A))
    check("同步：登入前的紀錄會上傳到帳號", cloud_on() == [ids[0]], str(cloud_on()))
    A.evaluate("()=>saveMaiCloud({v:1,at:5,name:'雲端玩家',rating:1,scores:[],new:null})")
    check("B50：登入中成績會另存到帳號", "雲端玩家" in (cloud.get("users/g1/mai/b50") or {}).get("data", ""))
    B = device()
    B.evaluate("()=>toggleVisited(1)")
    B.locator("#sync-login").click()   # 制霸頁的登入按鈕
    B.locator("#lg-google").click()
    synced(B)
    b_has = B.evaluate("()=>[...state.visited].sort()")
    check("同步：裝置 B 登入後兩台的紀錄合併", b_has == sorted(ids) and cloud_on() == sorted(ids),
          f"B={len(b_has)} 雲端={len(cloud_on())}")
    B.wait_for_function("()=>localStorage.getItem('maimai:mai')")
    check("B50：在別台裝置登入會拿到帳號裡的成績",
          B.evaluate("()=>JSON.parse(localStorage.getItem('maimai:mai')).name") == "雲端玩家")
    A.evaluate("()=>toggleVisited(0)")   # A 取消第一間；登入中 1.5 秒後自動上傳
    A.wait_for_timeout(2500)
    check("同步：登入中修改會自動上傳（A 取消的那間雲端也取消）", ids[0] not in cloud_on(), str(cloud_on()))
    id2 = A.evaluate("""()=>{const f=window.fetch;   // 寫入雲端的途中又標記一間
      window.fetch=(u,o)=>{if(o&&o.method==='POST'&&!window._t){window._t=1;toggleVisited(2)}return f(u,o)};
      syncNow();return DATA[2].i}""")
    A.wait_for_timeout(2500)
    check("同步：寫入途中的修改不會漏掉（會再傳一次）", id2 in cloud_on()
          and A.evaluate("o=>state.visited.has(o)", id2)
          and not A.evaluate("()=>JSON.parse(localStorage.getItem('maimai:syncDirty'))"), str(cloud_on()))
    A.evaluate("()=>toggleVisited(2)")
    A.wait_for_timeout(2500)
    check("同步：平常不顯示同步按鈕（自動同步）", not A.locator("#sync-now").is_visible()
          and "自動同步" in A.locator("#sync").inner_text())
    id3 = A.evaluate("""()=>{const f=window.fetch;   // 模擬斷網
      window.fetch=(u,o)=>window._off?Promise.reject(new TypeError('offline')):f(u,o);
      window._off=1;toggleVisited(3);return DATA[3].i}""")
    A.wait_for_timeout(2500)
    check("同步：同步失敗時才出現「重試同步」", A.locator("#sync-now").is_visible())
    A.evaluate("()=>{window._off=0}")
    A.locator("#sync-now").click()
    synced(A)
    check("同步：按重試後上傳成功、重試按鈕消失", id3 in cloud_on() and not A.locator("#sync-now").is_visible())
    A.evaluate("()=>toggleVisited(3)")
    A.wait_for_timeout(2500)
    B.reload(wait_until="networkidle")
    check("帳號：重新整理後維持登入", user_btn(B).endswith("測試玩家"), user_btn(B))
    B.wait_for_timeout(800)
    check("同步：重開網頁自動拉到別台裝置的變更", B.evaluate("()=>[...state.visited]") == [ids[1]])
    B.locator("#userbtn").click()
    me = B.locator("#me[open]")
    check("帳號：個人選單有名字、Email、去過數", me.is_visible() and "測試玩家" in me.inner_text()
          and "player@example.com" in me.inner_text() and me.locator(".me-stats b").first.inner_text() == "1",
          me.inner_text().replace("\n", " ")[:80])
    B.locator("#me-out").click()
    B.wait_for_timeout(300)
    check("帳號：登出後回到「登入」、這台裝置的紀錄清空、雲端還在",
          user_btn(B).endswith("登入") and B.evaluate("()=>state.visited.size") == 0 and cloud_on() == [ids[1]]
          and not B.evaluate("()=>localStorage.getItem('maimai:mai')"))
    A.context.close()
    B.context.close()

    C = device()
    C.locator("#userbtn").click()
    C.locator(".dlg-tabs button", has_text="註冊").click()
    check("註冊：註冊模式有暱稱欄、沒有「忘記密碼」", C.locator("#lg-name").is_visible()
          and not C.locator("#lg-reset").is_visible())
    C.fill("#lg-name", "小明")
    C.fill("#lg-email", "ming@example.com")
    C.fill("#lg-pw", "123")
    C.locator("#lg-submit").click()
    C.wait_for_timeout(300)
    check("註冊：密碼太短會提示", "6 個字元" in C.locator("#lg-err").inner_text(), C.locator("#lg-err").inner_text())
    C.fill("#lg-pw", "secret1")
    C.locator("#lg-submit").click()
    synced(C)
    check("註冊：Email 註冊後右上角顯示暱稱", user_btn(C).endswith("小明") and "users/e-ming@example.com" in cloud,
          user_btn(C))
    C.locator("#userbtn").click()
    C.once("dialog", lambda d: d.accept())
    C.locator("#me-del").click()
    C.wait_for_timeout(300)
    check("帳號：刪除帳號會刪掉雲端紀錄", "users/e-ming@example.com" not in cloud and user_btn(C).endswith("登入"))
    C.locator("#userbtn").click()
    C.fill("#lg-email", "ming@example.com")
    C.fill("#lg-pw", "wrong")
    C.locator("#lg-submit").click()
    C.wait_for_timeout(300)
    check("登入：密碼錯誤會提示", "密碼不對" in C.locator("#lg-err").inner_text(), C.locator("#lg-err").inner_text())
    C.context.close()

    # ---------- 🏅 制霸排行榜（預設不公開；公開後任何人看得到、可以加好友） ----------
    E = device()
    E.locator("#board summary").click()
    E.wait_for_selector("#board .empty")
    check("排行榜：沒登入也能看，提示登入才能公開", E.locator("#bd-login").is_visible()
          and "還沒有人公開" in E.locator("#board").inner_text())
    E.evaluate("()=>{toggleVisited(0);toggleVisited(1)}")
    E.locator("#bd-login").click()
    E.locator("#lg-google").click()
    synced(E)
    E.wait_for_selector("#bd-on")
    check("排行榜：登入後預設不公開", not E.locator("#bd-on").is_checked() and "board/g1" not in cloud)
    E.locator("#bd-on").check()
    E.wait_for_function("()=>document.querySelector('#board .bd-row.me')")
    ent = cloud.get("board/g1") or {}
    check("排行榜：公開後上傳名字和數字（不含去過哪些店）",
          ent.get("name") == "測試玩家" and ent.get("shops") == 2
          and set(ent) == {"name", "shops", "prefs", "tw", "twAreas", "areas", "at"}
          and ent["areas"] == ent["prefs"] + ent["twAreas"], str(ent))
    E.evaluate("()=>toggleVisited(2)")
    E.wait_for_timeout(2500)
    check("排行榜：公開中標記去過會自動更新", (cloud.get("board/g1") or {}).get("shops") == 3, str(cloud.get("board/g1")))
    E.fill("#bd-name", "制霸王")
    E.locator("#bd-save").click()
    E.wait_for_function("()=>{const r=document.querySelector('#board .bd-row.me');return r&&r.innerText.includes('制霸王')}")
    check("排行榜：可以改排行榜上的名字", cloud["board/g1"]["name"] == "制霸王")
    F = device()
    F.locator("#userbtn").click()
    F.locator(".dlg-tabs button", has_text="註冊").click()
    F.fill("#lg-email", "f@example.com")
    F.fill("#lg-pw", "secret1")
    F.locator("#lg-submit").click()
    synced(F)
    F.evaluate("()=>toggleVisited(5)")
    F.locator("#board summary").click()
    F.wait_for_selector("#board .bd-row")
    rows = F.locator("#board .bd-row").all_inner_texts()
    check("排行榜：全站看得到別人公開的進度，自己沒公開就不在上面",
          len(rows) == 1 and "制霸王" in rows[0] and "3 間" in rows[0], str(rows))
    F.locator("#bd-on").check()
    F.wait_for_function("()=>document.querySelectorAll('#board .bd-row').length===2")
    rows = F.locator("#board .bd-row").all_inner_texts()
    check("排行榜：依間數排名", "制霸王" in rows[0] and "（你）" in rows[1], str(rows))
    F.locator("[data-bs='areas']").click()
    F.wait_for_function("()=>{const b=document.querySelector('#board .bd-row .b50-score b');return b&&b.innerText.includes('縣市')}")
    check("排行榜：可以改依縣市數排", F.locator("#board .bd-row").count() == 2)
    F.goto(URL + "#cqf=g1")
    F.wait_for_function("()=>state.view==='conquest'&&document.querySelectorAll('#board .bd-row').length===2")
    check("排行榜：點好友連結會加好友並切到好友排行",
          F.evaluate("()=>JSON.parse(localStorage.getItem('maimai:cqFriends'))") == ["g1"]
          and F.locator("[data-bt='friends'][data-on='1']").count() == 1, F.locator("#board").inner_text()[:120])
    F.locator(".bd-del").first.click()
    F.wait_for_function("()=>document.querySelectorAll('#board .bd-row').length===1")
    check("排行榜：可以移除好友", F.evaluate("()=>JSON.parse(localStorage.getItem('maimai:cqFriends'))") == [])
    E.locator("#bd-on").uncheck()
    E.wait_for_timeout(500)
    check("排行榜：取消公開會從排行榜移除", "board/g1" not in cloud)
    F.locator("#userbtn").click()
    F.once("dialog", lambda d: d.accept())
    F.locator("#me-del").click()
    F.wait_for_timeout(300)
    check("排行榜：刪除帳號也會刪掉排行榜上的進度", not any(k.startswith("board/") for k in cloud), str(list(cloud)))
    E.context.close()
    F.context.close()

    # ---------- 🤝 好友代碼代抓（用 Python 假裝 mai-bot 的 otogo_worker.py） ----------
    D = device()
    D.evaluate("()=>{location.hash='view=b50'}")
    D.wait_for_selector("#mai-friend", timeout=5000)
    check("代抓：沒登入時提示登入", D.locator("#mai-friend #mf-login").is_visible())
    D.locator("#mf-login").click()
    D.locator("#lg-google").click()
    synced(D)
    D.wait_for_timeout(500)   # 等帳號裡的成績載完、畫面重畫好
    D.wait_for_selector("#mf-code")
    D.fill("#mf-code", "1234")
    D.locator("#mf-friend").click()
    check("代抓：好友代碼不是 13 位會提示", "13 位" in D.locator("#toast").inner_text() and "jobs/g1" not in cloud)
    D.fill("#mf-code", "1234-5678-90123")
    D.locator("#mf-friend").click()
    D.wait_for_selector("#mai-friend .busy")
    j = cloud.get("jobs/g1") or {}
    check("代抓：送出好友申請（工作寫到 jobs/{uid}）", j.get("type") == "friend" and j.get("code") == "1234567890123"
          and j.get("status") == "queued", str(j))
    D.evaluate("()=>sendJob('b50','1234567890123')")
    D.wait_for_timeout(300)
    check("代抓：工作還在排隊時不能再送", "太快" in D.locator("#toast").inner_text())
    cloud["jobs/g1"] = {**j, "status": "sent", "msg": "已送出好友申請，請到 maimai DX NET 接受「音GO」",
                         "at": j["at"] - 120000}
    D.wait_for_selector("#mf-b50:not([disabled])", timeout=8000)
    check("代抓：申請送出後顯示「我接受了」按鈕與說明", "我接受了" in D.locator("#mf-b50").inner_text()
          and "接受「音GO」" in D.locator("#mai-friend").inner_text())
    D.locator("#mf-b50").click()
    D.wait_for_selector("#mai-friend .busy")
    j = cloud.get("jobs/g1") or {}
    check("代抓：按下後送出抓成績的工作", j.get("type") == "b50" and j.get("status") == "queued", str(j))
    now = D.evaluate("()=>Date.now()")
    cloud["users/g1/mai/b50"] = {"at": now, "data": json.dumps({
        "v": 1, "at": now, "name": "好友代抓", "rating": 13000, "scores": [], "new": [], "src": "friend",
        "hist": [[now, 13000]]})}
    cloud["jobs/g1"] = {**j, "status": "done", "msg": "已更新"}
    D.wait_for_function("()=>(document.querySelector('#b50 .b50-name')||{}).textContent==='好友代抓'", timeout=8000)
    check("代抓：做完會自動拿到成績、標明是代抓的", "代抓" in D.locator("#b50").inner_text()
          and D.evaluate("()=>JSON.parse(localStorage.getItem('maimai:mai')).src") == "friend")
    D.wait_for_selector("#mf-b50")
    check("代抓：剛更新完「更新 B50」要等冷卻時間", "更新 B50" in D.locator("#mf-b50").inner_text()
          and D.locator("#mf-b50").is_disabled() and "分鐘後" in D.locator("#mai-friend").inner_text())
    D.context.close()

    # ---------- 🎵 B50（假的 maimai DX NET，跑真的書籤工具） ----------
    songs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "songs.json"),
                           encoding="utf-8"))

    def view_of(sh, intl=True):   # [等級, 定數, 估計, 版本]；國際版有不同數值時用國際版
        return sh[9] if intl and sh[9] else [sh[2], sh[3], sh[4], sh[8]]

    # 和 mai.js 一樣轉成 B50 用的舊格式：[歌名, 種類, 版本, 封面, [5 定數], 估計遮罩]
    legacy = []
    for s in songs["songs"]:
        for t, kind in ((0, "dx"), (1, "std")):
            own = [sh for sh in s[10] if sh[0] == t and isinstance(sh[1], int)]
            if not own:
                continue
            consts, est = [None] * 5, 0
            for sh in own:
                v = view_of(sh)
                consts[sh[1]] = v[1]
                est |= v[2] << sh[1]
            legacy.append([s[0], kind, songs["vers"][view_of(own[0])[3]][0], s[6], consts, est])
    keys = Counter((s[0], s[1]) for s in legacy)
    ok = [s for s in legacy if s[4][3] and not s[5] & 8 and keys[(s[0], s[1])] == 1]
    new_s = next(s for s in ok if s[2] in songs["new"])
    old_s = [s for s in ok if s[2] not in songs["new"]][:2]
    plays = [(old_s[0], 100.6, "ap"), (old_s[1], 99.2, ""), (new_s, 100.1, "fc")]

    def ra(c, a, fc):   # 與 mai-bot chart_rating 相同的整數算法
        k = next(k for t, k in [(100.5, 22.4), (100, 21.6), (99.5, 21.1), (99, 20.8), (98, 20.3), (97, 20),
                                (94, 16.8), (90, 15.2), (80, 13.6), (0, 12)] if a >= t)
        return (round(c * 10) * round(min(a, 100.5) * 10000) * round(k * 10)) // 10**8 \
            + (1 if fc.startswith("ap") else 0)
    want = sum(ra(s[4][3], a, fc) for s, a, fc in plays)

    def mai_html(rows):
        out = ""
        for s, a, fc in rows:
            icons = "".join(f'<img src="https://maimaidx-eng.com/maimai-mobile/img/music_icon_{i}.png">'
                            for i in [fc, "back"] if i)
            score = f'<div class="music_score_block w_112">{a:.4f}%</div>' if a else ""
            kind = "music_dx" if s[1] == "dx" else "music_standard"
            out += (f'<div class="w_450 m_15 p_r f_0"><div class="music_master_score_back pointer">{icons}'
                    f'<div class="music_name_block t_l">{html.escape(s[0])}</div>{score}</div>'
                    f'<img src="https://maimaidx-eng.com/maimai-mobile/img/{kind}.png" class="music_kind_icon"></div>')
        return out

    def fake_mai(route):
        u = urlparse(route.request.url)
        q = dict(x.split("=", 1) for x in u.query.split("&") if "=" in x)
        if u.path.endswith("/home/"):
            body = '<div class="name_block">ＴＥＳＴＥＲ</div><div class="rating_block">12345</div>'
        elif "musicGenre" in u.path:   # 只有 MASTER 有成績；另放一首沒打過的
            body = mai_html(plays + [(ok[-1], 0, "")]) if q.get("diff") == "3" else ""
        elif "musicVersion" in u.path:
            body = (mai_html([(new_s, 0, "")]) if q.get("version") == "30" else "" if q else
                    '<select name="version"><option value="29">A</option><option value="30">B</option></select>')
        else:
            body = ""
        route.fulfill(body=f"<html><body>{body}</body></html>", content_type="text/html")

    site = URL.rsplit("/", 1)[0]
    bm_src = b.new_context().request.get(site + "/bookmarklet.js").text()
    ctx = b.new_context(viewport={"width": 1100, "height": 900})
    ctx.route("https://maimaidx-eng.com/**", fake_mai)
    page = ctx.new_page()
    page.goto(site + "/index.html#view=b50", wait_until="networkidle")
    check("B50：還沒成績時顯示書籤工具教學", page.locator("#b50 .b50-guide[open]").is_visible()
          and (page.locator("#b50 .b50-bm").get_attribute("href") or "").startswith("javascript:"))
    page.add_script_tag(content=bm_src)
    page.wait_for_timeout(300)
    check("B50：在其他網站按書籤會提示要先開 maimai DX NET", "maimai DX NET" in page.inner_text("body"))
    page.goto("https://maimaidx-eng.com/maimai-mobile/home/")
    page.evaluate("s=>{window.OTOGO_SITE=s}", site)
    page.once("dialog", lambda d: d.accept())   # 音GO 問要不要匯入
    with page.expect_navigation(url=lambda u: u.startswith(site)):
        page.add_script_tag(content=bm_src)
    page.wait_for_selector("#b50 .b50-total")
    total = page.locator("#b50 .b50-total b").inner_text()
    check("B50：書籤工具讀完成績會帶回音GO", page.locator("#b50 .b50-name").inner_text() == "ＴＥＳＴＥＲ"
          and "mai=" not in page.url, page.url[-40:])
    check("B50：新曲、舊曲分開算（新曲以官網版本頁為準）", page.locator("#b50 .b50-row").count() == 3
          and "1 首" in page.locator(".b50-h").first.inner_text())
    check("B50：Rating 算法正確（含 AP +1）", total == str(want), f"{total} vs {want}")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#b50 .b50-total")
    check("B50：重新整理後成績還在", page.locator("#b50 .b50-total b").inner_text() == str(want))
    check("B50：匯入時記一筆 Rating 紀錄",
          page.evaluate("()=>JSON.parse(localStorage.getItem('maimai:mai')).hist.map(x=>x[1])") == [12345])

    # ---------- 🎵 maimai 工具（按鈕） ----------
    page.locator(".mai-modes .chip", has_text="推分建議").click()
    up = page.locator("#b50 .b50-row")
    check("推分：列出差一點就升級的譜面（AP 滿分的不列）", up.count() == 2, str(up.count()))
    page.locator(".mai-modes .chip", has_text="Rating 紀錄").click()
    check("Rating 紀錄：顯示官網 Rating", "12345" in page.locator(".mai-log").inner_text())
    page.locator(".mai-modes .chip", has_text="B50").click()
    page.locator("#b50 .b50-row").first.click()
    dlg = page.locator("#chart[open]")
    check("點 B50 的譜面：各評級 Rating＋自己的成績", dlg.is_visible() and "SSS+" in dlg.inner_text()
          and "你的成績" in dlg.inner_text())
    dlg.locator(".dlg-x").click()

    # ---------- 📚 曲庫（參考 arcade-songs） ----------
    def lvv(l):
        m = re.match(r"\d+", l)
        return int(m.group()) + (0.6 if "+" in l else 0) if m else None

    def count_where(lv=None, bit=2):
        return sum(1 for s in songs["songs"] for sh in s[10] if sh[7] & bit
                   and (lv is None or lvv(view_of(sh, bit == 2)[0]) == lvv(lv)))

    def shown_count():
        return int(re.search(r"符合 (\d+) 個譜面", page.locator("#mai-res .count").inner_text()).group(1))

    def nums(sel):   # 列表右邊的定數；宴譜面顯示等級（例：14+?）
        return [float(x.lstrip("≈")) if re.fullmatch(r"≈?\d+\.\d", x) else lvv(x)
                for x in page.locator(sel).all_inner_texts()]

    page.locator(".mai-tabs button", has_text="曲庫").click()
    page.wait_for_selector("#mai-res .mai-lrow")
    check("曲庫：預設列出國際版全部譜面", shown_count() == count_where(), f"{shown_count()} vs {count_where()}")
    check("maimai 頁：不顯示找店的搜尋與篩選", not page.locator("#q").is_visible()
          and not page.locator("#gamerow").is_visible())
    page.wait_for_function("()=>{const i=document.querySelector('#mai-res .b50-cover');return i&&i.complete}")
    cover = page.evaluate("()=>{const i=document.querySelector('#mai-res .b50-cover');return [i.getAttribute('src'),i.naturalWidth]}")
    check("曲庫：封面從本站讀（來源關了也還在）", cover[0].startswith("covers/") and cover[1] > 0, str(cover))
    # 找一首國際版有 DX MASTER、歌名是日文的歌，用羅馬拼音搜
    si, mi = next((i, j) for i, s in enumerate(songs["songs"]) if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", s[0])
                  and len(s[7]) >= 8 for j, sh in enumerate(s[10]) if sh[0] == 0 and sh[1] == 3 and sh[7] & 2)
    page.fill("#mai-q", songs["songs"][si][7])
    check("曲庫：羅馬拼音找得到日文歌名", songs["songs"][si][0] in page.locator("#mai-res").inner_text(),
          songs["songs"][si][7])
    page.locator(f'#mai-res .mai-lrow[data-s="{si}"][data-i="{mi}"]').click()
    dlg = page.locator("#chart[open]")
    sss = dlg.locator(".mai-rt tr", has_text="SSS+").inner_text()
    c_master = view_of(songs["songs"][si][10][mi])[1]
    check("曲庫：點譜面看各評級 Rating（SSS+ 正確）、譜師與物量", str(ra(c_master, 100.5, "")) in sss
          and "TAP" in dlg.inner_text(), sss)
    dlg.locator(".dlg-x").click()
    page.fill("#mai-q", "")

    page.locator("#mai-filter summary").click()
    page.select_option('select[data-f="lvMin"]', "1")
    page.select_option('select[data-f="lvMax"]', "1")
    check("曲庫：低等級也查得到（Lv 1）", shown_count() == count_where("1") > 0, str(shown_count()))
    page.select_option('select[data-f="lvMin"]', "13")
    page.select_option('select[data-f="lvMax"]', "")
    check("曲庫：等級只選一邊就只看那一級", shown_count() == count_where("13"), f"{shown_count()} vs {count_where('13')}")
    page.select_option('select[data-f="lvMin"]', "")
    vi = next(i for i, v in enumerate(songs["vers"]) if v[0] == "CiRCLE")
    page.select_option('select[data-f="verMin"]', str(vi))
    want_v = sum(1 for s in songs["songs"] for sh in s[10] if sh[7] & 2 and view_of(sh)[3] == vi)
    check("曲庫：版本只選一邊就只看那個版本", shown_count() == want_v, f"{shown_count()} vs {want_v}")
    page.select_option('select[data-f="verMin"]', "")
    page.fill('input[data-f="cMax"]', "13.7")
    want_c = sum(1 for s in songs["songs"] for sh in s[10] if sh[7] & 2 and round((view_of(sh)[1] or 0) * 10) == 137)
    check("曲庫：定數只填一個就只看那個定數", shown_count() == want_c, f"{shown_count()} vs {want_c}")
    page.fill('input[data-f="cMax"]', "")
    page.fill("#mai-q", "zzz")
    page.locator("#mai-reset").click()
    check("曲庫：重設篩選會一起清掉搜尋字", page.locator("#mai-q").input_value() == ""
          and shown_count() == count_where(), str(shown_count()))
    page.select_option('select[data-f="lvMin"]', "14+")
    page.select_option('select[data-f="lvMax"]', "14+")
    consts = nums("#mai-res .b50-score b")
    check("曲庫：等級 14+ 只列 14.6～14.9、定數高到低", shown_count() == count_where("14+")
          and all(14.6 <= c <= 14.9 for c in consts) and consts == sorted(consts, reverse=True),
          f"{shown_count()} vs {count_where('14+')} {consts[:5]}")
    page.select_option('select[data-f="lvMax"]', "15")
    heads = [h.split(" ")[1] for h in page.locator("#mai-res .mai-lvh").all_inner_texts()]
    want_heads = [l for l in ("15", "14+") if count_where(l)]
    check("定數表：依等級分段（高的在前）", heads[:len(want_heads)] == want_heads, str(heads))
    page.select_option('select[data-f="lvMax"]', "14+")
    page.locator("#mai-filter [data-r='region'][data-v='jp']").click()
    check("曲庫：切換日版用日版的等級／收錄", shown_count() == count_where("14+", 1)
          and "日版" in page.locator("#mai-res .count").inner_text(), f"{shown_count()} vs {count_where('14+', 1)}")
    page.locator("#mai-filter [data-r='region'][data-v='intl']").click()

    page.locator(".mai-views button", has_text="統計").click()
    check("曲庫：統計檢視合計和篩選結果一致",
          page.locator(".mai-sum tr").last.locator("td").last.inner_text() == str(count_where("14+")))
    page.locator(".mai-views button", has_text="歌曲").click()
    n_songs = len({i for i, s in enumerate(songs["songs"]) for sh in s[10]
                   if sh[7] & 2 and lvv(view_of(sh)[0]) == 14.6})
    check("歌曲檢視：一首歌一張卡、列出各難度定數", page.locator(".mai-song").count() == min(n_songs, 30)
          and page.locator(".mai-song").first.locator(".mai-sheet").count() >= 4
          and page.locator(".mai-song").first.locator(".mai-sheet:not(.dim)").count() >= 1,
          f"{page.locator('.mai-song').count()} vs {n_songs}")
    page.locator(".mai-song-t").first.click()
    song = page.locator("#song[open]")
    check("曲庫：點歌曲看所有譜面（譜師、物量）", song.is_visible() and song.locator(".mai-sheets-t tr").count() > 2)
    song.locator("#song-fav").click()
    check("我的清單：加入後按鈕變「已在」", "已在" in song.locator("#song-fav").inner_text())
    song.locator(".dlg-x").click()
    page.locator("#mai-filter [data-b='mine']").click()
    check("我的清單：只看清單裡的歌", page.locator(".mai-song").count() == 1)
    page.locator(".mai-song .mai-sheet:not(.dim)").first.click()
    check("歌曲檢視：點難度看各評級 Rating", page.locator("#chart[open] .mai-rt").is_visible())
    page.locator("#chart .dlg-x").click()
    page.locator("#mai-filter [data-b='mine']").click()

    page.locator(".mai-views button", has_text="定數表").click()
    page.locator("#mai-draw").click()
    page.locator("#draw [data-n='draw'][data-v='3']").click()
    got = nums("#draw-res .b50-score b")
    check("抽歌：從篩選結果抽 3 首", len(got) == 3 and all(14.6 <= c <= 14.9 for c in got), str(got))
    page.locator("#draw [data-dd='diffs'][data-v='3']").click()
    diffs_txt = page.locator("#draw-res .b50-diff").all_inner_texts()
    check("抽歌：在抽歌視窗直接選難度", bool(diffs_txt) and all(t == "MASTER" for t in diffs_txt), str(diffs_txt))
    page.locator("#draw [data-dd='diffs'][data-v='3']").click()
    page.select_option("#draw-lvmin", "14")
    page.locator("#draw .dlg-x").click()
    page.wait_for_timeout(300)   # 視窗的 close 事件之後才重畫曲庫
    check("抽歌：視窗裡改的等級會同步到篩選", page.locator('select[data-f="lvMin"]').input_value() == "14",
          page.locator('select[data-f="lvMin"]').input_value())
    page.select_option('select[data-f="lvMin"]', "14+")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#mai-res .mai-lrow")
    check("曲庫：重新整理後分頁與篩選都還在", page.locator(".mai-tabs [data-on='1']").inner_text() == "📚 曲庫"
          and shown_count() == count_where("14+"))

    # ---------- 🎖️ 段位 ----------
    def course(region, kind):
        return next(c for c in songs["dan"] if c[1] == region and c[2] == kind)

    page.locator(".mai-tabs button", has_text="段位").click()
    page.wait_for_selector("#mai-body .mai-lvh")
    ci = course("intl", "dan")
    heads = page.locator("#mai-body .mai-lvh").all_inner_texts()
    check("段位：預設國際版最新的段位認定", page.locator("#dan-ver").input_value() == ci[0]
          and len(heads) == len(ci[3]) and heads[0].startswith(ci[3][0][0])
          and page.locator("#mai-body .mai-lrow").count() == sum(len(sec[2]) for sec in ci[3]),
          f"{page.locator('#dan-ver').input_value()} {len(heads)}")
    page.locator("[data-dr='region'][data-v='jp']").click()
    cj = course("jp", "dan")
    check("段位：切換日版用日版的課題曲", page.locator("#dan-ver").input_value() == cj[0], cj[0])
    page.locator("[data-dk='kind'][data-v='friend']").click()
    check("段位：友人對戰顯示對手評級", page.locator("#dan-ver").input_value() == course("jp", "friend")[0]
          and "對手" in page.locator("#mai-body .mai-extra").first.inner_text())
    page.locator("#mai-body .mai-lrow").first.click()
    check("段位：點課題曲看各評級 Rating", page.locator("#chart[open] .mai-rt").is_visible())
    page.locator("#chart .dlg-x").click()
    page.locator("[data-dr='region'][data-v='intl']").click()

    # ---------- ✈️ 日版限定 ----------
    jp_only = [(sh_, not any(sh[7] & 2 for sh in s_[10])) for s_ in songs["songs"]
               for sh_ in [[sh for sh in s_[10] if sh[0] < 2 and sh[7] & 1 and not sh[7] & 2]] if sh_]
    page.locator(".mai-tabs button", has_text="日版限定").click()
    page.wait_for_selector("#jp-lv")
    check("日版限定：列出日版有、國際版沒有的歌和譜面",
          page.locator("#mai-body .mai-song").count() == len(jp_only)
          and f"{len(jp_only)} 首歌、{sum(len(x[0]) for x in jp_only)} 個譜面" in page.locator("#mai-body .count").inner_text(),
          page.locator("#mai-body .count").inner_text())
    page.locator("[data-jk='kind'][data-v='whole']").click()
    check("日版限定：可以只看整首限定", page.locator("#mai-body .mai-song").count() == sum(1 for x in jp_only if x[1]))
    page.select_option("#jp-lv", "14")
    n14 = sum(1 for x in jp_only if x[1] and any(lvv(sh[2]) >= 14 for sh in x[0]))
    check("日版限定：可以選最低等級", page.locator("#mai-body .mai-song").count() == n14, str(n14))
    page.evaluate("()=>localStorage.removeItem('maimai:maiList')")
    page.locator("#jp-addall").click()
    added = page.evaluate("()=>JSON.parse(localStorage.getItem('maimai:maiList')||'[]')")
    check("日版限定：一鍵全部加入我的清單", len(added) == n14 and page.locator("#jp-addall").is_disabled(), str(len(added)))
    page.locator("#mai-body .jp-fav").first.click()
    check("日版限定：單首可以從清單移除", page.locator("#mai-body .jp-fav[data-on='0']").count() == 1)
    page.locator("#mai-body .mai-sheet").first.click()
    check("日版限定：點譜面看各評級 Rating", page.locator("#chart[open] .mai-rt").is_visible())
    page.locator("#chart .dlg-x").click()
    page.locator("#jp-mine").click()
    page.wait_for_selector("#mai-res .mai-song")
    check("日版限定：「看我的清單」切到曲庫、日版、只看清單",
          page.locator(".mai-tabs [data-on='1']").inner_text() == "📚 曲庫"
          and "日版" in page.locator("#mai-res .count").inner_text()
          and page.locator("#mai-res .mai-song").count() == n14 - 1,
          f"{page.locator('#mai-res .mai-song').count()} vs {n14 - 1}")
    page.evaluate("()=>{localStorage.removeItem('maimai:maiList');localStorage.removeItem('maimai:maiFilter')}")

    # ---------- 🎯 目標 Rating、🆚 和好友比 B50（造一份 300 首的成績） ----------
    big = page.evaluate("""async()=>{const S=await loadSongs(),sc=[];let i=0;
      for(const [,s] of S.idx) if(s[4][3]&&!(s[5]&8)&&i<300){sc.push([s[0],s[1],3,97+((i*37)%350)/100,i%9?'':'fc','']);i++}
      return {v:1,at:Date.now(),name:'ME',rating:14000,scores:sc,new:null,
        hist:[[Date.now()-20*864e5,13800],[Date.now(),14000]]}}""")
    page.evaluate("d=>{localStorage.setItem('maimai:mai',JSON.stringify(d));localStorage.setItem('maimai:maiTab','\"b50\"')}", big)
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#b50 .b50-total")
    total0 = int(page.locator("#b50 .b50-total b").inner_text())
    page.locator(".mai-modes .chip", has_text="目標").click()
    page.fill("#goal-t", str(total0 + 150))
    page.locator("#goal-t").dispatch_event("change")
    page.wait_for_function("t=>document.querySelector('#b50 .mf-msg').innerText.includes('目標 '+t)", arg=total0 + 150)
    msg = page.locator("#b50 .mf-msg").first.inner_text()
    n_goal = page.locator("#b50 .b50-row").count()
    # 照建議推完，重算 B50 真的有到目標
    real = page.evaluate("""t=>{const S=mai.songs,d=JSON.parse(localStorage.getItem('maimai:mai')),g=mai.goal,
      p=goalPlan(computeB50(d,S),t,g.cap,g.gap),th=Object.fromEntries(RANKS.map(r=>[r[2],r[0]]));
      for(const x of p.steps){const s=d.scores.find(y=>y[0]===x.row.title&&y[1]===x.row.kind&&y[2]===x.row.diff);s[3]=th[x.name]}
      return [p.total,computeB50(d,S).total,p.steps.map(x=>x.gap)]}""", total0 + 150)
    m = re.search(r"推這 (\d+) 首", msg)
    check("目標 Rating：列出推哪幾首能到目標", m and n_goal == int(m.group(1)) and real[0] >= total0 + 150, msg)
    check("目標 Rating：照建議推完重算真的到目標（擠掉的譜面也算進去）", real[0] == real[1], str(real[:2]))
    check("目標 Rating：由簡單到難排、差距在 1% 以內", real[2] == sorted(real[2]) and all(g <= 1 for g in real[2]),
          str(real[2][:5]))
    page.fill("#goal-t", "30000")
    page.locator("#goal-t").dispatch_event("change")
    page.wait_for_function("()=>document.querySelector('#b50 .mf-msg').innerText.includes('還差')")
    check("目標 Rating：到不了時提示放寬條件", "放寬" in page.locator("#b50 .mf-msg").first.inner_text())
    page.locator("[data-gg='99']").click()
    check("目標 Rating：放寬差距後可以推更多首", page.locator("#b50 .b50-row").count() > n_goal)

    fr = dict(big, name="FRIEND", hist=[[big["at"] - 10 * 864e5, 13900], [big["at"], 14100]],
              scores=[[t_, k, d, min(100.5, a + 0.3) if i % 2 else a - 0.5, f, s_]
                      for i, (t_, k, d, a, f, s_) in enumerate(big["scores"])])
    code = page.evaluate("async f=>vsCode(f,await loadSongs())", fr)
    page.locator(".mai-modes .chip", has_text="比較").click()
    check("比較：還沒有朋友時顯示分享按鈕和貼上欄", page.locator("#vs-share").is_visible()
          and page.locator("#vs-in").is_visible())
    page.evaluate("()=>{window._shared=null;navigator.share=undefined;navigator.clipboard.writeText=async t=>{window._shared=t}}")
    page.locator("#vs-share").click()
    page.wait_for_function("()=>window._shared")
    link = page.evaluate("()=>window._shared")
    check("比較：分享連結帶著壓縮的成績、長度可以傳", "#vs=" in link and len(link) < 12000, str(len(link)))
    page.goto(site + "/index.html#vs=" + code)
    page.wait_for_selector(".vs-t")
    t = page.locator(".vs-t").inner_text()
    hi = sum(1 for i in range(len(big["scores"])) if i % 2)
    check("比較：點朋友的連結就並排比較（Rating、B35、B15、漲幅）", "ME（你）" in t and "FRIEND" in t
          and "每天 20.0" in t and "每天 10.0" in t and "vs=" not in page.url, t.replace("\n", " ")[:120])
    body = page.inner_text("#b50")
    check("比較：列出對方比較高、你比較高、共同課題曲",
          f"FRIEND 比較高 {hi} 個譜面" in body and f"你比較高 {len(big['scores']) - hi} 個譜面" in body
          and "共同課題曲" in body and page.locator("#b50 .vs-cmp").count() > 20)
    page.locator("#b50 button.b50-row:has(.vs-cmp)").first.click()
    check("比較：點譜面看各評級 Rating", page.locator("#chart[open] .mai-rt").is_visible())
    page.locator("#chart .dlg-x").click()
    code2 = page.evaluate("async f=>vsCode(f,await loadSongs())", dict(fr, name="FRIEND2"))
    page.fill("#vs-in", "https://example.com/index.html#vs=" + code2)
    page.locator("#vs-add").click()
    page.wait_for_selector("[data-vi='1']")
    check("比較：貼上連結也能加，可以切換朋友", page.locator("[data-vi]").count() == 2
          and "FRIEND2" in page.locator(".vs-t").inner_text())
    page.fill("#vs-in", "亂打的")
    page.locator("#vs-add").click()
    page.wait_for_timeout(300)
    check("比較：格式不對會提示", "格式不對" in page.locator("#toast").inner_text())
    page.locator("#vs-del").click()
    check("比較：可以移除朋友", page.locator("[data-vi]").count() == 0
          and "FRIEND" in page.locator(".vs-t").inner_text())
    ctx.close()

    # ---------- 營業狀態（固定時鐘） ----------
    ctx = b.new_context(timezone_id="America/New_York")
    page = ctx.new_page()

    def status_at(utc, shop):
        page.clock.set_fixed_time(utc)
        page.goto(URL, wait_until="domcontentloaded")
        return page.evaluate("d=>status(d).b&&status(d).b.t", shop)

    wk = ["10:00〜22:00"] * 7
    t = status_at("2026-10-05T14:30:00Z", {"p": "東京都", "h": "24時間"})          # 日本 週一 23:30
    check("營業狀態：24 小時營業深夜不會顯示『快打烊』", t == "24 小時營業", t)
    t = status_at("2026-10-04T03:00:00Z", {"p": "東京都", "h": "10:00〜22:00", "w": [""] + wk[1:]})  # 週日 12:00
    check("營業狀態：週休日顯示『今日公休』", t == "今日公休", t)
    t = status_at("2026-10-05T16:00:00Z", {"p": "東京都", "h": "10:00〜02:00", "w": ["10:00〜02:00"] * 7})  # 週二 01:00
    check("營業狀態：前一天營業到凌晨仍算營業中", t == "還有 60 分打烊", t)
    t = status_at("2026-10-04T13:30:00Z", {"p": "台灣", "h": "11:00〜21:30",
                                           "w": ["11:00〜22:00"] + ["11:00〜21:30"] * 5 + ["11:00〜22:00"]})  # 台灣 週日 21:30
    check("營業狀態：假日用假日的時間（巨城店週日 22:00 打烊）", t == "還有 30 分打烊", t)
    ws = page.evaluate("w=>weekSummary(w)", ["11:00〜22:00"] + ["11:00〜21:30"] * 5 + ["11:00〜22:00"])
    check("營業時間：一週摘要", ws == "一–五 11:00〜21:30・六日 11:00〜22:00", ws)
    ctx.close()

    # ---------- 🗓️ 遠征行程規劃 ----------
    ctx = b.new_context(viewport={"width": 1100, "height": 900})
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle")
    sa = {"i": "a", "n": "A", "p": "東京都", "y": 35.0, "x": 139.0, "h": "10:00〜22:00"}
    sb = {"i": "b", "n": "B", "p": "東京都", "y": 35.001, "x": 139.0, "h": "13:00〜15:00"}
    sc = {"i": "c", "n": "C", "p": "東京都", "y": 35.0, "x": 139.001, "h": "10:00〜22:00",
          "w": ["10:00〜22:00", ""] + ["10:00〜22:00"] * 5}
    sd = {"i": "d", "n": "D", "p": "東京都", "y": 35.0, "x": 139.002, "h": ""}
    se = {"i": "e", "n": "E", "p": "東京都", "y": 35.5, "x": 139.5, "h": "18:00〜02:00"}

    def trip(pool, **o):
        return page.evaluate("""([pool,o])=>{const p=planTrip(pool,Object.assign({date:'2026-11-02',start:'11:00',
          end:'23:30',stay:60,stops:5,move:'train',origin:null},o));return {s:p.stops.map(x=>[x.d.i,x.play,x.leave]),u:p.unknown}}""",
                             [pool, o])
    r = trip([sa, sb, sc, sd])   # 2026-11-02 是星期一：C 週一公休
    check("行程：依營業時間排（等 B 開門、跳過週一公休的 C、沒時間的 D）",
          r["s"] == [["a", 660, 720], ["b", 780, 840]] and r["u"] == 1, str(r))
    r = trip([sa, sc], date="2026-11-03")
    check("行程：換一天（週二）C 有開就排進去", [x[0] for x in r["s"]] == ["a", "c"], str(r))
    r = trip([se], start="23:00", end="23:30")
    check("行程：末班車時間到就離開", r["s"] == [["e", 1380, 1410]], str(r))
    r = trip([se], start="23:00", end="00:30")
    check("行程：末班車過半夜也算得對", r["s"] == [["e", 1380, 1440]], str(r))
    r = trip([sa], start="21:40")
    check("行程：快打烊、待不到 30 分的店不排", r["s"] == [], str(r))
    page.evaluate("()=>{window._open=null;window.open=u=>{window._open=u}}")
    page.locator(".chip", has_text="排行程").click()
    check("行程：沒選縣市／地點時請使用者先縮小範圍", "先在上面選縣市" in page.locator("#pl-res").inner_text())
    page.locator("#plan .dlg-x").click()
    page.select_option("#statusrow select", "東京都")
    page.locator(".chip", has_text="排行程").click()
    page.fill("#pl-date", "2026-11-02")
    page.locator("#pl-date").dispatch_event("change")
    page.locator("#plan [data-k='stops'][data-v='4']").click()
    times = page.evaluate("()=>[...document.querySelectorAll('#pl-res .pl-step .b50-meta')].map(e=>e.innerText.slice(0,11))")
    check("行程：在東京都排出 4 站，時間一站接一站", page.locator("#pl-res .pl-no").count() == 4
          and times == sorted(times) and "末班車 23:30" in page.locator("#pl-res").inner_text()
          and "（一）" in page.locator("#plan").inner_text(), str(times))
    check("行程：設定會記住", page.evaluate("()=>JSON.parse(localStorage.getItem('maimai:plan')).stops") == 4)
    page.locator("#pl-apply").click()
    check("行程：套用到路線並開 Google 導航", page.evaluate("()=>state.route.length") == 4
          and "google.com/maps/dir" in (page.evaluate("()=>window._open") or "") and not page.locator("#plan").is_visible())
    page.locator(".chip", has_text="排行程").click()
    check("行程：已選路線時可以只排路線裡的店",
          page.locator("#plan [data-k='src'][data-v='route'][data-on='1']").count() == 1
          and page.locator("#pl-res .pl-no").count() == 4)
    ctx.close()

    # ---------- 手機 ----------
    ctx = b.new_context(viewport={"width": 375, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle")
    w = page.evaluate("()=>[innerWidth,document.documentElement.scrollWidth]")
    check("手機 375px：沒有橫向溢出（清單）", w[1] <= w[0], f"{w}")
    nav = page.locator("#tabs").bounding_box()
    check("手機：分頁切換在畫面底部", nav and abs(nav["y"] + nav["height"] - 740) < 2 and nav["width"] >= 374, str(nav))
    page.screenshot(path=os.path.join(SHOTS, "mobile_list.png"))
    page.locator(".viewtoggle button", has_text="地圖").click()
    page.wait_for_selector(".mc", timeout=15000)
    w = page.evaluate("()=>[innerWidth,document.documentElement.scrollWidth]")
    check("手機 375px：沒有橫向溢出（地圖）", w[1] <= w[0], f"{w}")
    page.screenshot(path=os.path.join(SHOTS, "mobile_map.png"))
    page.goto(URL + "#view=b50", wait_until="networkidle")
    page.evaluate("d=>{localStorage.setItem('maimai:mai',JSON.stringify(d));localStorage.setItem('maimai:maiTab','\"b50\"')}", big)
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#b50 .b50-total")
    wide = []
    for mode in ["目標", "比較"]:
        page.locator(".mai-modes .chip", has_text=mode).click()
        w = page.evaluate("()=>[innerWidth,document.documentElement.scrollWidth]")
        if w[1] > w[0]:
            wide.append(mode)
    page.locator(".mai-tabs button", has_text="日版限定").click()
    page.wait_for_selector("#jp-lv")
    w = page.evaluate("()=>[innerWidth,document.documentElement.scrollWidth]")
    if w[1] > w[0]:
        wide.append("日版限定")
    check("手機 375px：目標、比較、日版限定沒有橫向溢出", not wide, str(wide))
    ctx.close()
    b.close()

bad = [r for r in results if not r[0]]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
