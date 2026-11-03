# Magic words

Magic words are chat commands for staff. Type one in the chat box and send it like a message. Only accounts with an access level
of `MODERATOR` or higher can use them; the README's step 6 shows how to make your account `SYSTEM_ADMIN`, which can use all of
them. They do not work in the Toontorial.

The words live in `server/toontown/spellbook/MagicWordIndex.py`. Every word also works under its class name (`~SetHP`), and
capitals do not matter.

## Who it affects

| Type | Affects |
|---|---|
| `~hp 50` | yourself |
| `~~hp 50` | the toon whose name tag you last clicked |
| `~~~hp 50` | you and the toon you last clicked |
| `~zonehp 50` | you and every toon in your zone |
| `~serverhp 50` | you and every toon in the district |

You can only use a word on toons with a lower access level than yours.

## Your toon

| Word | Also | Arguments | What it does |
|---|---|---|---|
| `~maxtoon` | `max`, `idkfa` | | Maxes the toon: every gag track, full experience and gags, the biggest gag pouch and task limit, 137 laff, 250 jellybean jar and a full bank, the final task tier, and every Cog suit at its top level. Needs `ADMIN`. |
| `~sethp` | `hp`, `laff`, `setlaff` | laff (-1 to max) | Sets the current laff. 0 or less makes the toon sad, unless it is immortal. |
| `~setmaxhp` | `maxhp`, `maxlaff`, `setmaxlaff` | max laff (15 to 137) | Sets the maximum laff and fills it. |
| `~inventory` | `gags`, `inv` | `restock` or `empty` (default `restock`) | Fills every gag slot, or empties them all (`max`, `all`, `fill` and `clear`, `reset`, `zero` also work). |
| `~setmaxcarry` | `pouch`, `gagpouch`, `gagcapacity` | size (0 to 255) | Sets the gag pouch size. |
| `~givebeans` | `beans`, `jellybeans`, `money` | amount (default: fill both) | Adds jellybeans: the jar fills first, the rest goes to the bank. Added by Glonktown. |
| `~setpinkslips` | `pinkslips`, `fires`, `setfires` | amount (default 255) | Sets the number of pink slips. |
| `~quests` | `quest`, `tasks`, `task`, `toontasks` | `finish` [index] | Finishes all ToonTasks, or only the one at that index (starting at 0). |
| `~globalteleport` | `globaltp`, `tpaccess` | | Unlocks teleporting to every playground. |

## Getting around

| Word | Also | Arguments | What it does |
|---|---|---|---|
| `~teleport` | `tp`, `goto` | place | Teleports to a playground or Cog HQ: `ttc` (Glonktown Central), `dd` (Donald's Dock), `dg` (Daisy Gardens), `mml` (Minnie's Melodyland), `tb` (The Brrrgh), `ddl` (Donald's Dreamland), `gs` (Goofy Speedway), `oz` or `aa` (Chip 'n Dale's Acorn Acres), `gz` (Chip 'n Dale's MiniGolf), `sbhq`, `factory` (outside the Sellbot Factory), `cbhq`, `lbhq`, `bbhq`. |
| `~factory` | | side (`1` for the side entrance, default front) | Starts a Sellbot Factory and takes you in. |
| `~bossbattle` | `boss` | see below | Starts or controls a boss battle. |

`~boss` takes a command:

| Command | What it does |
|---|---|
| `~boss vp`, `~boss cfo`, `~boss cj`, `~boss ceo` | Creates that boss battle and takes you in. Add `0` to start it idle instead (`~boss cfo 0`). Also `~boss create cfo`. |
| `~boss list` [type] | Lists the boss battles running, with their number. |
| `~boss join <number>` | Takes you to a running boss battle. |
| `~boss start` | Starts your boss battle again from the beginning. |
| `~boss stop` | Stops it (the boss idles). |
| `~boss skip` | Skips to the next round, where that boss supports it. |
| `~boss final` | Skips to the final round (also `pie`, `crane`). |
| `~boss kill` | Wins the battle (also `victory`, `finish`). |

## Games

| Word | Also | Arguments | What it does |
|---|---|---|---|
| `~minigame` | `mg` | game | In a playground, takes you to that trolley game; anywhere else, makes it the next one you get. Games: `race`, `cannon`, `tag`, `pattern` (`minnie`, `match`, `matching`), `ring`, `maze`, `tug`, `catch`, `diving`, `target`, `pairing`, `vine`, `ice`, `thief`, `2d`, `photo`, `travel`. `~mg teleport <game> [difficulty]` and `~mg request <game> [difficulty]` choose explicitly and can set a difficulty. |
| `~abortminigame` | `exitgame`, `quitgame`, `skipgame`, `exitminigame`, `quitminigame`, `skipminigame` | | Ends the trolley game you are in. |
| `~skipminigolfhole` | `skiphole`, `skipgolf`, `skipgolfhole` | | Skips the current golf hole. |
| `~abortgolfcourse` | `abortgolf`, `abortminigolf`, `abortcourse`, `leavegolf`, `leavecourse` | | Ends the golf course you are in. |

## Events

| Word | Also | Arguments | What it does |
|---|---|---|---|
| `~fireworks` | `firework` | show [`all`] | Starts a firework show where you are, or in every playground with `all`. Shows: `newyear` (default), `newyears`, `summer`, `combo`, `party`. |

Cog invasions start by themselves; `invasion_minutes` in `gameconfig.json` sets how long they last
([server/docker/README.md](../server/docker/README.md#game-settings-no-rebuild)).

## Staff modes

| Word | Also | Arguments | What it does |
|---|---|---|---|
| `~toggleimmortal` | `immortal`, `invincible`, `invulnerable` | | Cogs can no longer hurt the toon. |
| `~toggleinstantkill` | `instakill`, `instantkill` | | Any gag defeats a Cog at once. |
| `~toggleghost` | `ghost`, `invisible`, `spy` | | Makes the toon invisible to players. |
| `~togglesleep` | `sleep`, `nosleep`, `neversleep`, `insomnia`, `togglesleeping` | | Switches falling asleep when idle on or off. |
| `~togglerun` | `run` | | Much faster running, for yourself. |
| `~toggleoobe` | `oobe` | | Frees the camera from the toon ("out of body experience"), for yourself. |
| `~setgm` | `gm`, `icon`, `gmicon`, `seticon`, `setgmicon` | icon (0 to 3) | Shows a staff icon on the toon's name tag; 1 to 3 pick the icon, 0 removes it. |
