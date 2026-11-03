#!/bin/sh
# Build the browser page and the download packs, then copy them into runtime/web for the container.
#   tools/build_client.sh          page + packs
#   tools/build_client.sh packs    packs only (game code or art changed)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
mkdir -p "$ROOT/runtime/web"
cd "$ROOT/web/web"
if [ "$1" != "packs" ]; then
  "$ROOT/.venv/bin/pygbag" --build game > /dev/null
  "$PY" patch_web.py
  rsync -a --delete --exclude _ui game/build/web/ "$ROOT/runtime/web/_play/"
  # the page wears the game's own interface font and loading-screen sky (Disney's files, so they come from the resources, not git)
  for d in _play root; do
    mkdir -p "$ROOT/runtime/web/$d/_ui"
    cp "$ROOT/server/resources/phase_3/models/fonts/ImpressBT.ttf" "$ROOT/runtime/web/$d/_ui/ImpressBT.ttf"
    cp "$ROOT/server/resources/phase_3/maps/loading_bg_clouds.jpg" "$ROOT/runtime/web/$d/_ui/sky.jpg"
  done
fi
OT_DIR="$ROOT/server" "$PY" make_ot_packs.py
rsync -a --delete --exclude _ui --exclude gameconfig.json build/site/ "$ROOT/runtime/web/root/"
echo "client copied to $ROOT/runtime/web"
