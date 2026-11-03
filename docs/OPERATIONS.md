# Running the server

How to run, update, back up and debug Glonktown on the host Mac. Read [ARCHITECTURE.md](ARCHITECTURE.md) first.

Paths here are from the repository root:

```
server/    the game server (code, docker/, otpy/); server/resources holds the game's resources (not in git)
web/       the browser client
runtime/   the container's mounts (not in git): databases/, data/, web/{_play,root}
tools/     build_client.sh (page + packs into runtime/web), make_icons.py
```

The game's resources are in `server/resources` (see the README's setup step 2), mounted read-only.

## Everyday

### Start, stop, restart

```
docker compose -f server/docker/docker-compose.yml up -d --build      # build (if needed) and start
docker compose -f server/docker/docker-compose.yml stop
docker compose -f server/docker/docker-compose.yml restart
```

The image builds natively for ARM (Apple Silicon, Ampere) and x86_64.
A start takes **about 40 seconds**: the UberDOG, then the one district. Everyone playing is disconnected by a restart,
and the browser game reconnects by itself when it can. The container restarts itself if the UberDOG or the district crashes.

### Is it healthy?

```
docker ps --filter name=glonktown
tail -n 1 runtime/data/logs/ai1.log           # the district ends its start-up with "Done."
grep -il traceback runtime/data/logs/*.log    # should print nothing
```

### Logs

All in `runtime/data/logs/`, **replaced every time the container starts** (copy them first if you are chasing a problem that
happened before a restart):

| File | Process |
|---|---|
| `astron.log` | Astron |
| `ud.log` | the UberDOG |
| `ai1.log` | the district (Toon Valley) |
| `bridge.log` | the WebSocket bridge (one `open` and one `close` line per connection, with the address) |
| `auth.log` | the sign-in service |
| `client.log` | crash reports and test sessions from the browsers (see below) |

A `ConnectionClosedError` traceback in `bridge.log` is just a device disconnecting.

### Who is online

```
docker cp web/tools/who_is_online.py glonktown:/tmp/ && docker exec glonktown python /tmp/who_is_online.py
```

## Settings without a rebuild

`runtime/data/gameconfig.json` holds the settings the host may want to change on the night (gag XP boost, holidays, typed names,
invasion length). They are listed in `server/docker/README.md`. The server rereads the file every few seconds; browsers read it
when the page starts the game.

## Updating

### Server code

The code is copied into the image, so after a change in `server/` rebuild and restart:

```
docker compose -f server/docker/docker-compose.yml up -d --build
```

### The client (what players run)

Anything the **browser** runs (the game's Python, art, or the page's own files) is built into `runtime/web`:

```
tools/build_client.sh          # the page and the packs
tools/build_client.sh packs    # the packs only (game code changed)
```

Players reload the page once. Packs whose size changed are downloaded again; the rest stay cached on the device.

**After changing `etc/toon.dc` or `etc/otp.dc`, rebuild the image and the packs together**, then check they match:

```
python web/tools/check_pack_matches_server.py http://<the Mac's address>:7380 server/etc
```

If they disagree, Astron rejects every player (error 125, "Client DC hash mismatch") and the game says "Your installed files appear
to be invalid".

Server-only changes (anything under `toontown/…AI.py`, `astron/`) need only the image rebuild. Changes to a file that both sides read
(for example `ToonDNA.py`, `ToontownBattleGlobals.py`) need **both**.

## Accounts

### Logins (`runtime/data/users.json`)

The file has `open_registration` (true or false) and `users` (name to salted hash and an optional `admin` flag). The sign-in
service rereads it on every request, so you can edit it while the server runs. To close registration to new names, set
`open_registration` to `false`.

**A guest forgot their password:** delete their entry from `users`. They sign in again with the same name and a new password,
and get the same toons back, because the game account is matched by name (`runtime/databases/accounts.json`).

### Game accounts and toons (`runtime/databases`)

- `accounts.json` maps a name to an account number.
- `astrondb/<number>.yaml` is each object: an `AstronAccount` (its toons and access level) or a `DistributedToon`.
- To make an account staff ([magic words](MAGIC_WORDS.md)), set its `ACCESS_LEVEL` to `"SYSTEM_ADMIN"` (or `ADMIN`, `DEVELOPER`, `MODERATOR`).
  Stop the container first; Astron rewrites these files as the game runs.
- Never edit toons while the container is running.

## Backups

- Every 24 hours of uptime, the container writes `runtime/data/backups/auto-<date>.tgz` (the databases and `users.json`) and keeps
  the newest 14.
- Take one by hand before the party and before any risky change:

  ```
  cd runtime && tar czf data/backups/manual-$(date +%Y%m%d-%H%M).tgz databases data/users.json
  ```

- To restore, stop the container, unpack over `runtime/databases` and `runtime/data/users.json`, and start it.

## Client logging

Every browser sends **crash information** to `runtime/data/logs/client.log`, quietly: Python tracebacks and error lines, page errors,
lost connections, one line about the device (browser, screen size) and one line with the sign-in name. At most 400 lines per visit;
nothing else (no passwords, touches or frame timings). The page decides this (`quietLog` in `web/web/ttr-ui.js`).

The file stops growing at 30 MB. How many lines an address may send an hour is `CLOG_PER_HOUR` in
`server/docker/docker-compose.yml`.

## Test sessions with logging

Open the page with `?log=1` (for example `http://<the Mac's address>:7380/play/?log=1`) on the device that shows the problem and
reproduce it. Then read `runtime/data/logs/client.log`. Each line is `date time address text`; lines starting `PY|` are the game's
own output (including Python errors), and `JS|` lines are page errors and browser warnings. Logging stays on for the rest of that
browser visit and is off again on the next normal visit.

## Troubleshooting

| Symptom | Look at |
|---|---|
| Guests cannot connect at all | Is the container up? Does `ai1.log` end in "Done."? Is the Mac's firewall letting Docker accept connections? Then `bridge.log` for `open` lines. |
| The page loads on the Mac but not on phones | Use the Mac's network address, not `localhost`; check the phone is on the same Wi-Fi. |
| "Wrong password" for someone who is sure | `users.json`: is the name spelled as they type it (names are lower-cased)? Deleting their entry resets it (see Accounts). |
| A change is not showing | Was `tools/build_client.sh` run, and the page reloaded? A phone that still shows the old page needs its site data cleared. |
| A toon looks wrong | Colours are the 39-entry table in `ToonDNA.py`; check client and server both have it. |
| Game output after a crash is gone | Logs are replaced on restart; use a `?log=1` session next time. |
