# Ace Commander on the M5 CardputerZero

The Pi host (`../pi/`) set up for the CardputerZero (Compute Module 0, 320 x 170 LCD, built-in
keyboard, 352 MB RAM). Phase 0's findings: `notes/cardputerzero_phase0.md`.

- `run_cz.py`: the game on the LCD (KMSDRM on `/dev/dri/card1` when there's no desktop), the Elite
  layout full screen, text 1.6x in DejaVu Sans Condensed Bold (`TEXT_K`), whole-frame screens fitted to the LCD
  (`../pi/fit_pygame.py`, the Pi's `--wide`: drawn once into a list, the hints joined in one row along the bottom, the rest
  spread over the width and the height left; text made smaller, to 1.3x, only on a screen too full
  for its lines not to overlap), list menus with fewer lines further apart that scroll
  (`MENU_K`, the game's `config.menu_k`), fonts by path (pygame's lookup runs `fc-list`, which
  times out here), Fn + ; . , / as the arrows, W/A/S/D as the arrows on menus and screens with Q / Z / X as the badge's A / C / D (the
  hints say so), `--perf` for a FPS / RSS / CPU line a second.
- `ace-commander.sh`: what the launcher runs; logs in `~/.cache/ace_commander/play-*.log`.
- `install.sh`: the launcher (APPLaunch) entry and icon; needs root:
  `sudo sh ~/ace_commander/hosts/cardputerzero/install.sh`; options after it go on the launcher's
  command (`... install.sh --debug` for the DEBUG menu).
- Stop it from a shell: `touch ~/.cache/ace_commander/stop` (or SIGTERM). Holding Esc in the
  launcher ends it too.
- Test: `tests/test_cz_host.py` (SDL dummy driver), run by `tests/run_all.py`.

Saves and options are the Pi's: `~/.local/share/ace_commander/`.

## Working on it from another machine

Claude Code on the CardputerZero itself takes about half its RAM, so work on another machine and
copy over SSH (`Host cardzero` in `~/.ssh/config`):

    rsync -a --exclude .git --exclude __pycache__ --exclude build/ ./ cardzero:ace_commander/
    ssh cardzero 'tail -n 5 ~/.cache/ace_commander/play-*.log'
    ssh cardzero touch ~/.cache/ace_commander/stop
