import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import PilCtx

OUT = os.path.join(HERE, "shots")
os.makedirs(OUT, exist_ok=True)
bs.install()
import ace_commander
mod = ace_commander.app
game = mod.game


def shot(a, name):
    c = PilCtx(3)
    a.draw(c)
    c.finish(os.path.join(OUT, name))


tick = bs.tick


def place(g, name, kind, x, y, z, nose):
    o = game.Obj(g.types[name], kind, float(x), float(y), float(z))
    d = game._unit(*nose)
    game._look(o.m, d[0], d[1], d[2])
    g.objs.append(o)
    return o


random.seed(3)
ace_commander.app.SAVE_PATH = os.path.join(OUT, "render_commander.json")
if os.path.exists(ace_commander.app.SAVE_PATH):
    os.remove(ace_commander.app.SAVE_PATH)
for n in os.listdir(OUT):
    if n.endswith(".png"):
        os.remove(os.path.join(OUT, n))
a = ace_commander.AceCommander()
for _ in range(60):         # let the Cobra arrive and tumble a bit
    tick(a)
shot(a, "1_title.png")
a.title.t = ace_commander.title.T_IN + ace_commander.title.T_HOLD + 0.62
tick(a, fresh=["RIGHT"])
shot(a, "1b_title_flyby.png")
a.title.t = 0.55; tick(a)
shot(a, "1c_title_arriving.png")
tick(a, fresh=["LEFT"])
bs.choose(a, "NEW COMMANDER")
shot(a, "1d_level.png")
tick(a, fresh=["CONFIRM"])
a.cmdr.add_kills(140)
g = a.game
g.spawn_t = g.rock_t = 1e9
g.objs[:] = []
cobra = place(g, "COBRA MK III", "ship", -120, 60, 900, (0.6, -0.2, -0.75))
cobra.state = "break"; cobra.t = 99; cobra.aim = [0.6, -0.2, -0.75]
viper = place(g, "VIPER", "ship", 380, -150, 1900, (-0.5, 0.3, -0.8))
viper.state = "break"; viper.t = 99; viper.aim = [-0.5, 0.3, -0.8]
krait = place(g, "KRAIT", "ship", 150, 420, 3400, (0, -0.4, -1))
krait.state = "break"; krait.t = 99; krait.aim = [0.0, -0.4, -1.0]
place(g, "SIDEWINDER", "ship", -2500, 300, 6500, (1, 0, -1)).state = "flee"
place(g, "ASTEROID", "rock", -700, -420, 2600, (1, 0.2, 0))
place(g, "CANISTER", "can", 260, 120, 1100, (0.3, 1, 0.2))
ms = place(g, "MISSILE", "missile", 600, 200, 2800, (-0.2, -0.1, -1)); ms.t = 12
place(g, "PYTHON", "ship", 1500, -200, -3000, (0, 0, 1)).state = "flee"   # behind: radar only
g.score = 180; g.wave = 3; g.kills = 9
g.speed = 26.0
tick(a, held=["CONFIRM"], ms=40)
viper.beam = 0.1
g.shield = 62.0; g.hull = 88.0; g.heat = 0.45; g.missiles = 3
g._boom(-420.0, 260.0, 1500.0, 16)
for _ in range(4):
    g._booms(0.04)
g.say("INCOMING MISSILE")
a.ms = 41.0
shot(a, "2_flight.png")
g.locked = True
shot(a, "2b_flight_locked.png")
g.locked = False

g.flash = 0.2
g.beam = 0.0
shot(a, "3_hit.png")
g.flash = 0.0

def fpick(label):
    a.fsub = None
    a.fmenu = a._fitems().index(label)
    tick(a, fresh=["CONFIRM"])


tick(a, fresh=["A"])
tick(a)
shot(a, "4_menu.png")
fpick("STATUS")
shot(a, "4b_status.png")
fpick("PAUSE MENU")
shot(a, "4c_pause_menu.png")
fpick("DEBUG")
shot(a, "4d_debug.png")
fpick("LOCAL CHART")
shot(a, "4e_chart_here.png")
for _ in range(14):
    tick(a, held=["JOYRIGHT", "JOYUP"])
tick(a)
shot(a, "4f_chart_pick.png")
a.chart.cx, a.chart.cy = -60.0, 62.0; a.chart._select()
shot(a, "4g_chart_too_far.png")
tick(a, fresh=["A"])
objs = g.objs[:]
g.objs[:] = []
g.warp = 0.9; g.say("ZAONCE", 3.0)
shot(a, "4h_arriving.png")
g.warp = 0.3
shot(a, "4i_arriving_late.png")
g.warp = 0.0
g.objs[:] = objs
g._hurt(1000.0)
tick(a)
shot(a, "5_gameover.png")

tick(a, fresh=["CANCEL"])
shot(a, "5b_title_continue.png")
bs.choose(a, "NEW COMMANDER")
shot(a, "5c_level_replace.png")
tick(a, fresh=["CANCEL"])
bs.choose(a, "SHIP VIEWER")
shot(a, "6_viewer_cobra.png")
for _ in range(3):
    tick(a, fresh=["CONFIRM"])
for _ in range(20):
    tick(a)
shot(a, "7_viewer_thargoid.png")

# contact sheet
from PIL import Image
names = sorted(n for n in os.listdir(OUT) if n[0].isdigit())
tiles = [Image.open(os.path.join(OUT, n)).resize((360, 360)) for n in names]
sheet = Image.new("RGB", (360 * 4, 360 * ((len(tiles) + 3) // 4)), (40, 40, 48))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 4) * 360, (i // 4) * 360))
sheet.save(os.path.join(OUT, "sheet.png"))
print(names)
