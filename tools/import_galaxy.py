#!/usr/bin/env python3
"""Read the galaxy's starting numbers, the market's goods and the equipment
prices from the Elite source into game_data.py.

Usage:
    python3 import_galaxy.py PATH [PATH ...] [-o game_data.py]

PATH is an .asm file, or a directory that is searched recursively for *.asm,
for example your own clone of
github.com/markmoxon/elite-source-code-bbc-micro-disc

It takes these things from the source, and nothing else:
  - the three 16-bit seeds that every star system is worked out from
  - the 32 letter pairs that system names are built from
  - where a new commander starts (chart position) and with how much fuel
  - the market's goods table (QQ23): each good's name (from the comment on
    its line), base price, economic factor, unit, base quantity and mask
  - the equipment price list (PRXS): each item's name (from the comment on
    its line) and price in tenths of a credit
  - for the system description sentence ("goat soup", PDESC): the extended
    text tokens (TKN1) that it can reach from token 5, the table of random
    choices (MTIN) and the two-letter tokens (TKN2)
  - for the missions: the briefing texts (extended tokens 10, 11, 15 and
    216-223, and the two standard tokens they print, read from the comments
    on their lines), the special system sentences (RUTOK) and where they are
    said (RUPLA, RUGAL)

How systems and prices are worked out from these is written afresh in
galaxy.py and market.py.

Licensing: Elite is (c) Acornsoft 1984 and that repository has no licence, so
game_data.py is for your own use: don't publish it. It is listed in
.gitignore, like ship_data.py.
"""
import argparse
import os
import re
import sys

SEED = re.compile(r"^\s*EQUW\s+&([0-9A-Fa-f]{4})\s*\\\s*QQ21\s*=\s*Seed s([012])\b")
BYTE = re.compile(r"^\s*EQUB\s+(\d+)\s*\\\s*(QQ0|QQ1|QQ14)\s*=")
LABEL = re.compile(r"^\.([A-Za-z_][A-Za-z0-9_]*)\s*$")
PAIR = re.compile(r'^\s*EQUS\s+"(..)"')
# a line of the equipment prices: EQUW price \ n  Name   12.3 Cr
EQUIP = re.compile(r"^\s*EQUW\s+(\d+)\s*\\\s*(\d+)\s+(.+?)\s{2,}[\d.]+\s*Cr")
# a line of the goods table: ITEM price, factor, 'unit', quantity, %mask \ n = Name
# the extended tokens' macros (TKN1): ECHR 'x', ETOK n, ETWO 'a', 'b', ERND n,
# EJMP n, and EQUB VE at the end of each token
TOKEN_LINE = re.compile(r"^\s*(ECHR|ETOK|ETWO|ERND|EJMP|TOKN|EQUB)\s+(.*?)\s*(\\.*)?$")
# a standard text token's text, from the comment on its first line:
# \ Token 117:    "MILITARY  LASER"
STD_TOKEN = re.compile(r'\\\s*Token\s+(\d+):\s*"([^"]*)"')
# RUPLA / RUGAL: EQUB 211 or EQUB &80
TABLE_BYTE = re.compile(r"^\s*EQUB\s+(&[0-9A-Fa-f]+|\d+)")
QUOTED = re.compile(r"'(.)'")
NUMBER = re.compile(r"^\s*EQUB\s+(\d+)")
ITEM = re.compile(r"^\s*ITEM\s+(\d+)\s*,\s*(-?\d+)\s*,\s*'([tkg])'\s*,\s*(\d+)\s*,"
                  r"\s*%([01]{8})\s*\\\s*(\d+)\s*=\s*(.+?)\s*$")


def find_sources(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for name in sorted(files):
                    if name.lower().endswith(".asm"):
                        yield os.path.join(root, name)
        else:
            yield p


def scan_tokens(path, found):
    """The extended tokens (TKN1), the random-choice table (MTIN) and the
    two-letter tokens (TKN2), from the first file that has them. Tokens are
    kept as lists of ('kind', value) until the two-letter table is known."""
    block = None
    tokens = []
    rutok = []
    cur = []
    mtin = []
    tkn2 = []
    rupla = []
    rugal = []
    std = found.setdefault("std", {})
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = STD_TOKEN.search(line)
            if m and line.lstrip()[:4] in ("CHAR", "TWOK", "RTOK", "CONT"):
                std.setdefault(int(m.group(1)), m.group(2))
            m = LABEL.match(line)
            if m:
                block = m.group(1) if m.group(1) in ("TKN1", "MTIN", "TKN2", "RUTOK",
                                                     "RUPLA", "RUGAL") else None
                cur = []
                continue
            if block in ("RUPLA", "RUGAL"):
                m = TABLE_BYTE.match(line)
                if m:
                    v = m.group(1)
                    (rupla if block == "RUPLA" else rugal).append(
                        int(v[1:], 16) if v[0] == "&" else int(v))
                continue
            if block in ("TKN1", "RUTOK"):
                into = tokens if block == "TKN1" else rutok
                m = TOKEN_LINE.match(line)
                if not m:
                    continue
                kind, arg = m.group(1), m.group(2)
                if kind == "EQUB":
                    if arg.strip() == "VE":
                        into.append(cur)
                        cur = []
                    continue
                if kind == "TOKN":
                    cur.append(("std", int(arg.split()[0].strip(","))))
                    continue
                if kind == "ECHR" or kind == "ETWO":
                    q = QUOTED.findall(arg)
                    if kind == "ECHR" and len(q) == 1:
                        cur.append(("c", 39 if q[0] == "`" else ord(q[0])))
                    elif kind == "ETWO" and len(q) == 2:
                        cur.append(("two", q[0] + q[1]))
                else:
                    n = int(arg.split()[0].strip(","))
                    cur.append(("b", n + 91 if kind == "ERND" else n))
            elif block == "MTIN":
                m = NUMBER.match(line)
                if m:
                    mtin.append(int(m.group(1)))
            elif block == "TKN2":
                m = PAIR.match(line)
                if m:
                    tkn2.append(m.group(1))
                elif re.match(r"^\s*EQUB\s+12\s*,\s*10", line):
                    tkn2.append("\x0c\x0a")
    if len(tokens) > 200 and "tkn1" not in found:
        found["tkn1"] = tokens
    if len(rutok) > 20 and "rutok" not in found:
        found["rutok"] = rutok
    if rupla and len(rupla) == len(rugal) and "rupla" not in found:
        found["rupla"] = rupla
        found["rugal"] = rugal
    if len(mtin) >= 38 and "mtin" not in found:
        found["mtin"] = mtin[:38]
    if len(tkn2) >= 13 and "tkn2" not in found:
        found["tkn2"] = tkn2


# where the mission texts start: the briefings and debriefings (10, 11, 15,
# 222, 223), "INCOMING MESSAGE" (216), the captains' names (217-219) and the
# Constrictor's whereabouts (220, 221)
MISSION_TOKENS = (10, 11, 15, 216, 217, 218, 219, 220, 221, 222, 223)


def _pairs(found):
    # 215 is {crlf} (written ETWO '-', '-'); TKN2 is followed in memory by the
    # 32 name pairs (QQ16), which two-letter tokens from 228 on read
    q = found["pairs"]
    return ["--"] + found["tkn2"][1:] + [q[i:i + 2] for i in range(0, len(q), 2)]


def _encode(token, pairs, std, todo, mtin):
    """One token as bytes: 1-31 jumps, 32-90 letters, 91-128 random choices
    (MTIN), 129-214 other tokens, 215 and up pairs. A standard token (TOKN,
    shown after jump 6) is written out as its letters."""
    b = bytearray()
    for kind, v in token:
        if kind == "c":
            b.append(v)
        elif kind == "two":
            b.append(215 + pairs.index(v))
        elif kind == "std":
            for ch in re.sub(r"\{[^}]*\}", "", std[v]):
                b.append(ord(ch))
        else:
            b.append(v)
            if 91 <= v <= 128:
                todo.extend(range(mtin[v - 91], mtin[v - 91] + 5))
            elif 129 <= v <= 214:
                todo.append(v)
    return bytes(b)


def description_tokens(found):
    """TKN1's tokens that the description and the mission texts can reach
    from token 5 (and 153, "IAN", which MT17 prints, and MISSION_TOKENS),
    and from the special system sentences (RUTOK), decoded (see _encode)."""
    pairs = _pairs(found)
    tokens = found["tkn1"]
    mtin = found["mtin"]
    std = found.get("std", {})
    out = {}
    todo = [5, 153] + list(MISSION_TOKENS)
    rutok = [_encode(t, pairs, std, todo, mtin) for t in found["rutok"]]
    while todo:
        n = todo.pop()
        if n in out or n >= len(tokens):
            continue
        out[n] = _encode(tokens[n], pairs, std, todo, mtin)
    return out, rutok


def scan(path, found):
    """Add what this file has to found, keeping the first copy of each thing."""
    scan_tokens(path, found)
    in_pairs = False
    in_goods = False
    in_equip = False
    pairs = []
    goods = []
    equip = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LABEL.match(line)
            if m:
                if in_pairs and pairs:
                    found.setdefault("pairs", "".join(pairs))
                if in_goods and goods:
                    found.setdefault("goods", goods)
                if in_equip and equip:
                    found.setdefault("equip", equip)
                in_pairs = m.group(1) == "QQ16"
                in_goods = m.group(1) == "QQ23"
                in_equip = m.group(1) == "PRXS"
                pairs = []
                goods = []
                equip = []
                continue
            if in_equip:
                m = EQUIP.match(line)
                if m:
                    price, n, name = m.groups()
                    if int(n) == len(equip):
                        equip.append((name.split(",")[0].strip().upper(), int(price)))
                elif line.strip() and not line.lstrip().startswith("\\"):
                    found.setdefault("equip", equip)
                    in_equip = False
                continue
            if in_goods:
                m = ITEM.match(line)
                if m:
                    price, factor, unit, qty, mask, n, name = m.groups()
                    if int(n) == len(goods):
                        goods.append((name.upper(), int(price), int(factor), unit,
                                      int(qty), int(mask, 2)))
                elif line.strip() and not line.lstrip().startswith("\\"):
                    found.setdefault("goods", goods)
                    in_goods = False
                continue
            if in_pairs:
                m = PAIR.match(line)
                if m:
                    pairs.append(m.group(1))
                elif line.strip() and not line.lstrip().startswith("\\"):
                    found.setdefault("pairs", "".join(pairs))
                    in_pairs = False
                continue
            m = SEED.match(line)
            if m:
                found.setdefault("seed%s" % m.group(2), int(m.group(1), 16))
                continue
            m = BYTE.match(line)
            if m:
                found.setdefault(m.group(2), int(m.group(1)))
    if in_pairs and pairs:
        found.setdefault("pairs", "".join(pairs))
    if in_goods and goods:
        found.setdefault("goods", goods)
    if in_equip and equip:
        found.setdefault("equip", equip)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--output", default="game_data.py")
    args = ap.parse_args()

    found = {}
    for path in find_sources(args.paths):
        scan(path, found)
    missing = [k for k in ("seed0", "seed1", "seed2", "pairs", "QQ0", "QQ1", "QQ14", "goods", "equip",
                           "tkn1", "mtin", "tkn2", "rutok", "rupla")
               if k not in found]
    if missing:
        sys.exit("Not found in the .asm files under %s: %s" % (
            " ".join(args.paths), ", ".join(missing)))
    if len(found["pairs"]) != 64:
        sys.exit("Expected 32 letter pairs after .QQ16, found %d letters" % len(found["pairs"]))
    if len(found["goods"]) != 17:
        sys.exit("Expected 17 goods after .QQ23, found %d" % len(found["goods"]))
    if len(found["equip"]) != 14:
        sys.exit("Expected 14 equipment prices after .PRXS, found %d" % len(found["equip"]))

    desc, rutok = description_tokens(found)
    out = [
        '"""Galaxy starting numbers for Ace Commander, generated by import_galaxy.py.',
        "",
        "Derived from Elite (c) Acornsoft 1984. For personal use only: do not",
        "publish this file.",
        '"""',
        "# the three seeds every star system in the first galaxy is worked out from",
        "SEEDS = (0x%04X, 0x%04X, 0x%04X)" % (found["seed0"], found["seed1"], found["seed2"]),
        "# the 32 letter pairs that system names are built from",
        "PAIRS = %r" % found["pairs"],
        "# where a new commander starts on the chart, and the fuel in tenths of a light year",
        "START_XY = (%d, %d)" % (found["QQ0"], found["QQ1"]),
        "START_FUEL = %d" % found["QQ14"],
        "# the market's goods: (name, base price, economic factor, unit, base quantity, mask)",
        "GOODS = (",
    ] + ["    %r," % (g,) for g in found["goods"]] + [
        ")",
        "# the equipment: (name, price in tenths of a credit; fuel's is worked out)",
        "EQUIPMENT = (",
    ] + ["    %r," % (e,) for e in found["equip"]] + [
        ")",
        "# the system description sentence (describe.py): the extended tokens it",
        "# can reach, decoded; the random choices (each the first of five tokens);",
        "# the two-letter tokens from 215 (TKN2), followed in memory by the 32 name",
        "# pairs (QQ16), which the random names (MT18) also read",
        "DESC_TOKENS = {",
    ] + ["    %d: %r," % (k, v) for k, v in sorted(desc.items())] + [
        "}",
        "# the missions' special system sentences (RUTOK, numbered from 0), and",
        "# where they are said: (system, galaxy + 128 if always, not just during",
        "# the Constrictor mission) (RUPLA, RUGAL)",
        "DESC_RUTOK = (",
    ] + ["    %r," % (v,) for v in rutok] + [
        ")",
        "DESC_RU = %r" % (tuple(zip(found["rupla"], found["rugal"])),),
        "DESC_MTIN = %r" % bytes(found["mtin"]),
        "DESC_PAIRS = %r" % ("".join(found["tkn2"]) + found["pairs"]),
        "",
    ]
    with open(args.output, "w") as f:
        f.write("\n".join(out))
    print("Wrote %s" % args.output)


if __name__ == "__main__":
    main()
