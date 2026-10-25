/* 🎵 maimai 工具（mai-bot 的指令改成按鈕）：🔍 查歌、📋 定數表、🎲 抽一首，點任何譜面看各評級 Rating。
   定數來自 songs.json（scripts/songs.py 產生）。這個檔案只定義函式，在 b50.js、app.js 之前載入。 */
const DIFF_NAMES = ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'Re:MASTER'];
const DIFF_COLORS = ['#22bb5b', '#fb9c2d', '#f64861', '#9e45e2', '#c88cf0'];
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
const LEVELS = ['12', '12+', '13', '13+', '14', '14+', '15'];
const mai = { songs: null, loading: null, tab: null, level: null, pick: null, picks: null };

const rankOf = ach => RANKS.find(r => ach >= r[0]);
// 用整數算，避免 13.7 × 22.4 這類浮點誤差少 1 分（與 mai-bot 的 chart_rating 相同）
const rawRating = (c, ach, k) =>
  Math.floor(
    (Math.round(c * 10) * Math.round(Math.min(ach, 100.5) * 10000) * Math.round(k * 10)) / 1e8,
  );
// ALL PERFECT 以上每首 +1
const chartRating = (c, ach, fc) => rawRating(c, ach, rankOf(ach)[1]) + (/^ap/.test(fc) ? 1 : 0);
// 13 ＝ 定數 13.0～13.5，13+ ＝ 13.6～13.9（乘 10 用整數比）
const inLevel = (c, l) => {
  const c10 = Math.round(c * 10),
    b = parseInt(l, 10) * 10;
  return l.endsWith('+') ? c10 >= b + 6 && c10 < b + 10 : c10 >= b && c10 < b + 6;
};
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

function loadSongs() {
  if (!mai.loading)
    mai.loading = fetch('songs.json')
      .then(r => r.json())
      .then(d => {
        const idx = new Map(),
          charts = [];
        for (const s of d.songs) {
          if (!idx.has(s[0] + '|' + s[1])) idx.set(s[0] + '|' + s[1], s);
          s[4].forEach(
            (c, diff) => c != null && charts.push({ s, diff, c, est: !!(s[5] & (1 << diff)) }),
          );
        }
        return (mai.songs = { ...d, idx, charts });
      })
      .catch(e => {
        mai.loading = null;
        throw e;
      });
  return mai.loading;
}

/* ---- 共用：譜面列、難度標籤 ---- */
const diffTag = diff =>
  `<span class="b50-diff" style="background:${DIFF_COLORS[diff]}">${DIFF_NAMES[diff]}</span>`;
const coverImg = (img, cls = 'b50-cover') =>
  `<img class="${cls}" loading="lazy" alt="" src="${img ? COVER + esc(img) : 'icon.svg'}">`;
const constText = (c, est) => (est ? '≈' : '') + c.toFixed(1);
function chartRowHTML(ch, i) {
  return `<button class="b50-row mai-chart" data-k="${esc(ch.s[0] + '|' + ch.s[1])}" data-d="${ch.diff}">
    ${i == null ? '' : `<span class="b50-no">${i + 1}</span>`}${coverImg(ch.s[3])}
    <div class="b50-info"><div class="b50-title">${esc(ch.s[0])}</div>
      <div class="b50-meta">${diffTag(ch.diff)} ${ch.s[1] === 'dx' ? 'DX' : 'STD'} · ${esc(ch.s[2])}</div></div>
    <div class="b50-score"><b>${constText(ch.c, ch.est)}</b><small>定數</small></div>
  </button>`;
}
function bindCharts(el) {
  el.querySelectorAll('.mai-chart').forEach(
    b => (b.onclick = () => openChart(mai.songs.idx.get(b.dataset.k), +b.dataset.d)),
  );
}

/* ---- 點譜面：各評級 Rating（mai-bot /rt），有成績時標出下一個評級 ---- */
function myScore(s, diff) {
  const data = LS.get('mai', null);
  return data && data.scores.find(x => x[0] === s[0] && x[1] === s[1] && x[2] === diff);
}
function openChart(s, diff) {
  const c = s[4][diff],
    est = !!(s[5] & (1 << diff)),
    mine = myScore(s, diff),
    now = mine ? chartRating(c, mine[3], mine[4]) : 0;
  const rows = RANKS.slice(0, 7)
    .map(([t, k, name]) => {
      const r = rawRating(c, t, k),
        up = mine && t > mine[3] && r > now ? ` <small class="mai-up">+${r - now}</small>` : '';
      return `<tr${mine && rankOf(mine[3])[2] === name ? ' class="on"' : ''}><td>${name}</td><td>${t.toFixed(1)}%</td><td><b>${r}</b>${up}</td></tr>`;
    })
    .join('');
  const d = ensureDialog(
    'chart',
    `<div class="mai-chart-head">${coverImg(s[3], 'mai-cover-lg')}<div>
      <h2>${esc(s[0])}</h2>
      <div class="b50-meta">${diffTag(diff)} ${s[1] === 'dx' ? 'DX' : 'STD'} · ${esc(s[2])}</div>
      <div class="mai-const">定數 <b>${constText(c, est)}</b>${est ? '<small>（還沒公布，用等級估的）</small>' : ''}</div>
    </div></div>
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

/* ---- 🔍 查歌（mai-bot /m）：歌名或羅馬拼音 ---- */
function searchSongs(S, q) {
  q = q.trim().toLowerCase();
  if (!q) return [];
  const r = normRomaji(q),
    seen = new Map();
  for (const s of S.songs) {
    const t = s[0].toLowerCase();
    const score =
      t === q ? 3 : t.includes(q) ? 2 : r.length >= 3 && s[6] && s[6].includes(r) ? 1 : 0;
    if (score && !(seen.get(s[0]) >= score)) seen.set(s[0], score);
  }
  return [...seen]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([t]) => t);
}
function songCardHTML(S, title) {
  const kinds = ['dx', 'std'].map(k => S.idx.get(title + '|' + k)).filter(Boolean);
  return `<div class="mai-song">${coverImg(kinds[0][3])}
    <div class="b50-info"><div class="b50-title">${esc(title)}</div><div class="b50-meta">${esc(kinds[0][2])}</div>
    ${kinds
      .map(
        s =>
          `<div class="mai-sheets"><span class="mai-kind">${s[1] === 'dx' ? 'DX' : 'STD'}</span>${s[4]
            .map((c, diff) =>
              c == null
                ? ''
                : `<button class="mai-sheet" style="--dc:${DIFF_COLORS[diff]}" data-k="${esc(s[0] + '|' + s[1])}" data-d="${diff}">${DIFF_NAMES[diff].replace('Re:MASTER', 'Re:M')} <b>${constText(c, s[5] & (1 << diff))}</b></button>`,
            )
            .join('')}</div>`,
      )
      .join('')}</div></div>`;
}
function renderSearch(el, S) {
  el.innerHTML = `<input id="mai-q" class="mai-input" type="search" placeholder="歌名或羅馬拼音（例：senbonzakura）" autocomplete="off">
    <div id="mai-res"></div>`;
  const q = el.querySelector('#mai-q'),
    res = el.querySelector('#mai-res');
  q.value = mai.q || '';
  q.oninput = () => {
    mai.q = q.value;
    const titles = searchSongs(S, q.value);
    res.innerHTML = q.value.trim()
      ? titles.length
        ? titles.map(t => songCardHTML(S, t)).join('')
        : '<div class="empty">找不到這首歌</div>'
      : '<p class="cq-hint">輸入歌名就會列出各難度的定數；點定數看各評級能拿多少 Rating。</p>';
    res
      .querySelectorAll('.mai-sheet')
      .forEach(b => (b.onclick = () => openChart(S.idx.get(b.dataset.k), +b.dataset.d)));
  };
  q.oninput();
}

/* ---- 📋 定數表（mai-bot /c） ---- */
function levelChips(sel, multi) {
  return `<div class="chips mai-levels">${LEVELS.map(
    l =>
      `<span class="chip${multi ? '' : ' rad'}" data-l="${l}" data-on="${sel.includes(l) ? 1 : 0}">${l}</span>`,
  ).join('')}</div>`;
}
const inLevels = (ch, ls) => ls.some(l => inLevel(ch.c, l));
function renderLevel(el, S) {
  const l = (mai.level = mai.level || LS.get('maiLevel', '13+'));
  const list = S.charts
    .filter(ch => inLevels(ch, [l]))
    .sort((a, b) => b.c - a.c || a.s[0].localeCompare(b.s[0]));
  el.innerHTML = `${levelChips([l])}
    <p class="cq-hint">Lv ${l}：${list.length} 個譜面（定數高到低）。點譜面看各評級能拿多少 Rating。</p>
    ${list.map(ch => chartRowHTML(ch)).join('')}`;
  el.querySelectorAll('.mai-levels .chip').forEach(
    c =>
      (c.onclick = () => {
        mai.level = c.dataset.l;
        LS.set('maiLevel', mai.level);
        renderLevel(el, S);
      }),
  );
  bindCharts(el);
}

/* ---- 🎲 抽一首（mai-bot /r） ---- */
function renderRandom(el, S) {
  const ls = (mai.picks = mai.picks || LS.get('maiPicks', ['13+']));
  el.innerHTML = `<p class="cq-hint">選要抽的等級（可以複選），再按抽一首。</p>${levelChips(ls, true)}
    <div class="cq-actions"><button class="btn mai-roll" id="mai-roll">🎲 抽一首</button></div>
    <div id="mai-pick">${mai.pick ? chartRowHTML(mai.pick) : ''}</div>`;
  el.querySelectorAll('.mai-levels .chip').forEach(
    c =>
      (c.onclick = () => {
        const l = c.dataset.l;
        mai.picks = ls.includes(l) ? ls.filter(x => x !== l) : [...ls, l];
        LS.set('maiPicks', mai.picks);
        renderRandom(el, S);
      }),
  );
  el.querySelector('#mai-roll').onclick = () => {
    const pool = S.charts.filter(ch => inLevels(ch, ls.length ? ls : LEVELS));
    mai.pick = pool[Math.floor(Math.random() * pool.length)];
    renderRandom(el, S);
  };
  bindCharts(el);
}

/* ---- 🎵 maimai 頁：子分頁 ---- */
const MAI_TABS = [
  ['b50', '🏅 B50'],
  ['search', '🔍 查歌'],
  ['level', '📋 定數表'],
  ['random', '🎲 抽一首'],
];
function renderMai(el) {
  const tab = (mai.tab = mai.tab || LS.get('maiTab', 'b50'));
  el.innerHTML = `<div class="mai-tabs">${MAI_TABS.map(
    ([t, n]) => `<button data-t="${t}"${t === tab ? ' data-on="1"' : ''}>${n}</button>`,
  ).join('')}</div><div id="mai-body"><div class="empty">載入定數資料…</div></div>`;
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
      ({ b50: renderB50, search: renderSearch, level: renderLevel, random: renderRandom })[tab](
        body,
        S,
      );
    })
    .catch(() => (body.innerHTML = '<div class="empty">定數資料載入失敗（需要網路）</div>'));
}
