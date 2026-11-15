# Ace Commander for the EMF Tildagon / Spaceagon badge

Notes for picking this project up in a new session. Last updated at the end of the first
working session, 2026-11-12 (build 13); updated 2026-11-13 (build 16: renamed, on a Pi, design
phase 1 built) and again that night (build 22: DEBUG page, missile lock, phase 2), and
2026-11-14 (build 26: phase 3 started, the star system; build 27: docking by hand).

## What this is

A MicroPython app for the 2026 EMF Camp "Spaceagon" badge (Tildagon with the 2026 front
board): a wireframe flight combat game plus a ship viewer, using the ship geometry and stats
of BBC Micro Elite. Brian's constraints: plain MicroPython, **no custom firmware build**.
C or `@micropython.viper` is welcome only if measurements show it would help.

Built from `DESIGN.md`: phase 1 (title screen, saved commander with rank, three levels, new
button layout) and phase 2 (galaxy, local and galactic charts, system data, hyperspace,
fuel, docked screens as tabs, launch tunnel), and the start of phase 3 (build 26: planet,
sun, station, compass, jump drive, automatic docking; build 27: docking by hand; build
30: the market; 31: scooped cargo; 32: bounties, which finishes phase 3), and the start
of phase 4 (build 33: the Equip ship screen; build 36: every item's effect). Not built
yet: the rest of phase 6 (see `DESIGN.md`). Phases 4 and 5 are done, the system
description sentence (build 52) and the disc version's two missions (build 54).

## Files

- `app.py` - **the loading screen** (build 50). The badge's launcher imports
  `<folder>.app` and starts its `__app_export__` (firmware `system/launcher/utils.py`), so
  this file must be `app.py` and stay tiny: it draws at once, imports the other modules one
  by one with a progress bar, then hosts the real app. On a PC (tests) the package's
  `__init__` gives `ace.AceCommander` directly.
- `letters.py` - the name in block letters (rectangles), shared by `title.py` and the
  loading screen; imports nothing.
- `ace.py` - **the real app** (it was `app.py` until build 49; older notes below that say
  `app._dock`, `app.py` and so on mean this file): menu, input (`Pad`), frame loop (`run`),
  LEDs, pause, PERF logging.
- `game.py` - game rules, including the star system (`Space`, `Game.enter`). No badge
  imports, so it runs on a PC.
- `cockpit.py` - flight view, HUD, radar. Built from rectangles (see Speed).
- `viewer.py` - ship viewer. `bench.py` - the title screen's "Speed test".
- `title.py` - title screen: block-letter name from rectangles, tumbling ship, one menu line.
- `commander.py` - the saved commander (level, kills, rank, star system, fuel). Rules only,
  no badge imports. Saved to `commander.json` next to the app (gitignored).
- `galaxy.py` - the 256 star systems, worked out from three seeds. Rules only.
- `chart.py` - the local and galactic charts (imported the first time one is opened).
- `docked.py` - the docked tabs: Status, Market, Local chart, Galactic chart, System data.
- `market.py` - market prices, stock, buying and selling. Rules only, no badge imports.
- `equipment.py` - the Equip ship screen's rules: what is on sale, prices, fitting.
- `describe.py` - the system description sentence ("goat soup"): the original's extended
  tokens from `game_data.py`, put together as DETOK does; also the mission texts and the
  special system sentences. Rules only.
- `missions.py` - the disc version's two missions (Constrictor, Thargoid plans). Rules only.
- `briefing.py` - INCOMING MESSAGE and the mission texts, a screen at a time, on docking.
- `ship_data.py`, `game_data.py` - generated, **gitignored** (see Licensing). 31 ships; the
  galaxy's seeds, name letter pairs, starting place, the market's 17 goods and the 14
  equipment prices. Both must be copied to the badge.
- `tools/import_ships.py`, `tools/import_galaxy.py` - make those two from the Elite source.
- `tools/badge_log.py`, `deploy.bat` - copy to the badge, restart it, save its serial output
  to `badge_log.txt`.
- `tests/` - PC test suite with stand-ins for the badge firmware.

The repo folder must be called `ace_commander`: the tests import the app as that package, and
it installs to `/apps/ace_commander/` on the badge.

## Working with the badge

- **On Brian's Raspberry Pi the badge is plugged in and Claude can reach it:** copy files
  with `mpremote connect auto fs cp ... :/apps/ace_commander/`, `mpremote connect auto reset`,
  and log with `python3 tools/badge_log.py SECONDS PORT` (only one program can hold the port).
  On 2026-11-14 the badge was `/dev/ttyACM1`. Brian has two badges: serial
  `7c4fad337ac00000` (the usual one) and `64e83372252c0000` (build 34 put on it
  2026-11-14 over an older build; it keeps its own `commander.json`). Both run
  MicroPython 1.28; check `/dev/serial/by-id/` to see which is plugged in. To test over the REPL (`mpremote run x.py`),
  `import system.scheduler` first, or importing the app fails with
  `ImportError: can't import name eventbus` (the firmware's eventbus and scheduler import
  each other; at boot the scheduler comes first).
  The rest of this list is the older Windows / cloud-session workflow.
- Claude cannot reach the badge's serial port from its sandbox, and cannot type into a
  terminal by screen control (terminals are click-only). The loop that works: Claude writes
  files into this folder, Brian double-clicks `deploy.bat`, uses the badge, then says so, and
  Claude reads `badge_log.txt`.
- The badge was on **COM13** (`set BADGE_PORT=` at the top of `deploy.bat`).
- `deploy.bat` copies the code files; `deploy.bat all` also copies `ship_data.py`.
- A crashed app prints a traceback to serial, so it lands in `badge_log.txt`.
- All files on the badge must come from the same build. A mismatch between `app.py` and
  `cockpit.py` caused the one crash seen so far.

## Tests

`python tests/run_all.py` from the repo folder (needs `ship_data.py`). `tests/render.py`
draws real frames to `tests/shots/*.png` with Pillow, which is how layout was checked.
`tests/badge_stubs.py` copies the firmware's button matching rules, so joystick-versus-button
logic is tested for real. Also compile with the badge's own compiler, which the firmware
build in `~/Code/tildagon-firmware-builds` leaves behind (v1.28.0, the badge's version; runs
on the Pi without Docker):
`~/Code/tildagon-firmware-builds/work/2026-v2.2.1-rc1-mirror/badge-2024-software/micropython/mpy-cross/build/mpy-cross -march=xtensawin -o /tmp/x.mpy app.py`
for each `.py` file. Don't use `pip install mpy-cross`: it is a newer MicroPython (v1.29).

Nothing here proves behaviour on the badge. Say so when reporting.

## Firmware facts (read from the source, not guessed)

Source: `github.com/emfcamp/badge-2024-software`, folder `modules/`. Brian's own working app
`github.com/Corteil/file_explorer` is a good reference for app structure.

- Apps are packages: `__init__.py`, `app.py`, `tildagon.toml`, `metadata.json`. The app class
  must call `super().__init__()`.
- Buttons A to F are also UP, RIGHT, CONFIRM, DOWN, LEFT, CANCEL (`BUTTON_TYPES`). To tell a
  lettered button from the joystick use `frontboards.common.FRONTBOARD_BUTTON_TYPES["A".."F"]`
  and `events.joystick.JOYSTICK_BUTTON_TYPES["UP"/"DOWN"/"LEFT"/"RIGHT"/"SELECT"]`. The
  joystick is a digital 5-way switch.
- `Buttons.get()` / `.pressed()` search every known button in Python on each call. Polling
  about 25 controls a frame was a large hidden cost; `Pad` in `app.py` listens for
  `ButtonDownEvent` / `ButtonUpEvent` on `system.eventbus` instead.
- Frame loop (`modules/app.py`, `modules/system/scheduler/__init__.py`): the default
  `App.run` awaits `render_update`, which sleeps 50 ms after every update. `AceCommander.run`
  overrides it: sets `scheduler.render_needed`, yields once, continues. It falls back to
  `render_update` if anything raises or the app is not foregrounded.
- LEDs: `tildagonos.leds[1..12]` is the front ring (0 and 13-18 are other LEDs), values
  0-255, then `.write()`. Emit `PatternDisable()` first and `PatternEnable()` after
  (`system.patterndisplay.events`). `tildagonos.set_led_power(True)`.
- IMU: `imu.acc_read()` gives m/s^2. `imu.mag_read()` works on the 2026 board.
- Keyboard: `events.keyboard.KEYBOARD_BUTTONS` (letters, `SPACE`, `ENTER`, arrows...).
- `ctx` draws straight into the framebuffer; `display.end_frame` then sends it to the screen.
- A screen-reader hook prints every changed `ctx.text` string to serial, another reason to
  avoid per-frame text.

## Speed: what was measured on the badge

Speed test (build 10), ms per frame / of which drawing calls:
nothing 73 / 0, clear 80 / 7, 60 short lines 90 / 28, 60 thin lines 90 / 24,
20 long lines 87 / 18, 60 dots 79 / 8.5, 8 bars 79 / 7, 1 text 79 / 12, 6 texts 98 / 33.

So: a filled rectangle is about 0.03 ms, a line about 0.35 ms whatever its length or width,
a piece of text about 4 ms, a full clear about 7 ms.

Flight frame time, with about 11 objects:

| Build | Frame | What changed |
|---|---|---|
| 5-9 | 100-144 ms | first version |
| 11 | 130 ms | HUD rebuilt from rectangles (HUD 50 -> 5 ms), mid-distance ships as markers, 50 ms sleep skipped |
| 12 | 50-70 ms | event-driven input (`Pad`) |

Build 12 `PERF` lines: frame 65, update 15 (rules 14), draw 16.5, objs 11-12, fast 1. With
1-2 objects: frame about 48. So about 33 ms per frame is outside the app (sending the frame
to the screen plus the badge's own tasks) and looks fixed.

**The hitch is garbage collection (build 14, 2026-11-13, firmware v2.2.1-rc1 + PRs).** Build
14 forces no collection and lists the frames that ran 25 ms over the window's average:

| Objects | Average frame | Slow frames per 60 | Each one is over by | Time lost |
|---|---|---|---|---|
| 1-3 | 41 ms | 2 | 60 ms | 5% |
| 5-9 | 49 ms | 4.6 | 60 ms | 9% |
| 10-12 | 55 ms | 6.2 | 60 ms | 11% |

The slow frames are all the same size and their number follows the object count, and
`gc.mem_alloc()` saw-tooths between about 260 KB (live data) and 500 KB. So the badge collects
each time roughly 240 KB of garbage has built up: about 25 KB of garbage a frame with 12
objects. A forced `gc.collect()` took 41 ms in build 13. `gc.threshold()` is -1; the heap is
about 500 KB and `gc.mem_free()` counts memory the heap could still grow into, so "1.5 MB
free" does not mean collections are rare. `gc.mem_alloc()` itself takes 15 ms.

Brian could not feel the hitch in build 14 (he could with build 13's forced collection on
top). So this is a frame-rate cost of up to 11%, not a visible stutter.

**Build 16 in a real flight (2026-11-13, 66 windows):**

| Objects | Average frame | Slow frames per 60 | Each one is over by | Time lost |
|---|---|---|---|---|
| 1-3 | 38 ms | 0.7 | 71 ms | 2% |
| 5-9 | 46 ms | 2.5 | 66 ms | 6% |
| 10+ | 50 ms | 3.3 | 65 ms | 7% |

So collections are about half as frequent as in build 14 and the average frame is 3 to 5 ms
shorter, for the changes below.

**Where the garbage comes from (build 16, measured on the badge).** Every float result on
this port is a new 16-byte heap object; small whole numbers are free. To measure a function,
collect, `gc.disable()`, call it a few times, read `gc.mem_alloc()`, `gc.enable()`. Without
the disable a collection runs part-way and the figure comes out far too small (this fooled
one measurement). With 12 objects close enough to be wireframes, bytes per frame:

| Part | Build 15 | Build 16 | What changed |
|---|---|---|---|
| `cockpit.draw_world` | 28,000 | 700 | vertex, dust and explosion maths in whole numbers; screen positions in whole pixels |
| `cockpit.draw_hud` | 3,600 | 750 | radar blips in whole numbers |
| `Game._rotate` (turning) | 12,500 | 5,300 | positions in quarter units, directions times 16384; dust and explosion dots are whole numbers |
| `Game._think` | 13,400 | 6,400 | a ship re-plans on one frame in three (`THINK_EVERY`), staggered; it moves every frame |
| Whole frame, turning | about 59,000 | about 15,000 | |

Side effects: wireframes land on whole pixels (within a pixel of before); directions drift
by up to 0.35% in the tests, and rocks and canisters are squared up again in turn. Drawing
also got about 25% quicker. A REPL harness on a freshly booted badge has a small heap and
collects every few frames whatever you do, so judge the result from `slow` in the PERF lines
of a real flight, not from a harness.

## Next steps

1. Done: builds 13 and 14 were run and read; see above.
2. Done in build 16: float garbage cut by about three quarters (table above). What is left
   is mostly `_turn` / `_ortho` on the frames a ship re-plans, and storing results back as
   floats in `_rotate`. Going further means keeping object state in whole numbers.
3. Rules cost about 1.2 ms per object. Build 13 skips rotation maths when not turning;
   check what that saved.
4. Then gameplay: balance has only been judged by a crude autopilot in `tests/test_game.py`.
5. `DESIGN.md` has the rest of the game in phases, with all 11 decisions made. **Phase 1 is
   built (build 15) and Brian played it on the badge on 2026-11-13: title screen, new
   commander, rank messages, status, save and continue, and tap / hold D all worked.**
   **Phase 2, first part, is build 20 (2026-11-13): a commander is at a star system with
   fuel; LOCAL CHART in the in-flight menu picks a target; `Game.start_jump()` counts down
   5 s, clears the objects and sets `jumped`; `app._arrive` moves the commander, takes the
   fuel and saves.** Run over the REPL on the badge (not yet played by hand): making the
   galaxy 290 ms once, opening the chart 185 ms the first time, drawing it 14 ms, a change
   of selected system 28 ms (`Galaxy.system` twists the seeds from the start), the arrival
   streaks 11 ms.
   **Build 21 adds arriving docked.** After a jump `Game.arriving` is the number of ships
   to destroy (`max_hostile` for the level); when it reaches 0 no more come, and once none
   are left `dock_t` counts `DOCK_TIME` down and `Game.docked` is set. `app._dock` fills the
   tank (free until there is money to make), saves and shows mode `docked`. CONTINUE and
   NEW COMMANDER go to `docked` too, unless a flight was left part-way; every launch is a
   fresh `Game.reset()`. GAME OVER + C docks a commander where they last arrived. Brian
   asked for REFILL FUEL to stay on the DEBUG page; DOCK NOW is there too.
   **Build 22 finishes phase 2:** docked screens as tabs (`docked.Docked`; joystick
   changes tab, on charts E / B do and C sets `app.target`), the galactic chart
   (`chart.GalChart`), system data, a JUMP: name line in the in-flight menu when the target
   is in range, and a hexagon launch tunnel (`cockpit.draw_tunnel`, mode `launch`,
   `LAUNCH_TIME`). `Galaxy` now caches every system's seeds (1.5 KB), so `system()` no
   longer twists from the start. Measured over the REPL on the badge: Status and System
   data take about 90 ms to draw (all text), the local chart 26 ms, the galactic chart 35 ms
   to draw and 2 to 4 ms per cursor move (52 ms before its search used whole numbers), the
   tunnel 3 to 55 ms a frame. Build 23 (Brian's request): each station has its
   government's colour (`cockpit.station_colour`, eight, warm for anarchy to cool for
   corporate state, no red or white), used for the tunnel's mouth, the DOCKED label, the
   government's name and the LEDs, which pulse per ring (`cockpit.tunnel_glow`), flash full at
   the mouth and fade over the first half second of flight (`app.glow`). Left out: the description sentence ("goat soup"), which
   needs the original's text tables in `game_data.py`.
   **Build 26 starts phase 3: the star system** (2026-11-14). `Game.space` is a `Space`
   (planet and sun as centre + radius, the station an `Obj` of kind "station") for career
   flights; combat practice has none and keeps the waves. They are kept out of `Game.objs`
   and turned in floats (`_rot3`), because their distances (up to about 10^6) are beyond the
   cheap whole numbers `_rotate` uses. `app._enter_space` calls `Game.enter(radius_km,
   station, "launch" / "arrive", government)` on every fresh launch and on arriving.
   Arriving replaces build 21's "clear the ships and you are docked": the first group is
   `pending = max_hostile`, then `_encounters` sends a group every `ENCOUNTER` seconds (build 32 replaced both: see below),
   none in the safe zone. Reaching `DOCK_DIST` of the station sets `Game.docked`
   (docking option C); hitting the planet or sun is `_hurt(1e6)`. The jump drive
   (`JUMP_K`) needs speed up held at full speed, no ship or missile within radar range, and
   being outside the safe zone. New DEBUG cheat: TO THE STATION (`Game.to_station`). Build 31
   adds RELEASE CANISTER (`Game.release_canister`: one 700 ahead, drifting in to be
   scooped); build 32 made the DEBUG page a looping list (see below).
   The speed test has three circle tests. **Measured over the REPL on the badge (real ctx,
   not yet played by hand):** filled disc r20 1.3 ms, r100 7.2 ms; circle outline r20
   2.6 ms, r80 6.2 ms, and 4 to 5 ms for a big one whose edge crosses the screen. Cockpit
   draw (world + HUD): open space with nothing in it 10.3 ms; launch view (planet r about
   70) 17.6; arrived (small planet, station a dot) 14.1; station at 2500 19.4, at 900 21.1.
   Rules per step while turning: 1.05 ms / 480 bytes in open space, 1.9 ms / 2.6 KB in a
   system (the float turning of three bodies and the station's directions); with the jump
   drive on 1.1 ms / 1.1 KB. So the planet outline is the main new cost, up to about 7 ms a
   frame when big; a ring of rectangles would be cheaper if that matters. With the jump
   drive on the stardust is drawn as streaks (`STREAK_MIN`, two steps of `Game.fwd` long);
   Brian asked for them and confirmed they look good (2026-11-14). A real flight in a
   system that day: 36-38 ms a frame with no ships (draw 12.5-14), 38-47 ms with 1-4, one
   or two collections per 60 frames as before, no errors.
   **Build 27: docking by hand** (2026-11-14). `Game.docking` ("A" / "B" / "C", from
   `Commander.docking` via `Game.set_docking` in `app._enter_space`; `Game()` defaults to C
   so old tests keep working). The pause page has DOCKING: AUTHENTIC / ASSISTED / AUTOMATIC
   (C or right goes on, left back; saved straight away). `Game._approach` runs within
   `CAPTURE_DIST` for A and B: you touch the station at `bp.front + PLAYER_R` from its
   centre (`Blueprint.front` is the slot face: 160 Coriolis, 196 Dodo). A docks if you are
   in front of the slot (`SLOT_CONE_A`, 22 deg), flying into it (`HEAD_A`, 26 deg), the slot
   level on screen (`LEVEL_A`, |station roof . screen x| >= cos 30 deg, either way up; the
   station spins at `STATION_SPIN` so you roll with it) and at `DOCK_SPEED` (20) or less. B:
   in the cone (`SLOT_CONE_B`), heading in (`HEAD_B`) and slow, the tractor beam takes over
   ("TRACTOR BEAM"): the station turns its slot to you (`PULL_TURN`) and closes at `PULL`;
   speeding up past `DOCK_SPEED` loses it ("TOO FAST"). Anything else is a crash
   ("STATION HIT" / "TOO FAST"): `STATION_HIT` + 1.5 x speed damage, speed 0, bounced
   `BOUNCE` out (`Game._shift` moves the whole system), 1 s before another hit counts.
   TO THE STATION now also turns the slot to face you (`to_station(dist, slot=True)`).
   Tested on the PC only (tests/test_game.py "docking by hand"; shot 4m_slot_level.png
   shows the slot as a level letterbox when A's roll rule is met).
   **Build 28: the docking scene** (Brian's request after trying build 27, which he said
   ran fine). Flying in (any style) sets app mode `docking` for `DOCK_TIME` (3 s, C skips):
   the launch tunnel the other way round (`cockpit.draw_tunnel(..., inward=True)`,
   `_draw_dock`): the mouth in the station's colour starts `DOCK_START` ahead, the rings
   come at you more and more slowly, and you stop with the bay doors (a dim filled hexagon)
   `DOCK_END` ahead. The LEDs (`cockpit.dock_glow`) rise as the mouth nears, flash going
   through it, pulse for each ring; then `_dock()` as before. DOCK NOW and GAME OVER + C
   skip the scene. Measured on the badge (real ctx, REPL): 14-19 ms a frame to draw.
   **Build 29: every station's tunnel is different** (Brian's requests, after trying
   several looks). `cockpit.Tunnel(system, station)`: every ring is the station's slot, a
   level letterbox that doesn't turn (`SLOT_ASPECT`: Coriolis 3:1, Dodo 2:1, from their
   slot vertices), so the tunnel is four corners with straight long edges. The gaps between
   rings follow one of `TUNNEL_SPACINGS` (even, widening, narrowing, pairs, threes, picked
   from the system's number). At the end the tunnel opens into the docking bay: the same
   shape `BAY_SCALE` (3) times bigger and `BAY_DEPTH` deep, its doors on the far wall
   filled dimly in the station's colour; docking stops at the way into the bay (`DOCK_END`).
   **Ships are parked in the bay**, a fresh random set on each launch and docking
   (`app._pick_tunnel`): `game.parked_ships(gov, tech)` draws 1 to 4 names from pools that
   suit the system (pirate craft where the government is weak, traders, police Vipers where
   it is strong, shuttles below tech 5, Asp / Fer de Lance from tech 10), and
   `Tunnel.park` keeps only ships that fit through the slot at `SHIP_SCALE` (150 ship units
   to a tunnel unit; e.g. the Boa is too tall for a Coriolis but fits a Dodo), one to each
   of `PARK_SPOTS`, resting on the floor, facing in or out a little askew. Until you are in
   the bay only ships seen through its opening are drawn. Launch and docking at one
   station use the same tunnel; the LED pulses follow the real spacing (`_pulse`). Tried
   and dropped at Brian's request: morphing between shapes, hexagon doors, a spinning
   tunnel. At the end of docking the bay stays in view for a random `DOCK_HOLD` (1-2 s).
   `tools/tunnel_sheet.py` draws six stations side by side into
   `tests/shots/tunnels.png`. Measured on the badge (REPL, real ctx): making a tunnel and
   parking 4 ships about 4 ms; drawing 16-25 ms a frame with 4 parked.
   **The station hides the planet behind it** (Brian's request): in `_draw_space`, when
   the station is nearer than the planet's centre and its screen size overlaps the
   planet's outline, `draw_ship(..., solid=True)` fills the station's outline black
   (`_fill_hull`, the convex hull of its projected vertices) before its edges. Costs about
   2 ms on the badge, only while they overlap. Ships don't hide the planet (not asked).
   **Build 30: the market** (phase 3). `tools/import_galaxy.py` now also reads the goods
   table (QQ23: name from each line's comment, base price, economic factor, unit, base
   quantity, mask) into `game_data.GOODS`. `market.py` works prices and stock out the way
   the original does (read from TT151 and GVL in the source, written afresh): price in
   tenths = 4 x ((base + (r AND mask) + economy x factor) mod 256); stock = (quantity +
   (r AND mask) - economy x factor) mod 256, none if >= 128, then mod 64; no alien items.
   r is a random byte picked when a commander first docks in a system after arriving
   (`app._arrive` clears `Commander.market`, `app._dock` makes a new one with
   `market.new`), saved with the commander, so the stock you change stays until you jump.
   Prices don't change with trading. The hold takes 20 t of the first 13 goods; gold,
   platinum, gem-stones and alien items don't use it, 200 of each at most. The commander
   now keeps `cash` in tenths of a credit (saved as `credits` for old saves), `cargo` (17)
   and `hold`; save version 3. Market tab (second): joystick up / down picks a good (6
   rows, scrolls), C buys one and D sells one, all repeating when held (`app._repeat`,
   `REPEAT_WAIT`, `REPEAT_EVERY`); the reason a trade fails shows for 1.5 s. Trades are
   saved on launching and on going to the title. `cockpit.text` takes `align` (-1 left,
   1 right). Measured on the badge (REPL, real ctx): making the market 40 ms, drawing the
   tab 115 ms (all text, every frame, so held buttons repeat about 6 times a second), a
   buy 0.7 ms. Fuel is still free on docking (the equipment screen comes in phase 4).
   Illegal goods (slaves, narcotics, firearms) are sold like the rest until legal status
   exists (phase 5).
   **Build 31: scooped cargo into the hold, and green LEDs in the safe zone.** In a career
   flight `Game.scoop` is `app._scoop` (`market.scoop`): a scooped canister holds a random
   one of the first `SCOOP_GOODS` (8) goods, food to computers, as in the original (read
   from the main flight loop, part 8); it goes into the commander's hold and its name is
   shown, or with no room it is lost ("HOLD FULL", a small explosion, no damage). In
   combat practice (Brian's request) a canister is a pick-up instead (`Game._pickup`):
   it recharges the shields to full, and with chance `PICKUP_MISSILE` (0.5) holds a
   missile too, up to `MAX_MISSILES` (4). Scooping is still free and from any side: needing fuel
   scoops and the canister below you come with the equipment (phase 4). Being destroyed
   loses the cargo (cleared before the game-over save). The in-flight status page shows
   the hold. In the station's safe zone (`Space.safe`) the LEDs are steady green
   (`SAFE_GREEN`, 60 of 255); a hit's red flash and the station colour fading after launch
   come first, and paused they are off.
   **Build 32: bounties.** `Game._kill` adds the blueprint's `bounty` (tenths of a credit,
   from the ship data; asteroids and boulders have small ones) to `Game.bounty`, and
   `app._bank` pays it into `Commander.cash` as it banks kills (`banked_cash`), showing
   the new cash for 1.5 s as the original does (a new rank shows instead, and nothing
   overwrites the hyperspace countdown). The original pays only when no other message is
   showing; this pays always. Combat practice pays nothing. The in-flight status page
   shows hold and cash. Tests read bounty values from the ship data rather than writing
   Elite's numbers into the public repo.
   **Also in build 32, encounters and the safe zone as in Elite** (Brian's request; read
   from the main game loop, parts 3 and 4, and the space station spawning in the main
   flight loop). The safe zone is `SAFE_K` (2) planet radii round the station
   (`Space.safe_r`; Elite's is a box of 2 radii, all its planets one size), replacing the
   fixed `SAFE_DIST`. Outside it, once the last ships have gone, every `ENCOUNTER_EVERY`
   (20) s a roll (`Game._roll`): certain in an anarchy, else `PIRATE_ROLL` (47%) and a
   number 0-7 at least the government, so a corporate state about 6%. Then a lone bounty
   hunter (`HUNTER_CHANCE`, 39%: `HUNTERS`) or a pack of 1 to `PACK_MOST` (4) `PIRATES`,
   capped by the level's `max_hostile`, small types more likely (two random bytes ANDed);
   the next rolls are skipped, one per extra ship (Elite's EV). Differences: Elite rolls
   whatever is around; this waits for the last group to go, because every ship here is
   hostile (no traders or police until phase 5). Arriving from hyperspace brings an ambush
   of `max_hostile` pirates only in an anarchy or feudal system (`AMBUSH_GOV`). Measured
   in the PC test: 10 minutes outside the safe zone, 23 pirates in an anarchy, 4 in a
   corporate state.
   **Waves are for combat practice only** (Brian's request): in a commander's flight no
   "WAVE" message, no wave and score on the HUD, no free missile per wave, no NEXT WAVE
   cheat.
   **DEBUG page and bay windows** (build 32, Brian's requests): the frame time counter is
   a DEBUG switch, FRAME TIME: ON / OFF (`app.show_ms`, starting from `SHOW_FRAME_TIME`).
   The DEBUG page shows `DEBUG_ROWS` (7) lines in size 14, the chosen one in the middle and
   the list going round above and below it. The docking bay has `BAY_WINDOWS` (3) lit
   windows high on each side wall, white frames only (`cockpit._draw_windows`, `WINDOW_Y`,
   `WINDOW_LEN`, `WINDOW_FRAME`), drawn behind the parked ships and, from the tunnel,
   only when seen through the bay's opening. Bay scene on the badge: 17-30 ms a frame.
   **Build 33 starts phase 4: the Equip ship tab** (third, after Market). `import_galaxy.py`
   also reads the equipment price list (PRXS: name from each line's comment, price in
   tenths) into `game_data.EQUIPMENT`. `equipment.py` (read from EQSHP, written afresh):
   a station sells the first (shown tech level + 2) items, all 14 from tech 10; fuel is
   2 Cr a light year and fills the tank; missiles up to 4; one of everything else ("ALREADY
   FITTED"); a new laser refunds the old one's price. The commander keeps `missiles`
   (a new one starts with 3, as in the original), `laser` and `extras` (names from
   `equipment.EXTRAS`); save version 4. **Docking no longer refuels for free** (unless
   game_data.py has no equipment). Each fresh career flight is fitted from the commander
   (`app._fit`): missiles (fired ones are gone: `_bank` copies them back), laser
   (`Game.set_laser`, `game.LASERS`: beam twice the rate and hotter, military 1.5x the
   damage too, mining = pulse until mining exists), the energy unit (`ENERGY_UNIT`, twice
   the recharge) and fuel scoops: in a career flight a canister is scooped only with
   scoops and passing below you (`o.y < 0`), as in the original, else it is hit; combat
   practice always scoops. Shown but not sold yet ("soon", `equipment.SOON`): ECM, escape
   pod, energy bomb, docking computer, galactic hyperdrive, mining laser. Joystick picks,
   C buys. The tab draws in about 109 ms on the badge.
   **DEBUG additions** (Brian's requests): +1000 CR (career), and SHIP CONFIG, a page that
   changes the ship at once, in the flight and for the commander: laser (C cycles), missiles
   (0-4), energy unit; in a career also cargo bay (20 / 35 t) and fuel scoops. Add each
   new item there as its effect is built.
   **Being destroyed works as in the original** (build 35, Brian's choice on 2026-11-15,
   replacing build 34's "start again at the last station, keeping everything but the
   cargo"). The commander is saved **only when docked** (`app._write`: on docking, on
   leaving the docked screens for the title or a launch, and a new commander), as the
   original could save only at a station; arriving from hyperspace and quitting a flight to
   the title no longer save. `app.saved` keeps a JSON copy of the last save. On game over
   in a career `app._restore` puts the commander back to that copy, so the kills, bounties,
   cargo, missiles used, fuel and system since the last dock are all lost, and sets
   `banked` / `banked_cash` and `Game.missiles` so the dead flight banks nothing more. C
   ("back to last save") docks there. Changing the docking style mid-flight writes only
   that setting into the save (`app._write_setting`). A badge restart mid-flight also goes
   back to the last dock. Starting a NEW COMMANDER no longer banks a flight the last
   commander left part-way (it set `career` False first). Still possible: quit a flight to
   the title, play combat practice, then CONTINUE docks the commander wherever they were,
   with the flight's progress. `Commander.docked_at` is still saved but no longer used.
   The escape pod (build 36) saves you from this: per the disc source's ESCAPE routine
   it loses the cargo, uses up the pod, gives a full tank and docks you, and docking saves
   the rest of the flight (kills, bounties). Legal status doesn't exist yet; what the
   original does to credits and other equipment is not checked yet.
   **Build 34: sun skimming** (Brian's request; main flight loop part 15). `Game._sun`:
   cabin temperature = 285 - `SUN_HEAT` x (distance / sun radius)^2, at least 30; at
   `SCOOP_TEMP` (224) or more with fuel scoops, every `SUN_CHECK` s `Game.refuel`
   (`app._refuel`) takes speed // 8 tenths of a LY ("FUEL SCOOPS ON"). CT and AL gauges
   at the top of the HUD only near the sun (`cockpit._sun_gauges`), with a FU fuel bar
   under them (`Game.fuel`, copied from the commander; red below a quarter); LEDs orange to red
   with heat (16 steps), yellow pulses while scooping. The jump drive is off near the
   sun. DEBUG: TO THE SUN (`Game.to_sun`) and FUEL TO 1/4 (career: 1.7 LY). Hyperspace has no distance limit, as in
   Elite (only not docked or mid-countdown). Then (Brian: the gauges seemed stuck, as
   the sun was twice the planet's size and crossing its heat took a minute): the sun is
   now the planet's size (`SUN_SIZE` 1.0, as in Elite, whose planet and sun share one
   radius); AL is full where the cabin starts to warm and empty at the surface, worked
   out from `SUN_HEAT` so it fits every sun (`cockpit.SUN_GAUGE_ALT`); CT is green when
   cool, through yellow and orange to red at the scooping band (`ct_colour`,
   `CT_COLOURS`); TO THE SUN starts at the edge of the heat heading in (`to_sun(1.15,
   1.6)`: about 18 s at full speed to the band). CT is Elite's cabin temperature, a raw
   0-255 value with no units (30 deep space, 255 fatal in the original).
   Then (Brian): a planet behind the sun was drawn as a black disc over it, because the
   "planet in front of the sun" fill never checked which was nearer; `_draw_space` now
   draws whichever is nearer last (the sun hides a planet behind it). Each system's sun
   has one of `cockpit.SUN_COLOURS` (red, orange, yellow, white, blue-white), from the
   system's number (`Space.sun`, `Game.enter(..., sun)`). Messages and the sun gauges
   have a dark band behind them so they read against the sun.
   Each system's planet is a filled disc with a brighter outline, in one of
   `cockpit.PLANET_COLOURS` (ocean blue, green, desert, red, grey, purple, teal; `Space.planet`,
   `Game.enter(..., planet)`), so a planet in front of the sun hides it in its own colour.
   The stardust is now drawn after the planet and sun (it is close to you). Measured on
   the badge: draw_world 13 ms with a small planet, 19 ms in the launch view, 25 ms with
   a planet of radius about 200 px.
   **Build 36: every item of equipment works** (`equipment.SOON` is empty; 2026-11-15).
   ECM (`Game.ecm`): an enemy missile within `ECM_RANGE` (2500) makes `_ecm` destroy every
   enemy missile, costs `ECM_COST` (10) shield, says "ECM" and flashes the LEDs violet.
   Energy bomb (`Game.bombs`, B in flight): `energy_bomb()` kills every ship, missile and
   rock within `BOMB_RANGE` (canisters are spared), counts the kills, flashes the screen and
   LEDs white, and the app takes "bomb" off the commander. Escape pod (`Game.pod`): dying
   sets `Game.ejected` ("ESCAPE POD" box instead of GAME OVER); the app empties the hold,
   removes the pod, fills the tank (as in the original) and after `EJECT_TIME` (3 s, C skips)
   docks you at the system you were in, and that docking saves the flight's kills and
   bounties (without a pod, `_restore` goes back to the last save as in build 35). An
   energy bomb or galactic hyperdrive used in a flight that ends in death without a pod
   comes back with the last save, as everything else does. Docking computer (`Game.computer`):
   in-flight menu DOCKING COMPUTER while in the safe zone, DOCK COMPUTER OFF while on;
   `Game._autopilot` rolls the station over the crosshair, pitches onto it, flies at full
   speed (8x beyond `AUTO_FAST`) and slows in `AUTO_SLOW`, and docks you within the
   station's front + 340 whatever the docking style; stick, throttle, fire or missile
   switch it off. 12 to 17 s from anywhere in the safe zone; on the badge 1.9 ms a step.
   Galactic hyperdrive: in-flight menu GALACTIC JUMP, the usual countdown with
   `jump_to = ("galaxy", 0)`; `_arrive` adds 1 to `Commander.galaxy` (0-7, saved), uses
   the drive up, remakes `app.galaxy` from `galaxy.seeds_for` (each seed byte rotated left,
   as in the original; 62 ms on the badge) and arrives at the system nearest (96, 96)
   (`GAL_ARRIVE`), no fuel used, `docked_at` cleared. Mining laser: a rock it destroys
   breaks into SPLINTERs (asteroid 2-3, boulder 1-2; `Game._splinters`), "can" objects with
   `Obj.good = MINERALS`, which scoop as minerals; its damage is 15 (pulse 12). SHIP CONFIG
   has a switch for each.
   **Build 37 (Brian's requests, 2026-11-15):** the escape pod's screen times out after
   `EJECT_TIME` into the docking scene (`app._fly_in`, shared with flying in). The docking
   computer lines up before going in, as the original's does (`Game._autopilot`,
   `auto_phase`): 0, from beside or behind the station, out to a point to the side of it; 1,
   out to `AUTO_LINE` (2500) + front straight out from the slot; 2, turn onto the station
   and fly in at 0.7 x `DOCK_SPEED`, rolling to match the slot (`auto_level`) within
   `AUTO_LEVEL` (1000) of it; it docks only in phase 2, within front + 100. 60 random starts in
   the PC sim all arrive inside docking A's cone and level, never within 400 of the back of
   the station; the worst took 29 s. On the badge, from behind with the slot facing away:
   23.5 s game time, 3.1 ms a step. DEBUG has LEVEL (EASY / NORMAL / HARD, C goes round):
   the enemies at once and, in a career, the commander's level and rank thresholds, written
   into the save (`_write_setting`) so a death doesn't undo it.
   **Build 38 (Brian, 2026-11-15):** the docking computer said OFF as soon as it was chosen,
   because the C that chose it was still held on the next frames and counted as firing.
   Now only a fresh press of a flight control (`app._took_controls`: joystick, C, D, E, F,
   keys; never tilt) hands back control. Its state (`autodock`, `auto_phase`,
   `auto_level`) is cleared on docking (`app._dock`, so DOCK NOW too), on a hyperspace jump
   and on entering a system. While it flies, the view is from behind and above your ship
   (`cockpit.draw_world`: everything is shifted by `CHASE_UP` / `CHASE_BACK` for the draw and
   back, and a Cobra Mk III is drawn in cyan, banking with `Game.auto_stick`); no crosshair.
   **Build 39 (Brian):** the lasers fired on leaving a menu and on launching, for the same
   reason (C still held). `app.fire_lock` is set by `_resume` and `_start_flight`; while it
   is set, fire is ignored until C (and F / SPACE on a keyboard) is let go.
   Copying to the badge: twice on 2026-11-15 the badge rebooted part-way through copying
   `app.py`; `mpremote connect PORT resume fs cp ...` (no soft reset first) then worked.
   **Build 40 (Brian):** your ship is shown in the launch and docking tunnels, seen from
   behind: `Tunnel.fly(bp)` (set in `app._pick_tunnel`, a Cobra Mk III if it fits the slot)
   and `cockpit._draw_me`, `ME_AHEAD` (2.0) tunnel units ahead of the view, `ME_LOW` below
   the slot's middle, cyan, filled black inside. Docking ends with it in the bay between the
   parked ships. At 1.4 ahead it looked wider than the tunnel further on.
   **Build 41 (Brian):** take-off and landing in the tunnel scenes: on launch your ship
   rises off the bay floor (where the parked ships stand) over the first `ME_LIFT` of the
   scene while the view closes in, then flies out; on docking it settles onto the floor
   over the last `ME_LAND` (`cockpit._draw_me(ctx, tun, ahead, down)`, `_ease`). A **Repair
   Shop** docked tab (after Equip ship) repaints your ship: `cockpit.SHIP_COLOURS` (8),
   `docked.PAINT_PRICE` 10.0 Cr, saved as `Commander.colour`, used in the tunnels
   (`Tunnel.fly(bp, rgb)`) and the docking computer's view (`Game.ship_rgb`). Brian asked
   for it to be optional for now: shown only when DEBUG's REPAIR SHOP is ON
   (`app.repair_shop`, not saved, applies from the next docking). Ship types are written
   up as a future phase 6 extra in `DESIGN.md`, not built.
   **Build 42 starts phase 5: traders, police and legal status** (2026-11-15; Brian had
   play-tested every build to 41 and was happy). `Game.legal` 0-255 (the original's FIST;
   `legal_name`: CLEAN 0, OFFENDER 1-49, FUGITIVE 50+), saved as `Commander.legal`, copied
   game to commander in `app._bank`, set from it in `_fit`. Launching with illegal goods
   (`ILLEGAL`: slaves and narcotics 2 a tonne, firearms 1) raises it to at least their
   weight (`Game.illegal_cargo`). The first hit on a trader adds `HIT_TRADER` (16), killing
   one `KILL_TRADER` (16) more; firing on the police or the station (`_hit_station`: a shot
   that hits nothing else with the station in the crosshair) makes you a fugitive
   (`_crime`, `_provoke`). Each jump halves it (`app._arrive`); the escape pod clears it;
   dying without one goes back to the saved value. Ships have `Obj.role` ("pirate",
   "trader", "police") and two new states, "trade" and "patrol", that leave you alone;
   only "attack" / "break" count as hostile for encounters. `Game._traffic` (called from
   `_encounters` before the safe-zone check, so in the safe zone too): every
   `TRADER_EVERY` (12 s), with fewer than 2 traders, one of `TRADERS` (Cobra Mk III,
   Python, Boa, Anaconda, Moray) turns up with chance 0.45 (0.8 in the safe zone) facing the
   station; it steers there and docks (vanishes) on reaching it; fired on, it attacks if
   it has a laser, else flees; no bounty. Every `POLICE_EVERY` (6 s) in the safe zone,
   with fewer than 3 police: a Viper hunting you always if a fugitive, with chance
   legal / 64 if an offender, else now and then a patrol (`PATROL_CHANCE`); they launch
   out of the slot when the station is within 8,400, else arrive like other ships; a patrol
   turns on a fugitive. Radar: pirates and attackers red, police blue (`POLICE_BLUE`),
   traders white. Status pages show the legal status. DEBUG: ADD A TRADER, ADD POLICE,
   LEGAL (CLEAN / OFFENDER / FUGITIVE), career only. Tests: `tests/test_traffic.py`. On the
   badge: 6.7 ms a step with three police and a trader.
   **Build 43 (Brian):** bounty hunters (the encounter rolls' lone `HUNTERS`, now
   `Obj.role` "hunter", `group_role`) attack offenders and fugitives and fly by the clean
   (state "patrol", turning on you if you become an offender); firing on one is a crime
   like a trader (`HIT_TRADER`), killing one pays no bounty. Pirates prey on traders:
   `Game._pick_prey` picks the nearest trader that is nearer the pirate than you are and
   within `PREY_RANGE` (6,000); the pirate steers and fires at it (50% hits, the trader
   flees), and a trader it destroys spills its cargo (`_spill`) with no kill, bounty or
   crime for anyone (`_kill(..., credit=False)`). Hitting a pirate turns it back on you.
   DEBUG: ADD A HUNTER. Police numbers (Brian asked): no set number per station; at most
   `POLICE_MOST` (3) about at once, a new one possible every `POLICE_EVERY` (6 s), so
   destroyed ones are replaced without end. On the badge: 6.9 ms a step with two traders,
   a hunter and three pirates. Not built yet from phase 5: Thargoids, and legal status
   changing the market or bounties.
   **Build 44: traffic and legal status as the original** (Brian: "go fully original",
   after reading `~/Code/elite-source-code-bbc-micro-disc`, `elite-source-flight.asm`).
   This replaces the build 42/43 rules above where they differ. Legal status (FIST)
   changes only by ORing in contraband on launch (`game.bad`, `illegal_cargo`; the app
   also keeps `Game.bad` current in `_bank`), ORing in `KILL_COP` (64) for destroying a
   police ship, halving on each jump (SOLAR), and clearing with the escape pod or the
   galactic hyperdrive. Firing on a trader (innocent) or the station makes the station
   hostile (`Game.anger_station`, `Space.hostile`; ANGRY / AN2), not your record worse. A
   hostile station refuses docking, checked before anything else on touching it
   (`_refused`, ISDK check 1): at `DEATH_SPEED` (5) or more you are killed, slower a 5
   damage dent, speed 1 and a bounce; the docking computer flies you in to the same end
   (the original's goes through the same checks); it launches police after you
   (`STATION_COPS` 4 at most, `STATION_COP_CHANCE` a second; TACTICS TN5) and no shuttles,
   until you leave. Otherwise the station launches a Shuttle or Transporter now and then
   (`SHUTTLE_CHANCE` a second, one at a time, making for the planet). Outside the safe zone,
   each `ENCOUNTER_EVERY` tick (`Game._tick`, main game loop parts 2 to 4): 35/256 something
   harmless (half the time a trader, making for the station or the planet: `Obj.dest`);
   else a police Viper with chance (2 x BAD, ORed with legal status if police are about)
   / 256; then, with no police about, the pirate / hunter roll (still only with no hostile
   ships about, as before). Nothing turns up in the safe zone, and a pirate that follows
   you in becomes "patrol" for good (TN3). Police and hunters attack at `HUNT_LEGAL` (40)
   or more (TN1; Vipers are hunters in the original's flags), else patrol; firing on any
   ship makes it attack you. Bounties are every ship's blueprint bounty (the police and
   most traders: 0). Kept although not in the original, as Brian asked: pirates preying
   on traders. DEBUG: ANGER STATION.
   **Build 45 (Brian):** a hostile station's tractor beam (docking B) no longer takes hold,
   and lets go if the station turns; the docking computer won't start at a hostile station
   ("STATION HOSTILE") and switches off if it turns (not as the original, whose computer
   flew you in to a refused docking). Leaving the safe zone ends the lockdown (`_measure`):
   the original drops the station from the local bubble outside it (the sun takes its slot)
   and makes a new, friendly one on the way back in (NWSPS). Police already launched stay.
   **Build 46 (Brian):** in the docking computer's view the station is always a wireframe
   (`draw_ship` with `wire_min` 0 never falls back to a dot or marker), and never smaller
   than `CHASE_STATION_MIN` (12 px radius): a far one is drawn as if nearer along the same
   line of sight, then put back (`_draw_space(ctx, sp, wire)`). The cockpit view is as before.
   **Build 47 (Brian: a ship coming out of the station hit him on the run in):** a friendly
   station launches no shuttle while the docking computer flies or you are within
   `SLOT_CLEAR` (6,000) in front of its slot, inside `SLOT_CLEAR_CONE` of its axis
   (`Game._slot_clear`); a hostile station's police still launch. A ship that isn't
   attacking you ("trade" / "patrol") dodges sideways out of your line of travel when it is
   within `AVOID_AHEAD` (3,000) ahead and `AVOID_SIDE` of your path, or within `AVOID_DIST`
   heading your way (turning straight away put it back down your path). 40 docking-computer
   runs from random directions with a shuttle already coming out: no hits, all docked.
   **Build 48 (Brian):** the station is drawn to scale in the docking computer's view again
   (build 46's 12 px minimum is gone); it stays a wireframe at any distance, never a dot or
   marker. What launches from a station: a friendly one only Shuttles and Transporters, a
   hostile one only police Vipers, as in the disc original (TACTICS for the station).
   **Build 49: witchspace and Thargoids, and a loading screen** (2026-11-15). Loading:
   the first start showed nothing for about 10 s because MicroPython compiles every module
   from source (measured on the badge: ship_data 0.8 s, game 1.1 s, cockpit 0.65 s, app
   about 1.3 s). `loader.py` (a few KB) draws at once (0.2 s) and imports `STEPS` one at a
   time, redrawing a progress bar between them (about 6.9 s in all over the REPL), then makes
   `app.AceCommander(host=self)` and runs it. The real app sends its button handlers
   (`Pad(self.host)`), `app_is_foregrounded` and `minimise` through the host, the only object
   the scheduler knows. If a module fails to import the screen says LOAD FAILED and why.
   Witchspace (MJP, GTHG, TACTICS, read from the disc source): each normal jump has a
   `MISJUMP_ODDS` (3/256) chance (DEBUG: MIS-JUMP NEXT, like the original's CTRL) of
   `app._arrive` using the fuel but calling `Game.witchspace()` instead: `Space.witch`, no
   station, planet and sun put 1e9 away, 3 stardust specks (`WITCH_DUST`), `THARGOIDS` (4)
   Thargoids each with a Thargon (role "thargoid"), no other spawns, no jump drive, no
   compass, no legal-status halving. `app.witch` is your chart position, the target's x
   and its y XOR 31; `c.system` stays the system you left. You leave by hyperspace from
   there (`Galaxy.distance_xy`, `chart.Chart(..., at=)`, `_jump_ok`); arriving clears it. A
   Thargoid launches a Thargon in place of a missile, only below half energy; a Thargon
   with no Thargoid left drifts (state "drift", quarter speed, harmless); any Thargon
   scooped from below with fuel scoops is `ALIEN_ITEMS`. The escape pod is no help there
   (GAME OVER, back to the save). Status page says WITCHSPACE. On the badge: 6.3 ms a step
   with eight Thargoid ships. Also: the galactic chart shows the right galaxy number.
   Tests: `tests/test_witchspace.py`, `tests/test_loader.py`.
   **Build 50 (Brian: no loading screen on the badge):** the launcher imports
   `<folder>.app` directly, not the package's class, so build 49's `loader.py` was never
   used. The loader is now `app.py` and the real app `ace.py`; `__init__.py` imports nothing
   on the badge. Checked the launcher's way on the badge: the loading screen is ready in
   0.28 s, the game in 6.7 s. Old `loader.py` removed from the badge.
   **Build 51 (Brian):** the loading screen matches the title screen: the name in the same
   yellow and white block letters in the same place (`letters.draw_name`, which `title.py`
   uses too; the loader imports `letters` before its first frame), and LOADING in green
   where the menu line will be.
   **Build 52: the system description sentence, and D for system data on the charts**
   (Brian). `tools/import_galaxy.py` also reads the extended tokens (TKN1, the ECHR / ETOK /
   ETWO / ERND / EJMP macros, EOR VE removed), the random-choice table (MTIN) and the
   two-letter tokens (TKN2, followed in memory by QQ16, which tokens from 228 and MT18's
   made-up names read) into `game_data.DESC_TOKENS` (only the 192 tokens reachable from
   token 5 and 153), `DESC_MTIN`, `DESC_PAIRS`; game_data.py is now 6.6 KB. `describe.py`
   follows PDESC / DETOK / DETOK2 / DTS / DASC: RAND seeded with the system's s1 and s2,
   DORND with the carry clear going in (as Ian Bell's reading; it gives the classic Lave
   line word for word), jump codes 1, 2, 3 (name), 13 (lower case), 17 (name + "ian",
   a final vowel dropped), 18 (1 to 4 random pairs from TKN2+2), 19 (single cap); `?` in
   made-up names is skipped; the mission-only RUTOK sentences are left out. `docked.system_page`
   draws System data, tighter, with the sentence wrapped below in cyan (`DESC_Y`,
   `DESC_WIDTHS`), for the tab and for D on the in-flight local chart (`fsub` "data",
   `ace._draw_data`; C, D or F go back). D on the docked charts opens System data for the
   selected system without changing the target (`Docked.show`). Charts say "D: DATA". On
   the badge: a description takes 11-15 ms (cached for the page). Tests: `tests/test_describe.py`.
   **Build 53 (Brian):** D on the System data tab goes back to the chart tab you came from
   (`Docked.chart_tab`, the last chart opened; the local chart if none), with the cursor on
   the system you were looking at (`Docked.go(tab, sel)`, `back_to_chart`).
   **Build 54: the disc version's two missions** (2026-11-15), as DOENTRY, BRIEF,
   DEBRIEF, BRIEF2, BRIEF3, DEBRIEF2, THERE, PDESC and the spawning code read from the disc
   source. `Commander.mission` is the original's TP byte (saved as "mission"); the rules
   are in `missions.py`, checked on every docking (`ace._mission_news`, after `_dock`
   saves; it saves again if a mission moves on). Mission 1: docked in galaxy 1 or 2 with
   256 kills (`KILLS_1`, divided by the level's `RANK_DIVISOR` like the ranks: EASY 51,
   NORMAL 128, HARD 256) starts it; at Orarra (galaxy 2, 144,33) the encounter roll's lone
   bounty hunter (`Game._roll`, `Game.hunt`) is the Constrictor (`role` "constrictor",
   `Obj.ecm`) if none is about, and every lone hunter there attacks (`Game.orarra`). Only
   the military laser hurts it, at `CONSTRICTOR_LASER` (1/4); its ECM destroys your
   missiles within `ECM_RANGE`; the energy bomb kills it, as in the original. Killing it
   sets `Game.got_constrictor`, which `_bank` turns into TP bit 1; the next docking
   anywhere pays 5000 Cr and 256 kills (scaled). Mission 2: mission 1 done, galaxy 3,
   1280 kills: go to Ceerdi (215,84), get the plans, take them to Birera (63,72); with the
   plans (`Game.plans`) each encounter tick brings a Thargoid with chance
   `PLANS_THARGOID` (56/256). Reward: 256 kills and the naval energy unit
   (`extras` "navy", replacing "energy"; `NAVY_UNIT` 3x recharge against 2x;
   `equipment.have` counts it as an energy unit). Orarra is a democracy, so the hunter
   turns up rarely (as in the original): about 2% of the 20 s ticks.
   Texts: `import_galaxy.py` also reads tokens 10, 11, 15, 216-223 and what they reach,
   the two standard tokens they print (TOKN 117, 108, from the comments in
   `elite-text-tokens.asm`), RUTOK and RUPLA / RUGAL into `DESC_TOKENS`, `DESC_RUTOK`,
   `DESC_RU` (game_data.py 11.9 KB). `describe.mission_pages` handles the extra jump codes
   (4 name, 5/6 standard token in Sentence Case, 8, 9/22/24/25 screen breaks, 12
   paragraph, 23/29 lower case, 27 captain, 28 the Constrictor's trail) and gives screens
   of paragraphs; `briefing.Briefing` shows INCOMING MESSAGE 2 s, then lays them out for
   the round screen (`briefing.layout`, `_width`), the Constrictor turning above mission
   1's briefing; C next, F skip (mode "brief"). The commander's name is the badge's
   Name setting (`settings.get("name")`), else "Jameson" (`ace.DEFAULT_NAME`). The special
   sentences show on the docked System data tab for the system you are at
   (`system_page(..., cmdr)`): Teorge, Arredi, Anreer always, the rest only while
   mission 1 is under way. Words come out as the source prints them in lower case
   (e.g. "looked bound for arexe"): DTS capitalises only after {single cap}.
   DEBUG: ADD THE CONSTRICTOR, MISSION: stage (the next of `missions.STAGES`, raising
   kills to what the next mission needs; written into the save), TO MISSION SYSTEM
   (to the stage's galaxy and system, arriving as from hyperspace). On the badge (REPL):
   making a briefing 40-190 ms, a special sentence 13 ms. Tests: `tests/test_missions.py`.
   Not yet played by hand.
   Then (Brian: text too small to read; then "use the joystick to scroll the text"): the
   message is one column of size 13 text (`briefing.SIZE`, was 10), `WIDTH` 22 characters
   a line so every line fits anywhere in the view (`VIEW_TOP` / `VIEW_BOTTOM`, +-66),
   with the original's screens run together (`PAGE_GAP`). Joystick up / down (held)
   scrolls at `SCROLL_SPEED` (only the joystick on the new front board, not A / D); C
   pages down and at the end goes on; F skips. Grey bars show more above / below. The
   Constrictor sits at the top of mission 1's column and goes once scrolled near the top.
   Then (Brian): the Constrictor turns up after `missions.QUICK_WAIT` (120 s) outside
   Orarra's safe zone while you hunt it (`Game.con_wait`, `con_t`, reset on entering a
   system; one at a time; the original's roll still applies too). Settings page:
   CONSTRICTOR: 2 MIN / ORIGINAL (`Commander.quick_con`, saved,
   default 2 MIN; ORIGINAL leaves only the roll). SHIP CONFIG (DEBUG) has NAVY ENERGY
   UNIT: ON / OFF, which takes the place of the usual unit (and ENERGY UNIT the reverse).
   Then (Brian): the in-flight PAUSE MENU is now SETTINGS (`fsub` "settings"): STEER,
   and with a commander DOCKING and CONSTRICTOR (always shown). QUIT TO TITLE moved to the
   top in-flight menu, after SETTINGS.
   Then (Brian: "add an option screen"): OPTIONS on the title screen (mode "options",
   `_update_options`, `_draw_options`, `omenu`) shows the same lines as the in-flight
   Settings, from one list (`_settings(cmdr)`, changed by `_change(item, left)`): STEER,
   with a commander DOCKING and CONSTRICTOR (written into the save), and LEDS: ON / OFF
   (`use_leds`, replacing the fixed `USE_LEDS`, which is now only the default). Steering
   and LEDs are kept in `options.json` beside the save (`options_path()`, gitignored);
   the test stubs delete it on each `install()`.
   Then (Brian): an OPTIONS docked tab too, the last (`docked.TABS`; `Docked(...,
   options=(items function, change function))`, given `_settings(True)` and `_change` by
   `_dock`; also with no game_data, after Status). Joystick up / down picks, C changes
   (left / right still change tab, so DOCKING only goes forward there).
   Then (Brian, option 2): DEBUG is a sub-menu of Settings / Options, no longer on the
   top in-flight menu, in groups (`DEBUG_GROUPS`: SHIP, SPAWN, TRAVEL, COMMANDER,
   DISPLAY). In flight: Settings > DEBUG (fsub "debug", the groups, title with the build)
   > a group (fsub "dgroup", `dgroup`) > a cheat (`_debug` as before); SHIP CONFIG (fsub
   "ship") goes back to the SHIP group; F goes back a level each time. Practice drops
   `CAREER_ONLY`; a commander's flight drops NEXT WAVE. Away from a flight (title
   Options, docked Options tab): mode "odebug" (`od_from`, `od_page`, `od_sel`), only
   `OFF_FLIGHT` cheats (SHIP CONFIG, +10 KILLS, +1000 CR, LEVEL, LEGAL, MISSION, FRAME
   TIME, REPAIR SHOP; the last two without a commander), each written into the save at
   once (`_write_setting`); SHIP CONFIG there works on the commander (`_ship_items_c`,
   `_ship_config_c`); REPAIR SHOP from the docked tab adds or removes the tab at once
   (`_make_dock`). Lists of at most `DEBUG_ROWS` are drawn in order (`_draw_list`). The
   in-flight Settings page no longer shows the frame / rules / world / hud timings.
   Tests reach a cheat with `mod.cheat_group(line)`.
   Then (Brian): a rank ACE (4000 kills in the original's count, so EASY 800, NORMAL 2000,
   HARD 4000) between DEADLY and ELITE (`commander.RANKS`; not in the original). The
   loading screen's LOADING flashes, on and off at each redraw (`app.AceCommander.shown`;
   redraws come between imports, about 0.4 s apart). Docked charts: the joystick changes
   tab as on every tab (E / B too); C hands it to the cursor (`Docked.use_cursor`,
   `Docked.cursor`, `Chart.active`), then C picks a target and F hands it back; D shows a
   system's data either way; D back from System data returns with the cursor on. The
   hints: "C: MOVE CURSOR" / "< >   D: DATA", then "D: DATA  F: DONE" (the in-flight
   chart keeps "FUEL ... D: DATA").
   Then (Brian): no hint lines on the in-flight menu pages (PAUSED, SETTINGS, DEBUG);
   DEBUG is on the top in-flight menu again as well as at the end of Settings (F goes
   back to wherever it was opened from, `debug_from`). The SHIP group is SHIP CONFIG
   itself: its cheats (INVINCIBLE, REFILL MISSILES, REFILL FUEL, FUEL TO 1/4) then the
   equipment switches (`_is_cheat`); away from a flight SHIP opens the commander's
   equipment directly. The charts (docked and in flight) have no hints either: the
   distance ("3.6 LY", "... TOO FAR", "YOU ARE HERE") and "RANGE 7.0 LY"; while the
   joystick changes tabs the name is "< LAVE >" and the cursor grey, with the cursor
   yellow and the name plain once C hands it over (`Chart.active`).
   Then (Brian picked MISSION in the docked DEBUG and then had no jump): TO MISSION
   SYSTEM also works from the docked Options tab's DEBUG (a TRAVEL group with just it):
   `_mission_move` puts the commander there and `_dock()` docks again, so that stage's
   message plays (`self.game` is dropped first). Not on the title screen's Options.
   Then (Brian): the in-flight menu always has a HYPERSPACE line in a commander's flight
   (replacing build 22's "JUMP: name", shown only with a target in range): "HYPERSPACE:
   DISO" with a target in range starts the countdown; plain "HYPERSPACE" opens the local
   chart to pick one. Hidden during a countdown.
   Then (Brian): each laser has its own beam colour (`cockpit.LASER_COLOURS`: pulse magenta,
   beam blue, military green, mining yellow; enemy beams stay ORANGE), and the ring LEDs
   flash that colour while `Game.beam` is set after each shot (`_leds_flight`, below the
   bomb, ECM and hit flashes, above the launch glow, scooping, sun and safe zone).
   The top in-flight menu closes up (13 px lines, no help line) when
   it has more than six lines. Tests: `tests/test_equip_effects.py`.
6. **Tilt steering needs tuning: Brian doesn't like how it feels** (2026-11-13). He has not
   said what is wrong yet, so ask before changing it: sensitivity (`TILT_FULL`), dead zone
   (`TILT_DEADZONE`), axis directions, or the D hold time (`HOLD_MISSILE`).
8. Missile lock (build 19): the diamond is red, then green after `LOCK_TIME` (2 s, Brian's
   choice after playing with 1 s) and only then will D fire.
9. The in-flight menu has a DEBUG page of cheats (`DEBUG_MENU` in `app.py`, on by default
   while the game is being built; `Game.god` is the invincibility flag). Add a cheat there for
   each new thing that is slow to reach by playing, and turn it off before publishing.
   Its title shows the build (build 54), read from `metadata.json` by `app.build()`, so
   bump `version` in `metadata.json` and `tildagon.toml` for every build.
7. Level names (EASY / NORMAL / HARD) and their numbers are placeholders; see
   `commander.py` (`RANK_DIVISOR`) and `game.py` (`LEVELS`).

Measured on the badge in build 15: the title screen takes about 29 ms to draw (clear 7,
133 title rectangles 3.5, the one menu text 9.6, the ship the rest). Filling each rectangle
by itself is faster than one fill for all of them (3.5 against 7.7 ms). Flight averaged
51 ms a frame over five minutes.

## Not yet confirmed on the badge

- Tilt axis directions (`TILT_PITCH_SIGN`, `TILT_ROLL_SIGN`, `TILT_SWAP_AXES`).
- The local chart and hyperspace (build 20): cursor speed (`CURSOR_SPEED` in `chart.py`),
  whether the ring and dots read well, the streaks on arriving.
- Arriving (build 21, kept in build 26): whether 3 / 4 / 5 ships is the right fight.
- The star system (build 26): whether the planet, sun, station and compass read well;
  `ARRIVE_DIST`, `SAFE_K`, `JUMP_K`, `ENCOUNTER_EVERY` and `DOCK_DIST` by feel; the frame
  rate with the planet in view.
- Docking by hand (build 27): whether A is possible with the digital joystick (the
  tolerances above), whether B's beam feels right, crash damage and bounce; not yet on
  the badge (deployed and checked over the REPL; Brian's first test run was fine).
- The docking scene (build 28, confirmed by Brian) with build 29's varied tunnels: whether
  the shapes, morphing and spacings look good on the badge.
- The market (build 30): the layout on the badge, C / D and the repeat speed.
- Scooping into the hold, combat practice pick-ups and the green safe-zone LEDs (build 31).
- The Equip ship tab and the lasers, energy unit and fuel scoops in flight (build 33).
- Bounties (build 32): the cash message on a kill. Encounters by government and the
  planet-sized safe zone (build 32): whether the danger now feels right.
- Whether `deploy.bat`'s copy step reports failures properly (the log step is known to work).

Confirmed by Brian on 2026-11-13: F is faster and E slower; the LEDs flash on a hit and the
badge's own pattern comes back on leaving flight; ships switch from cross markers to
wireframes at a distance that looks fine (`WIRE_MIN`).

Confirmed by Brian on 2026-11-14 (build 25): the DEBUG page shows the build; the launch
tunnel's look and length; the station colours and the LED pulses on launch; the galactic
chart, cursor speed included (`G_CURSOR_SPEED`). Build 25 also flew 5 minutes with docking
and launching and no errors in the log.

## Controls (Brian's choices)

Joystick steers by default. C or joystick press fires, D missile, B energy bomb (not built
yet, says so), F/E speed up/down, A in-flight menu (status, settings with steering
and quit). Docked, on the market: joystick up / down picks a good, C buys, D sells (held
buttons repeat); on Equip ship: joystick picks an item, C buys. In tilt steering a tap on D re-zeroes and a hold fires the missile. Hostile ships red on the radar. Hit flash on the LEDs, not a ring
on screen. Enemy lasers run from the ship's gun to the bottom of the screen (the cockpit).

## Licensing

`ship_data.py` and `game_data.py` are derived from Elite (c) Acornsoft 1984, via
`github.com/markmoxon/elite-source-code-bbc-micro-disc`, which has no licence. They are
gitignored and must not be committed, published or put in the badge app store. Brian
generated it from his own clone. The converter that reads it is fine to publish.

The GitHub repo (`Corteil/ace_commander`, called `elite_demo` until 2026-11-13)
is **public** as of 2026-11-13, so check every commit
for Elite-derived data before pushing. Describe the project as a fan-made game inspired by
Elite, written from scratch, not as a port: no original code is used. The README's
"Credits and original material" section has the wording; Brian read it and agreed to merging it on 2026-11-13.

## Pitfalls for an agent working here

- On the Pi the badge sometimes drops off USB for a moment during an mpremote copy
  (`Input/output error`, then `no device found`); it comes back as the same port. Copy
  again and check every file's checksum before resetting.
- After writing files into this folder from a cloud session, **verify by checksum**. Once, a
  write reported success but delivered a stale cached copy of the same staging path. Staging
  each build under a fresh path avoided it.
- Git inside the sandbox cannot delete its own lock and temp files unless Brian grants delete
  permission, so a commit made there leaves `.git/*.lock` and `tmp_obj_*` behind. So far
  Brian has run commits and pushes himself.
- Say plainly what was tested only on a PC. Several early builds would have crashed on the
  badge (missing `super().__init__()`) while passing every PC test.
