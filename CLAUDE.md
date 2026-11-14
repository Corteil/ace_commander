# Ace Commander for the EMF Tildagon / Spaceagon badge

Notes for picking this project up in a new session. Last updated at the end of the first
working session, 2026-11-12 (build 13); updated 2026-11-13 (build 16: renamed, on a Pi, design
phase 1 built) and again that night (build 22: DEBUG page, missile lock, phase 2).

## What this is

A MicroPython app for the 2026 EMF Camp "Spaceagon" badge (Tildagon with the 2026 front
board): a wireframe flight combat game plus a ship viewer, using the ship geometry and stats
of BBC Micro Elite. Brian's constraints: plain MicroPython, **no custom firmware build**.
C or `@micropython.viper` is welcome only if measurements show it would help.

Built from `DESIGN.md`: phase 1 (title screen, saved commander with rank, three levels, new
button layout) and phase 2 (galaxy, local and galactic charts, system data, hyperspace,
fuel, arriving docked, docked screens as tabs, launch tunnel). Not built yet: a real
station, docking and trading (phases 3 to 6), and the system description sentence.

## Files

- `app.py` - menu, input (`Pad`), frame loop (`run`), LEDs, pause, PERF logging.
- `game.py` - game rules. No badge imports, so it runs on a PC.
- `cockpit.py` - flight view, HUD, radar. Built from rectangles (see Speed).
- `viewer.py` - ship viewer. `bench.py` - the title screen's "Speed test".
- `title.py` - title screen: block-letter name from rectangles, tumbling ship, one menu line.
- `commander.py` - the saved commander (level, kills, rank, star system, fuel). Rules only,
  no badge imports. Saved to `commander.json` next to the app (gitignored).
- `galaxy.py` - the 256 star systems, worked out from three seeds. Rules only.
- `chart.py` - the local and galactic charts (imported the first time one is opened).
- `docked.py` - the docked tabs: Status, Local chart, Galactic chart, System data.
- `ship_data.py`, `game_data.py` - generated, **gitignored** (see Licensing). 31 ships; the
  galaxy's seeds, name letter pairs and starting place. Both must be copied to the badge.
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
6. **Tilt steering needs tuning: Brian doesn't like how it feels** (2026-11-13). He has not
   said what is wrong yet, so ask before changing it: sensitivity (`TILT_FULL`), dead zone
   (`TILT_DEADZONE`), axis directions, or the D hold time (`HOLD_MISSILE`).
8. Missile lock (build 19): the diamond is red, then green after `LOCK_TIME` (2 s, Brian's
   choice after playing with 1 s) and only then will D fire.
9. The in-flight menu has a DEBUG page of cheats (`DEBUG_MENU` in `app.py`, on by default
   while the game is being built; `Game.god` is the invincibility flag). Add a cheat there for
   each new thing that is slow to reach by playing, and turn it off before publishing.
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
- Arriving and docking (build 21): whether 3 / 4 / 5 ships is the right fight, and
  `DOCK_TIME`.
- Docked tabs and the launch tunnel (build 22): the galactic chart's cursor speed
  (`G_CURSOR_SPEED`), the tunnel's look and length.
- The launch LEDs (build 23): whether the pulses and colours look right on the real LEDs.
- Whether `deploy.bat`'s copy step reports failures properly (the log step is known to work).

Confirmed by Brian on 2026-11-13: F is faster and E slower; the LEDs flash on a hit and the
badge's own pattern comes back on leaving flight; ships switch from cross markers to
wireframes at a distance that looks fine (`WIRE_MIN`).

## Controls (Brian's choices)

Joystick steers by default. C or joystick press fires, D missile, B energy bomb (not built
yet, says so), F/E speed up/down, A in-flight menu (status, and a pause menu with steering
and quit). In tilt steering a tap on D re-zeroes and a hold fires the missile. Hostile ships red on the radar. Hit flash on the LEDs, not a ring
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

- After writing files into this folder from a cloud session, **verify by checksum**. Once, a
  write reported success but delivered a stale cached copy of the same staging path. Staging
  each build under a fresh path avoided it.
- Git inside the sandbox cannot delete its own lock and temp files unless Brian grants delete
  permission, so a commit made there leaves `.git/*.lock` and `tmp_obj_*` behind. So far
  Brian has run commits and pushes himself.
- Say plainly what was tested only on a PC. Several early builds would have crashed on the
  badge (missing `super().__init__()`) while passing every PC test.
