import Alpine from '../vendor/alpine-3.17.4.min.js';
import { shell } from './shell.js';
import { bridge } from './game/bridge.js';
import { loading } from './screens/loading.js';
import { welcome } from './screens/welcome.js';
import { hasSignedInHere, login } from './screens/login.js';
import { downloadGameFiles } from './lib/downloader.js';
import { fetchGameConfig } from './lib/server.js';
import { visit } from './lib/storage.js';
import { log } from './lib/log.js';
import { relayout, relayoutSoon } from './lib/viewport.js';
import { goFullscreen, goFullscreenOnNextInput, isAndroid, isFullscreen, keepScreenAwake, standalone } from './lib/device.js';

// The way through the page: the welcome page, sign in, get the game files, then start the game.

let signedIn = null;      // { cookie, token }

export async function openWelcome(knownState) {
  shell.screen = 'welcome';
  Alpine.nextTick(() => { document.querySelector('#ttr .welcome').scrollTop = 0; });
  welcome.setState(knownState || 'checking');
  if (knownState) {
    welcome.recheckLater();
    return;
  }
  // back from a game that ended: straight on to the sign-in dialog, which says why
  const gameEnded = !!visit.get('ttr.ended');
  if (await welcome.checkServer() && gameEnded) openLogin();
}

export function openLogin(isNew = !hasSignedInHere()) {
  shell.screen = 'login';
  shell.titleRaised = true;
  login.open(isNew);
}

export async function signIn() {
  const result = await login.submit();
  if (result === 'closed') {
    openWelcome('closed');
  } else if (result) {
    signedIn = result;
    downloadAndPlay();
  }
}

export async function downloadAndPlay() {
  shell.screen = 'loading';
  loading.reset();
  try {
    await downloadGameFiles((status, detail, progress) => loading.report(status, detail, progress));
  } catch (e) {
    console.error(e);
    loading.fail(String(e?.stack || e));
    shell.titleRaised = true;
    return;
  }
  loading.showStarting();
  bridge.gameConfig = await fetchGameConfig();
  bridge.cookie = signedIn.cookie;
  bridge.playToken = signedIn.token || '';
  bridge.go = true;
  log('JS| session user: ' + signedIn.cookie.split(':')[0]);      // the name only, never the password
}

// called by the game once it is drawing
function gameStarted() {
  shell.screen = 'game';
  relayout();
  keepScreenAwake();
  // not full screen after all (refused, or left while loading): the first tap or key in the game makes it so
  if (!standalone && !isFullscreen()) goFullscreenOnNextInput();
  relayoutSoon(500, 2000, 6000);
}

// Called by the game when it has quit (main.py _end_game). The game cannot be started twice in one page, so start the page again: that
// also leaves full screen, and the sign-in dialog says why the player is back.
function gameEnded(kind, detail) {
  visit.set('ttr.ended', JSON.stringify([String(kind), String(detail || '')]));
  location.reload();
}

export function skipInstall() {
  if (isAndroid) goFullscreen();
  visit.set('ttr.skipInstall', '1');
  shell.installing = false;
  openWelcome();
}

export function watchFlow() {
  bridge.started = gameStarted;
  bridge.ended = gameEnded;
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    if (shell.playing) keepScreenAwake();
    if (welcome.visible && welcome.state === 'closed') welcome.checkServer();
  });
}

// what the markup calls ($store.flow)
export const flow = { openLogin, signIn, downloadAndPlay, skipInstall };
