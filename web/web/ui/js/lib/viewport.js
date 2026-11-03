import { bridge } from '../game/bridge.js';
import { saved } from './storage.js';
import { log } from './log.js';

// The page's size, measured in JavaScript rather than left to CSS: iOS (a Home Screen app especially) can report stale sizes, and the
// game must be told exactly what to draw at. Everything on screen is placed by CSS from the variables set here:
//   --screen-w, --screen-h   the window, in px
//   --sc                     the page scale: 1, or 1.45 on a tablet (the iOS app's own rule)
export const viewport = {
  width: 0,
  height: 0,
  scale: 1,
  safe: { top: 0, right: 0, bottom: 0, left: 0 },
  keyboardHold: false,    // in game, typed chat's keyboard is up: its resizing must not resize the game's window
};

const rootStyle = document.documentElement.style;
let measuredSize = '';

function measureSafeArea() {
  const probe = document.createElement('div');
  probe.style.cssText = 'position:absolute;visibility:hidden;padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px)';
  document.body.appendChild(probe);
  const style = getComputedStyle(probe);
  viewport.safe = {
    top: parseFloat(style.paddingTop) || 0,
    right: parseFloat(style.paddingRight) || 0,
    bottom: parseFloat(style.paddingBottom) || 0,
    left: parseFloat(style.paddingLeft) || 0,
  };
  probe.remove();
}

// Open Toontown test build: draw at the page's own pixel size by default (a phone's full screen resolution is too slow); the Display
// settings' picture quality, or ?res=1.5 / ?res=2, for sharper.
function pixelRatio() {
  const asked = parseFloat(new URLSearchParams(location.search).get('res') || saved.get('ttr_res') || '2') || 2;
  return Math.min(window.devicePixelRatio || 1, Math.max(0.5, Math.min(asked, 2)));
}

export function relayout() {
  if (viewport.keyboardHold) return;
  viewport.width = innerWidth;
  viewport.height = innerHeight;
  viewport.scale = Math.min(innerWidth, innerHeight) >= 700 ? 1.45 : 1;
  measuredSize = innerWidth + 'x' + innerHeight;
  measureSafeArea();

  rootStyle.setProperty('--screen-w', viewport.width + 'px');
  rootStyle.setProperty('--screen-h', viewport.height + 'px');
  rootStyle.setProperty('--sc', viewport.scale);

  const ratio = pixelRatio();
  bridge.winW = Math.round(viewport.width * ratio);
  bridge.winH = Math.round(viewport.height * ratio);
  bridge.safeL = viewport.safe.left;
  bridge.safeR = viewport.safe.right;
  bridge.safeT = viewport.safe.top;
  bridge.safeB = viewport.safe.bottom;
  bridge.vh = viewport.height;
}

export function relayoutSoon(...delays) {
  for (const ms of delays) setTimeout(relayout, ms);
}

// Opening the app already in landscape, iOS can stick on a viewport shorter than the window (932x371 on a 932x430 phone) until the
// phone is turned to portrait and back. If it is still short once the page has settled, try ways of making iOS measure again, one at a
// time, and log which one worked (a reload does not).
const viewportLooksStuck = () => innerWidth > innerHeight && outerWidth === innerWidth
  && outerHeight - innerHeight >= 20 && outerHeight - innerHeight <= 100;

const viewportMeta = () => document.querySelector('meta[name=viewport]');
const UNSTICK_TRIES = [
  ['viewport meta replaced', () => {
    const meta = viewportMeta();
    if (meta) { const copy = meta.cloneNode(); meta.remove(); document.head.appendChild(copy); }
  }],
  ['reflow', () => {
    const html = document.documentElement;
    html.style.display = 'none';
    void html.offsetHeight;
    html.style.display = '';
  }],
  ['scroll nudge', () => {
    document.body.style.minHeight = '120vh';
    scrollTo(0, 1);
    setTimeout(() => { scrollTo(0, 0); document.body.style.minHeight = ''; }, 50);
  }],
  ['viewport-fit toggled', () => {
    const meta = viewportMeta();
    if (!meta) return;
    const content = meta.getAttribute('content');
    meta.setAttribute('content', content.replace('viewport-fit=cover', 'viewport-fit=auto'));
    setTimeout(() => meta.setAttribute('content', content), 80);
  }],
  ['rotated page turn', () => {
    const html = document.documentElement;
    html.style.transition = 'none';
    html.style.transform = 'rotate(0.01deg)';
    void html.offsetHeight;
    html.style.transform = '';
  }],
];

let triesDone = 0;
function unstickViewport() {
  if (!viewportLooksStuck() || triesDone >= UNSTICK_TRIES.length) {
    if (triesDone > 0) {
      log('JS| env viewport ' + (viewportLooksStuck() ? 'still short after all tries: ' : 'fixed after: ')
        + UNSTICK_TRIES[triesDone - 1][0] + ' inner ' + innerWidth + 'x' + innerHeight);
    }
    return;
  }
  const [name, attempt] = UNSTICK_TRIES[triesDone++];
  try { attempt(); } catch {}
  setTimeout(() => {
    log(`JS| env vp try "${name}" inner ${innerWidth}x${innerHeight} outer ${outerWidth}x${outerHeight}`);
    relayout();
    setTimeout(unstickViewport, 200);
  }, 450);
}

export function watchViewport() {
  relayout();
  addEventListener('resize', relayout);
  addEventListener('orientationchange', () => setTimeout(relayout, 200));
  addEventListener('pageshow', () => setTimeout(relayout, 100));
  window.visualViewport?.addEventListener('resize', relayout);

  // iOS sometimes reports a stale window size until the phone is rotated: keep checking, and measure again a few times shortly after
  // start-up, so the game never stays drawn at the wrong size
  setInterval(() => { if (innerWidth + 'x' + innerHeight !== measuredSize) relayout(); }, 500);
  for (const ms of [250, 800, 1800, 3500]) {
    setTimeout(() => {
      try { scrollTo(0, 0); dispatchEvent(new Event('resize')); relayout(); } catch {}
    }, ms);
  }
  relayoutSoon(400, 1500, 4000, 9000);
  setTimeout(unstickViewport, 2500);
}
