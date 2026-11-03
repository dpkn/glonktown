const userAgent = navigator.userAgent || '';
const matches = (query) => !!window.matchMedia?.(query).matches;

export const isIOS = /iPhone|iPad|iPod/.test(userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
export const isAndroid = /Android/i.test(userAgent);
// opened from the Home Screen as an app, not in a browser tab
export const standalone = navigator.standalone === true || matches('(display-mode: standalone)');

export const hasTouchScreen = () => matches('(any-pointer: coarse)');
export const isTouchFirst = () => matches('(hover: none) and (pointer: coarse)');   // phones and tablets: they get on-screen keyboards
export const isCoarsePointer = () => matches('(pointer: coarse)');

// Full screen: a browser only allows it shortly after a tap or key press. iPhone has none for pages (there the Home Screen app is
// full screen); on Android it also locks the rotation to landscape, which a browser tab cannot do any other way.
export const canGoFullscreen = !standalone && !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);

export const isFullscreen = () => !!(document.fullscreenElement || document.webkitFullscreenElement);

export function goFullscreen() {
  const html = document.documentElement;
  const request = html.requestFullscreen || html.webkitRequestFullscreen;
  if (!request || isFullscreen()) return;
  try {
    request.call(html, { navigationUI: 'hide' })
      ?.then(() => screen.orientation.lock('landscape').catch(() => {}))
      .catch(() => {});
  } catch {}
}

// the next tap or key press (but not Escape, which is how full screen is left) goes full screen
export function goFullscreenOnNextInput() {
  const once = (e) => {
    if (e.key === 'Escape') return;
    removeEventListener('pointerup', once, true);
    removeEventListener('keydown', once, true);
    goFullscreen();
  };
  addEventListener('pointerup', once, true);
  addEventListener('keydown', once, true);
}

// keeps the screen on while playing
export function keepScreenAwake() {
  try {
    if (navigator.wakeLock && !document.hidden) navigator.wakeLock.request('screen').catch(() => {});
  } catch {}
}
