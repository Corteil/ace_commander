# Ace Commander for the EMF Tildagon / Spaceagon badge

Notes for picking this project up in a new session. Last updated at the end of the first
working session, 2026-11-12 (build 13); updated 2026-11-13 (build 14, renamed, on a Pi).

## What this is

A MicroPython app for the 2026 EMF Camp "Spaceagon" badge (Tildagon with the 2026 front
board): a wireframe flight combat game plus a ship viewer, using the ship geometry and stats
of BBC Micro Elite. Brian's constraints: plain MicroPython, **no custom firmware build**.
C or `@micropython.viper` is welcome only if measurements show it would help.

Not built yet: docking, trading, the galaxy.

## Files

- `app.py` - menu, input (`Pad`), frame loop (`run`), LEDs, pause, PERF logging.
- `game.py` - game rules. No badge imports, so it runs on a PC.
- `cockpit.py` - flight view, HUD, radar. Built from rectangles (see Speed).
- `viewer.py` - ship viewer. `bench.py` - the menu's "Speed test".
- `ship_data.py` - generated, **gitignored** (see Licensing). 31 ships.
- `tools/import_ships.py` - makes `ship_data.py` from the Elite source.
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
logic is tested for real. Also compile with the real compiler:
`pip install mpy-cross` then `python -m mpy_cross -o /tmp/x.mpy app.py`.

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

## Next steps

1. Done: builds 13 and 14 were run and read; see above.
2. Optional, for frame rate: cut float garbage in the hot loops: `Game._rotate`,
   `Game._think`, `_turn`, `_ortho` in `game.py`, and the vertex loop in `cockpit.draw_ship`.
   Options: integer fixed-point, `@micropython.viper` on integer arrays (no firmware build
   needed), or updating enemy AI on alternate frames. Growing the heap would make collections
   rarer but each one longer, which is likely to feel worse.
3. Rules cost about 1.2 ms per object. Build 13 skips rotation maths when not turning;
   check what that saved.
4. Then gameplay: balance has only been judged by a crude autopilot in `tests/test_game.py`.
5. The rest of the game (title screen with a tumbling ship, galaxy, docking, trading,
   equipment) is drafted in `DESIGN.md`. Its 11 decisions were all made on 2026-11-13 (table at the end);
   the level names and numbers are still open. Brian asked for
   the tumbling-ship title screen specifically. Nothing in it is built.

## Not yet confirmed on the badge

- Whether the LED pattern comes back on leaving flight. (Confirmed 2026-11-13: F is faster
  and E slower, and the LEDs flash on a hit.)
- Tilt axis directions (`TILT_PITCH_SIGN`, `TILT_ROLL_SIGN`, `TILT_SWAP_AXES`).
- Whether cross markers switch to wireframes at a good distance (`WIRE_MIN` in `cockpit.py`).
- Whether `deploy.bat`'s copy step reports failures properly (the log step is known to work).

## Controls (Brian's choices)

Joystick steers by default. C or joystick press fires, B missile, F/E speed up/down,
A pause, D re-zero tilt. Hostile ships red on the radar. Hit flash on the LEDs, not a ring
on screen. Enemy lasers run from the ship's gun to the bottom of the screen (the cockpit).

## Licensing

`ship_data.py` is derived from Elite (c) Acornsoft 1984, via
`github.com/markmoxon/elite-source-code-bbc-micro-disc`, which has no licence. It is
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
