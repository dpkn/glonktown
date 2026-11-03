# Glonktown browser client

The game as players run it: Open Toontown's Python in WebAssembly ([pygbag](https://github.com/pygame-web/pygbag) with Panda3D),
inside a page shell that handles sign-in, downloads, touch controls and sound. It started as
[Toontown: Anywhere](https://github.com/lPuffyy/toontown-anywhere)'s browser client.

This folder holds **no game files**: no models, textures, sounds or Disney content. The game's code is in [`../server`](../server),
and the download packs are built from it and the resources by [`../tools/build_client.sh`](../tools/build_client.sh).

| Folder | What it is |
|---|---|
| [`web/`](web) | The page's screens (sign-in, loading, controls), the Python glue that runs Open Toontown in the browser, and the scripts that build the download packs and the page. |
| [`tools/`](tools) | Small operations scripts: who is online, a check that the packs match the server, a browserless sign-in test. |
| [`docs/`](docs) | The write-up of the system. |

Start with **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**. The other documents:

- [docs/OPERATIONS.md](docs/OPERATIONS.md): running, updating, backing up and debugging the server.
- [docs/CHANGES.md](docs/CHANGES.md): everything that differs from stock Open Toontown, and the known problems.
- [docs/TODO.md](docs/TODO.md): open work.

## License and notices

The client code is under the BSD 3-Clause License, see [LICENSE](LICENSE). Third-party components and credits are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
