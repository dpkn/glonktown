"""After pygbag has built the page (pygbag --build game), put our screens into it:
   python patch_web.py"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
app = "game"       # the folder that holds main.py, built by pygbag into game/build/web
web = os.path.join(HERE, app, "build", "web")
index = os.path.join(web, "index.html")
s = open(index, encoding="utf-8").read()
import re
s = re.sub(r"ume_block\s*:\s*\d", "ume_block : 0", s)   # do not wait for a tap before starting Python (iOS Safari would wait forever behind our screens)
open(index, "w", encoding="utf-8").write(s)
# one viewport setting only: the page has two, and the second (height=device-height) cancels viewport-fit=cover (blue bars at the notch)
s = re.sub(r'<meta name="viewport" content="height=device-height, initial-scale=1.0">\s*', '', s)
s = s.replace('<meta name="viewport" content="width=device-width, initial-scale=1.0">',
              '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, user-scalable=no">')
open(index, "w", encoding="utf-8").write(s)
# the page shell (ui/): its styles, its markup, and its scripts
if "ui/js/main.js" not in s:
    shell = open(os.path.join(HERE, "ui", "shell.html"), encoding="utf-8").read()
    s = s.replace("</head>", '<link rel="stylesheet" href="ui/ui.css">\n</head>', 1)
    s = s.replace("</body>", shell + '<script src="server.js"></script>\n<script src="ttr-audio.js"></script>\n'
                  '<script type="module" src="ui/js/main.js"></script>\n</body>', 1)
    open(index, "w", encoding="utf-8").write(s)
# the game server the page signs in to and plays on: '' is the site the page came from. web/build_page.sh writes another one for the website
with open(os.path.join(web, "server.js"), "w") as f:
    f.write("window.TTR_SERVER = '';\n")
# home-screen app: manifest, icons, iOS app tags
import json
for f in ("icon-180.png", "icon-192.png", "icon-512.png"):
    shutil.copy(os.path.join(HERE, f), os.path.join(web, f))
json.dump({"name": "Glonktown", "short_name": "Glonktown", "start_url": "./", "scope": "./", "display": "standalone",
           "orientation": "landscape", "background_color": "#1c4cc4", "theme_color": "#1c4cc4",
           "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]},
          open(os.path.join(web, "manifest.webmanifest"), "w"))
s = open(index, encoding="utf-8").read()
s = re.sub(r"<title>[^<]*</title>", "<title>Glonktown</title>", s, count=1)
if "apple-touch-icon" not in s:
    tags = "".join(t + chr(10) for t in (
        '<link rel="manifest" href="manifest.webmanifest">',
        '<link rel="apple-touch-icon" href="icon-180.png">',
        '<meta name="apple-mobile-web-app-title" content="Glonktown">',
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">',
        '<meta name="theme-color" content="#1c4cc4">'))
    s = s.replace("</head>", tags + "</head>", 1)
open(index, "w", encoding="utf-8").write(s)
shutil.copy(os.path.join(HERE, "ttr-audio.js"), os.path.join(web, "ttr-audio.js"))
shutil.copytree(os.path.join(HERE, "ui"), os.path.join(web, "ui"), dirs_exist_ok=True, ignore=shutil.ignore_patterns("shell.html"))
# the Python runtime and Panda3D, which pygbag loads from its CDN, are served with the page instead (in cdn/, same layout),
# so devices only need to reach the game server. Pinned by sha256 and downloaded once into build/cdn/
import hashlib
import urllib.request
CDN = "https://pygame-web.github.io/cdn/"
RUNTIME = {
    "0.9.3/pythons.js": "6da43e3e62c3db933421b99681e8ef99ed9b0ce1589ed8a0c69b88443278e019",
    "0.9.3/cpythonrc.py": "b8a0b8168b58ef7c38c17d4705c9cbe1751fa667a0a6d26ed26f0537134735de",
    "0.9.3/empty.html": "b0693dc92f76e08bf1485b3dd9b514a2e31dfd6f39422a6b60edb722671dc98f",
    "0.9.3/empty.ogg": "884c20d864222b845aa78fb078ec370f4ddaa203cd92ace28440ed7733403b40",
    "0.9.3/cpython312/main.js": "01c4e4dc7145a482ad259d8272ce73d97b58ec2a141bfb57e620347730d159c7",
    "0.9.3/cpython312/main.wasm": "3cfb882de90feeb367325f0c58731932880c8f424fb5a670b98d035ae862b280",
    "0.9.3/cpython312/main.data": "b068df4d59b06b113cfc3c4d6419bdf699d2c2eeb547c9119e2044c98cdc4a59",
    "vtx.js": "9c5f4de60a85dad9093862715094d67d9c8065872657ad3effa1a6cac6834797",
    "vt/xterm.js": "f0aea0f75f48559013ae6643c2479dd737d26da42d5524e6d2b70915ae6523c7",
    "vt/xterm.css": "832f3f2c603b43ad4351ff04970150cc7a873014276db126a6065c6dd81e4872",
    "vt/xterm-addon-image.js": "a4795cf0998c595de120f79a69c6e522db5fff28dba7c50c1e872ea81a89fd81",
    "index-0.9.3-cp312.json": "ec6edacc1b95700c99b8daecb8ce3949e58e96a1da5234c81d8a0071aa537213",
    "cp312/panda3d-1.11.0-cp312-cp312-wasm32_bi_emscripten.whl": "6ed2698191f20abd3b29615084203cb06c820947fae092edfc2dc9f230614d2f",
}
for path, sha256 in RUNTIME.items():
    cached = os.path.join(HERE, "build", "cdn", path)
    if not os.path.exists(cached):
        data = urllib.request.urlopen(CDN + path).read()
        if hashlib.sha256(data).hexdigest() != sha256:
            raise SystemExit(f"{CDN + path} is not the file this page was pinned to (sha256 {sha256})")
        os.makedirs(os.path.dirname(cached), exist_ok=True)
        open(cached, "wb").write(data)
    os.makedirs(os.path.dirname(os.path.join(web, "cdn", path)), exist_ok=True)
    shutil.copy(cached, os.path.join(web, "cdn", path))
s = open(index, encoding="utf-8").read()
s = re.sub(r'\s*<script src="[^"]*browserfs\.min\.js"></script>', "", s)   # gone from the CDN too; pygbag no longer uses it
s = s.replace(CDN, "cdn/")
# vtx.js loads xterm with import(config.cdn + "../vt/xterm.js"), and import() takes a relative "cdn/..." for a package name
# (failed to resolve module specifier), so the page makes config.cdn a full address
s = s.replace('cdn : "cdn/0.9.3/"', 'cdn : new URL("cdn/0.9.3/", document.baseURI).href')
# PYGPI is where pygbag looks for its package index and wheels (Panda3D); without it, the CDN. cpythonrc.py runs before
# anything else in Python, so it sets it there
rc = os.path.join(web, "cdn", "0.9.3", "cpythonrc.py")
rc_text = open(rc, encoding="utf-8").read()
open(rc, "w", encoding="utf-8").write(rc_text.replace('    os.environ["APPDATA"] = home\n',
                                                     '    os.environ["APPDATA"] = home\n    os.environ.setdefault("PYGPI", "cdn/")\n', 1))
open(index, "w", encoding="utf-8").write(s)
print("patched", index)
