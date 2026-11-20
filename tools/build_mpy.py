"""Build a compiled copy of the app for the badge: .mpy instead of .py.

The badge otherwise compiles every module each time the game starts (the
loading screen exists because of it: game.py alone takes over a second), and
the source is about three times the size of the compiled code (about 496 KB
against 176 KB, 2026-11-20). This makes the compiled copy in a folder; it
doesn't touch the repo's files.

    python3 tools/build_mpy.py                  # build into build/badge/ace_commander
    python3 tools/build_mpy.py --elite          # with your own Elite files (your badge only)
    python3 tools/build_mpy.py --elite-only     # Elite's files instead of the game's own
    python3 tools/build_mpy.py --copy auto      # and copy it to the badge (mpremote)

- It must use the badge's own mpy-cross (MicroPython 1.28 on 2026-11-20): an
  .mpy from another version may not load. By default it looks for the one the
  firmware build on the Pi leaves behind (CLAUDE.md, "Tests"); --mpy-cross
  gives another, and --any-compiler allows a different version (a size check
  only: don't put that on a badge).
- app.py (the loading screen the launcher starts) and __init__.py stay
  source: tiny, and the launcher is known to work with them.
- --elite-only leaves out the game's own content (original_ships.py,
  original_data.py: about 32 KB built) for a badge that only plays Elite's;
  Options > DATA then isn't offered, and content.py falls back to Elite's if
  options.json still asks for the game's own.
- Only what a release holds goes in (git ls-files less .gitattributes'
  export-ignore), less README.md and LICENSE. Elite's files only with --elite, and never in a release.
- MicroPython imports x.py before x.mpy when both are there, so --copy also
  removes from the badge the .py of every module it copies as .mpy. To go
  back to source, copy the .py files again (deploy.bat) and the .mpy ones are
  simply not used.
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "build", "badge", "ace_commander")
PI_MPY_CROSS = os.path.expanduser(
    "~/Code/tildagon-firmware-builds/work/2026-v2.2.1-rc1-mirror/badge-2024-software/"
    "micropython/mpy-cross/build/mpy-cross")
BADGE_VERSION = "v1.28"
KEEP_SOURCE = ("app.py", "__init__.py")
ELITE = ("ship_data.py", "game_data.py")
OWN_CONTENT = ("original_ships.py", "original_data.py")
BADGE_DIR = ":/apps/ace_commander/"


def release_files():
    """The files a release holds, as git archive would make it."""
    files = subprocess.run(["git", "-C", REPO, "ls-files", "-c", "-o", "--exclude-standard"],
                           capture_output=True, text=True, check=True).stdout.split()
    files = sorted(set(f for f in files if os.path.isfile(os.path.join(REPO, f))))
    attrs = subprocess.run(["git", "-C", REPO, "check-attr", "export-ignore", "--"] + files,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    ignored = set(line.split(":")[0] for line in attrs if line.endswith(": set"))
    return [f for f in files if f not in ignored and f not in ELITE and "/" not in f
            and f not in ("README.md", "LICENSE")]     # not needed on the badge


def compiler(args):
    """The mpy-cross command to run, after checking its version."""
    if args.mpy_cross:
        cmd = [args.mpy_cross]
    elif os.path.exists(PI_MPY_CROSS):
        cmd = [PI_MPY_CROSS]
    elif args.any_compiler:
        cmd = [sys.executable, "-m", "mpy_cross"]
    else:
        sys.exit("The badge's mpy-cross isn't at %s.\nGive it with --mpy-cross PATH, or use "
                 "--any-compiler for a size check only (pip's mpy-cross is a newer MicroPython)."
                 % PI_MPY_CROSS)
    try:
        out = subprocess.run(cmd + ["--version"], capture_output=True, text=True).stdout
    except OSError as e:
        sys.exit("can't run %s: %s" % (cmd[0], e))
    if BADGE_VERSION not in out:
        if not args.any_compiler:
            sys.exit("%s is %s, not the badge's MicroPython %s. --any-compiler builds anyway "
                     "(a size check only)." % (cmd[0], out.strip() or "unknown", BADGE_VERSION))
        print("warning: %s is not the badge's %s: don't copy this build to a badge"
              % (out.strip() or cmd[0], BADGE_VERSION))
    return cmd


def build(args):
    cmd = compiler(args)
    out = os.path.abspath(args.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    files = release_files()
    if args.elite_only:
        args.elite = True
        files = [f for f in files if f not in OWN_CONTENT]
    if args.elite:
        missing = [f for f in ELITE if not os.path.exists(os.path.join(REPO, f))]
        if missing:
            sys.exit("--elite: %s not made yet (tools/import_ships.py, tools/import_galaxy.py)"
                     % ", ".join(missing))
        files += list(ELITE)
    made = []
    src = dst = 0
    for f in files:
        path = os.path.join(REPO, f)
        src += os.path.getsize(path)
        if f.endswith(".py") and f not in KEEP_SOURCE:
            target = os.path.join(out, f[:-3] + ".mpy")
            r = subprocess.run(cmd + ["-march=xtensawin", "-o", target, path],
                               capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit("compiling %s failed:\n%s%s" % (f, r.stdout, r.stderr))
        else:
            target = os.path.join(out, f)
            shutil.copy2(path, target)
        dst += os.path.getsize(target)
        made.append(os.path.basename(target))
    print("%d files in %s: %d KB as source, %d KB built" % (len(made), out, src // 1024, dst // 1024))
    return out, made


def mpremote(port, *words):
    return subprocess.run(["mpremote", "connect", port] + list(words), capture_output=True, text=True)


def copy(port, out, made):
    """Copy the build to the badge, remove the .py each .mpy replaces, and
    check every file's size there."""
    for name in made:
        r = mpremote(port, "fs", "cp", os.path.join(out, name), BADGE_DIR + name)
        if r.returncode != 0:
            sys.exit("copying %s failed (try again: the badge sometimes drops off USB):\n%s"
                     % (name, r.stderr))
    for name in made:
        if name.endswith(".mpy"):
            mpremote(port, "fs", "rm", BADGE_DIR + name[:-4] + ".py")    # fine if it isn't there
    r = mpremote(port, "fs", "ls", BADGE_DIR)
    sizes = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit():
            sizes[parts[1]] = int(parts[0])
    wrong = [n for n in made if sizes.get(n) != os.path.getsize(os.path.join(out, n))]
    if wrong:
        sys.exit("on the badge with the wrong size or missing: %s" % ", ".join(wrong))
    shadow = [n for n in made if n.endswith(".mpy") and n[:-4] + ".py" in sizes]
    if shadow:
        sys.exit("still on the badge as .py (they would be used instead): %s" % ", ".join(shadow))
    print("copied %d files to the badge, sizes checked; restart it with: mpremote connect %s reset"
          % (len(made), port))


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", default=OUT, help="the folder to build into (emptied first)")
    p.add_argument("--elite", action="store_true", help="include your own ship_data.py and game_data.py")
    p.add_argument("--elite-only", action="store_true",
                   help="Elite's files and not the game's own content (implies --elite)")
    p.add_argument("--mpy-cross", help="the badge's mpy-cross")
    p.add_argument("--any-compiler", action="store_true",
                   help="allow an mpy-cross that isn't the badge's version (size check only)")
    p.add_argument("--copy", metavar="PORT",
                   help="copy to the badge with mpremote (auto, or a port such as /dev/ttyACM0)")
    args = p.parse_args()
    out, made = build(args)
    if args.copy:
        copy(args.copy, out, made)


if __name__ == "__main__":
    main()
