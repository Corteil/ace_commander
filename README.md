# Ace Commander

A flight combat game and ship viewer for the EMF Tildagon / Spaceagon badge, drawn as
hidden-line wireframes using the ships of BBC Micro Elite. Plain MicroPython: no C and no
custom firmware.

The title screen, with a ship tumbling under the name, offers:

- **New commander** / **Continue** - fight waves of pirates, shoot rocks and scoop cargo as
  a saved commander. Your kills earn a rank, from Harmless up to Elite. A new commander picks
  one of three levels, which sets how many kills each rank takes and how tough the enemies
  are, and can't be changed afterwards. There is one commander; it is saved in
  `commander.json` next to the app when you quit to the title screen or are destroyed.
- **Combat practice** - the same fight with nothing kept.
- **Ship viewer** - every ship, one at a time, spinning.
- **Speed test** - times kinds of drawing on the badge.

Joystick left / right changes the choice, C selects it and F leaves the app.

Not in yet: docking, trading, the galaxy. The plan for those is in [DESIGN.md](DESIGN.md).

This is a fan-made game inspired by Elite. It is not official, licensed or endorsed. See
[Credits and original material](#credits-and-original-material).

## Flight controls

Written for the 2026 Spaceagon: the joystick steers and the lettered buttons do the rest.

| Input | Action |
|---|---|
| Joystick | pitch and roll |
| C, or press the joystick (hold) | lasers |
| D | fire a missile at the boxed target |
| B | energy bomb (not in the game yet) |
| F / E | speed up / slow down |
| A | in-flight menu, which pauses the game |

In the in-flight menu the joystick moves up and down, C selects, F goes back and A
resumes. It has **Status** (your commander's rank and kills) and a **Pause menu**, where you
switch steering between JOYSTICK and TILT or quit to the title screen.

The menu also has a **Debug** page of cheats for testing: invincibility, kill all enemies,
next wave, add an enemy, refill missiles and +10 kills. Kills made there count towards your
commander's rank. Set `DEBUG_MENU = False` in `app.py` to hide it.

With TILT, tilting the badge steers and the joystick still works. D then does two jobs: a
tap re-zeroes the tilt and holding it for about half a second fires the missile
(`HOLD_MISSILE` in `app.py`). To start in tilt mode, set `TILT_DEFAULT = True` in `app.py`.

Keyboard: `W` / `S` or up / down pitch, `A` / `D` or left / right roll, `E` / `Q` speed
up / down, `F` or space lasers, `M` missile, `P` in-flight menu.

To use other buttons, change `BTN_SPEED_UP`, `BTN_SPEED_DOWN`, `BTN_MISSILE`, `BTN_BOMB`
and `BTN_MENU` near the top of `app.py`.

On firmware without the joystick's own button names, the game falls back to tilt steering
with UP / DOWN for speed, LEFT for a missile, RIGHT to re-zero and CANCEL for the menu.

## The screen

- Left bars: speed (green) and laser temperature (yellow, red when it has overheated and
  locked out).
- Right bars: shield (blue) and energy (green). Shields soak up hits and recharge after a
  few seconds without damage; when energy runs out the game is over.
- Green squares: missiles left. A diamond marks the ship in the missile sights: red at
  first, green once it has stayed there for two seconds and the missile has locked on. D only
  fires at a green diamond; before that it says NO LOCK.
- Radar at the bottom: left-right is left-right, up the ellipse is ahead, and the stick on
  each blip shows how far above or below you it is. Red is a hostile ship, yellow is cargo,
  magenta is a missile, grey is a rock.
- Top: the wave in yellow and the score in white. The small number above them is the time
  each frame takes, in ms (`SHOW_FRAME_TIME` in `app.py`).
- The badge's LEDs flash red when you're hit (`USE_LEDS` in `app.py`; with it off, or if
  the LEDs can't be reached, a red ring flashes on screen instead).
- Ships far away are dots, at middle distance small cross markers, and close up wireframes.

## Speed

Measured on the badge, a filled rectangle costs about 0.03 ms, a line about 0.35 ms and a
piece of text about 4 ms, and the badge's own app loop waits 50 ms after every update. So:

- everything drawn every frame is made of rectangles where it can be, including the digits;
- only ships that look bigger than `WIRE_MIN` pixels (`cockpit.py`) are drawn as wireframes;
- in flight and the viewer the app asks for a redraw itself rather than waiting the 50 ms
  (`FAST_FRAMES` in `app.py`). This leans on the firmware's scheduler; if that isn't as
  expected it goes back to the normal loop by itself.

The menu's Speed test repeats the measurements, and the pause screen shows where a flight
frame's time went.

## Tuning

Near the top of `app.py`:

- `TILT_PITCH_SIGN`, `TILT_ROLL_SIGN`, `TILT_SWAP_AXES` if tilting goes the wrong way.
- `INVERT_PITCH = True` if you want joystick up to dive, flight-stick style.

Speeds, damage, ranges and how fast enemies turn are constants at the top of `game.py`.

## Ships

The app has no ships of its own. It reads `ship_data.py`, which you generate from your own
copy of the Elite source (31 ships, with each one's energy, speed, laser and missiles).
Without it the menu shows "ship_data.py not found".

`ship_data.py` is **not in this repo**. It is derived from Elite (c) Acornsoft 1984 and the
source repo it comes from has no licence, so it is listed in `.gitignore`. Make it yourself:

1. Get the source, for example
   [elite-source-code-bbc-micro-disc](https://github.com/markmoxon/elite-source-code-bbc-micro-disc).
2. Run the converter on it:

   ```
   python3 tools/import_ships.py path/to/elite-source-code-bbc-micro-disc
   ```

   Add `--list` to see which ships it finds.
3. That writes `ship_data.py` in the current folder.

Hidden lines are removed the way the original game does it: an edge is drawn only if one of
the two faces it sits between points back at the viewer.

## Files

- `app.py` - moves between the screens; input (tilt, buttons, keyboard); in-flight menu.
- `title.py` - the title screen: block-letter name, tumbling ship, one-line menu.
- `commander.py` - the saved commander: level, kills, rank. No badge imports.
- `game.py` - the flight game's rules, with no badge imports so it can be tested on a PC.
- `cockpit.py` - draws the flight view, radar and gauges.
- `viewer.py` - the ship viewer.
- `bench.py` - the menu's Speed test: times kinds of drawing on the badge.
- `deploy.bat` - double-click to copy the app to the badge, restart it, and save what the
  badge prints to `badge_log.txt` (`deploy.bat all` also copies `ship_data.py`).
- `tools/import_ships.py` - makes `ship_data.py`. Stays on your PC.
- `tests/` - tests that run on a PC with stand-ins for the badge: `python tests/run_all.py`.
- `CLAUDE.md` - project notes: firmware facts, measurements and what's next.
- `DESIGN.md` - design for the rest of the game. Phase 1 (title screen, commander, levels,
  new buttons) is built; docking, trading and the galaxy are not.

## Install

Copy `__init__.py app.py game.py cockpit.py viewer.py bench.py title.py commander.py
ship_data.py tildagon.toml metadata.json` to `/apps/ace_commander/` on the badge (for example with `mpremote fs cp`),
then restart it. On Windows, `deploy.bat all` does this.

## Credits and original material

Elite was written by David Braben and Ian Bell and published by Acornsoft in 1984. This
project is a fan-made game inspired by it, for the EMF Camp badge.

- **Code:** written from scratch in MicroPython. It contains no original Elite code and
  nothing translated from it.
- **Ideas re-implemented in new code:** the hidden-line rule, steering by rotating the
  universe around the player, the radar with height sticks, and the ship names. One message,
  "RIGHT ON COMMANDER!", is a line from the original.
- **Ship models and stats:** these are the original's own data and are **not in this repo**.
  The game needs them to run, so each user generates `ship_data.py` locally (see
  [Ships](#ships)) from Mark Moxon's annotated source at [bbcelite.com](https://elite.bbcelite.com/).
  That source repo has no licence, which is why the generated file is git-ignored and should
  not be published.
- **Badge firmware:** `tests/badge_stubs.py` mirrors the button-matching rules of the
  [badge firmware](https://github.com/emfcamp/badge-2024-software) so the tests behave like
  the badge.

"No original code" is not the same as "no legal issue". The ship data is the part someone
could object to, so it should not go into the badge app store. The game was first called
Elite and was renamed Ace Commander to keep clear of the original's name.
