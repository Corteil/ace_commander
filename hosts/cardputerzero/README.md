# Ace Commander on the M5 CardputerZero

The Pi host (`../pi/`) set up for the CardputerZero (Compute Module 0, 320 x 170 LCD, built-in
keyboard, 352 MB RAM). Phase 0's findings: `notes/cardputerzero_phase0.md`.

- `run_cz.py`: the game on the LCD (KMSDRM on `/dev/dri/card1` when there's no desktop), the Elite
  layout full screen, text 1.4x (`TEXT_K`), the badge's menu screens stretched across by the same
  (so their columns keep room), fonts by path (pygame's lookup runs `fc-list`, which times out
  here), W/A/S/D as the arrows on menus and screens with Q / Z / X as the badge's A / C / D (the
  hints say so), `--perf` for a FPS / RSS / CPU line a second.
- `ace-commander.sh`: what the launcher runs; logs in `~/.cache/ace_commander/play-*.log`.
- `install.sh`: the launcher (APPLaunch) entry and icon; needs root:
  `sudo sh ~/ace_commander/hosts/cardputerzero/install.sh`.
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
