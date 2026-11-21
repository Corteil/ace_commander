#!/usr/bin/env python3
"""Make the Tufty 2350 app folder: build/tufty/ace_commander/ (gitignored).

    python3 hosts/tufty/build_tufty.py            # the game's own content only
    python3 hosts/tufty/build_tufty.py --elite    # with your own Elite files (your Tufty only)
    python3 hosts/tufty/build_tufty.py --copy /media/pi/TUFTY   # and copy it to the TUFTY drive

The folder holds app/__init__.py (what Badgeware runs) and icon.png, the host's
modules (host_tufty, platform_tufty, controls_tufty, layout_tufty, dash_tufty,
ctx_tufty), and the game as the package ace_commander: the files a release
holds (as tools/build_mpy.py picks them), as source. On the Tufty it goes in
/system/apps/ace_commander, which MicroPython can't write: copy it with the
TUFTY drive (the Tufty's Mass Storage app, or a double tap of RESET).
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "build", "tufty", "ace_commander")
HOST_FILES = ("host_tufty.py", "platform_tufty.py", "controls_tufty.py", "layout_tufty.py",
              "dash_tufty.py", "ctx_tufty.py")
APP_FILES = ("__init__.py", "icon.png")
ELITE = ("ship_data.py", "game_data.py")
# the badge's own: its loading screen and its firmware side (never imported on the Tufty)
BADGE_ONLY = ("app.py", "platform_tildagon.py", "bench.py")


def game_files(elite):
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import build_mpy
    files = [f for f in build_mpy.release_files() if f.endswith(".py") and f not in BADGE_ONLY]
    if elite:
        files += [f for f in ELITE if os.path.exists(os.path.join(REPO, f))]
    return sorted(set(files))


def build(elite):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    pkg = os.path.join(OUT, "ace_commander")
    os.makedirs(pkg)
    for f in APP_FILES:
        shutil.copy2(os.path.join(HERE, "app", f), os.path.join(OUT, f))
    for f in HOST_FILES:
        shutil.copy2(os.path.join(HERE, f), os.path.join(OUT, f))
    files = game_files(elite)
    for f in files:
        shutil.copy2(os.path.join(REPO, f), os.path.join(pkg, f))
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print("%d game files + %d host files in %s: %d KB" % (len(files), len(HOST_FILES), OUT,
                                                          size // 1024))
    return OUT


def copy(drive):
    """Copy the folder to the TUFTY drive's apps folder, then flush it."""
    apps = os.path.join(drive, "apps")
    if not os.path.isdir(apps):
        sys.exit("no apps folder on %s: is the TUFTY drive mounted?" % drive)
    dest = os.path.join(apps, "ace_commander")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(OUT, dest)
    subprocess.run(["sync"], check=False)
    print("copied to", dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--elite", action="store_true", help="add your own Elite files")
    ap.add_argument("--copy", metavar="DRIVE", help="copy to the TUFTY drive (its mount point)")
    args = ap.parse_args()
    build(args.elite)
    if args.copy:
        copy(args.copy)


if __name__ == "__main__":
    main()
