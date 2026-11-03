import { bridge } from './game/bridge.js';
import { gameCanvas } from './game/canvas.js';
import { viewport } from './lib/viewport.js';
import { standalone } from './lib/device.js';
import { isTestServer } from './lib/server.js';
import { log } from './lib/log.js';

// Facts about the screen, for working out odd ones (foldables, iOS's stuck viewport) from the server's log.

function webglFacts(canvas) {
  try {
    if (!canvas) return '-';
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return 'none';
    const attributes = gl.getContextAttributes() || {};
    return (gl instanceof WebGL2RenderingContext ? 'webgl2' : 'webgl1') + ' depth=' + gl.getParameter(gl.DEPTH_BITS)
      + ' stencil=' + gl.getParameter(gl.STENCIL_BITS) + ' aa=' + attributes.antialias + ' samples=' + gl.getParameter(gl.SAMPLES);
  } catch (e) {
    return 'err ' + e;
  }
}

function displayMode() {
  if (matchMedia('(display-mode: standalone)').matches) return 'standalone';
  return matchMedia('(display-mode: fullscreen)').matches ? 'fullscreen' : 'browser';
}

function logScreenFacts(when) {
  try {
    const canvas = gameCanvas(), box = canvas?.getBoundingClientRect(), visual = window.visualViewport, { safe } = viewport;
    log([
      'JS| env ' + when,
      `inner ${innerWidth}x${innerHeight}`,
      `outer ${outerWidth}x${outerHeight}`,
      `screen ${screen.width}x${screen.height}`,
      `avail ${screen.availWidth}x${screen.availHeight}`,
      `dpr ${devicePixelRatio}`,
      'vv ' + (visual ? `${Math.round(visual.width)}x${Math.round(visual.height)}@${Math.round(visual.offsetLeft)},${Math.round(visual.offsetTop)} s${visual.scale}` : '-'),
      `standalone ${standalone}`,
      `dm ${displayMode()}`,
      'orient ' + (screen.orientation?.type || '-'),
      `safe ${safe.top},${safe.right},${safe.bottom},${safe.left}`,
      'canvas ' + (canvas ? `${canvas.width}x${canvas.height} css ${Math.round(box.width)}x${Math.round(box.height)}@${Math.round(box.left)},${Math.round(box.top)}` : '-'),
      `win ${bridge.winW}x${bridge.winH}`,
      `panda ${bridge.pw}x${bridge.ph}`,
      'gl ' + webglFacts(canvas),
      'ua ' + navigator.userAgent,
    ].join(' '));
  } catch (e) {
    log('JS| env failed ' + e);
  }
}

export function startDevTools() {
  for (const [when, ms] of [['load', 1500], ['+10s', 10000], ['+40s', 40000], ['+90s', 90000], ['+180s', 180000]]) {
    setTimeout(() => logScreenFacts(when), ms);
  }
  addEventListener('resize', () => setTimeout(() => logScreenFacts('resize'), 300));

  // the developer channel (local test server only): run the Python in debug_code.py in the game
  if (isTestServer) {
    let lastCode = '';
    setInterval(async () => {
      try {
        const code = await (await fetch('/__code?' + Date.now(), { cache: 'no-store' })).text();
        if (code && code !== lastCode) bridge.pycode = lastCode = code;
      } catch {}
    }, 2000);
  }
}
