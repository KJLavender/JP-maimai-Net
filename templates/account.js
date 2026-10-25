/* 👤 帳號與同步（Firebase）：登入後「去過」「收藏」存在 Firestore 的 users/{uid}，手機、電腦自動同步。
   - 不登入也能用全部功能，紀錄只存在這個瀏覽器
   - 可以用 Google 登入，或用 Email＋密碼註冊
   - Firebase SDK 用到時才載入：沒登入過的人不會連到 Firebase
   - 合併規則：每間店各自以「最後一次修改的時間」為準，兩台裝置各改各的不會互相蓋掉
   這個檔案只定義函式，在 app.js 之前載入。 */

// Firebase 網頁設定是公開資訊（不是密鑰），誰能讀寫什麼由 firestore.rules 控管。apiKey 空白時不顯示登入
const FIREBASE_CONFIG = window.MJM_FIREBASE || {
  apiKey: 'AIzaSyAiokQw8MgGowY4awqauglDpXcHgiVirbo',
  authDomain: 'maimai-map-2b8d4.firebaseapp.com',
  projectId: 'maimai-map-2b8d4',
  appId: '1:144324202826:web:fa98ad1292ed58ce9df1b3',
};
const FB_SDK = 'https://www.gstatic.com/firebasejs/13.1.0/';
const acct = { fb: null, loading: null, user: null, busy: false, timer: null, rev: 0 };
const acctEnabled = () => !!FIREBASE_CONFIG.apiKey;

const AUTH_ERR = {
  'auth/invalid-email': 'Email 格式不對',
  'auth/missing-email': '請輸入 Email',
  'auth/missing-password': '請輸入密碼',
  'auth/weak-password': '密碼至少要 6 個字元',
  'auth/email-already-in-use': '這個 Email 已經註冊過了，請直接登入',
  'auth/invalid-credential': 'Email 或密碼不對',
  'auth/wrong-password': 'Email 或密碼不對',
  'auth/user-not-found': 'Email 或密碼不對',
  'auth/too-many-requests': '嘗試太多次了，請稍後再試',
  'auth/popup-closed-by-user': '登入視窗被關掉了',
  'auth/cancelled-popup-request': '登入視窗被關掉了',
  'auth/popup-blocked': '瀏覽器擋了登入視窗，請再按一次',
  'auth/network-request-failed': '網路連線失敗',
  'auth/unauthorized-domain': '這個網址還沒加到 Firebase 的授權網域',
  'auth/operation-not-allowed': '這個登入方式還沒在 Firebase 開啟',
  'auth/requires-recent-login': '為了安全，請登出再登入一次後再刪除帳號',
  'permission-denied': '沒有權限存取雲端紀錄',
};
const authMsg = e => AUTH_ERR[e && e.code] || (e && e.message) || '發生錯誤';
const userName = u => u.displayName || (u.email || '').split('@')[0] || '玩家';

function loadFirebase() {
  if (!acct.loading)
    acct.loading = Promise.all(
      ['firebase-app', 'firebase-auth', 'firebase-firestore'].map(n => import(FB_SDK + n + '.js')),
    ).then(
      ([app, auth, fs]) => {
        const a = app.initializeApp(FIREBASE_CONFIG);
        acct.fb = { auth, fs, A: auth.getAuth(a), db: fs.getFirestore(a) };
        auth.onAuthStateChanged(acct.fb.A, onUser);
        return acct.fb;
      },
      () => {
        acct.loading = null;
        throw new Error('無法連線到登入服務（需要網路）');
      },
    );
  return acct.loading;
}

function rememberUser(u) {
  const photo = /^https:\/\//.test(u.photoURL || '') ? u.photoURL : '';
  LS.set('user', { name: userName(u), email: u.email || '', photo });
  renderUserBtn();
}
function onUser(u) {
  const was = acct.user;
  acct.user = u;
  if (u) {
    rememberUser(u);
    if (!was || was.uid !== u.uid) {
      syncNow();
      loadMaiCloud();
      mai.job = undefined;
      if (state.view === 'b50') render();
    }
  } else {
    LS.set('user', null);
    renderUserBtn();
    if (was && state.view === 'b50') render();
  }
  refreshSyncUI();
}

/* 每次標記／取消都記下時間，合併時才知道哪邊比較新 */
function markChanged(kind, id) {
  const t = LS.get('syncTimes', {});
  t[kind + ':' + id] = Date.now();
  LS.set('syncTimes', t);
  acct.rev++;
  if (!acct.user && !LS.get('user', null)) return;
  LS.set('syncDirty', true);
  clearTimeout(acct.timer);
  acct.timer = setTimeout(() => syncNow(), 1500);
}

/* 本機狀態 → {visited: {id: [1或0, 時間]}, favs: {...}} */
function localDoc() {
  const t = LS.get('syncTimes', {}),
    doc = { visited: {}, favs: {} };
  [
    ['visited', 'v', state.visited],
    ['favs', 'f', state.favs],
  ].forEach(([k, kind, set]) => {
    for (const id of set) doc[k][id] = [1, t[kind + ':' + id] || 0];
    for (const key in t)
      if (key.startsWith(kind + ':') && !set.has(key.slice(2))) doc[k][key.slice(2)] = [0, t[key]];
  });
  return doc;
}
function mergeDocs(a, b) {
  const out = { visited: {}, favs: {} };
  for (const k of ['visited', 'favs']) {
    const A = (a && a[k]) || {},
      B = (b && b[k]) || {};
    for (const id of new Set([...Object.keys(A), ...Object.keys(B)])) {
      const x = A[id],
        y = B[id];
      out[k][id] = !x ? y : !y ? x : y[1] > x[1] ? y : x;
    }
  }
  return out;
}
function applyDoc(doc) {
  const t = {};
  state.visited = new Set();
  state.favs = new Set();
  [
    ['visited', 'v', state.visited],
    ['favs', 'f', state.favs],
  ].forEach(([k, kind, set]) => {
    for (const [id, [on, ts]] of Object.entries(doc[k])) {
      if (on) set.add(id);
      if (ts) t[kind + ':' + id] = ts;
    }
  });
  LS.set('visited', [...state.visited]);
  LS.set('favs', [...state.favs]);
  LS.set('syncTimes', t);
}
const recordsKey = () => [...state.visited].sort() + '|' + [...state.favs].sort();

/* ---- 同步：在 Firestore 交易裡「讀雲端 → 合併 → 寫回」，兩台同時寫也不會蓋掉對方 ---- */
async function syncNow(interactive) {
  if (!acct.user || acct.busy) return;
  acct.busy = true;
  refreshSyncUI('同步中…');
  try {
    const { fs, db } = acct.fb,
      ref = fs.doc(db, 'users', acct.user.uid);
    const before = recordsKey(),
      rev = acct.rev;
    const merged = await fs.runTransaction(db, async tx => {
      const snap = await tx.get(ref);
      const m = mergeDocs(localDoc(), snap.exists() ? snap.data() : {});
      tx.set(ref, { v: 2, updated: new Date().toISOString(), ...m });
      return m;
    });
    // 交易進行中又標記的店也要留著（時間比較新的會勝出）
    applyDoc(mergeDocs(merged, localDoc()));
    const pending = acct.rev !== rev;
    LS.set('syncDirty', pending);
    LS.set('syncAt', Date.now());
    if (interactive) toast(`已同步：去過 ${state.visited.size} 間、收藏 ${state.favs.size} 間`);
    acct.busy = false;
    // 只有別台裝置帶來新紀錄才重畫，不然地圖上開著的彈出視窗會被關掉
    if (before !== recordsKey()) render();
    else refreshSyncUI();
    if (pending) {
      clearTimeout(acct.timer);
      acct.timer = setTimeout(() => syncNow(), 1500);
    }
  } catch (e) {
    acct.busy = false;
    toast('同步失敗：' + authMsg(e));
    refreshSyncUI();
  }
}

/* ---- 登入／註冊／登出 ---- */
async function loginGoogle() {
  try {
    const { auth, A } = await loadFirebase();
    await auth.signInWithPopup(A, new auth.GoogleAuthProvider());
    closeDialogs();
    toast('登入成功，紀錄會自動同步');
  } catch (e) {
    showLoginError(authMsg(e));
  }
}
async function loginEmail(mode, name, email, pw) {
  try {
    const { auth, A } = await loadFirebase();
    if (mode === 'up') {
      const cred = await auth.createUserWithEmailAndPassword(A, email, pw);
      if (name) {
        await auth.updateProfile(cred.user, { displayName: name });
        rememberUser(cred.user);
      }
    } else await auth.signInWithEmailAndPassword(A, email, pw);
    closeDialogs();
    toast(mode === 'up' ? '註冊完成，紀錄會自動同步' : '登入成功，紀錄會自動同步');
  } catch (e) {
    showLoginError(authMsg(e));
  }
}
async function resetPassword(email) {
  if (!email) return showLoginError('請先在上面輸入 Email');
  try {
    const { auth, A } = await loadFirebase();
    await auth.sendPasswordResetEmail(A, email);
    showLoginError('已寄出重設密碼的信，請到信箱收信');
  } catch (e) {
    showLoginError(authMsg(e));
  }
}
function clearLocalRecords() {
  state.visited = new Set();
  state.favs = new Set();
  ['visited', 'favs', 'syncTimes', 'syncDirty', 'syncAt', 'mai'].forEach(k =>
    localStorage.removeItem('maimai:' + k),
  );
}
async function logout() {
  let fb;
  try {
    fb = await loadFirebase();
  } catch (e) {
    return toast(e.message);
  }
  if (LS.get('syncDirty', false)) await syncNow();
  if (
    LS.get('syncDirty', false) &&
    !confirm('還有紀錄沒同步到雲端，登出後這台裝置上的這些紀錄會不見。確定要登出嗎？')
  )
    return;
  await fb.auth.signOut(fb.A);
  // 紀錄屬於帳號（已存在雲端），登出後這台裝置清空，下一個人登入才不會混到
  clearLocalRecords();
  closeDialogs();
  toast('已登出，紀錄保存在你的帳號裡');
  render();
}
async function deleteAccount() {
  if (
    !confirm(
      '確定要刪除帳號嗎？雲端上的去過／收藏紀錄會一起刪除，無法復原。\n（這台裝置上的紀錄會保留）',
    )
  )
    return;
  if (!acct.user) return toast('登入狀態還在載入，請稍後再試');
  try {
    const { auth, fs, A, db } = acct.fb;
    clearTimeout(acct.timer);
    await fs.deleteDoc(fs.doc(db, 'users', acct.user.uid, 'mai', 'b50'));
    await fs.deleteDoc(fs.doc(db, 'jobs', acct.user.uid)).catch(() => {}); // 剛送出的工作要等冷卻時間才能刪
    await fs.deleteDoc(fs.doc(db, 'users', acct.user.uid));
    await auth.deleteUser(A.currentUser);
    LS.set('syncDirty', false);
    closeDialogs();
    toast('帳號和雲端紀錄已刪除');
  } catch (e) {
    toast(authMsg(e));
  }
}

/* ---- 🎵 B50 成績：另存一份文件 users/{uid}/mai/b50，內容存成 JSON 字串（Firestore 不能存陣列裡的陣列） ---- */
const maiRef = () => acct.fb.fs.doc(acct.fb.db, 'users', acct.user.uid, 'mai', 'b50');
async function saveMaiCloud(data) {
  if (!acct.user) return;
  try {
    await acct.fb.fs.setDoc(maiRef(), { at: data.at, data: JSON.stringify(data) });
  } catch (e) {
    toast('B50 上傳到帳號失敗：' + authMsg(e));
  }
}
async function loadMaiCloud() {
  try {
    const snap = await acct.fb.fs.getDoc(maiRef()),
      local = LS.get('mai', null),
      remote = snap.exists() ? snap.data() : null;
    if (remote && (!local || remote.at > local.at)) {
      LS.set('mai', JSON.parse(remote.data));
      if (state.view === 'b50') render();
    } else if (local && (!remote || local.at > remote.at)) saveMaiCloud(local);
  } catch (_) {}
}

/* ---- 🤝 好友代碼代抓：在 jobs/{uid} 放一個工作，mai-bot 的 otogo_worker.py 做完會改 status、把成績寫進 users/{uid}/mai/b50 ---- */
const jobRef = () => acct.fb.fs.doc(acct.fb.db, 'jobs', acct.user.uid);
const sendMaiJob = (type, code) =>
  acct.fb.fs.setDoc(jobRef(), { type, code, status: 'queued', at: acct.fb.fs.serverTimestamp() });
async function getMaiJob() {
  const snap = await acct.fb.fs.getDoc(jobRef());
  return snap.exists() ? snap.data() : null;
}
/* ---- 右上角：登入按鈕／使用者名稱 ---- */
function avatarHTML(u) {
  return u.photo
    ? `<img class="avatar" src="${esc(u.photo)}" alt="" referrerpolicy="no-referrer">`
    : `<span class="avatar">${esc([...u.name][0] || '?')}</span>`;
}
function renderUserBtn() {
  const b = document.getElementById('userbtn');
  if (!b) return;
  b.hidden = !acctEnabled();
  const u = LS.get('user', null);
  b.innerHTML = u ? `${avatarHTML(u)}<span class="uname">${esc(u.name)}</span>` : '👤 登入';
  b.classList.toggle('in', !!u);
}
function closeDialogs() {
  document.querySelectorAll('dialog[open]').forEach(d => d.close());
}
function ensureDialog(id, html) {
  let d = document.getElementById(id);
  if (!d) {
    d = document.createElement('dialog');
    d.id = id;
    d.className = 'dlg';
    // 點對話框外面的暗處就關掉
    d.addEventListener('click', e => e.target === d && d.close());
    document.body.appendChild(d);
  }
  d.innerHTML = `<button class="dlg-x" aria-label="關閉">✕</button>${html}`;
  d.querySelector('.dlg-x').onclick = () => d.close();
  return d;
}

function openLogin() {
  loadFirebase().catch(() => {}); // 先載好，按 Google 登入時才能馬上開視窗（Safari 會擋延遲的彈出視窗）
  const d = ensureDialog(
    'login',
    `<h2>登入／註冊</h2>
    <p class="dlg-hint">不登入也能使用全部功能。登入後，「去過」和「收藏」會在手機、電腦自動同步。</p>
    <button class="gbtn" id="lg-google"><b>G</b> 用 Google 登入</button>
    <div class="dlg-or"><span>或用 Email</span></div>
    <div class="dlg-tabs"><button data-m="in" class="on">登入</button><button data-m="up">註冊</button></div>
    <form id="lg-form" novalidate>
      <input id="lg-name" placeholder="暱稱（顯示在右上角，可不填）" maxlength="20" autocomplete="nickname" hidden>
      <input id="lg-email" type="email" placeholder="Email" autocomplete="email">
      <input id="lg-pw" type="password" placeholder="密碼" autocomplete="current-password">
      <div class="dlg-err" id="lg-err" role="alert"></div>
      <button class="btn" id="lg-submit">登入</button>
    </form>
    <button class="linkbtn" id="lg-reset">忘記密碼？</button>
    <p class="dlg-hint"><a href="privacy.html" target="_blank" rel="noopener">隱私權說明</a></p>`,
  );
  let mode = 'in';
  const $ = s => d.querySelector(s);
  const setMode = m => {
    mode = m;
    d.querySelectorAll('.dlg-tabs button').forEach(b =>
      b.classList.toggle('on', b.dataset.m === m),
    );
    $('#lg-name').hidden = m !== 'up';
    $('#lg-reset').hidden = m === 'up';
    $('#lg-pw').placeholder = m === 'up' ? '密碼（至少 6 個字元）' : '密碼';
    $('#lg-pw').autocomplete = m === 'up' ? 'new-password' : 'current-password';
    $('#lg-submit').textContent = m === 'up' ? '註冊' : '登入';
    showLoginError('');
  };
  d.querySelectorAll('.dlg-tabs button').forEach(b => (b.onclick = () => setMode(b.dataset.m)));
  $('#lg-google').onclick = loginGoogle;
  $('#lg-form').onsubmit = e => {
    e.preventDefault();
    showLoginError('');
    loginEmail(mode, $('#lg-name').value.trim(), $('#lg-email').value.trim(), $('#lg-pw').value);
  };
  $('#lg-reset').onclick = () => resetPassword($('#lg-email').value.trim());
  d.showModal();
}
function showLoginError(m) {
  const el = document.getElementById('lg-err');
  if (el) el.textContent = m;
}

function syncStatusText() {
  const at = LS.get('syncAt', 0);
  const ago = at ? Math.round((Date.now() - at) / 60000) : null;
  const when =
    ago === null
      ? ''
      : ago < 1
        ? '剛剛'
        : ago < 60
          ? `${ago} 分鐘前`
          : `${Math.round(ago / 60)} 小時前`;
  return (
    (when ? `上次同步 ${when}` : '尚未同步') +
    (LS.get('syncDirty', false) ? ' · <b>有尚未同步的變更</b>' : '')
  );
}
function openMenu() {
  const u = LS.get('user', null),
    s = conquestStats();
  const d = ensureDialog(
    'me',
    `<div class="me-head">${avatarHTML(u)}<div><b>${esc(u.name)}</b><small>${esc(u.email)}</small></div></div>
    <div class="me-stats">
      <div><b>${s.shops}</b><span>去過</span></div>
      <div><b>${s.prefs}<small>/${s.prefTotal}</small></b><span>制霸縣</span></div>
      <div><b>${state.favs.size}</b><span>收藏</span></div>
    </div>
    <div class="me-sync">☁️ 自動同步 · ${syncStatusText()}${retryHTML('me-sync')}</div>
    <div class="me-acts">
      <button class="btn small" id="me-conq">🏆 我的制霸</button>
      <button class="btn ghost small" id="me-out">登出</button>
    </div>
    <button class="linkbtn danger" id="me-del">刪除帳號</button>`,
  );
  d.querySelector('#me-conq').onclick = () => {
    d.close();
    state.view = 'conquest';
    renderStatusRow();
    render();
    scrollTo(0, 0);
  };
  const retry = d.querySelector('#me-sync');
  if (retry) retry.onclick = () => (d.close(), syncNow(true));
  d.querySelector('#me-out').onclick = logout;
  d.querySelector('#me-del').onclick = deleteAccount;
  d.showModal();
}

/* ---- 制霸頁上的同步區塊 ---- */
// 平常都自動同步，只有失敗（例如離線）留下沒傳的變更時才給重試按鈕
const retryHTML = id =>
  LS.get('syncDirty', false) && !acct.busy
    ? ` <button class="linkbtn inline" id="${id}">重試同步</button>`
    : '';
function syncPanelHTML() {
  if (!acctEnabled()) return '';
  const u = LS.get('user', null);
  return `<div class="sync" id="sync">${
    u
      ? `<div class="sync-st">☁️ 紀錄自動同步到「${esc(u.name)}」的帳號 · ${syncStatusText()}${retryHTML('sync-now')}</div>`
      : `<button class="btn small" id="sync-login">👤 登入／註冊</button>
         <p class="cq-hint">登入後，去過和收藏會在手機、電腦自動同步。不登入也能照常使用。</p>`
  }</div>`;
}
function bindSyncPanel(el) {
  const n = el.querySelector('#sync-now'),
    l = el.querySelector('#sync-login');
  if (n) n.onclick = () => syncNow(true);
  if (l) l.onclick = openLogin;
}
function refreshSyncUI(msg) {
  const box = document.getElementById('sync');
  if (!box) return;
  if (msg) {
    const st = box.querySelector('.sync-st');
    if (st) st.textContent = '☁️ ' + msg;
  } else {
    box.outerHTML = syncPanelHTML();
    bindSyncPanel(document.getElementById('conquest'));
  }
}

addEventListener('DOMContentLoaded', () => {
  if (!acctEnabled()) return;
  const b = document.getElementById('userbtn');
  b.onclick = () => (LS.get('user', null) ? openMenu() : openLogin());
  renderUserBtn();
  // 登入過的裝置一開頁就恢復登入並同步（Firebase 會記住登入狀態）
  if (LS.get('user', null)) loadFirebase().catch(e => toast(e.message));
  // 切回這個分頁時拉一下別台裝置的新紀錄
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && acct.user && Date.now() - LS.get('syncAt', 0) > 30000) syncNow();
  });
});
