// The game's own loading-screen sky (_ui/sky.jpg, which tools/build_client.sh copies from its resources), so the page and the game's
// first screens are the same picture. Resolves to a ready-to-show image address, or '' without one (the plain blue stays).
const SKY = '/_ui/sky.jpg';

async function fetchSky() {
  if (typeof caches === 'undefined') {            // not a secure page: no Cache API, just fetch it
    const response = await fetch(SKY, { cache: 'no-store' });
    return response.ok ? response : null;
  }
  // ask the server first: a picture it no longer has (404) is dropped from the saved copy; the saved copy is only for when offline
  const cache = await caches.open('ttr-art-v1');
  let status = 0;
  try {
    const response = await fetch(SKY + '?t=' + Date.now(), { cache: 'no-store' });
    status = response.status;
    if (response.ok) {
      await cache.put(SKY, response.clone());
      return response;
    }
    if (status === 404) await cache.delete(SKY);
  } catch { /* offline */ }
  return status === 404 ? null : await cache.match(SKY);
}

export async function loadSky() {
  try {
    const response = await fetchSky();
    if (!response) return '';
    const url = URL.createObjectURL(await response.blob());
    const image = new Image();
    image.src = url;
    await image.decode().catch(() => {});
    return url;
  } catch {
    return '';
  }
}
