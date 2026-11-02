# Glonktown server

The game server for Glonktown, a private Toontown for a birthday LAN party. It is [Open Toontown](https://github.com/open-toontown/open-toontown),
the code of Disney's Toontown Online (sv1.0.47.38), by way of [Toontown: Anywhere](https://github.com/lPuffyy/open-toontown-anywhere)'s
server fork: the whole server in one Docker image, and a client that runs in a web browser.

What is on the `glonktown` branch:

- **A Docker image of the whole server**: Astron, the UberDOG, one district, a WebSocket bridge, a sign-in service and nginx.
- **[`otpy`](otpy)**: a pure-Python replacement for the compiled `libotp` and `libtoontown`, so the game runs on a plain Linux server and in a browser.
- Toontown: Anywhere's Astron compatibility, server-side friend manager, invasions, the Districts page, fishing and quest fixes.
- The classic characters and the original neighborhood names, fixes from other Open Toontown forks, small-group tuning and
  rebindable controls. The full list is in the client repository's `docs/CHANGES.md`.

## Run the server

You need Docker (with Rosetta emulation for amd64 on Apple Silicon) and the game's **resources** (the art, sound and DNA files). They
are Disney's, so they are not in this repository or in the image: they are mounted from `~/Documents/open-toontown/resources`.

```
docker compose -f docker/docker-compose.yml up -d --build
```

The server is ready when `runtime/data/logs/ai1.log` (next to this repository) ends with `Done.`, about a minute and a half after the
start. Only port 80 inside the container is published, as 7380 on the Mac; keep it on the home network and never publish Astron's
own ports.

More (mounts, staff accounts, sign-in, settings, what is inside the image): [docker/README.md](docker/README.md).

## Play

The browser client, and the scripts that build its download packs from the resources, are in the `web/` repository next to this one.
Guests open `http://<the Mac's address>:7380/play/`.

## License and credits

Open Toontown is the work of its contributors; Toontown: Anywhere and Glonktown add their changes on top. See [LICENSE](LICENSE).
Panda3D files in `docker/overlay` keep their own license (`docker/overlay/LICENSE-Panda3D.txt`).
