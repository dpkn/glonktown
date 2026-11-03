#!/bin/sh
# Cloudflare Workers Builds builds the page from GitHub with this (root directory "web", build command "sh build_page.sh"), then deploys
# it with wrangler.jsonc. Build variable: GLONKTOWN_SERVER (the game server, https://play.example.com). Any Python runs it: the one
# the page plays on is the WebAssembly build patch_web.py downloads
set -e
if [ -z "$GLONKTOWN_SERVER" ]; then
  echo "set GLONKTOWN_SERVER in the Worker's build variables: the game server's address, https://play.example.com"; exit 1
fi
cd "$(dirname "$0")/web"
python -m pip install --quiet pygbag==0.9.3
python -m pygbag --build game
python patch_web.py
printf "window.TTR_SERVER = '%s';\n" "${GLONKTOWN_SERVER%/}" > game/build/web/server.js
