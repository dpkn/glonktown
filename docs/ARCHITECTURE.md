# How Glonktown works

This is the write-up of the system: what the pieces are, how they fit together, and why they were built this way. Day-to-day
running is in [OPERATIONS.md](OPERATIONS.md), and every change to the game in [CHANGES.md](CHANGES.md).

## 1. The short version

Players open a web page on a phone, tablet or laptop. The page downloads the game (Python code and the game's art and sound,
about 390 MB, kept on the device) and runs it inside the browser, using Python compiled to WebAssembly. The game talks to the
server over a WebSocket. The server (Astron plus Python services) runs in **one Docker container** on the host's Mac, reached
over the party's home network.

```
 phone / tablet (browser or home-screen app)
 ┌──────────────────────────────────────────────┐
 │  page shell  (ttr-ui.js, ttr-ui.css)         │   sign-in, download, touch controls
 │  game        the game's Python + otpy,       │   Panda3D + CPython in WebAssembly (pygbag)
 │              running in the browser          │
 └───────────────┬───────────────┬──────────────┘
                 │ HTTP          │ WS  /ws
                 ▼               ▼
            home network  ───────────►  host Mac :7380
                                          │
 ┌────────────────────────────────────────▼───────────────────────────────┐
 │ Docker container "glonktown"                                           │
 │                                                                        │
 │  nginx :80 ─┬─ /play/, /packs.json, /_packs/*, /_ui/   static files    │
 │             ├─ /ws ───────────► ws bridge :7390 ──► Astron client agent│
 │             │                                         :7198 (TCP)      │
 │             └─ /auth /__log ───────────────────────► sign-in service  │
 │                                                       :7381            │
 │                                                                        │
 │  Astron (message director :7199, state server, database, client agent) │
 │  UberDOG ─ Toon Valley AI (the one district)                           │
 │  nightly backup loop                                                   │
 └────────────────────────────────────────────────────────────────────────┘
        volumes:  resources (read-only)   databases   web/ (page + packs)   data/ (users, backups, logs)
```

## 2. The parts

### 2.1 The browser client (`web/web/`)

Two layers run on the phone.

**The page shell** is plain JavaScript and CSS (`ttr-ui.js`, `ttr-ui.css`, `ttr-audio.js`). It owns everything outside the game
itself:

- the sign-in screen, the loading screen and its progress bar;
- the "turn your phone sideways" and "add to Home Screen" screens (iPhone, iPad and Android);
- downloading and caching the game files (section 4);
- the touch controls (thumb stick, jump, camera, book) and the on-screen keyboard handling;
- sound: it plays the game's sounds through the Web Audio API (`ttr-audio.js`), because Panda3D has no audio library in the
  browser;
- keeping the game's window the right size on phones with notches and moving toolbars;
- the optional test-session log (`?log=1`, section 7).

**The game** is the Python code in `server/otp` and `server/toontown`, run by [pygbag](https://github.com/pygame-web/pygbag):
CPython and Panda3D compiled to WebAssembly, drawing with WebGL. The glue code is in `web/web/game/`:

| File | Job |
|---|---|
| `main.py` | Starts the game after the shell has downloaded its files and signed in; installs `otpy`; sets the Panda3D options a browser needs; hands the game the sign-in name; keeps the window size in sync with the shell. |
| `webnet.py` | The game's network connection over WebSocket (a browser cannot open a plain TCP socket). |
| `webaudio.py` | `AudioManager` and `AudioSound` look-alikes that pass sound requests to the shell. |
| `webui.py`, `webui_core.py` | Touch controls and phone-sized versions of some game screens. |
| `xmlshim.py` | A small stand-in for `xml.sax`, which the browser's Python build lacks; it reads the game's DNA files. |

`web/web/patch_web.py` takes the page that pygbag builds and adds the shell, the Home Screen manifest and icons.

### 2.2 `otpy`: replacing the compiled libraries

The game needs two compiled Panda3D modules, `panda3d.otp` and `panda3d.toontown` (nametags, margin cells, the DNA loader, Cog
street paths, movement code). There is no build of them for WebAssembly, so **`otpy`** (`server/otpy/`) replaces them in pure
Python with the same interface:

| Module | Replaces |
|---|---|
| `dna.py`, `dnaparser.py` | the DNA loader and storage (streets, buildings, Cog paths) |
| `suit.py` | Cog path legs and leg lists |
| `movement.py` | `CMover`, `CImpulse` and the pet movement helpers |
| `nametag.py` | nametags, chat balloons, margin cells, whisper popups |
| `install.py` | registers all of the above as `panda3d.otp` and `panda3d.toontown` |

`otpy` is used in two places: in the browser (`main.py` installs it), and **on the server too** (the container loads it into
every Python process through a `sitecustomize.py`, section 2.4). It was checked against the compiled versions while it was
written, but the server using it instead of the compiled library is the least-tested part of the system.

### 2.3 The network

Docker publishes the container's port 80 as port 7380 on the Mac, and guests open `http://<the Mac's address>:7380/play/`. It
is plain HTTP on the home network: nothing is exposed to the internet, and nothing must be (section 3 explains why). Docker
Desktop hides each guest's own address (every connection arrives from its gateway), so the bridge's and the sign-in service's
per-address limits count all guests together; `server/docker/docker-compose.yml` sets them for the whole party.

For friends elsewhere the page can also be a website of its own, while the game server stays in the container, reached over HTTPS
through a tunnel. Cloudflare Workers builds the page from GitHub (`web/build_page.sh`) and serves it as static assets
(`web/wrangler.jsonc`). The packs and the page's art are Disney's files and not in git: `tools/upload_files.sh` puts them in an R2
bucket, and the Worker (`web/worker.js`) serves them at the same addresses nginx uses (`/packs.json`, `/_packs/`, `/_ui/`). The page loads `server.js`, which names the game server (`window.TTR_SERVER`; empty means the page's own site): sign-in
(`/auth`), the game settings (`/gameconfig.json`), the logs and the WebSocket go there, and the game files always come from the
page's own site. nginx lets other sites call `/auth` and read `/gameconfig.json` (CORS); sign-in uses no cookies. A device can
switch servers with `?server=<address>`, and keeps a separate saved login for each server it switched to.

### 2.4 The server container (`server/docker/`)

Everything the game needs on the server side runs in a single container (`glonktown`, built from `server/docker/Dockerfile` by
`docker-compose.yml`). `run.sh` starts these, in order, and stops the whole container if the UberDOG or the district dies, so
Docker restarts everything together:

1. **nginx** (port 80 inside, 7380 published). Serves the page and game files, and proxies `/ws` and the sign-in paths
   (`nginx.conf`).
2. **Sign-in service** (`auth_service.py`, port 7381). Checks passwords, collects crash reports and test-session logs.
   Section 5.
3. **WebSocket bridge** (`wsbridge.py`, port 7390). Copies bytes between a browser WebSocket and Astron's TCP client port. It
   reads nothing and changes nothing. Its connection limits are `MAX_PER_IP` and `MAX_NEW_PER_MIN` in `docker-compose.yml`.
4. **Astron** (`astrond`). The message director (7199), event logger (7197), state server (4002), database server (4003, YAML
   files in `astron/databases/astrondb`), database state server, and the client agent (7198). The Linux settings are
   `astron/config/astrond-linux.yml`, made by the Dockerfile.
5. **UberDOG** (`toontown.uberdog.UDStart`, base channel 1000000). The global services: login manager, friends managers,
   delivery manager, news and the rest listed in `astrond-linux.yml`, including **ToonPresence** (object 4730): it knows who is
   playing in any district, tells friends when someone comes or goes, and relays the Go To messages.
6. **One district AI** (`toontown.ai.AIStart`): **Toon Valley** (channel base 401000000), with Cog invasions. It starts 25
   seconds after the UberDOG and takes about a minute to finish loading.
7. **A backup loop** (section 6).
8. **The Cloudflare Tunnel** (`cloudflared`), only when `runtime/data/tunnel_token` holds a token: it makes nginx reachable over
   HTTPS at the tunnel's address, with no port opened. If it cannot connect it tries again every minute; it never stops the game.

The image is Python 3.9 with:

- **Panda3D 1.11.0** (a development wheel from the Panda3D archive, `1.11.0.dev4050`, the newest with both x86_64 and ARM
  Linux builds), which gives the compiled engine and the DC (network protocol) library;
- the Python side of **Panda3D 1.11.0's `direct` package** copied over the wheel's, because the Astron classes the game uses
  (`AstronInternalRepository` and friends) are missing from the wheel's copy. That folder is `server/docker/overlay/direct`, with
  Panda3D's license;
- `pytz` and `websockets`;
- a `sitecustomize.py` that loads `otpy`, so `panda3d.otp` and `panda3d.toontown` exist in every Python process.

The game's code is copied into the image, so a code change means rebuilding it. Four folders are mounted, so the image itself
holds no data:

| Mount | Holds |
|---|---|
| `/ot/src/resources` | the game's art, sound and DNA files, read-only (`server/resources`) |
| `/ot/src/astron/databases` | the toons and accounts (`runtime/databases`) |
| `/ot/web` | `_play/` (the built page) and `root/` (packs, packs.json) (`runtime/web`) |
| `/ot/data` | `users.json`, `gameconfig.json`, `parties.json`, `backups/`, `logs/` (`runtime/data`) |

## 3. Sign-in and a play session

1. The player types a name and password. The shell lower-cases the name and sends `name:password` to `POST /auth`.
2. The sign-in service looks the name up in `users.json`. An unknown name is registered on the spot (while registration is
   open), with a salted PBKDF2-SHA256 hash (100,000 rounds). A wrong password gets "Wrong password".
3. On success the shell downloads or checks the game files, then starts the game, giving it **only the name**.
4. The game opens a WebSocket to `/ws`. nginx passes it to the bridge, which opens a TCP connection to Astron's client agent.
5. The game sends the name as its play token. The UberDOG's login manager (`AstronLoginManagerUD`) looks the name up in
   `runtime/databases/accounts.json`, which maps names to account objects:
   - a known name loads that account and its up-to-six toons;
   - an unknown name gets a new account on the spot, with the default access level `NO_ACCESS` (set in
     `server/docker/live.prc`), so ordinary players have no staff powers;
   - accounts that were given a staff access level in the database can use [magic words](MAGIC_WORDS.md).
6. The player picks a toon, the game asks for an avatar, and the toon appears in the district. From there the district's AI
   creates the toon's objects, and the state server and client agent keep the phone's view up to date through interest.

**Important limitation:** step 5 trusts the name. Only the page checks the password (step 2); the game connection itself does
not. Someone who talks to `/ws` directly and sends another player's name as the token would be let in as that player. Fixing it
means having the sign-in service issue a short-lived signed token that the login manager checks. It is the most important open
security item (see [TODO.md](TODO.md)).

## 4. Getting the game files to the phone

The files are served as a handful of zip "packs" listed in `packs.json` (name, size and a hash of the contents). The shell:

- fetches `packs.json` fresh every time, then each `/_packs/<name>.zip?v=<hash>`; a pack that changed has a new hash, so a saved
  copy is never mistaken for it, and the packs that did not change come from the device. The packs are built without file times,
  so rebuilding the same files gives the same hashes;
- stores the packs in the browser's Cache API (or IndexedDB where that is unavailable) and unpacks them into the game's
  virtual file system;
- deletes cached packs that are no longer listed.

`web/web/make_ot_packs.py` builds the packs:

- **`_code.zip`**: the Python of the `otp` and `toontown` packages from `server/`, `otpy`, `pytz`, the `etc/` config files and
  the licence notices. While it is packed, two kinds of changes are made to the code: browser fixes (the game's see-through
  modes become plain alpha blending, because WebGL has no alpha test), and phone-friendly chat (large chat buttons pinned to
  the screen corner).
- **`models.zip` and one zip per `phase_*` folder**: the game's art, sound and data, taken as they are from
  `server/resources`. A folder bigger than 24 MiB is split into parts (`phase_4-1.zip`, `phase_4-2.zip`, ...), because static
  hosts cap the size of one file (Cloudflare Pages: 25 MiB).

The resources are not in this repository; the README's setup step 2 shows where to get them.

## 5. Accounts

There are two separate stores, deliberately:

| Store | File | What it holds |
|---|---|---|
| Logins | `runtime/data/users.json` | name, salted password hash, an admin flag, a registration switch |
| Game | `runtime/databases/accounts.json` and `astrondb/*.yaml` | which account belongs to which name; each account's toons and every toon's fields |

The sign-in service is the only thing that touches `users.json`. The page remembers each device's name and password, and a
forgotten password is reset by the host ([OPERATIONS.md](OPERATIONS.md#accounts)). The service still has recovery-answer
endpoints, but the page does not use them.

## 6. Data and backups

- **Toons and accounts** are YAML files, one per object, written by Astron's database server. No other database runs.
- **A nightly backup** (inside `run.sh`) tars the databases and `users.json` into `runtime/data/backups/`, and keeps 14.
- **Logs** are in `runtime/data/logs/` ([OPERATIONS.md](OPERATIONS.md#logs)). They are replaced each time the container starts.

## 7. Seeing what happens

- **Server logs:** one file per process in `runtime/data/logs/` (`astron.log`, `ud.log`, `ai1.log`, `bridge.log`, `auth.log`).
- **Crash reports:** every page sends Python errors, page errors and lost connections to `POST /__log`, which the sign-in
  service appends to `runtime/data/logs/client.log`.
- **Test sessions:** open the page with `?log=1`. For the rest of that visit the page sends everything the game prints
  (including Python errors), page errors and browser console warnings and errors as well. The file stops at 30 MB; how many
  lines an address may send an hour is `CLOG_PER_HOUR` in `docker-compose.yml`.
- **Who is online:** `web/tools/who_is_online.py` (run inside the container, see OPERATIONS.md).

## 8. What runs where, in one table

| Thing | Where | Port |
|---|---|---|
| Guest page | the Mac, on the home network | 7380 |
| nginx | container | 80 |
| Sign-in service | container | 7381 |
| WebSocket bridge | container | 7390 |
| Astron client agent | container | 7198 |
| Astron message director | container | 7199 |
| Astron event logger | container | 7197 |
| State server (control channel) | container, inside Astron | 4002 |
| Database server (control channel) | container, inside Astron | 4003 |

Only 7380 is reachable from outside the container, and only from the home network.
