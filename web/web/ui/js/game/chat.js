import { bridge } from './bridge.js';
import { focusGame, gameCanvas } from './canvas.js';
import { viewport, relayout } from '../lib/viewport.js';
import { onEnter } from '../lib/directives.js';
import { log } from '../lib/log.js';

// Typed chat. The game's own text box shows the text as it is typed; a hidden input (#ttr-textin) only brings up the on-screen keyboard
// and passes every keystroke to the game.
export const chat = {
  open: false,      // the game has a text box open
  input: null,
};

// The game server rejects chat that is not plain text (an iPhone keyboard turns ' and " into curly quotes, adds emoji, long dashes...)
// and throws the player out with error 127. Keep typed chat to plain characters.
function plainText(text) {
  return String(text)
    .replace(/[‘’‚‛′]/g, "'")
    .replace(/[“”„″]/g, '"')
    .replace(/[–—−]/g, '-')
    .replace(/…/g, '...')
    .replace(/[   ]/g, ' ')
    .replace(/[^\x20-\x7E]/g, '');
}

function openKeyboard() {
  try { chat.input.focus({ preventScroll: true }); } catch {}
}

// iOS only opens the keyboard from a real tap, and the game answers a tap a moment later. So a tap on a button that opens a text box
// opens the keyboard right away; if the game then opens no text box, it is closed again.
function isOnTextButton(point) {
  // the blue typed-chat button in the top-left corner (the game puts it 0.135 of the screen height from the left, the green Speed Chat
  // button at 0.36 and beyond). The game keeps its buttons inside the safe area, so the notch side moves them over by that much.
  const { safe, height } = viewport;
  if (point.clientX < safe.left + height * 0.13 && point.clientY < safe.top + height * 0.14) return true;

  // the Type a Name button on the name screen: the game says where it is (as fractions of the window)
  const [x, y] = String(bridge.typeBtn || '').split(',').map(Number);
  const canvas = gameCanvas();
  if (!canvas || !isFinite(x) || !isFinite(y)) return false;
  const box = canvas.getBoundingClientRect();
  return Math.hypot(point.clientX - (box.left + x * box.width), point.clientY - (box.top + y * box.height)) < box.height * 0.1;
}

let askedAt = 0;
function onTap(point) {
  if (document.activeElement === chat.input) return;
  if (!chat.open && !isOnTextButton(point)) return;
  openKeyboard();
  askedAt = Date.now();
  setTimeout(() => { if (!chat.open && Date.now() - askedAt >= 1400) chat.input.blur(); }, 1500);
}

export function watchChat({ isPlaying }) {
  const input = chat.input = document.getElementById('ttr-textin');

  input.addEventListener('input', () => {
    const text = plainText(input.value);
    if (text !== input.value) input.value = text;
    bridge.txtVal = text;
    bridge.txtIn++;
  });
  // a moment's wait before sending: when Return is pressed the keyboard may still be finishing an auto-correction of the last word
  onEnter(input, () => setTimeout(() => {
    bridge.txtVal = plainText(input.value);
    bridge.txtSub++;
    input.blur();
  }, 90));

  input.addEventListener('focus', () => {
    viewport.keyboardHold = true;
    const visual = window.visualViewport;
    log(`JS| tin focus; inner ${innerWidth}x${innerHeight} vv ` + (visual ? visual.width + 'x' + visual.height : '-'));
  });
  input.addEventListener('blur', () => {
    viewport.keyboardHold = false;
    log('JS| tin blur');
    setTimeout(() => { scrollTo(0, 0); relayout(); }, 250);
    setTimeout(() => {
      const focused = document.activeElement;
      if (!focused || focused === document.body || focused === input) focusGame();
    }, 0);
  });

  let lastTapAt = 0;
  const onTouchOrClick = (e) => {
    if (Date.now() - lastTapAt < 400) return;
    lastTapAt = Date.now();
    const point = e.changedTouches?.[0] ?? e;
    log(`JS| tap ${e.type} at ${Math.round(point.clientX)},${Math.round(point.clientY)} W=${viewport.width} H=${viewport.height}`);
    if (isPlaying()) onTap(point);
  };
  document.addEventListener('touchend', onTouchOrClick, true);
  document.addEventListener('pointerup', onTouchOrClick, true);
  addEventListener('resize', () => log(`JS| resize inner ${innerWidth}x${innerHeight} kbHold=${viewport.keyboardHold}`));

  bridge.setText = (open, text) => {
    chat.open = !!+open;
    log('JS| setText ' + open);
    if (chat.open) {
      input.value = text || '';
      openKeyboard();
    } else {
      input.blur();
    }
  };
}
