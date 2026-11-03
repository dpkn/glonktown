// The game files (the packs and the page's art) are Disney's, so they are not in git. They live in the R2 bucket bound as FILES
// (tools/upload_files.sh puts them there) and are served here at the same addresses the game server's nginx uses. The page itself is
// static: Cloudflare serves it before this runs.
const TYPES = { zip: 'application/zip', json: 'application/json', jpg: 'image/jpeg', ttf: 'font/ttf' };
const GAME_FILES = /^(packs\.json|_packs\/.+|_ui\/.+)$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    // pygbag asks for its Panda3D wheel as cdn//cp312/...
    if (url.pathname.includes('//')) {
      url.pathname = url.pathname.replace(/\/{2,}/g, '/');
      return Response.redirect(url.toString(), 301);
    }
    const key = decodeURIComponent(url.pathname.slice(1));
    const file = request.method === 'GET' && GAME_FILES.test(key) ? await env.FILES.get(key) : null;
    if (!file) return new Response('Not found', { status: 404 });
    return new Response(file.body, {
      headers: {
        'Content-Type': TYPES[key.split('.').pop()] || 'application/octet-stream',
        'Cache-Control': key === 'packs.json' ? 'no-cache' : 'public, max-age=300',
        ETag: file.httpEtag,
      },
    });
  },
};
