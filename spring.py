# Spring scenes for the Galactic Unicorn carousel (March - May): loaded by carousel.py only in those months.
import math
import random

from carousel import gfx, W, H, pen, px, Runs, text, text_width, tiny_text, tiny_width, TINY, ICONS, Stars, \
    during, around

RAINBOW = ((230, 30, 30), (250, 120, 20), (250, 220, 30), (40, 200, 60), (40, 110, 240), (130, 60, 200))


class Rainbow:
    """St. Patrick's: a rainbow ending in a pot of gold, shamrocks tumbling across a green hill."""
    dur = 22

    def __init__(self):
        self.sky = [pen(70 + 50 * y / H, 140 + 40 * y / H, 235) for y in range(H)]
        self.arc = []                               # (x, y, pen) for every rainbow pixel, worked out once
        cx, cy = 27, 13
        for y in range(H):
            for x in range(W):
                r = math.sqrt((x - cx) ** 2 + ((y - cy) * 1.5) ** 2)
                band = int(19 - r)
                if 0 <= band < len(RAINBOW):
                    self.arc.append((x, y, pen(*RAINBOW[band])))      # red on the outside
        self.hill = pen(30, 150, 50)
        self.hill2 = pen(20, 110, 35)
        self.pot, self.rim = pen(30, 30, 35), pen(70, 70, 80)
        self.gold = [pen(255, 200, 40), pen(255, 235, 120)]
        self.clover = pen(40, 220, 70)
        self.clovers = [[random.uniform(-W, 0), random.uniform(0, 6), random.uniform(5, 9), random.uniform(0, 6)]
                        for _ in range(4)]

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        for x, y, p in self.arc:
            gfx.set_pen(p)
            gfx.pixel(x, y)
        gfx.set_pen(self.hill2)
        gfx.circle(8, 14, 6)
        gfx.set_pen(self.hill)
        gfx.rectangle(0, H - 2, W, 2)
        gfx.circle(40, 15, 6)
        x = 41                                      # the pot of gold at the rainbow's end
        gfx.set_pen(self.pot)
        gfx.rectangle(x, 7, 7, 3)
        gfx.rectangle(x + 1, 10, 5, 1)
        gfx.set_pen(self.rim)
        gfx.rectangle(x - 1, 6, 9, 1)
        for i in range(5):
            px(x + 1 + i, 5, self.gold[(i + int(t * 4)) % 2])
        px(x + 3, 4, self.gold[int(t * 4) % 2])
        for c in self.clovers:                      # shamrocks tumbling by
            c[0] += c[2] * dt
            if c[0] > W + 3:
                c[0], c[1] = random.uniform(-15, -3), random.uniform(0, 5)
            cy = int(c[1] + math.sin(t * 2 + c[3]))
            cx = int(c[0])
            gfx.set_pen(self.clover)
            gfx.rectangle(cx, cy, 1, 1)
            gfx.rectangle(cx - 1, cy + 1, 3, 1)
            px(cx, cy + 2, self.hill2)


class Showers:
    """April showers: rain from drifting clouds, tulips pushing up and opening... then the sun comes out."""
    dur = 24

    def __init__(self):
        self.drops = [[random.uniform(0, W), random.uniform(0, H), random.uniform(8, 12)] for _ in range(14)]
        self.cloud = pen(90, 95, 110)
        self.cloud2 = pen(120, 125, 140)
        self.drop = pen(80, 140, 255)
        self.grass = pen(30, 110, 40)
        self.stem = pen(40, 160, 50)
        self.tulips = [(x, random.choice(((255, 60, 90), (255, 200, 40), (200, 80, 255), (255, 120, 40))),
                        random.uniform(0, 3)) for x in range(4, W - 2, 6)]

    def draw(self, t, dt):
        clear = max(0, min(1, (t - 15) / 3))           # the rain stops and the sky brightens
        sky = pen(30 + 70 * clear, 40 + 120 * clear, 60 + 175 * clear)
        gfx.set_pen(sky)
        gfx.clear()
        if clear > 0:
            gfx.set_pen(pen(255 * clear, 210 * clear, 60 * clear))
            gfx.circle(46, 2, 3)
        if clear < 1:
            for d in self.drops:
                d[1] += d[2] * dt
                if d[1] > H - 2:
                    d[0], d[1] = random.uniform(0, W), random.uniform(-2, 1)
                if random.random() > clear:
                    px(d[0], d[1], self.drop)
                    px(d[0], d[1] - 1, pen(40, 70, 130))
        drift = int(t * 1.5)                         # clouds drift right and away
        gfx.set_pen(self.cloud if clear < 0.5 else self.cloud2)
        for cx in (2, 20, 38):
            x = cx + drift + int(clear * 30)
            gfx.rectangle(x % (W + 20) - 10, 0, 12, 2)
            gfx.rectangle(x % (W + 20) - 8, 2, 8, 1)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 1, W, 1)
        for x, c, delay in self.tulips:              # stems grow, then the flowers open
            grow = max(0, min(1, (t - delay) / 8))
            h = int(1 + grow * 4)
            gfx.set_pen(self.stem)
            gfx.rectangle(x, H - 1 - h, 1, h)
            if grow > 0.6:
                gfx.set_pen(pen(*c))
                top = H - 2 - h
                gfx.rectangle(x - 1, top, 3, 2)
                if grow >= 1:
                    px(x - 1, top - 1, pen(*c))
                    px(x + 1, top - 1, pen(*c))
            if grow > 0.4:
                px(x + 1, H - 2, self.stem)          # a leaf


class Garden:
    """A spring garden: flowers swaying, a bumblebee buzzing around, a butterfly fluttering by."""
    dur = 22

    def __init__(self):
        self.sky = [pen(90 + 60 * y / H, 170 + 40 * y / H, 250) for y in range(H)]
        self.grass = pen(40, 150, 50)
        self.stem = pen(30, 120, 40)
        hues = ((255, 90, 150), (255, 220, 50), (180, 110, 255), (255, 255, 255), (255, 120, 60))
        self.flowers = [(x, random.randint(4, 7), pen(*random.choice(hues)), random.uniform(0, 6))
                        for x in range(2, W, 5)]
        self.center = pen(255, 200, 40)
        self.bee_y, self.bee_k = pen(255, 210, 0), pen(30, 30, 30)
        self.wing = pen(220, 240, 255)
        self.fly = [(255, 140, 20), (40, 40, 40)]
        self.fly_p = [pen(*c) for c in self.fly]
        self.sun = pen(255, 230, 120)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.sun)
        gfx.circle(50, 0, 3)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 2, W, 2)
        for x, h, c, ph in self.flowers:
            sway = int(round(math.sin(t * 1.2 + ph) * 0.7))
            gfx.set_pen(self.stem)
            gfx.rectangle(x, H - h, 1, h - 1)
            fx, fy = x + sway, H - h - 1
            gfx.set_pen(c)
            gfx.rectangle(fx - 1, fy, 3, 1)
            gfx.rectangle(fx, fy - 1, 1, 3)
            px(fx, fy, self.center)
        bx = W / 2 + math.sin(t * 0.7) * 20                     # the bee does lazy figure-eights
        by = 4 + math.sin(t * 1.4) * 2.5
        px(bx, by, self.bee_y)
        px(bx + 1, by, self.bee_k)
        px(bx + 2, by, self.bee_y)
        if int(t * 12) % 2:
            px(bx + 1, by - 1, self.wing)
        fx = (t * 4) % (W + 10) - 5                              # butterfly floats left to right
        fy = 2 + math.sin(t * 3) * 1.5
        open_ = int(t * 6) % 2
        for dx in ((-1, 1) if open_ else (0,)):
            px(fx + dx, fy, self.fly_p[0])
            px(fx + dx, fy + 1, self.fly_p[0])
        px(fx, fy, self.fly_p[1])


BUNNY = [
    [".ww....",
     ".wp....",
     ".ww....",
     "wwww...",
     "wwewwww",
     ".wwwwwwt",
     ".ww..ww."],
    ["..ww...",
     "..wp...",
     ".www...",
     "wwww...",
     "wwewwww",
     ".wwwwwwt",
     "w.....w."],
]


class Bunny:
    """Easter: a bunny hops across the meadow past painted eggs hidden in the grass."""
    dur = 20

    def __init__(self):
        self.sky = [pen(120 + 50 * y / H, 190 + 30 * y / H, 250) for y in range(H)]
        self.grass, self.grass2 = pen(50, 170, 60), pen(30, 120, 40)
        self.cols = {"w": pen(240, 235, 230), "p": pen(255, 150, 180), "e": pen(20, 20, 20), "t": pen(255, 255, 255)}
        eggs = ((255, 140, 200), (120, 200, 255), (255, 230, 90), (170, 140, 255), (140, 230, 160))
        self.frames = [Runs(f) for f in BUNNY]
        self.eggs = [(x, pen(*c), pen(c[0] * 0.6, c[1] * 0.6, c[2] * 0.6)) for x, c in zip((6, 17, 29, 38, 47), eggs)]

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        for x, c, stripe in self.eggs:
            gfx.set_pen(c)
            gfx.rectangle(x, H - 6, 2, 4)
            gfx.rectangle(x - 1, H - 5, 4, 2)
            gfx.set_pen(stripe)
            gfx.rectangle(x - 1, H - 4, 4, 1)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 2, W, 2)
        for x in range(0, W, 3):
            px(x + (int(t) % 2), H - 3, self.grass2)
        x = (t * 3.5) % (W + 14) - 9                             # hop, hop, pause
        phase = (t * 1.6) % 1
        hop = math.sin(phase * math.pi) * 2.5 if phase < 0.6 else 0
        self.frames[1 if phase < 0.6 else 0].draw(int(x), int(H - 9 - hop), self.cols, flip=True)


class Kite:
    """A breezy spring day: a kite dancing on its string, its tail flicking, clouds racing by."""
    dur = 20

    def __init__(self):
        self.sky = [pen(80 + 70 * y / H, 160 + 50 * y / H, 250) for y in range(H)]
        self.cloud = pen(245, 248, 255)
        self.clouds = [[random.uniform(0, W), random.randint(0, 4), random.randint(5, 9)] for _ in range(3)]
        self.grass = pen(60, 170, 60)
        self.string = pen(230, 230, 210)
        self.kite = [pen(255, 60, 80), pen(255, 210, 40)]
        self.bows = [pen(255, 60, 80), pen(60, 140, 255), pen(255, 210, 40)]

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.cloud)
        for c in self.clouds:
            c[0] -= dt * 5
            if c[0] < -c[2]:
                c[0], c[1] = W + random.uniform(1, 10), random.randint(0, 4)
            gfx.rectangle(int(c[0]), c[1], c[2], 1)
            gfx.rectangle(int(c[0]) + 1, c[1] - 1, c[2] - 3, 1)
        kx = 30 + math.sin(t * 0.7) * 8 + math.sin(t * 2.1) * 1.5   # the kite swoops about
        ky = 3 + math.sin(t * 1.1) * 1.5
        hx, hy = 6, H - 1                                         # down to whoever is holding it
        for i in range(1, 12):                                    # a sagging string
            f = i / 12
            px(hx + (kx - hx) * f, hy + (ky + 2 - hy) * f + math.sin(f * 3.14) * 1.5, self.string)
        x, y = int(kx), int(ky)
        gfx.set_pen(self.kite[0])
        gfx.triangle(x, y - 2, x - 2, y, x + 2, y)
        gfx.set_pen(self.kite[1])
        gfx.triangle(x - 2, y, x + 2, y, x, y + 3)
        for i in range(1, 6):                                     # tail with bows, flicking in the wind
            tx = x + i * 1.2 + math.sin(t * 6 - i) * 0.8
            ty = y + 3 + i * 0.7
            px(tx, ty, self.bows[i % 3] if i % 2 == 0 else self.string)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 1, W, 1)


class PiDay:
    """Pi Day (3/14): a pie, and the digits of pi marching past."""
    dur = 22
    DIGITS = "3.14159265358979323846264338327950288419716939937510"
    SPEED = 10

    def __init__(self):
        rows, cols = ICONS["pie"]
        self.pie = Runs(rows)
        self.cols = {k: pen(*c) for k, c in cols.items()}
        self.bg = pen(14, 6, 2)

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        gfx.set_clip(11, 0, W - 11, H)
        x = W - t * self.SPEED
        gfx.set_font("bitmap8")
        for i, ch in enumerate(self.DIGITS):
            w = 6 if ch != "." else 3
            if x >= W:
                break
            if x + w > 11:
                v = 0.7 + 0.3 * math.sin(t * 3 + i * 0.6)
                gfx.set_pen(pen(255 * v, 170 * v, 80 * v))
                gfx.text(ch, int(x), 2, -1, 1)
            x += w
        gfx.remove_clip()
        self.pie.draw(1, 3, self.cols)


class Sakura:
    """Cherry blossoms in full bloom, petals drifting on the breeze, a lantern glowing (spring in Japan)."""
    dur = 24

    def __init__(self):
        self.sky = [pen(120 + 60 * y / H, 160 + 40 * y / H, 230 - 20 * y / H) for y in range(H)]
        pinks = ((255, 170, 200), (255, 200, 220), (240, 130, 170), (255, 225, 235))
        self.bloom = []
        for cx, cy, rx in ((9, 3, 9), (40, 2, 10)):
            for y in range(7):
                for x in range(cx - rx, cx + rx + 1):
                    if ((x - cx) / rx) ** 2 + ((y - cy) / 3.6) ** 2 < 1 and random.random() < 0.9:
                        self.bloom.append((x, y, pen(*random.choice(pinks))))
        self.trunk = pen(70, 40, 40)
        self.grass = pen(90, 170, 90)
        self.petal = [pen(*c) for c in pinks]
        self.petals = [[random.uniform(0, W), random.uniform(-H, H), random.uniform(1, 2), random.uniform(0, 6),
                        random.choice(self.petal)] for _ in range(14)]
        self.lamp_wood = pen(60, 40, 30)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.trunk)
        gfx.rectangle(8, 5, 2, H - 5)
        gfx.rectangle(40, 4, 2, H - 4)
        px(7, 5, self.trunk)
        px(42, 5, self.trunk)
        for x, y, p in self.bloom:
            gfx.set_pen(p)
            gfx.pixel(x, y)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 1, W, 1)
        gfx.set_pen(self.lamp_wood)                 # a little stone lantern between the trees
        gfx.rectangle(23, H - 5, 5, 1)
        gfx.rectangle(25, H - 4, 1, 3)
        gfx.rectangle(24, H - 2, 3, 1)
        g = 0.7 + 0.3 * math.sin(t * 2)
        px(25, H - 4, pen(255 * g, 190 * g, 90 * g))
        for p in self.petals:
            p[1] += p[2] * dt
            p[0] += (1.5 + math.sin(t * 1.4 + p[3])) * dt
            if p[1] > H or p[0] > W:
                p[0], p[1] = random.uniform(-5, W - 5), random.uniform(-3, -1)
            px(p[0], p[1], p[4])


def tiny_upside_down(s, x, y, p):
    """The tiny font turned upside down (for April Fools)."""
    gfx.set_pen(p)
    x += tiny_width(s) - 1
    for ch in s:
        bits = TINY.get(ch, 0)
        for i in range(15):
            if bits >> i & 1:
                gfx.pixel(x - i % 3, y + 4 - i // 3)
        x -= 2 if ch == " " else 4


class Fools:
    """April Fools: the screen is upside down! ...then rights itself. gotcha."""
    dur = 16

    def __init__(self):
        self.bg = pen(10, 10, 30)
        self.ink = pen(255, 200, 60)

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        if t < 8:
            shake = int(math.sin(t * 9) * 1.2) if 5 < t < 8 else 0
            for i, line in enumerate(("HELLO", "THERE")):
                tiny_upside_down(line, (W - tiny_width(line)) // 2 + shake, 6 - i * 6, self.ink)
        elif t < 9:
            k = int((t - 8) * 6) % 2                # a quick glitchy flip
            gfx.set_pen(pen(255 * k, 200 * k, 60 * k))
            gfx.rectangle(0, 5, W, 1)
        else:
            for i, line in enumerate(("APRIL", "FOOLS!")):
                c = pen(255, 120 + 100 * (i == 0), 180 * (i == 1))
                tiny_text(line, (W - tiny_width(line)) // 2, i * 6, c)


class Earth:
    """Earth Day: our little planet turning in space."""
    dur = 22
    R = 5

    def __init__(self):
        self.stars = Stars(14, H)
        land = []                                   # a made-up but earthy map: 48 longitudes x 11 latitudes
        for lon in range(48):
            col = []
            for lat in range(11):
                a = lon / 48 * 6.283
                v = math.sin(a * 2 + 1) + math.sin(a * 3 + lat * 0.7) * 0.7 + math.sin(lat * 1.3 + a) * 0.5
                col.append(v > 0.6)
            land.append(col)
        self.land = land
        self.disk = []
        r = self.R
        for y in range(-r, r + 1):
            for x in range(-r, r + 1):
                if x * x + y * y <= r * r + 1:
                    lon = int((math.asin(max(-1, min(1, x / math.sqrt(max(1, r * r - y * y + 1))))) / 3.1416 + 0.5) * 24)
                    edge = (x * x + y * y) / (r * r)
                    self.disk.append((x, y, lon, y + r, edge))
        self.sea = [pen(30, 90, 230), pen(20, 60, 170)]
        self.green = [pen(50, 190, 70), pen(35, 130, 50)]
        self.ice = pen(230, 240, 255)
        self.ink = pen(120, 220, 140)

    def draw(self, t, dt):
        self.stars.draw(t)
        spin = int(t * 3)
        cx, cy = 7, 5
        for x, y, lon, lat, edge in self.disk:
            shade = 1 if edge > 0.6 or x < -2 else 0
            if lat in (0, 10):
                p = self.ice
            elif self.land[(lon + spin) % 48][lat]:
                p = self.green[shade]
            else:
                p = self.sea[shade]
            gfx.set_pen(p)
            gfx.pixel(cx + x, cy + y)
        v = min(1, t / 2, (self.dur - t) / 2)
        for i, line in enumerate(("LOVE YOUR", "PLANET")):
            tiny_text(line, 15 + (W - 15 - tiny_width(line)) // 2, i * 6, pen(120 * v, 220 * v, 140 * v))


class Picado:
    """Cinco de Mayo: strings of papel picado fluttering, confetti falling."""
    dur = 20
    COLORS = ((255, 60, 120), (255, 200, 40), (60, 200, 90), (60, 150, 255), (255, 120, 30), (180, 80, 255))

    def __init__(self):
        self.bg = pen(20, 10, 30)
        self.string = pen(200, 200, 200)
        self.flags = [pen(*c) for c in self.COLORS]
        self.conf = [[random.uniform(0, W), random.uniform(-H, H), random.uniform(2, 4), random.choice(self.flags)]
                     for _ in range(14)]

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        for c in self.conf:
            c[1] += c[2] * dt
            if c[1] > H:
                c[0], c[1] = random.uniform(0, W), -1
            px(c[0] + math.sin(t * 3 + c[2]) * 0.6, c[1], c[3])
        for row, y0 in enumerate((0, 6)):           # two strings of flags
            gfx.set_pen(self.string)
            gfx.rectangle(0, y0, W, 1)
            for i, x in enumerate(range(1 + row * 3, W, 7)):
                sway = int(round(math.sin(t * 3 + i * 0.9 + row) * 0.6))
                gfx.set_pen(self.flags[(i + row * 2) % len(self.flags)])
                gfx.rectangle(x + sway, y0 + 1, 5, 3)
                gfx.rectangle(x + sway + 1, y0 + 4, 3, 1)
                gfx.set_pen(self.bg)                # the cut-out pattern
                gfx.pixel(x + sway + 2, y0 + 2)
                gfx.pixel(x + sway, y0 + 3)
                gfx.pixel(x + sway + 4, y0 + 3)


class Bouquet:
    """Mother's Day: a bouquet in a vase with little hearts floating up."""
    dur = 20

    def __init__(self):
        self.bg = pen(30, 10, 25)
        self.vase = pen(120, 170, 230)
        self.stem = pen(40, 150, 50)
        self.heart = pen(255, 80, 140)
        cols = ((255, 90, 140), (255, 210, 60), (240, 240, 255), (200, 120, 255), (255, 140, 60))
        self.heads = [(26 + dx, dy, pen(*cols[i % len(cols)])) for i, (dx, dy) in
                      enumerate(((-6, 3), (-3, 1), (0, 0), (3, 1), (6, 3), (-4, 4), (4, 4), (0, 3)))]
        self.hearts = [[random.uniform(5, W - 5), random.uniform(0, H + 6), random.uniform(1, 2)] for _ in range(5)]

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        for h in self.hearts:
            h[1] -= h[2] * dt
            if h[1] < -2:
                h[0], h[1] = random.choice((random.uniform(2, 16), random.uniform(36, 50))), H + 1
            x, y = int(h[0]), int(h[1])
            px(x, y, self.heart)
            px(x + 2, y, self.heart)
            px(x + 1, y + 1, self.heart)
        gfx.set_pen(self.stem)
        for x, y, _ in self.heads:
            gfx.line(x, y + 1, 26, 7)
        for i, (x, y, p) in enumerate(self.heads):
            sway = int(round(math.sin(t * 1.3 + i) * 0.5))
            gfx.set_pen(p)
            gfx.rectangle(x - 1 + sway, y, 3, 1)
            gfx.rectangle(x + sway, y - 1, 1, 3)
            px(x + sway, y, pen(255, 220, 80))
        gfx.set_pen(self.vase)
        gfx.rectangle(23, 7, 7, 4)
        gfx.rectangle(22, 7, 9, 1)


SCENES = [
    (Rainbow, during(3, 1, 3, 18), 2),
    (Showers, during(3, 18, 4, 30), 1),
    (Kite, during(3, 1, 5, 31), 1),
    (Garden, during(4, 1, 5, 31), 1),
    (Bunny, around("Easter", 14, 1), 2),
    (PiDay, during(3, 13, 3, 14), 2),
    (Sakura, during(3, 20, 4, 25), 1),
    (Fools, during(4, 1, 4, 1), 3),
    (Earth, during(4, 19, 4, 22), 2),
    (Picado, during(5, 3, 5, 5), 2),
    (Bouquet, around("Mother's Day", 3), 2),
]

WEATHER = {"rain": [Showers], "storm": [Showers], "sunny": [Garden, Kite]}   # extra turns when it's like this out
