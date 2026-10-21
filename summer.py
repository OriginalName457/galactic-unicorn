# Summer scenes for the Galactic Unicorn carousel (June - August): loaded by carousel.py only in those months.
import math
import random

from carousel import gfx, W, H, pen, px, text, text_width, tiny_text, tiny_width, Stars, Latte, during, around


class Fireflies:
    """A warm summer night: tall grass swaying, fireflies blinking on and off."""
    dur = 24

    def __init__(self):
        self.sky = [pen(4 + 20 * y / H, 6 + 14 * y / H, 25 + 10 * y / H) for y in range(H)]
        self.stars = Stars(10, 5)
        self.grass = [(x, random.randint(2, 5), random.uniform(0, 6)) for x in range(0, W, 2)]
        self.blade = pen(10, 45, 20)
        self.moon = pen(255, 245, 200)
        self.bugs = [[random.uniform(0, W), random.uniform(2, H - 2), random.uniform(0, 6), random.uniform(0.5, 1.2),
                      random.uniform(0, 4)] for _ in range(14)]

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        self.stars.draw(t)
        gfx.set_pen(self.moon)
        gfx.circle(7, 2, 2)
        for b in self.bugs:
            b[0] += math.sin(t * b[3] + b[2]) * dt * 2
            b[1] += math.cos(t * b[3] * 1.3 + b[2]) * dt * 1.2
            b[1] = max(1, min(H - 2, b[1]))
            glow = (t + b[4]) % 2.8                     # blink... wait... blink
            v = max(0, 1 - abs(glow - 0.5) * 2)
            if v > 0:
                px(b[0], b[1], pen(200 * v, 255 * v, 60 * v))
                if v > 0.6:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        px(b[0] + dx, b[1] + dy, pen(40 * v, 60 * v, 10 * v))
        gfx.set_pen(self.blade)
        for x, h, ph in self.grass:
            lean = int(round(math.sin(t * 0.9 + ph) * 0.8))
            gfx.rectangle(x, H - h + 1, 1, h - 1)
            px(x + lean, H - h, self.blade)


class Beach:
    """The beach: waves rolling in, a sailboat on the horizon, a gull flapping overhead, an umbrella."""
    dur = 22

    def __init__(self):
        self.sky = [pen(80 + 70 * y / 5, 170 + 40 * y / 5, 255) for y in range(5)]
        self.sea = [pen(20, 90 + 20 * y, 170 + 10 * y) for y in range(4)]
        self.foam = pen(230, 245, 255)
        self.sand = pen(240, 210, 140)
        self.sun = pen(255, 230, 90)
        self.sail, self.hull = pen(250, 250, 250), pen(150, 60, 30)
        self.gull = pen(250, 250, 250)
        self.red, self.white, self.pole = pen(240, 50, 50), pen(250, 250, 250), pen(120, 100, 80)

    def draw(self, t, dt):
        for y in range(5):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.sun)
        gfx.circle(44, 1, 2)
        for j in range(4):
            gfx.set_pen(self.sea[j])
            gfx.rectangle(0, 5 + j, W, 1)
        bx = int(W - (t * 1.2) % (W + 8))               # the sailboat drifts along the horizon
        gfx.set_pen(self.sail)
        gfx.triangle(bx, 4, bx + 2, 1, bx + 2, 4)
        gfx.set_pen(self.hull)
        gfx.rectangle(bx - 1, 5, 5, 1)
        for x in range(W):                              # waves rolling up the beach
            k = math.sin(x * 0.4 - t * 2.5) + math.sin(x * 0.17 + t * 1.3)
            if k > 1.2:
                px(x, 6 if k < 1.6 else 7, self.foam)
        reach = 9 + int(round(math.sin(t * 1.3) * 0.8))
        gfx.set_pen(self.sand)
        gfx.rectangle(0, reach, W, H - reach)
        if reach < 9:
            gfx.set_pen(self.foam)
            gfx.rectangle(0, reach, W, 1)
        gx = (t * 7) % (W + 10) - 5                      # a gull flapping by
        gy = 2 + math.sin(t * 0.8)
        up = int(t * 5) % 2
        px(gx, gy, self.gull)
        px(gx - 1, gy - up, self.gull)
        px(gx + 1, gy - up, self.gull)
        gfx.set_pen(self.pole)                           # beach umbrella
        gfx.rectangle(12, 6, 1, 5)
        for i, x in enumerate(range(8, 17)):
            gfx.set_pen(self.red if (i // 2) % 2 == 0 else self.white)
            gfx.rectangle(x, 5 if 9 <= x <= 15 else 6, 1, 2 if 9 <= x <= 15 else 1)


CONE = [
    "..ppp..",
    ".ppppp.",
    "ccccccc",
    ".wwwww.",
    ".wwwww.",
    "..www..",
    "..www..",
    "...w...",
]


class IceCream(Latte):
    """An ice cream cone (no steam!) and summery words."""
    WORDS = ("sweet", "summer", "days")
    SPRITE = CONE
    COLORS = {"p": (255, 150, 190), "c": (120, 60, 30), "w": (220, 170, 90)}
    BG = (10, 20, 40)
    INK = (255, 190, 210)
    STEAM = False


class Meteors:
    """The Perseids (mid August): shooting stars across a dark sky. Make a wish!"""
    dur = 20

    def __init__(self):
        self.stars = Stars(20, 9)
        self.trees = pen(5, 15, 8)
        self.streaks = []
        self.wait = 1.0

    def draw(self, t, dt):
        self.stars.draw(t)
        self.wait -= dt
        if self.wait <= 0:
            self.streaks.append([random.uniform(10, W + 10), random.uniform(-1, 3), random.uniform(18, 28), 1.0])
            self.wait = random.uniform(0.8, 2.5)
        for s in self.streaks:
            s[0] -= s[2] * dt
            s[1] += s[2] * dt * 0.35
            s[3] -= dt * 1.4
            for k in range(5):                           # a bright head and a fading tail
                v = max(0, s[3]) * (1 - k / 5)
                px(s[0] + k, s[1] - k * 0.35, pen(255 * v, 240 * v, 200 * v))
        self.streaks = [s for s in self.streaks if s[3] > 0]
        gfx.set_pen(self.trees)
        gfx.rectangle(0, H - 1, W, 1)
        for x, h in ((3, 4), (8, 6), (44, 5), (49, 7)):
            gfx.triangle(x - 2, H - 1, x, H - 1 - h, x + 2, H - 1)
        if 12 < t < 17:
            v = min(1, t - 12, 17 - t)
            msg = "make a wish"
            text(msg, (W - text_width(msg, "bitmap6")) // 2, 4, pen(180 * v, 190 * v, 255 * v), "bitmap6")


class Juneteenth:
    """Juneteenth: its flag rippling: a bursting star rising over the horizon, red below and blue above."""
    dur = 20
    SX, SY = 15, 5

    def __init__(self):
        grid = []
        for y in range(H):
            row = []
            for x in range(W):
                horizon = 6.5 - 1.6 * math.sin(math.pi * x / (W - 1))     # the curved white horizon
                row.append("w" if abs(y - horizon) < 0.55 else ("b" if y < horizon else "r"))
            grid.append(row)
        sx, sy = self.SX, self.SY
        for k in range(12):                         # the nova: a twelve-point burst...
            a = k / 12 * 6.283
            r = 4.6 if k % 2 == 0 else 3.2
            x, y = int(round(sx + math.cos(a) * r)), int(round(sy + math.sin(a) * r * 0.8))
            if 0 <= x < W and 0 <= y < H:
                grid[y][x] = "w"
        for dx, dy in ((0, -2), (0, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (0, 1), (-1, 2), (1, 2),
                       (-1, 1), (1, 1)):            # ...around a white star
            grid[sy + dy][sx + dx] = "w"
        for dx, dy in ((-2, -2), (2, -2), (-3, 1), (3, 1), (-2, 3), (2, 3)):
            if grid[sy + dy][sx + dx] != "w":
                grid[sy + dy][sx + dx] = "b" if sy + dy < 6 else "r"
        self.cols = []                              # each column as runs of one colour: (colour, top, height)
        for x in range(W):
            runs, y = [], 0
            while y < H:
                n = 1
                while y + n < H and grid[y + n][x] == grid[y][x]:
                    n += 1
                runs.append((grid[y][x], y, n))
                y += n
            self.cols.append(runs)
        lv = (0.45, 0.6, 0.8, 1.0)
        self.pens = {"b": [pen(30 * k, 50 * k, 160 * k) for k in lv], "r": [pen(200 * k, 30 * k, 40 * k) for k in lv],
                     "w": [pen(240 * k, 240 * k, 240 * k) for k in lv]}

    def draw(self, t, dt):
        pens = self.pens
        for x in range(W):                          # rippling: light rolls along, the cloth lifts and falls
            k = math.sin(x * 0.35 - t * 4)
            shade = max(0, min(3, int(2.5 + 1.5 * k)))
            lift = int(round(k * 0.6 * x / W))
            runs = self.cols[x]
            for i, (c, y, n) in enumerate(runs):
                if i == 0:
                    y, n = y - 1, n + 1             # stretch the ends so lifting leaves no gaps
                if i == len(runs) - 1:
                    n += 1
                gfx.set_pen(pens[c][shade])
                gfx.rectangle(x, y + lift, 1, n)


class Grill:
    """The backyard grill: burgers sizzling, flames flickering, smoke curling up."""
    dur = 20

    def __init__(self):
        self.sky = [pen(90 + 80 * y / H, 160 + 50 * y / H, 240) for y in range(H)]
        self.lawn = pen(50, 150, 50)
        self.kettle, self.leg = pen(40, 40, 45), pen(90, 90, 95)
        self.burger, self.dog = pen(110, 50, 25), pen(200, 90, 50)
        self.flame = [pen(255, 80, 0), pen(255, 160, 20), pen(255, 220, 80)]
        self.smoke = []
        self.ink = pen(160, 40, 20)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.lawn)
        gfx.rectangle(0, H - 1, W, 1)
        gx = 4                                      # the kettle grill
        gfx.set_pen(self.leg)
        gfx.rectangle(gx + 2, 8, 1, 2)
        gfx.rectangle(gx + 10, 8, 1, 2)
        gfx.rectangle(gx + 6, 8, 1, 2)
        gfx.set_pen(self.kettle)
        gfx.rectangle(gx, 5, 13, 2)
        gfx.rectangle(gx + 1, 7, 11, 1)
        for i in range(6):                          # flames peeking up between the food
            px(gx + 1 + i * 2, 4, self.flame[random.randrange(3)])
        gfx.set_pen(self.burger)
        gfx.rectangle(gx + 1, 3, 3, 1)
        gfx.rectangle(gx + 6, 3, 3, 1)
        gfx.set_pen(self.dog)
        gfx.rectangle(gx + 10, 3, 3, 1)
        if random.random() < 0.3:
            self.smoke.append([gx + random.uniform(1, 12), 2, random.uniform(0, 6), 1.0])
        for sm in self.smoke:
            sm[1] -= dt * 1.5
            sm[3] -= dt * 0.5
            v = max(0, sm[3]) * 150
            px(sm[0] + math.sin(t * 2 + sm[2]) + (1 - sm[3]) * 4, sm[1], pen(v + 60, v + 60, v + 70))
        self.smoke = [sm for sm in self.smoke if sm[3] > 0 and sm[1] > -1]
        for i, line in enumerate(("GRILL", "MASTER")):
            tiny_text(line, 20 + (W - 20 - tiny_width(line)) // 2, i * 6, self.ink)


class Storm:
    """A summer thunderstorm rolling in at dusk: rain, and every so often a crack of lightning."""
    dur = 22

    def __init__(self):
        self.drops = [[random.uniform(0, W), random.uniform(0, H), random.uniform(10, 14)] for _ in range(18)]
        self.cloud = [pen(40, 40, 55), pen(60, 60, 75)]
        self.drop = pen(90, 120, 200)
        self.field = pen(15, 50, 20)
        self.house, self.window = pen(25, 20, 25), pen(255, 190, 80)
        self.bolt = None
        self.flash = 0.0
        self.wait = 3.0

    def draw(self, t, dt):
        f = self.flash
        gfx.set_pen(pen(15 + 200 * f, 15 + 200 * f, 30 + 210 * f))
        gfx.clear()
        for x in range(0, W, 4):                    # heavy rolling clouds
            h = 2 + int(1.5 + 1.5 * math.sin(x * 0.4 + t * 0.6))
            gfx.set_pen(self.cloud[(x // 4) % 2])
            gfx.rectangle(x, 0, 4, h)
        for d in self.drops:
            d[1] += d[2] * dt
            d[0] -= 2 * dt
            if d[1] > H - 1:
                d[0], d[1] = random.uniform(0, W + 4), random.uniform(1, 3)
            px(d[0], d[1], self.drop)
        self.wait -= dt
        if self.wait <= 0:                          # crack!
            x, path = random.randint(8, W - 8), []
            for y in range(2, H - 1):
                x += random.choice((-1, 0, 1))
                path.append((x, y))
            self.bolt, self.flash, self.wait = path, 1.0, random.uniform(3, 7)
        if self.bolt and self.flash > 0.3:
            for x, y in self.bolt:
                px(x, y, pen(255, 255, 220))
        self.flash = max(0.0, self.flash - dt * 2.5)
        gfx.set_pen(self.field)
        gfx.rectangle(0, H - 1, W, 1)
        gfx.set_pen(self.house)                     # a farmhouse with a light on
        gfx.rectangle(42, 7, 7, 3)
        gfx.triangle(41, 7, 45, 4, 49, 7)
        px(44, 8, self.window)


SCENES = [
    (Fireflies, during(6, 1, 8, 31), 1),
    (Beach, during(6, 1, 8, 31), 1),
    (IceCream, during(6, 1, 8, 31), 1),
    (Meteors, during(8, 8, 8, 15), 1),
    (Juneteenth, during(6, 17, 6, 19), 2),
    (Grill, lambda y, m, d: around("Father's Day", 3)(y, m, d) or during(7, 1, 7, 5)(y, m, d), 2),
    (Storm, during(6, 15, 8, 31), 1),
]

WEATHER = {"storm": [Storm], "sunny": [Beach, IceCream], "clear": [Fireflies]}   # extra turns when it's like this out
