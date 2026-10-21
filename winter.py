# Winter scenes for the Galactic Unicorn carousel (December - February): loaded by carousel.py only in those months.
import math
import random

from carousel import gfx, W, H, pen, px, Runs, text, text_width, tiny_text, tiny_width, wave, Stars, Latte, TINY_HEART, \
    during, around

int, min, max, range, len = int, min, max, range, len     # (quicker to find as globals: see carousel.py)


class Snowfall:
    """Snow drifting down; scenes draw it in front of (or behind) everything else."""

    def __init__(self, n, color=(200, 215, 255)):
        self.f = [[random.uniform(0, W), random.uniform(-H, H), random.uniform(1.2, 2.6), random.uniform(0, 6.28)]
                  for _ in range(n)]
        self.pens = [pen(color[0] * k, color[1] * k, color[2] * k) for k in (0.45, 0.75, 1.0)]

    def draw(self, t, dt, wind=0.4):
        for f in self.f:
            f[1] += f[2] * dt
            f[0] += (wind + math.sin(t * 1.3 + f[3]) * 0.8) * dt
            if f[1] >= H:
                f[0], f[1] = random.uniform(-2, W), random.uniform(-3, -1)
            px(f[0] % W, f[1], self.pens[int(f[2] * 1.2) - 1])


class Cabin:
    """A little log cabin in the snowy pines, window glowing, smoke curling from the chimney."""
    dur = 24

    def __init__(self):
        self.sky = [pen(2, 4 + 10 * y / H, 18 + 16 * y / H) for y in range(H)]
        self.stars = Stars(10, 5)
        self.moon = pen(230, 230, 200)
        self.snow = pen(150, 165, 200)
        self.snow2 = pen(210, 220, 250)
        self.pine = pen(8, 45, 25)
        self.wall, self.roof, self.door = pen(90, 45, 20), pen(220, 230, 255), pen(50, 25, 10)
        self.smoke = []
        self.flakes = Snowfall(18)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        self.stars.draw(t)
        gfx.set_pen(self.moon)
        gfx.circle(8, 2, 2)
        gfx.set_pen(self.sky[1])
        gfx.circle(9, 1, 2)                         # crescent
        for x, h in ((17, 7), (22, 9), (46, 8), (51, 6)):
            gfx.set_pen(self.pine)
            gfx.triangle(x - 3, H - 2, x, H - 2 - h, x + 3, H - 2)
            gfx.set_pen(self.snow2)
            px(x, H - 2 - h, self.snow2)
            px(x - 1, H - h + 1, self.snow2)
            px(x + 2, H - h + 3, self.snow2)
        cx = 31                                     # the cabin
        gfx.set_pen(self.wall)
        gfx.rectangle(cx, 6, 10, 4)
        gfx.set_pen(self.roof)
        gfx.triangle(cx - 2, 6, cx + 5, 1, cx + 12, 6)
        gfx.rectangle(cx + 8, 1, 2, 3)              # snowy chimney
        gfx.set_pen(self.wall)
        gfx.rectangle(cx + 8, 2, 2, 2)
        glow = 0.75 + 0.25 * math.sin(t * 7) * math.sin(t * 2.3)
        gfx.set_pen(pen(255 * glow, 170 * glow, 50 * glow))
        gfx.rectangle(cx + 2, 7, 2, 2)
        gfx.rectangle(cx + 7, 7, 2, 2)
        gfx.set_pen(self.door)
        gfx.rectangle(cx + 5, 7, 1, 3)
        if random.random() < 0.12:
            self.smoke.append([cx + 9, 0.5, random.uniform(0, 6), 1.0])
        for s in self.smoke:
            s[1] -= dt * 0.9
            s[3] -= dt * 0.45
            v = max(0, s[3]) * 70
            px(s[0] + math.sin(t + s[2]) * 1.5 + (1 - s[3]) * 3, s[1], pen(v, v, v * 1.1))
        self.smoke = [s for s in self.smoke if s[3] > 0 and s[1] > -1]
        gfx.set_pen(self.snow)                      # snowy ground
        gfx.rectangle(0, H - 2, W, 2)
        gfx.set_pen(self.snow2)
        gfx.rectangle(0, H - 2, W, 1)
        self.flakes.draw(t, dt)


SNOWMAN = [
    "...kkk...",
    "...ttt...",
    "..kkkkk..",
    "...www...",
    "...wnwo..",
    "..rrrrr..",
    "b.wwrww.b",
    ".bwwrwwb.",
    "..wwwww..",
    ".wwwwwww.",
    ".wwwwwww.",
]


class Snowman:
    """A snowman in a red scarf, waving, with "let it snow" drifting in beside him."""
    dur = 20
    WORDS = ("let it", "snow!", "let it", "snow!")

    def __init__(self):
        self.cols = {"k": pen(70, 70, 90), "t": pen(200, 30, 40), "w": pen(220, 230, 255), "n": pen(10, 10, 10), "o": pen(255, 120, 20),
                     "r": pen(220, 30, 40), "b": pen(110, 60, 25)}
        self.bg = [pen(5, 10 + 8 * y / H, 30 + 10 * y / H) for y in range(H)]
        self.flakes = Snowfall(16)
        self.ground = pen(170, 185, 220)
        self.body = Runs(SNOWMAN)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.bg[y])
            gfx.rectangle(0, y, W, 1)
        self.flakes.draw(t, dt, wind=-0.3)
        gfx.set_pen(self.ground)
        gfx.rectangle(0, H - 1, W, 1)
        self.body.draw(3, 0, self.cols)
        wave_up = int(t * 3) % 2
        px(11, 5 + wave_up, self.cols["b"])         # waving hand
        slot = t / (self.dur / len(self.WORDS))
        word = self.WORDS[min(len(self.WORDS) - 1, int(slot))]
        k = slot % 1
        v = min(1, k * 4, (1 - k) * 4)
        tx = 15 + (W - 15 - text_width(word)) // 2
        text(word, tx, 2, pen(200 * v, 225 * v, 255 * v))


class XmasTree:
    """A Christmas tree with twinkling lights, a shining star and presents underneath, snow outside."""
    dur = 22
    CX = 26

    def __init__(self):
        self.bg = pen(6, 8, 20)
        self.green, self.dark = pen(20, 120, 40), pen(10, 75, 25)
        self.trunk = pen(100, 50, 20)
        cx = self.CX
        self.lights = []
        hues = [(255, 40, 40), (255, 200, 40), (60, 140, 255), (255, 90, 200), (60, 230, 120)]
        for y in range(2, 9):
            half = (y - 1) * 7 // 8 + 1
            for x in range(cx - half + 1, cx + half, 2):
                if random.random() < 0.6:
                    self.lights.append((x + (y % 2), y, random.choice(hues), random.uniform(0, 6.28), random.uniform(1.5, 3.5)))
        self.gifts = [(cx - 9, 3, (220, 30, 40), (255, 220, 80)), (cx + 6, 3, (40, 90, 220), (240, 240, 240)),
                      (cx - 5, 2, (40, 170, 70), (255, 60, 60)), (cx + 3, 2, (230, 200, 40), (200, 40, 40))]
        self.gift_pens = [(x, h, pen(*c), pen(*r)) for x, h, c, r in self.gifts]
        self.flakes = Snowfall(10, (110, 120, 150))

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        self.flakes.draw(t, dt)
        cx = self.CX
        for y in range(1, 9):                       # tiers of branches
            half = (y - 1) * 7 // 8 + 1
            gfx.set_pen(self.green if y % 3 else self.dark)
            gfx.rectangle(cx - half + 1, y, 2 * half - 1, 1)
        gfx.set_pen(self.trunk)
        gfx.rectangle(cx - 1, 9, 3, 2)
        for x, y, c, ph, sp in self.lights:
            v = 0.25 + 0.75 * max(0, math.sin(t * sp + ph))
            px(x, y, pen(c[0] * v, c[1] * v, c[2] * v))
        s = wave(t, 4, 0.6, 1.0)
        star = pen(255 * s, 220 * s, 80 * s)
        px(cx, 0, star)
        if s > 0.9:
            px(cx - 1, 0, pen(120, 100, 40))
            px(cx + 1, 0, pen(120, 100, 40))
        for x, h, c, r in self.gift_pens:
            gfx.set_pen(c)
            gfx.rectangle(x, H - h, 4, h)
            gfx.set_pen(r)
            gfx.rectangle(x + 1, H - h, 1, h)                   # ribbon
            if h > 2:
                gfx.rectangle(x, H - h + 1, 4, 1)


REINDEER = [
    ["a.a.....",
     ".a......",
     "bbn.....",
     ".bbbbbb.",
     ".b....b."],
    ["a.a.....",
     ".a......",
     "bbn.....",
     ".bbbbbb.",
     "b......b"],
]
SLEIGH = [
    "...hf....",
    "..ssss...",
    ".rssss.rr",
    ".rrrrrrr.",
    "g.....g..",
    ".ggggggg.",
]


class Sleigh:
    """Santa's sleigh flying past a big moon over sleeping rooftops, Rudolph's nose blinking."""
    dur = 20

    def __init__(self):
        self.stars = Stars(14, 6)
        self.moon = pen(240, 235, 200)
        self.moon2 = pen(200, 195, 160)
        self.roof = pen(25, 20, 40)
        self.snow = pen(160, 170, 210)
        self.lit = pen(255, 190, 70)
        self.rd = {"a": pen(150, 100, 50), "b": pen(140, 80, 35), "n": pen(255, 20, 20)}
        self.nose = pen(255, 20, 20)
        self.sl = {"h": pen(240, 240, 240), "f": pen(255, 190, 150), "s": pen(220, 20, 30), "r": pen(150, 20, 25),
                   "g": pen(255, 200, 60)}
        self.sparkle = []
        self.deer = [Runs(f) for f in REINDEER]
        self.sleigh = Runs(SLEIGH)
        self.houses = [(0, 8, 6), (7, 7, 7), (15, 9, 5), (21, 8, 8), (30, 9, 6), (37, 7, 6), (44, 8, 9)]

    def draw(self, t, dt):
        self.stars.draw(t)
        gfx.set_pen(self.moon)
        gfx.circle(40, 4, 4)
        px(39, 3, self.moon2)
        px(42, 5, self.moon2)
        x = int(-30 + t * 5)                       # sleigh flies left to right
        y = 1 + math.sin(t * 1.4) * 0.8
        for i in range(2):                          # reindeer, in front (to the right); Rudolph leads
            rx = x + 12 + i * 9
            self.rd["n"] = self.nose if i == 1 and int(t * 3) % 2 == 0 else self.rd["b"]
            self.deer[int(t * 5 + i) % 2].draw(rx, int(y) - 1, self.rd, flip=True)
        gfx.set_pen(self.rd["a"])
        gfx.rectangle(x + 8, int(y) + 3, 5, 1)       # harness
        self.sleigh.draw(x, int(y), self.sl)
        if random.random() < 0.6:
            self.sparkle.append([x + random.uniform(-1, 3), y + 5, 1.0])
        for s in self.sparkle:
            s[2] -= dt * 1.2
            v = max(0, s[2])
            px(s[0], s[1], pen(255 * v, 220 * v, 120 * v))
        self.sparkle = [s for s in self.sparkle if s[2] > 0]
        for hx, hy, hw in self.houses:              # rooftops along the bottom
            gfx.set_pen(self.roof)
            gfx.rectangle(hx, hy + 1, hw, H - hy)
            gfx.set_pen(self.snow)
            gfx.rectangle(hx, hy, hw, 1)
            if (hx // 7) % 2 == 0 and hy + 2 < H:
                gfx.set_pen(self.lit)
                gfx.rectangle(hx + hw // 2 - 1, hy + 2, 1, 1)


class Cocoa(Latte):
    """Hot cocoa with marshmallows."""
    WORDS = ("hot", "cocoa", "weather")
    COLORS = {"c": (250, 250, 240), "m": (200, 30, 45), "h": (220, 200, 200), "l": (250, 250, 250)}
    BG = (4, 6, 18)
    INK = (200, 220, 255)


CANDY = ((255, 150, 190), (190, 160, 255), (150, 230, 190), (255, 230, 150), (255, 255, 255), (255, 180, 140))


class Candy:
    """Valentine's conversation hearts: BE MINE, XOXO, HUG ME..."""
    dur = 22
    SAYINGS = ("BE MINE", "XOXO", "HUG ME", "LUV U", "SWEET", "MY BAE")

    def __init__(self):
        self.floaters = [[random.uniform(10, W), random.uniform(0, H + 6), random.uniform(1, 2.5)] for _ in range(6)]
        self.bg = pen(20, 2, 10)
        self.small = Runs(TINY_HEART)
        self.small_pen = {"h": pen(60, 8, 30)}

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        for f in self.floaters:
            f[1] -= f[2] * dt
            if f[1] < -3:
                f[0], f[1] = random.uniform(10, W - 3), H + 1
            self.small.draw(int(f[0]), int(f[1]), self.small_pen)
        slot = t / (self.dur / 4)
        i = min(3, int(slot))
        word = self.SAYINGS[(i + int(t // self.dur)) % len(self.SAYINGS)]
        c = CANDY[i % len(CANDY)]
        k = slot % 1
        v = min(1, k * 4, (1 - k) * 4)
        beat = 1.0 if (t % 1.2) < 0.15 else 0.85
        hc = pen(c[0] * beat, c[1] * beat, c[2] * beat)
        gfx.set_pen(hc)                             # a big candy heart
        gfx.circle(3, 3, 2)
        gfx.circle(7, 3, 2)
        gfx.triangle(1, 4, 5, 9, 9, 4)
        gfx.rectangle(1, 3, 9, 2)
        text(word, 12 + (W - 12 - text_width(word)) // 2, 2, pen(c[0] * v, c[1] * v * 0.9, c[2] * v))


GROUNDHOG = [
    ".bbbb.",
    "bebbeb",
    "bbnnbb",
    ".bwwb.",
    "bbbbbb",
    "bbbbbb",
]


class Groundhog:
    """Groundhog Day: he pops up, looks around, sees his shadow... and ducks back down."""
    dur = 16
    X = 8

    def __init__(self):
        self.sky = [pen(60 + 60 * y / H, 120 + 50 * y / H, 220) for y in range(H)]
        self.snow, self.dirt, self.hole = pen(220, 230, 250), pen(90, 60, 30), pen(30, 18, 8)
        self.cols = {"b": pen(150, 100, 55), "e": pen(0, 0, 0), "n": pen(60, 30, 20), "w": pen(240, 240, 230)}
        self.sun = pen(255, 220, 80)
        self.shadow = pen(150, 160, 190)
        self.hog = Runs(GROUNDHOG)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        sun_up = min(1, max(0, (t - 6) / 2))
        if sun_up > 0:                              # the sun comes out from behind the clouds
            gfx.set_pen(pen(100 + 155 * sun_up, 155 + 65 * sun_up, 220 - 140 * sun_up))
            gfx.circle(46, 2, 2)
        cloud = pen(235, 240, 250)
        cx = 40 + (t - 6) * 3 if t > 6 else 40
        gfx.set_pen(cloud)
        gfx.rectangle(int(cx), 2, 10, 2)
        gfx.rectangle(int(cx) + 2, 1, 5, 1)
        gfx.set_pen(self.snow)
        gfx.rectangle(0, H - 3, W, 3)
        gfx.set_pen(self.hole)
        gfx.rectangle(self.X - 1, H - 3, 8, 1)
        if t < 1.5:
            rise = t / 1.5
        elif t < 11:
            rise = 1
        else:
            rise = max(0, 1 - (t - 11) * 1.5)
        top = int(H - 3 - 6 * rise)
        gfx.set_clip(0, 0, W, H - 3)
        self.hog.draw(self.X, top, self.cols)
        look = 0
        if 2 < t < 5:
            look = -1 if int(t * 1.2) % 2 else 1
        if look:                                    # eyes glance left and right
            for ex in (self.X + 1, self.X + 4):
                px(ex, top + 1, self.cols["b"])
                px(ex + look, top + 1, self.cols["e"])
        gfx.remove_clip()
        if sun_up > 0.5 and rise > 0.5:             # there's his shadow!
            gfx.set_pen(self.shadow)
            gfx.rectangle(self.X - 6, H - 2, 6, 1)      # (the sun is to his right)
        if 9 < t < 12.5:
            text("eek!", 18, 1, pen(70, 30, 90))


class Aurora:
    """Northern lights rippling over the snowy pines on a cold winter night."""
    dur = 24

    def __init__(self):
        self.stars = Stars(16, 7)
        self.green = [pen(20 * k, 230 * k, 110 * k) for k in (0.15, 0.3, 0.5, 0.75, 1.0)]
        self.glow = [pen(10 * k, 120 * k, 70 * k) for k in (0.15, 0.3, 0.5, 0.75, 1.0)]
        self.violet = [pen(120 * k, 40 * k, 160 * k) for k in (0.15, 0.3, 0.5, 0.75, 1.0)]
        self.pine = pen(12, 45, 28)
        self.snow = pen(120, 140, 170)

    def draw(self, t, dt):
        self.stars.draw(t)
        for x in range(W):                          # curtains of light: bright at the bottom edge, fading up
            k = (0.5 + 0.5 * math.sin(x * 0.21 + t * 0.7)) * (0.6 + 0.4 * math.sin(x * 0.09 - t * 0.4)) \
                + math.sin(x * 0.5 + t * 1.9) * 0.15
            if k < 0.08:
                continue
            lv = min(4, int(k * 5))
            base = int(5 + math.sin(x * 0.15 + t * 0.5) * 1.5)
            gfx.set_pen(self.green[lv])
            gfx.rectangle(x, base, 1, 1)
            gfx.set_pen(self.glow[lv])
            gfx.rectangle(x, base - 2, 1, 2)
            gfx.set_pen(self.violet[max(0, lv - 1)])
            gfx.rectangle(x, base - 4, 1, 2)
        gfx.set_pen(self.pine)
        for x, h in ((3, 6), (8, 4), (13, 7), (38, 5), (43, 8), (49, 6)):
            gfx.triangle(x - 2, H - 1, x, H - 1 - h, x + 2, H - 1)
        gfx.set_pen(self.snow)
        gfx.rectangle(0, H - 1, W, 1)


SKATER = [
    [".r.",
     ".f.",
     "bbb",
     ".b.",
     ".l.",
     ".ss"],
    [".r..",
     ".f..",
     "bbbr",
     ".b..",
     ".l..",
     "ss.."],
]


class Skater:
    """A skater gliding back and forth across a frozen pond, snow falling."""
    dur = 22

    def __init__(self):
        self.sky = [pen(8 + 10 * y / H, 12 + 18 * y / H, 40 + 20 * y / H) for y in range(H)]
        self.ice = [pen(120, 170, 220), pen(160, 200, 240)]
        self.bank = pen(200, 210, 235)
        self.pine = pen(10, 50, 30)
        self.cols = {"r": pen(230, 40, 50), "f": pen(250, 200, 170), "b": pen(60, 120, 230), "l": pen(30, 30, 60),
                     "s": pen(230, 230, 240)}
        self.frames = [Runs(f) for f in SKATER]
        self.flakes = Snowfall(12)
        self.marks = []

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.pine)
        for x, h in ((4, 6), (9, 8), (45, 7), (50, 5)):
            gfx.triangle(x - 3, 7, x, 7 - h, x + 3, 7)
        gfx.set_pen(self.bank)
        gfx.rectangle(0, 7, W, 1)
        gfx.set_pen(self.ice[0])
        gfx.rectangle(0, 8, W, 3)
        x = 26 + math.sin(t * 0.45) * 19
        going_left = math.cos(t * 0.45) < 0
        if random.random() < 0.5:
            self.marks.append([x + 1, 10, 1.0])
        for m in self.marks:                        # blade scratches fade on the ice
            m[2] -= dt * 0.5
            px(m[0], m[1], self.ice[1])
        self.marks = [m for m in self.marks if m[2] > 0]
        frame = self.frames[int(t * 1.5) % 2]
        frame.draw(int(x), 5, self.cols, flip=going_left)
        self.flakes.draw(t, dt)


DOVE = [
    ["w...w",
     ".www.",
     "..wgg"],
    [".....",
     "wwwww",
     "..wgg"],
]


class Dream:
    """MLK Day: the sun rising, a dove with an olive branch, "I have a dream"."""
    dur = 22

    def __init__(self):
        self.frames = [Runs(f) for f in DOVE]
        self.cols = {"w": pen(250, 250, 250), "g": pen(90, 180, 60)}
        self.hill = pen(20, 25, 40)

    def draw(self, t, dt):
        k = min(1, t / 12)                          # dawn brightens
        for y in range(H):
            f = y / H
            gfx.set_pen(pen(40 + 200 * k * f, 30 + 110 * k * f, 80 + 40 * (1 - f) - 30 * k))
            gfx.rectangle(0, y, W, 1)
        sy = int(H + 2 - k * 5)
        gfx.set_pen(pen(255, 200 * k + 40, 60 * k))
        gfx.circle(26, sy, 3)
        gfx.set_pen(self.hill)
        gfx.rectangle(0, H - 1, W, 1)
        if t < 10:                                  # the dove flies across first...
            dx = t * 7 - 6
            self.frames[int(t * 4) % 2].draw(int(dx), int(2 + math.sin(t * 1.5) * 1.2), self.cols, flip=True)
        else:                                       # ...then the words
            v = min(1, (t - 10) / 2, (self.dur - t) / 2)
            msg = "I HAVE A DREAM"
            tiny_text(msg, (W - tiny_width(msg)) // 2, 0, pen(255 * v, 240 * v, 200 * v))


SCENES = [
    (Cabin, during(12, 1, 2, 28), 1),
    (Snowman, during(12, 10, 2, 28), 1),
    (Cocoa, during(12, 1, 2, 28), 1),
    (XmasTree, during(12, 1, 12, 26), 2),
    (Sleigh, during(12, 1, 12, 25), 1),
    (Candy, during(2, 1, 2, 14), 2),
    (Groundhog, during(1, 30, 2, 2), 1),
    (Aurora, during(12, 1, 2, 28), 1),
    (Skater, during(12, 15, 2, 28), 1),
    (Dream, around("MLK Day", 1), 2),
]

WEATHER = {"snow": [Cabin, Snowman, Skater], "clear": [Aurora]}     # extra turns when it's really like this out
