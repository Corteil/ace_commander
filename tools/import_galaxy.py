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


def scan(path, found):
    """Add what this file has to found, keeping the first copy of each thing."""
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
    missing = [k for k in ("seed0", "seed1", "seed2", "pairs", "QQ0", "QQ1", "QQ14", "goods", "equip")
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
        "",
    ]
    with open(args.output, "w") as f:
        f.write("\n".join(out))
    print("Wrote %s" % args.output)


if __name__ == "__main__":
    main()
