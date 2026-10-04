"""用真的 Chrome 把網頁每個功能點一遍。
用法: python tests/test_site.py [url]       （預設 http://localhost:8765/index.html）
環境變數: BROWSER_CHANNEL（預設 chrome；設成空字串用 Playwright 內建 Chromium）
          SCREENSHOT_DIR（手機截圖輸出位置，預設 tests/out）"""
import os, sys, re
from urllib.parse import urlparse
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
    badges_ok = all(t in ("營業中",) or "打烊" in t for t in page.locator(".badge").all_inner_texts()[:50])
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

    check("沒有 JS 錯誤", not errors, "; ".join(errors)[:200])
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
