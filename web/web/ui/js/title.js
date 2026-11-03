// The title, lettered like the game's logo: the word is drawn five times over (a shadow, a dark rim, a red band, a black edge, then the
// yellow letters), each letter tipped and bobbed a little. It appears twice: floating over the loading and sign-in screens, and on the
// welcome card. Its size is set in CSS (title.css) from --title-aspect, measured here once the font is in.

const WORD = 'GLONKTOWN';
const TILT = [-7, 5, -4, 6, -5, 4, -6, 5, -3];
const BOB = [-4, 3, -2, 5, -4, 2, -3, 4, -1];
const OUTLINE = 19;       // half the widest outline, kept around the letters
const SHADOW = { x: 3, y: 9 };

let instances = 0;
let viewBox = '';

function titleSvg(id) {
  const letters = [...WORD].map((letter, i) => `<tspan y="${BOB[i]}">${letter}</tspan>`).join('');
  const layer = (part, extra = '') => `<use href="#${id}-word" class="${part}" ${extra}/>`;
  return `<svg role="img" aria-label="Glonktown">
    <defs>
      <linearGradient id="${id}-gold" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff7a8"/><stop offset=".45" stop-color="#ffe01a"/><stop offset="1" stop-color="#ffa600"/>
      </linearGradient>
      <text id="${id}-word" font-size="100" rotate="${TILT.join(' ')}">${letters}</text>
    </defs>
    ${layer('shadow', `transform="translate(${SHADOW.x} ${SHADOW.y})"`)}
    ${layer('rim')}
    ${layer('band')}
    ${layer('edge')}
    ${layer('letters', `fill="url(#${id}-gold)"`)}
  </svg>`;
}

// Fit the drawing to the letters, which change shape when a font arrives. Measured from whichever copy is on screen, and shared.
function measure() {
  for (const rim of document.querySelectorAll('#ttr .title use.rim')) {
    const box = rim.getBBox();
    if (!box.width) continue;
    const width = box.width + 2 * OUTLINE + SHADOW.x, height = box.height + 2 * OUTLINE + SHADOW.y;
    viewBox = [box.x - OUTLINE, box.y - OUTLINE, width, height].join(' ');
    document.documentElement.style.setProperty('--title-aspect', width / height);
    for (const svg of document.querySelectorAll('#ttr .title svg')) svg.setAttribute('viewBox', viewBox);
    return;
  }
}

export function watchTitleFonts() {
  document.fonts?.addEventListener('loadingdone', measure);
  document.fonts?.ready.then(measure);
}

export function title() {
  return {
    init() {
      this.$el.innerHTML = titleSvg('ttr-title-' + instances++);
      if (viewBox) this.$el.firstElementChild.setAttribute('viewBox', viewBox);
      requestAnimationFrame(measure);
    },
  };
}
