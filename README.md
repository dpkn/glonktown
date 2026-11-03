# Glonktown

An easy-to-use, private Toontown server and client. Guests play **in a web browser** on a laptop, phone or tablet, against a server running in
Docker on the host's PC or Mac. Nobody else installs anything.

## What's in it

- **Plays in the browser** (from Toontown: Anywhere): CPython and Panda3D compiled to WebAssembly, touch controls for phones, sound through Web Audio, sign-in with a name and password, and game files cached on the device after the first load.
- **Easy server setup**: one Docker image to run, nothing else to worry about.  
- **One district with Cog invasions**, the game is tuned for a few friends: boosted gag XP, accuracy up to 100, x3 invasion XP, TTR-style gag
  balance, no Laff requirement for facilities, street Cog levels per neighborhood, and toons on one side of a boss fight when
  there are fewer than four.
- **Rebindable controls**: a Controls tab in the Shticker Book, plus a Smooth Animations option.
- **Crash fixes and polish** from Open Toontown's open pull requests and from other forks (see [Credits](#credits)).
- **Magic Words**: Admins can trigger events and change game stats easily using the chat. 

Everything that differs from stock Open Toontown is listed in [web/docs/CHANGES.md](web/docs/CHANGES.md).

## Repository layout

| Path | What it is |
|---|---|
| [`server/`](server) | The game server: Open Toontown's code with Toontown: Anywhere's and Glonktown's changes, `otpy` (a pure-Python replacement for the game's compiled libraries) and the Docker image ([`server/docker/`](server/docker)). |
| [`web/`](web) | The browser client: the page shell, the Python glue that runs the game in WebAssembly, the scripts that build the download packs, and the docs ([`web/docs/`](web/docs)). |
| [`tools/`](tools) | `build_client.sh` builds the page and the packs; `make_icons.py` draws the home-screen icons. |
| `server/resources` | The game's art, sound and DNA files. **Not in git**: you clone it in step 2. |
| `runtime/` | The server's data: accounts, toons, logs and the built page. **Not in git**; created on first run. |

## Setup

### What you need

- A Mac with [Docker Desktop](https://www.docker.com/products/docker-desktop/) or [OrbStack](https://orbstack.dev). Built and tested
  on Apple Silicon. The server image is `linux/amd64` (its Panda3D build only exists for x86_64), so Docker emulates it there; with
  or without Rosetta it is fast enough for a party.
- Python 3.12 and Git.
- About 4 GB of free disk space: about 0.9 GB of resources, 0.8 GB for the server image and about 0.8 GB for the built game files.
- Internet access for the guests' devices: the page loads its Python runtime from pygbag's CDN.

### 1. Clone

```bash
git clone https://github.com/dpkn/glonktown.git
```

```bash
cd glonktown
```

### 2. Get the resources from Open Toontown

The game's art, sound and level files live in Open Toontown's separate
[resources repository](https://github.com/open-toontown/resources). Clone it into `server/resources`:

```bash
git clone https://github.com/open-toontown/resources.git server/resources
```

If you already have an Open Toontown checkout with its resources, a symlink works too, and saves the disk space:

```bash
ln -s /path/to/open-toontown/resources server/resources
```

`server/resources` is in `.gitignore`. Never commit it: it is Disney's content.

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
a minute and a half after it starts:

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
`ACCESS_LEVEL` to `"\"SYSTEM_ADMIN\""`. Then start the server again with the command from step 4.

### Settings

- **Game settings** (gag XP boost, holidays, typed names, invasion length) live in `runtime/data/gameconfig.json` and need no
  rebuild. They are listed in [server/docker/README.md](server/docker/README.md#game-settings-no-rebuild).
- **Time zone**: holidays follow the server's date in Amsterdam time. For another zone, change `TZ` in
  [server/docker/docker-compose.yml](server/docker/docker-compose.yml) and `TimeZone` in
  `server/toontown/toonbase/TTLocalizerEnglish.py`, then rebuild the client and the server.

## Hosting the party

- **Keep it on your home network.** The game connection trusts the name the page sends; only the sign-in page checks
  passwords. Never forward port 7380 or tunnel it to the internet.
- Turn on Docker Desktop's "Start Docker Desktop when you sign in". The site is only up while Docker runs.
- Keep the Mac awake for the evening with `caffeinate -dims`, and use Ethernet if you can.
- Guests must be on the same network as the Mac (not a guest Wi-Fi), and the router must not isolate Wi-Fi clients from each other.
- If Chrome on a guest's Mac can't reach the server while Safari can, give Chrome the Local Network permission (macOS 15 and
  later: System Settings → Privacy & Security → Local Network).
- A guest who forgot their password: delete their entry from `runtime/data/users.json`. They sign in again with the same name and a
  new password and get their toons back.
- Take a backup before the party: [web/docs/OPERATIONS.md](web/docs/OPERATIONS.md#backups).

## Updating

- Server-only code (`*AI.py`, `*UD.py`, `astron/`): rebuild the image with the command from step 4.
- Code the browser runs, or files both sides read (for example `ToonDNA.py`): also rebuild the packs with
  `tools/build_client.sh packs`. Players reload the page once.
- **A change to `server/etc/toon.dc` or `server/etc/otp.dc` needs both rebuilds.** If the packs and the server disagree, Astron
  rejects every player with error 125.

Running, debugging and backups in depth: [web/docs/OPERATIONS.md](web/docs/OPERATIONS.md). How the system fits together:
[web/docs/ARCHITECTURE.md](web/docs/ARCHITECTURE.md).

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

Fixes and features from other forks. Each commit keeps its original author in the git history.

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
> Disney content. You download those from Open Toontown yourself (step 2 below).
