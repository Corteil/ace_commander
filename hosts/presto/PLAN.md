# Plan: Ace Commander on the Pimoroni Presto

Status: **plan only, 2026-11-22** (Brian: "just plan for it for now, you can add a presto
folder"). Nothing built yet. Written against `main` at c5300c3 (builds up to 144) and Pimoroni's
Presto firmware **v2.0.0** (github.com/pimoroni/presto, released 2026-08-26). Sister hosts:
`hosts/tufty/` (the closest: RP2350, MicroPython, Qw/ST Pad) and `hosts/pi/`.

Rules, as for the other hosts:
- The badge build doesn't change for the Presto; its round 240x240 layout stays as it is.
- Elite-derived data (`ship_data.py`, `game_data.py`, `elite_sfx.py`) is made locally and never
  committed or published; the game's own `original_*` data and sounds are the default.
- Plain MicroPython on Pimoroni's own firmware: no custom firmware build.
- Copy, reset or open a REPL on the Presto only after Brian says OK.

## What the Presto is (from the repository, not yet seen on the bench)
- **RP2350B with 8 MB PSRAM** (the `psram` module; `psram.mkramfs()` in the launcher). Memory is
  not a worry, as on the Tufty (about 8 MB); speed should be about the Tufty's (60 ms frames).
- **4" square IPS touchscreen, 480x480**, through PicoGraphics (`presto.display`):
  `Presto(full_res=False)` gives **240x240, exactly the badge's canvas** (two layers by default),
  `full_res=True` 480x480 (one layer, slower). Only a 180-degree rotation is possible.
  `presto.update()` copies the front buffer out; `partial_update(x, y, w, h)` part of it.
  PicoVector (`picovector`: `Polygon`, `Transform`, antialiasing, `.af` fonts) for shapes and text.
- **Touch** (FT6236): `presto.touch_a` / `touch_b` (x, y, touched), two at once except when level
  with each other side by side; `touch_poll()`; `touch.Button` helpers.
- **A piezo buzzer on GPIO 43** (`presto.Buzzer(43).set_tone(freq, duty)`, PWM; under 50 Hz is
  silence): **sound with nothing to buy**.
- **7 RGB LEDs on the back** (GPIO 33): `set_led_rgb(i, r, g, b)`, with `auto_ambient_leds(False)`.
- **Qw/ST connector on I2C0, SDA 40, SCL 41**; `qwstpad` is frozen into the firmware (the
  `multi_player.py` example drives up to four Pads).
- WiFi (`ezwifi`, `secrets.py`), a microSD slot; `lsm6ds3` is frozen in (an accelerometer, for a
  Qw/ST sensor board: not on the Presto itself, so no tilt unless one is fitted).
- **No buttons for the game** (BOOT and RESET only).
- Apps: the launcher (`main.py`) lists `.py` files and runs the one chosen (`__import__`, via
  `/ramfs/launch.txt` after a reset). So the game goes on as a folder (`ace_commander/`, the
  package) plus a starter `ace_commander.py` (or similar) in the root that the launcher shows.

## Why it is cheap
The platform layer (builds 100-105) already keeps every device apart: a host sets
`config.platform`, `config.input`, `config.layout` and runs the shared game unchanged. The Tufty
host (`hosts/tufty/`) is the model: loading screen importing one module a frame, a `Feed` for
input, a ctx stand-in, LEDs from `platform.LEDS`, the Qw/ST Pad, `build_tufty.py --mpy`, strict
stand-ins for its tests. Sound is done too: `sfx.py`'s table and the stepping in `buzzer.py`
(one tone at a time, steps shorter than a frame skipped) carry over to a PWM buzzer.

## What's new to write (hosts/presto/)
| File | What | From |
|---|---|---|
| `ctx_presto.py` | the game's ~20 ctx calls (rgb/rgba, rectangle, move_to/line_to/stroke, arc, fill, text with align and size, save/restore, translate) on PicoGraphics + PicoVector, at 1x (240) or 2x (480) | new; the biggest part (the Tufty's is Badgeware, different calls) |
| `platform_presto.py` | `Platform`: `LEDS` (12 written, shown on the 7 back LEDs), no tilt, `text_dialog` = the letter picker, `sound_ok` / `sound` / `sound_step` on the PWM buzzer, `minimise` | platform_tufty |
| `sound_presto.py` | `sfx.py` played on `Buzzer(43)`: set_tone per step, noise as random pitches, levels as duty (quieter = smaller duty) | buzzer.py's stepping |
| `controls_presto.py` | the Pad map (as the Tufty's `PAD_MAP` / `PAD_MAP_OFF`) and the touch buttons, `Feed`, hint labels | controls_tufty |
| `host_presto.py` | loading screen, frame loop (`update`, then `presto.update()`), touch and Pad polling, saves in a writable folder | host_tufty |
| `layout_presto.py` (+ dash?) | only if not the badge's round layout (choice 2) | layout_tufty / dash_tufty |
| `build_presto.py` | the folder, `--elite`, `--mpy` (the firmware's MicroPython version: check), `--copy` (mpremote; the Presto has no USB drive mode like the Tufty's `mass_storage`) | build_tufty |
| `tests/sim_presto.py`, `tests/test_presto_host.py` | strict stand-ins for `presto`, `picographics`, `picovector`, `touch`, `machine.PWM`; title -> new commander -> docked -> flight -> sound | sim_badgeware, test_tufty_host |

The shared game should need nothing new. Possibly: a `config.layout` for a square screen (as
`config.more_hints` already covers square screens: Presto would set it, like the Tufty and the
Pi's Elite layout), and the hints' names for touch buttons (`relabel`, as the Tufty).

## Choices for Brian (recommendations first)
1. **Controls without a Pad**
   - **A. Touch buttons in the corners, the whole game** (recommended): in 240x240 the round view
     leaves four corner triangles free. Left corners: a D-pad (joystick) / steering; right
     corners: A-F as the badge's buttons, labelled. Two touches work at once (steer and fire),
     except two touches level side by side. Off the flight, tapping a menu line could choose it.
   - B. Combat practice only, as the Tufty without its Pad (`config.practice_only`,
     `auto_missiles`): simplest, but touch could do much more.
   - With the **Qw/ST Pad** plugged in: the Tufty's map (D-pad joystick, A=C, B=D, X=F, Y=E,
     + = A, - = B; Y off the flight = search), touch still there.
2. **Layout**
   - **A. The badge's round layout at 240x240** (recommended first): no new layout, no rescaling,
     the corners free for touch buttons; the LED ring shown on the back LEDs (and optionally
     drawn round the screen's edge, as the Tufty's border).
   - B. 480x480 full resolution, the round layout at 2x: crisper, slower; measure first.
   - C. A 3D view over a dashboard (the Pi's Elite layout / the Tufty's), square: more room for
     gauges, but the touch buttons then need space of their own.
3. **Sound**: the built-in buzzer from the start, Options > SOUND as elsewhere (recommended); a
   Qwiic buzzer on the Qw/ST port would also work (buzzer.py) but isn't needed.
4. **Back LEDs**: the badge's ring effects (hit red, station colours, jump flashes, ECM violet)
   spread over 7 LEDs (recommended), or Presto's own ambient mode.

## Steps
- **P0, on the bench**: Brian's Presto on the Pi with firmware v2.0.0; read its MicroPython
  version (for `--mpy`), the free heap, and time a frame of 240x240 drawing (rectangles, lines,
  a polygon, text) from the REPL, as was done for the Tufty. Check the buzzer and the back LEDs.
- **P1**: `ctx_presto` + `sim_presto` + a host that runs title -> new commander -> docked ->
  flight on the stand-ins, then on the Presto (combat practice with a Pad first).
- **P2**: touch buttons (choice 1) and their hints; the Pad.
- **P3**: sound on the buzzer, the back LEDs, the loading screen and icon (the Kestrel), saves.
- **P4**: `build_presto.py --mpy --copy`, a release zip from `tools/make_release.py` like the
  Tufty's and the Pi's.

## Questions to settle on the bench
- Where saves can go (a writable folder; the Tufty's app folder is read-only, the Presto's?).
- How the launcher shows a folder app (a starter `.py` in the root, its name and icon).
- Whether `--mpy` needs the firmware's own mpy-cross version (likely MicroPython 1.25-1.26 for
  v2.0.0: read `sys.implementation` on the board).
- Frame time at 240 vs 480, and with two PicoGraphics layers.
- Touch rate and how it feels for steering.
