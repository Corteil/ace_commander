# Plan: Ace Commander on a Raspberry Pi

Status: **draft 1, 2026-11-18; P0 done 2026-11-19 in `hosts/pi/` (Brian chose one repo); P1 by
keyboard done 2026-11-19 (branch `pi-p1`), frame comparison with the Pillow renders not yet.** Written against upstream v0.3.0
(`Corteil/ace_commander` main, 8c8a37c). Sister plan: the Tufty 2350 port
(`Corteil/tufty_ace_commarder`, `PLAN.md`), whose approach this reuses.

Rules (as for the Tufty port, until Brian decides otherwise):
- The EMF badge build doesn't change for the Pi without Brian's go-ahead, and its round
  240x240 layout stays as it is.
- Elite-derived data (`ship_data.py`, `game_data.py`) is generated locally and never
  committed; the game's own `original_*` data is the default.
- Plain Python on the Pi (CPython 3), no compiled extensions of our own.

## Why it is cheap
- The game's rules (`game`, `galaxy`, `commander`, `market`, `equipment`, `ships`, `missions`,
  `describe`, `content`, `rules`, `find`, `original_*`) have no badge imports and already run on
  CPython: the whole test suite runs on this Pi (Python 3.13).
- Everything is drawn through a canvas-style `ctx` (about 20 calls). The tests already have a
  Pillow `ctx` (`tests/badge_stubs.PilCtx`), and the Tufty port has one for Badgeware.
- **The Tufty host shows the shortest path:** upstream's real `ace.py` runs unmodified on stand-ins
  for the few firmware modules it imports (`tufty_firmware.py`: app base class, button events,
  event bus, LED ring). A Pi host does the same with pygame for the screen and input. A trial
  sync of v0.3.0 into the Tufty repo runs title -> new commander -> docked -> flight that way.
- The Pi is far faster than either badge: 60 frames a second with room to spare, no garbage
  collection hitches to design around.

## What this Pi has (checked 2026-11-18)
Compute Module 5, Raspberry Pi OS with a Wayland desktop, Python 3.13.5, **pygame 2.6.1** and
Pillow 11.1 installed, `/dev/dri` (KMS) present, sound cards present. No gamepad plugged in.

## Choices for Brian (recommendations first)
1. **Screen and layout**
   - **A. A desktop window, the badge's round layout at 2x (480x480)** (recommended first): no new
     layout, looks like the badge, develops on this Pi's desktop. Window size and scale are settings.
   - B. **HyperPixel 2.1 Round** (480x480, round): option A full screen, exactly the badge's shape.
   - C. **The Elite layout from the Tufty port** (3D view over a dashboard with the scanner) at
     320x240 or scaled: reuses `dash_tufty.py`; fits 4:3 screens (Display HAT Mini, a cyberdeck).
   - D. Full HD: a new, larger layout. Most work; later if at all.
2. **Controls**: a keyboard works from day one (the game already has Elite's keys, the search and
   name pages). Then a **USB / Bluetooth gamepad**, ideally with **analogue steering** from the
   stick (the badges only have digital). Badge buttons A-F map to spare keys or pad buttons.
3. **LEDs**: the 12-LED ring drawn on screen (as the Tufty's border) first; real LEDs later if
   wanted (a 12-LED NeoPixel ring, Blinkt!, Unicorn HAT).
4. **Where the code lives** (shared decision with the Tufty port; see below).

## Architecture
```
hosts/pi/
  run.py             # pygame window / full screen, the frame loop (update, draw, flip)
  pi_firmware.py     # stand-ins: app, events.input / joystick / keyboard, frontboards.common,
                     # system.eventbus, tildagonos LEDs, app_components.dialog (TextDialog)
  ctx_pygame.py      # the ctx calls on a pygame Surface, scaled, origin at the centre
  keys_pi.py         # keyboard (and later gamepad) -> the game's button events
  tests/             # headless (SDL dummy driver) tests of the host
```
- **Display**: draw at the final scale (logical coordinates times S) rather than scaling a
  240x240 bitmap, so lines stay sharp: `pygame.draw.line` / `aaline` with width, `polygon` for
  fills, `circle` / `arc`, text with `pygame.font` (a free font; size times S). A round mask for
  the round layout.
- **Input**: pygame key events become the firmware's `ButtonDownEvent` / `ButtonUpEvent` on the
  stand-in bus, named as the Keyboard Hexpansion's keys, so `Pad` and every `k_*` key work as on
  the badge. `AceCommander._keyboard()` then reports a keyboard (search and name use the typing
  pages). Badge buttons: the stand-in `FRONTBOARD_BUTTON_TYPES` A-F mapped to chosen keys or pad buttons
  (not the letter keys, which are the game's keyboard keys).
- **Analogue steering** needs one upstream hook: `_steer` reads held buttons as -1 / 0 / 1. A host
  value (`AceCommander.stick = (x, y)`, added to the axes) would be the smallest change: ask first.
- **Saves**: the game writes beside its own files (`APP_DIR`); on the Pi point `SAVE_PATH` and the
  options path at `~/.local/share/ace_commander/` (a host setting, no upstream change if the two
  paths stay module-level names).
- **Run it**: `python3 hosts/pi/run.py` (window), `--full` (full screen / KMS), `--layout round|elite`,
  `--scale N`. Later a `.desktop` entry, and autostart for a cyberdeck (systemd user service).

## Phases
### P0 - A window with the title screen
`ctx_pygame.py` and `pi_firmware.py` (start from the Tufty stand-ins), the loop in `main.py`, upstream
vendored or imported (see repo layout). Done when: the title screen draws in a 480x480 window and
the keyboard picks NEW COMMANDER.

### P1 - Playable with a keyboard, round layout
Every screen through the real game: title, new commander, docked tabs, Shipyard, charts, search,
flight, tunnels, briefings. LED ring on screen. Saves under `~/.local/share`. Tests: a headless
run (SDL dummy video driver) that drives the game through the same scenes as the Tufty host test,
and frame shots compared with upstream's Pillow renders. Done when: a full trip (launch, jump,
fight, dock, trade, buy a ship) works by keyboard, and the tests pass.

Done (2026-11-19): `hosts/pi/tests/test_pi_trip.py` (run by `tests/run_all.py`, ~3 s) plays
a trip by keys: every docked tab and Options drawn, buy on the market (2, C held), launch (1),
the in-flight screens 0 and 5-9 opened and closed by their keys, views 1-4, a fight (Space; the
pirate is kept in the sights instead of steered after), a system picked on the local chart (6,
arrows, Enter), hyperspace (H), the docking computer (C; the flight to the station is skipped by
placing the ship), sell (3, D held), a ship bought in the Shipyard (-, down, C, C), back to the
title (F) and quit (Esc). Host files (`run.load_game`): the save, options.json and debug.txt in
`~/.local/share/ace_commander/`; content.py is loaded with its `__file__` there so Options >
CONTENT applies on the Pi too; the DEBUG menu and the PERF lines only with `--debug` (or
debug.txt / the Easter egg, as on the badge). No change to the badge's files.
Not yet: comparing frames with `tests/render.py`'s Pillow shots; the LED ring is drawn but
untested against the jump flashes. Brian's answer to the F3 / F4 buying (2026-11-19): B buys and S sells,
in the game itself (build 93), so the badge's Keyboard Hexpansion has them too (on the Pi,
B was later made the badge's B, below).
Brian (2026-11-19, from a `--log-keys` run: he pressed A, C, D, F docked and nothing
happened): off the flight (docked, title, menus, the pause menu) and not while typing, the
letter keys A-F are also the badge's buttons (`keys_pi.BOTH`; Brian: "when docked the letter
keys act the same as the badge keys, apart when entering text"); then "badges b everywhere": docked, keyboard B
is only the badge's B (next tab, find on the chart), so on the Pi C buys and S sells.
Pi host only; the badge's Keyboard Hexpansion is unchanged.

### P2 - Gamepad
pygame joystick: D-pad and buttons first, then the analogue stick (needs the `_steer` hook), with
a dead zone and a curve. Button map in one table. Done when: a whole trip works on a pad alone.

### P3 - Screens
Full screen on the desktop and on KMS without a desktop; the HyperPixel Round (option B); the Elite
layout (option C) shared with the Tufty port. Scale and layout as settings in Options.

### P4 - Extras (each only if wanted)
Real LEDs on GPIO; sound (our own effects: lasers, hits, hyperspace, docking; nothing taken from the
original); a higher-detail mode (more stardust, thicker lines, larger scanner); packaging for
`pip install` or a `.deb`, and kiosk autostart.

## Repo layout (decided 2026-11-19: one repo)
Brian chose option A: the Pi host lives in `ace_commander/hosts/pi/` (left out of the app
store tarball by `.gitattributes`), importing the same game files as the badge. The Tufty port
moves to `hosts/tufty/` after its first run on hardware (G1).

## Risks and open questions
- Font: the badge's own font isn't available; text widths will differ a little, so screens laid out
  to the pixel for 240 may need small nudges (measured on the Tufty: text screens 73-86% alike).
- pygame on Wayland vs KMS full screen: check both on this CM5 early (P0).
- Analogue steering means touching upstream's `_steer`: ask before changing it.
- Two copies of the stand-ins (Tufty, Pi) unless the repo layout is decided first.

## First steps
1. Brian picks the screen (A recommended), the controls and the repo layout.
2. P0 in `hosts/pi/`: window, `ctx_pygame.py`, stand-ins, title screen.
3. P1 by keyboard, with the headless test.
