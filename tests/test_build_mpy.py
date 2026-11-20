"""tools/build_mpy.py: a compiled copy of the app for the badge. Needs pip's
mpy-cross (a size check: it is a newer MicroPython than the badge's, so
this proves the build's shape, not that the badge loads it)."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
try:
    import mpy_cross    # noqa: F401
except ImportError:
    print("SKIPPED: no mpy_cross (pip install mpy-cross)")
    sys.exit(0)

out = tempfile.mkdtemp(prefix="ace_mpy_")
tool = os.path.join(REPO, "tools", "build_mpy.py")
r = subprocess.run([sys.executable, tool, "--out", out], capture_output=True, text=True)
assert r.returncode != 0 or "v1.28" in r.stdout, "refuses a compiler that isn't the badge's"
r = subprocess.run([sys.executable, tool, "--any-compiler", "--out", out],
                   capture_output=True, text=True, check=True)
names = set(os.listdir(out))
assert {"app.py", "__init__.py", "tildagon.toml", "metadata.json"} <= names, names
assert "ace.mpy" in names and "game.mpy" in names and "ace.py" not in names
for bad in ("ship_data.py", "ship_data.mpy", "game_data.py", "game_data.mpy", "README.md", "CLAUDE.md"):
    assert bad not in names, bad
code = [n for n in os.listdir(REPO) if n.endswith(".py") and n not in ("ship_data.py", "game_data.py")]
for n in code:
    want = n if n in ("app.py", "__init__.py") else n[:-3] + ".mpy"
    assert want in names, ("missing", want)
src = sum(os.path.getsize(os.path.join(REPO, n)) for n in code)
built = sum(os.path.getsize(os.path.join(out, n)) for n in names if n.endswith((".mpy", ".py")))
assert built < src * 0.5, (built, src)
print("build: %d files, code %d KB as source, %d KB built: ok" % (len(names), src // 1024, built // 1024))
print("ALL BUILD TESTS PASSED")
