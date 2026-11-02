"""Play the start of a game session over the WebSocket, the way the browser does, without a browser. Run inside the container:
    docker cp tools/smoke_login.py glonktown:/tmp/ && docker exec -w /ot/src glonktown python /tmp/smoke_login.py [ws url] [sign-in name]
It checks that Astron accepts the code pack's protocol files (DC hash and version), signs in, makes a toon in the first free slot and
names it, signs in again to see the toon come back from the database, lists the classic characters and props in each playground of
the district, then asks the district to load the toon. The test account stays in the database (default name: glonktown-smoketest)."""
import asyncio
import json
import os
import sys
import tempfile
import zipfile

import websockets
from direct.distributed.MsgTypes import (CLIENT_ADD_INTEREST, CLIENT_DONE_INTEREST_RESP, CLIENT_EJECT, CLIENT_ENTER_OBJECT_REQUIRED,
                                         CLIENT_ENTER_OBJECT_REQUIRED_OTHER, CLIENT_HELLO, CLIENT_HELLO_RESP, CLIENT_OBJECT_SET_FIELD)
from panda3d.core import Datagram, DatagramIterator, Filename
from panda3d.direct import DCFile, DCPacker

URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1/ws"
NAME = sys.argv[2] if len(sys.argv) > 2 else "glonktown-smoketest"
LOGIN_MANAGER = 4670
GAME_ROOT, DISTRICTS_ZONE = 4618, 3
SERVER_VERSION = "sv1.0.47.38"
FIRST_NAME_ASTRO = 34
PLAYGROUNDS = {2000: "Toontown Central", 1000: "Donald's Dock", 3000: "The Brrrgh", 4000: "Minnie's Melodyland", 5000: "Daisy Gardens",
               6000: "Acorn Acres", 8000: "Goofy Speedway", 9000: "Donald's Dreamland"}
CHARACTER_WORDS = ("Mickey", "Minnie", "Goofy", "Donald", "Daisy", "Pluto", "Chip", "Dale", "Boat", "Piano")


def pack_dc():
    """The DC files players get are the ones inside the code pack; read those, and use them to talk to the server."""
    pack = zipfile.ZipFile("/ot/web/root/_packs/_code.zip")
    folder = tempfile.mkdtemp()
    dc = DCFile()
    for name in ("otp.dc", "toon.dc"):
        path = os.path.join(folder, name)
        with open(path, "wb") as f:
            f.write(pack.read("_code/etc/" + name))
        if not dc.read(Filename.fromOsSpecific(path)):
            raise SystemExit("could not read the pack's " + name)
    return dc


class Session:
    def __init__(self, ws, dc):
        self.ws, self.dc = ws, dc
        self.manager = dc.getClassByName("AstronLoginManager")
        self.buf = b""
        self.context = 0

    async def send(self, dg):
        payload = bytes(dg.getMessage())
        await self.ws.send(len(payload).to_bytes(2, "little") + payload)

    async def call(self, field, *args):
        await self.send(self.manager.clientFormatUpdate(field, LOGIN_MANAGER, list(args)))

    async def next_message(self):
        """One Astron message; a WebSocket frame can hold several, or part of one."""
        while True:
            if len(self.buf) >= 2:
                size = int.from_bytes(self.buf[:2], "little")
                if len(self.buf) >= 2 + size:
                    msg, self.buf = self.buf[2:2 + size], self.buf[2 + size:]
                    self.datagram = Datagram(msg)          # the iterator only points into it, so it must outlive the iterator
                    it = DatagramIterator(self.datagram)
                    kind = it.getUint16()
                    if kind == CLIENT_EJECT:
                        raise SystemExit("ejected: %d %s" % (it.getUint16(), it.getString()))
                    return kind, it, msg
            self.buf += await self.ws.recv()

    async def expect(self, wanted, timeout=60):
        """Wait for a field update from the login manager (or "hello" for the hello answer)."""
        async def wait():
            while True:
                kind, it, msg = await self.next_message()
                if kind == CLIENT_HELLO_RESP and wanted == "hello":
                    return None
                if kind == CLIENT_OBJECT_SET_FIELD:
                    doId, field = it.getUint32(), self.dc.getFieldByIndex(it.getUint16())
                    if doId == LOGIN_MANAGER and field.getName() == wanted:
                        packer = DCPacker()
                        packer.setUnpackData(bytes(msg[it.getCurrentIndex():]))
                        packer.beginUnpack(field)
                        value = packer.unpackObject()
                        packer.endUnpack()
                        return value
        return await asyncio.wait_for(wait(), timeout)

    async def objects_in(self, parent, zones, timeout=60):
        """Open interest in the zones and return {zone: [(doId, class name)]} of what the server sends."""
        self.context += 1
        found = {zone: [] for zone in zones}
        pending = set()
        for i, zone in enumerate(zones):
            ctx = self.context * 100 + i
            dg = Datagram()
            dg.addUint16(CLIENT_ADD_INTEREST)
            dg.addUint32(ctx)
            dg.addUint16(ctx % 65536)
            dg.addUint32(parent)
            dg.addUint32(zone)
            await self.send(dg)
            pending.add(ctx)

        async def wait():
            while pending:
                kind, it, _ = await self.next_message()
                if kind in (CLIENT_ENTER_OBJECT_REQUIRED, CLIENT_ENTER_OBJECT_REQUIRED_OTHER):
                    doId, _, zone, classId = it.getUint32(), it.getUint32(), it.getUint32(), it.getUint16()
                    if zone in found:
                        found[zone].append((doId, self.dc.getClass(classId).getName()))
                elif kind == CLIENT_DONE_INTEREST_RESP:
                    pending.discard(it.getUint32())
        await asyncio.wait_for(wait(), timeout)
        return found

    async def hello_and_login(self):
        dg = Datagram()
        dg.addUint16(CLIENT_HELLO)
        dg.addUint32(self.dc.getHash())
        dg.addString(SERVER_VERSION)
        await self.send(dg)
        await self.expect("hello")
        await self.call("requestLogin", NAME)
        (blob,) = await self.expect("loginResponse")
        reply = json.loads(blob)
        if reply.get("returnCode") != 0:
            raise SystemExit("login refused: %r" % reply)
        await self.call("requestAvatarList")
        (avatars,) = await self.expect("avatarListResponse")
        return avatars


async def main():
    from toontown.toon import ToonDNA
    dc = pack_dc()
    print("code pack DC hash %08x" % dc.getHash())
    async with websockets.connect(URL, max_size=2 ** 20) as ws:
        s = Session(ws, dc)
        avatars = await s.hello_and_login()
        print("hello accepted, signed in as %r, %d toon(s)" % (NAME, len(avatars)))
        used = {a[3] for a in avatars}
        slot = next(i for i in range(6) if i not in used)
        dna = ToonDNA.ToonDNA()
        dna.newToonRandom()
        await s.call("createAvatar", dna.makeNetString(), slot)
        (avId,) = await s.expect("createAvatarResponse")
        await s.call("setNamePattern", avId, -1, 0, FIRST_NAME_ASTRO, 1, -1, 0, -1, 0)
        _, status = await s.expect("namePatternAnswer")
        print("made toon %d in slot %d, name accepted: %s" % (avId, slot, bool(status)))
    async with websockets.connect(URL, max_size=2 ** 20) as ws:
        s = Session(ws, dc)
        avatars = await s.hello_and_login()
        back = [a for a in avatars if a[0] == avId]
        if not back:
            raise SystemExit("the new toon is missing after signing in again")
        _, name, dnaBlob, position, _ = back[0]
        same = bytes(dnaBlob) == bytes(dna.makeNetString())
        print("signed in again: toon %d is back as %r in slot %d, looks unchanged: %s" % (avId, name, position, same))
        if not same:
            raise SystemExit("the toon's DNA changed in the database")
        districts = [doId for doId, cls in (await s.objects_in(GAME_ROOT, [DISTRICTS_ZONE]))[DISTRICTS_ZONE] if cls == "ToontownDistrict"]
        print("districts:", districts)
        for zone, objects in (await s.objects_in(districts[0], list(PLAYGROUNDS))).items():
            names = sorted({cls for _, cls in objects if any(w in cls for w in CHARACTER_WORDS)})
            print("  %-20s %s" % (PLAYGROUNDS[zone], ", ".join(names) or "(no characters)"))
        await s.call("requestPlayAvatar", avId)
        await asyncio.sleep(8)
        print("asked the district to load toon %d; see ai1.log" % avId)


asyncio.run(main())
