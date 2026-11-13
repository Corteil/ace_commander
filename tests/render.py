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
a = ace_commander.AceCommander()
shot(a, "1_menu.png")

tick(a, fresh=["CONFIRM"])
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

g.flash = 0.2
g.beam = 0.0
shot(a, "3_hit.png")
g.flash = 0.0

tick(a, fresh=["A"])
tick(a)
shot(a, "4_pause.png")
tick(a, fresh=["CONFIRM"])
g._hurt(1000.0)
tick(a)
shot(a, "5_gameover.png")

tick(a, fresh=["CANCEL"])
tick(a, fresh=["DOWN"]); tick(a, fresh=["CONFIRM"])
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
sheet = Image.new("RGB", (360 * 4, 360 * 2), (40, 40, 48))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 4) * 360, (i // 4) * 360))
sheet.save(os.path.join(OUT, "sheet.png"))
print(names)
