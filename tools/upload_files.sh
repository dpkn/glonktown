#!/bin/sh
# Upload the game files (the packs and the page's art) to the R2 bucket the Pages site serves them from (web/functions/).
# Only files that changed since the last upload are sent, and packs.json goes last, so players never get a list of packs that
# are not there yet. Build the packs first with tools/build_client.sh.
#   tools/upload_files.sh [bucket]      (default: glonkfiles)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUCKET="${1:-glonkfiles}"
FILES="$ROOT/runtime/web/root"
SENT="$ROOT/runtime/uploaded-$BUCKET.txt"
if [ ! -f "$FILES/packs.json" ]; then
  echo "no packs in $FILES yet: run tools/build_client.sh first"; exit 1
fi
touch "$SENT"
put() {
  sum=$(shasum -a 256 "$FILES/$1" | cut -d' ' -f1)
  if grep -qx "$sum $1" "$SENT"; then return 0; fi
  npx wrangler r2 object put "$BUCKET/$1" --file "$FILES/$1" --remote
  { grep -v " $1\$" "$SENT" || true; echo "$sum $1"; } > "$SENT.tmp"
  mv "$SENT.tmp" "$SENT"
}
cd "$FILES"
for f in _packs/*.zip _ui/*; do put "$f"; done
put packs.json
echo "game files in R2 bucket $BUCKET are up to date"
