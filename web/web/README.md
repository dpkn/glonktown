# The browser client

What runs on the phone. How it fits together is in [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md), section 2.1.

| Path | Job |
|---|---|
| `ttr-ui.js`, `ttr-ui.css` | The page shell: sign-in, loading and download, touch controls, rotate and install screens, the in-game full-screen button, test-session logging |
| `ttr-audio.js` | Sound through the Web Audio API |
| `icon-*.png` | Home Screen icons (drawn by `tools/make_icons.py` at the repository root) |
| `game/` | The Python glue that starts the game in the browser (`main.py` and helpers) |
| `make_ot_packs.py` | Builds the download packs and `packs.json` |
| `patch_web.py` | Adds the shell, manifest and icons to the page pygbag builds |
| `ot_server.py`, `bridge_ot.py` | A small local test server and WebSocket bridge for development |
| `NOTICE.txt` | The licence notice packed into the code pack |

Not in the repository: the game's art, sound and data (`server/resources`, see the README at the root), and the `_ui/` files
that give the page the game's own look: `ImpressBT.ttf`, the game's interface font, and `sky.jpg`, its loading-screen sky
(`phase_3/maps/loading_bg_clouds.jpg`). `tools/build_client.sh` copies both from the resources. Without them the page is plain sky
blue and uses Nunito. The title and headings use Luckiest Guy from Google Fonts (or `_ui/ToonDisplay.ttf`, if you add one).

In game, a browser tab that has left full screen (Esc, or a swipe on Android) shows a small button at the top centre that goes
back to it.

The display settings (picture quality, smooth edges, the FPS counter, on-screen controls, keyboard keys) are hidden: open the
page once with `?display=1` to show the Display button and the in-game gear on that device, `?display=0` to hide them again.

## Build

1. Install [pygbag](https://github.com/pygame-web/pygbag) (the live site uses CDN version 0.9.3) and `pytz`.
2. Build the page from the glue code:

   ```
   pygbag --build web/game          # makes web/game/build/web/
   python web/patch_web.py          # adds the shell, and a server.js that plays on the page's own site
   ```

   The page signs in and plays on the site it came from (on the local test server, port 8002, it uses the bridge on 8766).
   `server.js` (`window.TTR_SERVER`) can name another game server, which `../build_page.sh` does for the website on Cloudflare.
3. Build the packs from the server's code and resources:

   ```
   OT_DIR=../server python web/make_ot_packs.py      # makes web/build/site/
   ```

   A big resource folder becomes several packs (`phase_4-1`, `phase_4-2`, ...) of at most 24 MiB each, because static hosts
   cap the size of one file (Cloudflare Pages: 25 MiB).

4. Put the files where the server serves them (`runtime/web` at the repository root, see [the operations notes](../../docs/OPERATIONS.md)):
   `web/game/build/web/*` to `_play/`, `web/build/site/*` to `root/`, and a `_ui/` folder with `ImpressBT.ttf` and `sky.jpg` (see
   above) into both `_play/` and `root/`.

## Try it locally

```
python web/ot_server.py 8002 0.0.0.0     # serves the page and packs, and accepts any sign-in
python web/bridge_ot.py                  # WebSocket on 8766 to a local Astron client agent on 7198
```

Run Astron, the UberDOG and a district from `server/` outside Docker, then open `http://<this machine>:8002`
on the phone. (The game fetches its Python runtime from a local address when the page is served from `localhost`, so use
the machine's network address, not `localhost`.)
