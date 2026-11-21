"""A PC stand-in for the Badgeware v3 calls the Tufty host makes (picovector
v3.1: screen, shape, color, font, rect, badge), drawn with Pillow so frames can
be looked at. Only what host_tufty, ctx_tufty and layout_tufty use. Written
from the v3 API (github.com/pimoroni/picovector-micropython, api/), no
firmware code copied.
"""
from PIL import Image, ImageDraw

# line heights measured on the Tufty (2026-11-21); widths about 0.6 of them
FONT_H = {"desert": 10, "sins": 12, "badgeware": 14, "smart": 16, "badgewaremax": 20, "ignore": 28}


class Font:
    def __init__(self, name):
        self.name = name
        self.h = FONT_H.get(name, 12)


class _Fonts:
    def __getattr__(self, name):
        return Font(name)


font = _Fonts()


class _Color:
    def rgb(self, r, g, b, a=255):
        return (int(r), int(g), int(b), int(a))


color = _Color()


class Rect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h


def rect(x, y, w, h):
    return Rect(x, y, w, h)


class Shape:
    def __init__(self, kind, data):
        self.kind = kind
        self.data = data


class Vec2:
    def __init__(self, x, y):
        self.x, self.y = x, y


import builtins             # noqa: E402
builtins.vec2 = Vec2        # a builtin on the Tufty


class _Shapes:
    def custom(self, points):
        # strict, as the Tufty's v3.1.1: one outline, a list of vec2 points
        if not isinstance(points, list) or not all(isinstance(q, Vec2) for q in points):
            raise TypeError("expected a list of vec2 points")
        return Shape("custom", [[c for q in points for c in (q.x, q.y)]])

    def line(self, x0, y0, x1, y1, w):
        return Shape("line", (x0, y0, x1, y1, w))


shape = _Shapes()


class Screen:
    def __init__(self, w=320, h=240):
        self.width, self.height = w, h
        self.img = Image.new("RGB", (w, h), (0, 0, 0))
        self.pen = (255, 255, 255, 255)
        self.font = Font("sins")
        self.clip = Rect(0, 0, w, h)
        self.calls = 0

    def _draw(self, fn):
        """Draw fn(draw, dx, dy) inside the clip rectangle only."""
        c = self.clip
        x0, y0 = max(0, int(c.x)), max(0, int(c.y))
        x1, y1 = min(self.width, int(c.x + c.w)), min(self.height, int(c.y + c.h))
        if x1 <= x0 or y1 <= y0:
            return
        sub = self.img.crop((x0, y0, x1, y1))
        r, g, b, a = self.pen
        if a < 255:
            layer = sub.copy()
            fn(ImageDraw.Draw(layer), -x0, -y0, (r, g, b))
            sub = Image.blend(sub, layer, a / 255.0)
        else:
            fn(ImageDraw.Draw(sub), -x0, -y0, (r, g, b))
        self.img.paste(sub, (x0, y0))
        self.calls += 1

    def clear(self):
        self._draw(lambda d, dx, dy, c: d.rectangle((0, 0, self.width, self.height), fill=c))

    def rectangle(self, x, y, w, h):
        self._draw(lambda d, dx, dy, c: d.rectangle((x + dx, y + dy, x + w - 1 + dx, y + h - 1 + dy), fill=c))

    def line(self, x0, y0, x1, y1):
        self._draw(lambda d, dx, dy, c: d.line((x0 + dx, y0 + dy, x1 + dx, y1 + dy), fill=c))

    def circle(self, c, r):
        x, y = c.x, c.y
        self._draw(lambda d, dx, dy, c: d.ellipse((x - r + dx, y - r + dy, x + r + dx, y + r + dy), fill=c))

    def shape(self, s):
        if s.kind == "custom":
            for flat in s.data:
                pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)]
                self._draw(lambda d, dx, dy, c, pts=pts: d.polygon([(px + dx, py + dy) for px, py in pts], fill=c))
        elif s.kind == "line":
            x0, y0, x1, y1, w = s.data
            self._draw(lambda d, dx, dy, c: d.line((x0 + dx, y0 + dy, x1 + dx, y1 + dy), fill=c, width=int(w + 0.5)))

    def measure_text(self, s):
        h = self.font.h
        return len(s) * h * 0.6, h

    def text(self, s, x, y):
        h = self.font.h
        self._draw(lambda d, dx, dy, c: d.text((x + dx, y + dy), s, fill=c))


class Badge:
    def __init__(self):
        self.down = set()
        self.lights = []
        self.mode_set = None

    def held(self, b):
        return b in self.down

    def mode(self, m):
        self.mode_set = m

    def caselights(self, level):
        self.lights.append(level)


BUTTONS = {"A": "BUTTON_A", "B": "BUTTON_B", "C": "BUTTON_C", "UP": "BUTTON_UP", "DOWN": "BUTTON_DOWN"}
