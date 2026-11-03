"""Build the browser download packs: _code.zip (the game's Python + config + our otpy) and one zip per resource folder (big folders in
   several parts: phase_3.5-1, phase_3.5-2, ...), plus packs.json.
   OT_DIR=<the game server checkout (Glonktown's server/), with its resources folder>  [OTPY_BASE=<folder holding otpy/> if OT_DIR has none]  python make_ot_packs.py      (writes into web/build/site)"""
import hashlib
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OT = os.environ.get("OT_DIR")
if not OT or not os.path.isdir(os.path.join(OT, "toontown")):
    raise SystemExit("set OT_DIR to the game server checkout that has its resources folder")
RES = os.path.join(OT, "resources")
# otpy/ (our replacement for the game's compiled libraries) is in the game server checkout; use the one in OT_DIR, or OTPY_BASE=<folder that holds otpy/>
OTPY_BASE = os.environ.get("OTPY_BASE") or OT
if not os.path.isdir(os.path.join(OTPY_BASE, "otpy")):
    raise SystemExit("otpy/ not found: build from the game server checkout, or set OTPY_BASE to the folder that holds otpy/")
SITE = os.path.join(HERE, "build", "site")
OUT = os.path.join(SITE, "_packs")
os.makedirs(OUT, exist_ok=True)
packs = []
# a static host limits the size of one file (Cloudflare Pages: 25 MiB), so a big resource folder goes out as several packs
PACK_LIMIT = 24 * 1024 * 1024


def entry(arc):
    return zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))     # no file times: the same files always make the same pack


def add(z, full, arc):
    with open(full, "rb") as f:
        z.writestr(entry(arc), f.read())


def pack_entry(name, zp):
    """The pack's line in packs.json: its name, size and a hash of its contents, which is how a device knows its saved copy is stale."""
    with open(zp, "rb") as f:
        return [name, os.path.getsize(zp), hashlib.sha256(f.read()).hexdigest()[:16]]


def folder_parts(folder):
    """The folder's files, split into lists that each make a pack under PACK_LIMIT; always in the same order, so a rebuild makes the same packs."""
    parts, part, size = [], [], 0
    for r, ds, fs in os.walk(folder):
        ds.sort()
        for f in sorted(fs):
            full = os.path.join(r, f)
            arc = os.path.relpath(full, RES).replace(os.sep, "/")
            n = os.path.getsize(full) + 100 + 2 * len(arc)       # the file and its two zip headers
            if part and size + n > PACK_LIMIT:
                parts.append(part)
                part, size = [], 0
            part.append((full, arc))
            size += n
    if part:
        parts.append(part)
    return parts



def web_patch(arc, text):
    """Phone-friendly chat: big chat buttons placed against the screen corner, so the
    page's safe-area margins can move them clear of the notch."""
    def sub(a, b):
        nonlocal text
        if a not in text:
            print("  WARNING: patch text not found in", arc, ":", a[:60])
        text = text.replace(a, b, 1)
    if arc.endswith("toontown/chat/ToontownChatManager.py"):
        text = "\n".join(["_CHAT_SCALE = 2.0", "_NORMAL_POS = (0.135, 0, -0.135)", "_SC_POS = (0.36, 0, -0.135)", ""]) + text
        sub("pos=(-1.2647, 0, 0.928), scale=1.179,", "pos=_NORMAL_POS, parent=base.a2dTopLeft, scale=_CHAT_SCALE,")
        sub("pos=TTLocalizer.TCMscButtonPos, scale=1.179,", "pos=_SC_POS, parent=base.a2dTopLeft, scale=_CHAT_SCALE,")
        sub("DirectFrame(parent=aspect2dp, relief=None, image=DGG.getDefaultDialogGeom(), image_scale=(0.45, 0.45, 0.45),",
            "DirectFrame(parent=base.a2dTopLeft, relief=None, image=DGG.getDefaultDialogGeom(), image_scale=(0.77, 0.70, 0.20),")
        sub("pos=(-0.4, 0, 0.754),", "pos=(0.40, 0, -0.105),")
        sub("pos=(-0.125, 0, -0.1), scale=1.179,", "pos=(-0.33, 0, 0.033), scale=1.179,")
        sub("pos=(0.0, 0, -0.1), scale=1.179,", "pos=(-0.195, 0, 0.033), scale=1.179,")
        sub("pos=(0.125, 0, -0.1), scale=1.179,", "pos=(-0.06, 0, 0.033), scale=1.179,")
        sub("self.normalPos = Vec3(-1.083, 0, 0.804)", "self.normalPos = Vec3(0.25, 0, -0.196)")
        sub("self.whisperPos = Vec3(0.0, 0, 0.71)", "self.whisperPos = Vec3(0.25, 0, -0.28)")
        sub("self.chatInputWhiteList.setPos(self.speedChatPlusPos)", "self.chatInputWhiteList.setPos(self.speedChatPlusPos)" + "\n" + "        self.chatInputWhiteList.reparentTo(base.a2dTopLeft)")
    elif arc.endswith("toontown/chat/TTChatInputSpeedChat.py"):
        text = "\n".join(["_SC_SCALE = 0.085", "_SC_X = 0.52", ""]) + text
        sub("self.speedChat.reparentTo(aspect2dp, DGG.FOREGROUND_SORT_INDEX)", "self.speedChat.reparentTo(base.a2dpTopLeft, DGG.FOREGROUND_SORT_INDEX)")
        sub("scZ = 0.96", "scZ = -0.04")
        sub("self.speedChat.setPos(-1.05, 0, scZ)", "self.speedChat.setPos(_SC_X, 0, scZ)")
        sub("self.speedChat.setScale(TTLocalizer.TTCISCspeedChat)", "self.speedChat.setScale(_SC_SCALE)")
    elif arc.endswith("toontown/quest/QuestParser.py"):
        # the tutorial moves the chat buttons with the 4:3 screen's coordinates; here they hang from the top left corner (above), so those
        # coordinates would send them off the screen. Send them to where the web layout keeps them instead, and point the arrows at them there.
        text = "\n".join([
            "_WEB_CHAT = {'chatScButton': (0.36, 0, -0.135), 'chatNormalButton': (0.135, 0, -0.135)}",
            "def _webChatPos(name, x, y, z):",
            "    home = _WEB_CHAT.get(name)",
            "    if home is None:",
            "        return x, y, z",
            "    if x < -1.0:",
            "        return home",
            "    return home[0] + 0.45, y, home[2] - 0.25",
            "def _webChatScale(name, x, y, z):",
            "    if name in _WEB_CHAT and abs(x - 1.179) < 0.01:",
            "        return 2.0, 2.0, 2.0",
            "    return x, y, z",
            ""]) + text
        sub("        return Func(node.setPos, x, y, z)", "        x, y, z = _webChatPos(nodeName, x, y, z)\n        return Func(node.setPos, x, y, z)")
        sub("        return Sequence(LerpPosInterval(node, t, Point3(x, y, z), blendType='easeInOut'), duration=0.0)",
            "        x, y, z = _webChatPos(nodeName, x, y, z)\n        return Sequence(LerpPosInterval(node, t, Point3(x, y, z), blendType='easeInOut'), duration=0.0)")
        sub("        return Func(node.setScale, x, y, z)", "        x, y, z = _webChatScale(nodeName, x, y, z)\n        return Func(node.setScale, x, y, z)")
        sub("        return Sequence(LerpScaleInterval(node, t, VBase3(x, y, z), blendType='easeInOut'), duration=0.0)",
            "        x, y, z = _webChatScale(nodeName, x, y, z)\n        return Sequence(LerpScaleInterval(node, t, VBase3(x, y, z), blendType='easeInOut'), duration=0.0)")
        sub("        return Func(arrows.arrowsOn, x1, y1, h1, x2, y2, h2)",
            "        if max(x1, x2) < -0.5:\n            return Func(lambda: arrows.arrowsOn(x1 + 4.0 / 3.0, y1 - 1.0, h1, x2 + 4.0 / 3.0, y2 - 1.0, h2, parent=base.a2dTopLeft))\n        return Func(arrows.arrowsOn, x1, y1, h1, x2, y2, h2)")
    elif arc.endswith("otp/otpbase/OTPGlobals.py"):
        # a phone's wide screen with the stock 52 degrees feels zoomed in: widen the default view (everything resets to this value)
        sub("DefaultCameraFov = 52.0", "DefaultCameraFov = 75.0")
    elif arc.endswith("toontown/minigame/Purchase.py"):
        # the jellybean results scene is a small set built for the original view: at our wider default it shows the edges and bends the shop
        sub("base.camLens.setFov(ToontownGlobals.DefaultCameraFov)", "base.camLens.setFov(52.0)")
    elif arc.endswith("toontown/chat/TTWhiteList.py"):
        # the chat word list: without it every typed word is refused and nothing is sent
        sub("        if __debug__:\n            searchPath.appendDirectory(Filename('resources/phase_3/etc'))",
            "\n".join(["        for _d in ('resources/phase_3/etc', '/data/data/game/assets/resources/phase_3/etc', '/data/data/game/assets/phase_3/etc'):",
                       "            searchPath.appendDirectory(Filename(_d))"]))
    elif arc.endswith("toontown/pets/PetNameGenerator.py"):
        sub("        filename = Filename(TTLocalizer.PetNameMaster)",
            "\n".join(["        for _d in ('resources/phase_3/etc', '/data/data/game/assets/resources/phase_3/etc', '/data/data/game/assets/phase_3/etc'):",
                       "            searchPath.appendDirectory(Filename(_d))",
                       "        filename = Filename(TTLocalizer.PetNameMaster)"]))
    return text

zp =os.path.join(OUT, "_code.zip")
n = 0
with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
    for pkg, base in (("otp", OT), ("toontown", OT), ("otpy", OTPY_BASE)):
        for r, ds, fs in os.walk(os.path.join(base, pkg)):
            ds[:] = sorted(d for d in ds if d != "__pycache__")
            for f in sorted(fs):
                if f.endswith(".py"):
                    full = os.path.join(r, f)
                    arc = "_code/" + os.path.relpath(full, base).replace(os.sep, "/")
                    text = open(full, encoding="utf-8", errors="surrogateescape").read()
                    # a browser's graphics layer has no alpha test, so the game's "binary"/"dual" see-through modes draw solid: use plain blending
                    text = text.replace("TransparencyAttrib.MDual", "TransparencyAttrib.MAlpha").replace("TransparencyAttrib.MBinary", "TransparencyAttrib.MAlpha")
                    text = web_patch(arc, text)
                    z.writestr(entry(arc), text.encode("utf-8", errors="surrogateescape"))
                    n += 1
    import pytz
    pz = os.path.dirname(os.path.dirname(pytz.__file__))
    for r, ds, fs in os.walk(os.path.join(pz, "pytz")):          # the game's time code needs pytz (pure Python + zone data)
        ds[:] = sorted(d for d in ds if d != "__pycache__")
        for f in sorted(fs):
            full = os.path.join(r, f)
            add(z, full, "_code/" + os.path.relpath(full, pz).replace(os.sep, "/"))
            n += 1
    for f in sorted(os.listdir(os.path.join(OT, "etc"))):
        add(z, os.path.join(OT, "etc", f), "_code/etc/" + f)
        n += 1
    add(z, os.path.join(OT, "LICENSE"), "_code/LICENSE-OpenToontown")          # BSD: source redistributions keep the licence notice
    add(z, os.path.join(HERE, "NOTICE.txt"), "_code/NOTICE.txt")
    n += 2
# a patch that no longer fits the source can leave a file that will not even load, and the game then stops at the loading screen: refuse to ship that
with zipfile.ZipFile(zp) as _z:
    _bad = []
    for _n in _z.namelist():
        if _n.endswith(".py"):
            try:
                compile(_z.read(_n), _n, "exec")
            except SyntaxError as _e:
                _bad.append("%s: %s" % (_n, _e))
if _bad:
    raise SystemExit("syntax errors in the code pack, not publishing: " + "; ".join(_bad))
packs.append(pack_entry("_code", zp))
print("_code", n, "files", os.path.getsize(zp) // 1024, "KB")
for d in sorted(os.listdir(RES)):
    p = os.path.join(RES, d)
    if not os.path.isdir(p) or d.startswith("."):
        continue
    parts = folder_parts(p)
    for i, files in enumerate(parts):
        name = d if len(parts) == 1 else "%s-%d" % (d, i + 1)
        zp = os.path.join(OUT, name + ".zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
            for full, arc in files:
                add(z, full, arc)
        packs.append(pack_entry(name, zp))
        print("%-12s %6d files %8.1f MB" % (name, len(files), os.path.getsize(zp) / 1e6))
built = {name + ".zip" for name, _, _ in packs}
for f in os.listdir(OUT):
    if f not in built:
        os.remove(os.path.join(OUT, f))
for name, size, _ in packs:
    if size > PACK_LIMIT:
        print("  WARNING: %s.zip is %.1f MB, too big for a static host such as Cloudflare Pages" % (name, size / 1e6))
json.dump(packs, open(os.path.join(SITE, "packs.json"), "w"))
json.dump({"files": [], "code": []}, open(os.path.join(SITE, "manifest.json"), "w"))
print("packs.json:", len(packs), "packs")
