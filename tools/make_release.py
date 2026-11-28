"""Make a release (0.4.0 on): the badge's compiled app on the `release` branch,
and the Tufty's and the Pi's zips to attach to the GitHub release.

    python3 tools/make_release.py 0.4.0             # build and check, nothing pushed
    python3 tools/make_release.py 0.4.0 --commit    # and commit it to `release`, tag v0.4.0
    python3 tools/make_release.py 0.4.0 --push      # and push the branch and the tag

The badge's app store installs the tarball GitHub makes of the commit a release's
tag points at, so the compiled .mpy files must be committed there. They go on the
`release` branch (each release one commit, compiled from main), so main stays
source. app.py (the loader), __init__.py, tildagon.toml and metadata.json stay
source; app.py removes any old .py that a .mpy replaces, since the store's update
writes over the old folder without deleting anything (build 132).

Nothing Elite-derived goes into any of it: no ship_data.py / game_data.py (the
game then plays its own ships and galaxy, as every release has).

Made in build/release/ (gitignored):
    badge/ace_commander/              what the release branch holds
    ace_commander-badge-V.tar         the tarball as GitHub would make it (checked < 600 KB)
    ace_commander-tufty-V.zip         unzip into the TUFTY drive's apps/ folder
    ace_commander-pi-V.zip            unzip anywhere; python3 ace_commander/hosts/pi/run.py
Each zip holds its device's key guide as ace_commander/KEY_GUIDE.pdf (tools/make_key_guide.py;
needs ReportLab and the DejaVu fonts).
The GitHub release itself (notes, the two zips) is made afterwards, with gh.
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_mpy    # noqa: E402

OUT = os.path.join(REPO, "build", "release")
WORKTREE = os.path.join(OUT, "worktree")
BRANCH = "release"
LIMIT = 600 * 1024          # the badge unpacks the whole tarball in memory (tests/test_install.py)
ELITE = build_mpy.DERIVED     # Elite-derived: ship_data, game_data, elite_sfx
EXTRA = ("README.md", "LICENSE")    # on the release branch too, for anyone reading it on GitHub
PI_README = """Ace Commander {v} for the Raspberry Pi (or any computer with Python 3 and pygame)

    sudo apt install python3-pygame      (or: pip install pygame)
    unzip ace_commander-pi-{v}.zip
    python3 ace_commander/hosts/pi/run.py

Options: --layout elite (a 3D view over a dashboard; F10 switches), --full (full screen),
--wide (in the Elite layout, the screens use the window's whole width),
--sound (the game's sounds; Options > SOUND turns them off), --debug (the DEBUG menu). Keys: arrows steer, F1-F6 are the badge's buttons A-F, and the
rest are Elite's keys; a game pad works too. Every key and pad button: KEY_GUIDE.pdf. Saves go in ~/.local/share/ace_commander/.
A desktop shortcut: Exec=python3 /path/to/ace_commander/hosts/pi/run.py
"""


def git(*args, cwd=REPO, check=True):
    r = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit("git %s failed:\n%s%s" % (" ".join(args), r.stdout, r.stderr))
    return r.stdout.strip()


def versions():
    """The version in tildagon.toml and metadata.json."""
    import json
    toml = [l for l in open(os.path.join(REPO, "tildagon.toml")) if l.startswith("version")]
    t = toml[0].split("=", 1)[1].strip().strip('"') if toml else None
    m = json.load(open(os.path.join(REPO, "metadata.json"))).get("version")
    return t, m


def check_repo(v, need_clean):
    t, m = versions()
    if t != v or m != v:
        sys.exit("tildagon.toml says %s and metadata.json %s, not %s: change them first" % (t, m, v))
    if need_clean:
        if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
            sys.exit("not on main")
        if git("status", "--porcelain", "--untracked-files=no"):
            sys.exit("main has changes not committed")


def build_badge(v):
    out = os.path.join(OUT, "badge", "ace_commander")
    args = argparse.Namespace(out=out, elite=False, elite_only=False, mpy_cross=None,
                              any_compiler=False)
    build_mpy.build(args)
    for f in EXTRA:
        shutil.copy2(os.path.join(REPO, f), out)
    names = sorted(os.listdir(out))
    bad = [n for n in names if n[:-4] + ".py" in ELITE or n in ELITE]
    if bad:
        sys.exit("Elite-derived files in the build: %s" % bad)
    for need in ("app.py", "__init__.py", "tildagon.toml", "metadata.json", "ace.mpy", "game.mpy"):
        if need not in names:
            sys.exit("%s missing from the build" % need)
    stray = [n for n in names if n.endswith(".py") and n not in build_mpy.KEEP_SOURCE]
    if stray:
        sys.exit("left as source: %s" % stray)
    # the tarball as GitHub would make it: one folder, ustar
    tar_path = os.path.join(OUT, "ace_commander-badge-%s.tar" % v)
    with tarfile.open(tar_path, "w", format=tarfile.USTAR_FORMAT) as t:
        t.add(out, arcname="Corteil-ace_commander-" + v, recursive=True)
    size = os.path.getsize(tar_path)
    if size >= LIMIT:
        sys.exit("the badge tarball is %d KB, over %d KB" % (size // 1024, LIMIT // 1024))
    print("badge: %d files, tarball %d KB (limit %d KB)" % (len(names), size // 1024, LIMIT // 1024))
    return out


def key_guide(platform, folder):
    """The device's key guide into folder, as KEY_GUIDE.pdf."""
    import make_key_guide
    make_key_guide.make(platform, os.path.join(folder, "KEY_GUIDE.pdf"))


def zip_dir(path, folder, arc_root, skip=()):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if d not in skip and d != "__pycache__")
            for f in sorted(files):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, folder)
                if f in ELITE or f[:-4] + ".py" in ELITE:
                    sys.exit("Elite-derived file in %s: %s" % (path, rel))
                z.write(full, os.path.join(arc_root, rel))


def build_tufty(v):
    r = subprocess.run([sys.executable, os.path.join(REPO, "hosts", "tufty", "build_tufty.py"),
                        "--mpy"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("build_tufty failed:\n%s%s" % (r.stdout, r.stderr))
    folder = os.path.join(REPO, "build", "tufty", "ace_commander")
    key_guide("tufty", folder)
    path = os.path.join(OUT, "ace_commander-tufty-%s.zip" % v)
    zip_dir(path, folder, "ace_commander")
    print("tufty: %s, %d KB" % (os.path.basename(path), os.path.getsize(path) // 1024))
    return path


def build_pi(v):
    """The game as source (the Pi runs CPython) and hosts/pi, less its tests."""
    stage = os.path.join(OUT, "pi", "ace_commander")
    shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
    os.makedirs(stage)
    for f in build_mpy.release_files() + list(EXTRA):
        shutil.copy2(os.path.join(REPO, f), stage)
    os.makedirs(os.path.join(stage, "hosts"))
    for f in git("ls-files", "hosts/pi").split():      # what git keeps, less the tests
        if f.startswith("hosts/pi/tests/"):
            continue
        dst = os.path.join(stage, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(REPO, f), dst)
    with open(os.path.join(stage, "README_PI.txt"), "w") as f:
        f.write(PI_README.format(v=v))
    key_guide("pi", stage)
    path = os.path.join(OUT, "ace_commander-pi-%s.zip" % v)
    zip_dir(path, stage, "ace_commander")
    print("pi: %s, %d KB" % (os.path.basename(path), os.path.getsize(path) // 1024))
    return path


def commit_release(v, badge):
    """One commit on the release branch holding exactly the badge build, tagged."""
    tag = "v" + v
    if git("tag", "-l", tag):
        sys.exit("tag %s exists already" % tag)
    src = git("rev-parse", "--short", "HEAD")
    if os.path.exists(WORKTREE):
        git("worktree", "remove", "--force", WORKTREE)
    git("fetch", "-q", "origin", check=False)
    if git("ls-remote", "--heads", "origin", BRANCH):
        git("worktree", "add", "-B", BRANCH, WORKTREE, "origin/" + BRANCH)
    elif git("branch", "--list", BRANCH):
        git("worktree", "add", WORKTREE, BRANCH)
    else:
        git("worktree", "add", "--detach", WORKTREE)
        git("checkout", "--orphan", BRANCH, cwd=WORKTREE)
    for n in os.listdir(WORKTREE):
        if n != ".git":
            p = os.path.join(WORKTREE, n)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    git("rm", "-rq", "--cached", ".", cwd=WORKTREE, check=False)
    for n in os.listdir(badge):
        shutil.copy2(os.path.join(badge, n), WORKTREE)
    git("add", "-A", cwd=WORKTREE)
    git("commit", "-q", "-m", "Ace Commander %s (compiled from main %s)\n\n"
        "The badge app as the app store installs it: built by tools/make_release.py." % (v, src),
        cwd=WORKTREE)
    git("tag", "-a", tag, "-m", "Ace Commander " + v, cwd=WORKTREE)
    print("committed to %s and tagged %s: %s" % (BRANCH, tag, git("rev-parse", "--short", "HEAD", cwd=WORKTREE)))


def push(v):
    git("push", "-q", "origin", BRANCH, cwd=WORKTREE)
    git("push", "-q", "origin", "v" + v)
    print("pushed %s and v%s" % (BRANCH, v))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("version", help="e.g. 0.4.0 (tildagon.toml and metadata.json must say it)")
    ap.add_argument("--commit", action="store_true", help="commit to the release branch and tag")
    ap.add_argument("--push", action="store_true", help="also push the branch and the tag")
    a = ap.parse_args()
    check_repo(a.version, a.commit or a.push)
    shutil.rmtree(os.path.join(OUT, "badge"), ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    badge = build_badge(a.version)
    build_tufty(a.version)
    build_pi(a.version)
    if a.commit or a.push:
        commit_release(a.version, badge)
    if a.push:
        push(a.version)


if __name__ == "__main__":
    main()
