# -*- coding: utf-8 -*-
# 「全日本音遊機廳」網頁 App 產生器。
# 功能：營業判斷+倒數、音遊按鈕(自動生成)、其他遊戲下拉、定位/距離/半徑、
#       深夜快篩、★收藏、精準導航、機廳巡り路線(多點導航)、⚡現在能玩一鍵、
#       記住偏好(localStorage)、清單/地圖雙檢視、資料更新日。
import csv, glob, os, re, json, datetime
from collections import Counter
from urllib.parse import quote

HEADER_KEYS = ["名稱","地址","都道府縣","營業時間","遊戲","郵遞區號","地圖連結","詳細連結","緯度","經度","中文名"]
RHYTHM_ORDER = [
    "maimai でらっくす", "CHUNITHM", "オンゲキ",
    "初音ミク Project DIVA Arcade Future Tone",
]
# 海外(台灣等)在官方系統裡登記的遊戲名稱跟日本不同字面，但其實是同一款遊戲，
# 篩選時應視為同一顆按鈕，否則玩家點「maimai DX」會漏掉台灣的店。
GAME_ALIAS = {
    "maimai DX International Version": "maimai でらっくす",
    "CHUNITHM International Version": "CHUNITHM",
}

def read_rows():
    src = None
    if os.path.exists("maimai_full.csv"):
        src = ["maimai_full.csv"]
    else:
        for pat in ("by_pref2/*.csv", "by_pref/*.csv"):
            fs = sorted(f for f in glob.glob(pat) if re.match(r"\d\d_", os.path.basename(f)))
            if fs:
                src = fs; break
    if not src:
        return [], ""
    print("讀取：", src[0] if len(src) == 1 else f"{len(src)} 個分縣檔")
    date = datetime.date.fromtimestamp(os.path.getmtime(src[0])).isoformat()
    rows, seen = [], set()
    for fp in src:
        with open(fp, encoding="utf-8-sig") as f:
            r = csv.reader(f); head = next(r, None) or []
            head = [h.lstrip("\ufeff").strip() for h in head]
            idx = {k: (head.index(k) if k in head else -1) for k in HEADER_KEYS}
            for row in r:
                def g(k):
                    i = idx[k]; return row[i].strip() if 0 <= i < len(row) else ""
                name, addr = g("名稱"), g("地址")
                if not name:
                    continue
                key = (name, addr)
                if key in seen:
                    continue
                seen.add(key)
                games = [GAME_ALIAS.get(x.strip(), x.strip()) for x in re.split(r"[、,]", g("遊戲")) if x.strip()]
                games = list(dict.fromkeys(games))
                zh = g("中文名")
                # 台灣店的英文名＋英文地址丟給 Google 常跑出一串結果；有中文名就只搜中文名，
                # 沒有就把「TOM'S WORLD(GIANT CITY@HSINCHU)」拆成一般字詞
                if g("都道府縣") == "台灣":
                    q = zh or re.sub(r"[()@]+", " ", name).strip()
                else:
                    q = f"{name} {addr}"
                url = g("地圖連結") or ("https://www.google.com/maps/search/?api=1&query=" + quote(q))
                m = re.search(r"sid=(\d+)", g("詳細連結"))
                rec = {"n": name, "a": addr, "p": g("都道府縣") or "其他",
                       "h": g("營業時間"), "g": games, "u": url, "d": g("詳細連結"),
                       "i": m.group(1) if m else name + "|" + addr}
                if zh and zh != name:
                    rec["z"] = zh
                try:
                    rec["y"], rec["x"] = round(float(g("緯度")), 6), round(float(g("經度")), 6)
                except ValueError:
                    pass
                rows.append(rec)
    return rows, date

rows, data_date = read_rows()
total = len(rows)
cnt = Counter(g for r in rows for g in r["g"])
rhythm = [g for g in RHYTHM_ORDER if cnt.get(g)]
others = sorted([g for g in cnt if g not in rhythm], key=lambda g: -cnt[g])
print(f"共 {total} 間；有座標 {sum(1 for r in rows if 'y' in r)}；資料日 {data_date}")
print("音遊按鈕：", "、".join(f"{g}({cnt[g]})" for g in rhythm) or "（無）")
print("其他遊戲（下拉）：", len(others), "款")

data_json = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
rhythm_json = json.dumps(rhythm, ensure_ascii=False)
others_json = json.dumps([[g, cnt[g]] for g in others], ensure_ascii=False)

HTML = r"""<!doctype html><html lang="zh-Hant"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>全日本音遊機廳</title>
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<meta name="theme-color" content="#0d0b1a"><link rel="apple-touch-icon" href="icon.svg">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<style>
:root{--bg:#0d0b1a;--surface:#171334;--surface2:#221c47;--line:#2e2760;--text:#eceaff;
 --muted:#9d96c9;--cyan:#26e0e6;--magenta:#ff3d9a;--green:#39d98a;--amber:#ffb454;--closed:#6b6690;
 --f:system-ui,"Hiragino Sans","Noto Sans CJK JP","Yu Gothic UI","Meiryo",sans-serif;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--f);line-height:1.55;
 -webkit-font-smoothing:antialiased;
 background-image:radial-gradient(1200px 400px at 10% -5%,rgba(255,61,154,.10),transparent),
   radial-gradient(1000px 400px at 100% 0,rgba(38,224,230,.08),transparent)}
a{color:inherit}
.wrap{max-width:760px;margin:0 auto;padding:0 14px 40px;transition:padding-bottom .15s}
body.has-route .wrap{padding-bottom:92px}
header{position:sticky;top:0;z-index:20;background:rgba(13,11,26,.9);backdrop-filter:blur(10px);
 border-bottom:1px solid var(--line);padding:11px 14px 9px}
.hbar{max-width:760px;margin:0 auto}
.trow{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
.eyebrow{font-size:.64rem;letter-spacing:.3em;color:var(--cyan);font-weight:700;text-transform:uppercase}
.title{font-size:1.3rem;font-weight:800;letter-spacing:-.01em;margin:0}
.title b{color:var(--magenta)}
.sub{font-size:.72rem;color:var(--muted);margin:1px 0 8px}
.qrow{display:flex;gap:7px}
#q{flex:1;min-width:0;padding:10px 13px;font-size:1rem;color:var(--text);background:var(--surface);
 border:1px solid var(--line);border-radius:11px;outline:none}
#q:focus{border-color:var(--cyan)}
.qbtn{flex:none;padding:0 13px;border-radius:11px;border:1px solid var(--line);
 background:var(--surface2);color:var(--cyan);font-size:.8rem;font-weight:700;cursor:pointer}
.hero{display:block;width:100%;margin-top:8px;padding:10px;border:none;border-radius:11px;
 background:linear-gradient(90deg,var(--magenta),#ff7ac1 55%,var(--cyan));color:#0d0b1a;
 font-size:.88rem;font-weight:800;letter-spacing:.02em;cursor:pointer}
.filters{margin-top:9px}
.frow{display:flex;gap:9px;align-items:flex-start;padding:4px 0}
.frow+.frow{border-top:1px solid rgba(46,39,96,.55)}
.flabel{flex:none;width:34px;font-size:.6rem;letter-spacing:.14em;color:var(--muted);
 text-transform:uppercase;font-weight:700;padding-top:8px}
.chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;flex:1;min-width:0}
.chip{font-size:.77rem;padding:5px 11px;border-radius:999px;border:1px solid var(--line);
 background:var(--surface);color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap}
.chip[data-on="1"]{color:#0d0b1a;font-weight:700;border-color:transparent}
.chip.g[data-on="1"]{background:var(--gc,#8f8ac0)}
.chip.g{border-color:var(--gc,#2e2760)}
.chip.tgl[data-on="1"]{background:var(--green);color:#062b1c}
.chip.late[data-on="1"]{background:var(--amber);color:#3a2600}
.chip.fav[data-on="1"]{background:#ffd24a;color:#3a2e00}
.chip.rad[data-on="1"]{background:var(--cyan);color:#04222a}
.chip.loc{background:linear-gradient(90deg,var(--magenta),#ff7ac1);color:#fff;border-color:transparent;font-weight:700}
.chip.clear{color:var(--magenta);border-color:rgba(255,61,154,.4)}
.locpill{display:none;align-items:center;gap:7px;font-size:.75rem;color:var(--cyan);
 background:rgba(38,224,230,.10);border:1px solid rgba(38,224,230,.35);border-radius:999px;padding:4px 6px 4px 11px}
.locpill b{color:var(--text);font-weight:600}
.locpill button{background:none;border:none;color:var(--muted);cursor:pointer;font-size:.9rem;line-height:1}
select{font-size:.77rem;padding:5px 9px;border-radius:999px;background:var(--surface);color:var(--muted);
 border:1px solid var(--line);outline:none;max-width:150px}
.viewtoggle{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-left:auto;flex:none}
.viewtoggle button{background:var(--surface);color:var(--muted);border:none;font-size:.77rem;padding:5px 13px;cursor:pointer}
.viewtoggle button[data-on="1"]{background:var(--magenta);color:#fff;font-weight:700}
.count{font-size:.72rem;color:var(--muted);margin:14px 2px 6px}
#map{display:none;position:relative;z-index:0;isolation:isolate;height:70vh;min-height:340px;border-radius:14px;
 overflow:hidden;margin-top:12px;border:1px solid var(--line);background:#0d0b1a}
.prefhead{font-size:.82rem;font-weight:700;color:var(--cyan);letter-spacing:.05em;
 padding:8px 2px;margin-top:6px;border-bottom:1px solid var(--line)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:13px 14px;margin:9px 0;animation:pop .35s ease both}
@keyframes pop{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion){.card{animation:none}}
.crow{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.cname{font-size:1.02rem;font-weight:700;min-width:0;overflow-wrap:anywhere}
.ename{font-size:.72rem;font-weight:400;color:var(--muted);margin-top:1px}
.star{background:none;border:none;color:#ffd24a;font-size:1.2rem;cursor:pointer;line-height:1;padding:0 2px}
.rgt{display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex:none}
.badge{font-size:.68rem;font-weight:700;padding:3px 9px;border-radius:999px;white-space:nowrap}
.badge.open{background:rgba(57,217,138,.16);color:var(--green);border:1px solid rgba(57,217,138,.4)}
.badge.soon{background:rgba(255,180,84,.18);color:var(--amber);border:1px solid rgba(255,180,84,.45)}
.badge.opensoon{background:rgba(38,224,230,.16);color:var(--cyan);border:1px solid rgba(38,224,230,.42)}
.badge.shut{background:rgba(107,102,144,.16);color:var(--closed);border:1px solid rgba(107,102,144,.4)}
.dist{font-size:.72rem;font-weight:700;color:var(--cyan);white-space:nowrap}
.hours{font-size:.82rem;color:var(--text);margin:5px 0 2px}
.hours .clk{color:var(--muted)}
.gtags{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0 2px}
.gt{font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:6px;color:#0d0b1a;background:var(--gc,#8f8ac0)}
.gt.dim{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:600}
.addr{font-size:.76rem;color:var(--muted);margin-top:7px;overflow-wrap:anywhere}
.rtbtn{display:inline-block;margin-top:9px}
.rtbtn[data-on="1"]{background:var(--magenta);color:#fff;border-color:transparent;font-weight:700}
.cfoot{display:flex;gap:8px;margin-top:11px;flex-wrap:wrap}
.btn{flex:1 1 100px;text-align:center;text-decoration:none;font-size:.82rem;font-weight:700;padding:9px;border-radius:10px;background:var(--magenta);color:#fff}
.btn.ghost{background:transparent;color:var(--muted);border:1px solid var(--line);font-weight:600}
.btn.small{padding:8px 14px;flex:none;font-size:.8rem}
.empty{text-align:center;color:var(--muted);padding:50px 20px}
.foot{text-align:center;color:var(--muted);font-size:.72rem;padding:24px 10px 8px;border-top:1px solid var(--line);margin-top:20px}
.top{display:block;text-align:center;color:var(--muted);font-size:.78rem;padding:14px;text-decoration:none}
#routebar{display:none;position:fixed;left:0;right:0;bottom:0;z-index:1500;align-items:center;gap:10px;
 background:var(--surface2);border-top:1px solid var(--line);
 padding:10px 14px calc(10px + env(safe-area-inset-bottom))}
#routebar .rcount{flex:1;font-size:.8rem;font-weight:700;color:var(--text)}
#toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:var(--surface2);color:var(--text);
 border:1px solid var(--line);border-radius:10px;padding:10px 16px;font-size:.82rem;opacity:0;transition:opacity .2s;pointer-events:none;z-index:2000;max-width:90%}
#toast.show{opacity:1}
body.has-route #toast{bottom:78px}
.pop{font-family:var(--f);min-width:210px}
.pop .pn{font-weight:700;font-size:.95rem;margin-bottom:3px}
.pop .ph{font-size:.78rem;color:var(--muted);margin:2px 0}
.pop .rtbtn{font-size:.72rem;padding:4px 9px}
.leaflet-container{font-family:var(--f);background:#0d0b1a}
.leaflet-tile-pane{filter:invert(1) hue-rotate(200deg) brightness(.9) contrast(.85) saturate(.35)}
.leaflet-popup-content{margin:11px 13px}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--surface);color:var(--text);
 border:1px solid var(--line);box-shadow:0 6px 24px rgba(0,0,0,.5)}
.leaflet-container a.btn{color:#fff}
.leaflet-container a.leaflet-popup-close-button{color:var(--muted)}
.leaflet-bar a,.leaflet-bar a:hover{background:var(--surface2);color:var(--text);border-color:var(--line)}
.leaflet-control-attribution{background:rgba(13,11,26,.75)!important;color:var(--muted)}
.leaflet-control-attribution a{color:var(--muted)}
.mc{display:flex;align-items:center;justify-content:center;border-radius:50%;
 background:rgba(255,61,154,.25);border:2px solid var(--magenta);color:#fff;font-weight:700;font-size:.75rem;
 box-shadow:0 0 0 4px rgba(255,61,154,.12)}
.mc.has-open{background:rgba(57,217,138,.22);border-color:var(--green);box-shadow:0 0 0 4px rgba(57,217,138,.12)}
.legend{display:inline-flex;gap:10px;margin-left:8px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px;vertical-align:-1px}
@media(max-width:430px){.flabel{width:28px;font-size:.55rem}.title{font-size:1.18rem}}
noscript{display:block;padding:20px;color:var(--muted)}
</style></head><body>
<header><div class="hbar">
 <div class="trow"><h1 class="title">全日本<b>音遊</b>機廳</h1><span class="eyebrow">Arcade Finder</span></div>
 <div class="sub">__TOTAL__ 間 · 營業狀態依當地時間計算</div>
 <div class="qrow">
   <input id="q" placeholder="搜尋店名、地址、縣市，或輸入地名後按「搜尋此地」" autocomplete="off">
   <button class="qbtn" id="geoq">搜尋此地</button>
 </div>
 <div class="filters">
   <div class="frow"><span class="flabel">音遊</span><span class="chips" id="gamerow"></span></div>
   <div class="frow"><span class="flabel">位置</span><span class="chips" id="locrow"></span></div>
   <div class="frow"><span class="flabel">篩選</span><span class="chips" id="statusrow"></span></div>
 </div>
</div></header>
<div class="wrap">
 <div class="count" id="count"></div>
 <div id="map"></div>
 <div id="list"></div>
 <div class="foot">資料更新：__DATE__ · 來源 ALL.Net 設置店舖檢索 · 營業狀態依當地時間即時計算（日本 UTC+9、台灣 UTC+8）</div>
 <a class="top" href="#" onclick="scrollTo(0,0);return false">▲ 回到頂端</a>
</div>
<div id="routebar">
 <span class="rcount">已選 0/9 站</span>
 <button id="routeclear" class="btn ghost small">清空</button>
 <button id="routestart" class="btn small">開始導覽</button>
</div>
<div id="toast"></div>
<noscript>此頁需要 JavaScript，請用 Chrome 或 Safari 開啟。</noscript>
<script id="data" type="application/json">__DATA__</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const DATA=JSON.parse(document.getElementById('data').textContent);
/* 日本新字体 → 台灣繁體 折疊表：搜尋時把兩邊都正規化，讓「沖繩」也能找到「沖縄」。
   來源 OpenCC JPShinjitaiCharacters（jp2t）。純搜尋用，不影響顯示。 */
const JP2T=(()=>{const P="万萬与與両兩並竝乗乘乱亂亀龜予豫争爭亘亙亜亞仏佛仮假会會伝傳体體余餘併倂価價倹儉偽僞児兒党黨円圓写寫凜凛処處剣劍剤劑剰剩励勵労勞効效勅敕勧勸勲勳区區医醫単單即卽厳嚴参參双雙収收叙敍台臺号號唖啞営營嘱囑噛嚙団團囲圍図圖国國圏圈圧壓堕墮塁壘塩鹽増增壊壞壌壤壮壯声聲壱壹売賣変變奥奧奨奬嬢孃学學宝寶実實寛寬寝寢対對寿壽専專将將尭堯尽盡届屆属屬岳嶽峡峽巌巖巣巢巻卷帯帶帰歸庁廳広廣廃廢弁辨弐貳弥彌弯彎弾彈当當径徑従從徳德徴徵応應恋戀恒恆恵惠悩惱悪惡惨慘慎愼懐懷戦戰戯戲戻戾払拂抜拔択擇担擔拝拜拠據拡擴挙擧挟挾挿插捜搜掲揭掻搔揺搖摂攝撃擊撹攪数數斉齊斎齋断斷旧舊昼晝晃晄晩晚暁曉暦曆曽曾条條来來枢樞栄榮桜櫻桝枡桟棧桧檜検檢楼樓楽樂概槪様樣槙槇権權横橫欠缺欧歐歓歡歩步歯齒歳歲歴歷残殘殴毆殻殼毎每気氣沢澤沪濾浄淨浅淺浜濱涙淚渇渴済濟渉涉渋澁渓溪温溫湾灣湿濕満滿滝瀧滞滯潜潛瀬瀨灯燈炉爐点點為爲焼燒犠犧状狀独獨狭狹猟獵献獻獣獸瓶甁画畫畳疊痩瘦痴癡発發盗盜県縣真眞研硏砕碎礼禮祢禰祷禱禄祿禅禪秘祕称稱稲稻穂穗穏穩穣穰窃竊竜龍粋粹粛肅糸絲経經絵繪継繼続續総總緑綠緒緖縁緣縄繩縦縱繊纖繍繡缶罐翻飜聴聽胆膽脚腳脱脫脳腦臓臟艶艷芦蘆芸藝茎莖萌萠蒋蔣蔵藏薫薰薬藥虚虛虫蟲蚕蠶蛍螢蛮蠻蝋蠟衛衞装裝褒襃覇霸覚覺覧覽観觀触觸訳譯証證誉譽説說読讀謡謠譲讓豊豐賛贊践踐転轉軽輕辞辭辺邊逓遞遅遲遥遙郎郞郷鄕酔醉醤醬醸釀釈釋鉄鐵鉱鑛銭錢鋳鑄錬鍊録錄鎮鎭関關閲閱闘鬥陥陷険險随隨隠隱雑雜霊靈静靜頴穎頼賴顔顏顕顯餅餠駅驛駆驅騒騷験驗髄髓髪髮鴎鷗鶏鷄鹸鹼麦麥麹麴麺麵黄黃黒黑黙默齢齡荘莊侠俠値值倶俱内內刹剎匀勻却卻厠廁呉吳呪咒嘘噓塡填姉姊姫姬庄莊彦彥悦悅戸戶掴摑晋晉曁暨査查楡榆氷冰汚污没沒涛濤溌潑猫貓産產畵畫痺痹皐皋砺礪税稅稜棱竃竈粧妝粽糉絶絕繋繫聡聰舎舍舗鋪舖鋪茘荔莱萊葱蔥蝉蟬贋贗醗醱鋭銳隣鄰駈驅鬪鬥鼈鱉";const m={};for(let i=0;i<P.length;i+=2)m[P[i]]=P[i+1];return m;})();
const foldCJK=s=>{let o='';for(const c of s)o+=JP2T[c]||c;return o;};
DATA.forEach((d,i)=>{d._idx=i;d._s=foldCJK((d.n+' '+d.a+' '+d.p+' '+(d.z||'')).toLowerCase());});
const byId={};DATA.forEach(d=>byId[d.i]=d);
const RHYTHM=__RHYTHM__, OTHERS=__OTHERS__;
const MAX_ROUTE=9;
const LS={get:(k,d)=>{try{const v=localStorage.getItem('maimai:'+k);return v?JSON.parse(v):d;}catch(_){return d;}},
 set:(k,v)=>{try{localStorage.setItem('maimai:'+k,JSON.stringify(v));}catch(_){}}};
const SHORT={'maimai でらっくす':'maimai DX','maimai DX International Version':'maimai DX Intl',
 'CHUNITHM International Version':'CHUNITHM Intl','初音ミク Project DIVA Arcade Future Tone':'Project DIVA',
 '頭文字D THE ARCADE':'頭文字D','HOUSE OF THE DEAD: SCARLET DAWN':'HOTD SD',
 'セガNET麻雀 MJ Arcade':'MJ Arcade','ALL.Net P-ras MULTI バージョン３':'P-ras MULTI 3',
 'ALL.Net P-ras MULTI':'P-ras MULTI','占いコレクション トロッテ':'トロッテ'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const gshort=n=>esc(SHORT[n]||n);
const GCOLOR=[[/maimai/,'#ff5fa2'],[/CHUNITHM/,'#ffb454'],[/オンゲキ/,'#4fa8ff'],
 [/DIVA|初音ミク/,'#4ee1b0'],[/頭文字D/,'#ff6a5a'],[/Wonderland/,'#b57cff'],[/.*/,'#8f8ac0']];
const gcolor=n=>{for(const[re,c]of GCOLOR)if(re.test(n))return c;return'#8f8ac0'};
const isRhythm=n=>RHYTHM.includes(n);

const state={q:'',games:new Set(LS.get('games',[])),openOnly:false,lateOnly:false,favOnly:false,
 pref:'',origin:LS.get('origin',null),radius:LS.get('radius',null),
 favs:new Set(LS.get('favs',[])),route:LS.get('route',[]).filter(id=>byId[id]),view:'list'};
LS.set('route',state.route);

function parseHours(s){if(!s)return null;
 if(/24/.test(s)&&/(時間|hour)/.test(s))return[[0,1440]];
 const m=s.match(/(\d{1,2}):(\d{2})\D+?(\d{1,2}):(\d{2})/);if(!m)return null;
 let st=+m[1]*60+ +m[2],en=+m[3]*60+ +m[4];if(en<=st)en+=1440;return[[st,en]];}
function localMin(off){const d=new Date();const u=d.getTime()+d.getTimezoneOffset()*6e4;
 const j=new Date(u+off*36e5);return j.getHours()*60+j.getMinutes();}
function isLate(h){const r=parseHours(h);return r?r.some(x=>x[1]>=1440):false;}
const tzOff=d=>d.p==='台灣'?8:9;
function status(d){const r=parseHours(d.h);if(!r)return{s:'unknown',b:null};
 const t=localMin(tzOff(d));let open=false,toClose=1e9;
 for(const[s,e]of r){let tt=null;if(t>=s&&t<e)tt=t;else if(t+1440>=s&&t+1440<e)tt=t+1440;
   if(tt!=null){open=true;toClose=Math.min(toClose,e-tt);}}
 if(open)return toClose<=60?{s:'open',b:{c:'soon',t:`還有 ${toClose} 分打烊`}}:{s:'open',b:{c:'open',t:'營業中'}};
 let toOpen=1e9;for(const[s,e]of r){let d=((s-t)%1440+1440)%1440;if(d>0)toOpen=Math.min(toOpen,d);}
 return toOpen<=60?{s:'closed',b:{c:'opensoon',t:`再 ${toOpen} 分開門`}}:{s:'closed',b:{c:'shut',t:'已打烊'}};}
function distKm(a,b){const R=6371,r=x=>x*Math.PI/180;const dLa=r(b.y-a.lat),dLo=r(b.x-a.lng);
 const s=Math.sin(dLa/2)**2+Math.cos(r(a.lat))*Math.cos(r(b.y))*Math.sin(dLo/2)**2;
 return 2*R*Math.asin(Math.sqrt(s));}
function fmtDist(km){return km<1?`約 ${Math.round(km*1000)} m`:`約 ${km.toFixed(1)} km`;}
function toast(m){const t=document.getElementById('toast');t.textContent=m;t.classList.add('show');
 clearTimeout(toast._t);toast._t=setTimeout(()=>t.classList.remove('show'),2800);}

function chip(cls,label,on,onclick){const el=document.createElement('span');
 el.className='chip '+cls;el.textContent=label;if(on)el.dataset.on='1';el.onclick=()=>onclick(el);return el;}

function renderGameRow(){
 const row=document.getElementById('gamerow');row.innerHTML='';
 const extra=[...state.games].filter(g=>!isRhythm(g));
 [...RHYTHM,...extra].forEach(g=>{
   const el=chip('g',gshort(g),state.games.has(g),()=>{
     state.games.has(g)?state.games.delete(g):state.games.add(g);
     LS.set('games',[...state.games]);renderGameRow();render();});
   el.style.setProperty('--gc',gcolor(g));row.appendChild(el);});
 if(OTHERS.length){
   const sel=document.createElement('select');
   sel.innerHTML='<option value="">＋ 其他遊戲…</option>'+
     OTHERS.filter(([g])=>!state.games.has(g)).map(([g,c])=>`<option value="${esc(g)}">${gshort(g)}（${c}）</option>`).join('');
   sel.onchange=()=>{if(!sel.value)return;state.games.add(sel.value);
     LS.set('games',[...state.games]);renderGameRow();render();};
   row.appendChild(sel);}
}
function renderLocRow(){
 const row=document.getElementById('locrow');row.innerHTML='';
 row.appendChild(chip('loc','📍 附近',false,()=>{
   if(!navigator.geolocation)return toast('此裝置不支援定位');toast('定位中…');
   navigator.geolocation.getCurrentPosition(p=>setOrigin(p.coords.latitude,p.coords.longitude,'我的位置','geo'),
    e=>toast('無法定位：'+(e.code===1?'請允許定位權限':e.message)),{enableHighAccuracy:true,timeout:9000});}));
 const pill=document.createElement('span');pill.className='locpill';pill.id='locpill';
 pill.innerHTML='📍 <b></b><button title="清除定位">✕</button>';
 pill.querySelector('button').onclick=clearOrigin;row.appendChild(pill);
 [5,10,20].forEach(km=>row.appendChild(chip('rad',km+'km',state.radius===km,()=>{
   if(!state.origin)return toast('先按「📍附近」或「搜尋此地」定位');
   state.radius=state.radius===km?null:km;LS.set('radius',state.radius);renderLocRow();render();})));
 refreshLocPill();
}
function renderStatusRow(){
 const row=document.getElementById('statusrow');row.innerHTML='';
 row.appendChild(chip('tgl','只看營業中',state.openOnly,()=>{state.openOnly=!state.openOnly;renderStatusRow();render();}));
 row.appendChild(chip('late','營業到深夜',state.lateOnly,()=>{state.lateOnly=!state.lateOnly;renderStatusRow();render();}));
 row.appendChild(chip('fav','★ 收藏',state.favOnly,()=>{state.favOnly=!state.favOnly;renderStatusRow();render();}));
 const prefs=[...new Set(DATA.map(d=>d.p))];
 const sel=document.createElement('select');
 sel.innerHTML='<option value="">全部縣市</option>'+prefs.map(p=>`<option${p===state.pref?' selected':''}>${esc(p)}</option>`).join('');
 sel.onchange=()=>{state.pref=sel.value;render();};row.appendChild(sel);
 const clr=chip('clear','✕ 清除篩選',false,()=>{
     state.games.clear();state.openOnly=state.lateOnly=state.favOnly=false;state.pref='';
     state.radius=null;state.q='';document.getElementById('q').value='';
     LS.set('games',[]);LS.set('radius',null);renderAllRows();render();});
 clr.id='clearf';row.appendChild(clr);
 const vt=document.createElement('div');vt.className='viewtoggle';
 vt.innerHTML=`<button data-v="list"${state.view==='list'?' data-on="1"':''}>清單</button>`+
              `<button data-v="map"${state.view==='map'?' data-on="1"':''}>地圖</button>`;
 vt.querySelectorAll('button').forEach(b=>b.onclick=()=>{state.view=b.dataset.v;renderStatusRow();render();});
 row.appendChild(vt);
}
function renderAllRows(){renderGameRow();renderLocRow();renderStatusRow();}
const locPill=()=>document.getElementById('locpill');
function refreshLocPill(){const p=locPill();if(!p)return;
 if(state.origin){p.style.display='inline-flex';p.querySelector('b').textContent=state.origin.label;}
 else p.style.display='none';}
function setOrigin(lat,lng,label,src){state.origin={lat,lng,label,src:src||'geo'};LS.set('origin',state.origin);renderLocRow();render();}
function clearOrigin(){state.origin=null;state.radius=null;LS.set('origin',null);LS.set('radius',null);renderLocRow();render();}

window.toggleFav=function(idx,el){const id=DATA[idx].i;
 if(state.favs.has(id))state.favs.delete(id);else state.favs.add(id);
 LS.set('favs',[...state.favs]);if(el)el.textContent=state.favs.has(id)?'★':'☆';
 if(state.favOnly)render();};

/* ---- 機廳巡り路線 ---- */
const inRoute=id=>state.route.includes(id);
function renderRouteBar(){
 const bar=document.getElementById('routebar');if(!bar)return;
 if(state.route.length===0){bar.style.display='none';document.body.classList.remove('has-route');return;}
 document.body.classList.add('has-route');bar.style.display='flex';
 bar.querySelector('.rcount').textContent=`已選 ${state.route.length}/${MAX_ROUTE} 站`;
}
window.toggleRoute=function(idx,el){
 const d=DATA[idx];if(!d||!('y'in d))return;
 const id=d.i,pos=state.route.indexOf(id);
 if(pos>=0){state.route.splice(pos,1);}
 else{if(state.route.length>=MAX_ROUTE){toast(`路線最多 ${MAX_ROUTE} 站（Google 路線網址上限）`);return;}
   state.route.push(id);}
 LS.set('route',state.route);
 if(el){const on=inRoute(id);el.dataset.on=on?'1':'0';el.textContent=on?'✅ 已加入路線':'🧭 加入路線';}
 renderRouteBar();};
document.getElementById('routeclear').onclick=()=>{state.route=[];LS.set('route',[]);renderRouteBar();render();};
document.getElementById('routestart').onclick=()=>{
 const stops=state.route.map(id=>byId[id]).filter(d=>d&&'y'in d);
 if(!stops.length)return toast('尚未加入任何機廳到路線');
 const dest=stops[stops.length-1],mids=stops.slice(0,-1);
 let url=`https://www.google.com/maps/dir/?api=1`;
 if(state.origin&&state.origin.src==='search')url+=`&origin=${state.origin.lat},${state.origin.lng}`;
 url+=`&destination=${dest.y},${dest.x}`;
 if(mids.length)url+=`&waypoints=${encodeURIComponent(mids.map(d=>`${d.y},${d.x}`).join('|'))}`;
 window.open(url,'_blank');};

document.getElementById('q').addEventListener('input',e=>{state.q=e.target.value.trim();render();});
document.getElementById('geoq').onclick=async()=>{const q=state.q.trim();if(!q)return toast('先在搜尋框輸入地名');
 toast('尋找「'+q+'」…');
 try{const r=await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=jp,tw&q='+encodeURIComponent(q));
  const j=await r.json();if(!j.length)return toast('找不到「'+q+'」');
  document.getElementById('q').value='';state.q='';setOrigin(+j[0].lat,+j[0].lon,q,'search');
 }catch(_){toast('定位服務連線失敗（需要網路）');}};

function match(d){
 if(state.pref&&d.p!==state.pref)return false;
 if(state.favOnly&&!state.favs.has(d.i))return false;
 if(state.q){if(!d._s.includes(foldCJK(state.q.toLowerCase())))return false;}
 for(const g of state.games)if(!d.g.includes(g))return false;
 if(state.openOnly&&status(d).s!=='open')return false;
 if(state.lateOnly&&!isLate(d.h))return false;
 return true;}
function filtered(){let rs=DATA.filter(match);
 if(state.origin){rs.forEach(d=>d._km=('y'in d)?distKm(state.origin,d):Infinity);
  if(state.radius)rs=rs.filter(d=>d._km<=state.radius);rs.sort((a,b)=>a._km-b._km);}
 return rs;}

function gtagsHTML(g){const r=g.filter(isRhythm),o=g.filter(x=>!isRhythm(x));
 return r.map(x=>`<span class="gt" style="--gc:${gcolor(x)}">${gshort(x)}</span>`).join('')
      + o.map(x=>`<span class="gt dim">${gshort(x)}</span>`).join('');}
function badgeHTML(d){const b=status(d).b;
 const dist=(state.origin&&'y'in d)?`<span class="dist">📍 ${fmtDist(d._km)}</span>`:'';
 return `<div class="rgt">${b?`<span class="badge ${b.c}">${b.t}</span>`:''}${dist}</div>`;}
function navBtns(d){
 if('y'in d){
   const nav=`https://www.google.com/maps/dir/?api=1&destination=${d.y},${d.x}`;
   return `<a class="btn" href="${nav}" target="_blank" rel="noopener">導航前往</a>`+
          `<a class="btn ghost" href="${esc(d.u)}" target="_blank" rel="noopener">店家資訊</a>`;
 }
 return `<a class="btn" href="${esc(d.u)}" target="_blank" rel="noopener">在 Google 地圖開啟</a>`;
}
function routeBtnHTML(d){if(!('y'in d))return'';
 const on=inRoute(d.i);
 return `<button class="chip rtbtn" data-on="${on?1:0}" onclick="toggleRoute(${d._idx},this)">${on?'✅ 已加入路線':'🧭 加入路線'}</button>`;}
function card(d){const star=state.favs.has(d.i)?'★':'☆';
 const ref=d.p==='台灣'?' <span class="clk">（僅供參考）</span>':'';
 const hours=d.h?`<div class="hours"><span class="clk">🕒</span> ${esc(d.h)}${ref}</div>`
   :`<div class="hours clk">🕒 官方未登記營業時間（點「店家資訊」看 Google 地圖）</div>`;
 const detail=d.d?`<a class="btn ghost" href="${esc(d.d)}" target="_blank" rel="noopener">官方詳細</a>`:'';
 return `<div class="card"><div class="crow"><div class="cname">
   <button class="star" onclick="toggleFav(${d._idx},this)">${star}</button> ${esc(d.z||d.n)}${d.z?`<div class="ename">${esc(d.n)}</div>`:''}</div>${badgeHTML(d)}</div>
  ${hours}${d.g.length?`<div class="gtags">${gtagsHTML(d.g)}</div>`:''}
  <div class="addr">${esc(d.a)}</div>
  ${routeBtnHTML(d)}
  <div class="cfoot">${navBtns(d)}${detail}</div></div>`;}
function popupHTML(d){const b=status(d).b;const star=state.favs.has(d.i)?'★':'☆';
 const nav=('y'in d)?`https://www.google.com/maps/dir/?api=1&destination=${d.y},${d.x}`:d.u;
 return `<div class="pop"><div class="pn"><button class="star" onclick="toggleFav(${d._idx},this)">${star}</button> ${esc(d.z||d.n)}</div>
  ${b?`<span class="badge ${b.c}">${b.t}</span>`:''} <span class="ph">${esc(d.h||'官方未登記營業時間')}</span>
  <div class="gtags">${gtagsHTML(d.g)}</div>
  <div style="margin-top:8px">${routeBtnHTML(d)}</div>
  <div class="cfoot"><a class="btn" href="${esc(nav)}" target="_blank" rel="noopener">導航前往</a></div></div>`;}

let map,cluster,meMarker;
function ensureMap(){if(map)return true;if(typeof L==='undefined')return false;
 map=L.map('map',{zoomControl:true,preferCanvas:true}).setView([37.5,137.5],5);
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,
   attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);
 cluster=L.markerClusterGroup({maxClusterRadius:50,chunkedLoading:true,showCoverageOnHover:false,
   iconCreateFunction:c=>{const ms=c.getAllChildMarkers(),n=ms.length,sz=n<10?30:n<50?36:44;
     return L.divIcon({html:n,iconSize:[sz,sz],className:'mc'+(ms.some(m=>m.options.open)?' has-open':'')});}});
 map.addLayer(cluster);return true;}
function renderMap(rs){const el=document.getElementById('map');
 if(!ensureMap()){el.innerHTML='<div class="empty">地圖需要網路連線，請改用「清單」。</div>';return;}
 cluster.clearLayers();const pts=rs.filter(d=>'y'in d);
 cluster.addLayers(pts.map(d=>{const open=status(d).s==='open';
   return L.circleMarker([d.y,d.x],{radius:7,weight:2,color:'#0d0b1a',fillOpacity:.95,open,
     fillColor:open?'#39d98a':'#ff3d9a'}).bindPopup(()=>popupHTML(d),{maxWidth:280});}));
 if(meMarker){map.removeLayer(meMarker);meMarker=null;}
 if(state.origin){meMarker=L.circleMarker([state.origin.lat,state.origin.lng],
   {radius:8,color:'#26e0e6',fillColor:'#26e0e6',fillOpacity:.9}).addTo(map);
   map.setView([state.origin.lat,state.origin.lng],state.radius?12:11);}
 else if(pts.length){try{map.fitBounds(L.latLngBounds(pts.map(d=>[d.y,d.x])).pad(0.08));}catch(_){}}
 setTimeout(()=>map.invalidateSize(),60);}

function render(){
 const listEl=document.getElementById('list'),mapEl=document.getElementById('map');
 const clr=document.getElementById('clearf');
 if(clr)clr.style.display=(state.games.size||state.openOnly||state.lateOnly||state.favOnly||state.pref||state.radius||state.q)?'':'none';
 const rs=filtered();
 document.getElementById('count').innerHTML=(state.origin?'依距離排序 · ':'')+
   (state.radius&&state.origin?`${state.radius}km 內 · `:'')+`顯示 ${rs.length} / ${DATA.length} 間`+
   (state.view==='map'?'<span class="legend"><span><i style="background:#39d98a"></i>營業中</span>'+
     '<span><i style="background:#ff3d9a"></i>未營業／時間未知</span></span>':'');
 if(state.view==='map'){mapEl.style.display='block';listEl.style.display='none';renderMap(rs);return;}
 mapEl.style.display='none';listEl.style.display='block';
 if(!rs.length){listEl.innerHTML='<div class="empty">沒有符合的機廳。<br>試著清掉搜尋或關掉篩選。</div>';return;}
 if(state.origin){listEl.innerHTML=`<div class="prefhead">附近機廳（離「${esc(state.origin.label)}」由近到遠）</div>`+rs.map(card).join('');}
 else{const byp={};rs.forEach(d=>(byp[d.p]=byp[d.p]||[]).push(d));
  let html='';for(const p in byp)html+=`<div class="prefhead">${esc(p)}（${byp[p].length}）</div>`+byp[p].map(card).join('');
  listEl.innerHTML=html;}
}
renderAllRows();render();renderRouteBar();
if('serviceWorker'in navigator&&location.protocol==='https:')navigator.serviceWorker.register('sw.js').catch(()=>{});
</script></body></html>"""

html_out = (HTML.replace("__TOTAL__", str(total))
                .replace("__DATE__", data_date)
                .replace("__RHYTHM__", rhythm_json)
                .replace("__OTHERS__", others_json)
                .replace("__DATA__", data_json))
os.makedirs("site", exist_ok=True)
open("site/index.html","w",encoding="utf-8").write(html_out)
open("site/manifest.webmanifest","w",encoding="utf-8").write(
 '{"name":"全日本音遊機廳","short_name":"音遊機廳","start_url":".","scope":".",'
 '"display":"standalone","background_color":"#0d0b1a","theme_color":"#0d0b1a",'
 '"icons":[{"src":"icon.svg","sizes":"any","type":"image/svg+xml","purpose":"any maskable"}]}')
open("site/icon.svg","w",encoding="utf-8").write(
 '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
 '<rect width="512" height="512" rx="120" fill="#0d0b1a"/>'
 '<circle cx="256" cy="256" r="150" fill="none" stroke="#ff3d9a" stroke-width="26"/>'
 '<circle cx="256" cy="256" r="150" fill="none" stroke="#26e0e6" stroke-width="26" '
 'stroke-dasharray="140 800" stroke-linecap="round"/><circle cx="256" cy="256" r="46" fill="#26e0e6"/></svg>')
open("site/sw.js","w",encoding="utf-8").write(
 "const C='maimai-v9';const A=['./','./index.html','./manifest.webmanifest','./icon.svg'];"
 "self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(A)))});"
 "self.addEventListener('activate',e=>{e.waitUntil(Promise.all(["
 "caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))),"
 "self.clients.claim()]))});"
 "self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(u.origin!==location.origin)return;"
 "if(e.request.mode==='navigate'||u.pathname.endsWith('index.html')||u.pathname==='/'){"
 "e.respondWith(fetch(e.request).then(r=>{const rc=r.clone();caches.open(C).then(c=>c.put(e.request,rc));return r;})"
 ".catch(()=>caches.match(e.request)));return;}"
 "e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});")
print("→ site/ 產生完成")
