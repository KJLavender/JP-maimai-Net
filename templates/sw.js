// Service Worker：讓網站可以離線開、可以加到主畫面。
// __CACHE__ 由 build_site.py 依網站內容自動算出，內容一改快取名稱就跟著變，使用者會拿到新版。
const C = 'maimai-__CACHE__';
const A = ['./', './index.html', './style.css', './app.js', './manifest.webmanifest', './icon.svg'];

self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(C).then(c => c.addAll(A)));
});

// 新版啟用時刪掉舊版快取
self.addEventListener('activate', e => {
  e.waitUntil(Promise.all([
    caches.keys().then(k => Promise.all(k.filter(x => x !== C).map(x => caches.delete(x)))),
    self.clients.claim(),
  ]));
});

self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (u.origin !== location.origin) return;   // 地圖圖磚、CDN 不管
  // 頁面本身：先拿網路上的新版，離線才用快取
  if (e.request.mode === 'navigate' || u.pathname.endsWith('index.html') || u.pathname === '/') {
    e.respondWith(fetch(e.request)
      .then(r => { const rc = r.clone(); caches.open(C).then(c => c.put(e.request, rc)); return r; })
      .catch(() => caches.match(e.request)));
    return;
  }
  // 其他靜態檔：快取優先（快取名稱跟著內容變，不會卡在舊版）
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
