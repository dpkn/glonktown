// Glonktown (web): the page around the game. The game itself runs in Python (game/main.py) and talks to the page through window.ttr
// (game/bridge.js). The screens are Alpine stores (screens/, game/hud.js) bound to the markup in ui/shell.html; the layout numbers are
// the iOS app's (main.m), kept in the CSS in ui/css/.
import Alpine from '../vendor/alpine-3.17.4.min.js';
import './game/bridge.js';
import { startLogging } from './lib/log.js';
import { viewport, watchViewport } from './lib/viewport.js';
import { registerDirectives } from './lib/directives.js';
import { loadSky } from './lib/sky.js';
import { goFullscreenOnNextInput, isAndroid, standalone } from './lib/device.js';
import { shell, watchOrientation } from './shell.js';
import { flow, openWelcome, watchFlow } from './flow.js';
import { title, watchTitleFonts } from './title.js';
import { loading } from './screens/loading.js';
import { welcome } from './screens/welcome.js';
import { login, watchLoginKeyboard } from './screens/login.js';
import { settings } from './screens/settings.js';
import { install, needsInstallHelp, watchInstallPrompt } from './screens/install.js';
import { hud, joystick, startHud } from './game/hud.js';
import { watchKeyboard } from './game/keyboard.js';
import { watchChat } from './game/chat.js';
import { preventZoom, touchAsMouse } from './game/touch.js';
import { keepCanvasSize } from './game/canvas.js';
import { startDevTools } from './dev.js';

// the lettering font for the title and headings, and the page font for when the game's own (_ui/ImpressBT.ttf) is not there; without
// an internet connection the system's own font is used. Added from here so it never holds up the page.
function loadWebFonts() {
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = 'https://fonts.googleapis.com/css2?family=Luckiest+Guy&family=Nunito:wght@600;700;800;900&display=swap';
  document.head.appendChild(link);
}

const isPlaying = () => shell.playing;
shell.installing = needsInstallHelp;

startLogging();
loadWebFonts();
watchViewport();
watchOrientation();
watchTitleFonts();
watchLoginKeyboard();
watchInstallPrompt();
watchFlow();
startHud({ isPlaying });
watchKeyboard({ isPlaying });
watchChat({ isPlaying });
touchAsMouse();
preventZoom();
keepCanvasSize(() => isPlaying() && !viewport.keyboardHold);
startDevTools();

Alpine.store('shell', shell);
Alpine.store('flow', flow);
Alpine.store('loading', loading);
Alpine.store('welcome', welcome);
Alpine.store('login', login);
Alpine.store('settings', settings);
Alpine.store('install', install);
Alpine.store('hud', hud);
Alpine.data('title', title);
Alpine.data('joystick', joystick);
registerDirectives(Alpine);
Alpine.start();

loadSky().then((url) => { shell.skyUrl = url; });

// Android: full screen and the landscape lock from the first tap (a browser tab cannot lock the rotation any other way). Everywhere
// else full screen starts with the sign-in.
if (isAndroid && !standalone) goFullscreenOnNextInput();

if (!needsInstallHelp) openWelcome();
