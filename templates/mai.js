/* 🎵 maimai 頁：🏅 B50 與 📚 曲庫（參考 arcade-songs：篩選、排序、譜面／封面／統計檢視、抽歌、我的清單），
   點任何譜面看各評級 Rating。資料來自 songs.json（scripts/songs.py 產生）。
   這個檔案只定義函式，在 b50.js、app.js 之前載入。 */
const DIFF_NAMES = ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'Re:MASTER'];
const DIFF_COLORS = ['#22bb5b', '#fb9c2d', '#f64861', '#9e45e2', '#c88cf0'];
const UTAGE_COLOR = '#e5307e';
const TYPE_NAMES = ['DX', 'STD', '宴'];
const COVER = 'https://dp4p6x0xfi5o9.cloudfront.net/maimai/img/cover/';
// [達成率門檻, 係數, 評級]（與 mai-bot 相同）
const RANKS = [
  [100.5, 22.4, 'SSS+'],
  [100, 21.6, 'SSS'],
  [99.5, 21.1, 'SS+'],
  [99, 20.8, 'SS'],
  [98, 20.3, 'S+'],
  [97, 20, 'S'],
  [94, 16.8, 'AAA'],
  [90, 15.2, 'AA'],
  [80, 13.6, 'A'],
  [0, 12, 'B'],
];
const FC_LABEL = { fc: 'FC', fcp: 'FC+', ap: 'AP', app: 'AP+' };
const LEVELS = [
  ...['1', '2', '3', '4', '5', '6', '7'],
  ...['7+', '8', '8+', '9', '9+', '10', '10+', '11', '11+', '12', '12+', '13', '13+', '14', '14+'],
  '15',
];
const PAGE = 60;
const mai = { songs: null, loading: null, tab: null, f: null, shown: PAGE };

const rankOf = ach => RANKS.find(r => ach >= r[0]);
// 用整數算，避免 13.7 × 22.4 這類浮點誤差少 1 分（與 mai-bot 的 chart_rating 相同）
const rawRating = (c, ach, k) =>
  Math.floor(
    (Math.round(c * 10) * Math.round(Math.min(ach, 100.5) * 10000) * Math.round(k * 10)) / 1e8,
  );
// ALL PERFECT 以上每首 +1
const chartRating = (c, ach, fc) => rawRating(c, ach, rankOf(ach)[1]) + (/^ap/.test(fc) ? 1 : 0);
// 「13+」「13+?」→ 13.6；宴的「*」沒有等級 → NaN
const levelValue = l => parseInt(l, 10) + (l.includes('+') ? 0.6 : 0);
// 和 mai-bot 相同的羅馬拼音正規化：shoukai／shokai／syoukai 都算同一個
const ROMAJI_RULES = [
  ['jy', 'j'],
  ['shi', 'si'],
  ['sh', 'sy'],
  ['chi', 'ti'],
  ['ch', 'ty'],
  ['tsu', 'tu'],
  ['fu', 'hu'],
  ['ji', 'zi'],
  ['j', 'zy'],
  ['ou', 'o'],
  ['oo', 'o'],
  ['uu', 'u'],
  ['aa', 'a'],
  ['ii', 'i'],
  ['ee', 'e'],
];
const normRomaji = s =>
  ROMAJI_RULES.reduce((t, [a, b]) => t.split(a).join(b), s.toLowerCase().replace(/[^a-z0-9]/g, ''));

/* songs.json → 物件。每個譜面有日版、國際版兩種數值（v[0]、v[1]）；B50 用國際版（maimai DX NET 國際版） */
function loadSongs() {
  if (!mai.loading)
    mai.loading = fetch('songs.json')
      .then(r => r.json())
      .then(d => {
        const idx = new Map(),
          sheets = [];
        const songs = d.songs.map((a, i) => {
          const s = {
            i,
            title: a[0],
            artist: a[1],
            cat: a[2],
            ver: a[3],
            bpm: a[4],
            date: a[5],
            img: a[6],
            ro: a[7],
            locked: a[8],
            comment: a[9],
            key: a[0] + '|' + a[1],
          };
          s.sheets = a[10].map(([t, df, lv, c, est, des, notes, reg, ver, io]) => {
            const jp = { lv, c, est, ver },
              sh = {
                s,
                t,
                d: df,
                des,
                notes,
                reg,
                v: [jp, io ? { lv: io[0], c: io[1], est: io[2], ver: io[3] } : jp],
              };
            sheets.push(sh);
            return sh;
          });
          s._s = foldCJK(
            [s.title, s.artist, ...s.sheets.map(sh => d.des[sh.des] || '')].join(' ').toLowerCase(),
          );
          // B50 用的舊格式：[歌名, 'dx'|'std', 版本, 封面, [5 難度定數], 估計遮罩, 羅馬拼音]
          for (const t of [0, 1]) {
            const own = s.sheets.filter(sh => sh.t === t && typeof sh.d === 'number');
            const k = s.title + '|' + ['dx', 'std'][t];
            if (!own.length || idx.has(k)) continue;
            const consts = [null, null, null, null, null];
            let est = 0;
            for (const sh of own) {
              consts[sh.d] = sh.v[1].c;
              est |= sh.v[1].est << sh.d;
            }
            idx.set(k, [
              s.title,
              ['dx', 'std'][t],
              d.vers[own[0].v[1].ver][0],
              s.img,
              consts,
              est,
              s.ro,
            ]);
          }
          return s;
        });
        return (mai.songs = { ...d, songs, sheets, idx });
      })
      .catch(e => {
        mai.loading = null;
        throw e;
      });
  return mai.loading;
}

/* ---- 共用 ---- */
const diffColor = sh => (sh.t === 2 ? UTAGE_COLOR : DIFF_COLORS[sh.d]);
const diffName = sh => (sh.t === 2 ? sh.d : DIFF_NAMES[sh.d]);
const diffTag = diff =>
  `<span class="b50-diff" style="background:${DIFF_COLORS[diff]}">${DIFF_NAMES[diff]}</span>`;
const coverImg = (img, cls = 'b50-cover') =>
  `<img class="${cls}" loading="lazy" alt="" src="${img ? COVER + esc(img) : 'icon.svg'}">`;
const constText = (c, est) => (est ? '≈' : '') + c.toFixed(1);
const regionIdx = () => (mai.f && mai.f.region === 'jp' ? 0 : 1);
function bindCharts(el) {
  el.querySelectorAll('.mai-chart').forEach(
    b =>
      (b.onclick = () => {
        const s = mai.songs.idx.get(b.dataset.k),
          diff = +b.dataset.d;
        openChart({
          title: s[0],
          kind: s[1],
          ver: s[2],
          img: s[3],
          diff,
          c: s[4][diff],
          est: s[5] & (1 << diff),
        });
      }),
  );
}

/* ---- 點譜面：各評級 Rating（mai-bot /rt），有成績時標出下一個評級 ---- */
function myScore(title, kind, diff) {
  const data = LS.get('mai', null);
  return data && data.scores.find(x => x[0] === title && x[1] === kind && x[2] === diff);
}
const NOTE_NAMES = ['TAP', 'HOLD', 'SLIDE', 'TOUCH', 'BREAK'];
function notesHTML(notes) {
  return notes
    ? `<div class="mai-notes">${NOTE_NAMES.map((n, i) => (notes[i] == null ? '' : `<span>${n} <b>${notes[i]}</b></span>`)).join('')}<span>合計 <b>${notes[5]}</b></span></div>`
    : '';
}
function openChart(t) {
  const { c, diff } = t,
    mine = myScore(t.title, t.kind, diff),
    now = mine ? chartRating(c, mine[3], mine[4]) : 0;
  const rows = RANKS.slice(0, 7)
    .map(([th, k, name]) => {
      const r = rawRating(c, th, k),
        up = mine && th > mine[3] && r > now ? ` <small class="mai-up">+${r - now}</small>` : '';
      return `<tr${mine && rankOf(mine[3])[2] === name ? ' class="on"' : ''}><td>${name}</td><td>${th.toFixed(1)}%</td><td><b>${r}</b>${up}</td></tr>`;
    })
    .join('');
  const sh = t.sh,
    designer = sh && mai.songs.des[sh.des];
  const d = ensureDialog(
    'chart',
    `<div class="mai-chart-head">${coverImg(t.img, 'mai-cover-lg')}<div>
      <h2>${esc(t.title)}</h2>
      <div class="b50-meta">${diffTag(diff)} ${t.kind === 'dx' ? 'DX' : 'STD'} · ${esc(t.ver)}${designer ? ' · 譜師 ' + esc(designer) : ''}</div>
      <div class="mai-const">定數 <b>${constText(c, t.est)}</b>${t.est ? '<small>（還沒公布，用等級估的）</small>' : ''}</div>
    </div></div>
    ${sh ? notesHTML(sh.notes) : ''}
    ${
      mine
        ? `<p class="mai-mine">你的成績 <b>${mine[3].toFixed(4)}%</b>（${rankOf(mine[3])[2]}${mine[4] ? ' · ' + (FC_LABEL[mine[4]] || '') : ''}）→ 單曲 Rating <b>${now}</b></p>`
        : ''
    }
    <table class="mai-rt"><tr><th>評級</th><th>達成率</th><th>Rating</th></tr>${rows}</table>
    <p class="cq-hint">ALL PERFECT 以上再 +1。</p>`,
  );
  d.showModal();
}
function sheetChart(sh, ri = regionIdx()) {
  const v = sh.v[ri];
  return {
    title: sh.s.title,
    kind: ['dx', 'std'][sh.t],
    ver: mai.songs.vers[v.ver][0],
    img: sh.s.img,
    diff: sh.d,
    c: v.c,
    est: v.est,
    sh,
  };
}

/* ---- 一首歌的詳細資料：所有譜面、版本、地區、我的清單 ---- */
const myList = () => new Set(LS.get('maiList', []));
function openSong(s) {
  const S = mai.songs,
    ri = regionIdx(),
    has = bit => s.sheets.some(sh => sh.reg & bit),
    fav = myList().has(s.key);
  const rows = s.sheets
    .map((sh, i) => {
      const v = sh.v[ri];
      return `<tr class="${sh.t === 2 ? '' : 'mai-tap'}" data-i="${i}">
        <td>${TYPE_NAMES[sh.t]}</td>
        <td><span class="b50-diff" style="background:${diffColor(sh)}">${esc(diffName(sh))}</span></td>
        <td>${esc(v.lv)}</td><td><b>${sh.t === 2 ? '—' : constText(v.c, v.est)}</b></td>
        <td>${esc(S.des[sh.des] || '—')}</td><td>${sh.notes ? sh.notes[5] : '—'}</td></tr>`;
    })
    .join('');
  const d = ensureDialog(
    'song',
    `<div class="mai-chart-head">${coverImg(s.img, 'mai-cover-lg')}<div>
      <h2>${esc(s.title)}</h2>
      <div class="b50-meta">${esc(s.artist)}</div>
      <div class="b50-meta">${esc(S.cats[s.cat])} · ${esc(S.vers[s.ver] ? S.vers[s.ver][0] : '')} · BPM ${s.bpm ?? '—'} · ${esc(s.date)}</div>
      <div class="mai-avail">${[
        [1, '日版'],
        [2, '國際版'],
        [8, '中國版'],
      ]
        .map(([b, n]) => `<span class="${has(b) ? 'on' : ''}">${has(b) ? '✓' : '✗'} ${n}</span>`)
        .join('')}</div>
    </div></div>
    ${s.comment ? `<p class="cq-hint">${esc(s.comment)}</p>` : ''}
    <div class="mf-row"><button class="btn small${fav ? '' : ' ghost'}" id="song-fav">${fav ? '★ 已在我的清單' : '☆ 加入我的清單'}</button>
      <a class="btn ghost small" target="_blank" rel="noopener" href="https://www.youtube.com/results?search_query=${encodeURIComponent('maimai ' + s.title + ' 譜面確認')}">▶ YouTube 譜面</a></div>
    <table class="mai-rt mai-sheets-t"><tr><th>類型</th><th>難度</th><th>等級</th><th>定數</th><th>譜師</th><th>物量</th></tr>${rows}</table>
    <p class="cq-hint">${ri ? '國際版' : '日版'}的等級／定數。點譜面看各評級 Rating。</p>`,
  );
  d.classList.add('dlg-wide');
  d.querySelector('#song-fav').onclick = () => {
    const l = myList();
    l.has(s.key) ? l.delete(s.key) : l.add(s.key);
    LS.set('maiList', [...l]);
    openSong(s);
    refreshLib();
  };
  d.querySelectorAll('tr.mai-tap').forEach(
    tr => (tr.onclick = () => openChart(sheetChart(s.sheets[+tr.dataset.i], ri))),
  );
  if (!d.open) d.showModal();
}

/* ---- 📚 曲庫：篩選 ---- */
const DEFAULT_F = {
  q: '',
  region: 'intl',
  diffs: [],
  types: [],
  cats: [],
  lvMin: '',
  lvMax: '',
  cMin: '',
  cMax: '',
  verMin: '',
  verMax: '',
  des: '',
  bpmMin: '',
  bpmMax: '',
  newOnly: false,
  mine: false,
  all: false,
  sort: 'c',
  desc: true,
  view: 'sheet',
  draw: 1,
};
const FILTER_KEYS = Object.keys(DEFAULT_F).filter(
  k => !['q', 'region', 'sort', 'desc', 'view', 'draw'].includes(k),
);
const activeFilters = f =>
  FILTER_KEYS.filter(k => (Array.isArray(f[k]) ? f[k].length : f[k] !== DEFAULT_F[k])).length;

function filterSheets(S, f) {
  const ri = f.region === 'jp' ? 0 : 1,
    bit = ri ? 2 : 1,
    q = foldCJK(f.q.trim().toLowerCase()),
    r = normRomaji(f.q),
    num = (x, d) => (x === '' || x == null || isNaN(+x) ? d : +x),
    lvMin = f.lvMin ? levelValue(f.lvMin) : null,
    lvMax = f.lvMax ? levelValue(f.lvMax) : null,
    cMin = num(f.cMin, -1),
    cMax = num(f.cMax, 99),
    vMin = num(f.verMin, -1),
    vMax = num(f.verMax, 999),
    bMin = num(f.bpmMin, null),
    bMax = num(f.bpmMax, null),
    diffs = new Set(f.diffs),
    types = new Set(f.types.map(Number)),
    cats = new Set(f.cats.map(Number)),
    mine = f.mine ? myList() : null,
    newVers = new Set(S.new.map(n => S.vers.findIndex(v => v[0] === n)));
  const out = [];
  for (const s of S.songs) {
    if (q && !s._s.includes(q) && !(r.length >= 3 && s.ro.includes(r))) continue;
    if (cats.size && !cats.has(s.cat)) continue;
    if (mine && !mine.has(s.key)) continue;
    if (
      (bMin != null || bMax != null) &&
      (s.bpm == null || s.bpm < (bMin ?? 0) || s.bpm > (bMax ?? 1e9))
    )
      continue;
    for (const sh of s.sheets) {
      const v = sh.v[ri];
      if (!f.all && !(sh.reg & bit)) continue;
      if (types.size && !types.has(sh.t)) continue;
      if (diffs.size && !diffs.has(sh.t === 2 ? 'u' : String(sh.d))) continue;
      if (lvMin != null || lvMax != null) {
        const l = levelValue(v.lv);
        if (isNaN(l) || l < (lvMin ?? 0) || l > (lvMax ?? 99)) continue;
      }
      if (v.c < cMin - 1e-9 || v.c > cMax + 1e-9) continue;
      if (v.ver < vMin || v.ver > vMax) continue;
      if (f.des !== '' && sh.des !== +f.des) continue;
      if (f.newOnly && !newVers.has(v.ver)) continue;
      out.push({ s, sh, v });
    }
  }
  const S_KEYS = {
    c: x => x.v.c,
    lv: x => levelValue(x.v.lv) || 0,
    date: x => (S.vers[x.v.ver] || [])[2] || x.s.date,
    bpm: x => x.s.bpm ?? -1,
    notes: x => (x.sh.notes ? x.sh.notes[5] : -1),
    title: x => x.s.title,
  };
  const key = S_KEYS[f.sort] || S_KEYS.c,
    dir = f.desc ? -1 : 1;
  const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  return out.sort(
    (a, b) =>
      dir * cmp(key(a), key(b)) ||
      (f.sort === 'lv' ? dir * (a.v.c - b.v.c) : 0) ||
      a.s.title.localeCompare(b.s.title) ||
      a.sh.t - b.sh.t ||
      (a.sh.t === 2 ? 0 : a.sh.d - b.sh.d),
  );
}

const maiChip = (attr, key, v, on, label, cls = '') =>
  `<span class="chip${cls}" ${attr}="${key}" data-v="${esc(v)}" data-on="${on ? 1 : 0}">${label}</span>`;
const opt = (v, label, sel) =>
  `<option value="${esc(v)}"${String(sel) === String(v) ? ' selected' : ''}>${esc(label)}</option>`;
function filterHTML(S, f) {
  const multi = (key, items) =>
    items.map(([v, n]) => maiChip('data-m', key, v, f[key].includes(String(v)), n)).join('');
  const lvOpts = sel => opt('', '不限', sel) + LEVELS.map(l => opt(l, l, sel)).join('');
  const verOpts = sel => opt('', '不限', sel) + S.vers.map((v, i) => opt(i, v[1], sel)).join('');
  const desSorted = S.des.map((n, i) => [i, n]).sort((a, b) => a[1].localeCompare(b[1]));
  return `<details class="mai-filter" id="mai-filter"${mai.filterOpen ? ' open' : ''}>
    <summary>⚙️ 篩選<span id="mai-fcount"></span></summary>
    <div class="mai-frow"><label>版本區域</label><div class="chips">${[
      ['intl', '國際版'],
      ['jp', '日版'],
    ]
      .map(([v, n]) => maiChip('data-r', 'region', v, f.region === v, n, ' rad'))
      .join('')}</div></div>
    <div class="mai-frow"><label>難度</label><div class="chips">${multi('diffs', [
      ...DIFF_NAMES.map((n, i) => [i, n]),
      ['u', '宴'],
    ])}</div></div>
    <div class="mai-frow"><label>類型</label><div class="chips">${multi(
      'types',
      TYPE_NAMES.map((n, i) => [i, n]),
    )}</div></div>
    <div class="mai-frow"><label>等級</label><div class="mai-range"><select data-f="lvMin">${lvOpts(f.lvMin)}</select> ～ <select data-f="lvMax">${lvOpts(f.lvMax)}</select></div></div>
    <div class="mai-frow"><label>定數</label><div class="mai-range"><input data-f="cMin" type="number" step="0.1" min="1" max="15" inputmode="decimal" placeholder="最低" value="${esc(f.cMin)}"> ～ <input data-f="cMax" type="number" step="0.1" min="1" max="15" inputmode="decimal" placeholder="最高" value="${esc(f.cMax)}"></div></div>
    <div class="mai-frow"><label>分類</label><div class="chips">${multi(
      'cats',
      S.cats.map((n, i) => [i, n]),
    )}</div></div>
    <div class="mai-frow"><label>版本</label><div class="mai-range"><select data-f="verMin">${verOpts(f.verMin)}</select> ～ <select data-f="verMax">${verOpts(f.verMax)}</select></div></div>
    <div class="mai-frow"><label>譜師</label><div class="mai-range"><select data-f="des">${opt('', '不限', f.des)}${desSorted.map(([i, n]) => opt(i, n, f.des)).join('')}</select></div></div>
    <div class="mai-frow"><label>BPM</label><div class="mai-range"><input data-f="bpmMin" type="number" inputmode="numeric" placeholder="最低" value="${esc(f.bpmMin)}"> ～ <input data-f="bpmMax" type="number" inputmode="numeric" placeholder="最高" value="${esc(f.bpmMax)}"></div></div>
    <div class="mai-frow"><label>其他</label><div class="chips">
      ${maiChip('data-b', 'newOnly', 1, f.newOnly, '🆕 新曲（B15）', ' tgl')}
      ${maiChip('data-b', 'mine', 1, f.mine, '⭐ 我的清單', ' fav')}
      ${maiChip('data-b', 'all', 1, f.all, '含已刪除／未收錄', ' tgl')}
      <span class="chip clear" id="mai-reset">✕ 重設篩選</span></div></div>
  </details>`;
}
const SORTS = [
  ['c', '定數'],
  ['lv', '等級'],
  ['date', '推出日期'],
  ['bpm', 'BPM'],
  ['notes', '物量'],
  ['title', '歌名'],
];
const VIEWS = [
  ['sheet', '📄 譜面'],
  ['grid', '🖼️ 封面'],
  ['sum', '📊 統計'],
];
function renderLibrary(el, S) {
  const f = (mai.f = { ...DEFAULT_F, ...LS.get('maiFilter', {}), ...(mai.f || {}) });
  el.innerHTML = `<input id="mai-q" class="mai-input" type="search" placeholder="搜尋歌名、藝術家、譜師；日文歌名可打羅馬拼音" autocomplete="off" value="${esc(f.q)}">
    ${filterHTML(S, f)}
    <div class="mai-tool">
      <select id="mai-sort" aria-label="排序">${SORTS.map(([v, n]) => opt(v, '排序：' + n, f.sort)).join('')}</select>
      <button class="iconbtn" id="mai-dir" aria-label="排序方向"></button>
      <div class="mai-views">${VIEWS.map(([v, n]) => `<button data-v="${v}">${n}</button>`).join('')}</div>
      <button class="btn small" id="mai-draw">🎲 抽歌</button>
    </div>
    <div id="mai-res"></div>`;
  const save = () => {
    LS.set('maiFilter', f);
    mai.shown = PAGE;
    refreshLib();
  };
  el.querySelector('#mai-q').oninput = e => {
    f.q = e.target.value;
    save();
  };
  el.querySelector('#mai-filter').ontoggle = e => (mai.filterOpen = e.target.open);
  el.querySelectorAll('[data-m]').forEach(
    c =>
      (c.onclick = () => {
        const a = f[c.dataset.m],
          v = c.dataset.v;
        f[c.dataset.m] = a.includes(v) ? a.filter(x => x !== v) : [...a, v];
        c.dataset.on = f[c.dataset.m].includes(v) ? 1 : 0;
        save();
      }),
  );
  el.querySelectorAll('[data-r]').forEach(
    c =>
      (c.onclick = () => {
        f[c.dataset.r] = c.dataset.v;
        el.querySelectorAll(`[data-r="${c.dataset.r}"]`).forEach(
          x => (x.dataset.on = x === c ? 1 : 0),
        );
        save();
      }),
  );
  el.querySelectorAll('[data-b]').forEach(
    c =>
      (c.onclick = () => {
        f[c.dataset.b] = !f[c.dataset.b];
        c.dataset.on = f[c.dataset.b] ? 1 : 0;
        save();
      }),
  );
  el.querySelectorAll('[data-f]').forEach(
    i =>
      (i.oninput = () => {
        f[i.dataset.f] = i.value;
        save();
      }),
  );
  el.querySelector('#mai-reset').onclick = () => {
    for (const k of FILTER_KEYS) f[k] = Array.isArray(DEFAULT_F[k]) ? [] : DEFAULT_F[k];
    LS.set('maiFilter', f);
    renderLibrary(el, S);
  };
  el.querySelector('#mai-sort').onchange = e => {
    f.sort = e.target.value;
    f.desc = !['title'].includes(f.sort);
    save();
  };
  el.querySelector('#mai-dir').onclick = () => {
    f.desc = !f.desc;
    save();
  };
  el.querySelectorAll('.mai-views button').forEach(
    b =>
      (b.onclick = () => {
        f.view = b.dataset.v;
        save();
      }),
  );
  el.querySelector('#mai-draw').onclick = () => openDraw();
  refreshLib();
}

function sheetRowHTML(x, i) {
  const { s, sh, v } = x,
    designer = mai.songs.des[sh.des];
  return `<button class="b50-row mai-lrow" data-s="${s.i}" data-i="${s.sheets.indexOf(sh)}">
    ${i == null ? '' : `<span class="b50-no">${i + 1}</span>`}${coverImg(s.img)}
    <div class="b50-info"><div class="b50-title">${esc(s.title)}</div>
      <div class="b50-meta"><span class="b50-diff" style="background:${diffColor(sh)}">${esc(diffName(sh))}</span>
      ${TYPE_NAMES[sh.t]} · Lv ${esc(v.lv)} · ${esc(mai.songs.vers[v.ver] ? mai.songs.vers[v.ver][1] : '')}${designer ? ' · ' + esc(designer) : ''}</div></div>
    <div class="b50-score"><b>${sh.t === 2 ? esc(v.lv) : constText(v.c, v.est)}</b><small>${sh.t === 2 ? '等級' : '定數'}</small></div>
  </button>`;
}
function bindRows(el) {
  el.querySelectorAll('.mai-lrow').forEach(
    b =>
      (b.onclick = () => {
        const s = mai.songs.songs[+b.dataset.s],
          sh = s.sheets[+b.dataset.i];
        sh.t === 2 ? openSong(s) : openChart(sheetChart(sh));
      }),
  );
  el.querySelectorAll('.mai-tile').forEach(
    b => (b.onclick = () => openSong(mai.songs.songs[+b.dataset.s])),
  );
}
function summaryHTML(list) {
  const cols = [...DIFF_NAMES, '宴'],
    by = new Map(),
    total = cols.map(() => 0);
  for (const { sh, v } of list) {
    const l = levelValue(v.lv),
      row = isNaN(l) ? '—' : LEVELS.find(x => levelValue(x) === l) || v.lv,
      c = sh.t === 2 ? 5 : sh.d;
    if (!by.has(row))
      by.set(
        row,
        cols.map(() => 0),
      );
    by.get(row)[c]++;
    total[c]++;
  }
  const rows = [...LEVELS, '—'].filter(l => by.has(l)).reverse();
  return `<table class="mai-rt mai-sum"><tr><th>等級</th>${cols.map((c, i) => `<th style="color:${i < 5 ? DIFF_COLORS[i] : UTAGE_COLOR}">${c.replace('Re:MASTER', 'Re:M')}</th>`).join('')}<th>合計</th></tr>
    ${rows
      .map(
        l =>
          `<tr><td><b>${esc(l)}</b></td>${by
            .get(l)
            .map(n => `<td>${n || ''}</td>`)
            .join('')}<td><b>${by.get(l).reduce((a, b) => a + b, 0)}</b></td></tr>`,
      )
      .join('')}
    <tr class="on"><td>合計</td>${total.map(n => `<td>${n}</td>`).join('')}<td><b>${list.length}</b></td></tr></table>`;
}
function refreshLib() {
  const res = document.getElementById('mai-res');
  if (!res || !mai.songs) return;
  const S = mai.songs,
    f = mai.f,
    list = filterSheets(S, f),
    n = activeFilters(f),
    songs = [...new Set(list.map(x => x.s))];
  mai.list = list;
  document.getElementById('mai-fcount').textContent = n ? `（${n}）` : '';
  document.getElementById('mai-dir').textContent = f.desc ? '↓' : '↑';
  document.getElementById('mai-sort').value = f.sort;
  document
    .querySelectorAll('.mai-views button')
    .forEach(b => (b.dataset.on = b.dataset.v === f.view ? 1 : 0));
  const head = `<p class="count">符合 ${list.length} 個譜面（${songs.length} 首歌）· ${f.region === 'jp' ? '日版' : '國際版'}</p>`;
  if (!list.length) {
    res.innerHTML = head + '<div class="empty">沒有符合的譜面</div>';
    return;
  }
  const more = left =>
    left > 0
      ? `<button class="btn ghost mai-more" id="mai-more">顯示更多（還有 ${left} 個）</button>`
      : '';
  if (f.view === 'sum') res.innerHTML = head + summaryHTML(list);
  else if (f.view === 'grid') {
    const show = songs.slice(0, mai.shown),
      ri = regionIdx(),
      matched = new Map();
    for (const x of list) {
      if (!matched.has(x.s)) matched.set(x.s, []);
      matched.get(x.s).push(x);
    }
    res.innerHTML =
      head +
      `<div class="mai-grid">${show
        .map(
          s => `<button class="mai-tile" data-s="${s.i}">${coverImg(s.img, 'mai-tile-img')}
          <span class="mai-tile-t">${esc(s.title)}</span>
          <span class="mai-tile-lv">${matched
            .get(s)
            .map(({ sh }) => `<i style="background:${diffColor(sh)}">${esc(sh.v[ri].lv)}</i>`)
            .join('')}</span></button>`,
        )
        .join('')}</div>` +
      more(songs.length - show.length);
  } else
    res.innerHTML =
      head +
      list
        .slice(0, mai.shown)
        .map(x => sheetRowHTML(x))
        .join('') +
      more(list.length - mai.shown);
  const m = document.getElementById('mai-more');
  if (m)
    m.onclick = () => {
      mai.shown += PAGE;
      refreshLib();
    };
  bindRows(res);
}

/* ---- 🎲 抽歌：從目前篩選結果隨機抽 ---- */
function openDraw(again) {
  const f = mai.f,
    pool = mai.list || [];
  if (!pool.length) return toast('沒有符合篩選的譜面可以抽');
  const n = Math.min(f.draw, pool.length),
    picked = new Set();
  while (picked.size < n) picked.add(pool[Math.floor(Math.random() * pool.length)]);
  const d = ensureDialog(
    'draw',
    `<h2>🎲 抽歌</h2>
    <p class="dlg-hint">從目前篩選的 ${pool.length} 個譜面裡抽。</p>
    <div class="chips mai-drawn">${[1, 3, 5, 10]
      .map(k => maiChip('data-n', 'draw', k, f.draw === k, k + ' 首', ' rad'))
      .join('')}</div>
    <div id="draw-res">${[...picked].map(x => sheetRowHTML(x)).join('')}</div>
    <div class="cq-actions"><button class="btn mai-roll" id="draw-again">🎲 再抽一次</button></div>`,
  );
  d.classList.add('dlg-wide');
  d.querySelectorAll('[data-n]').forEach(
    c =>
      (c.onclick = () => {
        f.draw = +c.dataset.v;
        LS.set('maiFilter', f);
        openDraw(true);
      }),
  );
  d.querySelector('#draw-again').onclick = () => openDraw(true);
  bindRows(d);
  if (!again || !d.open) d.showModal();
}

/* ---- 🎵 maimai 頁：子分頁 ---- */
const MAI_TABS = [
  ['b50', '🏅 B50'],
  ['lib', '📚 曲庫'],
];
function renderMai(el) {
  let tab = mai.tab || LS.get('maiTab', 'b50');
  if (!MAI_TABS.some(t => t[0] === tab)) tab = 'lib';
  mai.tab = tab;
  el.innerHTML = `<div class="mai-tabs">${MAI_TABS.map(
    ([t, n]) => `<button data-t="${t}"${t === tab ? ' data-on="1"' : ''}>${n}</button>`,
  ).join('')}</div><div id="mai-body"><div class="empty">載入歌曲資料…</div></div>`;
  el.querySelectorAll('.mai-tabs button').forEach(
    b =>
      (b.onclick = () => {
        mai.tab = b.dataset.t;
        LS.set('maiTab', mai.tab);
        renderMai(el);
      }),
  );
  const body = el.querySelector('#mai-body');
  loadSongs()
    .then(S => {
      if (state.view !== 'b50' || mai.tab !== tab) return;
      (tab === 'b50' ? renderB50 : renderLibrary)(body, S);
    })
    .catch(() => (body.innerHTML = '<div class="empty">歌曲資料載入失敗（需要網路）</div>'));
}
