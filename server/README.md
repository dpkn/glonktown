# Glonktown server

The game server: the whole server in one Docker image, and a game that also runs in a web browser. Where the code comes from is
in the [README's credits](../README.md#credits).

What is in this folder:

- **A Docker image of the whole server** ([`docker/`](docker)): Astron, the UberDOG, one district, a WebSocket bridge, a sign-in
  service and nginx.
- **[`otpy`](otpy)**: a pure-Python replacement for the compiled `libotp` and `libtoontown`, so the game runs on a plain Linux
  server and in a browser.
- The game's code (`otp/`, `toontown/`, `etc/`). Every change to it is in [`../docs/CHANGES.md`](../docs/CHANGES.md).

The game's **resources** (art, sound and DNA files) are Disney's, so they are not in this repository or in the image. Clone them
into `server/resources`; the [README at the repository root](../README.md) has the steps.

Running the server, its mounts, staff accounts and settings: [docker/README.md](docker/README.md).

## License

See [LICENSE](LICENSE).
Panda3D files in `docker/overlay` keep their own license (`docker/overlay/LICENSE-Panda3D.txt`).
