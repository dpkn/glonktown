// localStorage and sessionStorage can be missing or throw (private windows, blocked site data): every read falls back to a default
// and every write may silently do nothing.
function wrap(storageName) {
  let store = null;
  try { store = window[storageName]; } catch {}
  return {
    get(key, fallback = null) {
      try { return store.getItem(key) ?? fallback; } catch { return fallback; }
    },
    set(key, value) {
      try { store.setItem(key, value); } catch {}
    },
    remove(key) {
      try { store.removeItem(key); } catch {}
    },
  };
}

export const saved = wrap('localStorage');      // kept on this device
export const visit = wrap('sessionStorage');    // kept until the tab closes, across reloads
