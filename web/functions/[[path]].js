// The game files (the packs and the page's art) are Disney's, so they are not in git. They live in the R2 bucket bound as FILES
// (tools/upload_files.sh puts them there) and are served here at the same addresses the game server's nginx uses.
const TYPES = { zip: 'application/zip', json: 'application/json', jpg: 'image/jpeg', ttf: 'font/ttf' };

export async function onRequestGet({ request, env }) {
  const key = decodeURIComponent(new URL(request.url).pathname.slice(1));
  const file = await env.FILES.get(key);
  if (!file) return new Response('Not found', { status: 404 });
  return new Response(file.body, {
    headers: {
      'Content-Type': TYPES[key.split('.').pop()] || 'application/octet-stream',
      'Cache-Control': key === 'packs.json' ? 'no-cache' : 'public, max-age=300',
      ETag: file.httpEtag,
    },
  });
}
