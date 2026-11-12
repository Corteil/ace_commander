# Elite Demo

Hidden-line wireframe ships from BBC Micro Elite for the EMF Tildagon / Spaceagon badge.
A demo: it shows one ship at a time, spinning, and you can steer it with the badge.

## Controls

| Input | Action |
|---|---|
| Tilt the badge | pitch and roll the ship (accelerometer) |
| UP / DOWN | pitch (joystick or buttons) |
| LEFT / RIGHT | roll (joystick or buttons) |
| CONFIRM | next ship, and re-zero tilt to how you're holding the badge |
| CANCEL | exit |
| Keyboard | W / S pitch, A / D roll, N next ship, P previous ship |

If tilting moves the ship the wrong way, flip `TILT_PITCH_SIGN` / `TILT_ROLL_SIGN` or set
`TILT_SWAP_AXES = True` near the top of `app.py`.

## Ships

The app has no ships of its own. It reads `ship_data.py`, which you generate from your own
copy of the Elite source (31 ships: Cobra Mk III, Viper, Sidewinder, Thargoid, Mamba, ...).
Without it the app shows a "ship_data.py not found" message.

`ship_data.py` is **not in this repo**. It is derived from Elite (c) Acornsoft 1984 and the
source repo it comes from has no licence, so it is listed in `.gitignore`. Make it yourself:

1. Get the source, for example
   [elite-source-code-bbc-micro-disc](https://github.com/markmoxon/elite-source-code-bbc-micro-disc).
2. Run the converter on it:

   ```
   python3 tools/import_ships.py path/to/elite-source-code-bbc-micro-disc
   ```

   Add `--list` to see which ships it finds, or `--only SHIP_COBRA_MK_3 SHIP_VIPER` to pick some.
3. That writes `ship_data.py` in the current folder.

Hidden lines are removed the way the original game does it: an edge is drawn only if one of
the two faces it sits between points at the camera.

## Install

Copy `__init__.py app.py ship_data.py tildagon.toml metadata.json` to `/apps/elite_demo/` on
the badge (for example with `mpremote fs cp`), then restart it. `tools/` stays on your PC.
