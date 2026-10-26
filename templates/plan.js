/* 🗓️ 遠征行程規劃：選日期、出發時間、末班車，從「已選路線」或「目前篩選結果」排出一天的機廳行程。
   依那天（星期幾）的營業時間排，每一站都挑「最快能開始玩」的店（移動＋等開門最少），
   最後提醒要在末班車前離開。移動時間用直線距離估算（電車 / 步行），實際請以導航為準。
   這個檔案只定義函式，在 app.js 之前載入。 */

const PLAN_DEFAULT = {
  date: '',
  start: '11:00',
  end: '23:30',
  stay: 60,
  stops: 5,
  move: 'train',
};
const PLAN_STAY = [30, 45, 60, 90, 120];
const PLAN_STOPS = [2, 3, 4, 5, 6, 9];
// 每公里幾分鐘＋固定的轉乘／走到車站時間；直線距離 × 1.3 當作實際路程
const PLAN_MOVE = {
  train: { name: '🚃 電車', perKm: 2.4, base: 12 },
  walk: { name: '🚶 步行', perKm: 13, base: 0 },
};
const WD_NAMES = '日一二三四五六';

const hm = s => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(s || '');
  return m ? +m[1] * 60 + +m[2] : null;
};
// 分鐘 → 「23:30」；過了半夜顯示「翌 01:00」
const clock = t =>
  (t >= 1440 ? '翌 ' : '') +
  String(Math.floor((t % 1440) / 60)).padStart(2, '0') +
  ':' +
  String(Math.round(t % 60)).padStart(2, '0');
// 搭電車時，近的直接走路比較快
function moveOf(km, mode) {
  const t = m => (km < 0.05 ? 0 : Math.round(PLAN_MOVE[m].base + km * 1.3 * PLAN_MOVE[m].perKm)),
    walk = t('walk');
  return mode === 'train' && t('train') < walk
    ? { m: t('train'), how: 'train' }
    : { m: walk, how: 'walk' };
}
// 兩個 {y, x}（店或起點）之間的直線距離
const kmBetween = (a, b) => distKm({ lat: a.y, lng: a.x }, b);
const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/* 某間店在那天（wd）能玩的時段，以當天 0:00 起算的分鐘；前一天營業到凌晨的部分也算進來 */
function openWindows(d, wd) {
  const of = h => (allDay(h) ? [[0, 1440]] : parseHours(h) || []);
  const out = of(dayHours(d, wd)).map(w => w.slice());
  for (const [s, e] of of(dayHours(d, (wd + 6) % 7)))
    if (e > 1440 && !allDay(dayHours(d, (wd + 6) % 7))) out.push([s - 1440, e - 1440]);
  return out.sort((a, b) => a[0] - b[0]);
}
const hasHours = d => !!(d.w || parseHours(d.h));

/* 排行程：貪婪法，每一步挑「最快能開始玩」的店；時間不夠待滿就待到打烊／末班車（至少 30 分） */
function planTrip(pool, o) {
  const wd = new Date(o.date + 'T12:00').getDay(),
    start = hm(o.start),
    end = hm(o.end) <= start ? hm(o.end) + 1440 : hm(o.end),
    minStay = Math.min(30, o.stay),
    stops = [];
  let t = start,
    pos = o.origin ? { y: o.origin.lat, x: o.origin.lng } : null,
    left = pool.filter(hasHours);
  while (stops.length < o.stops && left.length) {
    let best = null;
    for (const d of left) {
      const km = pos ? kmBetween(pos, d) : 0,
        mv = pos ? moveOf(km, o.move) : { m: 0 },
        arrive = t + mv.m;
      for (const [s, e] of openWindows(d, wd)) {
        const play = Math.max(arrive, s),
          leave = Math.min(play + o.stay, e, end);
        if (leave - play < minStay) continue;
        // 第一站沒有起點時：挑最早開門的，同時間挑附近店最多的（之後比較好排）
        const cost = play - t + (pos ? 0 : -nearCount(d, pool) / 100);
        if (!best || cost < best.cost) best = { d, km, mv, arrive, play, leave, close: e, cost };
        break;
      }
    }
    if (!best) break;
    stops.push(best);
    t = best.leave;
    pos = best.d;
    left = left.filter(x => x !== best.d);
  }
  return { wd, start, end, stops, unknown: pool.length - pool.filter(hasHours).length };
}
const nearCount = (d, pool) => pool.filter(x => x !== d && kmBetween(d, x) < 2).length;

/* 候選店：已選路線（2 間以上）或目前篩選結果；「只看營業中」是看現在，排別天的行程時不套用 */
function planPool(src) {
  if (src === 'route') return state.route.map(id => byId[id]).filter(d => d && 'y' in d);
  const keep = state.openOnly;
  state.openOnly = false;
  const rs = filtered().filter(d => 'y' in d);
  state.openOnly = keep;
  return rs;
}
// 目前的篩選範圍夠小才自動挑店（沒有縣市、地點、搜尋時，全國挑起點沒有意義）
const poolNarrow = () => !!(state.origin || state.pref || state.q || state.favOnly);

function planResultHTML(o, pool) {
  plan.last = [];
  if (!pool.length) return '<div class="empty">沒有可以排的機廳（需要有座標）</div>';
  if (o.src !== 'route' && !poolNarrow())
    return '<div class="empty">先在上面選縣市、輸入地名按「搜尋此地」或按「📍 附近」，再來排行程。</div>';
  const p = planTrip(pool, o);
  if (!p.stops.length)
    return `<div class="empty">${clock(p.start)}～${clock(p.end)} 之間沒有排得進去的機廳（可能都公休或還沒開門），換個時間或日期試試。</div>`;
  let html = '',
    prev = o.origin ? o.origin.label : null;
  html += `<div class="pl-step pl-mark">🕒 ${clock(p.start)} 出發${prev ? `（${esc(prev)}）` : ''}</div>`;
  p.stops.forEach((x, i) => {
    const d = x.d,
      wait = x.play - x.arrive,
      notes = [];
    if (wait > 0) notes.push(`等開門 ${wait} 分`);
    if (x.leave === x.close) notes.push(`${clock(x.close)} 打烊，待到關門`);
    else if (x.leave === p.end) notes.push('末班車時間到，要離開了');
    if (x.leave - x.play < o.stay) notes.push(`只能玩 ${x.leave - x.play} 分`);
    if (i || o.origin)
      html += `<div class="pl-move">${PLAN_MOVE[x.mv.how].name} 約 ${x.mv.m} 分 · ${x.km.toFixed(1)} km</div>`;
    html += `<div class="pl-step"><span class="pl-no">${i + 1}</span>
      <div class="b50-info"><div class="b50-title">${esc(d.z || d.zg || d.n)}</div>
        <div class="b50-meta">${clock(x.play)}～${clock(x.leave)} · 當天 ${esc(dayHours(d, p.wd) || '公休')}</div>
        ${notes.length ? `<div class="pl-warn">⚠ ${notes.join(' · ')}</div>` : ''}</div></div>`;
  });
  const last = p.stops[p.stops.length - 1],
    spare = p.end - last.leave;
  html += `<div class="pl-step pl-mark${spare < 30 ? ' pl-late' : ''}">🚉 末班車 ${clock(p.end)} · 最後一站 ${clock(last.leave)} 離開${
    spare < 30
      ? `，只剩 ${spare} 分，先查好車次、提早出發`
      : `，還有 ${Math.floor(spare / 60) ? Math.floor(spare / 60) + ' 小時 ' : ''}${spare % 60} 分緩衝`
  }</div>`;
  const skipped = [
    p.stops.length < Math.min(o.stops, pool.length) ? `只排得進 ${p.stops.length} 站` : '',
    p.unknown ? `${p.unknown} 間沒有營業時間，沒有排進去` : '',
  ].filter(Boolean);
  if (skipped.length) html += `<p class="cq-hint">${skipped.join(' · ')}</p>`;
  plan.last = p.stops.map(x => x.d.i);
  return html;
}

const plan = { last: [] };
function openPlan() {
  const o = { ...PLAN_DEFAULT, ...LS.get('plan', {}) };
  if (!o.date || o.date < todayISO()) o.date = todayISO();
  o.src = state.route.length >= 2 ? 'route' : 'filter';
  const draw = () => {
    o.origin = state.origin;
    const pool = planPool(o.src),
      wd = new Date(o.date + 'T12:00').getDay();
    const radio = (key, items) =>
      items
        .map(
          ([v, n]) =>
            `<span class="chip rad" data-k="${key}" data-v="${v}" data-on="${String(o[key]) === String(v) ? 1 : 0}">${n}</span>`,
        )
        .join('');
    const d = ensureDialog(
      'plan',
      `<h2>🗓️ 排遠征行程</h2>
      <div class="mai-frow"><label>日期</label><div class="mai-range"><input type="date" id="pl-date" value="${esc(o.date)}"> <b>（${WD_NAMES[wd]}）</b></div></div>
      <div class="mai-frow"><label>時間</label><div class="mai-range"><input type="time" id="pl-start" value="${esc(o.start)}"> 出發 ～ <input type="time" id="pl-end" value="${esc(o.end)}"> 末班車</div></div>
      <div class="mai-frow"><label>每間待</label><div class="chips">${radio(
        'stay',
        PLAN_STAY.map(m => [m, m + ' 分']),
      )}</div></div>
      <div class="mai-frow"><label>最多</label><div class="chips">${radio(
        'stops',
        PLAN_STOPS.map(n => [n, n + ' 站']),
      )}</div></div>
      <div class="mai-frow"><label>移動</label><div class="chips">${radio(
        'move',
        Object.entries(PLAN_MOVE).map(([k, m]) => [k, m.name]),
      )}</div></div>
      <div class="mai-frow"><label>從哪裡挑</label><div class="chips">${radio('src', [
        ...(state.route.length >= 2 ? [['route', `🧭 已選路線（${state.route.length} 間）`]] : []),
        ['filter', `📋 目前篩選結果（${planPool('filter').length} 間）`],
      ])}</div></div>
      <p class="dlg-hint">${o.origin ? `起點：${esc(o.origin.label)}。` : '沒有設定起點（按「📍 附近」或「搜尋此地」可以設定），第一站挑最早開門的店。'}移動時間是用直線距離估的，實際以導航為準。</p>
      <div id="pl-res">${planResultHTML(o, pool)}</div>
      <div class="cq-actions"><button class="btn small" id="pl-apply"${plan.last.length ? '' : ' disabled'}>🧭 套用到路線並導航</button></div>`,
    );
    d.classList.add('dlg-wide');
    const save = () => {
      // 候選來源不記：每次打開時有選路線就用路線
      const { origin, src, ...keep } = o;
      LS.set('plan', keep);
      draw();
    };
    d.querySelectorAll('[data-k]').forEach(
      c =>
        (c.onclick = () => {
          const v = c.dataset.v;
          o[c.dataset.k] = isNaN(+v) ? v : +v;
          save();
        }),
    );
    d.querySelector('#pl-date').onchange = e => {
      o.date = e.target.value || todayISO();
      save();
    };
    d.querySelector('#pl-start').onchange = e => {
      if (hm(e.target.value) != null) o.start = e.target.value;
      save();
    };
    d.querySelector('#pl-end').onchange = e => {
      if (hm(e.target.value) != null) o.end = e.target.value;
      save();
    };
    d.querySelector('#pl-apply').onclick = () => {
      state.route = plan.last.slice(0, MAX_ROUTE);
      LS.set('route', state.route);
      d.close();
      renderRouteBar();
      render();
      document.getElementById('routestart').click();
    };
    if (!d.open) d.showModal();
  };
  draw();
}
