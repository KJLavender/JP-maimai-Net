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
  el.outerHTML = friendHTML();
  bindFriend();
}
function bindFriend() {
  const $ = id => document.getElementById(id);
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
// 每幾秒看一次工作做完了沒（最多等 15 分鐘）
async function watchJob() {
  if (mai.watching) return;
  mai.watching = true;
  const t0 = Date.now();
  try {
    while (acct.user && Date.now() - t0 < 15 * 60000) {
      await new Promise(r => setTimeout(r, 3000));
      const was = mai.job,
        j = (mai.job = await getMaiJob());
      if (!j || !JOB_BUSY.includes(j.status)) {
        if (j && j.type === 'b50' && j.status === 'done') {
          await loadMaiCloud();
          toast('B50 已更新');
        }
        paintFriend();
        break;
      }
      if (!was || was.status !== j.status) paintFriend();
    }
  } catch (_) {
  } finally {
    mai.watching = false;
  }
}

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
    ).join('')}</div>
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
  el.querySelectorAll('.mai-modes .chip').forEach(
    c =>
      (c.onclick = () => {
        mai.b50mode = c.dataset.m;
        renderB50(el, S);
      }),
  );
  bindCharts(el);
  bindGuide(el);
  bindFriend();
  if (mode === 'goal') bindGoal(el, S);
  if (mode === 'vs') bindVs(el, S);
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
