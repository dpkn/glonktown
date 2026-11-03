# Changes

Glonktown is built in three layers. This file lists the second and third, kept apart:

1. **[Open Toontown](https://github.com/open-toontown/open-toontown)** at commit `2b366a2`: the open-source code of Disney's
   Toontown Online.
2. **[Toontown: Anywhere](https://github.com/lPuffyy/open-toontown-anywhere)**: the server in one Docker image and the game in a web
   browser. `git log 2b366a2..cc55a23` lists its server changes.
3. **Glonktown**: everything after that, for a few friends on one home network, including fixes merged from other forks.

Open problems are in [TODO.md](TODO.md).

## By Glonktown

### Gameplay

- **The classic characters are back** (Mickey, Minnie, Goofy, Donald, Daisy, Pluto, Chip and Dale, with their holiday chatter),
  and the neighborhoods have their original names (Donald's Dock, Minnie's Melodyland, Daisy Gardens, Goofy Speedway, Donald's
  Dreamland, Chip 'n Dale's Acorn Acres). The Donald's Dock boat is back, and Minnie's piano spins again (upstream never created
  it). Toontown: Anywhere had removed the characters and renamed the neighborhoods.
- **The town is called Glonktown** in the game's own text and window title; the first playground is Glonktown Central.
- **One district**, Toon Valley, with Cog invasions. Toontown: Anywhere ran three.
- **Small-group tuning** (from Retrolight): Aoogah and Trunk damage and gag carry limits as on Toontown Rewritten (3 TNT, 7
  Trapdoor), toons enter boss fights on one side when there are fewer than four, no Laff requirement for facilities, street Cog
  levels per neighborhood, accuracy can reach 100, and invasions give x3 gag XP. The gag XP boost itself is still
  `gameconfig.json`'s.
- **Field Office Cogs stay at level 10 or below.** A Field Office Cog is one level above its street's highest; with the new
  Dreamland levels that made 11, which no street Cog reaches, and the district crashed choosing one.
- **Times** are Amsterdam's (`TTLocalizer.TimeZone`, and `TZ` in the container), so holidays follow the host's date.
- **Parties work** (upstream left the whole server side empty, and the party client called a `getString` that Python's
  `IntEnum` does not have, so the planner, the Events page and every activity crashed; `PartyGlobals.PartyEnum` adds it).
  - **Planning:** a Party Planner takes the host to the planner, which charges the party's cost and sends invites to the friends
    picked. A friend answers from their mailbox; the host sees the answers on the Events page, where they can also make the
    party private or cancel it (95% back).
  - **Running:** at its start time the host is told the party can start and starts it from the Events page. It lasts 30
    minutes, then everyone gets the "party is over" message and is sent home half a minute later. Invited friends go from their
    Events page; a public party is also listed at the Toontown Central party gate, which now exists. A party nobody started is
    refunded (95%), the next time its host plays if they are away.
  - **Activities:** jukebox, dance floor, fireworks (once a party, host only), trampoline, cannons and the clouds above them,
    catch, Cog pie toss and tug of war, with their Valentine, Winter and Victory versions. The server checks what clients
    report (a catch is only counted for an object the server knows fell, trampoline beans only as fast as perfect bouncing
    can reach them, cannon aim within the cannon's limits) and pays the jellybeans.
  - **Kept** in `/ot/data/parties.json` (`toontown/parties/PartyStoreAI.py`, `toontown/uberdog/DistributedPartyManagerAI.py`),
    so invites reach friends who were offline. A party that was running when the server restarted can be started again by its
    host for the rest of its 30 minutes.
  - **Client fixes:** party times use the right time zone (they were 42 minutes off), a refused party entry sends the toon back
    with a message instead of into an empty Party Grounds, other players' pies show in the Cog pie toss, the right hand catches
    fruit, a guest arriving mid-bounce no longer crashes on the trampoline, the tug of war no longer crashes when a team empties
    as it starts, and the Valentine jukeboxes silence the party music like the others.
- **`~beans`**, a new magic word: gives jellybeans, filling the jar first and then the bank. All magic words are in
  [MAGIC_WORDS.md](MAGIC_WORDS.md).

### Fixes from other forks

Upstream pull requests #115 and #148 to #153 (tag game, database writes, news page, unknown magic words, the photo album page,
street branch zones), Retrolight's Cashbot HQ and Speedway pie crashes, DarthMDev's entity file fix and maxrdz's GM name fix. Who
made each is in the [README's credits](../README.md#credits).

### Controls

- **Rebindable controls** (from calebcodesalot): a Controls tab in the Shticker Book's options to rebind walking, jumping,
  ToonTasks, gags and chat (arrow keys or WASD presets), and a Smooth Animations switch (on by default, as before).
- **WASD by default**: W/A/S/D to walk, Space to jump and Enter to chat, for toons that never changed their keys (saved keys stay).
- **Run key for everyone**: hold Shift to run at the `~run` Magic Word's speed. It can be rebound in the Controls tab.
- **Escape stays in the game in full screen** in Chrome and Edge (hold Escape to leave full screen). Safari and Firefox always
  leave full screen on Escape.
- **Walking no longer gets stuck after a cutscene.** Typed chat and the joystick switched walking on while a cutscene held the
  toon, and it could never walk again afterwards.

### In the browser

- **Ice Slide works.** Toontown: Anywhere's page replaced Panda3D's ODE physics module (`panda3d.ode`) with an empty stand-in, so
  Ice Slide crashed while loading (`OdeUtil.getInfinity`) and everyone on the trolley stayed on the loading screen. The browser's
  Panda3D has ODE built in, and `web/web/game/main.py` no longer hides it. Golf uses the same module but has not been tested in the
  browser yet.
- **Full screen stays on when the game window opens.** The game's options ask for a window, and Panda3D's WebGL window left full
  screen when its startup properties said so. The page owns full screen now. A tab that has left full screen (Esc, or a swipe on
  Android) gets a button at the top of the game that goes back to it.
- **Quitting, or losing the server, goes back to the sign-in screen.** pygbag's own `sys.exit` stops the page's Python without
  raising, so Exit (or Cancel on "connection lost") froze the game on a grey screen, still in full screen. In the game `sys.exit`
  raises again, `main.py` hands the quit to the page, and the page starts again at the sign-in screen, which says why: logged out,
  the connection was lost, or the server's reason for throwing the player out. Reconnecting by itself now stops after three tries
  (closing the box used to reset the count, so it went on forever) and then goes back the same way, and a box with only OK
  (thrown out on purpose) no longer reconnects into the same error.
- **Chrome no longer runs out of memory** on the silent keep-alive sound: it is one second of real silence instead of an empty
  looping clip.
- The loading and pick-a-toon screens use the stock cloud sky (`loading_bg_clouds.jpg`).

### The page

- **It is called Glonktown**; the server choice card, the community links and the credit line are gone.
- **It looks like the game**: the loading-screen cloud sky, the game's ImpressBT font, a sign-in dialog like the game's (pale
  yellow, green rim), the game's loading bar, and a title lettered like the game's logo.
- **Sign-in asks only for a name and a password.** The recovery questions are gone; the host resets a forgotten password
  ([OPERATIONS.md](OPERATIONS.md#accounts)).

### Hosting

- **The game connection checks the sign-in.** It used to trust whatever name the game sent, so anyone who talked to the
  WebSocket directly could play as someone else. The sign-in service now hands out a play token signed with a key only
  the server knows, valid for a day, and the login manager lets in only genuine tokens ([ARCHITECTURE.md](ARCHITECTURE.md),
  section 3).
- **Connection limits for a party.** Docker Desktop on a Mac hides each guest's own address (every connection arrives from its
  gateway), so the bridge's per-address limits would be shared by everyone. They are settings now (`MAX_PER_IP`,
  `MAX_NEW_PER_MIN`, and `CLOG_PER_HOUR` for crash reports), set for the whole party in `server/docker/docker-compose.yml`.
- **A browserless sign-in test**, `web/tools/smoke_login.py`: says hello with the pack's DC hash, signs in, makes a toon, loads it
  again and lists the playground characters.
- **Removed**: Toontown: Anywhere's Discord status service and bots, its Docker image publishing, the quest guide and the
  old-server migration tools.

## From Toontown: Anywhere

What Toontown: Anywhere changed in Open Toontown, and Glonktown keeps.

### Running anywhere

- **The whole server in one Docker image**: Astron, the UberDOG, the districts, a WebSocket bridge, a sign-in service, nginx and a
  nightly backup ([ARCHITECTURE.md](ARCHITECTURE.md#24-the-server-container-serverdocker)).
- **`otpy`**, a pure-Python replacement for the compiled `libotp` and `libtoontown`, used on the server and in the browser.
- **The game in the browser**: CPython and Panda3D in WebAssembly through pygbag, the page shell (sign-in, the loading and download
  screen, the rotate and "add to Home Screen" screens), touch controls, sound through Web Audio, the download packs cached on the
  device, crash reports, and the test-session log (`?log=1`).
- Many small compatibility fixes (chat, nametags, estate, pets, minigames, hoods, and so on) that let the game run on Astron's
  current client interface and in the browser.

### Districts and population

- The district statistics object (`ToontownDistrictStats`) is generated under the game's root object, which is where the
  client's interest can see it. This is what makes the Districts page show populations.
- A district's population is counted for its own streets. Toons in Welcome Valley are listed under Welcome Valley, not in two
  places.
- `ToontownDistrictStats` has a new field, `setInvasion(string, uint8, uint32)`, that tells every client which Cog is invading a
  district and how many are left (`server/etc/toon.dc`).

### Cog invasions (`toontown/suit/SuitInvasionManagerAI.py`, rewritten)

- Each district schedules its own invasions: the **first about one to four minutes after the district opens**, then one every
  **10 to 25 minutes**. Each is **1,000 Cogs** of one random type, and also ends after `invasion_minutes` (`gameconfig.json`).
- Cogs defeated count down the invasion; it ends at zero.
- Starting or stopping an invasion publishes it on the district statistics (so the Districts page shows it), sends a Toon HQ
  bulletin to the district, and logs `invasion begins` at warning level. Toons arriving mid-invasion get the bulletin five
  seconds after they appear.

### Fishing

- **Fish Bingo is switched off.** The hourly Bingo Night (20 minutes of every hour, announced by Toon HQ) is built
  (`toontown/fishing/FishBingoScheduleAI.py`) but disabled by `ENABLED = False`, because it crashes ([TODO.md](TODO.md)).
- Pond fish swim to a new spot over **9 seconds** (stock: 5) and then **rest 3 to 8 seconds** before moving again
  (`FishingTargetGlobals.py`, `DistributedFishingTargetAI.py`).

### Quests

- When a toon with no tasks talks to a Toon HQ officer, the server first checks whether the toon has finished every required
  reward of its tier and, if so, moves it to the next tier (`QuestManagerAI.py`). Before this, a toon could be left on a finished
  tier and be offered only "Just For Fun" tasks.

### Friends

- **Toon-to-toon friend invitations work** (`otp/friends/FriendManagerAI.py`). Stock Open Toontown has only an empty stub for it,
  and the client was sending its friend requests to a global object (number 4501) that no server process ever created. Astron
  answers a message to a missing object by disconnecting the sender, with error code 117, so tapping "Add friend" dropped the
  player with "An unexpected problem has occurred (error code 117)".
- Every district's AI generates its own friend manager (like its time manager), and the client uses the one it is sent
  (`ToontownStart.py` no longer creates the missing global object). The manager runs the invitation: it checks the invitee is in
  the district, is not the inviter and is not already a friend, passes the invitation on, relays the invitee's answer, adds both
  toons to each other's friends lists when it is yes (limit 50), and tells the inviter.
- **The friends list is filled by the server.** The game has no "get friends list" request on Astron, so the list window had no
  names to show. When a toon enters a district, its AI looks up each friend (name, look, pet, and whether the friend is in this
  district) and sends them to the toon's own client (`setFriendDetails`, a new field in `server/etc/toon.dc`); it is sent again
  when two toons become friends. Friends in the district are told when a friend arrives or leaves (`setFriendOnline`).
- **Friends in other districts, and Go To.** A new UberDOG service, `ToonPresence` (object 4730,
  `toontown/friends/ToonPresence*.py`, listed in `astrond.yml`), knows which toons are playing in every district. Each district's
  AI tells it when a toon arrives, leaves or makes a friend, and it tells that toon's friends in any district (`friendOnline`). It
  also carries the **Go To** questions and answers. In the stock game a client sends those straight to the other toon's object;
  the server drops a client that sends to an object it cannot see (error 117), so Go To to anyone out of view would have
  disconnected the player. The client now sends them to `ToonPresence`, which passes them on, but only between toons who are
  both playing and are friends.
- **Ending a friendship works** (it used to crash the game: the client sent a message type Astron does not have). The client asks
  its own district to drop the friend and tells `ToonPresence`, which tells the friend's device, which asks the friend's district
  to drop the other toon. If the friend is not playing at that moment, they keep the old friend until they remove it themselves.
- Secret friends are not offered (both secret requests answer "not available").
- Only toons in the same district can invite each other, which is also how the invitation works in the game.

### Options

- **Options are remembered in the browser** (`otp/settings/Settings.py`). The game's own options file lived in the browser's
  temporary file system and was gone on every load. In the browser, options are saved in local storage, one set for each sign-in
  name, and come back when that name plays again on that device. (Computers still use `useropt.json`.) They are not stored on the
  server.

### Access

- A brand-new account gets `NO_ACCESS` (set in `server/docker/live.prc`), not stock Open Toontown's `SYSTEM_ADMIN`. Staff are made
  by editing the account in the database (README, step 6).

### Toon colours

- `ToonDNA.py` carries a 39-entry colour table instead of the stock 27, and the allowed-colour set and the default colour lists
  follow it. This file is read by both the server and the client.

### On the phone

- **Districts page** (`toontown/shtiker/ShardPage.py`): tapping a district highlights it and shows a panel with its name,
  population and, if there is one, the invading Cog's head. A **Teleport Here!** button takes you there. A district with an
  invasion has its name in red in the list. The total population is shown at the top.
- **Cog Gallery**: the frame is narrowed so it does not stretch on wide phone screens.
- **Wide phones** (`ToonBase.py`, `ToontownBattleGlobals.py`): the margin cells (the little arrows and name tags at the screen
  edges) are re-laid out when the aspect ratio changes, and the battle camera widens its field of view so the battle fits a very
  wide screen.
- **Fishing** (`DistributedFishingSpot.py`): the board is stretched under the interface, and the jar, bucket and exit button are
  spread out on wide screens without covering the laff meter.
- **Loading screen** (`ToontownLoadingScreen.py`): a sky backdrop sized to any screen, a scroll banner for the tip, and a progress
  bar.
- **Phone chat**: large chat buttons pinned to the screen corner (done while the packs are built, see `web/web/make_ot_packs.py`).
- **Clarabelle's Cattlelog** (`toontown/catalog/CatalogScreen.py`): Clarabelle speaks, the window background is coloured while
  the catalog is open, her TV window shows her room and switchboard, and the hang-up button is pinned to the screen corner.
  Gifting shows a stand-in toon (the server has no "get avatar details" message).
