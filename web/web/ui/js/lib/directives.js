// Alpine directives and helpers shared by the screens.

// Enter / Go / Send on a phone keyboard does not always arrive as a plain "Enter" key press (Android keyboards that are suggesting
// words report the key "Unidentified" and send the line break as an input event instead), so listen for both ways.
export function onEnter(input, handler) {
  let lastAt = 0;
  const fire = (e) => {
    e.preventDefault();
    const now = Date.now();
    if (now - lastAt < 250) return;
    lastAt = now;
    handler(e);
  };
  const onKeydown = (e) => { if (e.key === 'Enter' || e.keyCode === 13) fire(e); };
  const onBeforeinput = (e) => { if (e.inputType === 'insertLineBreak' || e.inputType === 'insertParagraph') fire(e); };
  input.addEventListener('keydown', onKeydown);
  input.addEventListener('beforeinput', onBeforeinput);
  return () => {
    input.removeEventListener('keydown', onKeydown);
    input.removeEventListener('beforeinput', onBeforeinput);
  };
}

// A button held down by a finger or the mouse; the "down" class dims it while held.
export function onHold(element, { down, move, up }, { dim = true } = {}) {
  let released = true;
  element.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    element.setPointerCapture(e.pointerId);
    released = false;
    if (dim) element.classList.add('down');
    down?.(e);
  });
  element.addEventListener('pointermove', (e) => {
    if (move && element.hasPointerCapture(e.pointerId)) {
      e.preventDefault();
      move(e);
    }
  });
  const release = (e) => {
    if (released) return;
    released = true;
    element.classList.remove('down');
    up?.(e);
  };
  element.addEventListener('pointerup', release);
  element.addEventListener('pointercancel', release);
  element.addEventListener('lostpointercapture', release);
  element.addEventListener('contextmenu', (e) => e.preventDefault());
}

export function registerDirectives(Alpine) {
  // x-enter="expression": run it on Enter (see onEnter)
  Alpine.directive('enter', (el, { expression }, { evaluateLater, cleanup }) => {
    const run = evaluateLater(expression);
    cleanup(onEnter(el, (e) => run(() => {}, { scope: { $event: e } })));
  });

  // x-hold="expression": run it with $pressed true when held down, and false when let go
  Alpine.directive('hold', (el, { expression }, { evaluateLater }) => {
    const run = evaluateLater(expression);
    const report = (pressed) => run(() => {}, { scope: { $pressed: pressed } });
    onHold(el, { down: () => report(true), up: () => report(false) });
  });
}
