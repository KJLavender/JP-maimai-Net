/* 🏆 機廳制霸：標記「去過」的店、47 都道府縣制霸地圖、匯出圖片、備份／還原。
   紀錄只存在使用者自己的瀏覽器（localStorage 'maimai:visited'），不會上傳到任何地方。
   這個檔案只定義函式，在 app.js 之前載入；用到的 DATA、state、LS 等在呼叫時才取。 */

/* 都道府縣方格地圖：[欄, 列]（概略的地理位置，不是精確地圖） */
const PREF_TILES = {
  北海道: [12, 0],
  青森県: [12, 2],
  秋田県: [11, 3],
  岩手県: [12, 3],
  山形県: [11, 4],
  宮城県: [12, 4],
  石川県: [8, 5],
  富山県: [9, 5],
  新潟県: [10, 5],
  福島県: [11, 5],
  福井県: [7, 6],
  岐阜県: [8, 6],
  長野県: [9, 6],
  群馬県: [10, 6],
  栃木県: [11, 6],
  茨城県: [12, 6],
  山口県: [1, 7],
  島根県: [2, 7],
  鳥取県: [3, 7],
  兵庫県: [4, 7],
  京都府: [5, 7],
  滋賀県: [6, 7],
  愛知県: [8, 7],
  山梨県: [9, 7],
  埼玉県: [10, 7],
  東京都: [11, 7],
  千葉県: [12, 7],
  佐賀県: [0, 8],
  福岡県: [1, 8],
  広島県: [2, 8],
  岡山県: [3, 8],
  大阪府: [4, 8],
  奈良県: [5, 8],
  三重県: [6, 8],
  静岡県: [9, 8],
  神奈川県: [10, 8],
  長崎県: [0, 9],
  熊本県: [1, 9],
  大分県: [2, 9],
  愛媛県: [3, 9],
  香川県: [4, 9],
  和歌山県: [5, 9],
  鹿児島県: [1, 10],
  宮崎県: [2, 10],
  高知県: [3, 10],
  徳島県: [4, 10],
  沖縄県: [0, 11],
};
const TILE_COLS = 13,
  TILE_ROWS = 12;
/* 達成比例 → 顏色（單一色相、由暗到亮；深色背景上越亮代表去過越多，已用 dataviz 驗證器檢查） */
const CONQ_STEPS = [
  { min: 1, c: '#86b6ef', ink: '#0d1b33', label: '全制霸' },
  { min: 0.5, c: '#3987e5', ink: '#fff', label: '50%+' },
  { min: 0.25, c: '#256abf', ink: '#fff', label: '25%+' },
  { min: 0, c: '#184f95', ink: '#fff', label: '去過' },
];
const prefShort = p => (p === '北海道' ? p : p.replace(/[都府県]$/, ''));
const conqStep = r => CONQ_STEPS.find(s => r >= s.min);

function conquestStats() {
  const per = {};
  DATA.forEach(d => {
    const s = (per[d.p] = per[d.p] || { total: 0, visited: 0 });
    s.total++;
    if (state.visited.has(d.i)) s.visited++;
  });
  const jpPrefs = Object.keys(PREF_TILES);
  return {
    per,
    shops: DATA.filter(d => state.visited.has(d.i)).length,
    prefs: jpPrefs.filter(p => per[p] && per[p].visited > 0).length,
    prefTotal: jpPrefs.length,
    tw: per['台灣'] ? per['台灣'].visited : 0,
  };
}

window.toggleVisited = function (idx, el) {
  const id = DATA[idx].i;
  if (state.visited.has(id)) state.visited.delete(id);
  else state.visited.add(id);
  LS.set('visited', [...state.visited]);
  markChanged('v', id); // Google 同步用（有開同步就自動上傳）
  if (el) {
    const on = state.visited.has(id);
    el.dataset.on = on ? '1' : '0';
    el.textContent = on ? '✅ 去過' : '🏁 標記去過';
  }
};
function visitedBtnHTML(d) {
  const on = state.visited.has(d.i);
  return `<button class="chip vbtn" data-on="${on ? 1 : 0}" onclick="toggleVisited(${d._idx},this)">${on ? '✅ 去過' : '🏁 標記去過'}</button>`;
}

function renderConquest(el) {
  const s = conquestStats();
  const tiles = Object.entries(PREF_TILES)
    .map(([p, [c, r]]) => {
      const t = s.per[p] || { total: 0, visited: 0 };
      const st = t.visited ? conqStep(t.visited / t.total) : null;
      const style =
        `grid-column:${c + 1};grid-row:${r + 1}` +
        (st ? `;background:${st.c};color:${st.ink}` : '');
      return `<button class="ctile${st ? ' on' : ''}" style="${style}" data-p="${esc(p)}"
        title="${esc(p)}：去過 ${t.visited} / ${t.total} 間"><b>${esc(prefShort(p))}</b><span>${t.visited}/${t.total}</span></button>`;
    })
    .join('');
  const legend =
    `<span><i class="sw none"></i>未去過</span>` +
    [...CONQ_STEPS]
      .reverse()
      .map(x => `<span><i class="sw" style="background:${x.c}"></i>${x.label}</span>`)
      .join('');
  el.innerHTML = `
  <div class="cq-tiles">
    <div class="stat"><div class="sv">${s.shops}</div><div class="sl">去過的機廳</div></div>
    <div class="stat"><div class="sv">${s.prefs}<small> / ${s.prefTotal}</small></div><div class="sl">制霸都道府縣</div></div>
    ${s.tw ? `<div class="stat"><div class="sv">${s.tw}</div><div class="sl">台灣去過</div></div>` : ''}
  </div>
  <div class="cq-map" style="grid-template-columns:repeat(${TILE_COLS},1fr);grid-template-rows:repeat(${TILE_ROWS},1fr)">${tiles}</div>
  <div class="cq-legend">${legend}</div>
  <p class="cq-hint">在清單或地圖的店家上按「🏁 標記去過」就會記下來；點縣名可以看那個縣的機廳。</p>
  <div class="cq-actions"><button class="btn small" id="cq-export">📷 匯出圖片</button></div>
  ${syncPanelHTML()}
  <details class="cq-more"><summary>不用 Google 帳號？用備份代碼搬紀錄</summary>
    <p class="cq-hint">紀錄平常只存在這個瀏覽器。換手機時先按「備份」複製代碼，到新手機按「還原」貼上。</p>
    <div class="cq-actions">
      <button class="btn ghost small" id="cq-backup">💾 備份</button>
      <button class="btn ghost small" id="cq-restore">📥 還原</button>
    </div>
  </details>`;
  el.querySelectorAll('.ctile').forEach(
    b =>
      (b.onclick = () => {
        state.pref = b.dataset.p;
        state.view = 'list';
        renderStatusRow();
        render();
        scrollTo(0, 0);
      }),
  );
  el.querySelector('#cq-export').onclick = exportConquestImage;
  el.querySelector('#cq-backup').onclick = backupVisited;
  el.querySelector('#cq-restore').onclick = restoreVisited;
  bindSyncPanel(el);
}

/* ---- 備份／還原：把「去過」和「收藏」轉成一串代碼，換手機時貼上 ---- */
const b64 = {
  enc: s => btoa(String.fromCharCode(...new TextEncoder().encode(s))),
  dec: s => new TextDecoder().decode(Uint8Array.from(atob(s), c => c.charCodeAt(0))),
};
function backupCode() {
  return 'MJM1:' + b64.enc(JSON.stringify({ visited: [...state.visited], favs: [...state.favs] }));
}
async function backupVisited() {
  const code = backupCode();
  try {
    await navigator.clipboard.writeText(code);
    toast('已複製備份代碼，到新手機按「還原」貼上');
  } catch (_) {
    prompt('複製這串備份代碼：', code);
  }
}
function applyBackup(code) {
  const m = /^MJM1:(.+)$/.exec((code || '').trim());
  if (!m) return false;
  let o;
  try {
    o = JSON.parse(b64.dec(m[1]));
  } catch (_) {
    return false;
  }
  const known = id => byId[id]; // 店已下架的 ID 就略過
  (o.visited || []).filter(known).forEach(id => (state.visited.add(id), markChanged('v', id)));
  (o.favs || []).filter(known).forEach(id => (state.favs.add(id), markChanged('f', id)));
  LS.set('visited', [...state.visited]);
  LS.set('favs', [...state.favs]);
  return true;
}
function restoreVisited() {
  const code = prompt('貼上備份代碼（會和目前的紀錄合併）：');
  if (code === null) return;
  if (applyBackup(code)) {
    toast(`已還原：去過 ${state.visited.size} 間、收藏 ${state.favs.size} 間`);
    render();
  } else toast('代碼格式不對，請確認有完整複製（以 MJM1: 開頭）');
}

/* ---- 匯出成圖片（1080×1350，適合貼到社群） ---- */
function drawConquest() {
  const s = conquestStats();
  const W = 1080,
    H = 1350,
    cv = document.createElement('canvas');
  cv.width = W;
  cv.height = H;
  const g = cv.getContext('2d'),
    F = '"Noto Sans CJK JP","Hiragino Sans","Yu Gothic UI","Meiryo",system-ui,sans-serif';
  g.fillStyle = '#0d0b1a';
  g.fillRect(0, 0, W, H);
  g.fillStyle = '#eceaff';
  g.font = `800 56px ${F}`;
  g.fillText('我的音遊機廳制霸', 64, 120);
  g.fillStyle = '#9d96c9';
  g.font = `500 30px ${F}`;
  g.fillText(
    `去過 ${s.shops} 間 · 制霸 ${s.prefs} / ${s.prefTotal} 都道府縣${s.tw ? ` · 台灣 ${s.tw} 間` : ''}`,
    64,
    175,
  );
  const cell = 74,
    gap = 6,
    x0 = (W - TILE_COLS * cell) / 2,
    y0 = 240;
  Object.entries(PREF_TILES).forEach(([p, [c, r]]) => {
    const t = s.per[p] || { total: 0, visited: 0 };
    const st = t.visited ? conqStep(t.visited / t.total) : null;
    const x = x0 + c * cell,
      y = y0 + r * cell,
      w = cell - gap;
    g.fillStyle = st ? st.c : '#221c47';
    g.beginPath();
    g.roundRect(x, y, w, w, 10);
    g.fill();
    g.fillStyle = st ? st.ink : '#6b6690';
    g.font = `700 21px ${F}`;
    g.textAlign = 'center';
    g.fillText(prefShort(p), x + w / 2, y + w / 2 + 2);
    g.font = `500 15px ${F}`;
    g.fillText(`${t.visited}/${t.total}`, x + w / 2, y + w / 2 + 24);
    g.textAlign = 'left';
  });
  // 色階說明（跟網頁上的圖例一樣）
  let lx = 64;
  g.font = `500 22px ${F}`;
  [{ c: null, label: '未去過' }, ...[...CONQ_STEPS].reverse()].forEach(x => {
    g.fillStyle = x.c || '#221c47';
    g.beginPath();
    g.roundRect(lx, H - 158, 24, 24, 5);
    g.fill();
    g.fillStyle = '#9d96c9';
    g.fillText(x.label, lx + 32, H - 139);
    lx += 32 + g.measureText(x.label).width + 28;
  });
  g.fillStyle = '#9d96c9';
  g.font = `500 26px ${F}`;
  g.fillText('maimai-japan-map.netlify.app', 64, H - 64);
  return cv;
}
function exportConquestImage() {
  drawConquest().toBlob(async blob => {
    const file = new File([blob], 'maimai-conquest.png', { type: 'image/png' });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: '我的音遊機廳制霸' });
        return;
      } catch (_) {}
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'maimai-conquest.png';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  }, 'image/png');
}
