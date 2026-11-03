import { bridge } from '../game/bridge.js';

// Gets the game files into the game's file system. They come as packs (uncompressed zips, listed in packs.json with their size and a
// hash of their contents), saved on the device so they are not downloaded every launch: in the Cache API on secure (https) pages, in
// IndexedDB everywhere else.

const ASSETS = '/data/data/game/assets/';
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const megabytes = (bytes) => Math.round(bytes / 1e6);

const packStore = (() => {
  let opening = null;
  function open() {
    opening ??= new Promise((resolve, reject) => {
      if (typeof indexedDB === 'undefined') { reject(new Error('no IndexedDB')); return; }
      const request = indexedDB.open('ttr', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('packs');
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    return opening;
  }
  async function transaction(mode, run) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('packs', mode);
      const request = run(tx.objectStore('packs'));
      tx.oncomplete = () => resolve(request?.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  }
  return {
    get: (key) => transaction('readonly', (s) => s.get(key)),
    put: (key, value) => transaction('readwrite', (s) => s.put(value, key)),
    keys: () => transaction('readonly', (s) => s.getAllKeys()),
    delete: (key) => transaction('readwrite', (s) => s.delete(key)),
  };
})();

function writeGameFile(path, data) {
  try { window.FS.mkdirTree(path.slice(0, path.lastIndexOf('/'))); } catch { /* exists */ }
  window.FS.writeFile(path, data);
}

// Reads a zip as it streams in, handing over each file. Packs are made without compression or data descriptors, so every entry's size
// is in its local header.
async function unzipStream(body, { onBytes, onFile, onChunk }) {
  const reader = body.getReader();
  let buffer = new Uint8Array(1 << 20), length = 0, position = 0;

  async function have(bytes) {
    while (length - position < bytes) {
      const { done, value } = await reader.read();
      if (done) return false;
      onBytes(value.length);
      onChunk?.(value);
      if (length + value.length > buffer.length) {
        if (position > 0) { buffer.copyWithin(0, position, length); length -= position; position = 0; }
        if (length + value.length > buffer.length) {
          const bigger = new Uint8Array(Math.max(buffer.length * 2, length + value.length));
          bigger.set(buffer.subarray(0, length));
          buffer = bigger;
        }
      }
      buffer.set(value, length);
      length += value.length;
    }
    return true;
  }

  const decoder = new TextDecoder();
  while (await have(30)) {
    const header = new DataView(buffer.buffer, buffer.byteOffset + position, 30);
    if (header.getUint32(0, true) !== 0x04034b50) break;      // the central directory: no more files
    const flags = header.getUint16(6, true), method = header.getUint16(8, true);
    const size = header.getUint32(18, true), nameLength = header.getUint16(26, true), extraLength = header.getUint16(28, true);
    if ((flags & 8) || method !== 0) throw new Error('unsupported pack format');
    if (!(await have(30 + nameLength + extraLength))) throw new Error('pack ended early');
    const name = decoder.decode(buffer.subarray(position + 30, position + 30 + nameLength));
    position += 30 + nameLength + extraLength;
    if (!(await have(size))) throw new Error('pack ended early');
    if (!name.endsWith('/')) onFile(name, buffer.subarray(position, position + size));
    position += size;
  }
  try { await reader.cancel(); } catch {}
}

async function waitForGameEngine(report) {
  report('Getting ready...', '', 0);
  let waited = 0;
  while (!(window.FS && bridge.pyReady)) {
    await sleep(150);
    waited += 150;
    if (waited === 30000) report('Getting ready...', 'Starting the game engine. This can take a little while the first time.', 0);
    if (waited === 90000) report('Getting ready...', 'Still starting. If nothing changes, reload this page.', 0);
  }
}

// report(status, detail, fraction done) is called as it goes
export async function downloadGameFiles(report) {
  await waitForGameEngine(report);

  report('Checking game files...', '', 0);
  const packs = await (await fetch('/packs.json?t=' + Date.now(), { cache: 'no-store' })).json();   // [name, size, hash]
  const totalBytes = packs.reduce((sum, [, size]) => sum + size, 0);

  let cache = null;
  try {
    if (typeof caches !== 'undefined' && !/nocache/.test(location.search)) cache = await caches.open('ttr-packs-v1');
  } catch {}

  // packs.json is always fetched fresh, and each pack is saved under a hash of its contents: a pack that changed gets a new address, so
  // the saved copy is never used for it, and saved packs that are no longer listed are deleted
  const packUrl = (name, hash) => '/_packs/' + name + '.zip?v=' + hash;
  const wanted = new Set(packs.map(([name, , hash]) => packUrl(name, hash)));
  try {
    if (cache) {
      for (const request of await cache.keys()) {
        if (!wanted.has(request.url.replace(location.origin, '')) && !wanted.has(request.url)) await cache.delete(request);
      }
    } else {
      for (const key of await packStore.keys()) if (!wanted.has(key)) await packStore.delete(key);
    }
  } catch { /* cleaning up is optional */ }

  let bytesDone = 0, packsDone = 0, downloading = false;
  const progress = () => report(downloading ? 'Downloading game files' : 'Loading game files',
    `${megabytes(bytesDone)} of ${megabytes(totalBytes)} MB   (${packsDone} of ${packs.length} packs)`,
    totalBytes ? bytesDone / totalBytes : 0);

  for (const [name, , hash] of packs) {
    const url = packUrl(name, hash);
    let body, saving = null, chunks = null;

    const savedBlob = cache ? null : await packStore.get(url).catch(() => null);
    const cached = cache ? await cache.match(url) : null;
    if (savedBlob) {
      body = savedBlob.stream();
    } else if (cached) {
      body = cached.body;
    } else {
      downloading = true;
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`could not download ${name} (${response.status})`);
      if (cache) {
        const [forUnzip, forCache] = response.body.tee();
        body = forUnzip;
        saving = cache.put(url, new Response(forCache, { headers: { 'content-type': 'application/zip' } })).catch(() => {});
      } else {
        body = response.body;
        chunks = [];
      }
    }

    await unzipStream(body, {
      onBytes: (n) => { bytesDone += n; progress(); },
      onFile: (path, data) => {
        const destination = path.startsWith('_code/') ? ASSETS + path.slice(6) : ASSETS + 'resources/' + path;
        writeGameFile(destination, data.slice());
      },
      onChunk: chunks && ((chunk) => chunks.push(chunk)),
    });

    if (saving) await saving;
    if (chunks) {
      try { await packStore.put(url, new Blob(chunks, { type: 'application/zip' })); }
      catch (e) { console.warn('could not save ' + name, e); }
    }
    packsDone++;
    progress();
    await sleep(0);
  }
  report('Ready', '', 1);
}
