/* 🏅 制霸排行榜：登入後可以「公開我的制霸進度」（預設不公開），公開的進度存在 Firestore 的 board/{uid}，
   任何人都能讀（只有名字和數字，沒有去過哪些店）。好友：用好友連結（#cqf=uid）加，名單只存在這個瀏覽器。
   排行榜收起來時不會連到 Firebase。這個檔案只定義函式，在 conquest.js、account.js 之後、app.js 之前載入。 */

// app.js 一載入就會改寫網址，所以先在這裡記下來
const BOARD_FRIEND = new URLSearchParams(location.hash.slice(1)).get('cqf');
const BOARD_N = 50;
const BOARD_SORTS = [
  ['shops', '依間數'],
  ['areas', '依縣市數'],
];
const board = { open: false, tab: 'all', sort: 'shops', rows: null, err: '', seq: 0 };
const boardRef = uid => acct.fb.fs.doc(acct.fb.db, 'board', uid);
const boardOn = () => !!acct.user && LS.get('boardOn', '') === acct.user.uid;
const boardName = () => (LS.get('boardName', '') || userName(acct.user)).slice(0, 20);
const friendIds = () => LS.get('cqFriends', []);

function boardEntry() {
  const s = conquestStats();
  return {
    name: boardName(),
    shops: s.shops,
    prefs: s.prefs,
    tw: s.tw,
    twAreas: s.twAreas,
    areas: s.prefs + s.twAreas,
    at: acct.fb.fs.serverTimestamp(),
  };
}
// 公開中：每次同步完都更新一次排行榜上的數字
async function publishBoard() {
  if (!boardOn()) return;
  try {
    await acct.fb.fs.setDoc(boardRef(acct.user.uid), boardEntry());
  } catch (e) {
    toast('排行榜更新失敗：' + authMsg(e));
  }
}
async function setBoardOn(on) {
  const { fs } = acct.fb,
    uid = acct.user.uid;
  try {
    if (on) {
      LS.set('boardOn', uid);
      await fs.setDoc(boardRef(uid), boardEntry());
      toast('已公開你的制霸進度');
    } else {
      await fs.deleteDoc(boardRef(uid));
      LS.set('boardOn', '');
      toast('已從排行榜移除');
    }
  } catch (e) {
    LS.set('boardOn', '');
    toast('設定失敗：' + authMsg(e));
  }
  loadBoard();
}
// 換裝置登入時，看雲端有沒有公開中的紀錄
async function checkBoardOn() {
  try {
    const snap = await acct.fb.fs.getDoc(boardRef(acct.user.uid));
    LS.set('boardOn', snap.exists() ? acct.user.uid : '');
    if (snap.exists() && snap.data().name) LS.set('boardName', snap.data().name);
  } catch (_) {}
}

async function loadBoard() {
  const seq = ++board.seq;
  board.rows = null;
  board.err = '';
  paintBoard();
  try {
    const { fs, db } = await loadFirebase();
    let rows;
    if (board.tab === 'all') {
      const snap = await fs.getDocs(
        fs.query(fs.collection(db, 'board'), fs.orderBy(board.sort, 'desc'), fs.limit(BOARD_N)),
      );
      rows = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    } else {
      const ids = [...new Set([...friendIds(), ...(boardOn() ? [acct.user.uid] : [])])];
      rows = (
        await Promise.all(
          ids.map(id =>
            fs.getDoc(fs.doc(db, 'board', id)).then(
              s => (s.exists() ? { id, ...s.data() } : { id, hidden: true }),
              () => ({ id, hidden: true }),
            ),
          ),
        )
      ).sort((a, b) => !!a.hidden - !!b.hidden || (b[board.sort] || 0) - (a[board.sort] || 0));
    }
    if (seq === board.seq) board.rows = rows;
  } catch (e) {
    if (seq === board.seq) board.err = authMsg(e);
  }
  if (seq === board.seq) paintBoard();
}

function boardRowHTML(x, i) {
  const me = acct.user && x.id === acct.user.uid,
    del =
      board.tab === 'friends' && !me
        ? `<button class="linkbtn inline bd-del" data-id="${esc(x.id)}" aria-label="移除好友">✕</button>`
        : '';
  if (x.hidden)
    return `<div class="bd-row hidden"><span class="bd-no">—</span><div class="b50-info"><div class="b50-title">（沒有公開進度）</div></div>${del}</div>`;
  return `<div class="bd-row${me ? ' me' : ''}"><span class="bd-no">${i + 1}</span>
    <span class="avatar">${esc([...(x.name || '?')][0])}</span>
    <div class="b50-info"><div class="b50-title">${esc(x.name)}${me ? ' <small>（你）</small>' : ''}</div>
      <div class="b50-meta">都道府縣 ${x.prefs}/47 · 台灣縣市 ${x.twAreas}</div></div>
    <div class="b50-score"><b>${board.sort === 'areas' ? x.areas + ' 縣市' : x.shops + ' 間'}</b><small>${board.sort === 'areas' ? x.shops + ' 間' : x.areas + ' 縣市'}</small></div>${del}</div>`;
}
function boardBodyHTML() {
  const u = acct.user,
    tabs = [
      ['all', '🌏 全站'],
      ['friends', `🤝 好友（${friendIds().length}）`],
    ];
  const me = u
    ? `<div class="bd-me">
        <label class="bd-pub"><input type="checkbox" id="bd-on"${boardOn() ? ' checked' : ''}> 公開我的制霸進度</label>
        <div class="mf-row"><input id="bd-name" class="mai-input" maxlength="20" placeholder="排行榜上的名字" value="${esc(boardName())}">
          <button class="btn ghost small" id="bd-save"${boardOn() ? '' : ' disabled'}>更新名字</button>
          <button class="btn ghost small" id="bd-link">🔗 我的好友連結</button></div>
        <p class="cq-hint">公開的只有名字和去過的間數、縣市數，不會公開去過哪些店。好友連結傳給朋友，對方點開就會把你加進好友。</p>
      </div>`
    : LS.get('user', null)
      ? '<p class="cq-hint">登入狀態載入中…</p>'
      : `<p class="cq-hint">登入後可以公開自己的進度、和朋友比一比（預設不公開）。</p>
         <div class="cq-actions"><button class="btn small" id="bd-login">👤 登入</button></div>`;
  const list = board.err
    ? `<div class="empty">排行榜載入失敗：${esc(board.err)}</div>`
    : !board.rows
      ? '<div class="empty">載入中…</div>'
      : board.rows.length
        ? board.rows.map(boardRowHTML).join('')
        : `<div class="empty">${board.tab === 'all' ? '還沒有人公開進度' : '還沒有好友。把你的好友連結傳給朋友，也請朋友傳給你。'}</div>`;
  return `${me}
    <div class="chips bd-tabs">${tabs.map(([v, n]) => `<span class="chip rad" data-bt="${v}" data-on="${board.tab === v ? 1 : 0}">${n}</span>`).join('')}
      ${BOARD_SORTS.map(([v, n]) => `<span class="chip tgl" data-bs="${v}" data-on="${board.sort === v ? 1 : 0}">${n}</span>`).join('')}</div>
    <div class="bd-list">${list}</div>`;
}
const boardHTML = () =>
  acctEnabled()
    ? `<details class="board" id="board"${board.open ? ' open' : ''}><summary>🏅 制霸排行榜</summary><div id="board-body">${board.open ? boardBodyHTML() : ''}</div></details>`
    : '';
function paintBoard() {
  const el = document.getElementById('board-body');
  if (!el || !board.open) return;
  el.innerHTML = boardBodyHTML();
  const $ = id => el.querySelector('#' + id);
  if ($('bd-login')) $('bd-login').onclick = openLogin;
  if ($('bd-on')) $('bd-on').onchange = e => setBoardOn(e.target.checked);
  if ($('bd-save'))
    $('bd-save').onclick = () => {
      const n = $('bd-name').value.trim();
      if (!n) return toast('名字不能空白');
      LS.set('boardName', n.slice(0, 20));
      publishBoard().then(loadBoard);
    };
  if ($('bd-link'))
    $('bd-link').onclick = async () => {
      const url = `${location.origin}${location.pathname}#cqf=${encodeURIComponent(acct.user.uid)}`;
      try {
        await navigator.clipboard.writeText(url);
        toast('已複製好友連結');
      } catch (_) {
        prompt('複製這個好友連結：', url);
      }
    };
  el.querySelectorAll('[data-bt]').forEach(
    c => (c.onclick = () => ((board.tab = c.dataset.bt), loadBoard())),
  );
  el.querySelectorAll('[data-bs]').forEach(
    c => (c.onclick = () => ((board.sort = c.dataset.bs), loadBoard())),
  );
  el.querySelectorAll('.bd-del').forEach(
    b =>
      (b.onclick = () => {
        LS.set(
          'cqFriends',
          friendIds().filter(x => x !== b.dataset.id),
        );
        loadBoard();
      }),
  );
}
function bindBoard(el) {
  const d = el.querySelector('#board');
  if (!d) return;
  // 制霸頁重畫時（例如同步完）保持展開，用已經載入的資料
  d.ontoggle = () => {
    if (d.open === board.open) return;
    board.open = d.open;
    if (d.open) loadBoard();
  };
  if (board.open) board.rows || board.err ? paintBoard() : loadBoard();
}

function addBoardFriend(id) {
  if (!acctEnabled() || !/^[\w.@-]{1,128}$/.test(id)) return;
  if (!friendIds().includes(id)) LS.set('cqFriends', [...friendIds(), id]);
  toast('已加入好友，到制霸排行榜看看');
  board.open = true;
  board.tab = 'friends';
  board.rows = null;
  state.view = 'conquest';
  renderStatusRow();
  render();
}
addEventListener('DOMContentLoaded', () => BOARD_FRIEND && addBoardFriend(BOARD_FRIEND));
// 網頁開著時又點了好友連結：這個監聽比 app.js 的先註冊，先記下網址；
// 等 app.js 重讀完網址（會切回清單）再切到制霸頁
addEventListener('hashchange', () => {
  const id = new URLSearchParams(location.hash.slice(1)).get('cqf');
  if (id) setTimeout(() => addBoardFriend(id));
});
