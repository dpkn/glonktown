#!/bin/sh
# Cloudflare Pages builds the page from GitHub with this. The project's settings: root directory "web", build command
# "sh build_pages.sh", build output directory "web/game/build/web", and the variables GLONKTOWN_SERVER (the game server,
# https://play.example.com) and PYTHON_VERSION=3.12. The game files are not in git: functions/ serves them from an R2 bucket.
set -e
if [ -z "$GLONKTOWN_SERVER" ]; then
  echo "set GLONKTOWN_SERVER in the Pages project's variables: the game server's address, https://play.example.com"; exit 1
fi
cd "$(dirname "$0")/web"
python -m pip install --quiet pygbag==0.9.3
python -m pygbag --build game
python patch_web.py
OUT=game/build/web
printf "window.TTR_SERVER = '%s';\n" "${GLONKTOWN_SERVER%/}" > "$OUT/server.js"
# only the game files' addresses go to the function; everything else is the static page
printf '{"version": 1, "include": ["/packs.json", "/_packs/*", "/_ui/*"], "exclude": []}\n' > "$OUT/_routes.json"
