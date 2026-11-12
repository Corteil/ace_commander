#!/usr/bin/env python3
"""Convert Elite ship blueprints into ship_data.py for the badge demo.

Usage:
    python3 import_ships.py PATH [PATH ...] [-o ship_data.py] [--list]
                            [--only SHIP_VIPER SHIP_MAMBA ...]

PATH is an .asm file, or a directory that is searched recursively for *.asm,
for example your own clone of github.com/markmoxon/elite-a-source-code-bbc-micro

The ship data is read from the VERTEX, EDGE and FACE macros that follow each
.SHIP_xxx label:

    VERTEX x, y, z, face1, face2, face3, face4, visibility
    EDGE   vertex1, vertex2, face1, face2, visibility
    FACE   normal_x, normal_y, normal_z, visibility

Copy the generated ship_data.py next to app.py on the badge. The app has no
ships of its own: without this file it only shows a "ship_data.py not found"
message.

Licensing: Elite is (c) Acornsoft 1984 and that repository has no licence, so
the generated file is for your own use. Don't publish it, for example in the
badge app store.
"""
import argparse
import os
import re
import sys

LABEL = re.compile(r"^\.([A-Za-z0-9_]+)")
MACRO = re.compile(r"^\s*(VERTEX|EDGE|FACE)\b(.*)$", re.IGNORECASE)
SAFE = re.compile(r"^[0-9a-fA-FxX&+\-*/() ]+$")
FIRST = (
    "SHIP_COBRA_MK_3", "SHIP_VIPER", "SHIP_SIDEWINDER",
    "SHIP_THARGOID", "SHIP_CANISTER",
)


def warn(msg):
    print("warning: " + msg, file=sys.stderr)


def number(text):
    """Evaluate a small integer expression such as -12, 6*4 or &1F."""
    text = text.strip().replace("&", "0x")
    if not SAFE.match(text):
        raise ValueError(text)
    return int(eval(text, {"__builtins__": {}}, {}))


SUBLABELS = ("_VERTICES", "_EDGES", "_FACES")
BORROW = re.compile(r"SHIP_([A-Z0-9_]+?)_EDGES\s*-\s*SHIP_([A-Z0-9_]+)")
NO_FACE = 15  # an edge between "face 15" and "face 15" belongs to no face


def finish(ships):
    """Fill in borrowed edge lists, and give face-less edges a face that is
    always visible (a zero normal, which the app treats as always drawn)."""
    for rec in ships.values():
        src = ships.get(rec.get("edges_from"))
        if not rec["edges"] and src and src["edges"]:
            rec["edges"] = list(src["edges"])
        nf = len(rec["faces"])
        if nf and any(NO_FACE >= nf and NO_FACE in (e[2], e[3]) for e in rec["edges"]):
            rec["edges"] = [(a, b, nf if f1 == NO_FACE else f1, nf if f2 == NO_FACE else f2)
                            for a, b, f1, f2 in rec["edges"]]
            rec["faces"] = list(rec["faces"]) + [(0, 0, 0)]


def merge(ships, found):
    """Add one file's ships. The same ship appears in several files (one per
    disc variant), so keep the first copy and warn if a later one differs."""
    for name, rec in found:
        old = ships.get(name)
        if old is None:
            ships[name] = rec
        elif (old["verts"], old["edges"], old["faces"]) != (rec["verts"], rec["edges"], rec["faces"]):
            warn("%s at %s differs from the copy at %s, keeping the first" % (
                name, rec["where"], old["where"]))


def scan_file(path):
    found = []
    current = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            m = LABEL.match(line)
            if m:
                name = m.group(1)
                if name.endswith(SUBLABELS):
                    pass  # still inside the current ship's data
                elif name.startswith("SHIP_"):
                    current = {"verts": [], "edges": [], "faces": [],
                               "where": "%s:%d" % (path, lineno)}
                    found.append((name, current))
                else:
                    current = None
                continue
            if current is None:
                continue
            # a ship can borrow another ship's edge list (the Thargon uses the
            # canister's), which its header gives as HI(SHIP_X_EDGES - SHIP_Y)
            m = BORROW.search(line)
            if m and m.group(1) != m.group(2) and m.group(2) == found[-1][0][5:]:
                current["edges_from"] = "SHIP_" + m.group(1)
            m = MACRO.match(line)
            if not m:
                continue
            kind = m.group(1).upper()
            body = m.group(2).split("\\", 1)[0]  # BeebAsm comments start with \
            try:
                args = [number(p) for p in body.split(",") if p.strip()]
            except (ValueError, SyntaxError):
                warn("%s:%d: can't read %r" % (path, lineno, line.strip()))
                continue
            if kind == "VERTEX" and len(args) >= 3:
                current["verts"].append(tuple(args[:3]))
            elif kind == "EDGE" and len(args) >= 4:
                current["edges"].append(tuple(args[:4]))
            elif kind == "FACE" and len(args) >= 3:
                current["faces"].append(tuple(args[:3]))
            else:
                warn("%s:%d: wrong number of arguments for %s" % (path, lineno, kind))
    return found


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


def is_valid(label, ship):
    nv, nf = len(ship["verts"]), len(ship["faces"])
    if not (nv and nf and ship["edges"]):
        return False
    for a, b, f1, f2 in ship["edges"]:
        if not (0 <= a < nv and 0 <= b < nv and 0 <= f1 < nf and 0 <= f2 < nf):
            warn("%s: edge refers to a vertex or face that doesn't exist, skipped" % label)
            return False
    return True


def display_name(label):
    s = label[len("SHIP_"):].replace("_", " ")
    return re.sub(r"\bMK ([123])\b", lambda m: "MK " + "I" * int(m.group(1)), s)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("-o", "--output", default="ship_data.py")
    ap.add_argument("--list", action="store_true", help="list the ships found and exit")
    ap.add_argument("--only", nargs="+", metavar="SHIP_NAME",
                    help="include just these ships, in this order")
    args = ap.parse_args()

    ships = {}
    for path in find_sources(args.paths):
        merge(ships, scan_file(path))
    finish(ships)
    ships = {k: v for k, v in ships.items() if is_valid(k, v)}
    if not ships:
        sys.exit("No ship blueprints found. Looked for VERTEX/EDGE/FACE macros "
                 "after .SHIP_xxx labels in the .asm files under: " + " ".join(args.paths))

    if args.only:
        missing = [n for n in args.only if n not in ships]
        if missing:
            sys.exit("Not found: " + ", ".join(missing))
        order = list(args.only)
    else:
        order = [n for n in FIRST if n in ships]
        order += sorted(n for n in ships if n not in order)

    if args.list:
        for n in order:
            s = ships[n]
            print("%-28s %3d vertices %3d edges %3d faces  (%s)" % (
                n, len(s["verts"]), len(s["edges"]), len(s["faces"]), s["where"]))
        return

    out = [
        '"""Ship blueprints for the Elite demo, generated by import_ships.py.',
        "",
        "Derived from Elite (c) Acornsoft 1984. For personal use only: do not",
        "publish this file.",
        "",
        "Each entry is (name, vertices, edges, face normals), where an edge is",
        '(vertex, vertex, face, face).',
        '"""',
        "SHIPS = (",
    ]
    for n in order:
        s = ships[n]
        out.append("    (%r," % display_name(n))
        out.append("     %r," % (tuple(s["verts"]),))
        out.append("     %r," % (tuple(s["edges"]),))
        out.append("     %r)," % (tuple(s["faces"]),))
    out.append(")")
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("Wrote %d ships to %s" % (len(order), args.output))


if __name__ == "__main__":
    main()
