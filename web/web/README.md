# The browser client

What runs on the phone. How it fits together is in [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md), section 2.1.

| Path | Job |
|---|---|
| `ttr-ui.js`, `ttr-ui.css` | The page shell: sign-in, loading and download, touch controls, rotate and install screens, recovery cards, test-session logging |
| `ttr-audio.js` | Sound through the Web Audio API |
| `icon-*.png` | Home Screen icons (drawn by `tools/make_icons.py` at the repository root) |
| `game/` | The Python glue that starts Open Toontown in the browser (`main.py` and helpers) |
| `make_ot_packs.py` | Builds the download packs and `packs.json` |
| `patch_web.py` | Adds the shell, manifest and icons to the page pygbag builds |
| `ot_server.py`, `bridge_ot.py` | A small local test server and WebSocket bridge for development |
| `NOTICE.txt` | The licence notice packed into the code pack |

Not in the repository: the game's art, sound and data (`server/resources`, see the README at the root), the `_ui/` pictures the page
uses (`background.jpg` for the sky and the Toon font `ToonDisplay.ttf` for the title; the page works without them, with a
drawn sky and system fonts) and an optional `logo.png`. The rest of the page uses Nunito from Google Fonts.

The display settings (picture quality, smooth edges, the FPS counter, on-screen controls, keyboard keys) are hidden: open the
page once with `?display=1` to show the Display button and the in-game gear on that device, `?display=0` to hide them again.

## Build

1. Install [pygbag](https://github.com/pygame-web/pygbag) (the live site uses CDN version 0.9.3) and `pytz`.
2. Build the page from the glue code:

   ```
   pygbag --build web/game          # makes web/game/build/web/
   python web/patch_web.py auto     # "auto": the page connects to wss://<its own site>/ws
   ```

   For a local test use `python web/patch_web.py ws://localhost:8766` instead.
3. Build the packs from the server's code and resources:

   ```
   OT_DIR=../server python web/make_ot_packs.py      # makes web/build/site/
   ```

4. Put the files where the server serves them (`runtime/web` at the repository root, see [the operations notes](../docs/OPERATIONS.md)):
   `web/game/build/web/*` to `_play/`, `web/build/site/*` to `root/`, and your `_ui/` folder into both `_play/` and `root/`.

## Try it locally

```
python web/ot_server.py 8002 0.0.0.0     # serves the page and packs, and accepts any sign-in
python web/bridge_ot.py                  # WebSocket on 8766 to a local Astron client agent on 7198
```

Run Astron, the UberDOG and a district from your Open Toontown checkout as usual, then open `http://<this machine>:8002`
on the phone. (The game fetches its Python runtime from a local address when the page is served from `localhost`, so use
the machine's network address, not `localhost`.)
