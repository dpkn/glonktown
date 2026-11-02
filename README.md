# Glonktown

A private Toontown for a birthday LAN party. Guests play **in a web browser** on a laptop, phone or tablet, against a server
running in Docker on the host's Mac. Nobody installs anything. It is not affiliated with, endorsed by, or connected to Disney
or Toontown Rewritten.

The game is **[Open Toontown](https://github.com/open-toontown/open-toontown)** (the open-source Toontown Online code), by way of
[Toontown: Anywhere](https://github.com/lPuffyy/toontown-anywhere)'s browser client and server fork, with the classic characters
restored, fixes from other forks and settings for a small group. The browser client is Python running in WebAssembly
([pygbag](https://github.com/pygame-web/pygbag) with Panda3D).

## Play

On the party's network, open **`http://<the host Mac's address>:7380/play/`**, pick a toon name and a password, and tap **PLAY!**
Use the same name and password next time.

- The first start downloads the game files (about 390 MB). They are kept on the device afterwards.
- Phones drop the connection when you switch to another app. Coming back, the game tries to reconnect by itself.
- Forgot your password? Ask the host to reset it; your toons stay.

The server only trusts the name the page sends, so it must stay on the home network: never forward its port or tunnel it to the
internet.

## What is in this repository

This repository holds the browser client, but **no game files**: no models, textures, sounds or Disney content. The game's code and
the server's Docker image are in the server repository next to it (`../server`).

| Folder | What it is |
|---|---|
| [`web/`](web) | The browser client: the page's screens (sign-in, loading, controls), the Python glue that runs Open Toontown in the browser, and the scripts that build the download packs and the page. |
| [`tools/`](tools) | Small operations scripts. |
| [`docs/`](docs) | The write-up of the system. |

Start with **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. The other documents:

- [docs/OPERATIONS.md](docs/OPERATIONS.md): running, updating, backing up and debugging the server.
- [docs/CHANGES.md](docs/CHANGES.md): everything that differs from stock Open Toontown, and the known problems.
- [docs/TODO.md](docs/TODO.md): open work.

## What the game records

To find crashes, the page sends **error and crash information** to the server on the Mac: Python error messages, page errors, lost
connections, the kind of device and browser, the screen size, and the **sign-in name** (never the password). It does not record
touches, chat or screenshots. Opening the page with `?log=1` added to the address turns on a fuller log for that visit.

## License and notices

The client code is under the BSD 3-Clause License, see [LICENSE](LICENSE). Open Toontown is under the BSD 3-Clause License too, and
Panda3D under a modified BSD license. Third-party components and credits are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Toontown is a trademark of Disney. This is a private fan project with no commercial purpose.
