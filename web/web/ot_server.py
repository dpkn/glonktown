"""Local test server for the Open Toontown browser build: serves the built page, the download packs, a stand-in sign-in answer, and a
developer channel.   python ot_server.py <port> [bind]
   /            built page (game/build/web)             /packs.json, /_packs/*   game files (build/site/)
   POST /auth   always "ok" (the test server accepts any name)                    /__code   python for the running game (debug_code.py)
   POST /__log  the page's log lines, printed here                                 /leaderboard.json   a made-up leaderboard
                                                                                   /community_goal.json   a made-up Save Glonktown"""
import json
import mimetypes
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "game", "build", "web")
SITE = os.path.join(HERE, "build", "site")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
BIND = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
mimetypes.add_type("application/wasm", ".wasm")


LEADERBOARD = json.dumps({"now": int(time.time()), "toons": [
    {"name": "Daantastic", "species": "dog", "laff": 42, "tracks": 4, "playground": "Minnie's Melodyland", "online": True, "where": "Daisy Gardens", "lastSeen": int(time.time())},
    {"name": "Weird Pickles Paddledoodle", "species": "rabbit", "laff": 37, "tracks": 4, "playground": "Daisy Gardens", "online": False, "where": None, "lastSeen": int(time.time()) - 7200},
    {"name": "Waldo Wildwhip", "species": "pig", "laff": 25, "tracks": 3, "playground": "Donald's Dock", "online": True, "where": "Toontown Central", "lastSeen": int(time.time())},
    {"name": "Zippety Crunchyton", "species": "bear", "laff": 15, "tracks": 2, "playground": "Toontown Central", "online": False, "where": None, "lastSeen": int(time.time()) - 3 * 86400},
]}).encode()

COMMUNITY_GOAL = json.dumps({"updated": int(time.time()), "target": 1500, "points": 812,
    "counts": {"cogs": 241, "buildings": 6, "invasions": 2, "bosses": 0},
    "milestones": [{"percent": 25, "at": 375, "reward": "100 jellybeans for every toon", "reached": True},
                   {"percent": 50, "at": 750, "reward": "Double gag experience for the rest of the party", "reached": True},
                   {"percent": 75, "at": 1125, "reward": "Full Laff and a full gag bag for every toon", "reached": False},
                   {"percent": 100, "at": 1500, "reward": "Fireworks in every playground, and 500 jellybeans for every toon", "reached": False}],
    "helpers": {"100000003": {"name": "Daantastic", "points": 402}, "100000004": {"name": "Weird Pickles Paddledoodle", "points": 377},
                "100000005": {"name": "Waldo Wildwhip", "points": 128}},
    "events": [{"time": int(time.time()) - 240, "text": "50% reached: Double gag experience for the rest of the party"},
               {"time": int(time.time()) - 600, "text": "Daantastic and Waldo Wildwhip took back a 3-story building"},
               {"time": int(time.time()) - 1500, "text": "The town stopped the Flunkies invasion"}],
    "gifted": {}}).encode()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        if "/_packs/" not in self.path:
            sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _find(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"
        for root in (SITE, WEB):
            full = os.path.normpath(os.path.join(root, path.lstrip("/")))
            if full.startswith(root) and os.path.isfile(full):
                return full
        return None

    def _send(self, code, data=b"", ctype="text/plain", head=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if not head:
            self.wfile.write(data)

    def _serve(self, head=False):
        if self.path.startswith("/__code"):
            try:
                data = open(os.path.join(HERE, "debug_code.py"), "rb").read()
            except OSError:
                data = b""
            return self._send(200, data, head=head)
        f = self._find()
        if not f:
            return self._send(404, b"not found", head=head)
        data = open(f, "rb").read()
        self._send(200, data, mimetypes.guess_type(f)[0] or "application/octet-stream", head)

    def do_GET(self):
        if self.path.startswith("/leaderboard.json"):
            return self._send(200, LEADERBOARD, "application/json")
        if self.path.startswith("/community_goal.json"):
            return self._send(200, COMMUNITY_GOAL, "application/json")
        self._serve()

    def do_HEAD(self):
        self._serve(True)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        if self.path.startswith("/__log"):
            sys.stderr.write("PAGE| " + body.decode("utf-8", "replace") + chr(10))
            sys.stderr.flush()
            return self._send(204)
        if self.path.startswith("/auth"):
            return self._send(200, b"ok")
        self._send(404, b"not found")


ThreadingHTTPServer((BIND, PORT), H).serve_forever()
