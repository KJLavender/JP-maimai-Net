/* ☁️ Google 同步：把「去過」和「收藏」存到使用者自己 Google 雲端硬碟的「應用程式資料夾」。
   - 權限只有 drive.appdata：網站只看得到自己建立的那個隱藏檔案，看不到使用者的其他檔案
   - 沒有後端：瀏覽器直接拿 Google 的存取權杖呼叫 Drive API，權杖只放在記憶體（約 1 小時）
   - 合併規則：每間店各自以「最後一次修改的時間」為準，兩台裝置各改各的都不會互相蓋掉
   這個檔案只定義函式，在 app.js 之前載入。 */

// OAuth 用戶端 ID（公開資訊，不是密鑰），由 build_site.py 從 GOOGLE_OAUTH_CLIENT_ID 填進 config。
// 空字串時不顯示同步功能。測試可用 window.MJM_CLIENT_ID 覆蓋
const GOOGLE_CLIENT_ID =
  window.MJM_CLIENT_ID ||
  JSON.parse(document.getElementById('config').textContent).googleClientId ||
  '';
const SYNC_SCOPE = 'https://www.googleapis.com/auth/drive.appdata';
const SYNC_FILE = 'maimai-sync.json';
const sync = { token: null, exp: 0, busy: false, timer: null, rev: 0, hinted: false };
const syncEnabled = () => !!GOOGLE_CLIENT_ID;
const syncReady = () => sync.token && Date.now() < sync.exp;

/* 每次標記／取消都記下時間，合併時才知道哪邊比較新 */
function markChanged(kind, id) {
  const t = LS.get('syncTimes', {});
  t[kind + ':' + id] = Date.now();
  LS.set('syncTimes', t);
  sync.rev++;
  if (!LS.get('syncOn', false)) return;
  LS.set('syncDirty', true);
  if (syncReady()) {
    clearTimeout(sync.timer);
    sync.timer = setTimeout(() => syncNow(false), 1500);
  } else if (!sync.hinted) {
    sync.hinted = true;
    toast('已記在這台裝置。要上傳到 Google，請到「制霸」按「🔄 立即同步」');
  }
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

/* ---- Google 登入（Google Identity Services，用到時才載入） ---- */
function loadGIS() {
  if (window.google && google.accounts && google.accounts.oauth2) return Promise.resolve();
  return new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://accounts.google.com/gsi/client';
    s.onload = res;
    s.onerror = () => rej(new Error('無法載入 Google 登入（需要網路）'));
    document.head.appendChild(s);
  });
}
async function getToken() {
  if (syncReady()) return sync.token;
  await loadGIS();
  return new Promise((res, rej) => {
    google.accounts.oauth2
      .initTokenClient({
        client_id: GOOGLE_CLIENT_ID,
        scope: SYNC_SCOPE,
        callback: r => {
          if (r.error) return rej(new Error(r.error));
          sync.token = r.access_token;
          sync.exp = Date.now() + (r.expires_in - 60) * 1000;
          res(sync.token);
        },
        error_callback: e =>
          rej(
            new Error(
              e.type === 'popup_closed'
                ? '登入視窗被關掉了'
                : e.type === 'popup_failed_to_open'
                  ? '瀏覽器擋了登入視窗，請允許彈出視窗後再試'
                  : e.type,
            ),
          ),
      })
      .requestAccessToken({ prompt: LS.get('syncOn', false) ? '' : 'consent' });
  });
}
async function drive(path, opts = {}) {
  const r = await fetch('https://www.googleapis.com' + path, {
    ...opts,
    headers: { Authorization: 'Bearer ' + sync.token, ...(opts.headers || {}) },
  });
  if (r.status === 401) {
    sync.token = null;
    throw new Error('登入已過期，請再按一次同步');
  }
  if (!r.ok) throw new Error('Google 雲端硬碟回應 ' + r.status);
  return r;
}

/* ---- 同步：下載雲端 → 合併 → 上傳 ---- */
async function syncNow(interactive) {
  if (sync.busy || !syncEnabled()) return;
  sync.busy = true;
  refreshSyncUI('同步中…');
  try {
    await getToken();
    const q = encodeURIComponent(`name='${SYNC_FILE}'`);
    const list = await (
      await drive(`/drive/v3/files?spaces=appDataFolder&q=${q}&fields=files(id)`)
    ).json();
    const id = list.files && list.files[0] && list.files[0].id;
    const remote = id ? await (await drive(`/drive/v3/files/${id}?alt=media`)).json() : {};
    const before = [...state.visited, '|', ...state.favs].join(),
      rev = sync.rev;
    const merged = mergeDocs(localDoc(), remote);
    applyDoc(merged);
    const changed = before !== [...state.visited, '|', ...state.favs].join();
    const body = JSON.stringify({ v: 2, updated: new Date().toISOString(), ...merged });
    if (id) {
      await drive(`/upload/drive/v3/files/${id}?uploadType=media`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
    } else {
      const b = 'mjm' + Date.now(),
        meta = JSON.stringify({ name: SYNC_FILE, parents: ['appDataFolder'] });
      await drive('/upload/drive/v3/files?uploadType=multipart', {
        method: 'POST',
        headers: { 'Content-Type': `multipart/related; boundary=${b}` },
        body:
          `--${b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${meta}\r\n` +
          `--${b}\r\nContent-Type: application/json\r\n\r\n${body}\r\n--${b}--`,
      });
    }
    LS.set('syncOn', true);
    LS.set('syncAt', Date.now());
    // 上傳的這段時間又有修改 → 還不算同步完，稍後再傳一次
    const pending = sync.rev !== rev;
    LS.set('syncDirty', pending);
    if (interactive) toast(`已同步：去過 ${state.visited.size} 間、收藏 ${state.favs.size} 間`);
    sync.busy = false;
    // 只有別台裝置帶來新紀錄才重畫，不然地圖上開著的彈出視窗會被關掉
    if (changed) render();
    else refreshSyncUI();
    if (pending) {
      clearTimeout(sync.timer);
      sync.timer = setTimeout(() => syncNow(false), 1500);
    }
  } catch (e) {
    sync.busy = false;
    toast('同步失敗：' + e.message);
    refreshSyncUI();
  }
}
function stopSync() {
  if (sync.token && window.google) google.accounts.oauth2.revoke(sync.token, () => {});
  sync.token = null;
  LS.set('syncOn', false);
  LS.set('syncDirty', false);
  toast('已停止 Google 同步（這台裝置的紀錄還在）');
  render();
}

/* ---- 制霸頁上的同步區塊 ---- */
function syncPanelHTML() {
  if (!syncEnabled()) return '';
  const on = LS.get('syncOn', false),
    at = LS.get('syncAt', 0);
  const ago = at ? Math.round((Date.now() - at) / 60000) : null;
  const when =
    ago === null
      ? ''
      : ago < 1
        ? '剛剛'
        : ago < 60
          ? `${ago} 分鐘前`
          : `${Math.round(ago / 60)} 小時前`;
  return `<div class="sync" id="sync">
    ${
      on
        ? `<div class="sync-st">☁️ 已開啟 Google 同步${when ? ` · 上次同步 ${when}` : ''}${
            LS.get('syncDirty', false) ? ' · <b>有尚未同步的變更</b>' : ''
          }</div>
           <div class="cq-actions"><button class="btn small" id="sync-now">🔄 立即同步</button>
           <button class="btn ghost small" id="sync-stop">停止同步</button></div>`
        : `<button class="btn small" id="sync-now">☁️ 用 Google 帳號同步</button>
           <p class="cq-hint">登入後手機、電腦的紀錄會自動合併。紀錄存在你自己的 Google 雲端硬碟（隱藏的應用程式資料夾），
           網站看不到你的其他檔案。<a href="privacy.html" target="_blank" rel="noopener">隱私權說明</a></p>`
    }
  </div>`;
}
function bindSyncPanel(el) {
  const n = el.querySelector('#sync-now'),
    s = el.querySelector('#sync-stop');
  if (n) n.onclick = () => syncNow(true);
  if (s) s.onclick = stopSync;
}
// 開過同步的裝置先載好 Google 登入：按下按鈕後要立刻開登入視窗，不然 Safari 會當成彈出廣告擋掉
if (syncEnabled() && localStorage.getItem('maimai:syncOn') === 'true') loadGIS().catch(() => {});

function refreshSyncUI(msg) {
  const box = document.getElementById('sync');
  if (!box) return;
  if (msg) {
    const n = box.querySelector('#sync-now');
    if (n) n.textContent = msg;
  } else {
    box.outerHTML = syncPanelHTML();
    bindSyncPanel(document.getElementById('conquest'));
  }
}
