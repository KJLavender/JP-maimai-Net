/* 🎵 音GO 書籤工具：在 maimai DX NET（國際版）登入後執行，讀「你自己的」成績，帶回音GO 算 B50。
   - 只讀你自己登入後看得到的頁面；帳號密碼只在官網輸入，不經過音GO
   - 成績壓縮後放在網址的 # 後面帶回音GO，# 後面的內容不會送到任何伺服器 */
(function () {
  const SITE = window.OTOGO_SITE || new URL(document.currentScript.src).origin;
  const BASE = 'https://maimaidx-eng.com/maimai-mobile/';
  const DIFFS = ['BASIC', 'ADVANCED', 'EXPERT', 'MASTER', 'Re:MASTER'];

  const box = document.createElement('div');
  box.style.cssText =
    'position:fixed;inset:auto 12px 12px 12px;z-index:99999;padding:14px 16px;border-radius:12px;' +
    'background:#171334;color:#eceaff;font:15px/1.5 system-ui,sans-serif;box-shadow:0 6px 24px #0008';
  document.body.appendChild(box);
  const say = m => (box.textContent = '🎵 音GO：' + m);

  async function get(path) {
    const r = await fetch(BASE + path, { credentials: 'include' });
    if (!r.ok) throw new Error('官網回應 ' + r.status);
    return new DOMParser().parseFromString(await r.text(), 'text/html');
  }
  // 一首歌一個 *_score_back 區塊；DX／STD 圖示有時在區塊外層
  function blocks(doc, fn) {
    doc.querySelectorAll('div[class*="_score_back"]').forEach(b => {
      const t = b.querySelector('.music_name_block');
      if (!t) return;
      const k =
        b.querySelector('img.music_kind_icon') ||
        b.parentElement.querySelector('img.music_kind_icon');
      fn(b, t.textContent.trim(), k && /music_standard/.test(k.src) ? 'std' : 'dx');
    });
  }
  async function gzip64(s) {
    const z = new Blob([s]).stream().pipeThrough(new CompressionStream('gzip'));
    const buf = new Uint8Array(await new Response(z).arrayBuffer());
    let bin = '';
    for (let i = 0; i < buf.length; i += 0x8000)
      bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  (async () => {
    if (location.hostname !== 'maimaidx-eng.com')
      throw new Error('請先打開 maimai DX NET（maimaidx-eng.com）並登入，再按這個書籤');
    say('確認登入狀態…');
    const home = await get('home/');
    const name = (home.querySelector('.name_block') || {}).textContent;
    if (!name) throw new Error('還沒登入 maimai DX NET，請先登入再按一次');
    const rating = parseInt((home.querySelector('.rating_block') || {}).textContent, 10) || 0;

    const scores = [];
    for (let diff = 0; diff < DIFFS.length; diff++) {
      say(`讀取 ${DIFFS[diff]} 成績（${diff + 1}/${DIFFS.length}）…`);
      blocks(await get(`record/musicGenre/search/?genre=99&diff=${diff}`), (b, title, kind) => {
        const ach = [...b.querySelectorAll('.music_score_block')]
          .map(e => e.textContent.trim())
          .find(x => x.endsWith('%'));
        if (!ach) return; // 沒打過
        const icons = [...b.querySelectorAll('img')]
          .map(i => (i.src.match(/music_icon_(\w+)\.png/) || [])[1])
          .filter(Boolean);
        const fc = icons.find(x => /^(fc|fcp|ap|app)$/.test(x)) || '';
        const fs = icons.find(x => /^(fs|fsp|fdx|fdxp|sync)$/.test(x)) || '';
        scores.push([title, kind, diff, parseFloat(ach), fc, fs]);
      });
    }
    if (!scores.length) throw new Error('沒有讀到任何成績');

    // 新曲枠以官網「版本」頁最新兩個版本為準；讀不到就交給音GO 用資料集判斷
    let fresh = null;
    try {
      say('讀取新曲清單…');
      const v = await get('record/musicVersion/search/');
      const ids = [...v.querySelectorAll('select[name="version"] option')]
        .map(o => o.value)
        .filter(x => /^\d+$/.test(x))
        .map(Number)
        .sort((a, b) => a - b)
        .slice(-2);
      fresh = [];
      for (const id of ids)
        blocks(await get(`record/musicVersion/search/?version=${id}`), (b, title, kind) =>
          fresh.push(title + '|' + kind),
        );
      if (!fresh.length) fresh = null;
    } catch (_) {
      fresh = null;
    }

    say(`讀到 ${scores.length} 個譜面，正在打開音GO…`);
    const payload = { v: 1, at: Date.now(), name: name.trim(), rating, scores, new: fresh };
    location.href = `${SITE}/#view=b50&mai=${await gzip64(JSON.stringify(payload))}`;
  })().catch(e => {
    say(e.message);
    box.style.background = '#5a1530';
  });
})();
