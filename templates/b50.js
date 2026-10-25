/* 🎵 B50：書籤工具從 maimai DX NET 帶回來的成績，配上 songs.json 的定數算 Rating（舊曲 B35＋新曲 B15）。
   成績存在這個瀏覽器（localStorage 'maimai:mai'）；登入時另存一份到帳號（account.js）。
   這個檔案只定義函式，在 app.js 之前載入。 */

// 書籤工具把成績放在網址 #mai=…；app.js 一載入就會改寫網址，所以先在這裡記下來
const MAI_IMPORT = new URLSearchParams(location.hash.slice(1)).get('mai');
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
const mai = { songs: null, loading: null };

const rankOf = ach => RANKS.find(r => ach >= r[0]);
// ALL PERFECT 以上每首 +1
const chartRating = (c, ach, fc) =>
  Math.floor((c * rankOf(ach)[1] * Math.min(ach, 100.5)) / 100) + (/^ap/.test(fc) ? 1 : 0);

function loadSongs() {
  if (!mai.loading)
    mai.loading = fetch('songs.json')
      .then(r => r.json())
      .then(d => {
        const idx = new Map();
        for (const s of d.songs) if (!idx.has(s[0] + '|' + s[1])) idx.set(s[0] + '|' + s[1], s);
        return (mai.songs = { ...d, idx });
      })
      .catch(e => {
        mai.loading = null;
        throw e;
      });
  return mai.loading;
}

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
  return { b15, b35, new15: sum(b15), old35: sum(b35), total: sum(b15) + sum(b35), unknown };
}

function b50RowHTML(r, i) {
  const rank = rankOf(r.ach)[2];
  return `<div class="b50-row">
    <span class="b50-no">${i + 1}</span>
    <img class="b50-cover" loading="lazy" alt="" src="${r.img ? COVER + esc(r.img) : 'icon.svg'}">
    <div class="b50-info"><div class="b50-title">${esc(r.title)}</div>
      <div class="b50-meta"><span class="b50-diff" style="background:${DIFF_COLORS[r.diff]}">${DIFF_NAMES[r.diff]}</span>
      ${r.kind === 'dx' ? 'DX' : 'STD'} · 定數 ${r.est ? '≈' : ''}${r.c.toFixed(1)}${r.fc ? ` · <b>${FC_LABEL[r.fc] || ''}</b>` : ''}</div></div>
    <div class="b50-score"><b>${r.ach.toFixed(4)}%</b><small>${rank} · <b>${r.ra}</b></small></div>
  </div>`;
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

function renderB50(el) {
  const data = LS.get('mai', null);
  if (!data) {
    el.innerHTML = `<div class="b50-empty">還沒有成績。照下面的步驟從 maimai DX NET 匯入，就能看到你的 B50。</div>${guideHTML(true)}`;
    bindGuide(el);
    return;
  }
  el.innerHTML = '<div class="empty">載入定數資料…</div>';
  loadSongs()
    .then(S => {
      if (state.view !== 'b50') return;
      const r = computeB50(data, S);
      const when = new Date(data.at).toLocaleString('zh-TW', { hour12: false });
      const diff = data.rating ? r.total - data.rating : 0;
      el.innerHTML = `
      <div class="b50-head">
        <div><div class="b50-name">${esc(data.name)}</div><small>官網 Rating ${data.rating || '—'} · 更新於 ${esc(when)}</small></div>
        <div class="b50-total"><b>${r.total}</b><small>舊曲 ${r.old35} ＋ 新曲 ${r.new15}</small></div>
      </div>
      ${
        diff
          ? `<p class="cq-hint">和官網差 ${diff > 0 ? '+' : ''}${diff}：標「≈」的譜面定數還沒公布，是用等級估的。</p>`
          : ''
      }
      <h3 class="b50-h">新曲 B15 <small>${r.b15.length} 首</small></h3>${r.b15.map(b50RowHTML).join('')}
      <h3 class="b50-h">舊曲 B35 <small>${r.b35.length} 首</small></h3>${r.b35.map(b50RowHTML).join('')}
      ${guideHTML(false)}
      <p class="cq-hint">定數資料：arcade-songs（更新 ${esc(S.updated)}）${
        r.unknown.length ? ` · ${r.unknown.length} 個譜面找不到定數，沒有算進去` : ''
      }</p>`;
      bindGuide(el);
    })
    .catch(() => (el.innerHTML = '<div class="empty">定數資料載入失敗（需要網路）</div>'));
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
  LS.set('mai', data);
  saveMaiCloud(data);
  toast(`已匯入 ${data.scores.length} 個成績`);
  state.view = 'b50';
  renderStatusRow();
  render();
});
