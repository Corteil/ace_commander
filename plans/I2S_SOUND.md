# Plan: I2S sound on the badge

Status: **built as build 145 (2026-11-23), not yet heard on the badge**; was plan only, 2026-11-22 (Brian: "make plans for I2S sound on the badge"). Written
against `main` at 2763e98 (release 0.4.3, builds up to 144). Nothing built yet.

Today the badge plays the game's sounds only on a SparkFun Qwiic Buzzer (`buzzer.py`, build
140): one tone at a time, four volume levels, noise as random pitches. An I2S DAC or amplifier
on a hexpansion port would play them properly: the parts mixed together, real noise, smooth
levels, as the Pi does (`hosts/pi/sound_pi.py`), from the same table (`sfx.py`, Elite's sounds
via `elite_sfx.py` or the game's own).

Rules: the badge build stays the main target and works as now with no sound hardware (no
start-up cost beyond a check); plain MicroPython (viper allowed where measured to help); no
custom firmware; nothing Elite-derived committed.

## What is known (read from the source, not tried on the badge)
- **The firmware has I2S.** MicroPython's esp32 port turns `machine.I2S` on wherever the chip
  has it (`MICROPY_PY_MACHINE_I2S = SOC_I2S_SUPPORTED`, `ports/esp32/mpconfigport.h`), and the
  Tildagon board doesn't turn it off. The ESP32-S3 has two I2S units (0 and 1). TX, 16 or 32
  bits, MONO or STEREO, any rate; `ibuf` (bytes buffered in DMA); blocking `write()`, or
  non-blocking with `irq(callback)` (the callback runs via the scheduler, between bytecodes).
- **The hexpansion ports' high-speed pins** go straight to ESP32-S3 GPIOs
  (`system/hexpansion/config.py`): port 1 GPIO 39-42, 2: 35-38, 3: 34, 33, 47, 48, 4: 11, 14,
  13, 12, 5: 18, 16, 15, 17, 6: 3-6. `HexpansionConfig(port).pin[0..3]`. I2S out needs three.
- **An I2S hexpansion exists: AudioHexpansion** (github.com/andreacampanella/AudioHexpansion,
  2026-07): a carrier for a **PCM5102A** I2S DAC module (line out / headphones; its H3L pad
  shorted). Its apps on the store, **BadgeRadio** (internet radio) and **Badge-o-techno** (a
  synthesiser), use the same wiring and set-up:
  - `hs[0]` = BCK (sck), `hs[1]` = LRCK (ws), `hs[2]` = DIN (sd); port 2 by default, chosen
    in the app.
  - `I2S(0, sck=, ws=, sd=, mode=I2S.TX, bits=16, format=I2S.MONO, rate=22050, ibuf=20000)`
    (Badge-o-techno; BadgeRadio stereo 44.1 kHz), opened once small first "to recover from a
    crash's leftover state", then for real.
  - Badge-o-techno fills a reused buffer with viper DSP in a background thread and `write`s it.
- A **MAX98357A** I2S amplifier breakout (3 W class D, drives a small speaker directly; BCLK,
  LRC, DIN plus GAIN / SD) on a hexpansion breakout board takes the same three pins and the same
  code: the choice is headphones / line out (PCM5102A) or a speaker (MAX98357A).
- The ports can't say what's on them unless the hexpansion has an EEPROM header
  (`hexpansion_headers`, its `friendly_name`, as `keyboard_fitted()` reads): the AudioHexpansion
  design is the badge team's breakout, which has the EEPROM footprint, so it may or may not
  carry one.

## Design
**`i2s_sound.py`** (shared, badge only), behind the platform's existing sound interface
(`sound_ok`, `sound(name)`, `sound_step()`), so `ace.py` and `game.py` don't change:

- **Synthesis on the fly, not recorded sounds.** Pre-rendered PCM for 15 sounds at 11 kHz would
  be about 300 KB of heap: too much for the badge (CLAUDE.md, garbage and heap). Instead a few
  voices, one per channel as Elite's (`sfx.CHANNELS`: a new sound replaces the one on its
  channel), each stepping through its sound's parts: square waves at the step's frequency and
  level, noise (a cheap random generator held for `rate / |f|` samples) for negative
  frequencies. Mixed into one reused `bytearray`.
- **Rate**: 11025 Hz mono 16-bit to start (the BBC Micro's sounds are low-fi; half the work of
  22050). Measure, then decide.
- **Never blocking the frame**: non-blocking `I2S.irq` refills (double buffering, two chunks of
  about 512 samples, 46 ms each), or Badge-o-techno's background thread. `ibuf` big enough to
  ride out the game's garbage collections (100-180 ms each, about every 100 flight frames since
  build 108): about 250-300 ms, 5.5-6.6 KB at 11025 Hz.
- **Viper** for the inner loop (a voice's samples into the buffer, whole numbers only): about
  440 samples a 40 ms frame; aim for under 2 ms a frame. No floats, no new objects per frame.
- **Silence**: when nothing plays, write zeros (or stop and deinit after a while; check whether
  the PCM5102A clicks on start and stop).
- **Volume**: a software scale (the levels in `sfx.py` are 0-126); Options > SOUND could become
  OFF / LOW / HIGH.
- **Which port**: Options > SOUND gets a port line (PORT 1-6, default 2 as BadgeRadio), saved in
  options.json; or found by a hexpansion header's name if it has one. The Keyboard Hexpansion
  (port 4 on Brian's badge) and the Qwiic Buzzer's port are skipped. The Qwiic buzzer stays as
  the fallback when no I2S port is set.
- **Releasing it**: deinit on leaving the game (`minimise`, crash path), so BadgeRadio and
  Badge-o-techno can open I2S 0 afterwards; open with the small "recovery" instance first, as
  they do.

The same synthesis also makes a WAV on a PC (CPython, the tests): `tests/test_sound.py` can
compare it with the Pi's mixer output, sound by sound.

## Steps
- **S0, hardware and a REPL check** (Brian's OK needed for the badge): get an AudioHexpansion (or
  a breakout hexpansion with a MAX98357A); on the badge, `from machine import I2S` and play a
  1 kHz square wave from the REPL on port 2, as BadgeRadio sets it up. Note any start / stop
  click, and whether the port's EEPROM says anything.
- **S1, the synthesiser on a PC**: `i2s_sound.py` with a stand-in `I2S`, rendering every sound
  of `sfx.py` to WAV; compare with the Pi; tests for voices, channels (flush), parts mixed,
  levels, noise, no allocation per frame.
- **S2, on the badge**: viper inner loop, irq or thread, the frame-time and garbage cost
  measured on the badge (`PERF` lines, `gc.mem_alloc()` round a frame), as for build 108.
- **S3, the options**: SOUND port and volume, saved; the fallback to the Qwiic buzzer; release on
  exit.
- **S4**: notes, the key guide, a release.

## Choices for Brian (recommendations first)
1. **Hardware**: the **AudioHexpansion** (PCM5102A, headphones / line out; known to work on the
  badge, with apps already on the store) first, recommended; a MAX98357A speaker amp on a
  breakout hexpansion second (same code; louder, no headphones needed).
2. **Port**: chosen in Options, default 2 (recommended); or a fixed port.
3. **Rate**: 11025 Hz (recommended), 22050 if the badge has the time.
4. **Thread or irq**: irq first (no thread to manage alongside the firmware's scheduler); a
  thread as Badge-o-techno if the irq can't keep up.

## Not covered
The Tufty 2350 has no free I2S pins (its Qw/ST port is I2C), so it keeps the Qwiic buzzer; the
Presto has its own PWM buzzer (`hosts/presto/PLAN.md`); the Pi already mixes in pygame.
