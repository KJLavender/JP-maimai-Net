/* 🏅 B50：成績配上 songs.json 的定數算 Rating（舊曲 B35＋新曲 B15），加上 📈 推分建議、📉 Rating 紀錄。
   成績存在這個瀏覽器（localStorage 'maimai:mai'）；登入時另存一份到帳號（account.js）。
   成績格式：{v:1, at, name, rating, scores:[[歌名, 'dx'|'std', 難度0-4, 達成率, fc, fs]], new:[歌名|種類]|null, hist:[[at, rating]]}
   這個檔案只定義函式，在 mai.js 之後、app.js 之前載入。 */

// 書籤工具把成績放在網址 #mai=…；app.js 一載入就會改寫網址，所以先在這裡記下來
const MAI_IMPORT = new URLSearchParams(location.hash.slice(1)).get('mai');

function computeB50(data, S) {
  const fresh = data.new ? new Set(data.new) : null,
    newVer = new Set(S.new),
    rows = [],
    unknown = [];
  for (const [title, kind, diff, ach, fc, fs] of data.scores) {
    const s = S.idx.get(title + '|' + kind),
      c = s && s[4][diff];
    if (c == null) {
      unknown.push(title);
      continue;
    }
    rows.push({
      s,
      title,
      kind,
      diff,
      ach,
      fc,
      fs,
      c,
      est: !!(s[5] & (1 << diff)),
      img: s[3],
      isNew: fresh ? fresh.has(title + '|' + kind) : newVer.has(s[2]),
      ra: chartRating(c, ach, fc),
    });
  }
  const top = (a, n) => a.sort((x, y) => y.ra - x.ra || y.ach - x.ach).slice(0, n);
  const sum = a => a.reduce((t, r) => t + r.ra, 0);
  const b15 = top(
      rows.filter(r => r.isNew),
      15,
    ),
    b35 = top(
      rows.filter(r => !r.isNew),
      35,
    );
  return { rows, b15, b35, new15: sum(b15), old35: sum(b35), total: sum(b15) + sum(b35), unknown };
}

// 📈 推分建議（與 mai-bot /up 相同）：差一點就到下一個評級、而且推上去總 Rating 會漲的譜面
function suggestions(r, limit = 10) {
  const inB50 = new Set([...r.b15, ...r.b35]),
    floor = {
      true: r.b15.length === 15 ? r.b15[14].ra : 0,
      false: r.b35.length === 35 ? r.b35[34].ra : 0,
    },
    picks = [];
  for (const row of r.rows) {
    let best = null;
    for (const [t, k, name] of RANKS.filter(x => x[0] > row.ach).slice(-2)) {
      const nr = rawRating(row.c, t, k) + (/^ap/.test(row.fc) ? 1 : 0),
        gain = nr - (inB50.has(row) ? row.ra : floor[row.isNew]);
      if (gain <= 0) continue;
      const gap = t - row.ach,
        score = gain / Math.max(gap, 0.05);
      if (!best || score > best.score)
        best = { row, t, name, gap, gain, score, in: inB50.has(row) };
    }
    if (best) picks.push(best);
  }
  return picks.sort((a, b) => b.score - a.score || b.gain - a.gain).slice(0, limit);
}

function b50RowHTML(r, i) {
  const rank = rankOf(r.ach)[2];
  return `<button class="b50-row mai-chart" data-k="${esc(r.title + '|' + r.kind)}" data-d="${r.diff}">
    <span class="b50-no">${i + 1}</span>${coverImg(r.img)}
    <div class="b50-info"><div class="b50-title">${esc(r.title)}</div>
      <div class="b50-meta">${diffTag(r.diff)}
      ${r.kind === 'dx' ? 'DX' : 'STD'} · 定數 ${constText(r.c, r.est)}${r.fc ? ` · <b>${FC_LABEL[r.fc] || ''}</b>` : ''}</div></div>
    <div class="b50-score"><b>${r.ach.toFixed(4)}%</b><small>${rank} · <b>${r.ra}</b></small></div>
  </button>`;
}
function upRowHTML(p, i) {
  const r = p.row;
  return `<button class="b50-row mai-chart" data-k="${esc(r.title + '|' + r.kind)}" data-d="${r.diff}">
    <span class="b50-no">${i + 1}</span>${coverImg(r.img)}
    <div class="b50-info"><div class="b50-title">${esc(r.title)}</div>
      <div class="b50-meta">${diffTag(r.diff)} ${r.kind === 'dx' ? 'DX' : 'STD'} · 定數 ${constText(r.c, r.est)} · ${p.in ? 'B50 內' : '推上去可進 B50'}</div></div>
    <div class="b50-score"><b>${r.ach.toFixed(4)}% → ${p.name}</b><small>差 ${p.gap.toFixed(4)}% · <b>+${p.gain}</b></small></div>
  </button>`;
}

function histSVG(h) {
  const W = 600,
    H = 180,
    P = 24,
    vs = h.map(x => x[1]),
    lo = Math.min(...vs) - 10,
    hi = Math.max(...vs) + 10,
    xy = (v, i) => [
      P + ((W - 2 * P) * i) / Math.max(h.length - 1, 1),
      P + (H - 2 * P) * (1 - (v - lo) / (hi - lo)),
    ];
  const pts = vs
    .map((v, i) =>
      xy(v, i)
        .map(n => n.toFixed(1))
        .join(','),
    )
    .join(' ');
  return `<svg class="mai-hist" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rating 走勢">
    <polyline points="${pts}" fill="none" stroke="var(--amber)" stroke-width="3" stroke-linejoin="round"/>
    ${vs.map((v, i) => `<circle cx="${xy(v, i)[0]}" cy="${xy(v, i)[1]}" r="4" fill="var(--amber)"/>`).join('')}
  </svg>`;
}
function histHTML(data) {
  const h = (data.hist || []).filter(x => x[1]);
  if (!h.length) return '<div class="empty">還沒有紀錄。每次更新成績都會記一筆官網 Rating。</div>';
  const day = t => new Date(t).toLocaleDateString('zh-TW');
  return `${h.length > 1 ? histSVG(h.slice(-30)) : ''}
    <p class="cq-hint">共 ${h.length} 筆，從 ${h[0][1]} 到 ${h[h.length - 1][1]}（${h[h.length - 1][1] - h[0][1] >= 0 ? '+' : ''}${h[h.length - 1][1] - h[0][1]}）</p>
    <div class="mai-log">${h
      .slice(-10)
      .reverse()
      .map((x, i, a) => {
        const d = a[i + 1] ? x[1] - a[i + 1][1] : 0;
        return `<div><span>${esc(day(x[0]))}</span><b>${x[1]}</b><small>${d ? (d > 0 ? '+' : '') + d : ''}</small></div>`;
      })
      .join('')}</div>`;
}

const bookmarkletCode = () =>
  `javascript:(function(d){var s=d.createElement('script');s.src='${location.origin}/bookmarklet.js?v='+Date.now();d.body.append(s)})(document)`;
function guideHTML(open) {
  return `<details class="b50-guide"${open ? ' open' : ''}><summary>🔖 用書籤工具${open ? '匯入' : '更新'}成績</summary>
    <ol>
      <li><b>電腦（Chrome）</b>：把這個按鈕拖到書籤列 → <a class="btn small b50-bm" href="${esc(bookmarkletCode())}">🎵 音GO 更新成績</a><br>
        <b>手機</b>：按 <button class="btn ghost small" id="b50-copy">📋 複製書籤程式碼</button>，隨便新增一個書籤，名稱改「音GO」、網址整個換成剛剛複製的程式碼。</li>
      <li>打開 <a href="https://maimaidx-eng.com/maimai-mobile/" target="_blank" rel="noopener">maimai DX NET</a> 並登入。</li>
      <li>在 maimai DX NET 的頁面上點這個書籤（手機在網址列打「音GO」再點書籤），讀完會自動回到這裡。</li>
    </ol>
    <p class="cq-hint">只會讀你自己的成績；帳號密碼只在官網輸入，不會經過音GO。成績存在這個瀏覽器，登入音GO 後會同步到你的帳號。</p>
  </details>`;
}
function bindGuide(el) {
  const c = el.querySelector('#b50-copy');
  if (c)
    c.onclick = async () => {
      try {
        await navigator.clipboard.writeText(bookmarkletCode());
        toast('已複製書籤程式碼');
      } catch (_) {
        prompt('複製這段書籤程式碼：', bookmarkletCode());
      }
    };
  const bm = el.querySelector('.b50-bm');
  if (bm)
    bm.onclick = e => {
      e.preventDefault();
      toast('這是書籤：請拖到書籤列，到 maimai DX NET 再點');
    };
}

const B50_MODES = [
  ['list', '🏅 B50'],
  ['up', '📈 推分建議'],
  ['log', '📉 Rating 紀錄'],
];
function renderB50(el, S) {
  const data = LS.get('mai', null);
  if (!data) {
    el.innerHTML = `<div class="b50-empty">還沒有成績。照下面的步驟從 maimai DX NET 匯入，就能看到你的 B50。</div>${guideHTML(true)}`;
    bindGuide(el);
    return;
  }
  const mode = (mai.b50mode = mai.b50mode || 'list'),
    r = computeB50(data, S),
    when = new Date(data.at).toLocaleString('zh-TW', { hour12: false }),
    diff = data.rating ? r.total - data.rating : 0;
  let body;
  if (mode === 'up') {
    const ps = suggestions(r);
    body = `<p class="cq-hint">差一點就到下一個評級、推上去總 Rating 會漲的譜面（漲幅／差距排序）。點譜面看各評級的 Rating。</p>
      ${ps.length ? ps.map(upRowHTML).join('') : '<div class="empty">目前沒有推分建議</div>'}`;
  } else if (mode === 'log') body = histHTML(data);
  else
    body = `${
      diff
        ? `<p class="cq-hint">和官網差 ${diff > 0 ? '+' : ''}${diff}：標「≈」的譜面定數還沒公布，是用等級估的。</p>`
        : ''
    }
      <h3 class="b50-h">新曲 B15 <small>${r.b15.length} 首</small></h3>${r.b15.map(b50RowHTML).join('')}
      <h3 class="b50-h">舊曲 B35 <small>${r.b35.length} 首</small></h3>${r.b35.map(b50RowHTML).join('')}`;
  el.innerHTML = `
    <div class="b50-head">
      <div><div class="b50-name">${esc(data.name)}</div><small>官網 Rating ${data.rating || '—'} · 更新於 ${esc(when)}</small></div>
      <div class="b50-total"><b>${r.total}</b><small>舊曲 ${r.old35} ＋ 新曲 ${r.new15}</small></div>
    </div>
    <div class="chips mai-modes">${B50_MODES.map(
      ([m, n]) =>
        `<span class="chip rad" data-m="${m}" data-on="${m === mode ? 1 : 0}">${n}</span>`,
    ).join('')}</div>
    ${body}
    ${guideHTML(false)}
    <p class="cq-hint">定數資料：arcade-songs（更新 ${esc(S.updated)}）${
      r.unknown.length ? ` · ${r.unknown.length} 個譜面找不到定數，沒有算進去` : ''
    }</p>`;
  el.querySelectorAll('.mai-modes .chip').forEach(
    c =>
      (c.onclick = () => {
        mai.b50mode = c.dataset.m;
        renderB50(el, S);
      }),
  );
  bindCharts(el);
  bindGuide(el);
}

// 存新成績：順便記一筆 Rating 紀錄（同一次更新不重複記）
function saveMai(data) {
  const old = LS.get('mai', null),
    hist = (data.hist || (old && old.hist) || []).slice();
  if (data.rating && !hist.some(x => x[0] === data.at)) hist.push([data.at, data.rating]);
  data.hist = hist.sort((a, b) => a[0] - b[0]).slice(-200);
  LS.set('mai', data);
  saveMaiCloud(data);
}

async function gunzip64(s) {
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/'));
  const z = new Blob([Uint8Array.from(bin, c => c.charCodeAt(0))])
    .stream()
    .pipeThrough(new DecompressionStream('gzip'));
  return new Response(z).text();
}
addEventListener('DOMContentLoaded', async () => {
  if (!MAI_IMPORT) return;
  let data;
  try {
    data = JSON.parse(await gunzip64(MAI_IMPORT));
    if (!Array.isArray(data.scores) || typeof data.name !== 'string') throw 0;
  } catch (_) {
    return toast('成績資料格式不對，請在 maimai DX NET 重新按一次書籤');
  }
  // 網址可能是別人傳來的連結：先問過再覆蓋
  if (
    !confirm(
      `要匯入「${data.name}」的 ${data.scores.length} 個成績嗎？（官網 Rating ${data.rating}）`,
    )
  )
    return;
  delete data.hist; // 紀錄只認這台／帳號自己累積的，不吃網址帶來的
  saveMai(data);
  toast(`已匯入 ${data.scores.length} 個成績`);
  state.view = 'b50';
  mai.tab = 'b50';
  renderStatusRow();
  render();
});
