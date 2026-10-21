# Extra fall scenes for the Galactic Unicorn carousel (September - November), on top of the Halloween and Japan
# ones in carousel.py: loaded by carousel.py only in those months.
import math
import random

from carousel import gfx, W, H, pen, px, Runs, tiny_text, Stars, Latte, during, around

int, min, range, len, enumerate = int, min, range, len, enumerate     # (quicker to find as globals: see carousel.py)


class Orchard:
    """Apple picking: a tree heavy with apples, one dropping now and then into the basket."""
    dur = 22

    def __init__(self):
        self.sky = [pen(110 + 60 * y / H, 170 + 30 * y / H, 240) for y in range(H)]
        self.leaf = [pen(40, 140, 40), pen(60, 170, 50), pen(30, 110, 30), pen(150, 160, 40)]
        self.trunk = pen(90, 50, 20)
        self.grass = pen(70, 140, 40)
        self.red = pen(230, 30, 30)
        self.basket, self.weave = pen(170, 110, 50), pen(120, 70, 30)
        self.canopy, self.apples = [], []
        for cx in (10, 31):
            for y in range(7):
                for x in range(cx - 8, cx + 9):
                    if ((x - cx) / 8.5) ** 2 + ((y - 3) / 3.6) ** 2 < 1:
                        self.canopy.append((x, y, random.choice(self.leaf)))
                        if random.random() < 0.12:
                            self.apples.append([x, y])
        self.falling = None
        self.in_basket = 0
        self.wait = 2.0

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.trunk)
        for cx in (10, 31):
            gfx.rectangle(cx - 1, 6, 2, H - 6)
        for x, y, c in self.canopy:
            gfx.set_pen(c)
            gfx.pixel(x, y)
        for x, y in self.apples:
            px(x, y, self.red)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 1, W, 1)
        self.wait -= dt
        if self.falling is None and self.wait <= 0 and self.apples:
            self.falling = self.apples.pop(random.randrange(len(self.apples))) + [0.0]
        if self.falling:
            f = self.falling
            f[2] += dt * 14                         # speeds up as it falls
            f[1] += f[2] * dt
            if f[1] >= H - 2:
                self.falling, self.wait = None, random.uniform(1.0, 2.5)
                self.in_basket += 1
            else:
                px(f[0], f[1], self.red)
        bx = 43                                     # the basket fills up
        gfx.set_pen(self.basket)
        gfx.rectangle(bx, H - 4, 8, 3)
        gfx.set_pen(self.weave)
        gfx.rectangle(bx, H - 3, 8, 1)
        gfx.rectangle(bx - 1, H - 4, 1, 1)
        gfx.rectangle(bx + 8, H - 4, 1, 1)
        for i in range(min(self.in_basket, 7)):
            px(bx + 1 + i, H - 5, self.red)


class Turkey:
    """Thanksgiving: a turkey struts across the leaves, stops, fans out his tail... gobble gobble!"""
    dur = 22
    FEATHERS = ((200, 40, 20), (240, 120, 20), (250, 200, 40), (150, 80, 30))

    def __init__(self):
        self.sky = [pen(40 + 80 * y / H, 25 + 45 * y / H, 70 - 30 * y / H) for y in range(H)]
        self.ground = pen(70, 35, 10)
        self.leaves = [(x, random.choice(((220, 80, 10), (180, 40, 10), (240, 160, 20)))) for x in range(0, W, 2)]
        self.leaf_p = [(x, pen(*c)) for x, c in self.leaves]
        self.body, self.head, self.beak = pen(110, 55, 20), pen(170, 120, 100), pen(255, 190, 40)
        self.wattle, self.eye, self.leg = pen(230, 20, 20), pen(0, 0, 0), pen(240, 140, 20)
        self.fp = [pen(*c) for c in self.FEATHERS]

    def turkey(self, x, gy, spread, step):
        n = 9
        for i in range(n):                          # tail feathers fan out behind him
            a = (i / (n - 1) - 0.5) * 2.6 * spread - 0.35
            sx, sy = math.sin(a), -math.cos(a)
            for k in range(2, 7):
                c = self.fp[0 if k == 6 else (1 if k == 5 else (2 if k >= 4 else 3))] if i % 2 == 0 else \
                    self.fp[1 if k == 6 else (2 if k == 5 else 3)]
                px(x - 1 + sx * k, gy - 4 + sy * k, c)
        gfx.set_pen(self.body)
        gfx.circle(x, gy - 3, 2)
        gfx.rectangle(x + 2, gy - 6, 1, 3)          # neck
        gfx.set_pen(self.head)
        gfx.rectangle(x + 2, gy - 7, 2, 1)
        px(x + 3, gy - 7, self.eye)
        px(x + 4, gy - 7, self.beak)
        px(x + 3, gy - 6, self.wattle)
        px(x - 1 + (step % 2), gy, self.leg)
        px(x + 1 - (step % 2), gy, self.leg)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.ground)
        gfx.rectangle(0, H - 1, W, 1)
        for x, p in self.leaf_p:
            px(x, H - 1, p)
        if t < 7:                                   # strut in...
            x, spread, step = -8 + t * 3.5, 0.45, int(t * 4)
        elif t < 14:                                # ...show off...
            x, step = 16.5, 0
            k = min(1, (t - 7) * 2, (14 - t) * 2)
            spread = 0.45 + 0.55 * k
        else:                                       # ...and strut off
            x, spread, step = 16.5 + (t - 14) * 3.5, 0.45, int(t * 4)
        self.turkey(int(x), H - 1, spread, step)
        if 8 < t < 13.5:
            v = min(1, (t - 8) * 2, (13.5 - t) * 2)
            for i, word in enumerate(("GOBBLE", "GOBBLE!")):
                if t > 8 + i * 1.2:
                    tiny_text(word, 26 + i, i * 6, pen(255 * v, 200 * v, 120 * v))


BUS = [
    "..yyyyyyyyyyyyyy",
    ".yywwywwywwywwyy",
    "yywwywwywwywwyyy",
    "yyyyyyyyyyyyyyyy",
    "kkkkkkkkkkkkkkkr",
    "yyyyyyyyyyyyyyyl",
    ".kk.........kk..",
]


class Bus:
    """Back to school: the yellow school bus rolls up, stops (stop sign out!), and heads off."""
    dur = 18

    def __init__(self):
        self.sky = [pen(110 + 60 * y / H, 170 + 30 * y / H, 240) for y in range(H)]
        self.road, self.line = pen(50, 50, 55), pen(230, 210, 80)
        self.cols = {"y": pen(250, 190, 0), "w": pen(150, 210, 255), "k": pen(30, 30, 30), "r": pen(255, 40, 30),
                     "l": pen(255, 250, 200)}
        self.body = Runs(BUS)
        self.trees = [(x, pen(*c)) for x, c in ((4, (220, 120, 20)), (22, (60, 150, 40)), (40, (230, 60, 20)))]
        self.trunk = pen(90, 50, 20)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        for x, c in self.trees:
            gfx.set_pen(c)
            gfx.circle(x + 3, 3, 3)
            gfx.set_pen(self.trunk)
            gfx.rectangle(x + 3, 6, 1, 3)
        gfx.set_pen(self.road)
        gfx.rectangle(0, H - 2, W, 2)
        gfx.set_pen(self.line)
        for x in range(0, W, 6):
            gfx.rectangle(x, H - 1, 3, 1)
        if t < 6:                                   # pull in...
            x = -17 + (1 - (1 - t / 6) ** 2) * 35
        elif t < 11:                                # ...stop...
            x = 18
        else:                                       # ...and off we go
            x = 18 + ((t - 11) ** 2) * 1.2
        x = int(x)
        self.body.draw(x, H - 8, self.cols)
        if 6.5 < t < 10.5:                          # the stop sign swings out, lights flash
            gfx.set_pen(self.cols["r"])
            gfx.rectangle(x + 3, H - 5, 2, 2)
            if int(t * 4) % 2:
                px(x + 2, H - 8, self.cols["r"])
                px(x + 15, H - 8, self.cols["r"])


class Scarecrow:
    """A scarecrow in the cornfield under a harvest moon, crows hopping about and flapping off."""
    dur = 22

    def __init__(self):
        self.stars = Stars(8, 4)
        self.sky = [pen(30 + 50 * y / H, 15 + 25 * y / H, 40 - 10 * y / H) for y in range(H)]
        self.moon = pen(250, 190, 90)
        self.corn = [pen(170, 140, 50), pen(130, 100, 30)]
        self.hat, self.straw = pen(90, 60, 30), pen(240, 200, 80)
        self.face, self.shirt, self.post = pen(220, 180, 120), pen(160, 40, 40), pen(80, 50, 20)
        self.crow = pen(45, 38, 60)
        self.crows = [[x, 9, random.uniform(0, 6), 0.0] for x in (6, 37, 47)]

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        self.stars.draw(t)
        gfx.set_pen(self.moon)
        gfx.circle(44, 3, 3)
        for x in range(0, W, 2):                    # rows of corn
            if 22 <= x <= 30:
                continue
            h = 4 + (x * 7 % 3)
            gfx.set_pen(self.corn[(x // 2) % 2])
            gfx.rectangle(x, H - h, 1, h)
            px(x + 1, H - h + 1 + int(math.sin(t * 2 + x) > 0.6), self.corn[0])
        cx = 26                                     # the scarecrow
        gfx.set_pen(self.post)
        gfx.rectangle(cx, 5, 1, H - 5)
        gfx.set_pen(self.shirt)
        gfx.rectangle(cx - 4, 4, 9, 1)
        gfx.rectangle(cx - 1, 4, 3, 3)
        px(cx - 5, 5, self.straw)
        px(cx + 5, 5, self.straw)
        gfx.set_pen(self.face)
        gfx.rectangle(cx - 1, 2, 3, 2)
        gfx.set_pen(self.hat)
        gfx.rectangle(cx - 2, 1, 5, 1)
        gfx.rectangle(cx - 1, 0, 3, 1)
        for c in self.crows:                        # crows peck about, then flap off and come back
            phase = (t + c[2]) % 9
            if phase < 6:
                y = 9 - (1 if int(t * 3 + c[2]) % 5 == 0 else 0)
                x = c[0] + math.sin(t * 0.5 + c[2]) * 2
            else:
                k = phase - 6
                x, y = c[0] + k * 6, 9 - k * 3
            px(x, y, self.crow)
            px(x + 1, y, self.crow)
            px(x - 1, y - (int(t * 8) % 2 if phase >= 6 else 0), self.crow)


PIE = [
    "...www...",
    "..wwwww..",
    "ccccccccc",
    "ooooooooo",
    "ooooooooo",
    ".ttttttt.",
]


class Pie(Latte):
    """A warm pumpkin pie with a dollop of cream."""
    WORDS = ("grateful", "thankful", "full")
    SPRITE = PIE
    COLORS = {"w": (250, 245, 230), "c": (220, 160, 70), "o": (230, 110, 20), "t": (130, 130, 140)}
    BG = (16, 6, 2)
    INK = (255, 190, 110)


SCENES = [
    (Orchard, during(9, 1, 10, 20), 1),
    (Turkey, around("Thanksgiving", 24, 1), 2),
    (Pie, around("Thanksgiving", 14, 2), 1),
    (Bus, during(8, 28, 9, 12), 2),
    (Scarecrow, during(9, 15, 10, 31), 1),
]

WEATHER = {"sunny": [Orchard]}      # extra turns when it's like this out
