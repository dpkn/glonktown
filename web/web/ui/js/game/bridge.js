import { saved } from '../lib/storage.js';
import { server } from '../lib/server.js';
import { log } from '../lib/log.js';

// window.ttr: the one object the page and the game (main.py, webui.py) share. The game reads these fields every frame and calls the
// functions; the page fills both in.
export const bridge = window.ttr = {
  // start-up
  aa: saved.get('ttr_aa') === '0' ? '0' : '1',   // smooth edges, read once when the game starts
  wsUrl: server.socketUrl,
  pyReady: false,         // set by the game once Python runs and its file system is there
  go: false,              // set by the page once signed in and the files are in place: the game may start
  cookie: '',             // "name:password"
  playToken: '',
  gameConfig: '',         // the server's gameconfig.json

  // the window: the size to draw at, and the safe area the game keeps its on-screen items inside
  winW: 0, winH: 0,
  safeL: 0, safeR: 0, safeT: 0, safeB: 0,
  vh: 0,
  pw: 0, ph: 0,           // set by the game: the size it really draws at

  // touch controls: "forward,back,left,right,jump,action,tugLeft,tugRight" and a counter of camera taps
  inp: '0,0,0,0,0,0,0,0',
  camN: 0,

  // typed chat: counters the game watches for a new value and for a send
  txtIn: 0, txtSub: 0, txtVal: '',
  typeBtn: '',            // set by the game: where its "Type a Name" button is, "x,y" as fractions of the window

  dbg: false,
  pycode: '',             // the developer channel's Python source (dev.js)

  plog: log,
  // called by the game; filled in by the modules that handle them
  setUI() {},             // hud.js
  setText() {},           // chat.js
  started() {},           // flow.js
  ended() {},             // flow.js
};
