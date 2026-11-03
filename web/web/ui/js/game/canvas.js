import { bridge } from './bridge.js';
import { log } from '../lib/log.js';

// The game draws into pygbag's canvas and only listens to events sent to it.
export const gameCanvas = () => document.querySelector('canvas.emscripten');

export function sendToGame(event) {
  try { (gameCanvas() || document).dispatchEvent(event); } catch (e) { log('JS| sending ' + event.type + ' failed ' + e); }
}

// A key event for the game. `made` marks it as the page's own, so the keyboard handling (keyboard.js) lets it through.
export function sendKeyToGame(type, { key, code, keyCode }, modifiers = {}) {
  const event = new KeyboardEvent(type, { key, code, keyCode, which: keyCode, bubbles: true, cancelable: true, ...modifiers });
  // some browsers leave keyCode at 0 on made events; the game reads it
  try {
    Object.defineProperty(event, 'keyCode', { get: () => keyCode });
    Object.defineProperty(event, 'which', { get: () => keyCode });
  } catch {}
  event.ttrMade = true;
  sendToGame(event);
}

// After a chat is sent nothing is left focused, so a hardware keyboard (iPad Magic Keyboard, a desktop) stops reaching the game.
export function focusGame() {
  const canvas = gameCanvas();
  if (!canvas) return;
  if (!canvas.hasAttribute('tabindex')) canvas.tabIndex = -1;
  try { canvas.focus({ preventScroll: true }); } catch {}
}

// pygbag's start-up code resizes the canvas when the window changes, without telling the game, so the game can end up drawing into a
// smaller area than the canvas (a grey strip at the edge). If the game agrees with the size the page asked for but the canvas does
// not, put the canvas right.
export function keepCanvasSize(shouldCheck) {
  let fixes = 0;
  setInterval(() => {
    const canvas = gameCanvas();
    if (!shouldCheck() || !canvas) return;
    const width = +bridge.winW, height = +bridge.winH;
    if (width > 0 && height > 0 && +bridge.pw === width && +bridge.ph === height && (canvas.width !== width || canvas.height !== height)) {
      canvas.width = width;
      canvas.height = height;
      fixes++;
      if (fixes <= 5) log(`JS| env fixcanvas #${fixes} set ${width}x${height}`);
    }
  }, 400);
}
