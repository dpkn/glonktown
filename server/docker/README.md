# Running the server in Docker

This folder builds **one image that runs the whole Glonktown server**: Astron (built from source), the UberDOG, one district
(Toon Valley), a WebSocket bridge for the browser client, a small sign-in service, nginx, and backups, on the host's Mac for a
LAN party.

The image has the game's **code**. It does **not** have the game's **resources** (the art, sound and DNA files): they belong to
Disney and are not in this repository. When the resources mount is empty, the first start downloads them from
[open-toontown/resources](https://github.com/open-toontown/resources) at `RESOURCES_COMMIT` (in the Dockerfile). The source setup
mounts your own clone in `server/resources` read-only instead.

## Build and run

On the Mac, with Docker (Docker Desktop or OrbStack), from the root of the repository:

```
docker compose -f server/docker/docker-compose.yml up -d --build
```

The image builds natively for ARM (Apple Silicon, Ampere) and x86_64; the first build compiles Astron and takes
several minutes. The district is open when `runtime/data/logs/ai1.log` ends with `Done.`, about 40 seconds after the start.

| Mount (from `docker-compose.yml`) | What it holds |
|---|---|
| `/ot/src/resources` | The game's resources. Downloaded on the first start when empty; a read-only mount without `phase_3` stops the container with a message. |
| `/ot/src/astron/databases` | `runtime/databases`: the toons and accounts (Astron's YAML database). Back this up. |
| `/ot/data` | `runtime/data`: `users.json` (sign-ins), `gameconfig.json`, `logs/`, `backups/`. |
| `/ot/web` | `runtime/web`: the browser client's page (`_play/`) and download packs (`root/`), built by `tools/build_client.sh` at the repository root. |

Hosts run the published image (`ghcr.io/dpkn/glonktown`) with the `docker-compose.yml` at the repository root instead, which
publishes the port to the computer itself only and keeps everything in `runtime/` next to it.

Port **80** inside is the only port published, as **7380** on the Mac: nginx serves the page and packs, and passes `/ws` (the game's
WebSocket), `/auth`, `/recover` and `/setrecovery` (sign-in) to the services behind it. Keep it on the home network.

## The client

The browser client (the page, its Python glue, and the scripts that build the download packs from the resources) is in `web/`
at the repository root.

## Notes

- **Players are ordinary.** `docker/live.prc` makes new accounts `NO_ACCESS`. To make someone staff (for the
  [magic words](../../docs/MAGIC_WORDS.md)), set `ACCESS_LEVEL` to
  `SYSTEM_ADMIN` (or `ADMIN`, `DEVELOPER`, `MODERATOR`) in their account file under `runtime/databases/astrondb`, while the server is stopped.
- **Sign-in.** The sign-in service keeps `users.json` (salted PBKDF2-SHA256) and gives each signed-in player a play token, signed with
  `login_secret` in the data folder; the game's login manager only lets in genuine tokens. Everything is plain HTTP, so keep the server
  reachable only through nginx: never publish Astron's ports or forward 7380 to the internet. For the internet, `run.sh` runs a
  Cloudflare Tunnel (HTTPS) when the data folder has a `tunnel_token`; without one it stays off.
- **What is inside.** Python 3.9, Panda3D 1.11 (a development wheel), the Python side of Panda3D 1.11 in `docker/overlay/direct`
  (Panda3D's own files, with its license), our pure-Python replacement for the compiled `libotp` / `libtoontown` (`otpy/`), and Astron
  built from <https://github.com/Astron/Astron> at the commit named in the Dockerfile.
- **Time zone.** The container runs on Amsterdam time (`TZ` in `docker-compose.yml`), so holidays follow the host's date.

## Game settings (no rebuild)

Settings the person running the server may want to change live in one small file, `gameconfig.json`, in the data folder
(`/ot/data/gameconfig.json`):

```
{"gag_xp_boost": 4}
```

| Setting | Default | What it does |
|---|---|---|
| `gag_xp_boost` | `4` | Multiplies the gag training points credited for each hit. The per-battle cap per track grows with it (200 times the boost). `1` is the original rate. |
| `typed_names` | `"auto"` | `"auto"`: the server approves typed toon names that pass its checks. `"off"`: players must pick a name from the lists. |
| `halloween` | `"auto"` | Street decorations, the spooky sky and the Halloween Speed Chat phrases. `"auto"`: on from October 20 to November 1 (the server's date). `"on"` or `"off"` forces it. |
| `winter` | `"auto"` | Winter street decorations, the winter Speed Chat menu and the carol menu. `"auto"`: December 1 to January 3. `"on"` or `"off"` forces it. |
| `valentines` | `"auto"` | Valentine's Day: double Toon-up from safe-zone hearts. `"auto"`: February 7 to 15. `"on"` or `"off"` forces it. |
| `jellybean_days` | `"off"` | Extra jellybeans from trolley games and fishing. `"auto"`: every Saturday and Sunday. `"on"` forces it. Off unless you set it, because it changes the economy. |
| `invasion_cogs` | `75` | How many Cogs an invasion has. It ends when they are all defeated, and the next one starts 10 to 25 minutes later. 75 is about what 6 to 8 toons can defeat in the time an invasion lasts. |
| `invasion_minutes` | `30` | A Cog invasion also ends by itself after this many minutes, when the town has not defeated them all. |
| `community_goal` | `1500` | The points the town needs to save Glonktown (`toontown/ai/CommunityGoalAI.py`): a Cog is worth its level, a building taken back 10 per floor, a finished invasion 50, a boss 100. Rewards come at each quarter. 1500 is about three hours for 6 to 8 new toons; lower it during the party if it goes slowly. The progress is kept in `community_goal.json` in the data folder: start it over with `~goal reset` before the party. |
| `walkers` | `6` | Walking toons in each playground while a real toon is there (0 to 12; `0` turns them off). A change takes effect within a few seconds: extra walkers leave and missing ones arrive. |

The server looks at the file again every few seconds, so a change reaches the next battle without a restart (a holiday change takes up to a minute, and players already in the game see it at once). The browser game reads the same file
(served as `/gameconfig.json`) when the page starts the game, so players pick the change up the next time they load the page. A missing file, or a
missing or invalid setting, means the default. The web server serves this file to everyone, so keep secrets out of it.

## Typed toon names

When a player types a name, the server judges it itself (`otp/login/NameJudge.py`) and either accepts it on the spot or rejects it with the game's
standard message. It checks the length (2 to 24 characters, at most 4 words), the game's own name rules, that it is not an NPC's name, a list of
blocked words, and that no other toon already has the name. Every decision is written to the server log as a `typed-name` event.

The blocked-word list is only a starter (kept ROT13-encoded so the repository does not spell the words out). Add your own to
`/ot/data/blocked_names.txt`, one per line; the server reads the file again when it changes, with no restart:

```
# a word on its own: blocked as a whole word (also as word+s, +y, +er, +ing, +head, +face, +hat, +hole)
badger
# *word: blocked anywhere inside a name (for words that are never innocent)
*grumpus
# !word: allowed, for an innocent name the filter would otherwise catch
!shitake
```

Before matching, the name is flattened so common tricks do not work: capitals, accents, full-width letters, look-alike letters from other
alphabets (a Cyrillic "o"), look-alike characters (0 for o, 1 for i, 3 for e, @ for a) and repeated letters are all evened out, and spaces, dots and
dashes between letters are ignored for the "anywhere inside" words ("f u c k"). This stops the obvious cases only; check new names as they appear and
extend the file. To switch typed names off completely, set `"typed_names": "off"` in `gameconfig.json`.
