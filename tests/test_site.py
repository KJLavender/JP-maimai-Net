"""用真的 Chrome 把網頁每個功能點一遍。
用法: python tests/test_site.py [url]       （預設 http://localhost:8765/index.html）
環境變數: BROWSER_CHANNEL（預設 chrome；設成空字串用 Playwright 內建 Chromium）
          SCREENSHOT_DIR（手機截圖輸出位置，預設 tests/out）"""
import json, os, sys, re
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
""",
    }
    CORS = {"Access-Control-Allow-Origin": "*"}

    def fake_fb(route):
        route.fulfill(body=FAKE_FB[route.request.url.rsplit("/", 1)[1]], content_type="text/javascript", headers=CORS)

    def fake_fs(route):
        u = urlparse(route.request.url)
        path, q = u.path.lstrip("/"), dict(x.split("=", 1) for x in u.query.split("&"))
        if path != "users/" + unquote(q["uid"]):
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
    B = device()
    B.evaluate("()=>toggleVisited(1)")
    B.locator("#sync-login").click()   # 制霸頁的登入按鈕
    B.locator("#lg-google").click()
    synced(B)
    b_has = B.evaluate("()=>[...state.visited].sort()")
    check("同步：裝置 B 登入後兩台的紀錄合併", b_has == sorted(ids) and cloud_on() == sorted(ids),
          f"B={len(b_has)} 雲端={len(cloud_on())}")
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
          user_btn(B).endswith("登入") and B.evaluate("()=>state.visited.size") == 0 and cloud_on() == [ids[1]])
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

    # ---------- 手機 ----------
    ctx = b.new_context(viewport={"width": 375, "height": 740}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto(URL, wait_until="networkidle")
    w = page.evaluate("()=>[innerWidth,document.documentElement.scrollWidth]")
    check("手機 375px：沒有橫向溢出（清單）", w[1] <= w[0], f"{w}")
    page.screenshot(path=os.path.join(SHOTS, "mobile_list.png"))
    page.locator(".viewtoggle button", has_text="地圖").click()
    page.wait_for_selector(".mc", timeout=15000)
    w = page.evaluate("()=>[innerWidth,document.documentElement.scrollWidth]")
    check("手機 375px：沒有橫向溢出（地圖）", w[1] <= w[0], f"{w}")
    page.screenshot(path=os.path.join(SHOTS, "mobile_map.png"))
    ctx.close()
    b.close()

bad = [r for r in results if not r[0]]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
sys.exit(1 if bad else 0)
