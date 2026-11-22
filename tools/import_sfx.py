"""Make elite_sfx.py, Elite's sounds in the game's tone format (sfx.py), from
your own clone of the BBC Micro disc source:

    python3 tools/import_sfx.py ~/Code/elite-source-code-bbc-micro-disc

It reads the sound table SFX (the four SOUND bytes of each of Elite's ten
sounds) from the main source and the four sound envelopes E% from the loader,
plays each SOUND on a model of the BBC Micro's sound system (envelopes stepped
every centisecond), and writes the result as runs of (Hz, ms, level) steps.
The game uses it with Elite's data (Options > DATA: ELITE), else its own sounds.

elite_sfx.py is derived from Elite (c) Acornsoft 1984: like ship_data.py and
game_data.py it is gitignored and must not be committed or published.

Which game event plays which Elite sound is read from where the original calls
them (NOISE, BEEP, EXNO, EXNO3 in the flight source):
    laser    0  our laser firing (MA68)
    hit      24 our laser strikes a ship (EXNO)
    explode  24 a ship we killed (EXNO2 -> EXNO)
    hurt     8  lasers hitting our shields
    crash    16 + 24 together: a collision, hit with no shields left, a missile
                exploding, a canister lost scooping (EXNO3)
    die      16 + 24 together (DEATH -> EXNO3)
    lock     32 short high beep: missile locked on (BEEP)
    unarm    40 long low beep: missile unarmed
    beep     32 short high beep: FUEL SCOOPS ON, ENERGY LOW (their {beep}), and
                docked after a trade or a refusal (dn, dn2)
    boop     40 long low beep: the in-system jump refused (WA1), a search that
                finds nothing (HME6)
    missile  48 our missile launched (FRMIS)
    incoming 48 an enemy's missile launched (SFRMIS)
    launch   48 launching from the station (LAUN)
    jump     56 the hyperspace tunnel (LL164)
    ecm      64 E.C.M. on (until it goes off: 72)
Everything else (countdowns, scooping, docking, the energy bomb, combat
practice's waves and upgrades) is silent, as in Elite.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "elite_sfx.py")
FLIGHT = "1-source-files/main-sources/elite-source-flight.asm"
DOCKED = "1-source-files/main-sources/elite-source-docked.asm"
LOADER = "1-source-files/main-sources/elite-loader3.asm"

EVENTS = {      # event: (priority, the Elite sound numbers played together)
    "laser": (1, (0,)),
    "hit": (2, (24,)),
    "explode": (3, (24,)),
    "hurt": (2, (8,)),
    "crash": (4, (24, 16)),
    "die": (5, (24, 16)),
    "lock": (2, (32,)),
    "unarm": (2, (40,)),
    "beep": (2, (32,)),
    "boop": (2, (40,)),
    "missile": (3, (48,)),
    "incoming": (4, (48,)),
    "launch": (3, (48,)),
    "jump": (5, (56,)),
    "ecm": (3, (64,)),
}
ECM_CS = 50             # E.C.M. on lasts until it goes off: the game's E.C.M. is 0.5 s
RELEASE_CS = 100        # an envelope's release is cut off after this long
SHIFT = (7800, 3900, 1950)  # the noise channel's three fixed rates (Hz), pitch & 3 = 0-2;
                            # 3 follows channel 1's tone (twice its frequency here)
QUIET = 8               # a part never louder than this (of 126) only steers the noise:
                        # Elite's death sound sweeps channel 1, unheard, to colour it


def _num(t):
    t = t.strip()
    if t.startswith("&"):
        return int(t[1:], 16)
    return int(t)


def read_sfx(src):
    """{sound number: (channel, amplitude, pitch, duration)} from the SFX table."""
    for name in (FLIGHT, DOCKED):
        text = open(os.path.join(src, name)).read()
        m = re.search(r"^\.SFX\s*$(.*?)^\\ \*\*\*", text, re.M | re.S)
        if m:
            break
    else:
        sys.exit("no SFX table in %s" % src)
    out = {}
    for line in m.group(1).splitlines():
        line = line.split("\\")[0]
        if "EQUB" not in line:
            continue
        b = [_num(x) for x in line.split("EQUB")[1].split(",")]
        out[len(out) * 8] = (b[0], b[1], b[2], b[3])
    return out


def read_envelopes(src):
    """{envelope number: its 14 ENVELOPE parameters} from the loader's E%."""
    text = open(os.path.join(src, LOADER)).read()
    m = re.search(r"^\.E%\s*$(.*?)^\\ \*\*\*", text, re.M | re.S)
    if not m:
        sys.exit("no E% envelopes in %s" % src)
    out = {}
    for line in m.group(1).splitlines():
        line = line.split("\\")[0]
        if "EQUB" in line:
            b = [_num(x) for x in line.split("EQUB")[1].split(",")]
            out[b[0]] = b
    return out


def _signed(v):
    return v - 256 if v > 127 else v


def hz(p):
    """A BBC Micro SOUND pitch as Hz: 53 is middle C, 4 steps a semitone."""
    return int(round(261.63 * 2 ** (((p % 256) - 53) / 48.0)))


def play(sound, envs):
    """One SOUND as a list of centisecond (pitch, level 0-126) samples."""
    chan, amp, pitch, dur = sound
    chan &= 3
    amp = _signed(amp)
    cs = ECM_CS if dur == 255 else dur * 5
    out = []
    if amp <= 0:                        # a fixed volume, -15 loudest
        level = -amp * 126 // 15
        return chan, [(pitch, level)] * cs
    n, t, pi1, pi2, pi3, pn1, pn2, pn3, aa, ad, as_, ar, ala, ald = envs[amp]
    step = t & 127
    repeat = not (t & 128)
    pis = ((pi1, pn1), (pi2, pn2), (pi3, pn3))
    p = pitch
    sec, k = 0, 0                       # the pitch section and step within it
    level, phase = 0, "A"
    i = 0
    while True:
        if i % step == 0:               # the envelope moves on each step
            while sec < 3 and k >= pis[sec][1]:
                sec, k = sec + 1, 0
            if sec >= 3 and repeat:
                sec, k = 0, 0
                while sec < 3 and k >= pis[sec][1]:
                    sec, k = sec + 1, 0
            if sec < 3:
                p = (p + _signed(pis[sec][0] & 255)) % 256
                k += 1
            if i >= cs:
                phase = "R"
            if phase == "A":
                level += aa
                if level >= ala:
                    level, phase = ala, "D"
            elif phase == "D":
                level += ad
                if (ad < 0 and level <= ald) or (ad >= 0 and level >= ald):
                    level, phase = ald, "S"
            elif phase == "S":
                level += as_
            else:
                level += ar
            level = max(0, min(126, level))
        if i >= cs and (level <= 0 or i >= cs + RELEASE_CS):
            break
        out.append((p, level))
        i += 1
    return chan, out


def _noise(p, ch1):
    """The noise channel at pitch p as a step's frequency: white noise as -rate
    (Hz: how often it changes), periodic noise as the buzz it makes (rate / 15)."""
    if (p & 3) == 3:
        rate = hz(ch1) * 2 if ch1 is not None else SHIFT[1]
    else:
        rate = SHIFT[p & 3]
    return -rate if p & 4 else max(50, rate // 15)


def steps(sounds, envs):
    """SOUNDs played together as the game's parts: lists of (Hz, ms, level),
    a negative Hz noise changing that often, 0 a rest; runs merged. A quiet
    channel-1 part steers the noise and isn't kept itself. Also returns the
    channel of the first part kept (Elite restarts a sound on its channel)."""
    played = [play(s, envs) for s in sounds]
    steer = None
    for chan, samples in played:
        if chan == 1 and max([lv for p, lv in samples] or [0]) < QUIET:
            steer = samples
    parts = []
    first = None
    for chan, samples in played:
        if samples is steer:
            continue
        if first is None:
            first = chan
        out = []
        for i, (p, level) in enumerate(samples):
            if level <= 0:
                f, level = 0, 0
            elif chan == 0:                 # the noise channel
                f = _noise(p, steer[min(i, len(steer) - 1)][0] if steer else None)
            else:
                f = hz(p)
            if out and out[-1][0] == f and out[-1][2] == level:
                out[-1][1] += 10
            else:
                out.append([f, 10, level])
        while out and out[-1][0] == 0:
            out.pop()
        parts.append([tuple(x) for x in out])
    return first, parts


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.split("\n\n")[1])
    src = os.path.expanduser(sys.argv[1])
    sfx_table = read_sfx(src)
    envs = read_envelopes(src)
    lines = ['"""Elite\'s sounds in the game\'s tone format (sfx.py), made by',
             'tools/import_sfx.py from the BBC Micro disc source.',
             '',
             'DERIVED FROM ELITE (c) ACORNSOFT 1984: gitignored, never commit or publish it.',
             '"""',
             '',
             'SOUNDS = {']
    chans = {}
    for event, (prio, nums) in EVENTS.items():
        chan, parts = steps([sfx_table[n] for n in nums], envs)
        chans[event] = chan
        lines.append("    %r: (%d, %s)," % (event, prio, ", ".join(repr(p) for p in parts)))
    lines.append("}")
    lines.append("")
    lines.append("# the BBC Micro channel each plays on: a sound restarts one there (flush)")
    lines.append("CHANNELS = %r" % chans)
    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote %s: %d sounds from Elite's %d" % (OUT, len(EVENTS), len(sfx_table)))


if __name__ == "__main__":
    main()
