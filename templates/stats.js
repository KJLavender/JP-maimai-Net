/* 📊 統計：各音遊設置店數的變化（data/history.json，每週更新加一筆）＋各都道府縣機廳數。
   SVG 手刻、不用圖表套件。配色是網站的遊戲識別色，調暗到深色背景的亮度範圍，已用 dataviz 驗證器檢查
   （色盲可辨、對比 ≥ 3:1）。這個檔案只定義函式，在 app.js 之前載入。 */

const SERIES = [
  { k: 'maimai でらっくす', name: 'maimai DX', c: '#e0458a' },
  { k: 'CHUNITHM', name: 'CHUNITHM', c: '#c98500' },
  { k: 'オンゲキ', name: 'オンゲキ', c: '#3a86e0' },
  { k: '初音ミク Project DIVA Arcade Future Tone', name: 'Project DIVA', c: '#1fa67c' },
  { k: 'cherrit', name: 'cherrit', c: '#9a5ce6' },
];
const statsUI = { game: '', allRegions: false, table: false };
const svgEl = (tag, attrs) =>
  `<${tag} ${Object.entries(attrs)
    .map(([k, v]) => `${k}="${v}"`)
    .join(' ')}/>`;
const md = d => `${+d.slice(5, 7)}/${+d.slice(8, 10)}`;
const niceMax = v => {
  const p = 10 ** Math.floor(Math.log10(v || 1)),
    m = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(x => x * p >= v); // 細一點，軸才不會空一大截
  return m * p;
};

function renderStats(el) {
  const hist = (CONFIG.history || []).filter(h => h.jp);
  const last = hist[hist.length - 1],
    prev = hist[hist.length - 2];
  const tw = DATA.filter(d => d.p === '台灣').length,
    jp = DATA.length - tw;
  const delta = last && prev ? last.jp.total - prev.jp.total : 0;
  const ch0 = hist.find(h => h.jp.games.cherrit),
    ch1 = last;
  el.innerHTML = `
  <div class="cq-tiles">
    <div class="stat"><div class="sv">${jp}</div><div class="sl">日本機廳${prev ? `<br><span class="dl">比 ${md(prev.date)} ${delta >= 0 ? '+' : ''}${delta}</span>` : ''}</div></div>
    <div class="stat"><div class="sv">${tw}</div><div class="sl">台灣機廳</div></div>
    ${ch0 && ch1 && ch0 !== ch1 ? `<div class="stat"><div class="sv">${ch1.jp.games.cherrit}</div><div class="sl">cherrit 設置店<br><span class="dl">${md(ch0.date)} 時 ${ch0.jp.games.cherrit} 間</span></div></div>` : ''}
  </div>
  <section class="chart">
    <div class="chead"><h3>各音遊設置店數（日本）</h3><button class="chip" id="st-table">${statsUI.table ? '📈 圖表' : '📋 表格'}</button></div>
    <div class="ckeys">${SERIES.map(s => `<span><i style="background:${s.c}"></i>${s.name}</span>`).join('')}</div>
    <div id="st-line"></div>
    <p class="cq-hint">每週資料更新會多一個點；${hist.length ? `目前有 ${hist.length} 筆（${md(hist[0].date)} 起）` : '還沒有歷史資料'}。</p>
  </section>
  <section class="chart">
    <div class="chead"><h3>各都道府縣機廳數</h3></div>
    <div class="chips" id="st-games">${[{ k: '', name: '全部機廳' }, ...SERIES]
      .map(
        s =>
          `<span class="chip stg" data-k="${esc(s.k)}"${statsUI.game === s.k ? ' data-on="1"' : ''}>${s.name}</span>`,
      )
      .join('')}</div>
    <div id="st-bar"></div>
  </section>`;
  el.querySelector('#st-table').onclick = () => {
    statsUI.table = !statsUI.table;
    renderStats(el);
  };
  el.querySelectorAll('#st-games .chip').forEach(
    c =>
      (c.onclick = () => {
        statsUI.game = c.dataset.k;
        renderStats(el);
      }),
  );
  // 用圖表框的內容寬度（扣掉卡片內距），不然 SVG 會超出右邊被切掉
  const lineBox = el.querySelector('#st-line'),
    barBox = el.querySelector('#st-bar');
  drawLine(lineBox, hist, Math.max(260, lineBox.clientWidth));
  drawBars(barBox, Math.max(260, barBox.clientWidth));
}

/* ---- 折線：各遊戲設置店數 ---- */
function drawLine(box, hist, W) {
  if (!hist.length) return;
  if (statsUI.table) {
    box.innerHTML =
      `<table class="stable"><tr><th>日期</th>${SERIES.map(s => `<th>${s.name}</th>`).join('')}<th>總數</th></tr>` +
      hist
        .map(
          h =>
            `<tr><td>${h.date}</td>${SERIES.map(s => `<td>${h.jp.games[s.k] || 0}</td>`).join('')}<td>${h.jp.total}</td></tr>`,
        )
        .join('') +
      '</table>';
    return;
  }
  const H = 240,
    m = { l: 44, r: 20, t: 10, b: 26 },
    iw = W - m.l - m.r,
    ih = H - m.t - m.b;
  const ts = hist.map(h => Date.parse(h.date)),
    t0 = ts[0],
    t1 = ts[ts.length - 1] || t0 + 1;
  const ymax = niceMax(Math.max(...hist.flatMap(h => SERIES.map(s => h.jp.games[s.k] || 0))));
  const X = t => m.l + (t1 === t0 ? iw / 2 : ((t - t0) / (t1 - t0)) * iw),
    Y = v => m.t + ih - (v / ymax) * ih;
  let g = '';
  for (let i = 0; i <= 4; i++) {
    const v = (ymax / 4) * i,
      y = Y(v);
    g += svgEl('line', { x1: m.l, x2: W - m.r, y1: y, y2: y, class: 'grid' });
    g += `<text x="${m.l - 6}" y="${y + 4}" class="tick" text-anchor="end">${v}</text>`;
  }
  // 日期標籤：太靠近的就略過（最新一筆一定留），避免手機上疊在一起
  const xs = [];
  for (let i = ts.length - 1; i >= 0; i--)
    if (!xs.length || xs[xs.length - 1][0] - X(ts[i]) >= 40) xs.push([X(ts[i]), md(hist[i].date)]);
  xs.forEach(
    ([x, t]) => (g += `<text x="${x}" y="${H - 6}" class="tick" text-anchor="middle">${t}</text>`),
  );
  SERIES.forEach(s => {
    const pts = hist.map((h, i) => [X(ts[i]), Y(h.jp.games[s.k] || 0)]);
    g += `<path d="M${pts.map(p => p.join(',')).join('L')}" fill="none" stroke="${s.c}" stroke-width="2" stroke-linejoin="round"/>`;
    pts.forEach(
      ([x, y]) => (g += svgEl('circle', { cx: x, cy: y, r: 4, fill: s.c, class: 'ring' })),
    );
  });
  g += `<line id="st-x" class="xhair" y1="${m.t}" y2="${m.t + ih}" x1="-9" x2="-9"/>`;
  g += svgEl('rect', { x: m.l, y: m.t, width: iw, height: ih, fill: 'transparent', id: 'st-hit' });
  box.innerHTML = `<div class="cwrap"><svg width="${W}" height="${H}" role="img" aria-label="各音遊設置店數變化">${g}</svg><div class="ctip" hidden></div></div>`;
  const tip = box.querySelector('.ctip'),
    xh = box.querySelector('#st-x');
  box.querySelector('#st-hit').addEventListener('pointermove', e => {
    const r = e.currentTarget.ownerSVGElement.getBoundingClientRect(),
      px = e.clientX - r.left;
    let i = 0;
    ts.forEach((t, j) => Math.abs(X(t) - px) < Math.abs(X(ts[i]) - px) && (i = j));
    const h = hist[i],
      x = X(ts[i]);
    xh.setAttribute('x1', x);
    xh.setAttribute('x2', x);
    tip.hidden = false;
    tip.innerHTML =
      `<b>${h.date}</b>` +
      [...SERIES]
        .sort((a, b) => (h.jp.games[b.k] || 0) - (h.jp.games[a.k] || 0))
        .map(
          s =>
            `<div><i style="background:${s.c}"></i>${s.name}<span>${h.jp.games[s.k] || 0}</span></div>`,
        )
        .join('');
    tip.style.left = Math.min(x + 10, W - 170) + 'px';
    tip.style.top = '8px';
  });
  box.querySelector('#st-hit').addEventListener('pointerleave', () => {
    tip.hidden = true;
    xh.setAttribute('x1', -9);
    xh.setAttribute('x2', -9);
  });
}

/* ---- 長條：各都道府縣（含台灣）有這款遊戲的機廳數 ---- */
function drawBars(box, W) {
  const s = SERIES.find(x => x.k === statsUI.game),
    color = s ? s.c : '#7a6fd0';
  const cnt = {};
  DATA.forEach(d => {
    if (!statsUI.game || d.g.includes(statsUI.game)) cnt[d.p] = (cnt[d.p] || 0) + 1;
  });
  const all = Object.entries(cnt).sort((a, b) => b[1] - a[1]),
    rows = statsUI.allRegions ? all : all.slice(0, 15);
  if (statsUI.table) {
    box.innerHTML =
      `<table class="stable"><tr><th>#</th><th>地區</th><th>機廳數</th></tr>` +
      all.map(([p, n], i) => `<tr><td>${i + 1}</td><td>${esc(p)}</td><td>${n}</td></tr>`).join('') +
      '</table>';
    return;
  }
  const lw = 64,
    vw = 40,
    bh = 18,
    rh = bh + 6,
    iw = W - lw - vw,
    max = rows.length ? rows[0][1] : 1,
    H = rows.length * rh + 4;
  let g = '';
  rows.forEach(([p, n], i) => {
    const y = i * rh + 2,
      w = Math.max(2, (n / max) * iw),
      r = Math.min(4, w / 2);
    g += `<g class="bar" data-tip="${esc(p)}：${s ? s.name + ' ' : ''}${n} 間">
      <text x="${lw - 8}" y="${y + bh - 4}" class="blabel" text-anchor="end">${esc(prefShort(p))}</text>
      <path d="M${lw},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${bh - 2 * r}a${r},${r} 0 0 1 -${r},${r}h-${w - r}z" fill="${color}"/>
      <text x="${lw + w + 6}" y="${y + bh - 4}" class="tick">${n}</text>
      <rect x="0" y="${y - 3}" width="${W}" height="${rh}" fill="transparent"/></g>`;
  });
  box.innerHTML =
    `<div class="cwrap"><svg width="${W}" height="${H}" role="img" aria-label="各都道府縣機廳數">${g}</svg><div class="ctip" hidden></div></div>` +
    (all.length > 15
      ? `<button class="chip" id="st-more">${statsUI.allRegions ? '只看前 15 名' : `顯示全部 ${all.length} 個地區`}</button>`
      : '');
  const tip = box.querySelector('.ctip');
  box.querySelectorAll('.bar').forEach(b => {
    b.addEventListener('pointermove', e => {
      const r = box.querySelector('svg').getBoundingClientRect();
      tip.hidden = false;
      tip.textContent = b.dataset.tip;
      tip.style.left = Math.min(e.clientX - r.left + 12, W - 170) + 'px';
      tip.style.top = e.clientY - r.top - 34 + 'px';
    });
    b.addEventListener('pointerleave', () => (tip.hidden = true));
  });
  const more = box.querySelector('#st-more');
  if (more)
    more.onclick = () => {
      statsUI.allRegions = !statsUI.allRegions;
      drawBars(box, W);
    };
}
