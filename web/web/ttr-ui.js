/* Glonktown (web) - loading screen, game-file downloader, sign-in and the in-game
   touch controls. The layout numbers are copied from the iOS app (main.m). The game itself runs in Python (main.py). */
(function () {
  'use strict';
  const LS = (() => { try { return window.localStorage; } catch (e) { return { getItem() { return null; }, setItem() {}, removeItem() {} }; } })();
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const T = window.ttr = {
    aa: (() => { try { return window.localStorage.getItem('ttr_aa') === '0' ? '0' : '1'; } catch (e) { return '1'; } })(),
    pyReady: false, go: false, gameConfig: '', typeBtn: '', dbg: false, safeL: 0, safeR: 0, safeT: 0, safeB: 0, vh: 0, pycode: '', winW: 0, winH: 0, cookie: '', inp: '0,0,0,0,0,0,0,0', camN: 0, txtIn: 0, txtSub: 0, txtVal: '',
    wsUrl: window.TTR_WS || ((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws'),
  };

  // ------------------------------------------------------------------ preferences
  const prefs = {
    get mode() { return LS.getItem('ttr_srv_mode'); },
    get res() { return LS.getItem('ttr_srv_res') || ''; },
    get game() { return LS.getItem('ttr_srv_game') || ''; },
    get isDefault() { return this.mode !== 'custom'; },
    get base() { return this.isDefault ? '' : this.res.replace(/\/+$/, ''); },
    get ws() {
      if (this.isDefault) return T.wsUrl;
      const g = this.game;
      return /^wss?:/i.test(g) ? g : ((location.protocol === 'https:' ? 'wss://' : 'ws://') + g);
    },
    get userKey() { return this.isDefault ? 'ttr_user' : 'ttr_user_' + btoa(this.res).slice(0, 12); },
  };

  // ------------------------------------------------------------------ helpers
  // the page's font (the title keeps the toon font); without an internet connection the system's own font is used
  const uiFont = document.createElement('link');
  uiFont.rel = 'stylesheet'; uiFont.href = 'https://fonts.googleapis.com/css2?family=Nunito:wght@600;700;800;900&display=swap';
  document.head.appendChild(uiFont);
  const root = document.createElement('div');
  root.id = 'ttr';
  document.body.appendChild(root);
  function el(tag, cls, parent, css) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (css) Object.assign(e.style, css);
    (parent || root).appendChild(e);
    return e;
  }
  function place(e, x, y, w, h) {
    const s = e.style;
    s.left = x + 'px'; s.top = y + 'px';
    if (w != null) s.width = w + 'px';
    if (h != null) s.height = h + 'px';
  }
  let W = 0, H = 0, sc = 1;
  let lastInner = '';
  let dn = 0;
  // Test sessions: open the page with ?log=1 (kept for the rest of the visit) and everything the game prints, plus any page error or crash
  // message, is sent to the server's /__log, where it is saved with the time and this device's address.
  let LOGGING = location.port === '8001' || location.port === '8002';
  try {
    if (/[?&]log=1/.test(location.search)) sessionStorage.setItem('ttr.log', '1');
    if (sessionStorage.getItem('ttr.log') === '1') LOGGING = true;
  } catch (e) {}
  // Everyone else is logged quietly: only crash information (Python tracebacks, errors, lost connections, page errors) and one line
  // about the device and the sign-in name. No passwords, no touches, no frame timings. At most 400 lines per visit.
  let quietSent = 0, tbLeft = 0, lastQuiet = '';
  const QUIET_WANT = /Traceback|[A-Za-z_]*(Error|Exception)\b|STEP FAILED|reconnecting|webnet: (closed|error)|Aborted/;
  function quietLog(m) {
    if (quietSent >= 400) return;
    let want = false;
    if (m.indexOf('PY|') === 0) {
      const t = m.slice(3).trim();
      if (/Traceback \(most recent call last\)/.test(t)) { tbLeft = 30; want = true; }
      else if (tbLeft > 0) { want = true; tbLeft--; if (/^[A-Za-z_.]*(Error|Exception)\b/.test(t)) tbLeft = 0; }
      else if (QUIET_WANT.test(t)) want = true;
    } else if (/^JS\| (page error|unhandled|console\.error|session)/.test(m)) want = true;
    if (!want || m === lastQuiet) return;
    lastQuiet = m; quietSent++;
    try { navigator.sendBeacon('/__log', m); } catch (e) {}
  }
  function plog(m) {
    if (LOGGING) { try { navigator.sendBeacon('/__log', m); } catch (e) {} return; }
    if (m.indexOf('JS| env') !== 0) { quietLog(m); return; }
    // the real site: only the screen-fact lines, a few per visit, as a plain request the web server's log records
    if (m.indexOf('JS| env') !== 0 || dn >= 12) return;
    dn++; try { new Image().src = '/__d?' + encodeURIComponent(m) + '&r=' + Date.now(); } catch (e) {}
  }
  T.plog = plog;
  {
    addEventListener('error', (e) => plog('JS| page error: ' + e.message + ' @ ' + (e.filename || '') + ':' + (e.lineno || '')));
    addEventListener('unhandledrejection', (e) => plog('JS| unhandled rejection: ' + (e.reason && (e.reason.stack || e.reason.message) || e.reason)));
    (LOGGING ? ['error', 'warn'] : ['error']).forEach((lv) => { const o = console[lv]; console[lv] = function () { o.apply(console, arguments); try { plog('JS| console.' + lv + ': ' + Array.prototype.slice.call(arguments).map(String).join(' ').slice(0, 600)); } catch (e) {} }; });
    plog((LOGGING ? 'JS| log session started: ' : 'JS| session: ') + navigator.userAgent + ' ' + innerWidth + 'x' + innerHeight);
  }
  const _cl = console.log; console.log = function () { _cl.apply(console, arguments); try { const m = String(arguments[0]); if (m.indexOf('PY|') === 0) plog(m); } catch (e) {} };
  let installUp = false;
  let kbHold = false;             // in game, the keyboard must not resize the game's window
  const SAFE = { t: 0, b: 0, l: 0, r: 0 };
  const layouts = [];
  function measure() {
    W = innerWidth; H = innerHeight; lastInner = W + 'x' + H;
    sc = Math.min(W, H) >= 700 ? 1.45 : 1.0;      // the app scales up on iPad
    document.documentElement.style.setProperty('--sc', sc);
    const probe = el('div', null, root, { position: 'absolute', visibility: 'hidden', paddingTop: 'env(safe-area-inset-top,0px)', paddingBottom: 'env(safe-area-inset-bottom,0px)', paddingLeft: 'env(safe-area-inset-left,0px)', paddingRight: 'env(safe-area-inset-right,0px)' });
    const cs = getComputedStyle(probe);
    SAFE.t = parseFloat(cs.paddingTop) || 0; SAFE.b = parseFloat(cs.paddingBottom) || 0; SAFE.l = parseFloat(cs.paddingLeft) || 0; SAFE.r = parseFloat(cs.paddingRight) || 0;
    probe.remove();
  }
  function relayout() {
    if (kbHold) return;
    measure(); layouts.forEach((f) => f());
    // Open Toontown test build: draw at the page's own pixel size by default (a phone's full screen resolution is too slow); ?res=1.5 or ?res=2 for sharper
    let cap = 2; try { cap = parseFloat(new URLSearchParams(location.search).get('res') || localStorage.getItem('ttr_res') || '2') || 2; } catch (e) { cap = 2; }
    cap = Math.max(0.5, Math.min(cap, 2));
    const dpr = Math.min(window.devicePixelRatio || 1, cap);
    T.winW = Math.round(W * dpr); T.winH = Math.round(H * dpr);
    fitTitle();
    T.safeL = SAFE.l; T.safeR = SAFE.r; T.safeT = SAFE.t; T.safeB = SAFE.b; T.vh = H;      // the game keeps its on-screen items inside these
  }
  function fitTitle() {
    if (typeof title === 'undefined') return;
    let fs = Math.min(84 * sc, W / 11, H * 0.14);
    title.style.fontSize = fs + 'px';
    // measure the word, not the title box (that is always as wide as the screen)
    for (let i = 0; i < 12 && titleWord.offsetWidth > W * 0.92; i++) { fs *= 0.9; title.style.fontSize = fs + 'px'; }
  }
  addEventListener('resize', relayout);
  // iOS (especially a Home Screen app) sometimes reports a stale window size until the phone is rotated: keep checking, and re-measure
  // a few times shortly after start-up, so the game never stays drawn for the wrong size
  addEventListener('pageshow', () => setTimeout(relayout, 100));
  if (window.visualViewport) visualViewport.addEventListener('resize', () => { if (!kbHold) relayout(); });
  setInterval(() => { if (!kbHold && (innerWidth + 'x' + innerHeight) !== lastInner) relayout(); }, 500);
  // Opening the app already in landscape, iOS can report a viewport that is shorter than the screen (e.g. 932x371 on a 932x430 phone) and
  // not correct it until something nudges it: ask for a fresh measurement a few times right after the page starts
  // Opening the app already in landscape, iOS can stick on a viewport shorter than the window (932x371 on a 932x430 phone) until the phone is
  // turned to portrait and back. If it is still short once the page has settled, try ways of making iOS measure again, one at a time, and
  // log which one worked (a reload does not).
  const vpStuck = () => innerWidth > innerHeight && outerWidth === innerWidth && outerHeight - innerHeight >= 20 && outerHeight - innerHeight <= 100;
  const vpTries = [
    ['viewport meta replaced', () => { const m = document.querySelector('meta[name=viewport]'); if (m) { const n = m.cloneNode(); m.remove(); document.head.appendChild(n); } }],
    ['reflow', () => { const d = document.documentElement; d.style.display = 'none'; void d.offsetHeight; d.style.display = ''; }],
    ['scroll nudge', () => { document.body.style.minHeight = '120vh'; scrollTo(0, 1); setTimeout(() => { scrollTo(0, 0); document.body.style.minHeight = ''; }, 50); }],
    ['viewport-fit toggled', () => { const m = document.querySelector('meta[name=viewport]'); if (m) { const c = m.getAttribute('content'); m.setAttribute('content', c.replace('viewport-fit=cover', 'viewport-fit=auto')); setTimeout(() => m.setAttribute('content', c), 80); } }],
    ['rotated page turn', () => { const d = document.documentElement; d.style.transition = 'none'; d.style.transform = 'rotate(0.01deg)'; void d.offsetHeight; d.style.transform = ''; }],
  ];
  let vpStep = 0;
  function vpTry() {
    if (!vpStuck() || vpStep >= vpTries.length) { if (vpStep > 0) plog('JS| env viewport ' + (vpStuck() ? 'still short after all tries: ' : 'fixed after: ') + (vpStep ? vpTries[vpStep - 1][0] : '-') + ' inner ' + innerWidth + 'x' + innerHeight); return; }
    const t = vpTries[vpStep++];
    try { t[1](); } catch (e) {}
    setTimeout(() => { plog('JS| env vp try "' + t[0] + '" inner ' + innerWidth + 'x' + innerHeight + ' outer ' + outerWidth + 'x' + outerHeight); relayout(); setTimeout(vpTry, 200); }, 450);
  }
  setTimeout(vpTry, 2500);
  [250, 800, 1800, 3500].forEach((ms) => setTimeout(() => { try { window.scrollTo(0, 0); dispatchEvent(new Event('resize')); if (!kbHold) relayout(); } catch (e) {} }, ms));
  [400, 1500, 4000, 9000].forEach((ms) => setTimeout(() => { if (!kbHold) relayout(); }, ms));
  addEventListener('orientationchange', () => setTimeout(relayout, 200));

  // ------------------------------------------------------------------ backdrop: an evening sky with twinkling stars, slow clouds and light
  // motes drifting up from the hills. All of it only moves or fades (no repainting), so it stays smooth while the game starts up.
  const cssVars = (e, vars) => { Object.keys(vars).forEach((k) => e.style.setProperty('--' + k, vars[k])); return e; };
  let seed = 7;
  const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;          // the same sky on every visit
  const bg = el('div', null, root);
  bg.id = 'ttr-bg';
  const bgImg = el('img', null, bg);
  bgImg.style.display = 'none';
  for (let i = 0; i < 46; i++) {
    const secs = 2.5 + rand() * 4;
    cssVars(el('div', 'star', bg, { left: rand() * 100 + '%', top: Math.pow(rand(), 1.6) * 55 + '%', animationDuration: secs + 's', animationDelay: -rand() * secs + 's' }),
      { s: (0.8 + rand() * 1.8).toFixed(1) });
  }
  [[0.1, 560, 240, 0.15, 0.35], [0.24, 420, 190, 0.6, 0.45], [0.38, 640, 280, 0.35, 0.55], [0.5, 380, 170, 0.85, 0.6]].forEach(([top, w, secs, phase, o]) => {
    cssVars(el('div', 'cloud', bg, { top: top * 100 + '%', animationDuration: secs + 's', animationDelay: -secs * phase + 's' }), { w, o });
  });
  el('div', 'hills', bg);
  for (let i = 0; i < 14; i++) {
    const secs = 10 + rand() * 8;
    cssVars(el('div', 'mote', bg, { left: 4 + rand() * 92 + '%', animationDuration: secs + 's', animationDelay: -rand() * secs + 's' }),
      { s: (2 + rand() * 2.5).toFixed(1), dx: Math.round((rand() - 0.5) * 80) });
  }
  const title = el('div', null, root);
  title.id = 'ttr-title';
  const titleWord = el('span', null, title);
  titleWord.textContent = 'GLONKTOWN';
  const logo = el('img', null, root);
  logo.id = 'ttr-logo';
  logo.style.display = 'none';
  let haveArt = false;
  layouts.push(() => {
    if (haveArt && logo.naturalWidth) {
      const lh = Math.min(H * 0.40, 200 * sc), lw = lh * logo.naturalWidth / logo.naturalHeight;
      Object.assign(logo.style, { height: lh + 'px', width: lw + 'px', top: Math.max(H * 0.04, 10) + 'px' });
    }
  });
  async function loadArt() {
    try {
      if (typeof caches === 'undefined') {                       // not a secure page: no Cache API, just fetch the two pictures
        const urls = await Promise.all([prefs.base + '/_ui/background.jpg', prefs.base + '/_ui/logo.png'].map(async (u) => {
          const r = await fetch(u, { cache: 'no-store' }); return r.ok ? URL.createObjectURL(await r.blob()) : null; }));
        if (urls[0]) {          // the logo is optional: the sky alone is enough
          bgImg.src = urls[0]; if (urls[1]) logo.src = urls[1];
          await Promise.all([bgImg.decode().catch(() => {}), logo.decode().catch(() => {})]);
          bgImg.style.display = ''; if (urls[1]) { logo.style.display = ''; title.style.display = 'none'; }
          bg.classList.add('art');
          haveArt = true; relayout();
        }
        return;
      }
      const cache = await caches.open('ttr-art-v1');
      const get = async (url) => {
        // ask the server first: a picture it no longer has (404) is dropped from the saved copy; the saved copy is only for when we are offline
        let status = 0, r = null;
        try {
          const n = await fetch(url + '?t=' + Date.now(), { cache: 'no-store' });
          status = n.status;
          if (n.ok) { await cache.put(url, n.clone()); r = n; } else if (n.status === 404) await cache.delete(url);
        } catch (e) { /* offline */ }
        if (!r && status !== 404) r = await cache.match(url);
        return r ? URL.createObjectURL(await r.blob()) : null;
      };
      const [b, l] = await Promise.all([get(prefs.base + '/_ui/background.jpg'), get(prefs.base + '/_ui/logo.png')]);
      if (b) {
        bgImg.src = b; if (l) logo.src = l;
        await Promise.all([bgImg.decode().catch(() => {}), logo.decode().catch(() => {})]);
        bgImg.style.display = ''; if (l) { logo.style.display = ''; title.style.display = 'none'; }
        bg.classList.add('art');
        haveArt = true; relayout();
      }
    } catch (e) { /* the gradient and title stay */ }
  }

  // ------------------------------------------------------------------ loading screen
  const load = el('div', null, root);
  load.id = 'ttr-load';
  const bar = el('div', null, load); bar.id = 'ttr-bar'; const barFill = el('i', null, bar);
  const status = el('div', null, load); status.id = 'ttr-status';
  const detail = el('div', null, load); detail.id = 'ttr-detail';
  const spin = el('div', null, load); spin.id = 'ttr-spin'; spin.style.display = 'none';
  for (let i = 0; i < 3; i++) el('i', null, spin);
  const errBox = el('div', null, load); errBox.id = 'ttr-error'; errBox.style.display = 'none';
  const errBtn = el('button', 'ttr-pill light on', load); errBtn.textContent = 'Try again'; errBtn.style.display = 'none';
  layouts.push(() => {
    const bw = Math.min(W * 0.6, 560 * sc), bh = 6 * sc, by = H * 0.55;
    Object.assign(bar.style, { width: bw + 'px', height: bh + 'px', top: by + 'px' });
    status.style.top = by - 40 * sc + 'px';
    detail.style.top = by + bh + 14 * sc + 'px';
    spin.style.top = by + 'px';        // where the bar was: the bar is hidden while the game starts
    Object.assign(errBtn.style, { left: (W - 170) / 2 + 'px', top: H - 64 + 'px', width: '170px', height: '40px', fontSize: '16px' });
  });
  function setStatus(msg, det, frac) {
    status.textContent = msg || ''; detail.textContent = det || '';
    if (frac != null) { bar.style.display = ''; barFill.style.width = Math.max(0, Math.min(1, frac)) * 100 + '%'; }
  }
  function showLoad(on) { load.style.display = on ? '' : 'none'; }
  function showError(msg) {
    spin.style.display = 'none'; status.textContent = 'Something went wrong';
    errBox.textContent = msg; errBox.style.display = ''; errBtn.style.display = '';
  }
  errBtn.addEventListener('click', () => { errBox.style.display = 'none'; errBtn.style.display = 'none'; beginDownload(); });

  // ------------------------------------------------------------------ the downloader
  // Saved packs: the Cache API on secure (https) pages, IndexedDB everywhere else, so the files are not downloaded every launch.
  const idb = (() => {
    let dbp = null;
    function open() {
      if (!dbp) dbp = new Promise((res, rej) => {
        if (typeof indexedDB === 'undefined') { rej(new Error('no IndexedDB')); return; }
        const r = indexedDB.open('ttr', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('packs');
        r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
      });
      return dbp;
    }
    async function tx(mode, fn) {
      const db = await open();
      return new Promise((res, rej) => {
        const t = db.transaction('packs', mode), rq = fn(t.objectStore('packs'));
        t.oncomplete = () => res(rq && rq.result); t.onerror = () => rej(t.error); t.onabort = () => rej(t.error);
      });
    }
    return { get: (k) => tx('readonly', (s) => s.get(k)), put: (k, v) => tx('readwrite', (s) => s.put(v, k)),
             keys: () => tx('readonly', (s) => s.getAllKeys()), del: (k) => tx('readwrite', (s) => s.delete(k)) };
  })();
  function fsReady() { return typeof window.FS !== 'undefined' && T.pyReady; }
  const ASSETS = '/data/data/game/assets/';
  function fsWrite(path, data) {
    const FSr = window.FS;
    const dir = path.slice(0, path.lastIndexOf('/'));
    try { FSr.mkdirTree(dir); } catch (e) { /* exists */ }
    FSr.writeFile(path, data);
  }
  async function streamUnzip(body, onBytes, onEntry, tap) {
    const reader = body.getReader();
    let buf = new Uint8Array(1 << 20), len = 0, pos = 0;
    async function fill(min) {
      while (len - pos < min) {
        const r = await reader.read();
        if (r.done) return false;
        const v = r.value;
        onBytes(v.length);
        if (tap) tap(v);
        if (len + v.length > buf.length) {
          if (pos > 0) { buf.copyWithin(0, pos, len); len -= pos; pos = 0; }
          if (len + v.length > buf.length) { const nb = new Uint8Array(Math.max(buf.length * 2, len + v.length)); nb.set(buf.subarray(0, len)); buf = nb; }
        }
        buf.set(v, len); len += v.length;
      }
      return true;
    }
    const dec = new TextDecoder();
    for (;;) {
      if (!(await fill(30))) break;
      const dv = new DataView(buf.buffer, buf.byteOffset + pos, 30);
      if (dv.getUint32(0, true) !== 0x04034b50) break;                       // central directory: done
      const flags = dv.getUint16(6, true), method = dv.getUint16(8, true);
      const csize = dv.getUint32(18, true), nlen = dv.getUint16(26, true), elen = dv.getUint16(28, true);
      if ((flags & 8) || method !== 0) throw new Error('unsupported pack format');
      if (!(await fill(30 + nlen + elen))) throw new Error('pack ended early');
      const name = dec.decode(buf.subarray(pos + 30, pos + 30 + nlen));
      pos += 30 + nlen + elen;
      if (!(await fill(csize))) throw new Error('pack ended early');
      if (!name.endsWith('/')) onEntry(name, buf.subarray(pos, pos + csize));
      pos += csize;
    }
    try { await reader.cancel(); } catch (e) { /* ignore */ }
  }
  async function downloadAll() {
    setStatus('Getting ready...', '', 0);
    let waited = 0;
    while (!fsReady()) {
      await sleep(150); waited += 150;
      if (waited === 30000) setStatus('Getting ready...', 'Starting the game engine. This can take a little while the first time.', 0);
      if (waited === 90000) setStatus('Getting ready...', 'Still starting. If nothing changes, reload this page.', 0);
    }
    setStatus('Checking game files...', '', 0);
    const base = prefs.base;
    const packs = await (await fetch(base + '/packs.json?t=' + Date.now(), { cache: 'no-store' })).json();
    const total = packs.reduce((a, p) => a + p[1], 0);
    let got = 0, done = 0;
    let cache = null;
    try { if (typeof caches !== 'undefined' && !/nocache/.test(location.search)) cache = await caches.open('ttr-packs-v1'); } catch (e) { cache = null; }
    const want = new Set(packs.map((p) => base + '/_packs/' + p[0] + '.zip?s=' + p[1]));   // the size is part of the address: a browser cache ignores everything after a # , so a changed pack was never fetched again
    try {
      if (cache) { for (const k of await cache.keys()) { if (!want.has(k.url.replace(location.origin, '')) && !want.has(k.url)) await cache.delete(k); } }
      else { for (const k of await idb.keys()) { if (!want.has(k)) await idb.del(k); } }
    } catch (e) { /* cleaning up is optional */ }
    const mb = (n) => Math.round(n / 1e6);
    const upd = (first) => setStatus(first ? 'Downloading game files' : 'Loading game files',
      mb(got) + ' of ' + mb(total) + ' MB   (' + done + ' of ' + packs.length + ' packs)', total ? got / total : 0);
    let fromNet = false;
    for (const [name, size] of packs) {
      const url = base + '/_packs/' + name + '.zip';
      const key = url + '?s=' + size;
      let body, putP = null, chunks = null;
      let resp = cache ? await cache.match(key) : null;
      if (cache && !resp && name !== '_code') {            // copy saved by an older page version (its address had no size in it): keep it, so game art is not downloaded twice
        const old = await cache.match(url);
        if (old) { resp = old; try { await cache.put(key, old.clone()); await cache.delete(url); } catch (e) { /* fine */ } }
      }
      let blob = null;
      if (!cache) { try { blob = await idb.get(key); } catch (e) { blob = null; } }
      if (blob) body = blob.stream();
      else if (!resp) {
        fromNet = true;
        resp = await fetch(key, { cache: 'no-store' });
        if (!resp.ok) throw new Error('could not download ' + name + ' (' + resp.status + ')');
        if (cache) {
          const [x, y] = resp.body.tee();
          body = x;
          putP = cache.put(key, new Response(y, { headers: { 'content-type': 'application/zip' } })).catch(() => {});
        } else { body = resp.body; chunks = []; }
      } else body = resp.body;
      await streamUnzip(body, (n) => { got += n; upd(fromNet); }, (path, data) => {
        const dest = path.startsWith('_code/') ? ASSETS + path.slice(6) : ASSETS + 'resources/' + path;
        fsWrite(dest, data.slice());
      }, chunks ? (v) => chunks.push(v) : null);
      if (putP) await putP;
      if (chunks) { try { await idb.put(key, new Blob(chunks, { type: 'application/zip' })); } catch (e) { console.warn('could not save ' + name, e); } chunks = null; }
      done++; upd(fromNet);
      await sleep(0);
    }
    setStatus('Ready', '', 1);
  }

  // ------------------------------------------------------------------ shared pieces: pills, fields
  function pill(text, parent, cls) {
    const b = el('button', 'ttr-pill ' + (cls || ''), parent);
    const s = document.createElement('span'); s.textContent = text; b.appendChild(s);
    b.classList.add('on');
    return b;
  }
  function field(ph, secure, parent, name, ac) {
    const f = el('input', 'ttr-field on', parent);
    f.type = secure ? 'password' : 'text'; f.placeholder = ph;
    f.autocapitalize = 'none'; f.autocorrect = 'off'; f.spellcheck = false;
    if (name) f.name = name; if (ac) f.autocomplete = ac;
    return f;
  }

  // ------------------------------------------------------------------ the sign-in screen (same layout as the app)
  const login = el('div', null, root);
  login.id = 'ttr-login'; login.style.display = 'none';
  const uField = field('Toon name', false, login, 'username', 'username');
  const pField = field('Password', true, login, 'password', 'current-password');
  const playBtn = el('button', 'ttr-btn on', login); playBtn.textContent = 'PLAY';
  const forgot = el('button', 'ttr-link on', login); forgot.textContent = 'Forgot password?';
  const lmsg = el('div', null, login); lmsg.id = 'ttr-msg';
  let kbMode = false;
  // only phones and tablets get an on-screen keyboard to make room for; a desktop keeps the fields where they are
  const touchFirst = () => !!(window.matchMedia && matchMedia('(hover: none) and (pointer: coarse)').matches);
  function loginLayout() {
    const vv = window.visualViewport;
    const kb = kbMode && vv && touchFirst();
    const top = kb ? vv.offsetTop : 0;                  // the visible area above the keyboard starts here
    const w = Math.min(W * 0.5, 360 * sc), y0 = kb ? top + 10 * sc : H * (haveArt ? 0.47 : 0.36);
    [uField, pField].forEach((f, i) => { Object.assign(f.style, { width: w + 'px', top: y0 + i * 56 * sc + 'px', left: W / 2 + 'px' }); });
    const bw = 220 * sc, bh = 50 * sc;
    place(playBtn, (W - bw) / 2, y0 + 120 * sc, bw, bh);
    place(forgot, (W + bw) / 2 + 14 * sc, y0 + 120 * sc + bh * 0.2, null, bh * 0.6);
    lmsg.style.top = y0 + 194 * sc + 'px'; lmsg.style.fontSize = 16 * sc + 'px';
    logo.style.opacity = title.style.opacity = kb ? '0' : '';
  }
  layouts.push(loginLayout);
  if (window.visualViewport) {
    visualViewport.addEventListener('resize', () => { if (kbMode) loginLayout(); });
    visualViewport.addEventListener('scroll', () => { if (kbMode) loginLayout(); });
  }
  function loginMessage(m, bad) { lmsg.textContent = m; lmsg.className = bad ? 'bad' : ''; lmsg.id = 'ttr-msg'; }
  function showLogin() {
    showLoad(false); login.style.display = '';
    uField.value = LS.getItem(prefs.userKey) || '';
    pField.value = LS.getItem(prefs.userKey + '.pw') || '';
    loginMessage('New here? Pick a name and password and tap PLAY.', false);
    relayout();
  }
  async function authCall(path, text) {
    try {
      const r = await fetch(prefs.base + path, { method: 'POST', body: text, headers: { 'Content-Type': 'text/plain' } });
      const t = (await r.text()).trim();
      if (r.status === 404) return { ok: true, tag: 'ok', text: t };
      return { ok: r.ok, tag: r.ok ? t : '', text: t };
    } catch (e) { return { ok: false, tag: '', text: "Can't reach the Toontown server. Check your Wi-Fi." }; }
  }
  async function signIn() {
    const user = uField.value.trim().toLowerCase(), pw = pField.value;
    if (!user || !pw) { loginMessage('Enter your toon name and password.', true); return; }
    if (user.includes(':')) { loginMessage("Please don't use colons in your name.", true); return; }
    if (!standalone) goFull();        // the game plays full screen; a browser only allows that straight after a tap or key press, so ask now
    playBtn.disabled = true; loginMessage('Signing in...', false);
    const cookie = user + ':' + pw;
    const r = await authCall('/auth', cookie);
    playBtn.disabled = false;
    if (!r.ok) { loginMessage(r.text || 'Sign-in failed.', true); return; }
    LS.setItem(prefs.userKey, user); LS.setItem(prefs.userKey + '.pw', pw);
    startGame(cookie);
  }
  [uField, pField].forEach((f) => {
    f.setAttribute('enterkeyhint', f === pField ? 'go' : 'next');
    f.addEventListener('focus', () => { kbMode = true; loginLayout(); });
    f.addEventListener('blur', () => setTimeout(() => {
      if (document.activeElement !== uField && document.activeElement !== pField) { kbMode = false; loginLayout(); window.scrollTo(0, 0); }
    }, 80));
  });
  login.addEventListener('pointerdown', (e) => { if (e.target === login || e.target === lmsg) { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); } });
  playBtn.addEventListener('click', signIn);
  // Enter / Go / Send on a phone keyboard does not always arrive as a plain "Enter" key press (Android keyboards that are suggesting words
  // report key "Unidentified" and send the line break as an input event instead), so listen for both ways.
  function onEnter(el, fn) {
    let t = 0;
    const go = (e) => { const n = Date.now(); if (n - t < 250) return; t = n; fn(e); };
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.keyCode === 13 || e.which === 13) { e.preventDefault(); go(e); } });
    el.addEventListener('beforeinput', (e) => { if (e.inputType === 'insertLineBreak' || e.inputType === 'insertParagraph') { e.preventDefault(); go(e); } });
  }
  onEnter(pField, () => signIn());
  onEnter(uField, () => pField.focus());
  forgot.addEventListener('click', () => loginMessage('Ask the host to reset your password. Your toons stay.', false));

  // ------------------------------------------------------------------ the flow
  async function beginDownload() {
    login.style.display = 'none'; showLoad(true);
    errBox.style.display = 'none'; errBtn.style.display = 'none'; spin.style.display = 'none';
    loadArt();
    try { await downloadAll(); showLogin(); }
    catch (e) { console.error(e); showError(String(e && e.stack || e)); }
  }
  async function startGame(cookie) {
    login.style.display = 'none'; showLoad(true);
    setStatus('Starting Toontown...', '', null); bar.style.display = 'none'; spin.style.display = '';
    T.wsUrl = prefs.ws;
    try {            // the server's game settings (gameconfig.json); no file, or no answer in 3 seconds, means the game's own defaults
      const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 3000);
      const r = await fetch('/gameconfig.json?t=' + Date.now(), { cache: 'no-store', signal: ctl.signal });
      clearTimeout(timer);
      if (r.ok) T.gameConfig = await r.text();
    } catch (e) { }
    T.cookie = cookie; T.go = true;
    plog('JS| session user: ' + String(cookie).split(':')[0]);       // the name only, never the password
  }
  T.started = function () {          // called by the game once it is drawing
    bg.style.display = 'none'; logo.style.display = 'none'; title.style.display = 'none'; load.style.display = 'none';
    hud.style.display = '';
    relayout(); keepAwake();
    if (!standalone && !isFullscreen()) {        // not full screen after all (refused, or left while loading): the first tap or key in the game makes it so
      const once = (e) => { if (e.key === 'Escape') return; removeEventListener('pointerup', once, true); removeEventListener('keydown', once, true); goFull(); };
      addEventListener('pointerup', once, true); addEventListener('keydown', once, true);
    }
    [500, 2000, 6000].forEach((ms) => setTimeout(() => { if (!kbHold) relayout(); }, ms));
  };

  // ------------------------------------------------------------------ in-game controls (same layout as the app)
  const hud = el('div', null, root);
  hud.id = 'ttr-hud'; hud.style.display = 'none';
  const joy = el('div', 'pad', hud); joy.id = 'ttr-joy';
  const knob = el('div', null, joy); knob.id = 'ttr-knob';
  const jump = el('div', 'pad', hud); jump.id = 'ttr-jump'; jump.textContent = 'JUMP';
  const cam = el('div', 'pad', hud); cam.id = 'ttr-cam'; cam.textContent = 'CAM';
  const act = el('div', 'pad', hud); act.id = 'ttr-act'; act.textContent = 'ACTION';
  const tasks = el('div', 'pad', hud); tasks.id = 'ttr-tasks'; tasks.textContent = 'TASKS';
  const padl = el('div', 'pad', hud); padl.id = 'ttr-padl'; padl.textContent = '◀';
  const padr = el('div', 'pad', hud); padr.id = 'ttr-padr'; padr.textContent = '▶';
  // frames-per-second counter (the page's own animation frames, which is how often the game can draw)
  const fps = el('div', null, hud); fps.id = 'ttr-fps'; fps.textContent = '-- FPS';
  (function () {
    let n = 0, t0 = performance.now();
    function tick(t) {
      n++;
      if (t - t0 >= 500) { if (hud.style.display !== 'none') fps.textContent = Math.round(n * 1000 / (t - t0)) + ' FPS'; n = 0; t0 = t; }
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  })();
  const st = { f: 0, b: 0, l: 0, r: 0, j: 0, a: 0, pl: 0, pr: 0 };
  let hudVisible = false;
  function pushInput() { T.inp = [st.f, st.b, st.l, st.r, st.j, st.a, st.pl, st.pr].join(','); }
  layouts.push(() => {
    const js = 150 * sc, jb = 92 * sc, cb = 58 * sc, pb = 112 * sc;
    place(joy, Math.max(SAFE.l, 24) + 20 * sc, H - js - Math.max(SAFE.b, 16) - 24 * sc, js, js);
    const kd = js * 0.42; Object.assign(knob.style, { width: kd + 'px', height: kd + 'px', left: (js - kd) / 2 + 'px', top: (js - kd) / 2 + 'px' });
    const jx = W - jb - Math.max(SAFE.r, 24) - 30 * sc, jy = H - jb - Math.max(SAFE.b, 16) - 130 * sc;
    place(jump, jx, jy, jb, jb);
    place(cam, jx + (jb - cb) / 2, jy - cb - 16 * sc, cb, cb); cam.style.fontSize = cb * 0.26 + 'px';
    // ACTION sits lower than JUMP, nearer the thumb (players kept missing it when throwing in Field Offices), but clear of the screen's bottom edge
    place(act, jx - jb - 20 * sc, Math.min(jy + 70 * sc, H - jb - Math.max(SAFE.b, 16) - 8 * sc), jb, jb); act.style.fontSize = jb * 0.26 + 'px';
    place(fps, W / 2 - 40 * sc, Math.max(SAFE.t, 6) + 4 * sc, 80 * sc, 20 * sc); fps.style.fontSize = 13 * sc + 'px';
    const tb = 62 * sc;           // TASKS: left edge, above the stick
    place(tasks, Math.max(SAFE.l, 24) + 20 * sc + (js - tb) / 2, H - js - Math.max(SAFE.b, 16) - 24 * sc - tb - 24 * sc, tb, tb); tasks.style.fontSize = tb * 0.24 + 'px';
    const py = H - pb - Math.max(SAFE.b, 16) - 20 * sc;
    place(padl, W / 2 - pb - 14 * sc, py, pb, pb); padl.style.fontSize = pb * 0.26 + 'px';
    place(padr, W / 2 + 14 * sc, py, pb, pb); padr.style.fontSize = pb * 0.26 + 'px';
  });
  function joyUpdate(e) {
    const rc = joy.getBoundingClientRect(), cx = rc.width / 2, cy = rc.height / 2;
    let dx = e.clientX - rc.left - cx, dy = e.clientY - rc.top - cy;
    const maxr = rc.width * 0.38, len = Math.hypot(dx, dy);
    if (len > maxr) { dx = dx / len * maxr; dy = dy / len * maxr; }
    const kd = rc.width * 0.42;
    knob.style.left = cx + dx - kd / 2 + 'px'; knob.style.top = cy + dy - kd / 2 + 'px';
    const nx = dx / maxr, ny = -dy / maxr;
    const f = +(ny > 0.35), b = +(ny < -0.35), l = +(nx < -0.35), r = +(nx > 0.35);
    if (f !== st.f || b !== st.b || l !== st.l || r !== st.r) { st.f = f; st.b = b; st.l = l; st.r = r; pushInput(); }
  }
  function joyReset() {
    const rc = joy.getBoundingClientRect(), kd = rc.width * 0.42;
    knob.style.left = (rc.width - kd) / 2 + 'px'; knob.style.top = (rc.height - kd) / 2 + 'px';
    st.f = st.b = st.l = st.r = 0; pushInput();
  }
  function bindHold(node, onDown, onUp, onMove) {
    node.addEventListener('pointerdown', (e) => { e.preventDefault(); e.stopPropagation(); node.setPointerCapture(e.pointerId); node.classList.add('down'); onDown(e); });
    node.addEventListener('pointermove', (e) => { if (onMove && node.hasPointerCapture(e.pointerId)) { e.preventDefault(); onMove(e); } });
    const up = (e) => { node.classList.remove('down'); onUp(e); };
    node.addEventListener('pointerup', up); node.addEventListener('pointercancel', up); node.addEventListener('lostpointercapture', (e) => { if (node.classList.contains('down')) up(e); });
    node.addEventListener('contextmenu', (e) => e.preventDefault());
  }
  bindHold(joy, joyUpdate, () => { joy.classList.remove('down'); joyReset(); }, joyUpdate); joy.classList.remove('down');
  joy.addEventListener('pointerdown', () => joy.classList.remove('down'));
  bindHold(jump, () => { st.j = 1; pushInput(); }, () => { st.j = 0; pushInput(); });
  bindHold(cam, () => { T.camN++; }, () => {});
  bindHold(act, () => { st.a = 1; pushInput(); }, () => { st.a = 0; pushInput(); });
  // TASKS presses the game's tasks key (End): the key going down shows the task list, coming up hides it, so a tap shows it and the next tap hides it
  let tasksOn = false;
  function tasksKey(type) {
    const cv = document.querySelector('canvas.emscripten') || document;
    const k = { key: 'End', code: 'End', keyCode: 35, which: 35, bubbles: true, cancelable: true };
    try { const ev = new KeyboardEvent(type, k); ev.ttrMade = true; cv.dispatchEvent(ev); } catch (e) { plog('JS| tasks key failed ' + e); }
  }
  function tasksSet(on) { if (on === tasksOn) return; tasksOn = on; tasks.classList.toggle('on', on); tasksKey(on ? 'keydown' : 'keyup'); }
  tasks.addEventListener('click', (e) => { e.preventDefault(); gameFocus(); tasksSet(!tasksOn); });
  tasks.addEventListener('pointerdown', (e) => e.stopPropagation());
  bindHold(padl, () => { st.pl = 1; pushInput(); }, () => { st.pl = 0; pushInput(); });
  bindHold(padr, () => { st.pr = 1; pushInput(); }, () => { st.pr = 0; pushInput(); });
  // Python tells us what to show: controls, the ACTION button, the tug-of-war buttons (same rules as the app)
  let uiArgs = [0, 0, 0];
  T.setUI = function (vis, action, tug) {
    uiArgs = [vis, action, tug];
    vis = !!+vis && !touchHidden();
    if (hudVisible && !vis) { joyReset(); st.a = st.pl = st.pr = 0; pushInput(); }
    hudVisible = vis;
    if (!vis) tasksSet(false);
    [joy, jump, cam, tasks].forEach((n) => { n.style.display = vis ? '' : 'none'; });
    act.style.display = (vis && +action) ? '' : 'none';
    const tg = vis && +tug;
    padl.style.display = padr.style.display = tg ? '' : 'none';
  };
  [joy, jump, cam, tasks, act, padl, padr].forEach((n) => { n.style.display = 'none'; });

  // ------------------------------------------------------------------ display settings (sign-in screen and in game)
  const RES_CHOICES = [['2', 'Sharp'], ['1.5', 'Balanced'], ['1', 'Fast'], ['0.75', 'Fastest']];
  const lsGet = (k, d) => { try { const v = LS.getItem(k); return v == null ? d : v; } catch (e) { return d; } };
  const lsSet = (k, v) => { try { LS.setItem(k, v); } catch (e) {} };
  // The Display button (sign-in screen) and the gear (in game) only show on a device that opened the page once with ?display=1
  // (remembered; ?display=0 hides them again)
  const displayParam = new URLSearchParams(location.search).get('display');
  if (displayParam === '0' || displayParam === '1') lsSet('ttr_display', displayParam);
  const showDisplayButtons = lsGet('ttr_display', '0') === '1';
  function applyFps() { fps.style.display = lsGet('ttr_fps', '0') === '1' ? '' : 'none'; }
  applyFps();
  const setWrap = el('div', null, root); setWrap.id = 'ttr-set'; setWrap.style.display = 'none';
  function showSettings() {
    setWrap.innerHTML = ''; setWrap.style.display = '';
    const card = el('div', 'card', setWrap);
    const h = el('h2', null, card); h.textContent = 'Display';
    const row = (label, hint, choices, current, onPick) => {
      const r = el('div', 'row', card);
      const l = el('div', 'lbl', r); l.textContent = label;
      if (hint) { const sm = el('small', null, l); sm.textContent = hint; }
      const g = el('div', 'seg', r);
      choices.forEach(([val, txt]) => {
        const b = el('button', val === current ? 'sel' : '', g); b.textContent = txt;
        b.addEventListener('click', () => { [...g.children].forEach((c) => c.classList.remove('sel')); b.classList.add('sel'); onPick(val); });
      });
    };
    row('Picture quality', 'Lower is smoother on slower devices', RES_CHOICES, String(lsGet('ttr_res', '') || '2'), (v) => { lsSet('ttr_res', v); relayout(); });
    const aaNow = T.aa;
    const note = el('div', 'note', card); note.style.visibility = 'hidden'; note.textContent = 'Smooth edges changes when the game restarts.';
    row('Smooth edges', 'Softens jagged lines; off is faster', [['1', 'On'], ['0', 'Off']], aaNow, (v) => { lsSet('ttr_aa', v); note.style.visibility = v === aaNow ? 'hidden' : ''; restart.style.display = v === aaNow ? 'none' : ''; });
    row('Speed counter', 'The FPS number at the top', [['1', 'Show'], ['0', 'Hide']], lsGet('ttr_fps', '0'), (v) => { lsSet('ttr_fps', v); applyFps(); });
    row('On-screen controls', 'Auto shows them on touch screens, until you play with a keyboard', [['auto', 'Auto'], ['show', 'Show'], ['hide', 'Hide']], lsGet('ttr_touch', 'auto'),
      (v) => { lsSet('ttr_touch', v); applyTouchUI(); });
    const keysBtn = el('button', 'act', card); keysBtn.textContent = 'Keyboard keys';
    keysBtn.addEventListener('click', showKeys);
    const restart = el('button', 'act', card); restart.textContent = 'Restart game now'; restart.style.display = 'none';
    restart.addEventListener('click', () => location.reload());
    const done = el('button', 'act done', card); done.textContent = 'Done';
    done.addEventListener('click', () => { setWrap.style.display = 'none'; setWrap.innerHTML = ''; });
  }
  const gearBtn = el('button', 'ttr-gear on', hud); gearBtn.textContent = '⚙';
  if (!showDisplayButtons) gearBtn.style.display = 'none';
  gearBtn.addEventListener('pointerdown', (e) => e.stopPropagation());
  gearBtn.addEventListener('click', (e) => { e.preventDefault(); showSettings(); });
  layouts.push(() => place(gearBtn, W / 2 + 46 * sc, Math.max(SAFE.t, 6), 30 * sc, 28 * sc));
  const dsp = pill('Display', login, 'light');
  if (!showDisplayButtons) dsp.style.display = 'none';
  dsp.addEventListener('click', showSettings);
  layouts.push(() => { const ph = 30 * sc; place(dsp, W - 126 * sc - 14 - SAFE.r, Math.max(SAFE.t, 6) + 8, 126 * sc, ph); dsp.style.visibility = kbMode ? 'hidden' : ''; });

  // ------------------------------------------------------------------ typed chat: the game's own text box shows the text live;
  // this invisible input only brings up the keyboard and passes every keystroke to the game
  const tin = document.createElement('input');
  tin.id = 'ttr-textin'; tin.type = 'text'; tin.maxLength = 120; tin.autocomplete = 'off'; tin.autocapitalize = 'sentences'; tin.autocorrect = 'off';
  tin.setAttribute('enterkeyhint', 'send');
  root.appendChild(tin);
  let textOn = false, askAt = 0;
  // The game server rejects chat that is not plain text (an iPhone keyboard turns ' and " into curly quotes, adds emoji, long dashes...)
  // and throws the player out with error 127. Keep typed chat to plain characters.
  function plainChat(t) {
    return String(t).replace(/[\u2018\u2019\u201A\u201B\u2032]/g, "'").replace(/[\u201C\u201D\u201E\u2033]/g, '"')
      .replace(/[\u2013\u2014\u2212]/g, '-').replace(/\u2026/g, '...').replace(/[\u00A0\u2007\u202F]/g, ' ')
      .replace(/[^\x20-\x7E]/g, '');
  }
  tin.addEventListener('input', () => { const c = plainChat(tin.value); if (c !== tin.value) tin.value = c; T.txtVal = c; T.txtIn++; });
  // a moment's wait before sending: when Return is pressed the keyboard may still be finishing an auto-correction of the last word
  onEnter(tin, () => setTimeout(() => { T.txtVal = plainChat(tin.value); T.txtSub++; tin.blur(); }, 90));
  tin.addEventListener('focus', () => { kbHold = true; plog('JS| tin focus; inner ' + innerWidth + 'x' + innerHeight + ' vv ' + (window.visualViewport ? visualViewport.width + 'x' + visualViewport.height : '-')); });
  // After a chat is sent the invisible input gives up focus and nothing is left focused, so a hardware keyboard (iPad Magic Keyboard,
  // a desktop) stops reaching the game. Hand the focus back to the game's canvas.
  function gameFocus() {
    const cv = document.querySelector('canvas.emscripten'); if (!cv) return;
    if (!cv.hasAttribute('tabindex')) cv.tabIndex = -1;
    try { cv.focus({ preventScroll: true }); } catch (e) {}
  }
  tin.addEventListener('blur', () => {
    kbHold = false; plog('JS| tin blur'); setTimeout(() => { window.scrollTo(0, 0); relayout(); }, 250);
    setTimeout(() => { const a = document.activeElement; if (!a || a === document.body || a === tin) gameFocus(); }, 0);
  });
  // a key press while nothing is focused: focus the game so the following keys reach it
  document.addEventListener('keydown', () => { const a = document.activeElement; if ((!a || a === document.body) && hud.style.display !== 'none') gameFocus(); }, true);
  // iOS only opens the keyboard from a real tap, and the game answers a tap a moment later. So a tap on the typed-chat button
  // (top-left corner) opens the keyboard right away; if the game then does not open a text box, it is closed again.
  function kbTap(e) {
    if (hud.style.display === 'none' || document.activeElement === tin) return;
    const p = (e.changedTouches && e.changedTouches[0]) || e;
    // only the blue typed-chat button (the game puts it at 0.135 of the screen height from the left, the green Speed Chat button
    // at 0.36 and beyond): the keyboard opens at once, and closes again if the game opens no text box
    // (the game keeps its buttons inside the safe area, so the notch side moves them over by that much)
    const inCorner = p.clientX < SAFE.l + H * 0.13 && p.clientY < SAFE.t + H * 0.14;
    // the Type a Name button on the name screen: the game tells us where it is (T.typeBtn, as fractions of the window)
    let onTypeBtn = false;
    const nb = String(T.typeBtn || '').split(',').map(Number);
    const cv = document.querySelector('canvas.emscripten');
    if (nb.length === 2 && isFinite(nb[0]) && isFinite(nb[1]) && cv) {
      const r = cv.getBoundingClientRect();
      onTypeBtn = Math.hypot(p.clientX - (r.left + nb[0] * r.width), p.clientY - (r.top + nb[1] * r.height)) < r.height * 0.1;
    }
    if (!textOn && !inCorner && !onTypeBtn) return;
    try { tin.focus({ preventScroll: true }); } catch (err) {}
    askAt = Date.now();
    setTimeout(() => { if (!textOn && Date.now() - askAt >= 1400) tin.blur(); }, 1500);
  }
  let lastTap = 0;
  const kbOnce = (e) => { if (Date.now() - lastTap < 400) return; lastTap = Date.now(); plog('JS| tap ' + e.type + ' at ' + Math.round((e.changedTouches ? e.changedTouches[0] : e).clientX) + ',' + Math.round((e.changedTouches ? e.changedTouches[0] : e).clientY) + ' W=' + W + ' H=' + H); kbTap(e); };
  document.addEventListener('touchend', kbOnce, true);
  document.addEventListener('pointerup', kbOnce, true);
  addEventListener('resize', () => plog('JS| resize inner ' + innerWidth + 'x' + innerHeight + ' kbHold=' + kbHold));
  T.setText = function (on, val) {
    textOn = !!+on; plog('JS| setText ' + on);
    if (textOn) { tin.value = val || ''; try { tin.focus({ preventScroll: true }); } catch (e) {} } else { tin.blur(); }
  };

  // ------------------------------------------------------------------ hardware keyboard (iPad Magic Keyboard, a desktop): the touch controls hide while
  // one is used, and keys can be remapped. A page cannot ask what keyboard is attached, so a real key press outside typed chat is the sign;
  // a finger on the screen after a quiet spell brings the controls back. A remapped key is swallowed and the game's own key is sent instead,
  // so the game's keys keep working too.
  const GAME_KEYS = [        // [id, label, the game's key]
    ['fwd', 'Walk forward', 'ArrowUp'], ['back', 'Walk back', 'ArrowDown'], ['left', 'Turn left', 'ArrowLeft'], ['right', 'Turn right', 'ArrowRight'],
    ['jump', 'Jump', 'ControlLeft'], ['pie', 'Throw pie', 'Delete'], ['tasks', 'Tasks', 'End'], ['gags', 'Gags', 'Home'],
    ['map', 'Map', 'AltLeft'], ['book', 'Shticker Book', 'F8'], ['friends', 'Friends', 'F7'], ['camera', 'Camera view', 'Tab']];
  const KEYINFO = { ArrowUp: ['ArrowUp', 38], ArrowDown: ['ArrowDown', 40], ArrowLeft: ['ArrowLeft', 37], ArrowRight: ['ArrowRight', 39],
    ControlLeft: ['Control', 17], Delete: ['Delete', 46], End: ['End', 35], Home: ['Home', 36], AltLeft: ['Alt', 18], F8: ['F8', 119], F7: ['F7', 118], Tab: ['Tab', 9] };
  const actTarget = {}; GAME_KEYS.forEach(([id, , code]) => { actTarget[id] = code; });
  let keyMap = {};           // the player's key (event code) -> action id
  try { keyMap = JSON.parse(lsGet('ttr_keys', '{}')) || {}; } catch (e) { keyMap = {}; }
  const saveKeys = () => lsSet('ttr_keys', JSON.stringify(keyMap));
  let kbUsed = false, lastKeyAt = 0, keyCapture = null;
  const heldKeys = {};       // the player's key -> the game key sent for it, until it comes up
  const hasTouchScreen = () => !!(window.matchMedia && matchMedia('(any-pointer: coarse)').matches);
  function touchHidden() { const m = lsGet('ttr_touch', 'auto'); return m === 'hide' || (m === 'auto' && (kbUsed || !hasTouchScreen())); }
  function applyTouchUI() { T.setUI(uiArgs[0], uiArgs[1], uiArgs[2]); }
  function keyName(code) {
    const named = { ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→', ControlLeft: 'Ctrl', ControlRight: 'Right Ctrl', AltLeft: 'Alt/Option',
      AltRight: 'Right Alt', ShiftLeft: 'Shift', ShiftRight: 'Right Shift', MetaLeft: 'Cmd', MetaRight: 'Right Cmd', Space: 'Space', Backspace: 'Backspace' };
    if (named[code]) return named[code];
    return String(code).replace(/^Key/, '').replace(/^Digit/, '').replace(/^Numpad/, 'Num ');
  }
  // typing: the game has a text box open, or a page text field (sign-in, settings) has the focus. The hidden chat input (tin) can keep
  // the focus after a message is sent, so it only counts while the game's text box is open (textOn).
  function typing() { const a = document.activeElement; return textOn || (a && a !== tin && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA')); }
  function sendKey(type, code, e) {
    const [key, kc] = KEYINFO[code];
    const down = type === 'keydown';
    const ev = new KeyboardEvent(type, { key, code, keyCode: kc, which: kc, repeat: !!(e && e.repeat), bubbles: true, cancelable: true,
      ctrlKey: (code === 'ControlLeft' && down) || !!(e && e.ctrlKey), altKey: (code === 'AltLeft' && down) || !!(e && e.altKey), shiftKey: !!(e && e.shiftKey) });
    try { Object.defineProperty(ev, 'keyCode', { get: () => kc }); Object.defineProperty(ev, 'which', { get: () => kc }); } catch (err) {}
    ev.ttrMade = true;
    const cv = document.querySelector('canvas.emscripten') || document;
    try { cv.dispatchEvent(ev); } catch (err) { plog('JS| key send failed ' + err); }
  }
  function onKey(e) {
    if (e.ttrMade || !e.isTrusted) return;   // only a real keyboard counts (the TASKS button sends its own End key)
    if (keyCapture) { e.preventDefault(); e.stopImmediatePropagation(); if (e.type === 'keydown') keyCapture(e); return; }
    if (hud.style.display === 'none' || typing()) return;
    if (e.type === 'keydown' && e.key !== 'Meta') {
      lastKeyAt = Date.now();
      if (!kbUsed) { kbUsed = true; plog('JS| keyboard in use (' + e.code + ')'); applyTouchUI(); }
    }
    const id = keyMap[e.code];
    if (!id || !actTarget[id]) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const a = document.activeElement;
    if (a === tin) tin.blur();          // (its blur hands the focus back to the game)
    else if (!a || a === document.body) gameFocus();
    if (e.type === 'keydown') { heldKeys[e.code] = actTarget[id]; sendKey('keydown', actTarget[id], e); }
    else { const t = heldKeys[e.code] || actTarget[id]; delete heldKeys[e.code]; sendKey('keyup', t, e); }
  }
  addEventListener('keydown', onKey, true); addEventListener('keyup', onKey, true);
  // The game takes typed letters from keypress, which a cancelled keydown should already stop; some browsers send it anyway.
  // A remapped key must never type its letter (that opens typed chat).
  addEventListener('keypress', (e) => {
    if (e.ttrMade || keyCapture || typing()) return;
    if ((e.code && keyMap[e.code]) || (!e.code && Object.keys(heldKeys).some((c) => c === 'Key' + String(e.key).toUpperCase()))) {
      e.preventDefault(); e.stopImmediatePropagation();
    }
  }, true);
  // switching away with a remapped key held: let it go in the game too
  addEventListener('blur', () => { Object.keys(heldKeys).forEach((c) => { sendKey('keyup', heldKeys[c]); delete heldKeys[c]; }); });
  addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'touch' && kbUsed && Date.now() - lastKeyAt > 20000) { kbUsed = false; plog('JS| touch again: controls back'); applyTouchUI(); }
  }, true);
  function showKeys() {
    keyCapture = null;
    setWrap.innerHTML = ''; setWrap.style.display = '';
    const card = el('div', 'card', setWrap);
    const h = el('h2', null, card); h.textContent = 'Keyboard keys';
    const tip = el('div', 'tip', card); tip.textContent = 'Tap an action, then press the key you want for it. The game\'s own keys keep working too.';
    GAME_KEYS.forEach(([id, label, code]) => {
      const r = el('div', 'row', card);
      const l = el('div', 'lbl', r); l.textContent = label;
      const sm = el('small', null, l); sm.textContent = 'Game key: ' + keyName(code);
      const g = el('div', 'seg', r);
      const b = el('button', null, g);
      const mine = Object.keys(keyMap).filter((c) => keyMap[c] === id);
      b.textContent = mine.length ? mine.map(keyName).join(', ') : keyName(code);
      if (mine.length) b.classList.add('sel');
      b.addEventListener('click', () => {
        [...card.querySelectorAll('.seg button.wait')].forEach((x) => x.classList.remove('wait'));
        b.classList.add('wait'); b.textContent = 'Press a key... (Esc cancels)';
        keyCapture = (e) => {
          keyCapture = null;
          if (e.code && e.code !== 'Escape') {
            Object.keys(keyMap).forEach((c) => { if (keyMap[c] === id) delete keyMap[c]; });
            if (e.code !== code) keyMap[e.code] = id;     // the game's own key needs no remap
            saveKeys(); plog('JS| key ' + e.code + ' -> ' + id);
          }
          showKeys();
        };
      });
    });
    const reset = el('button', 'act', card); reset.textContent = 'Use the game\'s keys';
    reset.addEventListener('click', () => { keyMap = {}; saveKeys(); showKeys(); });
    const wasd = el('button', 'act', card); wasd.textContent = 'Use WASD and Space';
    wasd.addEventListener('click', () => { keyMap = { KeyW: 'fwd', KeyS: 'back', KeyA: 'left', KeyD: 'right', Space: 'jump' }; saveKeys(); showKeys(); });
    const back = el('button', 'act done', card); back.textContent = 'Back';
    back.addEventListener('click', () => { keyCapture = null; showSettings(); });
  }

  // ------------------------------------------------------------------ portrait: ask for landscape (iOS has no way to lock it)
  const rot = el('div', null, root);
  rot.id = 'ttr-rotate'; rot.style.display = 'none';
  rot.innerHTML = '<div class="ph"></div><div class="tx">Turn your phone sideways to play</div>';
  function checkRotate() {
    const coarse = window.matchMedia && matchMedia('(pointer: coarse)').matches;
    rot.style.display = (coarse && innerHeight > innerWidth && !installUp) ? '' : 'none';
  }
  addEventListener('resize', checkRotate); addEventListener('orientationchange', () => setTimeout(checkRotate, 150));

  // ------------------------------------------------------------------ go
  measure(); relayout(); checkRotate();
  showLoad(true); setStatus('Getting ready...', '', 0);
  loadArt();
  // ------------------------------------------------------------------ opened in a normal browser tab on iPhone/iPad: show how to add it to the Home Screen
  const ua = navigator.userAgent || '';
  const isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const standalone = window.navigator.standalone === true || (window.matchMedia && matchMedia('(display-mode: standalone)').matches);
  const qs = new URLSearchParams(location.search);
  let skipInstall = false; try { skipInstall = sessionStorage.getItem('ttr.skipInstall') === '1'; } catch (e) {}
  const isAndroid = /Android/i.test(ua);
  const needInstall = (qs.get('install') === '1') || ((isIOS || isAndroid) && !standalone && !skipInstall && qs.get('install') !== '0');
  let installEvt = null;                       // Chrome on Android offers a one-tap install through this event
  addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); installEvt = e; const b = document.getElementById('ttr-installbtn'); if (b) b.style.display = ''; });
  // Android: full screen + landscape lock from the first tap (a normal browser tab cannot lock the rotation any other way).
  // Everywhere else full screen starts with PLAY (iPhone has no full screen for pages: there the Home Screen app is full screen)
  function isFullscreen() { return !!(document.fullscreenElement || document.webkitFullscreenElement); }
  function goFull() {
    const d = document.documentElement, req = d.requestFullscreen || d.webkitRequestFullscreen;
    if (!req || isFullscreen()) return;
    try { const r = req.call(d, { navigationUI: 'hide' }); if (r && r.then) r.then(() => { try { screen.orientation.lock('landscape').catch(() => {}); } catch (e) {} }).catch(() => {}); } catch (e) {}
  }
  if (isAndroid && !standalone) { const once = () => { removeEventListener('pointerup', once, true); goFull(); }; addEventListener('pointerup', once, true); }
  // keep the screen on while playing
  let wl = null;
  function keepAwake() { try { if (navigator.wakeLock && !document.hidden) navigator.wakeLock.request('screen').then((l) => { wl = l; }).catch(() => {}); } catch (e) {} }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && hud.style.display !== 'none') keepAwake(); });
  // Open Toontown test build: served from the PC's own test server (port 8002), the files and the game connection are on that same machine
  if (!prefs.mode && location.port === '8002') { LS.setItem('ttr_srv_mode', 'custom'); LS.setItem('ttr_srv_res', location.origin); LS.setItem('ttr_srv_game', 'ws://' + location.hostname + ':8766'); }
  function begin() { beginDownload(); }
  if (needInstall) {
    installUp = true; checkRotate();
    const ins = el('div', null, root); ins.id = 'ttr-install';
    const share = '<svg class="shr" viewBox="0 0 24 24" width="26" height="26" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M12 3v12M8 7l4-4 4 4M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1"/></svg>';
    const steps = isAndroid
      ? '<ol><li><i>1</i><span>Open this page in your browser app itself (Chrome works best), not inside another app</span></li>' +
        '<li><i>2</i><span>Tap the &#8942; menu, then &ldquo;Install app&rdquo; (or &ldquo;Add to Home screen&rdquo;)</span></li>' +
        '<li><i>3</i><span>Open Glonktown from your Home screen. If it still shows a bar at the top, install it again from Chrome</span></li></ol>' +
        '<button class="go" id="ttr-installbtn" style="display:none;text-decoration:none;background:#ffd926;color:#733805;border-radius:14px;padding:10px 22px;box-shadow:0 3px 0 rgba(0,0,0,.35);text-shadow:none">Install app</button>'
      : '<ol><li><i>1</i><span>Tap the Share button ' + share + ' in Safari (tap &middot;&middot;&middot; first if you do not see it)</span></li>' +
        '<li><i>2</i><span>Tap &ldquo;View More&rdquo; if you see it, then scroll down and tap &ldquo;Add to Home Screen&rdquo;</span></li>' +
        '<li><i>3</i><span>Tap Add, then open Glonktown from your Home Screen</span></li></ol>';
    ins.innerHTML = '<div class="box"><div class="ic">' + share.replace('width="26" height="26"', 'width="30" height="30"') + '</div>' +
      '<div class="h">Add Glonktown to your Home Screen</div>' + steps +
      '<button class="go skip">Continue in the browser anyway</button></div>';
    const ib = ins.querySelector('#ttr-installbtn');
    if (ib) { if (installEvt) ib.style.display = ''; ib.addEventListener('click', () => { if (installEvt) { installEvt.prompt(); installEvt.userChoice.then(() => {}).catch(() => {}); } }); }
    ins.querySelector('.skip').addEventListener('click', () => {
      if (isAndroid) goFull();
      try { sessionStorage.setItem('ttr.skipInstall', '1'); } catch (e) {}
      installUp = false; ins.remove(); checkRotate(); begin();
    });
  } else begin();
  // screen facts for the test server's log (to work out odd screens such as foldables)
  function glInfo(c) {
    try {
      if (!c) return '-';
      const gl = c.getContext('webgl2') || c.getContext('webgl'); if (!gl) return 'none';
      const a = gl.getContextAttributes() || {};
      return (gl instanceof WebGL2RenderingContext ? 'webgl2' : 'webgl1') + ' depth=' + gl.getParameter(gl.DEPTH_BITS) + ' stencil=' + gl.getParameter(gl.STENCIL_BITS) + ' aa=' + a.antialias + ' samples=' + gl.getParameter(gl.SAMPLES);
    } catch (e) { return 'err ' + e; }
  }
  function envLog(tag) {
    try {
      const c = document.querySelector('canvas.emscripten'); const r = c ? c.getBoundingClientRect() : null; const vv = window.visualViewport;
      plog('JS| env ' + tag + ' inner ' + innerWidth + 'x' + innerHeight + ' outer ' + outerWidth + 'x' + outerHeight + ' screen ' + screen.width + 'x' + screen.height + ' avail ' + screen.availWidth + 'x' + screen.availHeight +
        ' dpr ' + devicePixelRatio + ' vv ' + (vv ? Math.round(vv.width) + 'x' + Math.round(vv.height) + '@' + Math.round(vv.offsetLeft) + ',' + Math.round(vv.offsetTop) + ' s' + vv.scale : '-') +
        ' standalone ' + standalone + ' dm ' + (matchMedia('(display-mode: standalone)').matches ? 'standalone' : matchMedia('(display-mode: fullscreen)').matches ? 'fullscreen' : 'browser') +
        ' orient ' + ((screen.orientation && screen.orientation.type) || '-') + ' safe ' + SAFE.t + ',' + SAFE.r + ',' + SAFE.b + ',' + SAFE.l +
        ' canvas ' + (c ? c.width + 'x' + c.height + ' css ' + Math.round(r.width) + 'x' + Math.round(r.height) + '@' + Math.round(r.left) + ',' + Math.round(r.top) : '-') + ' win ' + T.winW + 'x' + T.winH + ' panda ' + T.pw + 'x' + T.ph + ' gl ' + glInfo(c) + ' ua ' + ua);
    } catch (e) { plog('JS| env failed ' + e); }
  }
  setTimeout(() => envLog('load'), 1500); setTimeout(() => envLog('+10s'), 10000); setTimeout(() => envLog('+40s'), 40000); setTimeout(() => envLog('+90s'), 90000); setTimeout(() => envLog('+180s'), 180000);
  addEventListener('resize', () => setTimeout(() => envLog('resize'), 300));
  // Touch on the game itself: the game only understands the mouse, and a finger that slides (aiming a fishing cast, dragging in a
  // minigame) never produces mouse movement in a phone browser. Turn a touch on the game into mouse move / press / release.
  // The game's menus only react to a press on a button it has already seen the pointer arrive on, so the press is sent a moment
  // after the move (a few frames), and held a moment before it is released. Sending all three at once made quick taps on small
  // buttons (the chat menus) miss.
  (function () {
    const DOWN_DELAY = 70, MIN_HOLD = 60;
    let active = null, last = null, pressed = false, downTimer = null, downPlanned = 0;
    const isGame = (t) => t && t.classList && t.classList.contains('emscripten');
    function fire(type, e) {
      const cv = document.querySelector('canvas.emscripten'); if (!cv) return;
      cv.dispatchEvent(new MouseEvent(type, { bubbles: true, cancelable: true, view: window, clientX: e.clientX, clientY: e.clientY,
        screenX: e.screenX, screenY: e.screenY, button: 0, buttons: type === 'mouseup' ? 0 : 1 }));
    }
    function press() { if (downTimer) { clearTimeout(downTimer); downTimer = null; } if (!pressed) { pressed = true; fire('mousedown', last); } }
    document.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse' || !isGame(e.target) || active !== null) return;
      active = e.pointerId; last = e; e.preventDefault();
      fire('mousemove', e);
      downPlanned = Date.now() + DOWN_DELAY;
      downTimer = setTimeout(press, DOWN_DELAY);
    }, { capture: true, passive: false });
    document.addEventListener('pointermove', (e) => { if (e.pointerId === active) { e.preventDefault(); last = e; fire('mousemove', e); } }, { capture: true, passive: false });
    const up = (e) => {
      if (e.pointerId !== active) return;
      active = null; last = e;
      const wait = Math.max(0, downPlanned + MIN_HOLD - Date.now());
      setTimeout(() => { press(); pressed = false; fire('mouseup', e); }, wait);
    };
    document.addEventListener('pointerup', up, true);
    document.addEventListener('pointercancel', up, true);
    document.addEventListener('touchstart', (e) => { if (isGame(e.target)) e.preventDefault(); }, { capture: true, passive: false });   // no second, browser-made set of mouse events
  })();
  // The page's own start-up code resizes the drawing surface when the window changes, without telling the game, so the game can end up
  // drawing into a smaller area than the surface (a grey strip at the edge). If the game agrees with the size we asked for but the surface
  // does not, put the surface right.
  let fixes = 0;
  setInterval(() => {
    if (kbHold || hud.style.display === 'none') return;
    const c = document.querySelector('canvas.emscripten'); if (!c) return;
    const w = +T.winW, h = +T.winH;
    if (w > 0 && h > 0 && +T.pw === w && +T.ph === h && (c.width !== w || c.height !== h)) {
      c.width = w; c.height = h; fixes++;
      if (fixes <= 5) plog('JS| env fixcanvas #' + fixes + ' set ' + w + 'x' + h);
    }
  }, 400);
  // No zooming: Safari ignores user-scalable=no, so a quick double tap or a pinch zooms the whole page in. Stop both.
  ['gesturestart', 'gesturechange', 'gestureend'].forEach((t) => document.addEventListener(t, (e) => e.preventDefault(), { passive: false }));
  (function () {
    let last = 0;
    document.addEventListener('touchend', (e) => {
      const now = Date.now();
      const tg = e.target;
      const typing = tg && tg.closest && tg.closest('input, textarea, select, [contenteditable]');
      if (now - last < 350 && !typing) e.preventDefault();      // the second tap of a double tap
      last = now;
    }, { passive: false });
  })();
  // developer channel (only on the local test server, port 8001): run Python source from debug_code.py in the game
  if (location.port === '8001' || location.port === '8002') {
    let lastCode = '';
    setInterval(async () => {
      try { const t = await (await fetch('/__code?' + Date.now(), { cache: 'no-store' })).text(); if (t && t !== lastCode) { lastCode = t; T.pycode = t; } } catch (e) {}
    }, 2000);
  }
})();
