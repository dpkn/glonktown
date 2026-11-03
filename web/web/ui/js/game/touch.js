import { gameCanvas } from './canvas.js';

// Touch on the game itself. The game only understands the mouse, and a finger that slides (aiming a fishing cast, dragging in a
// minigame) never produces mouse movement in a phone browser, so a touch on the game becomes mouse move / press / release.
// The game's menus only react to a press on a button it has already seen the pointer arrive on, so the press is sent a moment after
// the move (a few frames), and held a moment before it is released. Sending all three at once made quick taps on small buttons (the
// chat menus) miss.
const PRESS_DELAY = 70;
const MIN_HOLD = 60;

const isGame = (target) => target?.classList?.contains('emscripten');

function sendMouse(type, from) {
  gameCanvas()?.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window,
    clientX: from.clientX, clientY: from.clientY, screenX: from.screenX, screenY: from.screenY,
    button: 0, buttons: type === 'mouseup' ? 0 : 1,
  }));
}

export function touchAsMouse() {
  let finger = null, lastEvent = null, pressed = false, pressTimer = null, pressAt = 0;

  function press() {
    clearTimeout(pressTimer);
    pressTimer = null;
    if (!pressed) {
      pressed = true;
      sendMouse('mousedown', lastEvent);
    }
  }

  document.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' || !isGame(e.target) || finger !== null) return;
    finger = e.pointerId;
    lastEvent = e;
    e.preventDefault();
    sendMouse('mousemove', e);
    pressAt = Date.now() + PRESS_DELAY;
    pressTimer = setTimeout(press, PRESS_DELAY);
  }, { capture: true, passive: false });

  document.addEventListener('pointermove', (e) => {
    if (e.pointerId !== finger) return;
    e.preventDefault();
    lastEvent = e;
    sendMouse('mousemove', e);
  }, { capture: true, passive: false });

  const lift = (e) => {
    if (e.pointerId !== finger) return;
    finger = null;
    lastEvent = e;
    setTimeout(() => {
      press();
      pressed = false;
      sendMouse('mouseup', e);
    }, Math.max(0, pressAt + MIN_HOLD - Date.now()));
  };
  document.addEventListener('pointerup', lift, true);
  document.addEventListener('pointercancel', lift, true);

  // no second, browser-made set of mouse events
  document.addEventListener('touchstart', (e) => { if (isGame(e.target)) e.preventDefault(); }, { capture: true, passive: false });
}

// No zooming: Safari ignores user-scalable=no, so a quick double tap or a pinch zooms the whole page in. Stop both.
export function preventZoom() {
  for (const type of ['gesturestart', 'gesturechange', 'gestureend']) {
    document.addEventListener(type, (e) => e.preventDefault(), { passive: false });
  }
  let lastTouchEnd = 0;
  document.addEventListener('touchend', (e) => {
    const now = Date.now();
    const inTextField = e.target?.closest?.('input, textarea, select, [contenteditable]');
    if (now - lastTouchEnd < 350 && !inTextField) e.preventDefault();     // the second tap of a double tap
    lastTouchEnd = now;
  }, { passive: false });
}
