# Glonktown

An easy-to-use, private server and browser client for the classic toon MMO, for playing with a few friends. Guests play **in a web browser** on a laptop, phone or tablet, against a server running in
Docker on the host's PC or Mac. Nobody else installs anything.

## What's in it

- **Plays in the browser**: CPython and Panda3D compiled to WebAssembly, touch controls for phones, sound through Web Audio, sign-in with a name and password, and game files cached on the device after the first load.
- **Easy server setup**: one Docker image to run, nothing else to worry about.  
- **One district with Cog invasions**, the game is tuned for a few friends: boosted gag XP, accuracy up to 100, x3 invasion XP, rebalanced
  gags, no Laff requirement for facilities, street Cog levels per neighborhood, and toons on one side of a boss fight when
  there are fewer than four.
- **Rebindable controls**: a Controls tab in the Shticker Book, plus a Smooth Animations option.
- **Crash fixes and polish** collected from other projects (see [Credits](#credits)).
- **Magic Words**: Admins can trigger events and change game stats easily using the chat ([all of them](docs/MAGIC_WORDS.md)).

Every change to the game is listed in [docs/CHANGES.md](docs/CHANGES.md).

## Repository layout

| Path | What it is |
|---|---|
| [`server/`](server) | The game server: the game's code, `otpy` (a pure-Python replacement for the game's compiled libraries) and the Docker image ([`server/docker/`](server/docker)). |
| [`web/`](web) | The browser client: the page shell, the Python glue that runs the game in WebAssembly, the scripts that build the download packs. |
| [`docs/`](docs) | How it works, running it, every change, the magic words and the to-do list. |
| [`tools/`](tools) | `build_client.sh` builds the page and the packs; `make_icons.py` draws the home-screen icons. |
| `server/resources` | The game's art, sound and DNA files. **Not in git**: you clone it in step 2. |
| `runtime/` | The server's data: accounts, toons, logs and the built page. **Not in git**; created on first run. |

## Setup

### What you need

- A Mac with [Docker Desktop](https://www.docker.com/products/docker-desktop/) or [OrbStack](https://orbstack.dev), or a 64-bit
  Linux machine with Docker. Built and tested on Apple Silicon. The server image builds natively for ARM (Apple Silicon, Ampere)
  and x86_64.
- Python 3.12 and Git.
- About 4 GB of free disk space.
- Internet access for the guests' devices: the page loads its Python runtime from pygbag's CDN.

### 1. Clone

```bash
git clone https://github.com/dpkn/glonktown.git
```

```bash
cd glonktown
```

### 2. Get the game's resources

The game's art, sound and level files live in a separate
[resources repository](https://github.com/open-toontown/resources). Clone it into `server/resources`:

```bash
git clone https://github.com/open-toontown/resources.git server/resources
```

### 3. Build the browser client

Make a virtual environment with pygbag 0.9.3 (the version whose CDN the page uses) and pytz:

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install pygbag==0.9.3 pytz
```

Then build the page and the download packs into `runtime/web`:

```bash
tools/build_client.sh
```

### 4. Start the server

```bash
docker compose -f server/docker/docker-compose.yml up -d --build
```

The first build compiles Astron and takes several minutes. The server is ready when the district's log ends with `Done.`, about
40 seconds after it starts:

```bash
tail -n 1 runtime/data/logs/ai1.log
```

### 5. Play

Find the Mac's address on the network:

```bash
ipconfig getifaddr en0
```

On any device on the same network, open **`http://<that address>:7380/play/`**, pick a toon name and a password, and tap
**PLAY**. Use the Mac's network address, not `localhost`, even on the Mac itself: from `localhost` the page tries to load its Python
runtime from a local address.

The first start downloads about 390 MB of game files; after that they stay on the device. Players sign in with the same name
and password next time.

### 6. Make yourself an admin

New accounts are ordinary players. To use magic words, sign in once, then stop the server:

```bash
docker compose -f server/docker/docker-compose.yml stop
```

Look up your account number in `runtime/databases/accounts.json`, and in `runtime/databases/astrondb/<number>.yaml` change
`ACCESS_LEVEL` to `"\"SYSTEM_ADMIN\""`. Then start the server again with the command from step 4. The magic words are
listed in [docs/MAGIC_WORDS.md](docs/MAGIC_WORDS.md).

### Settings

- **Game settings** (gag XP boost, holidays, typed names, invasion length) live in `runtime/data/gameconfig.json` and need no
  rebuild. They are listed in [server/docker/README.md](server/docker/README.md#game-settings-no-rebuild).
- **Time zone**: holidays follow the server's date in Amsterdam time. For another zone, change `TZ` in
  [server/docker/docker-compose.yml](server/docker/docker-compose.yml) and `TimeZone` in
  `server/toontown/toonbase/TTLocalizerEnglish.py`, then rebuild the client and the server.

## Hosting the party

- **Keep plain HTTP on your home network.** `http://<the Mac's address>:7380` sends passwords unencrypted, so never forward
  port 7380 to the internet. For friends elsewhere, use HTTPS through a tunnel: see [Playing over the internet](#playing-over-the-internet).
- Turn on Docker Desktop's "Start Docker Desktop when you sign in". The site is only up while Docker runs.
- Keep the Mac awake for the evening with `caffeinate -dims`, and use Ethernet if you can.
- Guests must be on the same network as the Mac (not a guest Wi-Fi), and the router must not isolate Wi-Fi clients from each other.
- If Chrome on a guest's Mac can't reach the server while Safari can, give Chrome the Local Network permission (macOS 15 and
  later: System Settings → Privacy & Security → Local Network).
- A guest who forgot their password: delete their entry from `runtime/data/users.json`. They sign in again with the same name and a
  new password and get their toons back.
- Take a backup before the party: [docs/OPERATIONS.md](docs/OPERATIONS.md#backups).

## Playing over the internet

Friends who are not on your network can play on a website of your own. Cloudflare Workers builds the page from this repository on
GitHub, so a push updates it. The game files are Disney's, so they stay out of git: they go in an R2 bucket, which the site serves
them from (`web/worker.js`, set up in `web/wrangler.jsonc`). The game server stays on the Mac, or on a VPS, reached through a Cloudflare Tunnel, so no port is opened and everything
is HTTPS. All of it fits in Cloudflare's free allowances; you need a domain on Cloudflare, and R2 asks for a payment method.

1. In Cloudflare Zero Trust, under Networks → Tunnels, create a tunnel with a public hostname such as `play.example.com` pointing to
   `http://localhost:7380`, and run its connector on the Mac:

   ```bash
   brew install cloudflared
   ```

   ```bash
   sudo cloudflared service install <the tunnel's token>
   ```

2. Put the game files in an R2 bucket. Build them first with `tools/build_client.sh` (step 3 of the setup).

   ```bash
   npx wrangler login
   ```

   ```bash
   npx wrangler r2 bucket create glonkfiles
   ```

   ```bash
   tools/upload_files.sh
   ```

   The first upload sends about 380 MB; later runs send only the files that changed.

3. In the Cloudflare dashboard, under Workers & Pages → Create → Import a repository, pick this repository and set:

   | Setting | Value |
   |---|---|
   | Project name | `glonktown` (the `name` in `web/wrangler.jsonc`) |
   | Build command | `sh build_page.sh` |
   | Deploy command | `npx wrangler deploy` |
   | Root directory (under advanced settings) | `web` |
   | Build variables | `GLONKTOWN_SERVER` = `https://play.example.com`, `PYTHON_VERSION` = `3.12` |

   The bucket binding comes from `web/wrangler.jsonc`; with another bucket name, change it there and pass the name to
   `tools/upload_files.sh`.

4. Give the Worker your domain (`example.com`) under its Settings → Domains & Routes → Add → Custom domain.

Every push builds the page again; other branches get preview versions. A push never changes the game files: run
`tools/upload_files.sh` when the art or the game's code changed.

- The page always opens on the sign-in screen; the game files download after signing in.
- The server's address must be `https://`: a page on HTTPS cannot reach a plain HTTP server.
- To move the server to a VPS, run the same Docker setup there with your `runtime/` folder, and run the tunnel's connector there
  instead of on the Mac. The address stays the same, so the site needs no new build. Any 64-bit Linux VPS works, x86_64 or ARM,
  with 2 GB of memory or more (Oracle Cloud's free Ampere VM, for example). On a VPS, change the port in `docker-compose.yml` to
  `127.0.0.1:7380:80`: Docker's published ports skip the server's firewall, so otherwise anyone could reach the plain HTTP site
  on the server's public address.
- For a different server address, change `GLONKTOWN_SERVER` in the Worker's build variables and build again (or push).
- One device can try another server by adding `?server=<address>` to the site's address; `?server=` switches it back.
- While registration is open, anyone who finds the site can make an account. Once your friends have signed up, set
  `"open_registration": false` in `runtime/data/users.json`.
- After a change to the game's code, upload the files and rebuild the server together (see [Updating](#updating)).

## Updating

- Server-only code (`*AI.py`, `*UD.py`, `astron/`): rebuild the image with the command from step 4.
- Code the browser runs, or files both sides read (for example `ToonDNA.py`): also rebuild the packs with
  `tools/build_client.sh packs`. Players reload the page once.
- **A change to `server/etc/toon.dc` or `server/etc/otp.dc` needs both rebuilds.** If the packs and the server disagree, Astron
  rejects every player with error 125.
- Playing over the internet: a push updates the page. After `tools/build_client.sh`, also run `tools/upload_files.sh`, so the
  site gets the new packs.

Running, debugging and backups in depth: [docs/OPERATIONS.md](docs/OPERATIONS.md). How the system fits together:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What the game records

To find crashes, the page sends **error and crash information** to the server on the Mac: Python error messages, page errors,
lost connections, the kind of device and browser, the screen size, and the **sign-in name** (never the password). It does not
record touches, chat or screenshots. Adding `?log=1` to the page's address turns on a fuller log for that visit.

## Credits
Glonktown is **[Open Toontown](https://github.com/open-toontown/open-toontown)** (the open-source Toontown Online code), by way of
**[Toontown: Anywhere](https://github.com/lPuffyy/open-toontown-anywhere)**'s server fork and browser client, with the classic
characters put back, fixes collected from other Open Toontown forks, and settings for a small group.

Glonktown is a small layer on top of other people's work.

- **[Open Toontown](https://github.com/open-toontown/open-toontown)** and its contributors: the game's code, and the
  [resources](https://github.com/open-toontown/resources).
- **[Toontown: Anywhere](https://github.com/lPuffyy/open-toontown-anywhere)** by [lPuffyy](https://github.com/lPuffyy): the base of
  this project. Their [server fork](https://github.com/lPuffyy/open-toontown-anywhere) and
  [browser client](https://github.com/lPuffyy/toontown-anywhere) made the whole thing possible: the server in one Docker image,
  `otpy`, the game running in the browser with touch controls and Web Audio sound, the download packs, the sign-in service,
  Astron compatibility, the friend manager, Cog invasions, the Districts page, and many fixes besides.

Fixes and features from other forks

| From | What |
|---|---|
| Open Toontown pull request [#115](https://github.com/open-toontown/open-toontown/pull/115) by [demiurgeQuantified](https://github.com/demiurgeQuantified) | Tag game collisions after Toon Escape |
| Open Toontown pull requests [#148](https://github.com/open-toontown/open-toontown/pull/148) to [#153](https://github.com/open-toontown/open-toontown/pull/153) by [edkimmel](https://github.com/edkimmel) | Saving packed database fields (toons save and reload correctly), the news page, unknown magic words no longer crash the district, the Photo Album page, street branch zones |
| [Project Retrolight](https://github.com/BrythonLexi/project-retrolight) by [BrythonLexi](https://github.com/BrythonLexi) | Crash fixes for Cashbot HQ ([`a21162e`](https://github.com/BrythonLexi/project-retrolight/commit/a21162e)) and pies in Goofy Speedway races ([`3a9e1c2`](https://github.com/BrythonLexi/project-retrolight/commit/3a9e1c2)); the small-group tuning: TTR-style Aoogah and Trunk damage with 3 TNT and 7 Trapdoor ([`041cede`](https://github.com/BrythonLexi/project-retrolight/commit/041cede)), one side in boss fights below four toons ([`6426b7b`](https://github.com/BrythonLexi/project-retrolight/commit/6426b7b)), no Laff requirement for facilities ([`e419dc9`](https://github.com/BrythonLexi/project-retrolight/commit/e419dc9)) and street Cog levels ([`97b0436`](https://github.com/BrythonLexi/project-retrolight/commit/97b0436)), balanced on Loopy's suggestions. Retrolight also inspired the 100 accuracy cap and x3 invasion XP. |
| [calebcodesalot's fork](https://github.com/calebcodesalot/open-toontown), changes by flytrapdev | Rebindable controls with a Controls tab, rebindable ToonTasks and gag hotkeys, Smooth Animations |
| [DarthMDev's fork](https://github.com/DarthMDev/open-toontown) | Entity file fix ([`860d261`](https://github.com/DarthMDev/open-toontown/commit/860d261)) |
| [maxrdz's fork](https://github.com/maxrdz/toontown) | No GM prefix on GM toons' names ([`c009e51`](https://github.com/maxrdz/toontown/commit/c009e51)) |

Built with [Panda3D](https://www.panda3d.org), [pygbag](https://github.com/pygame-web/pygbag) and
[Astron](https://github.com/Astron/Astron). More in [web/THIRD_PARTY_NOTICES.md](web/THIRD_PARTY_NOTICES.md).

## License

BSD 3-Clause, see [LICENSE](LICENSE). The server and client folders carry the licenses they came with
([server/LICENSE](server/LICENSE), [web/LICENSE](web/LICENSE)), and Panda3D's files in `server/docker/overlay` keep Panda3D's
license.

> Glonktown is a non-commercial fan project. It is not affiliated with, endorsed by, or connected to Disney or Toontown
> Rewritten. Toontown is a trademark of Disney. This repository contains **no game files**: no models, textures, sounds or other
> Disney content. You download those yourself (setup step 2).
