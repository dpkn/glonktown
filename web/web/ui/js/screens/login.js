import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { server, serverIsOpen } from '../lib/server.js';
import { saved, visit } from '../lib/storage.js';
import { goFullscreen, isTouchFirst, standalone } from '../lib/device.js';

// The sign-in dialog, under the title. Two tabs say which it is: making an account, or signing in to one. A device that has signed in
// before opens on the second, with the name and password filled in.

const UNREACHABLE = "Can't reach the Glonktown server. It may be switched off, or check your internet.";

export const hasSignedInHere = () => !!saved.get(server.userKey);

// The sign-in service answers "ok <play token>": the game logs in with the token, which the server checks. It only makes a new account
// when the player said they are new, so a mistyped name is an error, not an empty account.
async function askServer(cookie, isNew) {
  try {
    const response = await fetch(server.url('/auth'), {
      method: 'POST',
      body: cookie,
      headers: { 'Content-Type': 'text/plain', 'X-Ttr-Mode': isNew ? 'new' : 'login' },
    });
    const text = (await response.text()).trim();
    if (response.status === 404) return { ok: true, token: '', text };      // a server without sign-in
    const [, token] = text.split(' ');
    return { ok: response.ok, token: response.ok ? token || '' : '', text };
  } catch {
    return { ok: false, unreachable: true, text: UNREACHABLE };
  }
}

// the page was started again because the game ended (flow.js); say why
function whyTheGameEnded() {
  let ended = null;
  try { ended = JSON.parse(visit.get('ttr.ended')); } catch {}
  visit.remove('ttr.ended');
  return ended;
}

export const login = Alpine.reactive({
  isNew: false,
  username: '',
  password: '',
  message: '',
  messageIsError: false,
  busy: false,
  keyboardUp: false,      // one of the fields has the focus

  // on phones and tablets the dialog moves up above the on-screen keyboard; a desktop keeps it where it is
  get raisedForKeyboard() { return this.keyboardUp && !!window.visualViewport && isTouchFirst(); },

  open(isNew) {
    this.setMode(isNew);
    const ended = whyTheGameEnded();
    if (!ended) return;
    const [kind, detail] = ended;
    if (kind === 'quit') this.say("You've logged out. See you soon!");
    else if (kind === 'lost') this.say(detail || 'Lost the connection to the Glonktown server.', true);
    else this.say(`The game stopped unexpectedly (error ${detail}).`, true);
  },

  setMode(isNew) {
    this.isNew = isNew;
    this.username = isNew ? '' : saved.get(server.userKey, '');
    this.password = isNew ? '' : saved.get(server.userKey + '.pw', '');
    this.say(isNew ? 'Pick any name and password. Remember them!' : 'Welcome back! Sign in to play.');
  },

  say(message, isError = false) {
    this.message = message;
    this.messageIsError = isError;
  },

  // Resolves to the sign-in ({ cookie, token }) once the server said yes, 'closed' when the server turned out to be switched off, or
  // null after saying what is wrong.
  async submit() {
    const name = this.username.trim().toLowerCase(), password = this.password;
    if (!name || !password) {
      this.say(this.isNew ? 'Pick a name and a password.' : 'Enter your name and password.', true);
      return null;
    }
    if (name.includes(':')) {
      this.say("Please don't use colons in your name.", true);
      return null;
    }

    this.busy = true;
    this.say('Signing in...');
    const cookie = name + ':' + password;
    const answer = await askServer(cookie, this.isNew);
    this.busy = false;

    if (answer.unreachable && !(await serverIsOpen())) return 'closed';
    if (!answer.ok) {
      this.say(answer.text || 'Sign-in failed.', true);
      return null;
    }

    // the game plays full screen; a browser only allows that shortly after a tap or key press, so ask as soon as the sign-in answered
    if (!standalone) goFullscreen();
    saved.set(server.userKey, name);
    saved.set(server.userKey + '.pw', password);
    return { cookie, token: answer.token };
  },

  fieldFocused() {
    this.keyboardUp = true;
    this.followKeyboard();
  },
  fieldBlurred() {
    setTimeout(() => {
      if (document.activeElement?.closest?.('.sign-in .field')) return;
      this.keyboardUp = false;
      scrollTo(0, 0);
    }, 80);
  },
  // the dialog sits at the top of the visible area, which scrolls and shrinks as the keyboard comes and goes
  followKeyboard() {
    const top = window.visualViewport?.offsetTop ?? 0;
    document.documentElement.style.setProperty('--keyboard-top', top + 'px');
  },
});

export function watchLoginKeyboard() {
  for (const type of ['resize', 'scroll']) {
    window.visualViewport?.addEventListener(type, () => { if (login.keyboardUp) login.followKeyboard(); });
  }
}
