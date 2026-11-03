import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { saved } from '../lib/storage.js';
import { log } from '../lib/log.js';
import { focusGame, sendKeyToGame } from './canvas.js';
import { chat } from './chat.js';

// A hardware keyboard (iPad Magic Keyboard, a desktop). A page cannot ask what keyboard is attached, so a real key press outside typed
// chat is the sign one is used: the touch controls then hide (hud.js), and a finger on the screen after a quiet spell brings them back.
// Keys can be remapped: a remapped key is swallowed and the game's own key is sent instead, so the game's keys keep working too.

export const GAME_ACTIONS = [
  { id: 'fwd', label: 'Walk forward', gameKey: 'KeyW' },
  { id: 'back', label: 'Walk back', gameKey: 'KeyS' },
  { id: 'left', label: 'Turn left', gameKey: 'KeyA' },
  { id: 'right', label: 'Turn right', gameKey: 'KeyD' },
  { id: 'jump', label: 'Jump', gameKey: 'Space' },
  { id: 'run', label: 'Run (hold)', gameKey: 'ShiftLeft' },
  { id: 'pie', label: 'Throw pie', gameKey: 'Delete' },
  { id: 'tasks', label: 'Tasks', gameKey: 'End' },
  { id: 'gags', label: 'Gags', gameKey: 'Home' },
  { id: 'map', label: 'Map', gameKey: 'AltLeft' },
  { id: 'book', label: 'Shticker Book', gameKey: 'F8' },
  { id: 'friends', label: 'Friends', gameKey: 'F7' },
  { id: 'camera', label: 'Camera view', gameKey: 'Tab' },
];

// the game's default keys (the WASD preset of the game's Controls tab)
const GAME_KEYS = {
  KeyW: { key: 'w', keyCode: 87 },
  KeyS: { key: 's', keyCode: 83 },
  KeyA: { key: 'a', keyCode: 65 },
  KeyD: { key: 'd', keyCode: 68 },
  Space: { key: ' ', keyCode: 32 },
  ShiftLeft: { key: 'Shift', keyCode: 16 },
  ArrowUp: { key: 'ArrowUp', keyCode: 38 },
  ArrowDown: { key: 'ArrowDown', keyCode: 40 },
  ArrowLeft: { key: 'ArrowLeft', keyCode: 37 },
  ArrowRight: { key: 'ArrowRight', keyCode: 39 },
  ControlLeft: { key: 'Control', keyCode: 17 },
  Delete: { key: 'Delete', keyCode: 46 },
  End: { key: 'End', keyCode: 35 },
  Home: { key: 'Home', keyCode: 36 },
  AltLeft: { key: 'Alt', keyCode: 18 },
  F8: { key: 'F8', keyCode: 119 },
  F7: { key: 'F7', keyCode: 118 },
  Tab: { key: 'Tab', keyCode: 9 },
};

const gameKeyOf = Object.fromEntries(GAME_ACTIONS.map((action) => [action.id, action.gameKey]));

const KEY_NAMES = {
  ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→',
  ControlLeft: 'Ctrl', ControlRight: 'Right Ctrl', AltLeft: 'Alt/Option', AltRight: 'Right Alt',
  ShiftLeft: 'Shift', ShiftRight: 'Right Shift', MetaLeft: 'Cmd', MetaRight: 'Right Cmd', Space: 'Space', Backspace: 'Backspace',
};

export function keyName(code) {
  return KEY_NAMES[code] ?? String(code).replace(/^Key/, '').replace(/^Digit/, '').replace(/^Numpad/, 'Num ');
}

export function sendGameKey(type, code, modifiers) {
  sendKeyToGame(type, { code, ...GAME_KEYS[code] }, modifiers);
}

// A saved key that is now the game's own key needs no remap (the game's keys were the arrow keys before they became WASD).
function loadKeyMap() {
  let entries;
  try { entries = JSON.parse(saved.get('ttr_keys', '{}')) || {}; } catch { return {}; }
  return Object.fromEntries(Object.entries(entries).filter(([code, id]) => gameKeyOf[id] && code !== gameKeyOf[id]));
}

// the player's keys (event codes) -> action ids
export const keyMap = Alpine.reactive(loadKeyMap());

export const keyboard = Alpine.reactive({
  inUse: false,     // a real key was pressed: the touch controls hide
});
let lastKeyAt = 0;

function replaceKeyMap(entries) {
  for (const code of Object.keys(keyMap)) delete keyMap[code];
  Object.assign(keyMap, entries);
  saved.set('ttr_keys', JSON.stringify(keyMap));
}

export const keysFor = (actionId) => Object.keys(keyMap).filter((code) => keyMap[code] === actionId);

export function remap(actionId, code) {
  const entries = Object.fromEntries(Object.entries(keyMap).filter(([, id]) => id !== actionId));
  if (code !== gameKeyOf[actionId]) entries[code] = actionId;     // the game's own key needs no remap
  replaceKeyMap(entries);
  log('JS| key ' + code + ' -> ' + actionId);
}

export const useGameKeys = () => replaceKeyMap({});
export const useArrowKeys = () => replaceKeyMap({ ArrowUp: 'fwd', ArrowDown: 'back', ArrowLeft: 'left', ArrowRight: 'right', ControlLeft: 'jump' });

// the next key pressed goes to this instead (the Keyboard keys dialog, choosing a key)
let captureNextKey = null;
export function captureKey(handler) { captureNextKey = handler; }

// Typing: the game has a text box open, or a page text field (sign-in, settings) has the focus. The hidden chat input can keep the
// focus after a message is sent, so it only counts while the game's text box is open.
function isTyping() {
  const focused = document.activeElement;
  return chat.open || (focused && focused !== chat.input && (focused.tagName === 'INPUT' || focused.tagName === 'TEXTAREA'));
}

const heldKeys = {};      // the player's key -> the game key sent for it, until it comes up

export function watchKeyboard({ isPlaying }) {
  function onKey(e) {
    if (e.ttrMade || !e.isTrusted) return;      // only a real keyboard counts (the TASKS button sends its own End key)
    if (captureNextKey) {
      e.preventDefault();
      e.stopImmediatePropagation();
      if (e.type === 'keydown') {
        const handler = captureNextKey;
        captureNextKey = null;
        handler(e);
      }
      return;
    }
    if (!isPlaying() || isTyping()) return;

    if (e.type === 'keydown' && e.key !== 'Meta') {
      lastKeyAt = Date.now();
      if (!keyboard.inUse) {
        keyboard.inUse = true;
        log('JS| keyboard in use (' + e.code + ')');
      }
    }

    const actionId = keyMap[e.code];
    if (!actionId || !gameKeyOf[actionId]) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const focused = document.activeElement;
    if (focused === chat.input) chat.input.blur();          // its blur hands the focus back to the game
    else if (!focused || focused === document.body) focusGame();

    const down = e.type === 'keydown';
    const gameKey = down ? gameKeyOf[actionId] : heldKeys[e.code] || gameKeyOf[actionId];
    if (down) heldKeys[e.code] = gameKey;
    else delete heldKeys[e.code];
    sendGameKey(e.type, gameKey, {
      repeat: e.repeat,
      ctrlKey: (gameKey === 'ControlLeft' && down) || e.ctrlKey,
      altKey: (gameKey === 'AltLeft' && down) || e.altKey,
      shiftKey: (gameKey === 'ShiftLeft' && down) || e.shiftKey,
    });
  }
  addEventListener('keydown', onKey, true);
  addEventListener('keyup', onKey, true);

  // The game takes typed letters from keypress, which a cancelled keydown should already stop; some browsers send it anyway. A remapped
  // key must never type its letter (that opens typed chat).
  addEventListener('keypress', (e) => {
    if (e.ttrMade || captureNextKey || isTyping()) return;
    const remapped = e.code ? keyMap[e.code] : Object.keys(heldKeys).includes('Key' + String(e.key).toUpperCase());
    if (remapped) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }, true);

  // switching away with a remapped key held: let it go in the game too
  addEventListener('blur', () => {
    for (const code of Object.keys(heldKeys)) {
      sendGameKey('keyup', heldKeys[code]);
      delete heldKeys[code];
    }
  });

  addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'touch' && keyboard.inUse && Date.now() - lastKeyAt > 20000) {
      keyboard.inUse = false;
      log('JS| touch again: controls back');
    }
  }, true);

  // a key press while nothing is focused: focus the game so the following keys reach it
  document.addEventListener('keydown', () => {
    const focused = document.activeElement;
    if ((!focused || focused === document.body) && isPlaying()) focusGame();
  }, true);
}
