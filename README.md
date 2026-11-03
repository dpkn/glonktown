# Glonktown

An easy-to-use private server and browser client for the classic toon MMO, made for playing with a few friends. Players play
**in a web browser** on a laptop, phone or tablet, at [glonk.town](https://glonk.town). The host runs the server in Docker on a
PC, Mac or small server, and nobody else installs anything.

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

## Host a server

Your friends play on [glonk.town](https://glonk.town), and the site connects them to your server. Your server needs no website of
its own, only a [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/), which gives it an
HTTPS address without opening a port on your router.

### What you need

- A computer that stays on while you play: a Mac with [Docker Desktop](https://www.docker.com/products/docker-desktop/) or
  [OrbStack](https://orbstack.dev), a Windows 10 or 11 PC with [Docker Desktop](https://www.docker.com/products/docker-desktop/), or a 64-bit Linux machine with Docker (x86_64 or ARM, 2 GB of memory or more).
- A free Cloudflare account with a domain on it
- About 2 GB of free disk space.

### 1. Start the server

Make a folder for the server and get its settings file. On Windows, run these in PowerShell and type `curl.exe` instead of `curl`:

```bash
mkdir glonktown && cd glonktown
```

```bash
curl -O https://raw.githubusercontent.com/dpkn/glonktown/main/docker-compose.yml
```

Start it:

```bash
docker compose up -d
```

The first start downloads the game's art, sound and level files (about 400 MB, from
[open-toontown/resources](https://github.com/open-toontown/resources)). Everything the server keeps goes in `runtime/` inside
this folder. The server is ready when the district's log ends with `Done.`:

```bash
tail -n 1 runtime/data/logs/ai1.log
```

On Windows:

```powershell
Get-Content runtime\data\logs\ai1.log -Tail 1
```

### 2. Connect the tunnel

1. In Cloudflare Zero Trust, under Networks → Tunnels, create a tunnel (Cloudflared) and give it one route (Published application
   routes, or Public hostnames on older dashboards): for example `play.example.com`, service `HTTP`, URL `localhost:7380`. No
   Access application is needed.
2. The dashboard then shows an install command that ends in the tunnel's token. Copy the token (or the whole command) and save it
   as `runtime/data/tunnel_token`. On a Mac:

   ```bash
   pbpaste > runtime/data/tunnel_token
   ```

   On Windows, in PowerShell:

   ```powershell
   Get-Clipboard | Set-Content runtime\data\tunnel_token
   ```

3. Restart the server:

   ```bash
   docker compose restart
   ```

The server runs the tunnel itself whenever it runs. `runtime/data/logs/tunnel.log` shows whether it connected.

### 3. Play

Open **`https://glonk.town/?server=https://play.example.com`** (with your tunnel's address), pick a toon name and a password, and
tap **PLAY**. Send the same link to your friends. Each device remembers the server, so after the first visit
`https://glonk.town` is enough.

The first start downloads about 390 MB of game files; after that they stay on the device. Players sign in with the same name and
password next time.

### 4. Make yourself an admin

New accounts are ordinary players. To use the [magic words](docs/MAGIC_WORDS.md), sign in once, then stop the server:

```bash
docker compose stop
```

Look up your account number in `runtime/databases/accounts.json`, and in `runtime/databases/astrondb/<number>.yaml` change
`ACCESS_LEVEL` to `"\"SYSTEM_ADMIN\""`. Then start the server again:

```bash
docker compose up -d
```

### Settings

- **Game settings** (gag XP boost, holidays, typed names, invasion length) live in `runtime/data/gameconfig.json` and need no
  restart. They are listed in [server/docker/README.md](server/docker/README.md#game-settings-no-rebuild).
- **Sign-ups**: while registration is open, anyone who finds your server's address can make an account. Once your friends have
  signed up, set `"open_registration": false` in `runtime/data/users.json`.
- **Time zone**: holidays follow the server's date in Amsterdam time. Change `TZ` in `docker-compose.yml` for the server's side.

### Updating

glonk.town always runs the newest version of the game, so keep your server up to date:

```bash
docker compose pull
```

```bash
docker compose up -d
```

If every player gets error 125 when signing in, the server and the site are on different versions: update the server.

### Hosting the party

- Turn on Docker Desktop's "Start Docker Desktop when you sign in" (Settings → General). The server is only up while Docker runs.
- Keep the computer awake for the evening, and use Ethernet if you can. On a Mac, run `caffeinate -dims`; on Windows, set
  Settings → System → Power → Sleep to Never.
- A player who forgot their password: delete their entry from `runtime/data/users.json`. They sign in again with the same name and
  a new password and get their toons back.
- The server makes a backup every night in `runtime/data/backups`. Take one by hand before the party:
  [docs/OPERATIONS.md](docs/OPERATIONS.md#backups).
- To move the server to another machine, copy the whole folder (with `runtime/`, so the toons and the tunnel's token come along),
  start it there and stop it on the old one: two servers on one tunnel would share the players between them. The address stays
  the same.
- To take the server off the internet, delete `runtime/data/tunnel_token` and restart the server.

## Development

Everything below is for changing the game, or for running your own copy of the website.

### Repository layout

| Path                                                                       | What it is                                                                                                                                                       |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`server/`](server)                                                        | The game server: the game's code, `otpy` (a pure-Python replacement for the game's compiled libraries) and the Docker image ([`server/docker/`](server/docker)). |
| [`web/`](web)                                                              | The browser client: the page shell, the Python glue that runs the game in WebAssembly, the scripts that build the download packs.                                |
| [`docs/`](docs)                                                            | How it works, running it, every change, the magic words and the to-do list.                                                                                      |
| [`tools/`](tools)                                                          | `build_client.sh` builds the page and the packs; `upload_files.sh` uploads them to the website's bucket; `make_icons.py` draws the home-screen icons.            |
| [`docker-compose.yml`](docker-compose.yml)                                 | Runs the published image, for hosts.                                                                                                                             |
| [`.github/workflows/server-image.yml`](.github/workflows/server-image.yml) | Builds that image for x86_64 and ARM on every push to `main` that changes `server/`, and publishes it as `ghcr.io/dpkn/glonktown`.                               |
| `server/resources`                                                         | The game's art, sound and DNA files. **Not in git**: you clone it below.                                                                                         |
| `runtime/`                                                                 | The server's data: accounts, toons, logs and the built page. **Not in git**; created on first run.                                                               |

### Run it from source

You need Docker, Python 3.12 and Git.

```bash
git clone https://github.com/dpkn/glonktown.git && cd glonktown
```

The game's resources go in `server/resources` (a clone, or a symlink to one). Use the commit in `RESOURCES_COMMIT` in
[server/docker/Dockerfile](server/docker/Dockerfile), so the packs match the published server:

```bash
git clone https://github.com/open-toontown/resources.git server/resources
```

Make a virtual environment with pygbag 0.9.3 (the version whose runtime the page bundles) and pytz, then build the page and the download
packs into `runtime/web`:

```bash
python3.12 -m venv .venv && .venv/bin/pip install pygbag==0.9.3 pytz
```

```bash
tools/build_client.sh
```

Build the server image from source and start it:

```bash
docker compose -f server/docker/docker-compose.yml up -d --build
```

The first build compiles Astron and takes several minutes. This server serves the page itself, at
**`http://<this computer's address>:7380/play/`** (find the address with `ipconfig getifaddr en0` on a Mac). The page carries
its own Python runtime and Panda3D, so the devices only need to reach this server, not the internet.

On the home network:

- Plain HTTP sends passwords unencrypted, so never forward port 7380 to the internet: use the tunnel for that.
- Players must be on the same network as the server (not a guest Wi-Fi), and the router must not isolate Wi-Fi clients from each
  other.
- If Chrome on a Mac can't reach the server while Safari can, give Chrome the Local Network permission (macOS 15 and later: System
  Settings → Privacy & Security → Local Network).
- One device can try another server by adding `?server=<address>` to the page's address; `?server=` switches it back.

### What to rebuild after a change

- Server-only code (`*AI.py`, `*UD.py`, `astron/`): rebuild the image with the command above. A push to `main` publishes the new
  image for hosts.
- Code the browser runs, or files both sides read (for example `ToonDNA.py`): also rebuild the packs with
  `tools/build_client.sh packs`. Players reload the page once.
- **A change to `server/etc/toon.dc` or `server/etc/otp.dc` needs both rebuilds.** If the packs and the server disagree, Astron
  rejects every player with error 125. On the website, upload the packs (below) and publish the image together, and tell hosts to
  update.
- **Time zone**: besides `TZ`, change `TimeZone` in `server/toontown/toonbase/TTLocalizerEnglish.py`, then rebuild the client and
  the server.

Running, debugging and backups in depth: [docs/OPERATIONS.md](docs/OPERATIONS.md). How the system fits together:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### Your own website

This is how glonk.town runs. Cloudflare Workers builds the page from this repository on GitHub, so a push updates it. The game
files are Disney's, so they stay out of git: they go in an R2 bucket, which the site serves them from (`web/worker.js`, set up in
`web/wrangler.jsonc`). All of it fits in Cloudflare's free allowances; you need a domain on Cloudflare, and R2 asks for a payment
method.

1. Put the game files in an R2 bucket. Build them first with `tools/build_client.sh`.

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

2. In the Cloudflare dashboard, under Workers & Pages → Create → Import a repository, pick this repository and set:

   | Setting                                  | Value                                                                                                |
   | ---------------------------------------- | ---------------------------------------------------------------------------------------------------- |
   | Project name                             | `glonktown` (the `name` in `web/wrangler.jsonc`)                                                     |
   | Build command                            | `sh build_page.sh`                                                                                   |
   | Deploy command                           | `npx wrangler deploy`                                                                                |
   | Root directory (under advanced settings) | `web`                                                                                                |
   | Build variables                          | `GLONKTOWN_SERVER` = `https://play.example.com` (the server devices use when no `?server=` is given) |

   The bucket binding comes from `web/wrangler.jsonc`; with another bucket name, change it there and pass the name to
   `tools/upload_files.sh`.

3. Give the Worker your domain (`example.com`) under its Settings → Domains & Routes → Add → Custom domain.

Every push builds the page again; other branches get preview versions. A push never changes the game files: run
`tools/upload_files.sh` when the art or the game's code changed.

- The page opens on a welcome screen that checks whether the game server answers: only then can players go on to sign in,
  otherwise it says Glonktown is closed (and asks again every 30 seconds). The game files download after signing in.
- The server's address must be `https://`: a page on HTTPS cannot reach a plain HTTP server.
- For a different default server, change `GLONKTOWN_SERVER` in the Worker's build variables and build again (or push).

## What the game records

To find crashes, the page sends **error and crash information** to the game server: Python error messages, page errors,
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

| From                                                                                                                                                                                                      | What                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Open Toontown pull request [#115](https://github.com/open-toontown/open-toontown/pull/115) by [demiurgeQuantified](https://github.com/demiurgeQuantified)                                                 | Tag game collisions after Toon Escape                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Open Toontown pull requests [#148](https://github.com/open-toontown/open-toontown/pull/148) to [#153](https://github.com/open-toontown/open-toontown/pull/153) by [edkimmel](https://github.com/edkimmel) | Saving packed database fields (toons save and reload correctly), the news page, unknown magic words no longer crash the district, the Photo Album page, street branch zones                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| [Project Retrolight](https://github.com/BrythonLexi/project-retrolight) by [BrythonLexi](https://github.com/BrythonLexi)                                                                                  | Crash fixes for Cashbot HQ ([`a21162e`](https://github.com/BrythonLexi/project-retrolight/commit/a21162e)) and pies in Goofy Speedway races ([`3a9e1c2`](https://github.com/BrythonLexi/project-retrolight/commit/3a9e1c2)); the small-group tuning: TTR-style Aoogah and Trunk damage with 3 TNT and 7 Trapdoor ([`041cede`](https://github.com/BrythonLexi/project-retrolight/commit/041cede)), one side in boss fights below four toons ([`6426b7b`](https://github.com/BrythonLexi/project-retrolight/commit/6426b7b)), no Laff requirement for facilities ([`e419dc9`](https://github.com/BrythonLexi/project-retrolight/commit/e419dc9)) and street Cog levels ([`97b0436`](https://github.com/BrythonLexi/project-retrolight/commit/97b0436)), balanced on Loopy's suggestions. Retrolight also inspired the 100 accuracy cap and x3 invasion XP. |
| [calebcodesalot's fork](https://github.com/calebcodesalot/open-toontown), changes by flytrapdev                                                                                                           | Rebindable controls with a Controls tab, rebindable ToonTasks and gag hotkeys, Smooth Animations                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| [DarthMDev's fork](https://github.com/DarthMDev/open-toontown)                                                                                                                                            | Entity file fix ([`860d261`](https://github.com/DarthMDev/open-toontown/commit/860d261))                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| [maxrdz's fork](https://github.com/maxrdz/toontown)                                                                                                                                                       | No GM prefix on GM toons' names ([`c009e51`](https://github.com/maxrdz/toontown/commit/c009e51))                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

Built with [Panda3D](https://www.panda3d.org), [pygbag](https://github.com/pygame-web/pygbag) and
[Astron](https://github.com/Astron/Astron). More in [web/THIRD_PARTY_NOTICES.md](web/THIRD_PARTY_NOTICES.md).

## License

BSD 3-Clause, see [LICENSE](LICENSE). The server and client folders carry the licenses they came with
([server/LICENSE](server/LICENSE), [web/LICENSE](web/LICENSE)), and Panda3D's files in `server/docker/overlay` keep Panda3D's
license.

> Glonktown is a non-commercial fan project. It is not affiliated with, endorsed by, or connected to Disney or Toontown
> Rewritten. Toontown is a trademark of Disney. This repository contains **no game files**: no models, textures, sounds or other
> Disney content. The server downloads those itself, from [open-toontown/resources](https://github.com/open-toontown/resources).
