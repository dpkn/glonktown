import { saved } from './storage.js';

// The page and the game files always come from the page's own site. The game server (sign-in, game settings, logs and the game
// connection) is that same site, unless server.js (window.TTR_SERVER) names another one. ?server=<address> moves this device to a
// different server, and ?server= with nothing after it moves it back.
const asked = new URLSearchParams(location.search).get('server');
if (asked !== null) {
  if (asked.trim()) saved.set('ttr_server', asked.trim());
  else saved.remove('ttr_server');
}

const chosenOnThisDevice = saved.get('ttr_server') || '';
let origin = (chosenOnThisDevice || window.TTR_SERVER || '').replace(/\/+$/, '');
if (origin && !/^https?:\/\//i.test(origin)) origin = location.protocol + '//' + origin;

const pageSocketBase = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host;

export const isTestServer = location.port === '8001' || location.port === '8002';

export const server = {
  url: (path) => origin + path,
  // the local test server (port 8002) has its own bridge on 8766
  socketUrl: location.port === '8002' && !origin
    ? `ws://${location.hostname}:8766`
    : (origin ? origin.replace(/^http/i, 'ws') : pageSocketBase) + '/ws',
  // each server has its own logins
  userKey: chosenOnThisDevice ? 'ttr_user@' + origin.replace(/^https?:\/\//i, '') : 'ttr_user',
};

async function fetchWithin(ms, path) {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), ms);
  try {
    return await fetch(server.url(path), { cache: 'no-store', signal: abort.signal });
  } finally {
    clearTimeout(timer);
  }
}

// The game server answers for its settings file (200, or 404 without one) with a header any site may read. A server that is switched
// off answers nothing, or only with an error page from in between (the tunnel's), which the page may not read.
export async function serverIsOpen() {
  try {
    return (await fetchWithin(6000, '/gameconfig.json?t=' + Date.now())).status < 500;
  } catch {
    return false;
  }
}

// The server's game settings; no file, or no answer in 3 seconds, means the game's own defaults ('').
export async function fetchGameConfig() {
  try {
    const response = await fetchWithin(3000, '/gameconfig.json?t=' + Date.now());
    return response.ok ? await response.text() : '';
  } catch {
    return '';
  }
}
