# Hosts: Ace Commander on other devices

The game in the folder above is the EMF Tildagon / Spaceagon badge app; that is what the app
store installs (this folder is left out of release tarballs: `.gitattributes`). Each folder here
runs the same game files on another device:

- `pi/`: a Raspberry Pi (or any computer with Python 3 and pygame), in a window or full screen.
  See `pi/PLAN.md`.
- `tufty/`: the Pimoroni Tufty 2350 on Badgeware v3 (since build 109).
- `presto/`: the Pimoroni Presto (RP2350, 4" square touchscreen, buzzer): a plan only so far,
  `presto/PLAN.md` (2026-11-22).

How a host works (for now): the game imports a few Tildagon firmware modules (`app`,
`events.input`, `events.joystick`, `events.keyboard`, `frontboards.common`, `system.eventbus`,
`tildagonos`, ...). A host puts stand-ins for those in `sys.modules`, then runs the real `ace.py`
unchanged: it feeds button events in, calls `update()` and `draw(ctx)`, and gives `draw` a ctx
that draws on its own screen. The badge's behaviour doesn't change. A cleaner interface (moving
the ~300 firmware-facing lines of `ace.py` into a platform layer) comes once two hosts run.

Rules: the badge build stays the main target (its tests, its compiler, a run on the badge);
its round 240x240 layout doesn't change; Elite-derived data is never committed.
