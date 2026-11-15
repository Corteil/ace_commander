"""The app as the badge's app store installs it (build 58): the release
tarball (git archive, which leaves out what .gitattributes marks
export-ignore) unpacked into a folder named <owner>_<repo>, with none of
Elite's files. It must start, load, and play with its own content."""
import asyncio, io, os, shutil, subprocess, sys, tarfile
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import badge_stubs as bs
from badge_stubs import CountCtx

TMP = os.path.join(HERE, "install")
NAME = "Corteil_ace_commander"      # what the store calls the folder: owner_repo
shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(os.path.join(TMP, NAME))
# the files a release would hold: everything git keeps (or would keep), less
# what .gitattributes marks export-ignore, as git archive does
files = subprocess.run(["git", "-C", REPO, "ls-files", "-c", "-o", "--exclude-standard"],
                       capture_output=True, text=True, check=True).stdout.split()
files = sorted(set(f for f in files if os.path.exists(os.path.join(REPO, f))))
attrs = subprocess.run(["git", "-C", REPO, "check-attr", "export-ignore", "--"] + files,
                       capture_output=True, text=True, check=True).stdout.splitlines()
ignored = set(l.split(":")[0] for l in attrs if l.endswith(": set"))
names = [f for f in files if f not in ignored]
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w") as t:
    for f in names:
        t.add(os.path.join(REPO, f), arcname=f)
tar = buf.getvalue()
with tarfile.open(fileobj=io.BytesIO(tar)) as t:
    t.extractall(os.path.join(TMP, NAME))
# and git agrees about what export-ignore leaves out
for d in ("tests/test_app.py", "tools/shipmaker.py", "CLAUDE.md"):
    assert any(l.startswith(d + ":") and l.endswith(": set") for l in subprocess.run(
        ["git", "-C", REPO, "check-attr", "export-ignore", "--", d],
        capture_output=True, text=True).stdout.splitlines()), d

# only the app: no tests, tools, notes, or anything made from Elite
assert "app.py" in names and "tildagon.toml" in names and "LICENSE" in names
for bad in ("ship_data.py", "game_data.py", "CLAUDE.md", "DESIGN.md", "deploy.bat"):
    assert bad not in names, bad
assert not any(n.startswith(("tests", "tools")) for n in names), names
assert len(tar) < 600 * 1024, "the badge unpacks the whole tarball in memory: %d" % len(tar)
toml = open(os.path.join(TMP, NAME, "tildagon.toml")).read()
for key in ('license = "MIT"', 'url = "https://github.com/Corteil/ace_commander"',
            'category = "Games"'):
    assert key in toml, key
desc = [l for l in toml.split("\n") if l.startswith("description")][0]
assert len(desc.split('"')[1]) <= 140, "the store's limit"
print("release tarball: %d files, %d KB, only the app: ok" % (len(names), len(tar) // 1024))

# the badge's launcher imports <folder>.app and starts __app_export__
sys.path.insert(0, TMP)
bs.install()
loader = __import__(NAME + ".app", None, None, ["__app_export__"])
ld = loader.__app_export__()
frames = []


class Handed(Exception):
    pass


async def render_update():
    c = CountCtx(); ld.draw(c)
    frames.append([t[0] for t in c.texts])
    if ld.real is not None:
        raise Handed()


try:
    asyncio.run(ld.run(render_update))
except Handed:
    pass
assert ld.error is None and ld.real is not None, ld.error
ace = sys.modules[NAME + ".ace"]
content = sys.modules[NAME + ".content"]
assert content.OWN and not content.HAVE_ELITE and len(ace.SHIPS) == 31
assert ace.APP_DIR.endswith(NAME), "saves next to the app, wherever it is installed"
ace.SAVE_PATH = os.path.join(TMP, NAME, "commander.json")
a = ld.real
bs.choose(a, "NEW COMMANDER"); bs.tick(a, fresh=["C"])
assert a.mode == "docked" and a.galaxy.system(a.cmdr.system).name == "DAENOR"
assert os.path.exists(ace.SAVE_PATH)
a.dock.go(0); bs.tick(a, fresh=["C"])
for _ in range(300):
    bs.tick(a)
c = CountCtx(); a.draw(c)
assert a.mode == "flight"
shutil.rmtree(TMP, ignore_errors=True)
print("installed as %s: loads, starts at Daenor with its own content, flies: ok" % NAME)
print("ALL INSTALL TESTS PASSED")
