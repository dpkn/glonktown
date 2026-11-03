import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { bridge } from '../game/bridge.js';
import { GAME_ACTIONS, captureKey, keyName, keysFor, remap, useGameKeys, useWasd } from '../game/keyboard.js';
import { saved } from '../lib/storage.js';
import { relayout } from '../lib/viewport.js';

// The Display dialog (from the sign-in screen and, in game, the gear) and its Keyboard keys page.

// The Display button and the gear only show on a device that opened the page once with ?display=1 (remembered; ?display=0 hides them)
const displayParam = new URLSearchParams(location.search).get('display');
if (displayParam === '0' || displayParam === '1') saved.set('ttr_display', displayParam);

const OPTIONS = [
  {
    key: 'resolution', storageKey: 'ttr_res', fallback: '2',
    label: 'Picture quality', hint: 'Lower is smoother on slower devices',
    choices: [['2', 'Sharp'], ['1.5', 'Balanced'], ['1', 'Fast'], ['0.75', 'Fastest']],
  },
  {
    key: 'smoothEdges', storageKey: 'ttr_aa', fallback: '1',
    label: 'Smooth edges', hint: 'Softens jagged lines; off is faster',
    choices: [['1', 'On'], ['0', 'Off']],
  },
  {
    key: 'fpsCounter', storageKey: 'ttr_fps', fallback: '0',
    label: 'Speed counter', hint: 'The FPS number at the top',
    choices: [['1', 'Show'], ['0', 'Hide']],
  },
  {
    key: 'touchControls', storageKey: 'ttr_touch', fallback: 'auto',
    label: 'On-screen controls', hint: 'Auto shows them on touch screens, until you play with a keyboard',
    choices: [['auto', 'Auto'], ['show', 'Show'], ['hide', 'Hide']],
  },
];

export const settings = Alpine.reactive({
  options: OPTIONS,
  values: Object.fromEntries(OPTIONS.map((o) => [o.key, saved.get(o.storageKey, '') || o.fallback])),
  showDisplayButtons: saved.get('ttr_display', '0') === '1',

  get showFps() { return this.values.fpsCounter === '1'; },
  // smooth edges is read once, when the game starts
  get needsRestart() { return this.values.smoothEdges !== bridge.aa; },

  pick(option, value) {
    this.values[option.key] = value;
    saved.set(option.storageKey, value);
    if (option.key === 'resolution') relayout();
  },
  restartGame() { location.reload(); },
});

export const keysDialog = Alpine.reactive({
  actions: GAME_ACTIONS,
  waitingFor: null,     // the action whose new key is being pressed

  keysFor,
  gameKeyName: (action) => keyName(action.gameKey),
  buttonText(action) {
    if (this.waitingFor === action.id) return 'Press a key... (Esc cancels)';
    const mine = keysFor(action.id);
    return mine.length ? mine.map(keyName).join(', ') : keyName(action.gameKey);
  },

  listen(action) {
    this.waitingFor = action.id;
    captureKey((e) => {
      this.waitingFor = null;
      if (e.code && e.code !== 'Escape') remap(action.id, e.code);
    });
  },
  stopListening() {
    this.waitingFor = null;
    captureKey(null);
  },
  useGameKeys() { this.stopListening(); useGameKeys(); },
  useWasd() { this.stopListening(); useWasd(); },
});
