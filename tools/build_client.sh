#!/bin/sh
# Build the browser page and the download packs, then copy them into runtime/web for the container.
#   tools/build_client.sh          page + packs
#   tools/build_client.sh packs    packs only (game code or art changed)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
cd "$ROOT/web/web"
if [ "$1" != "packs" ]; then
  "$ROOT/.venv/bin/pygbag" --build game > /dev/null
  "$PY" patch_web.py auto
  rsync -a --delete --exclude _ui game/build/web/ "$ROOT/runtime/web/_play/"
fi
OT_DIR="$ROOT/server" "$PY" make_ot_packs.py
rsync -a --delete --exclude _ui --exclude gameconfig.json build/site/ "$ROOT/runtime/web/root/"
echo "client copied to $ROOT/runtime/web"
