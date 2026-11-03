# Glonktown browser client

The game as players run it: the game's Python in WebAssembly ([pygbag](https://github.com/pygame-web/pygbag) with Panda3D),
inside a page shell that handles sign-in, downloads, touch controls and sound.

This folder holds **no game files**: no models, textures, sounds or Disney content. The game's code is in [`../server`](../server),
and the download packs are built from it and the resources by [`../tools/build_client.sh`](../tools/build_client.sh).

| Folder | What it is |
|---|---|
| [`web/`](web) | The page's screens (sign-in, loading, controls), the Python glue that runs the game in the browser, and the scripts that build the download packs and the page. |
| [`tools/`](tools) | Small operations scripts: who is online, a check that the packs match the server, a browserless sign-in test. |

How it all fits together is in [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md), section 2.1.

## License and notices

The client code is under the BSD 3-Clause License, see [LICENSE](LICENSE). Third-party components and credits are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
