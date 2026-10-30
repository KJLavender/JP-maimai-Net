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

/* 🎯 目標 Rating：一次推一個評級，每步挑「漲幅／要推的達成率」最划算的，推到目標為止。
   每推一首都重算 B15／B35（推上去的譜面可能擠掉別首），所以漲幅是實際會漲的分數。 */
const GOAL_CAPS = [
  [99.5, 'SS+'],
  [100, 'SSS'],
  [100.5, 'SSS+'],
];
const GOAL_GAPS = [0.5, 1, 2, 99];
function goalPlan(r, target, cap, maxGap) {
  const rows = r.rows.map(x => ({ ...x, from: x.ach })),
    picked = new Map();
  let total = r.total;
  while (total < target && picked.size < 50) {
    // 目前在 B15／B35 裡的譜面，和各組最後一名（推上去的譜面要贏過它才擠得進去）
    const inTop = new Set(),
      floor = {};
    for (const isNew of [true, false]) {
      const n = isNew ? 15 : 35,
        top = rows
          .filter(x => x.isNew === isNew)
          .sort((x, y) => y.ra - x.ra)
          .slice(0, n);
      top.forEach(x => inTop.add(x));
      floor[isNew] = top.length === n ? top[n - 1].ra : 0;
    }
    let best = null;
    for (const row of rows) {
      const next = RANKS.filter(x => x[0] > row.ach && x[0] <= cap).pop();
      if (!next || next[0] - row.from > maxGap) continue;
      const ra = rawRating(row.c, next[0], next[1]) + (/^ap/.test(row.fc) ? 1 : 0),
        gain = ra - (inTop.has(row) ? row.ra : floor[row.isNew]);
      if (gain <= 0) continue;
      const score = gain / Math.max(next[0] - row.ach, 0.05);
      if (!best || score > best.score) best = { row, t: next[0], name: next[2], ra, gain, score };
    }
    if (!best) break;
    best.row.ach = best.t;
    best.row.ra = best.ra;
    total += best.gain;
    const p = picked.get(best.row) || { row: best.row, gain: 0 };
    p.gain += best.gain;
    p.name = best.name;
    p.gap = best.t - best.row.from;
    picked.set(best.row, p);
  }
  return { total, steps: [...picked.values()].sort((a, b) => a.gap - b.gap || b.gain - a.gain) };
}
function goalRowHTML(p, i) {
  const r = p.row;
  return `<button class="b50-row mai-chart" data-k="${esc(r.title + '|' + r.kind)}" data-d="${r.diff}">
    <span class="b50-no">${i + 1}</span>${coverImg(r.img)}
    <div class="b50-info"><div class="b50-title">${esc(r.title)}</div>
      <div class="b50-meta">${diffTag(r.diff)} ${r.kind === 'dx' ? 'DX' : 'STD'} · 定數 ${constText(r.c, r.est)}</div></div>
    <div class="b50-score"><b>${r.from.toFixed(4)}% → ${p.name}</b><small>差 ${p.gap.toFixed(4)}% · <b>+${p.gain}</b></small></div>
  </button>`;
}
function goalHTML(r) {
  const g = (mai.goal = mai.goal || { target: 0, cap: 100, gap: 1, ...LS.get('maiGoal', {}) });
  if (!g.target || g.target <= r.total) g.target = Math.ceil((r.total + 1) / 100) * 100;
  const p = goalPlan(r, g.target, g.cap, g.gap),
    ok = p.total >= g.target;
  return `<div class="mai-dan-bar goal-bar">
      <label>目標 Rating <input id="goal-t" class="mai-input" type="number" inputmode="numeric" min="${r.total + 1}" step="50" value="${g.target}"></label>
      <div class="chips">${GOAL_CAPS.map(([t, n]) => `<span class="chip rad" data-gc="${t}" data-on="${g.cap === t ? 1 : 0}">最高推到 ${n}</span>`).join('')}</div>
      <div class="chips">${GOAL_GAPS.map(x => `<span class="chip rad" data-gg="${x}" data-on="${g.gap === x ? 1 : 0}">${x === 99 ? '差距不限' : `差 ${x}% 以內`}</span>`).join('')}</div>
    </div>
    <p class="mf-msg${ok ? '' : ' err'}">${
      ok
        ? `🎯 推這 <b>${p.steps.length}</b> 首就能從 ${r.total} 到 <b>${p.total}</b>（目標 ${g.target}）`
        : `目前的條件最多推到 ${p.total}，還差 ${g.target - p.total}。試著放寬「最高推到」或「差距」。`
    }</p>
    <p class="cq-hint">由簡單到難排（要推的達成率越少越前面）。只算打過的譜面；點譜面看各評級 Rating。</p>
    ${p.steps.map(goalRowHTML).join('') || '<div class="empty">沒有可以推的譜面</div>'}`;
}
function bindGoal(el, S) {
  const g = mai.goal,
    save = () => {
      LS.set('maiGoal', g);
      renderB50(el, S);
    },
    t = el.querySelector('#goal-t');
  if (!t) return;
  t.onchange = () => {
    g.target = Math.round(+t.value) || 0;
    save();
  };
  el.querySelectorAll('[data-gc]').forEach(
    c => (c.onclick = () => ((g.cap = +c.dataset.gc), save())),
  );
  el.querySelectorAll('[data-gg]').forEach(
    c => (c.onclick = () => ((g.gap = +c.dataset.gg), save())),
  );
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

/* ---- 🤝 好友代碼代抓：送好友申請 → 使用者在官網接受 → 按按鈕抓成績（工作由 mai-bot 的 otogo_worker.py 做） ---- */
const JOB_BUSY = ['queued', 'running'];
const JOB_WAIT = { b50: 10, friend: 1 }; // 同一個帳號兩次工作之間要隔幾分鐘（firestore.rules 也有擋）
const jobMs = t => (t && t.toMillis ? t.toMillis() : t || 0);
const jobLeft = j => (j ? jobMs(j.at) + JOB_WAIT[j.type] * 60000 - Date.now() : 0);
// 排隊超過 2 分鐘還沒人接手：機器人（otogo_worker.py）多半沒在跑
const jobStale = j => !!j && j.status === 'queued' && Date.now() - jobMs(j.at) > 2 * 60000;
function friendInner() {
  if (!acct.user)
    return LS.get('user', null)
      ? '<p class="cq-hint">登入狀態載入中…</p>'
      : `<p class="cq-hint">登入音GO 後輸入好友代碼，音GO 的機器人加你好友就能幫你抓成績，不用書籤。</p>
        <button class="btn" id="mf-login">👤 登入</button>`;
  const j = mai.job;
  if (j === undefined) return '<p class="cq-hint">載入中…</p>';
  const msg =
    j && j.msg ? `<p class="mf-msg${j.status === 'error' ? ' err' : ''}">${esc(j.msg)}</p>` : '';
  if (jobStale(j))
    return `<p class="mf-msg err">🤖 機器人目前沒有回應，可能暫時離線。</p>
      <p class="cq-hint">工作會留著，機器人上線後就會處理（${esc(j.code)}）。急著看成績的話，可以先用下面的書籤工具匯入。</p>`;
  if (j && JOB_BUSY.includes(j.status))
    return `<p class="mf-msg busy">${
      j.status === 'queued'
        ? '⏳ 排隊中…'
        : j.type === 'friend'
          ? '⏳ 正在送出好友申請…'
          : '⏳ 正在抓成績（約 1～2 分鐘）…'
    }</p><p class="cq-hint">可以先去看別的，好了會自動更新。</p>`;
  const left = jobLeft(j),
    wait = left > 0 ? ` disabled title="${Math.ceil(left / 60000)} 分鐘後可以再按"` : '',
    waitHint =
      left > 0 ? `<small class="mf-wait">${Math.ceil(left / 60000)} 分鐘後可以再按</small>` : '',
    change = '<button class="btn ghost small" id="mf-change">換好友代碼</button>';
  // 還沒綁好友代碼：輸入代碼、送好友申請
  if (!j || mai.changeCode || (j.type === 'friend' && j.status === 'error'))
    return `${msg}<p class="cq-hint">好友代碼在 maimai DX NET 的「好友」→「好友代碼」，13 位數字。</p>
      <div class="mf-row"><input id="mf-code" class="mai-input" inputmode="numeric" maxlength="16" placeholder="好友代碼（13 位數字）" value="${esc(LS.get('maiCode', ''))}">
      <button class="btn" id="mf-friend"${wait}>🤝 送出好友申請</button></div>${waitHint}`;
  // 送出了、等使用者在官網接受
  if (j.type === 'friend' && j.status === 'sent')
    return `${msg}<div class="mf-row"><button class="btn" id="mf-b50"${wait}>✅ 我接受了，抓成績</button>${change}</div>${waitHint}`;
  return `${msg}<div class="mf-row"><button class="btn" id="mf-b50"${wait}>🔄 更新 B50</button>${change}</div>${waitHint}
    <p class="cq-hint">好友代碼 ${esc(j.code)}</p>`;
}
const friendHTML = () =>
  acctEnabled()
    ? `<div class="mai-friend" id="mai-friend"><h3 class="b50-h">🤝 用好友代碼自動抓成績</h3>${friendInner()}</div>`
    : '';
function paintFriend() {
  const el = document.getElementById('mai-friend');
  if (!el) return;
  const typed = document.getElementById('mf-code');
  el.outerHTML = friendHTML();
  if (typed && document.getElementById('mf-code'))
    document.getElementById('mf-code').value = typed.value;
  bindFriend();
}
function bindFriend() {
  const $ = id => document.getElementById(id);
  // 冷卻時間到了自動把按鈕打開（剩餘分鐘數每 30 秒更新）
  clearTimeout(mai.waitTimer);
  const left = jobLeft(mai.job);
  if (left > 0 && $('mai-friend'))
    mai.waitTimer = setTimeout(paintFriend, Math.min(left + 200, 30000));
  if ($('mf-login')) $('mf-login').onclick = openLogin;
  if ($('mf-change'))
    $('mf-change').onclick = () => {
      mai.changeCode = true;
      paintFriend();
    };
  if ($('mf-friend'))
    $('mf-friend').onclick = () => {
      const code = $('mf-code').value.replace(/\D/g, '');
      if (code.length !== 13) return toast('好友代碼是 13 位數字');
      sendJob('friend', code);
    };
  if ($('mf-b50')) $('mf-b50').onclick = () => sendJob('b50', mai.job.code);
  // 切回這頁時還在等的工作：確定有在追（之前的追蹤可能因為 15 分鐘到了而停掉）
  if (mai.job && JOB_BUSY.includes(mai.job.status) && !mai.watching) watchJob();
  // 第一次顯示：讀一次目前的工作狀態
  if (acct.user && mai.job === undefined && !mai.jobLoading) {
    mai.jobLoading = true;
    getMaiJob()
      .then(
        j => (mai.job = j),
        () => (mai.job = null),
      )
      .then(() => {
        mai.jobLoading = false;
        paintFriend();
        if (mai.job && JOB_BUSY.includes(mai.job.status)) watchJob();
      });
  }
}
async function sendJob(type, code) {
  try {
    await sendMaiJob(type, code);
  } catch (e) {
    return toast(
      e && e.code === 'permission-denied' ? '按太快了，請過幾分鐘再試' : '送出失敗：' + authMsg(e),
    );
  }
  LS.set('maiCode', code);
  mai.changeCode = false;
  mai.job = { type, code, status: 'queued', at: Date.now() };
  paintFriend();
  watchJob();
}
// 每幾秒看一次工作做完了沒（最多等 15 分鐘）；一次讀取失敗（斷網、分頁在背景）不會讓它停掉
async function watchJob() {
  if (mai.watching) return;
  mai.watching = true;
  const t0 = Date.now();
  try {
    while (acct.user && Date.now() - t0 < 15 * 60000) {
      await new Promise(r => setTimeout(r, 3000));
      let j;
      try {
        j = await getMaiJob();
      } catch (_) {
        continue;
      }
      const was = mai.job;
      mai.job = j;
      if (!j || !JOB_BUSY.includes(j.status)) {
        if (j && j.type === 'b50' && j.status === 'done') {
          await loadMaiCloud();
          toast('B50 已更新');
        }
        paintFriend();
        break;
      }
      if (!was || was.status !== j.status || jobStale(was) !== jobStale(j)) paintFriend();
    }
  } finally {
    mai.watching = false;
  }
}
// 分頁從背景切回來時，還在等的工作馬上再看一次
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible' && mai.job && JOB_BUSY.includes(mai.job.status))
    watchJob();
});

const B50_MODES = [
  ['list', '🏅 B50'],
  ['up', '📈 推分建議'],
  ['goal', '🎯 目標'],
  ['vs', '🆚 比較'],
  ['log', '📉 Rating 紀錄'],
];
function renderB50(el, S) {
  const data = LS.get('mai', null);
  if (!data) {
    const vs = LS.get('maiVs', []);
    el.innerHTML = `<div class="b50-empty">還沒有成績。用好友代碼讓音GO 幫你抓，或用書籤工具從 maimai DX NET 匯入，就能看到你的 B50。</div>
      ${vs.length ? `<p class="mf-msg">🆚 已收到 ${esc(vs[0].name)} 的成績，匯入你自己的成績後就能並排比較。</p>` : ''}
      ${friendHTML()}${guideHTML(!acct.user)}`;
    bindGuide(el);
    bindFriend();
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
  } else if (mode === 'goal') body = goalHTML(r);
  else if (mode === 'vs') body = vsHTML(r, data, S);
  else if (mode === 'log') body = histHTML(data);
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
    ${acct.user ? friendHTML() : ''}
    <div class="chips mai-modes">${B50_MODES.map(
      ([m, n]) =>
        `<span class="chip rad" data-m="${m}" data-on="${m === mode ? 1 : 0}">${n}</span>`,
    ).join('')}<span class="chip share" id="b50-img">🖼️ 匯出圖片</span></div>
    ${body}
    ${acct.user ? '' : friendHTML()}
    ${guideHTML(false)}
    <p class="cq-hint">${
      data.src === 'friend'
        ? '這份成績是用好友代碼代抓的：只有 EXPERT 以上、沒有 FC／AP 標記（AP 的 +1 不會算）。'
        : ''
    }定數資料：arcade-songs（更新 ${esc(S.updated)}）${
      r.unknown.length ? ` · ${r.unknown.length} 個譜面找不到定數，沒有算進去` : ''
    }</p>`;
  el.querySelectorAll('.mai-modes .chip[data-m]').forEach(
    c =>
      (c.onclick = () => {
        mai.b50mode = c.dataset.m;
        renderB50(el, S);
      }),
  );
  el.querySelector('#b50-img').onclick = () => openB50Image(data, r, S);
  bindCharts(el);
  bindGuide(el);
  bindFriend();
  if (mode === 'goal') bindGoal(el, S);
  if (mode === 'vs') bindVs(el, S);
}

/* ---- 🖼️ B50 圖片：用 Canvas 畫（封面在本站 covers/，同源才能匯出） ---- */
const RANK_COLOR = {
  'SSS+': '#ffd23f',
  SSS: '#ffc23f',
  'SS+': '#ffad5c',
  SS: '#ff9f5c',
  'S+': '#ff8a65',
  S: '#ff8a65',
};
const loadImg = src =>
  new Promise(res => {
    const i = new Image();
    i.onload = () => res(i);
    i.onerror = () => res(null);
    i.src = src;
  });
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
function fitText(ctx, t, w) {
  if (ctx.measureText(t).width <= w) return t;
  while (t && ctx.measureText(t + '…').width > w) t = t.slice(0, -1);
  return t + '…';
}
async function drawB50Image(data, r, S) {
  const F = getComputedStyle(document.body).fontFamily,
    font = (px, w = 700) => `${w} ${px}px ${F}`,
    W = 1200,
    PAD = 32,
    COLS = 5,
    GAP = 12,
    CW = (W - PAD * 2 - GAP * (COLS - 1)) / COLS,
    CH = Math.round(CW * 0.72),
    VER = 22,
    HEAD = 170,
    SEC = 52;
  const nNew = Math.ceil(r.b15.length / COLS),
    nOld = Math.ceil(r.b35.length / COLS),
    H = PAD + HEAD + SEC + nNew * (CH + VER + GAP) + SEC + nOld * (CH + GAP) + 44;
  const cv = document.createElement('canvas'),
    ctx = cv.getContext('2d'),
    k = 2;
  cv.width = W * k;
  cv.height = H * k;
  ctx.scale(k, k);
  const imgs = new Map();
  await Promise.all(
    [...new Set([...r.b15, ...r.b35].map(x => x.img).filter(Boolean))].map(async n =>
      imgs.set(n, await loadImg(COVER + n)),
    ),
  );
  // 背景
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#f7f2ff');
  bg.addColorStop(1, '#eaf4ff');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);
  // 標頭：名字、日期、Rating 牌
  const rating = data.rating || r.total,
    when = new Date(data.at).toLocaleString('zh-TW', { hour12: false }),
    vers = S.new.join(' ／ ');
  ctx.fillStyle = '#7a7690';
  ctx.font = font(16, 500);
  ctx.fillText(`${when} · 國際版 · 新曲 ${vers}`, PAD, PAD + 18);
  ctx.fillStyle = '#1c1b2b';
  ctx.font = font(44, 800);
  ctx.fillText(fitText(ctx, data.name, W - PAD * 2 - 300), PAD, PAD + 72);
  const px = W - PAD - 260,
    py = PAD + 8;
  const plate = ctx.createLinearGradient(px, py, px + 260, py + 84);
  ['#ff6fb5', '#ffd23f', '#5fe3a1', '#5fb8ff', '#b07cff'].forEach((c, i) =>
    plate.addColorStop(i / 4, c),
  );
  roundRect(ctx, px, py, 260, 84, 14);
  ctx.fillStyle = plate;
  ctx.fill();
  roundRect(ctx, px + 8, py + 8, 244, 68, 10);
  ctx.fillStyle = '#2a1f3d';
  ctx.fill();
  ctx.fillStyle = '#ffe680';
  ctx.font = font(48, 900);
  ctx.textAlign = 'center';
  ctx.fillText(String(rating), px + 130, py + 60);
  ctx.textAlign = 'left';
  // 統計列
  const avg = a => (a.length ? a.reduce((t, x) => t + x.ra, 0) / a.length : 0);
  const stats = [
    ['B50 合計', String(r.total)],
    ['新曲 B15', String(r.new15)],
    ['舊曲 B35', String(r.old35)],
    ['來源', data.src === 'friend' ? '好友代碼代抓' : '書籤工具'],
  ];
  stats.forEach(([l, v], i) => {
    const x = PAD + i * 200;
    ctx.fillStyle = '#7a7690';
    ctx.font = font(14, 500);
    ctx.fillText(l, x, PAD + 118);
    ctx.fillStyle = '#1c1b2b';
    ctx.font = font(24, 800);
    ctx.fillText(v, x, PAD + 148);
  });
  let y = PAD + HEAD;
  const section = (title, rows) => {
    const a = avg(rows);
    ctx.fillStyle = '#1c1b2b';
    ctx.font = font(26, 900);
    ctx.fillText(title, PAD, y + 32);
    ctx.fillStyle = '#7a7690';
    ctx.font = font(15, 600);
    ctx.textAlign = 'right';
    ctx.fillText(`平均 ${a.toFixed(2)} [~${Math.round(a * 50)}]`, W - PAD, y + 32);
    ctx.textAlign = 'left';
    y += SEC;
  };
  const card = (x, cy, row, showVer) => {
    const color = DIFF_COLORS[row.diff];
    ctx.save();
    roundRect(ctx, x, cy, CW, CH, 10);
    ctx.clip();
    ctx.fillStyle = '#2a2540';
    ctx.fillRect(x, cy, CW, CH);
    const im = imgs.get(row.img);
    if (im) {
      const s = Math.max(CW / im.width, CH / im.height),
        iw = im.width * s,
        ih = im.height * s;
      ctx.drawImage(im, x + (CW - iw) / 2, cy + (CH - ih) / 2, iw, ih);
    }
    const g = ctx.createLinearGradient(0, cy, 0, cy + CH);
    g.addColorStop(0.25, 'rgba(10,8,20,0)');
    g.addColorStop(1, 'rgba(10,8,20,.9)');
    ctx.fillStyle = g;
    ctx.fillRect(x, cy, CW, CH);
    // 右上：單曲 Rating
    ctx.fillStyle = color;
    roundRect(ctx, x + CW - 64, cy - 10, 74, 46, 10);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font = font(24, 900);
    ctx.textAlign = 'right';
    ctx.fillText(String(row.ra), x + CW - 8, cy + 26);
    // 左上：FC／AP
    if (row.fc) {
      ctx.textAlign = 'left';
      ctx.font = font(12, 900);
      const t = FC_LABEL[row.fc] || '',
        tw = ctx.measureText(t).width + 12;
      ctx.fillStyle = /^ap/.test(row.fc) ? '#ffd23f' : '#3fdd90';
      roundRect(ctx, x + 6, cy + 6, tw, 20, 10);
      ctx.fill();
      ctx.fillStyle = '#1c1b2b';
      ctx.fillText(t, x + 12, cy + 20);
    }
    // 下方：定數、達成率、評級、歌名、DX／ST
    const rank = rankOf(row.ach)[2];
    ctx.textAlign = 'left';
    ctx.fillStyle = '#fff';
    ctx.font = font(20, 900);
    ctx.fillText(constText(row.c, row.est), x + 8, cy + CH - 30);
    const cw = ctx.measureText(constText(row.c, row.est)).width;
    ctx.font = font(12, 600);
    ctx.fillText(row.ach.toFixed(4) + '%', x + 14 + cw, cy + CH - 30);
    ctx.textAlign = 'right';
    ctx.fillStyle = RANK_COLOR[rank] || '#fff';
    ctx.font = font(15, 900);
    ctx.fillText(rank, x + CW - 8, cy + CH - 30);
    ctx.fillStyle = '#fff';
    ctx.font = font(11, 800);
    ctx.fillText(row.kind === 'dx' ? 'DX' : 'ST', x + CW - 8, cy + CH - 10);
    ctx.textAlign = 'left';
    ctx.font = font(13, 600);
    ctx.fillText(fitText(ctx, row.title, CW - 44), x + 8, cy + CH - 10);
    ctx.restore();
    // 難度顏色的外框
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    roundRect(ctx, x + 1.5, cy + 1.5, CW - 3, CH - 3, 9);
    ctx.stroke();
    if (showVer) {
      const v = S.vers.find(z => z[0] === row.s[2]);
      ctx.fillStyle = '#ffd6ec';
      roundRect(ctx, x, cy + CH + 3, CW, VER - 5, 6);
      ctx.fill();
      ctx.fillStyle = '#c2185b';
      ctx.font = font(12, 800);
      ctx.textAlign = 'center';
      ctx.fillText(v ? v[0] : row.s[2], x + CW / 2, cy + CH + 15);
      ctx.textAlign = 'left';
    }
  };
  const grid = (rows, showVer) => {
    rows.forEach((row, i) => {
      card(
        PAD + (i % COLS) * (CW + GAP),
        y + Math.floor(i / COLS) * (CH + GAP + (showVer ? VER : 0)),
        row,
        showVer,
      );
    });
    y += Math.ceil(rows.length / COLS) * (CH + GAP + (showVer ? VER : 0));
  };
  section('NEW', r.b15);
  grid(r.b15, true);
  section('OTHERS', r.b35);
  grid(r.b35, false);
  ctx.fillStyle = '#9a96b0';
  ctx.font = font(13, 500);
  ctx.fillText(
    `音GO · ${location.host || 'otogo'} · 定數資料 arcade-songs（${S.updated}）`,
    PAD,
    H - 18,
  );
  return cv;
}
async function openB50Image(data, r, S) {
  const d = ensureDialog('b50img', '<h2>🖼️ B50 圖片</h2><div class="empty">畫圖中…</div>');
  d.classList.add('dlg-wide');
  if (!d.open) d.showModal();
  const cv = await drawB50Image(data, r, S),
    url = cv.toDataURL('image/png'),
    name = `otogo-b50-${new Date(data.at).toISOString().slice(0, 10)}.png`;
  d.querySelector('.empty').outerHTML =
    `<img id="b50img-pic" class="b50-img" alt="B50 圖片" src="${url}">
    <div class="cq-actions"><a class="btn" id="b50img-dl" download="${name}" href="${url}">⬇️ 下載圖片</a>
    ${navigator.canShare ? '<button class="btn ghost" id="b50img-share">📤 分享</button>' : ''}</div>
    <p class="dlg-hint">手機也可以長按圖片儲存。</p>`;
  const sh = d.querySelector('#b50img-share');
  if (sh)
    sh.onclick = () =>
      cv.toBlob(async b => {
        const file = new File([b], name, { type: 'image/png' });
        if (navigator.canShare({ files: [file] }))
          navigator.share({ files: [file] }).catch(() => {});
        else toast('這個瀏覽器不支援分享圖片，請用下載');
      });
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
