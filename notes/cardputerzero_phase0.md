# CardputerZero: Phase 0 (the Pi version, unchanged)

2026-11-27. Goal: run `hosts/pi/run.py` on the M5 CardputerZero with no game code changed,
and record how it behaves. Repo at `886b580` (Merge PR #61). Nothing here is committed.

## The device

| | |
|---|---|
| Board | Raspberry Pi Compute Module 0 Rev 1.0, 4 cores, aarch64 |
| OS | Debian GNU/Linux 13 (trixie), kernel 6.18.39+rpt-rpi-v8 |
| Python | 3.13.5 |
| pygame | python3-pygame 2.6.1-1+b2 from apt (already installed), SDL 2.32.4 |
| SDL video drivers | KMSDRM, wayland, offscreen, dummy (no x11) |
| RAM | 352 MiB total; ~37-74 MiB available at idle (desktop + Claude Code running) |
| Swap | 352 MiB zram, often 250+ MiB used |
| Disk | 29 GB, 21 GB free |
| Screen | `card1-SPI-1`, 320 x 170 (`/dev/dri/card1`, fbdev `/dev/fb0` = `/dev/fb_lcd`) |
| Keyboard | `tca8418c`, `/dev/input/event3` (`/dev/input/by-path/platform-3f804000.i2c-event`) |
| Audio | ES8389 (card 1) through PipeWire, default sink "Built-in Audio Stereo" |
| Watchdog | BCM2835 hardware watchdog, 1 minute (systemd) |

## Graphics: how it has to be set up

- `XDG_RUNTIME_DIR=/run/user/1000` is set in the SSH shell; `WAYLAND_DISPLAY` is not.
  The desktop session (lightdm, labwc, wf-panel-pi) uses `wayland-0` (`DISPLAY=:1` is Xwayland).
- **Wayland is no use for the game**: labwc's only output is `NOOP-1 "Headless output 2"`,
  1920 x 1080. It never draws on the LCD, and labwc has no keyboard (only the HDMI CEC and IR
  inputs). A Wayland run was started but not finished (the session was lost); not tried again.
- **KMSDRM works**: `SDL_VIDEODRIVER=kmsdrm SDL_KMSDRM_DEVICE_INDEX=1`. Nothing is DRM master
  on card1, so SDL takes it; `pi` is in `video` and `input`. `--full` gives a 320 x 170 window.
  The game's picture covers the launcher's fbdev drawing while it runs.
- pygame prints `UserWarning: Process running 'fc-list' timed-out! System fonts cannot be
  loaded` at start (it delays the first frame by several seconds). The game's text still draws.

## The launcher (APPLaunch) and why the game has to be an app

`M5CardputerZero-APPLaunch` (systemd user unit `APPLaunch.service`, `Restart=always`) owns
the LCD (`/dev/fb0`) and reads the keyboard *without* EVIOCGRAB, shared with its child apps.
Its own apps are LVGL on fbdev. It handles "Hold ESC Exit", the screensaver and the backlight.

Run from SSH, the game worked but: the screensaver blanked the screen, the launcher also
acted on every key, and the SSH link froze (see Memory). So it was installed as a launcher app:

- `~/.local/share/ace_phase0/ace-commander-phase0.sh`: starts `run.py --layout elite --full
  --sound --duel --log-keys` through the wrapper below with KMSDRM on card1, plus `vmstat`.
- `~/.local/share/ace_phase0/fpswrap.py`: test wrapper (outside the repo; the game is
  imported unchanged): an FPS / RSS / CPU line a second, the stop switch, and (added during
  testing, at Brian's request) **W/A/S/D as the arrow keys on every menu and screen**
  (off flight, and in flight while paused, a chart or an `fsub` page is open; not while typing).
- `/usr/share/APPLaunch/applications/ace_commander.desktop` and
  `/usr/share/APPLaunch/share/images/ace_commander.png` (90 x 90 from `hosts/pi/icon.png`),
  installed with `sudo sh ~/i.sh` (which also added `CardZero` to `/etc/hosts`: sudo warned
  "unable to resolve host CardZero", as `/etc/hosts` named only `cardputerzero`).
- The launcher reads app entries only from `/usr/share/APPLaunch/applications` (root).
- Logs: `~/.cache/ace_phase0/play-*.log`, `vmstat-*.log` (the scratchpad was lost on reboots).

**Stopping it from a shell:** `touch ~/.cache/ace_phase0/stop` (clean exit), or
`pkill -f fpswrap.py` (SIGTERM, also clean). As a launcher app, holding Esc also ends it
cleanly (two runs ended with "FPSWRAP stop requested").

## Memory: the main problem

- Three freezes/reboots during the session (boots at 20:28, 20:49, 21:25, 21:31). The one
  journalled: swap 273 / 352 MiB used, `rtkit-daemon: The canary thread is apparently
  starving` 35 s before the end, no OOM kill; the system thrashed until the watchdog
  (or Brian) reset it. SSH froze with it.
- What uses the RAM: Claude Code ~130 MB RSS, the desktop (lightdm, labwc, Xwayland,
  wf-panel-pi, pcmanfm...), the game 80-110 MB peak.
- The game's RSS: peak (`ru_maxrss`) 109 MB and 81 MB in the two runs that exited;
  live RSS 30-53 MB in flight when not swapped out, falling to 5-8 MB when the system
  pushed it out to swap.
- vmstat over runs: free memory often 0, swap in/out 2-5 MB/s on average with Claude Code
  connected; much less when it was not (run 3).

### After booting to the command line (22:06, Brian)

`multi-user.target`; lightdm / labwc / Xwayland / wf-panel gone. APPLaunch still starts (the
user manager runs without a login) and owns the LCD, so the game's launcher entry still works.
Available memory was still only 39 MB with swap 167 MB used, because **Claude Code is
177 MB RSS**, now half of RAM; everything else is small (zeroclaw 5 MB, systemd ~4 MB each).
Memory split: `arm=384M`, `gpu=128M` (firmware), CMA 64 MB. `gpu_mem` is not set in
`config.txt`. Lowering it (e.g. `gpu_mem=32`) would give Linux up to ~96 MB more; vc4 KMS
doesn't need it, but the firmware camera / video decode might (the launcher has a Camera
app), so it is untested and Brian's call.

## Frame rate and CPU (FPS once a second, from the wrapper)

The Pi host caps at 60 (`FPS = 60`, `clock.tick`); it reaches about 48.

| Run | Mode | Seconds | FPS median (min-max) | Game CPU median (max) |
|---|---|---|---|---|
| 1 (SSH, 21:17-21:24) | menu / docked | 19 | 48 (43-50) | 33-40% |
| 1 | flight | 351 | 46.5 (**0.2**-49) | 55% (78%) |
| 2 (launcher) | menu / docked | 28 | 48 (44-50) | 32-39% |
| 3 (launcher, 21:45-22:02) | flight | 929 | 48.7 (6.4-49.2) | 66% (94%) |
| 3 | practice | 13 | 46.8 (30-48) | 26% |

CPU % is of one core (`process_time`). Run 1, with Claude Code and SSH busy, had 46 flight
seconds under 30 FPS (22 under 10). Run 3 had 9 under 30 (1 under 10): the slow seconds are
swapping, not drawing. With memory to spare it holds ~48 FPS in flight. System-wide (vmstat)
CPU was 59-73% idle in the launcher runs, 37% idle plus 20% I/O wait in run 1.

## The tests (what the logs show, and what still needs Brian's word)

`--log-keys` prints every key pygame receives and the control it becomes.

| Test | Result |
|---|---|
| Picture on the LCD | Yes, 320 x 170. **Menu text too small to read comfortably** (Brian). |
| Sound | The player loaded (no "no sound:" line). Whether it was heard: **not confirmed**. |
| W/A/S/D with Space/F at once | W and Space held together twice in flight, both received: the keyboard sends more than one key at a time. Whether steering and firing then worked together: **not confirmed**. |
| E / Q speed | E and Q received in flight. |
| M missile | Received in flight. |
| V, 1-4 views | V, 1 and 3 received in flight. |
| P pause | Received (4 times in run 3). |
| C docking computer | Received in flight (run 1). |
| Tab | Received (`Keyboard.TAB`). |
| Fn + arrows | **No arrow key reached SDL at all** in runs 1 and 2, though the driver lists KEY_UP/DOWN/LEFT/RIGHT (103/105/106/108). So the menus could not be used; Brian asked for letter keys, hence the wrapper's W/A/S/D. The raw evdev logger (`rawkeys.py`) ran but no keys were pressed in its window: what Fn + `;` `.` `,` `/` actually send is still unknown. |
| Esc | Received; holding it exits the app (launcher). |
| Docked buy / sell | C buys. D sells, but with W/A/S/D as menu arrows **D is now "right"**, so selling needs another key (Brian: move buy/sell). |
| Game controller | An "X360 Controller" was plugged in during run 3 and worked (triggers, d-pad, shoulder, back, start, A, stick). |
| Every other key | All 37 letters, digits, Shift, Ctrl, Alt, Backspace, Enter, Esc map as on the Pi. |
| DUEL (`--duel`) | MULTIPLAYER is on the title screen; not played against a second machine. |

## Working on the CardputerZero remotely (SSH)

Claude Code on the CardputerZero itself takes ~177 MB, half the RAM, and dies with the
device when it freezes. So from Phase 1, run Claude Code on another machine (Brian's Pi or PC)
and use the CardputerZero as a target over SSH. No FTP: SSH copies files (`rsync`, `scp`, SFTP).

On the CardputerZero: sshd and avahi are running, `rsync` is installed, so it is
`CardZero.local` (192.168.68.88 on 2026-11-27). It had no `~/.ssh` yet.

One-time setup, on the other machine:

```
ssh-keygen -t ed25519            # only if there is no key yet
ssh-copy-id pi@CardZero.local    # the CardputerZero's password, once
ssh pi@CardZero.local true       # must now log in with no password
```

and in its `~/.ssh/config`:

```
Host cardzero
    HostName CardZero.local
    User pi
```

**Claude's commands have no terminal, so the login must need no password** (the same reason
`sudo` failed here). `sudo` on the CardputerZero still asks for one: Brian runs anything that
needs root (as `sudo sh ~/i.sh` above).

The loop:

- Edit, test (`tests/run_all.py`, pygame with the dummy driver) and commit in the repo on
  the other machine.
- Copy to the device: `rsync -a --delete --exclude .git ~/ace_commander/ cardzero:ace_commander/`
  The device's copy is then only a copy, and `--delete` removes anything there that the
  source lacks, this file included, so before the first rsync copy it back:
  `scp cardzero:ace_commander/notes/cardputerzero_phase0.md ~/ace_commander/notes/`.
- Run: Brian starts Ace Commander from the launcher (best for key tests: the launcher then
  ignores the keys and holding Esc quits). Or detached, surviving a dropped link:
  `ssh cardzero systemd-run --user ~/.local/share/ace_phase0/ace-commander-phase0.sh`
  (it then runs beside the launcher, which also reacts to the keys).
- Measure while Brian plays: `ssh cardzero 'tail -n 5 ~/.cache/ace_phase0/play-*.log'`,
  `ssh cardzero vmstat -w 2 5`, `ssh cardzero free -m`.
- Stop it: `ssh cardzero touch ~/.cache/ace_phase0/stop`.

The test files (`fpswrap.py`, `ace-commander-phase0.sh`, `rawkeys.py`, the `.desktop` and
icon) are in `~/.local/share/ace_phase0/` on the device, outside the repo; Phase 1's
`hosts/cardputerzero/` should take them over.

## Next steps (Phase 1)

1. **Free memory first.** Done: the desktop no longer boots. Still to do: play with
   Claude Code exited and measure again; maybe `gpu_mem=32`. Without this, any testing can
   freeze the device.
2. **A CardputerZero host**, `hosts/cardputerzero/`, built on `hosts/pi/` (the badge game
   unchanged): KMSDRM on card1 by default, a launcher `.desktop` + install script, the
   stop file, and no `fc-list` font lookup (a bundled or fixed font path).
3. **Text size**: the 240-unit canvas is drawn at 170/240 = 0.71, so 14-pt text is ~10 px
   and small labels hit the 6 px minimum (`ctx_pygame.text`). A text scale (~1.4) in the host,
   then fix what overlaps; a 320 x 170 layout of the dashboard.
4. **Keys**: find what Fn + arrows send (`rawkeys.py`), map them if possible; keep W/A/S/D as
   menu arrows; buy / sell on Z / X (C and Enter also buy); an Options line
   **KEYS: WASD / CLASSIC**, CLASSIC proposed as:
   pitch X / S, roll Z / C, faster / slower Space / Shift, fire F, target / missile T / M,
   E.C.M. / bomb E / B, docking computer D, views V and 1-4, pause P, jump / hyperspace J / H.
5. **Confirm by hand**: sound heard, fire while steering, the docking computer docks.
6. DUEL against the Pi or a second machine over UDP.
