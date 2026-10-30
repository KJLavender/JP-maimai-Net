/* 🆚 和好友比 B50：把自己的成績壓縮成一條分享連結（#vs=…），朋友打開就能並排比較。
   不經過伺服器：連結裡帶的是 Rating 最高的 300 個譜面＋Rating 紀錄，打開的人存在自己的瀏覽器（localStorage 'maimai:maiVs'）。
   這個檔案只定義函式，在 b50.js 之後、app.js 之前載入。 */

// app.js 一載入就會改寫網址，所以先在這裡記下來
const VS_IMPORT = new URLSearchParams(location.hash.slice(1)).get('vs');
const VS_MAX = 5; // 最多存幾個朋友

async function gzip64(s) {
  const z = new Blob([new TextEncoder().encode(s)])
    .stream()
    .pipeThrough(new CompressionStream('gzip'));
  const buf = new Uint8Array(await new Response(z).arrayBuffer());
  let bin = '';
  for (let i = 0; i < buf.length; i += 0x8000)
    bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
/* 分享內容：B50 會用到的譜面優先，最多 300 個；B15 用到的「新曲」名單也一起帶 */
async function vsCode(data, S) {
  const r = computeB50(data, S),
    rows = [...r.rows].sort((a, b) => b.ra - a.ra).slice(0, 300),
    pick = new Set(rows.map(x => x.title + '|' + x.kind + '|' + x.diff));
  const out = {
    v: 1,
    name: data.name,
    rating: data.rating,
    at: data.at,
    src: data.src,
    scores: data.scores.filter(x => pick.has(x[0] + '|' + x[1] + '|' + x[2])),
    new: data.new ? data.new.filter(k => rows.some(x => x.title + '|' + x.kind === k)) : null,
    hist: (data.hist || []).slice(-30),
  };
  return gzip64(JSON.stringify(out));
}
async function shareVs(S) {
  const data = LS.get('mai', null);
  if (!data) return;
  const url = `${location.origin}${location.pathname}#vs=${await vsCode(data, S)}`;
  if (navigator.share) {
    try {
      await navigator.share({ title: `${data.name} 的 maimai 成績 · 音GO`, url });
      return;
    } catch (_) {}
  }
  try {
    await navigator.clipboard.writeText(url);
    toast('已複製比較連結，傳給朋友就能比 B50');
  } catch (_) {
    prompt('複製這個連結傳給朋友：', url);
  }
}
async function readVs(text) {
  const m = /(?:#|&|^)vs=([\w-]+)/.exec((text || '').trim()),
    code = m ? m[1] : (text || '').trim();
  const d = JSON.parse(await gunzip64(code));
  if (!Array.isArray(d.scores) || typeof d.name !== 'string') throw 0;
  return d;
}
// 同名的朋友只留最新一份
function addVs(d) {
  const list = LS.get('maiVs', []).filter(x => x.name !== d.name);
  list.unshift(d);
  LS.set('maiVs', list.slice(0, VS_MAX));
  mai.vsIdx = 0;
}

/* Rating 漲幅：最近 30 天（不到 30 天就從第一筆算）每天漲多少 */
function growth(hist, now) {
  const h = (hist || []).filter(x => x[1]);
  if (h.length < 2) return null;
  const last = h[h.length - 1],
    since = last[0] - 30 * 864e5,
    first = h.find(x => x[0] >= since) || h[0],
    from = first === last ? h[h.length - 2] : first,
    days = Math.max((last[0] - from[0]) / 864e5, 1);
  return { diff: last[1] - from[1], days: Math.round(days), perDay: (last[1] - from[1]) / days };
}
const growthText = g =>
  g ? `${g.days} 天 ${g.diff >= 0 ? '+' : ''}${g.diff}（每天 ${g.perDay.toFixed(1)}）` : '紀錄不夠';

function vsRowHTML(x) {
  const r = x.me || x.fr,
    cell = (y, who) =>
      y
        ? `<span class="vs-${who}">${y.ach.toFixed(4)}%<small> ${rankOf(y.ach)[2]}</small></span>`
        : `<span class="vs-${who} none">沒打過</span>`;
  return `<button class="b50-row mai-chart" data-k="${esc(r.title + '|' + r.kind)}" data-d="${r.diff}">
    ${coverImg(r.img)}
    <div class="b50-info"><div class="b50-title">${esc(r.title)}</div>
      <div class="b50-meta">${diffTag(r.diff)} ${r.kind === 'dx' ? 'DX' : 'STD'} · 定數 ${constText(r.c, r.est)}</div></div>
    <div class="b50-score vs-cmp">${cell(x.me, 'me')}${cell(x.fr, 'fr')}</div>
  </button>`;
}

function vsHTML(r, data, S) {
  const list = LS.get('maiVs', []),
    i = Math.min(mai.vsIdx || 0, Math.max(list.length - 1, 0)),
    share = `<div class="cq-actions"><button class="btn small" id="vs-share">🔗 分享我的成績給朋友比較</button></div>`,
    paste = `<div class="mf-row"><input id="vs-in" class="mai-input" placeholder="貼上朋友的比較連結" autocomplete="off"><button class="btn" id="vs-add">🆚 比較</button></div>`;
  if (!list.length)
    return `<p class="cq-hint">按「分享」把比較連結傳給朋友；朋友也分享給你後，貼在下面（或直接點連結）就能並排比 B50。</p>${share}${paste}`;
  const fd = list[i],
    f = computeB50(fd, S),
    key = x => x.title + '|' + x.kind + '|' + x.diff,
    mine = new Map(r.rows.map(x => [key(x), x])),
    theirs = new Map(f.rows.map(x => [key(x), x])),
    pairs = [...new Set([...mine.keys(), ...theirs.keys()])].map(k => ({
      me: mine.get(k),
      fr: theirs.get(k),
    })),
    both = pairs.filter(x => x.me && x.fr),
    frB50 = new Set([...f.b15, ...f.b35].map(key)),
    higher = both
      .filter(x => x.fr.ach > x.me.ach)
      .sort((a, b) => b.fr.ra - b.me.ra - (a.fr.ra - a.me.ra) || b.fr.c - a.fr.c),
    lower = both
      .filter(x => x.me.ach > x.fr.ach)
      .sort((a, b) => b.me.ra - b.fr.ra - (a.me.ra - a.fr.ra) || b.me.c - a.me.c),
    common = both.filter(x => x.me.ach < 100 && x.fr.ach < 100).sort((a, b) => b.me.c - a.me.c),
    notPlayed = pairs.filter(x => !x.me && frB50.has(key(x.fr))).sort((a, b) => b.fr.ra - a.fr.ra),
    gm = growth(data.hist),
    gf = growth(fd.hist),
    win = (a, b) => (a > b ? ' class="win"' : '');
  const sec = (title, rows, hint) =>
    `<h3 class="b50-h">${title} <small>${rows.length} 個譜面</small></h3>${hint ? `<p class="cq-hint">${hint}</p>` : ''}${
      rows.length ? rows.slice(0, 15).map(vsRowHTML).join('') : '<div class="empty">沒有</div>'
    }`;
  return `${
    list.length > 1
      ? `<div class="chips">${list.map((x, j) => `<span class="chip rad" data-vi="${j}" data-on="${j === i ? 1 : 0}">${esc(x.name)}</span>`).join('')}</div>`
      : ''
  }
    <table class="mai-rt vs-t">
      <tr><th></th><th class="vs-me">${esc(data.name)}（你）</th><th class="vs-fr">${esc(fd.name)}</th></tr>
      <tr><td>Rating</td><td${win(r.total, f.total)}><b>${r.total}</b></td><td${win(f.total, r.total)}><b>${f.total}</b></td></tr>
      <tr><td>舊曲 B35</td><td${win(r.old35, f.old35)}>${r.old35}</td><td${win(f.old35, r.old35)}>${f.old35}</td></tr>
      <tr><td>新曲 B15</td><td${win(r.new15, f.new15)}>${r.new15}</td><td${win(f.new15, r.new15)}>${f.new15}</td></tr>
      <tr><td>漲幅</td><td${gm && gf ? win(gm.perDay, gf.perDay) : ''}>${growthText(gm)}</td><td${gm && gf ? win(gf.perDay, gm.perDay) : ''}>${growthText(gf)}</td></tr>
    </table>
    <p class="cq-hint">${esc(fd.name)} 的成績更新於 ${esc(new Date(fd.at).toLocaleDateString('zh-TW'))}，兩人都打過 ${both.length} 個譜面。</p>
    ${sec(`${esc(fd.name)} 比較高`, higher, 'Rating 差最多的在前面，可以請教對方')}
    ${sec('你比較高', lower)}
    ${sec('共同課題曲', common, '兩個人都還沒 SSS 的譜面，定數高到低，可以一起練')}
    ${sec(`${esc(fd.name)} 的 B50 裡你沒打過的`, notPlayed)}
    <div class="cq-actions"><button class="btn ghost small" id="vs-del">✕ 移除 ${esc(fd.name)}</button></div>
    ${share}${paste}`;
}
function bindVs(el, S) {
  const $ = id => el.querySelector('#' + id);
  if ($('vs-share')) $('vs-share').onclick = () => shareVs(S);
  if ($('vs-add'))
    $('vs-add').onclick = async () => {
      try {
        addVs(await readVs($('vs-in').value));
      } catch (_) {
        return toast('連結格式不對，請請朋友重新分享');
      }
      renderB50(el, S);
    };
  if ($('vs-del'))
    $('vs-del').onclick = () => {
      const list = LS.get('maiVs', []);
      list.splice(Math.min(mai.vsIdx || 0, list.length - 1), 1);
      LS.set('maiVs', list);
      mai.vsIdx = 0;
      renderB50(el, S);
    };
  el.querySelectorAll('[data-vi]').forEach(
    c =>
      (c.onclick = () => {
        mai.vsIdx = +c.dataset.vi;
        renderB50(el, S);
      }),
  );
}

async function importVs(code) {
  let d;
  try {
    d = await readVs(code);
  } catch (_) {
    return toast('比較連結格式不對，請請朋友重新分享');
  }
  addVs(d);
  toast(`已加入 ${d.name} 的成績，可以比較了`);
  state.view = 'b50';
  mai.tab = 'b50';
  mai.b50mode = 'vs';
  renderStatusRow();
  render();
}
addEventListener('DOMContentLoaded', () => VS_IMPORT && importVs(VS_IMPORT));
// 網頁開著時又點了比較連結：這個監聽比 app.js 的先註冊，網址還沒被改寫；解壓縮完才切頁，不會被 app.js 蓋掉
addEventListener('hashchange', () => {
  const code = new URLSearchParams(location.hash.slice(1)).get('vs');
  if (code) importVs(code);
});
