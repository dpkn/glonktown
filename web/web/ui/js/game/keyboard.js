import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { log } from '../lib/log.js';
import { focusGame } from './canvas.js';
import { chat } from './chat.js';

// A hardware keyboard (iPad Magic Keyboard, a desktop). A page cannot ask what keyboard is attached, so a real key press outside typed
// chat is the sign one is used: the touch controls then hide (hud.js), and a finger on the screen after a quiet spell brings them back.
// Which key does what is set in the game itself (the Shticker Book's Controls tab).

export const keyboard = Alpine.reactive({
  inUse: false,     // a real key was pressed: the touch controls hide
});
let lastKeyAt = 0;

// Typing: the game has a text box open, or a page text field (sign-in, settings) has the focus. The hidden chat input can keep the
// focus after a message is sent, so it only counts while the game's text box is open.
function isTyping() {
  const focused = document.activeElement;
  return chat.open || (focused && focused !== chat.input && (focused.tagName === 'INPUT' || focused.tagName === 'TEXTAREA'));
}

export function watchKeyboard({ isPlaying }) {
  addEventListener('keydown', (e) => {
    if (!e.isTrusted || e.key === 'Meta') return;
    if (!isPlaying() || isTyping()) return;
    lastKeyAt = Date.now();
    if (!keyboard.inUse) {
      keyboard.inUse = true;
      log('JS| keyboard in use (' + e.code + ')');
    }
  }, true);

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
