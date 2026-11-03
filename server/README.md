# Glonktown server

The game server. It is [Open Toontown](https://github.com/open-toontown/open-toontown), the code of Disney's Toontown Online
(sv1.0.47.38), by way of [Toontown: Anywhere](https://github.com/lPuffyy/open-toontown-anywhere)'s server fork: the whole server
in one Docker image, and a game that also runs in a web browser.

What is in this folder:

- **A Docker image of the whole server** ([`docker/`](docker)): Astron, the UberDOG, one district, a WebSocket bridge, a sign-in
  service and nginx.
- **[`otpy`](otpy)**: a pure-Python replacement for the compiled `libotp` and `libtoontown`, so the game runs on a plain Linux
  server and in a browser.
- The game's code (`otp/`, `toontown/`, `etc/`) with Toontown: Anywhere's Astron compatibility, server-side friend manager,
  invasions, Districts page, fishing and quest fixes, and Glonktown's changes: the classic characters and original neighborhood
  names, fixes from other Open Toontown forks, small-group tuning and rebindable controls. The full list is in
  [`../web/docs/CHANGES.md`](../web/docs/CHANGES.md).

The game's **resources** (art, sound and DNA files) are Disney's, so they are not in this repository or in the image. Clone them
into `server/resources`; the [README at the repository root](../README.md) has the steps.

Running the server, its mounts, staff accounts and settings: [docker/README.md](docker/README.md).

## License

Open Toontown is the work of its contributors; Toontown: Anywhere and Glonktown add their changes on top. See [LICENSE](LICENSE).
Panda3D files in `docker/overlay` keep their own license (`docker/overlay/LICENSE-Panda3D.txt`).
