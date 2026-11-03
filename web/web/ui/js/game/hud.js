import Alpine from '../../vendor/alpine-3.17.4.min.js';
import { bridge } from './bridge.js';
import { focusGame } from './canvas.js';
import { keyboard } from './keyboard.js';
import { settings } from '../screens/settings.js';
import { onHold } from '../lib/directives.js';
import { canGoFullscreen, goFullscreen, hasTouchScreen, isFullscreen } from '../lib/device.js';

// The in-game touch controls, laid out like the iOS app's: a stick, JUMP, CAM, ACTION, TASKS and the tug-of-war pads. The game says
// which ones it wants (setUI); the page sends back which are held (bridge.inp) and how often CAM was tapped (bridge.camN).

const INPUTS = ['forward', 'back', 'left', 'right', 'jump', 'action', 'tugLeft', 'tugRight', 'tasks'];     // bridge.inp's order
const held = Object.fromEntries(INPUTS.map((name) => [name, false]));

function setHeld(changes) {
  Object.assign(held, changes);
  bridge.inp = INPUTS.map((name) => +held[name]).join(',');
}

export const hud = Alpine.reactive({
  requested: { controls: false, action: false, tug: false },     // what the game asks for
  knob: { x: 0, y: 0 },
  tasksOpen: false,
  fps: '-- FPS',
  fullscreen: isFullscreen(),

  // Auto: on touch screens, until a hardware keyboard is used
  get touchControlsWanted() {
    const mode = settings.values.touchControls;
    return mode === 'show' || (mode === 'auto' && !keyboard.inUse && hasTouchScreen());
  },
  get showControls() { return this.requested.controls && this.touchControlsWanted; },
  get showAction() { return this.showControls && this.requested.action; },
  get showTug() { return this.showControls && this.requested.tug; },
  get showFullscreenButton() { return canGoFullscreen && !this.fullscreen; },

  hold(name, pressed) { setHeld({ [name]: pressed }); },
  turnCamera() { bridge.camN++; },

  // TASKS holds the game's ToonTasks key down while open: down shows the task list and up hides it, so a tap shows it and the next tap
  // hides it
  toggleTasks() {
    focusGame();
    this.setTasksOpen(!this.tasksOpen);
  },
  setTasksOpen(open) {
    if (open === this.tasksOpen) return;
    this.tasksOpen = open;
    setHeld({ tasks: open });
  },

  goFullscreen() {
    goFullscreen();
    focusGame();
  },
});

function releaseControls() {
  hud.knob = { x: 0, y: 0 };
  setHeld(Object.fromEntries(INPUTS.map((name) => [name, false])));
  hud.setTasksOpen(false);
}

// the stick: dragged within 38% of its size; past a third of the way in a direction counts as that direction held
export function joystick() {
  return {
    init() {
      onHold(this.$el, { down: (e) => this.steer(e), move: (e) => this.steer(e), up: () => this.center() }, { dim: false });
    },
    steer(e) {
      const box = this.$el.getBoundingClientRect();
      const reach = box.width * 0.38;
      let x = e.clientX - box.left - box.width / 2;
      let y = e.clientY - box.top - box.height / 2;
      const distance = Math.hypot(x, y);
      if (distance > reach) {
        x *= reach / distance;
        y *= reach / distance;
      }
      hud.knob = { x, y };
      const right = x / reach, up = -y / reach;
      setHeld({ forward: up > 0.35, back: up < -0.35, left: right < -0.35, right: right > 0.35 });
    },
    center() {
      hud.knob = { x: 0, y: 0 };
      setHeld({ forward: false, back: false, left: false, right: false });
    },
  };
}

// frames per second: the page's own animation frames, which is how often the game can draw
function countFrames(isPlaying) {
  let frames = 0, since = performance.now();
  const tick = (now) => {
    frames++;
    if (now - since >= 500) {
      if (isPlaying()) hud.fps = Math.round(frames * 1000 / (now - since)) + ' FPS';
      frames = 0;
      since = now;
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

export function startHud({ isPlaying }) {
  bridge.setUI = (controls, action, tug) => {
    hud.requested = { controls: !!+controls, action: !!+action, tug: !!+tug };
  };
  // controls going away while held (the game hid them, or a keyboard took over) let go of everything
  Alpine.effect(() => {
    if (!hud.showControls) queueMicrotask(releaseControls);
  });
  for (const type of ['fullscreenchange', 'webkitfullscreenchange']) {
    document.addEventListener(type, () => { hud.fullscreen = isFullscreen(); });
  }
  countFrames(isPlaying);
}
