# A carousel through the year for the Pimoroni Galactic Unicorn (53x11): cozy fall and Halloween, and scenes
# for the other seasons and US holidays (winter.py, spring.py, summer.py, fall.py), with holiday countdowns.
#
# Buttons:  A = next scene   B = weather now   C = clock now   D = hold scene
#           LUX +/- = brightness   SLEEP = screen on/off
#
# The Pi keeps the clock in sync over Wi-Fi or USB (see unicorn.py). Lines it can send:
#   T y m d h mi s wd   set the clock
#   M some text         add a custom message to the carousel ("M" alone clears it)
#   B 30                set brightness in percent (remembered across restarts)
#   S chime             play a tune on the speaker (see TUNES), or notes like "S C5:2 E5:2 G5:4"
#   V 30                set speaker volume in percent (remembered; VOL +/- buttons too)
#   D 2026 12 24        pretend it's another day, to see that season's scenes ("D" alone goes back)
#   N                   next scene (like the A button)
#   X name              run name.py's run(gu) (an experiment pushed from the Pi) and reply with its result
#   P                   how long each scene takes to draw (ms, slowest frame) and free memory
#   G Name              show a scene now (by its class name, or an animation's id)
#   TIMER 300 Tea       a kitchen timer: counts down on screen, then rings ("TIMER 0" cancels)
#   ?                   status
# Replies to commands sent over USB are printed as "@@ reply" (Unicorn Studio reads them).
#
# Your choices (scenes switched off, alarms, your own dates and messages, your own pixel animations, the weather's
# town) are in settings.json, written by Unicorn Studio (studio/unicorn_studio.py). Without a Pi, the Unicorn keeps
# its own clock and fetches the weather itself over Wi-Fi (online.py).
#
# The same commands also arrive over Wi-Fi (see net.py), so a power-only cable is enough.

import time
import math
import random
import sys
import gc

import net
from machine import mem32

# The built-ins the scenes use most, as globals: MicroPython looks a name up in the module's globals before the
# built-ins, and a name that isn't there means searching the table up to an empty slot (slow in a big module).
int, min, max, abs, range, len, round, float, enumerate, str = int, min, max, abs, range, len, round, float, \
    enumerate, str

# Breadcrumbs for tracking down freezes: kept in the watchdog's scratch registers, which survive the watchdog's
# restart (not a power cut). audioring.py reads the last ones at start-up; "?" reports them after a freeze.
CRUMB, FRAMES, PUMPS, PUMP_AT = 0x4005800c, 0x40058010, 0x40058014, 0x40058018
wdt = None              # the watchdog: started with the speaker stream, restarts the Unicorn if it ever freezes


def crumb(n):
    mem32[CRUMB] = n

from galactic import GalacticUnicorn
from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN

BRIGHTNESS = 0.3        # daytime brightness; LUX buttons or `unicorn.py bright N` adjust it (saved)
EVENING_BRIGHTNESS = 0.3  # same as daytime: the user wants a flat 30% all day and night
RAMP_START, RAMP_END = 17, 21   # climbs from daytime to evening brightness between these hours
MORNING = 7             # back to daytime brightness
FADE = 0.8              # seconds of fade in/out between scenes

try:
    with open("brightness.txt") as f:
        BRIGHTNESS = max(0.02, min(1.0, float(f.read())))
except (OSError, ValueError):
    pass

gu = GalacticUnicorn()
gfx = PicoGraphics(display=DISPLAY_GALACTIC_UNICORN)
W, H = GalacticUnicorn.WIDTH, GalacticUnicorn.HEIGHT

custom_msg = ""


def load_settings():
    try:
        import json
        with open("settings.json") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


SETTINGS = load_settings()
OFF = set(SETTINGS.get("off", ()))      # scenes switched off (class names, or animation ids)


def pen(r, g, b):
    return gfx.create_pen(int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b))))


BLACK = pen(0, 0, 0)


def px(x, y, p):
    gfx.set_pen(p)
    gfx.pixel(int(x), int(y))


def sprite(rows, x, y, colors, flip=False):
    for j, row in enumerate(rows):
        n = len(row)
        for i in range(n):
            ch = row[n - 1 - i] if flip else row[i]   # MicroPython has no [::-1] on str
            c = colors.get(ch)
            if c is not None:
                gfx.set_pen(c)
                gfx.pixel(x + i, y + j)


class Runs:
    """A sprite turned into horizontal runs of one colour and drawn as rectangles: several times faster than
    sprite(). Colours are looked up when drawing, so they can flicker."""

    def __init__(self, rows):
        runs = []
        for y, row in enumerate(rows):
            x = 0
            while x < len(row):
                n = 1
                while x + n < len(row) and row[x + n] == row[x]:
                    n += 1
                if row[x] != ".":
                    runs.append((row[x], x, y, n, len(row)))
                x += n
        runs.sort()
        self.runs = runs

    def draw(self, x, y, colors, flip=False):
        last = None
        for ch, dx, dy, n, row_w in self.runs:
            c = colors.get(ch)
            if c is None:
                continue
            if c is not last:
                gfx.set_pen(c)
                last = c
            gfx.rectangle(x + (row_w - dx - n if flip else dx), y + dy, n, 1)


def text(s, x, y, p, font="bitmap8"):
    gfx.set_font(font)
    gfx.set_pen(p)
    gfx.text(s, int(x), int(y), -1, 1)


def text_width(s, font="bitmap8"):
    gfx.set_font(font)
    return gfx.measure_text(s, 1)


def wave(t, speed=1.0, lo=0.0, hi=1.0, phase=0.0):
    return lo + (hi - lo) * (0.5 + 0.5 * math.sin(t * speed + phase))


def clock_synced():
    return time.localtime()[0] >= 2025


# ---------------------------------------------------------------- sprites

PUMPKIN = [
    "....gg...",
    ".ooooooo.",
    "ooyyoyyoo",
    "ooooyoooo",
    "oyoyoyoyo",
    "ooyoyoyoo",
    ".ooooooo.",
]
MINI_PUMPKIN = [
    "..g..",
    ".ooo.",
    "ooooo",
    "ooooo",
    ".ooo.",
]
MINIS = {  # the clock's little picture through the year: (rows, {letter: rgb})
    "pumpkin": (MINI_PUMPKIN, {"o": (230, 90, 0), "g": (40, 120, 20)}),
    "snow": (["s.s.s",
              ".sss.",
              "sssss",
              ".sss.",
              "s.s.s"], {"s": (170, 210, 255)}),
    "tree": (["..y..",
              ".ggg.",
              "gg.gg",
              "ggggg",
              "..t.."], {"y": (255, 210, 60), "g": (20, 140, 40), "t": (110, 60, 20)}),
    "heart": ([".h.h.",
               "hhhhh",
               "hhhhh",
               ".hhh.",
               "..h.."], {"h": (255, 50, 100)}),
    "flower": ([".p.p.",
                "ppypp",
                ".p.p.",
                "..g..",
                ".gg.."], {"p": (255, 120, 180), "y": (255, 220, 60), "g": (40, 170, 50)}),
    "sun": (["y.y.y",
             ".yyy.",
             "yyyyy",
             ".yyy.",
             "y.y.y"], {"y": (255, 190, 30)}),
}
HEART = [
    ".hh.hh.",
    "hhhhhhh",
    "hhhhhhh",
    ".hhhhh.",
    "..hhh..",
    "...h...",
]
TINY_HEART = [
    "h.h",
    "hhh",
    ".h.",
]
BAT = [
    ["b...b",
     ".bbb.",
     "....."],
    [".....",
     ".bbb.",
     "b...b"],
]
GHOST = [
    [".wwwww.",
     "wwwwwww",
     "wwewwew",
     "wwwwwww",
     "wwwwwww",
     "wwwwwww",
     "w.ww.ww"],
    [".wwwww.",
     "wwwwwww",
     "wwewwew",
     "wwwwwww",
     "wwwwwww",
     "wwwwwww",
     "ww.ww.w"],
]
MUG = [
    "ccccccc..",
    "mmmmmmmhh",
    "mmmlmmm.h",
    "mmllmmm.h",
    "mmmlmmmhh",
    "mmmmmmm..",
    ".mmmmm...",
]


class Stars:
    def __init__(self, n, max_y=H - 3):
        self.s = [(random.randrange(W), random.randrange(max_y), random.uniform(0, 6.28), random.uniform(0.5, 2))
                  for _ in range(n)]

    def draw(self, t):
        for x, y, ph, sp in self.s:
            v = wave(t, sp, 10, 90, ph)
            px(x, y, pen(v, v, v * 0.9))


# ---------------------------------------------------------------- scenes

class Leaves:
    """Dusky sky, a little autumn tree, leaves drifting down into piles."""
    dur = 25

    def __init__(self):
        self.sky = [pen(4 + 40 * y / H, 2 + 14 * y / H, 14 - 8 * y / H) for y in range(H)]
        self.cols = [pen(220, 50, 10), pen(240, 110, 0), pen(250, 170, 10), pen(160, 35, 5), pen(150, 80, 15)]
        self.trunk = pen(70, 30, 8)
        self.pile = [[random.choice(self.cols) for _ in range(random.randint(1, 2))] for _ in range(W)]
        self.canopy = []
        for y in range(6):
            for x in range(-1, 14):
                if ((x - 6) / 6.5) ** 2 + ((y - 2) / 3.2) ** 2 < 1 and random.random() < 0.9:
                    self.canopy.append((x, y, random.choice(self.cols)))
        self.leaves = [self.new(True) for _ in range(16)]

    def new(self, anywhere=False):
        y = random.uniform(-2, H - 4) if anywhere else random.uniform(-4, -1)
        return [random.uniform(0, W), y, random.uniform(1.2, 3.0), random.uniform(0, 6.28), random.choice(self.cols)]

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.trunk)
        gfx.rectangle(5, 4, 2, H - 4)
        px(4, 5, self.trunk)
        px(7, 6, self.trunk)
        for x, y, c in self.canopy:
            px(x, y, c)
        wind = 0.8 + math.sin(t * 0.25) * 1.2
        for lf in self.leaves:
            lf[1] += lf[2] * dt
            sway = math.sin(t * 1.6 + lf[3])
            lf[0] = (lf[0] + (wind + sway * 2.0) * dt) % W
            x = int(lf[0])
            ground = H - len(self.pile[x])
            if lf[1] >= ground:
                if len(self.pile[x]) < 3:
                    self.pile[x].append(lf[4])
                lf[:] = self.new()
                continue
            y = int(lf[1])
            px(x, y, lf[4])
            if sway > 0.3:          # tumbling: sometimes 2 pixels wide
                px((x + 1) % W, y, lf[4])
            elif sway < -0.3:
                px(x, y - 1, lf[4])
        for x in range(W):
            for i, c in enumerate(self.pile[x]):
                px(x, H - 1 - i, c)


class Pumpkins:
    """Jack-o'-lanterns flickering under a harvest moon with bats."""
    dur = 22

    def __init__(self):
        self.stars = Stars(10)
        self.cols = {"o": pen(230, 90, 0), "g": pen(40, 120, 20)}
        self.moon = pen(250, 210, 120)
        self.crater = pen(200, 160, 90)
        self.ground = pen(18, 8, 2)
        self.bats = [[random.uniform(-30, -5), random.uniform(1, 4), random.uniform(5, 9), random.uniform(0, 6)]
                     for _ in range(3)]
        self.flick = [1.0, 1.0]
        self.bat_pen = pen(110, 40, 160)

    def draw(self, t, dt):
        self.stars.draw(t)
        gfx.set_pen(self.moon)
        gfx.circle(46, 3, 3)
        px(45, 2, self.crater)
        px(47, 4, self.crater)
        gfx.set_pen(self.ground)
        gfx.rectangle(0, H - 1, W, 1)
        for i, x in enumerate((4, 25)):
            self.flick[i] += (random.uniform(0.5, 1.0) - self.flick[i]) * 0.3
            f = self.flick[i]
            self.cols["y"] = pen(255 * f, 200 * f, 40 * f)
            sprite(PUMPKIN, x, H - 7, self.cols)
        for b in self.bats:
            b[0] += b[2] * dt
            if b[0] > W + 5:
                b[0] = random.uniform(-25, -5)
                b[1] = random.uniform(0, 4)
            y = b[1] + math.sin(t * 3 + b[3]) * 1.0
            frame = BAT[int(t * 6 + b[3]) % 2]
            sprite(frame, int(b[0]), int(y), {"b": self.bat_pen})


class Ghost:
    """A friendly ghost floating over a graveyard. boo!"""
    dur = 22

    def __init__(self):
        self.stars = Stars(12, 6)
        self.cols = {"w": pen(170, 180, 220), "e": BLACK}
        self.stone = pen(50, 50, 60)
        self.grass = pen(10, 40, 10)
        self.trail = []
        self.boo = pen(150, 100, 255)

    def draw(self, t, dt):
        self.stars.draw(t)
        gfx.set_pen(self.grass)
        gfx.rectangle(0, H - 1, W, 1)
        for x in (8, 30, 44):
            gfx.set_pen(self.stone)
            gfx.rectangle(x, H - 5, 4, 4)
            gfx.rectangle(x + 1, H - 6, 2, 1)
        gx = 23 + 20 * math.sin(t * 0.3)
        gy = 1.5 + math.sin(t * 2.2) * 1.2
        going_left = math.cos(t * 0.3) < 0
        if random.random() < 0.4:
            self.trail.append([gx + 3 + random.uniform(-2, 2), gy + 6, 1.0])
        for p in self.trail:
            p[2] -= dt * 0.8
            p[1] -= dt * 1.5
            v = max(0, p[2]) * 120
            px(p[0], p[1], pen(v * 0.8, v * 0.8, v))
        self.trail = [p for p in self.trail if p[2] > 0]
        sprite(GHOST[int(t * 4) % 2], int(gx), int(gy), self.cols, flip=going_left)
        phase = t % 7
        if 3 < phase < 6:
            bx = 2 if gx > W / 2 else W - 22
            v = min(1, (phase - 3) * 2, (6 - phase) * 2)
            text("boo!", bx, 1, pen(150 * v, 100 * v, 255 * v), "bitmap6")


class Campfire:
    """A crackling campfire with a tent, pines, sparks and stars."""
    dur = 24
    FW = 13
    FX = 20

    def __init__(self):
        self.stars = Stars(14, 5)
        self.heat = [0.0] * (self.FW * H)
        self.sparks = []
        self.log = pen(90, 40, 10)
        self.tent = pen(20, 70, 30)
        self.pine = pen(5, 35, 15)
        self.palette = []
        for i in range(32):
            h = i / 31
            self.palette.append(pen(255 * min(1, h * 2.2), 255 * max(0, h - 0.35) * 1.4, 255 * max(0, h - 0.8) * 2))

    def draw(self, t, dt):
        self.stars.draw(t)
        fw, hh = self.FW, self.heat
        mid = fw / 2
        for x in range(fw):
            edge = 1 - abs(x - mid + 0.5) / mid
            hh[(H - 2) * fw + x] = random.uniform(0.5, 1.0) * edge ** 0.6
        for y in range(H - 2):
            row, below = y * fw, (y + 1) * fw
            for x in range(fw):
                s = hh[below + x] * 2 + hh[below + max(0, x - 1)] + hh[below + min(fw - 1, x + 1)]
                hh[row + x] = max(0, s / 4 - random.uniform(0.04, 0.13))
        for y in range(H - 1):
            for x in range(fw):
                v = hh[y * fw + x]
                if v > 0.05:
                    px(self.FX + x, y, self.palette[min(31, int(v * 31))])
        if random.random() < 0.15:
            self.sparks.append([self.FX + random.uniform(3, fw - 3), H - 4, random.uniform(-1, 1), 1.0])
        for s in self.sparks:
            s[1] -= dt * 4
            s[0] += s[2] * dt
            s[3] -= dt * 0.6
            v = max(0, s[3])
            px(s[0], s[1], pen(255 * v, 140 * v, 20 * v))
        self.sparks = [s for s in self.sparks if s[3] > 0 and s[1] > -1]
        gfx.set_pen(self.log)
        gfx.rectangle(self.FX + 1, H - 1, fw - 2, 1)
        px(self.FX, H - 2, self.log)
        px(self.FX + fw - 1, H - 2, self.log)
        gfx.set_pen(self.tent)
        gfx.triangle(2, H - 1, 8, H - 8, 14, H - 1)
        glow = wave(t, 3, 0.6, 1.0)
        gfx.set_pen(pen(200 * glow, 90 * glow, 10))
        gfx.triangle(7, H - 1, 8, H - 4, 9, H - 1)
        gfx.set_pen(self.pine)
        for x, h in ((40, 8), (46, 10), (51, 7)):
            gfx.triangle(x - 3, H - 1, x, H - 1 - h, x + 3, H - 1)


class Latte:
    """A pumpkin spice latte steaming away. cozy. (Other seasons make their own cups by changing these.)"""
    dur = 20
    WORDS = ("cozy", "sweater", "weather")
    SPRITE = MUG
    COLORS = {"c": (240, 215, 170), "m": (220, 95, 25), "h": (200, 180, 160), "l": (250, 200, 120)}
    BG = (16, 6, 2)
    INK = (250, 190, 120)
    STEAM = True

    def __init__(self):
        self.bg = pen(*self.BG)
        self.cols = {k: pen(*c) for k, c in self.COLORS.items()}
        self.cup = Runs(self.SPRITE)
        self.steam = []

    def draw(self, t, dt):
        gfx.set_pen(self.bg)
        gfx.clear()
        mx, my = 5, H - len(self.SPRITE)
        self.cup.draw(mx, my, self.cols)
        if self.STEAM and random.random() < 0.25:
            self.steam.append([mx + random.uniform(1, 6), my - 1, random.uniform(0, 6.28), 1.0])
        for s in self.steam:
            s[1] -= dt * 1.6
            s[3] -= dt * 0.35
            x = s[0] + math.sin(s[1] * 1.2 + s[2]) * 1.2
            v = max(0, s[3]) * 110
            px(x, s[1], pen(v, v * 0.9, v * 0.8))
        self.steam = [s for s in self.steam if s[3] > 0 and s[1] > -1]
        slot = t / (self.dur / len(self.WORDS))
        word = self.WORDS[min(len(self.WORDS) - 1, int(slot))]
        k = slot % 1
        v = min(1, k * 4, (1 - k) * 4)
        area_x = 17
        font = "bitmap8" if text_width(word) <= W - area_x else "bitmap6"
        tx = area_x + (W - area_x - text_width(word, font)) // 2
        r, g, b = self.INK
        text(word, tx, 2 if font == "bitmap8" else 3, pen(r * v, g * v, b * v), font)


class Clock:
    """The time, with a little seasonal picture, then the date."""
    dur = 9

    def __init__(self):
        _, m, d = today()
        if m == 12 and d <= 26:
            mini = "tree"
        elif m == 2 and d <= 14:
            mini = "heart"
        else:
            mini = ("snow", "snow", "flower", "flower", "flower", "sun", "sun", "sun",
                    "pumpkin", "pumpkin", "pumpkin", "snow")[m - 1]
        self.mini, cols = MINIS[mini]
        self.cols = {k: pen(*c) for k, c in cols.items()}
        self.amber = pen(255, 150, 30)

    @staticmethod
    def available():
        return clock_synced()

    def draw(self, t, dt):
        lt = time.localtime()
        if t < 6:
            h = lt[3] if SETTINGS.get("24h") else lt[3] % 12 or 12
            hs, ms = str(h), "%02d" % lt[4]
            ampm = "" if SETTINGS.get("24h") else "pm" if lt[3] >= 12 else "am"
            total = text_width(hs) + 4 + text_width(ms) + 2 + text_width(ampm, "bitmap6")
            x = 8 + (W - 8 - total) // 2
            sprite(self.mini, 1, 3, self.cols)
            text(hs, x, 2, self.amber)
            x += text_width(hs) + 1
            c = pen(255 * wave(t, 6, 0.2, 1), 150 * wave(t, 6, 0.2, 1), 30)
            px(x, 4, c)
            px(x, 7, c)
            x += 3
            text(ms, x, 2, self.amber)
            x += text_width(ms) + 2
            text(ampm, x, 4, pen(180, 90, 20), "bitmap6")
        else:
            days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
            months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
            s = "%s %d %s" % (days[lt[6]], lt[2], months[lt[1] - 1])
            if text_width(s, "bitmap6") > W:
                s = "%d %s" % (lt[2], months[lt[1] - 1])
            text(s, (W - text_width(s, "bitmap6")) // 2, 3, pen(240, 170, 80), "bitmap6")


def day_of_year(y, m, d):
    cum = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    leap = 1 if m > 2 and (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 0
    return cum[m - 1] + d + leap


# ---------------------------------------------------------------- the calendar: seasons and holidays

date_override = None    # (y, m, d) from "D 2026 12 24", to try out another time of year; "D" alone clears it


def today():
    if date_override:
        return date_override
    lt = time.localtime()
    return lt[0], lt[1], lt[2]


def weekday(y, m, d):
    """0 = Monday (Sakamoto's method)."""
    if m < 3:
        y -= 1
    return (y + y // 4 - y // 100 + y // 400 + (0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4)[m - 1] + d + 6) % 7


def nth_weekday(y, m, wd, n):
    """Day of the month of the nth weekday wd (0 = Monday) in month m; n = -1 for the last one."""
    if n > 0:
        return 1 + (wd - weekday(y, m, 1)) % 7 + 7 * (n - 1)
    last = (31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[m - 1]
    return last - (weekday(y, m, last) - wd) % 7


def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    j, k = c // 4, c % 4
    m = (a + 11 * h) // 319
    r = (2 * e + 2 * j - k - h + m + 32) % 7
    n = (h - m + r + 90) // 25
    return n, (h - m + r + n + 19) % 32


_holidays = {}


def holidays(y):
    """(month, day, name for "N days 'til ...", greeting on the day, icon, days of countdown beforehand).
    Only the big ones count down (the user's wish); the rest just get a greeting on the day."""
    if y not in _holidays:
        em, ed = easter(y)
        if len(_holidays) > 2:
            _holidays.clear()
        _holidays[y] = [
            (1, 1, "New Year", "Happy New Year %d!" % y, "spark", 0),
            (1, nth_weekday(y, 1, 0, 3), "MLK Day", "Happy MLK Day!", "star", 0),
            (2, 2, "Groundhog Day", "Happy Groundhog Day!", "hog", 0),
            (2, 14, "Valentine's", "Happy Valentine's Day!", "heart", 14),
            (2, nth_weekday(y, 2, 0, 3), "Presidents' Day", "Happy Presidents' Day!", "flag", 0),
            (3, 14, "Pi Day", "Happy Pi Day! 3.14159...", "pie", 0),
            (3, 17, "St. Patrick's", "Happy St. Patrick's Day!", "clover", 0),
            (3, 20, "spring", "Happy first day of spring!", "flower", 0),
            (4, 1, "April Fools'", "Happy April Fools' Day!", "star", 0),
            (em, ed, "Easter", "Happy Easter!", "egg", 14),
            (4, 22, "Earth Day", "Happy Earth Day!", "globe", 0),
            (5, 5, "Cinco de Mayo", "Happy Cinco de Mayo!", "star", 0),
            (5, nth_weekday(y, 5, 6, 2), "Mother's Day", "Happy Mother's Day!", "flower", 0),
            (5, nth_weekday(y, 5, 0, -1), "Memorial Day", "Happy Memorial Day", "flag", 0),
            (6, nth_weekday(y, 6, 6, 3), "Father's Day", "Happy Father's Day!", "sun", 0),
            (6, 19, "Juneteenth", "Happy Juneteenth!", "star", 0),
            (6, 21, "summer", "Happy first day of summer!", "sun", 0),
            (7, 4, "the 4th", "Happy 4th of July!", "flag", 10),
            (9, nth_weekday(y, 9, 0, 1), "Labor Day", "Happy Labor Day!", "flag", 0),
            (9, 22, "fall", "Happy first day of fall!", "leaf", 0),
            (10, 31, "Halloween", "Happy Halloween!!", "pumpkin", 60),
            (11, 11, "Veterans Day", "Happy Veterans Day", "flag", 0),
            (11, nth_weekday(y, 11, 3, 4), "Thanksgiving", "Happy Thanksgiving!", "turkey", 21),
            (12, 25, "Christmas", "Merry Christmas!", "tree", 30),
            (12, 31, "New Year's Eve", "Happy New Year's Eve!", "spark", 0),
        ]
        for e in SETTINGS.get("dates", ()):         # your own: birthdays, trips... {"name", "date": "MM-DD" or
            try:                                    # "YYYY-MM-DD", "greeting", "icon", "lead": days of countdown}
                p = [int(v) for v in e["date"].split("-")]
                if len(p) == 2 or p[0] == y:
                    _holidays[y].append((p[-2], p[-1], e["name"], e.get("greeting") or e["name"] + "!",
                                         e.get("icon") if e.get("icon") in ICONS else "star", int(e.get("lead", 0))))
            except (KeyError, ValueError, IndexError):
                pass
    return _holidays[y]


def holiday_messages():
    """Today's greetings, then any countdowns running: [(text, icon)]."""
    y, m, d = today()
    now = day_of_year(y, m, d)
    rest_of_year = day_of_year(y, 12, 31) - now
    hello, soon = [], []
    for this_year, table in ((True, holidays(y)), (False, holidays(y + 1))):
        for hm, hd, name, greeting, icon, lead in table:
            k = day_of_year(y, hm, hd) - now if this_year else rest_of_year + day_of_year(y + 1, hm, hd)
            if k < 0 or k > max(lead, 0):
                continue
            if k == 0:
                hello.append((greeting, icon))
            else:
                if name == "New Year":
                    name = str(y + 1)
                soon.append((k, ("%s is TOMORROW!" % name) if k == 1 else ("%d days 'til %s" % (k, name)), icon))
    soon.sort()
    return hello + [(msg, icon) for _, msg, icon in soon]


def holiday_date(name, y):
    for h in holidays(y):
        if h[2] == name:
            return h[0], h[1]


def during(m1, d1, m2, d2):
    """A window of the year, inclusive (it may wrap past New Year)."""
    a, b = m1 * 100 + d1, m2 * 100 + d2
    return lambda y, m, d: a <= m * 100 + d <= b if a <= b else (m * 100 + d >= a or m * 100 + d <= b)


def around(name, before, after=0):
    """From `before` days ahead of a holiday until `after` days past it."""
    def when(y, m, d):
        hm, hd = holiday_date(name, y)
        return -before <= day_of_year(y, m, d) - day_of_year(y, hm, hd) <= after
    return when


ICONS = {   # little pictures for the countdowns: (rows, {letter: rgb})
    "pumpkin": (PUMPKIN, {"o": (230, 90, 0), "g": (40, 120, 20), "y": (255, 200, 40)}),
    "heart": (HEART, {"h": (255, 40, 90)}),
    "turkey": (["r.o.y.o.r",
                "royyhyyor",
                "royhehyor",
                ".obhkhbo.",
                ".bbbwbbb.",
                "..bbbbb..",
                "..f...f.."],
               {"r": (200, 40, 20), "o": (240, 120, 20), "y": (250, 200, 40), "h": (170, 110, 70), "e": (0, 0, 0),
                "k": (255, 190, 40), "w": (230, 20, 20), "b": (110, 55, 20), "f": (240, 140, 20)}),
    "tree": (["....y....",
              "...ggg...",
              "..grgbg..",
              "...ggg...",
              "..gggyg..",
              ".gbgggrg.",
              "gggyggggg",
              "....t...."],
             {"y": (255, 210, 60), "g": (20, 120, 40), "r": (255, 40, 40), "b": (80, 140, 255), "t": (110, 60, 20)}),
    "spark": (["y...y...y",
               ".y..y..y.",
               "..y.y.y..",
               "yyyy.yyyy",
               "..y.y.y..",
               ".y..y..y.",
               "y...y...y"],
              {"y": (255, 210, 80)}),
    "star": (["...y...",
              "...y...",
              "yyyyyyy",
              ".yyyyy.",
              "..yyy..",
              ".yy.yy.",
              ".y...y."],
             {"y": (255, 220, 70)}),
    "flag": (["bwbwrrrrr",
              "wbwbwwwww",
              "bwbwrrrrr",
              "wwwwwwwww",
              "rrrrrrrrr",
              "wwwwwwwww",
              "rrrrrrrrr"],
             {"b": (30, 50, 200), "w": (230, 230, 230), "r": (220, 20, 30)}),
    "clover": (["..gg.gg..",
                "..ggggg..",
                "gg..g..gg",
                "ggggggggg",
                ".ggg.ggg.",
                "....s....",
                "...s....."],
               {"g": (30, 200, 60), "s": (20, 120, 40)}),
    "egg": (["..ppp..",
             ".ppppp.",
             "yyyyyyy",
             "ppppppp",
             "bbbbbbb",
             ".ppppp.",
             "..ppp.."],
            {"p": (240, 130, 200), "y": (250, 230, 90), "b": (110, 180, 255)}),
    "flower": ([".p...p.",
                "ppp.ppp",
                ".pyyyp.",
                "ppp.ppp",
                ".p.g.p.",
                "..gg...",
                "...g..."],
               {"p": (255, 110, 170), "y": (255, 220, 60), "g": (40, 170, 50)}),
    "sun": (["y..y..y",
             ".yyyyy.",
             ".yyyyy.",
             "yyyyyyy",
             ".yyyyy.",
             ".yyyyy.",
             "y..y..y"],
            {"y": (255, 190, 30)}),
    "leaf": (["...o...",
              ".o.o.o.",
              ".ooooo.",
              "ooooooo",
              ".ooooo.",
              "...b...",
              "...b..."],
             {"o": (240, 100, 10), "b": (110, 50, 10)}),
    "globe": ([".bbgb.",
               "bggbbb",
               "bbggbb",
               "bbbggb",
               "gbbbgb",
               ".bbbb."],
              {"b": (30, 90, 230), "g": (40, 190, 60)}),
    "hog": ([".bbbb.",
             "bebbeb",
             "bbnnbb",
             ".bwwb.",
             "bbbbbb",
             "dddddd"],
            {"b": (150, 100, 55), "e": (0, 0, 0), "n": (60, 30, 20), "w": (240, 240, 230), "d": (90, 55, 25)}),
    "gift": (["..r...r..",
              "...r.r...",
              "ggggrgggg",
              "ggggrgggg",
              "rrrrrrrrr",
              "ggggrgggg",
              "ggggrgggg"],
             {"g": (40, 170, 90), "r": (255, 60, 80)}),
    "pie": (["...www...",
             "..wwwww..",
             "ccccccccc",
             "ooooooooo",
             "ooooooooo",
             ".ttttttt."],
            {"w": (250, 245, 230), "c": (220, 160, 70), "o": (230, 110, 20), "t": (130, 130, 140)}),
}


class Countdown:
    """Today's holiday greeting, or how many days until the next one, with its little picture."""
    SPEED = 12
    turn = 0            # takes turns when more than one is going on

    @staticmethod
    def available():
        return clock_synced() and bool(holiday_messages())

    @staticmethod
    def messages():
        return holiday_messages()

    def __init__(self):
        msgs = self.messages()
        self.msg, icon = msgs[type(self).turn % len(msgs)]
        type(self).turn += 1
        rows, cols = ICONS[icon]
        self.rows = rows
        self.icon = Runs(rows)
        self.cols = {k: pen(*c) for k, c in cols.items()}
        self.flicker = icon in ("pumpkin", "spark", "tree")
        self.base = cols
        self.iw = len(rows[0]) + 1
        self.tw = text_width(self.msg)
        self.widths = [gfx.measure_text(ch, 1) + 1 for ch in self.msg]
        self.dur = (W - self.iw + self.tw) / self.SPEED + 0.5
        self.warm = icon in ("pumpkin", "leaf", "turkey", "pie", "sun")

    def draw(self, t, dt):
        gfx.set_clip(self.iw, 0, W - self.iw, H)
        x = W - t * self.SPEED
        # color each character along a sweep: orange -> purple in fall, rainbow-ish the rest of the year
        gfx.set_font("bitmap8")
        for i, ch in enumerate(self.msg):
            w = self.widths[i]
            if x >= W:
                break
            if x + w > self.iw and ch != " ":                 # only the letters on screen
                k = wave(t, 2, phase=i * 0.5)
                if self.warm:
                    gfx.set_pen(pen(255 - 120 * k, 110 - 70 * k, 200 * k))
                else:
                    gfx.set_pen(pen(255 - 155 * k, 120 + 100 * k, 200 * (1 - k) + 55 * k))
                gfx.text(ch, int(x), 2, -1, 1)
            x += w
        gfx.remove_clip()
        if self.flicker:
            f = random.uniform(0.6, 1.0)
            for k in ("y", "r", "b"):
                if k in self.base:
                    c = self.base[k]
                    self.cols[k] = pen(c[0] * f, c[1] * f, c[2] * f)
        self.icon.draw(0, (H - len(self.rows)) // 2, self.cols)


class Note:
    """Your messages (from Unicorn Studio, or `unicorn.py say ...`), one per visit."""
    SPEED = 12
    turn = 0

    def __init__(self):
        msgs = Note.messages()
        self.msg = msgs[Note.turn % len(msgs)]
        Note.turn += 1
        self.dur = (W + text_width(self.msg)) / self.SPEED + 0.5

    @staticmethod
    def messages():
        return [m for m in list(SETTINGS.get("messages", [])) + [custom_msg] if m]

    @staticmethod
    def available():
        return bool(Note.messages())

    def draw(self, t, dt):
        text(self.msg, W - t * self.SPEED, 2, pen(120, 220, 255))


# ---------------------------------------------------------------- autumn in Japan

TORII = [
    "kkkkkkkkkkk",
    ".rrrrrrrrr.",
    "...r.p.r...",
    ".rrrrrrrrr.",
    "...r...r...",
    "...r...r...",
    "...r...r...",
    "...r...r...",
    "...k...k...",
]
PAVILION = [
    "......f......",
    ".....fff.....",
    "...rrrrrrr...",
    "....ggggg....",
    "..rrrrrrrrr..",
    "...gGgGgGg...",
    ".rrrrrrrrrrr.",
    "..wbwbwbwbw..",
]


def momiji_pens():
    return [pen(230, 30, 20), pen(200, 20, 30), pen(250, 90, 10), pen(250, 150, 20), pen(170, 15, 15)]


class Momiji:
    """Red maple leaves (momiji) for any scene: drift down and away."""

    def __init__(self, n, cols):
        self.cols = cols
        self.l = [[random.uniform(0, W), random.uniform(-H, H), random.uniform(1.0, 2.4), random.uniform(0, 6.28),
                   random.choice(cols)] for _ in range(n)]

    def draw(self, t, dt, wind=-1.5):
        for lf in self.l:
            lf[1] += lf[2] * dt
            sway = math.sin(t * 1.7 + lf[3])
            lf[0] += (wind + sway * 1.8) * dt
            if lf[1] > H or lf[0] < -1 or lf[0] > W + 1:
                lf[0], lf[1] = random.uniform(0, W + 8), random.uniform(-4, -1)
            px(lf[0], lf[1], lf[4])
            if sway > 0.5:
                px(lf[0] + 1, lf[1], lf[4])


class Torii:
    """A walk through the thousand red gates of Fushimi Inari, maple leaves falling."""
    dur = 24
    GAP = 14

    def __init__(self):
        self.cols = {"r": pen(230, 60, 10), "k": pen(80, 45, 45), "p": pen(250, 200, 80)}
        self.bg = [pen(4, 10 + 6 * y / H, 4) for y in range(H)]
        self.path = pen(45, 40, 35)
        self.leaves = Momiji(10, momiji_pens())
        self.lamps = pen(255, 170, 60)

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.bg[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.path)
        gfx.rectangle(0, H - 2, W, 2)
        off = (t * 4) % self.GAP
        red, black = self.cols["r"], self.cols["k"]
        for i in range(-1, W // self.GAP + 2):
            x = int(i * self.GAP - off)
            gfx.set_pen(black)                      # drawn with rectangles (the sprite is too slow x5)
            gfx.rectangle(x, 1, 11, 1)
            gfx.rectangle(x + 3, 9, 1, 1)
            gfx.rectangle(x + 7, 9, 1, 1)
            gfx.set_pen(red)
            gfx.rectangle(x + 1, 2, 9, 1)
            gfx.rectangle(x + 1, 4, 9, 1)
            gfx.rectangle(x + 3, 3, 1, 6)
            gfx.rectangle(x + 7, 3, 1, 6)
            px(x + 5, 3, self.cols["p"])
            glow = wave(t, 2.5, 0.5, 1.0, i)
            px(x + 5, H - 3, pen(255 * glow, 150 * glow, 40 * glow))     # little lantern under each gate
        self.leaves.draw(t, dt)


class Kinkaku:
    """Kinkaku-ji, the Golden Pavilion, glowing over its pond with maples on either side."""
    dur = 24
    WATER = 8
    PX = 20

    def __init__(self):
        cols = {"f": (255, 220, 60), "r": (45, 25, 15), "g": (240, 175, 20), "G": (255, 215, 70),
                "w": (200, 170, 120), "b": (70, 45, 25)}
        maple = ((230, 30, 20), (200, 20, 30), (250, 90, 10), (250, 150, 20), (170, 15, 15))
        pine = (10, 50, 20)
        wy = self.WATER
        scene = [[(30 + 120 * y // wy, 50 + 60 * y // wy, 120 - 40 * y // wy)] * W for y in range(wy)]
        for peak, half in ((16, 6), (37, 7)):                   # dark pine hills behind
            for y in range(1, wy):
                for x in range(W):
                    if abs(x - peak) <= half * (y - 1) / (wy - 2):
                        scene[y][x] = pine
        for cx in (3, 8, 45, 50):                               # maple trees
            for y in range(1, wy):
                for x in range(max(0, cx - 4), min(W, cx + 5)):
                    if ((x - cx) / 4.2) ** 2 + ((y - 4) / 3.4) ** 2 < 1 and random.random() < 0.85:
                        scene[y][x] = random.choice(maple) if random.random() < 0.8 else pine
        for j, row in enumerate(PAVILION):
            for i in range(len(row)):
                if row[i] in cols:
                    scene[j][self.PX + i] = cols[row[i]]
        self.above = [[pen(*c) for c in row] for row in scene]
        self.below = []
        for y in range(wy, H):                                  # the pond mirrors it, darker and bluer
            r = scene[2 * wy - 1 - y]
            self.below.append([pen(c[0] * 0.45, c[1] * 0.5, c[2] * 0.6 + 20) for c in r])
        self.leaves = Momiji(4, momiji_pens())
        self.glint = pen(255, 250, 200)

    def draw(self, t, dt):
        for y in range(self.WATER):
            row = self.above[y]
            for x in range(W):
                gfx.set_pen(row[x])
                gfx.pixel(x, y)
        for k in range(2):                                      # a few gold pixels catch the light
            if random.random() < 0.3:
                px(random.randint(self.PX + 3, self.PX + 9), random.choice((3, 5)), self.glint)
        for j, row in enumerate(self.below):
            y = self.WATER + j
            shift = int(round(math.sin(t * 2 + y * 1.3) * 0.9))
            for x in range(W):
                gfx.set_pen(row[min(W - 1, max(0, x + shift))])
                gfx.pixel(x, y)
        self.leaves.draw(t, dt, wind=-0.6)


class Fuji:
    """Mt Fuji at sunset with the shinkansen zipping past."""
    dur = 22

    def __init__(self):
        self.sky = [pen(60 + 180 * y / 9, 20 + 80 * y / 9, 80 - 50 * y / 9) for y in range(H)]
        self.sun = pen(255, 120, 40)
        self.mtn = pen(40, 50, 100)
        self.snow = pen(235, 235, 255)
        self.ground = pen(15, 25, 15)
        self.body, self.stripe, self.window = pen(240, 240, 240), pen(20, 60, 200), pen(30, 40, 80)
        self.rail = pen(80, 80, 80)
        self.cloud = pen(250, 160, 130)
        self.clouds = [[random.uniform(0, W), random.randint(1, 3), random.randint(4, 7)] for _ in range(3)]
        self.train_x, self.wait = W + 10, 2.0

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        gfx.set_pen(self.sun)
        gfx.circle(12, 5, 2)
        for c in self.clouds:
            c[0] -= dt * 1.2
            if c[0] < -c[2]:
                c[0] = W + 2
            gfx.set_pen(self.cloud)
            gfx.rectangle(int(c[0]), c[1], c[2], 1)
        gfx.set_pen(self.mtn)
        gfx.triangle(15, H - 2, 30, 1, 45, H - 2)
        gfx.rectangle(28, 1, 5, 1)
        gfx.set_pen(self.snow)
        gfx.rectangle(28, 1, 5, 1)
        gfx.rectangle(27, 2, 7, 1)
        for x, d in ((26, 1), (28, 2), (30, 1), (32, 2), (34, 1)):     # jagged snow line
            gfx.rectangle(x, 3, 1, d)
        gfx.set_pen(self.ground)
        gfx.rectangle(0, H - 3, W, 3)
        gfx.set_pen(self.rail)
        gfx.rectangle(0, H - 1, W, 1)
        if self.wait > 0:
            self.wait -= dt
            return
        self.train_x -= dt * 70
        x = int(self.train_x)
        n = 44
        gfx.set_pen(self.body)
        gfx.rectangle(x + 3, H - 4, n, 1)
        gfx.rectangle(x + 1, H - 3, n + 2, 1)
        px(x + 2, H - 4, self.body)
        gfx.set_pen(self.stripe)
        gfx.rectangle(x, H - 2, n + 3, 1)
        for wx in range(x + 7, x + n, 3):
            px(wx, H - 4, self.window)
        if x + n < -2:
            self.train_x, self.wait = W + 10, random.uniform(2, 5)


# ---------------------------------------------------------------- Japanese words (kotoba)

# A tiny 3x5 capital-letter font, so two lines of 13 letters fit on the 11 rows.
TINY = {    # 15-bit masks: 5 rows of 3 pixels, top-left first
    'A': 23530, 'B': 15083, 'C': 25166, 'D': 15211, 'E': 29391, 'F': 4815,
    'G': 27470, 'H': 23533, 'I': 29847, 'J': 11044, 'K': 23277, 'L': 29257,
    'M': 23549, 'N': 23407, 'O': 11114, 'P': 4843, 'Q': 26474, 'R': 23275,
    'S': 14478, 'T': 9367, 'U': 31597, 'V': 11117, 'W': 24557, 'X': 23213,
    'Y': 9389, 'Z': 29351, ' ': 0, ',': 5120, '.': 8192, '-': 448,
    '(': 17556, ')': 5265, '"': 45, "'": 18, '!': 8338, '?': 8355,
    '/': 4772, ';': 5136,
    '0': 31599, '1': 29850, '2': 29671, '3': 31143, '4': 18925, '5': 31183, '6': 31695, '7': 9383,
    '8': 31727, '9': 31215, ':': 520, '%': 21157,
}


NARROW = " :."     # characters that only take 2 columns


def tiny_width(s):
    return sum(2 if ch in NARROW else 4 for ch in s) - 1


def tiny_text(s, x, y, p):
    gfx.set_pen(p)
    for ch in s:
        bits = TINY.get(ch, 0)
        for i in range(15):
            if bits >> i & 1:
                gfx.pixel(x + i % 3, y + i // 3)
        x += 2 if ch in NARROW else 4               # narrow spaces leave more room for letters


class Kotoba:
    """A Japanese flashcard (words sent by the Pi as kotoba.json, 10 a day): the word in big letters, then the card
    flips over to its English meaning, and back, three times round. One word per visit; the next visit has the next."""
    SHOW = 3.6          # seconds each side stays up
    FLIP = 0.7          # seconds per flip
    ROUNDS = 3
    FADE = 0.7
    next_word = 0

    @staticmethod
    def available():
        try:
            import os
            os.stat("kotoba.json")
            return True
        except OSError:
            return False

    def __init__(self):
        import json
        with open("kotoba.json") as f:
            words = json.load(f)["words"]
        w = words[Kotoba.next_word % len(words)]
        Kotoba.next_word = (Kotoba.next_word + 1) % len(words)
        self.faces = (w["w"], w["m"])
        self.timeline = []              # (start, end, side shown or None while flipping, flip from, flip to)
        t, side = 0.0, 0
        for k in range(self.ROUNDS * 2):
            self.timeline.append((t, t + self.SHOW, side))
            t += self.SHOW
            if k < self.ROUNDS * 2 - 1:
                self.timeline.append((t, t + self.FLIP, None))
                t += self.FLIP
                side = 1 - side
        self.dur = t
        self.sky = [pen(22 - 8 * y / H, 8 + 2 * y / H, 26 - 4 * y / H) for y in range(H)]   # dim plum night
        self.stars = [(random.randrange(W), random.randrange(H), random.uniform(0, 6.28)) for _ in range(9)]
        self.card = ((48, 22, 30), (18, 36, 52))          # front: deep plum, back: deep blue
        self.edge = ((110, 55, 60), (50, 90, 120))
        self.ink = ((255, 185, 100), (235, 230, 210))       # the word in warm orange, the meaning in cream

    def fit(self, s):
        """The biggest of the Unicorn's fonts that fits the card without scrolling."""
        for font, y in (("bitmap8", 2), ("bitmap6", 3)):
            if text_width(s, font) <= W - 4:
                return font, y
        return None, 3

    def draw(self, t, dt):
        for y in range(H):
            gfx.set_pen(self.sky[y])
            gfx.rectangle(0, y, W, 1)
        for x, y, ph in self.stars:
            v = wave(t, 0.8, 0, 38, ph)
            px(x, y, pen(v, v * 0.85, v * 0.7))
        seg = self.timeline[-1]
        for s in self.timeline:
            if s[0] <= t < s[1]:
                seg = s
        start, end, side = seg
        width = 1.0
        if side is None:                                    # mid-flip: the card narrows, turns, widens again
            p = (t - start) / (end - start)
            before = self.timeline[self.timeline.index(seg) - 1][2]
            side = before if p < 0.5 else 1 - before
            width = abs(math.cos(p * math.pi))
        v = max(0, min(1, t / self.FADE, (self.dur - t) / self.FADE))
        cw = max(1, int(W * width + 0.5))
        x0 = (W - cw) // 2

        def shade(rgb, k=1.0):
            return pen(rgb[0] * v * k, rgb[1] * v * k, rgb[2] * v * k)
        gfx.set_pen(shade(self.card[side], 0.6 + 0.4 * width))
        gfx.rectangle(x0, 0, cw, H)
        gfx.set_pen(shade(self.edge[side], 0.6 + 0.4 * width))
        gfx.rectangle(x0, 0, cw, 1)
        gfx.rectangle(x0, H - 1, cw, 1)
        gfx.rectangle(x0, 0, 1, H)
        gfx.rectangle(x0 + cw - 1, 0, 1, H)
        if width > 0.15:
            words = self.faces[side]
            font, y = self.fit(words)
            gfx.set_clip(x0 + 1, 1, max(1, cw - 2), H - 2)
            ink = shade(self.ink[side], width)
            if font:
                text(words, (W - text_width(words, font)) // 2, y, ink, font)
            else:
                up = words.upper()
                tiny_text(up, (W - tiny_width(up)) // 2, y, ink)
            gfx.remove_clip()


class Fireworks:
    """Fireworks: gold and silver for New Year's (with the year), red, white and blue for the 4th."""
    dur = 22

    def __init__(self):
        y, m, d = today()
        self.fourth = m in (6, 7)
        if self.fourth:
            self.cols = [(255, 40, 40), (240, 240, 255), (60, 90, 255)]
            self.word = ""
        else:
            self.cols = [(255, 200, 60), (230, 230, 255), (255, 90, 160), (80, 220, 255), (150, 255, 120)]
            self.word = str(y + 1 if m == 12 else y)
        self.shells, self.sparks = [], []
        self.wait = 0.3
        self.stars = Stars(6, 6)

    def draw(self, t, dt):
        self.stars.draw(t)
        if self.word:
            v = wave(t, 0.8, 0.25, 0.7)
            text(self.word, (W - text_width(self.word)) // 2, 2, pen(255 * v, 200 * v, 90 * v))
        self.wait -= dt
        if self.wait <= 0 and len(self.shells) < 3:
            self.shells.append([random.uniform(6, W - 6), H, random.uniform(1.5, 5), random.choice(self.cols)])
            self.wait = random.uniform(0.4, 1.3)
        for sh in self.shells:
            sh[1] -= dt * 9
            px(sh[0], sh[1], pen(200, 160, 120))
            px(sh[0], sh[1] + 1, pen(70, 50, 30))
            if sh[1] <= sh[2]:
                n = random.randint(10, 16)
                for i in range(n):
                    a = i / n * 6.283
                    sp = random.uniform(3.5, 6)
                    self.sparks.append([sh[0], sh[1], math.cos(a) * sp, math.sin(a) * sp * 0.7, 1.0, sh[3]])
        self.shells = [sh for sh in self.shells if sh[1] > sh[2]]
        for p in self.sparks:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 4 * dt                      # gravity
            p[2] *= 0.97
            p[4] -= dt * 0.7
            v = max(0, p[4])
            c = p[5]
            if v > 0.15 or random.random() < 0.5:   # twinkle out at the end
                px(p[0], p[1], pen(c[0] * v, c[1] * v, c[2] * v))
        self.sparks = [p for p in self.sparks if p[4] > 0 and p[1] < H]


class Flag:
    """The stars and stripes, rippling in the breeze (for the flag holidays)."""
    dur = 18
    CANTON_W, CANTON_H = 22, 6

    def __init__(self):
        self.red = [pen(220 * k, 20 * k, 30 * k) for k in (0.45, 0.6, 0.8, 1.0)]
        self.white = [pen(230 * k, 230 * k, 235 * k) for k in (0.45, 0.6, 0.8, 1.0)]
        self.blue = [pen(30 * k, 50 * k, 190 * k) for k in (0.45, 0.6, 0.8, 1.0)]
        self.star = [pen(255 * k, 255 * k, 255 * k) for k in (0.45, 0.6, 0.8, 1.0)]

    def draw(self, t, dt):
        cw, ch = self.CANTON_W, self.CANTON_H
        for x in range(0, W, 2):                    # two columns at a time (the Unicorn draws it twice as fast)
            k = math.sin(x * 0.35 - t * 4)
            shade = max(0, min(3, int(2.5 + 1.5 * k)))   # light and shadow roll along the cloth
            lift = int(round(k * 0.6 * x / W))
            for y in range(H):
                yy = y - lift
                if x < cw and 0 <= yy < ch:
                    p = self.star[shade] if (x % 4 == 0 and yy % 2 == 0) or (x % 4 == 2 and yy % 2 == 1) \
                        else self.blue[shade]
                else:
                    p = self.red[shade] if yy % 2 == 0 else self.white[shade]
                gfx.set_pen(p)
                gfx.rectangle(x, y, 2, 1)



REMINDERS = {"Mother's Day": (10, 5), "Father's Day": (10, 5)}    # days ahead to nudge: "did you get a gift?"


def gift_reminders():
    y, m, d = today()
    out = []
    for name, days in REMINDERS.items():
        hm, hd = holiday_date(name, y)
        k = day_of_year(y, hm, hd) - day_of_year(y, m, d)
        if k in days:
            out.append(("Hey, %s is in %d days! Did you get a gift?" % (name, k), "gift"))
    return out


class Reminder(Countdown):
    """A nudge, all day, 10 and 5 days before Mother's Day and Father's Day."""
    turn = 0

    @staticmethod
    def available():
        return clock_synced() and bool(gift_reminders())

    @staticmethod
    def messages():
        return gift_reminders()


# ---------------------------------------------------------------- the weather outside (weather.json from the Pi)

_wx = [None, None]       # [raw file text, parsed]


def weather():
    """Latest weather sent by the Pi (weather/weather.py), or None if there's none or it's over 3 hours old."""
    try:
        with open("weather.json") as f:
            raw = f.read()
    except OSError:
        return None
    if raw != _wx[0]:
        try:
            import json
            _wx[0], _wx[1] = raw, json.loads(raw)
        except ValueError:
            return None
    w = _wx[1]
    lt = time.localtime()
    try:
        d, hm = w["t"].split("T")
        y, m, dd = [int(v) for v in d.split("-")]
        age = (day_of_year(lt[0], lt[1], lt[2]) - day_of_year(y, m, dd)) * 1440 + lt[3] * 60 + lt[4] \
            - int(hm[:2]) * 60 - int(hm[3:5])
    except (KeyError, ValueError, IndexError):
        return None
    return w if clock_synced() and -60 < age < 180 else None


def minutes_now():
    lt = time.localtime()
    return lt[3] * 60 + lt[4]


def is_night(w):
    m = minutes_now()
    return m < w.get("rise", 420) or m > w.get("set", 1140)


def moon_phase():
    """0 = new, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter."""
    y, m, d = today()
    leaps = (y - 1) // 4 - 499 - ((y - 1) // 100 - 19) + ((y - 1) // 400 - 4)     # leap days since 2000
    days = (y - 2000) * 365 + leaps + day_of_year(y, m, d) - 1 + time.localtime()[3] / 24 - 5.76   # new moon 6 Jan 2000
    return (days % 29.530588853) / 29.530588853


def moon_name(p):
    return ("new moon", "waxing crescent", "first quarter", "waxing gibbous", "full moon", "waning gibbous",
            "last quarter", "waning crescent")[int(p * 8 + 0.5) % 8]


def moon_pixels(r, p):
    """[(dx, dy, lit)] for a moon of radius r at phase p."""
    k = math.cos(2 * math.pi * p)
    out = []
    for y in range(-r, r + 1):
        ry = math.sqrt(max(0, r * r - y * y + r * 0.5))
        for x in range(-r, r + 1):
            if abs(x) <= ry:
                xn, span = x / r, ry / r
                out.append((x, y, xn > k * span if p < 0.5 else xn < -k * span))
    return out


def season_ground(m, kind):
    if kind == "snow" or m in (12, 1, 2):
        return (200, 210, 235), (150, 160, 190)
    if m in (3, 4, 5):
        return (90, 190, 80), (60, 140, 50)
    if m in (6, 7, 8):
        return (40, 140, 40), (25, 100, 30)
    return (190, 100, 30), (120, 60, 20)


class Outside:
    """A window on the real weather: the sun (or moon) where it actually is, clouds, rain, snow, fog, lightning,
    and the ground dressed for the season."""
    dur = 22

    @staticmethod
    def available():
        return weather() is not None

    def __init__(self):
        w = self.w = weather()
        self.kind = w["kind"]
        m = minutes_now()
        rise, set_ = w["rise"], w["set"]
        self.night = is_night(w)
        dusk = min(abs(m - rise), abs(m - set_)) < 40
        grey = self.kind in ("cloudy", "rain", "snow", "storm", "fog")
        if self.night:
            top, bottom = (2, 4, 16), (10, 14, 40)
        elif dusk:
            top, bottom = (60, 50, 120), (255, 130, 60)
        elif grey:
            top, bottom = (90, 95, 110), (140, 145, 160)
        else:
            top, bottom = (40, 110, 230), (130, 190, 255)
        if self.kind == "storm":
            top, bottom = (30, 30, 45), (60, 60, 75)
        self.sky = [pen(top[0] + (bottom[0] - top[0]) * y / 8, top[1] + (bottom[1] - top[1]) * y / 8,
                        top[2] + (bottom[2] - top[2]) * y / 8) for y in range(H)]
        self.sun_x = 3 + (m - rise) / max(1, set_ - rise) * (W - 6)
        self.sun_y = 8 - math.sin(max(0, min(1, (m - rise) / max(1, set_ - rise))) * math.pi) * 6
        self.moon = moon_pixels(2, moon_phase()) if self.night and not grey else []
        self.stars = Stars(12, 6) if self.night and not grey else None
        n = max(0, min(6, w.get("cloud", 0) // 16))
        if grey:
            n = 6
        cc = (40, 45, 60) if self.night else ((80, 80, 95) if self.kind == "storm" else
                                              ((170, 175, 190) if grey else (245, 248, 255)))
        self.cloud = pen(*cc)
        self.cloud2 = pen(cc[0] * 0.8, cc[1] * 0.8, cc[2] * 0.8)
        self.clouds = [[random.uniform(0, W), random.randint(0, 3), random.randint(5, 11)] for _ in range(n)]
        self.wind = 1 + w.get("wind", 5) / 6
        busy = {"rain": 16, "storm": 22, "snow": 16}.get(self.kind, 0)
        self.drops = [[random.uniform(0, W), random.uniform(0, H), random.uniform(0, 6)] for _ in range(busy)]
        self.drop = pen(110, 150, 255) if self.kind != "snow" else pen(235, 240, 255)
        g1, g2 = season_ground(today()[1], self.kind)
        self.ground, self.ground2 = pen(*g1), pen(*g2)
        if self.night:
            self.ground, self.ground2 = pen(g1[0] * 0.25, g1[1] * 0.25, g1[2] * 0.3), pen(g2[0] * 0.2, g2[1] * 0.2, g2[2] * 0.25)
        self.house = pen(70, 40, 30) if not self.night else pen(25, 15, 15)
        self.roof = pen(120, 40, 30) if not self.night else pen(40, 20, 20)
        self.window = pen(255, 190, 80) if self.night or grey else pen(120, 170, 220)
        self.pine = pen(20, 80, 35) if not self.night else pen(8, 25, 14)
        self.fog = pen(170, 175, 185) if not self.night else pen(50, 55, 65)
        self.flash = 0.0
        self.bolt = None

    def draw(self, t, dt):
        f = self.flash
        for y in range(H):
            gfx.set_pen(self.sky[y] if f <= 0 else pen(230 * f, 230 * f, 255 * f))
            gfx.rectangle(0, y, W, 1)
        if self.stars:
            self.stars.draw(t)
        if self.moon:
            dark = pen(30, 30, 40)
            lit = pen(240, 235, 200)
            for dx, dy, on in self.moon:
                px(42 + dx, 2 + dy, lit if on else dark)
        elif not self.night and self.kind not in ("storm", "rain", "snow"):
            gfx.set_pen(pen(255, 220, 90))
            gfx.circle(int(self.sun_x), int(self.sun_y), 2)
        for c in self.clouds:
            c[0] += self.wind * dt
            if c[0] > W:
                c[0] = -c[2]
            gfx.set_pen(self.cloud)
            gfx.rectangle(int(c[0]), c[1] + 1, c[2], 2)
            gfx.set_pen(self.cloud2)
            gfx.rectangle(int(c[0]) + 2, c[1], c[2] - 4, 1)
        for d in self.drops:
            if self.kind == "snow":
                d[1] += dt * 2
                d[0] += (math.sin(t + d[2]) * 0.8 + self.wind * 0.3) * dt
            else:
                d[1] += dt * 11
                d[0] += self.wind * 0.4 * dt
            if d[1] > H - 2:
                d[0], d[1] = random.uniform(-3, W), random.uniform(1, 3)
            px(d[0], d[1], self.drop)
        if self.kind == "storm":
            if random.random() < dt / 4:            # every few seconds: a flash and a bolt
                x, self.bolt = random.randint(10, W - 10), []
                for y in range(3, H - 2):
                    x += random.choice((-1, 0, 1))
                    self.bolt.append((x, y))
                self.flash = 0.8
            if self.bolt and self.flash > 0.3:
                for x, y in self.bolt:
                    px(x, y, pen(255, 255, 220))
            self.flash = max(0.0, self.flash - dt * 2.5)
        gfx.set_pen(self.pine)                      # home sweet home
        for x, h in ((3, 5), (6, 7), (48, 6)):
            gfx.triangle(x - 2, H - 2, x, H - 2 - h, x + 2, H - 2)
        gfx.set_pen(self.house)
        gfx.rectangle(12, H - 5, 7, 3)
        gfx.set_pen(self.roof)
        gfx.triangle(11, H - 5, 15, H - 8, 19, H - 5)
        px(14, H - 4, self.window)
        px(17, H - 4, self.window)
        gfx.set_pen(self.ground)
        gfx.rectangle(0, H - 2, W, 2)
        gfx.set_pen(self.ground2)
        gfx.rectangle(0, H - 1, W, 1)
        if self.kind == "fog":
            for y in (4, 6, 8):
                off = int(t * 2 + y * 7) % 12
                gfx.set_pen(self.fog)
                for x in range(-off, W, 12):
                    gfx.rectangle(x, y, 7, 1)


WX_ICONS = {   # 9x7 weather pictures for the forecast
    "clear": (["y...y...y", ".y.yyy.y.", "..yyyyy..", "yyyyyyyyy", "..yyyyy..", ".y.yyy.y.", "y...y...y"],
              {"y": (255, 200, 40)}),
    "night": (["...mmm...", "..mm.....", ".mm......", ".mm......", ".mm......", "..mm...m.", "...mmmm.."],
              {"m": (240, 230, 180)}),
    "partly": (["y..y.....", ".yyy.....", "yyy.wwww.", ".y.wwwwww", "..wwwwwww", "wwwwwwwww", "........."],
               {"y": (255, 200, 40), "w": (230, 235, 245)}),
    "cloudy": (["...www...", "..wwwww..", ".wwwwwwgg", "wwwwwwwgg", "ggggggggg", ".........", "........."],
               {"w": (210, 215, 225), "g": (150, 155, 170)}),
    "fog": (["ggggggg..", ".........", "..ggggggg", ".........", "ggggggg..", ".........", "..ggggggg"],
            {"g": (170, 175, 190)}),
    "rain": (["..wwwww..", ".wwwwwww.", "wwwwwwwww", ".........", ".b..b..b.", "b..b..b..", "........."],
             {"w": (170, 175, 190), "b": (90, 140, 255)}),
    "snow": (["..wwwww..", ".wwwwwww.", "wwwwwwwww", ".........", ".s..s..s.", "...s..s..", ".s.....s."],
             {"w": (170, 175, 190), "s": (240, 245, 255)}),
    "storm": (["..ggggg..", ".ggggggg.", "ggggggggg", "....yy...", "...yy....", "....yy...", "...y....."],
              {"g": (90, 90, 105), "y": (255, 230, 60)}),
}


class Forecast:
    """The local weather in pages: the temperature, what it's doing, today's high and low, what's coming."""
    PAGE = 3.2

    @staticmethod
    def available():
        return weather() is not None

    def __init__(self):
        w = weather()
        kind = w["kind"]
        icon = "night" if kind in ("clear", "partly") and is_night(w) else kind
        rows, cols = WX_ICONS.get(icon, WX_ICONS["cloudy"])
        self.icon = Runs(rows)
        self.cols = {k: pen(*c) for k, c in cols.items()}
        self.pages = w.get("pages") or ["%d°" % w["temp"]]
        self.dur = self.PAGE * len(self.pages) + 0.5
        tmp = w["temp"]
        warm = max(0, min(1, (tmp - 20) / 60))      # cold blue ... warm orange
        self.ink = (255 * (0.5 + 0.5 * warm), 160 + 40 * warm - 40 * (1 - warm), 255 * (1 - warm) + 60 * warm)

    def fit(self, s):
        plain, extra = s.replace("°", ""), (3 if "°" in s else 0)
        for font, y in (("bitmap8", 2), ("bitmap6", 3)):
            if text_width(plain, font) + extra <= W - 12:
                return font, y
        return None, 3

    def draw(self, t, dt):
        self.icon.draw(1, 2, self.cols)
        i = min(len(self.pages) - 1, int(t / self.PAGE))
        k = (t / self.PAGE) % 1
        v = min(1, k * 5, (1 - k) * 5) if t < self.dur - 0.5 else 0
        s = self.pages[i]
        r, g, b = self.ink
        p = pen(r * v, g * v, b * v)
        font, y = self.fit(s)
        if font is None:                            # too long: the tiny font
            up = s.upper().replace("°", "")
            lines = [up]
            if tiny_width(up) > W - 11 and " " in up:     # still too wide: two lines
                words = up.split(" ")
                cut = max(1, len(words) // 2)
                lines = [" ".join(words[:cut]), " ".join(words[cut:])]
            for i, line in enumerate(lines):
                y = 3 if len(lines) == 1 else i * 6
                tiny_text(line, max(10, 11 + (W - 11 - tiny_width(line)) // 2), y, p)
            return
        plain = s.replace("°", "")
        width = text_width(plain, font) + (3 if "°" in s else 0)
        x = 11 + (W - 11 - width) // 2
        if "°" in s:                                # the fonts have no degree sign: draw a tiny one
            before = s.split("°")[0]
            text(before, x, y, p, font)
            dx = x + text_width(before, font)
            gfx.set_pen(p)
            gfx.rectangle(dx, y, 2, 2)
            text(s.split("°")[1], dx + 3, y, p, font)
        else:
            text(s, x, y, p, font)


class Moon:
    """Tonight's moon, in its real phase, with its name."""
    dur = 12

    @staticmethod
    def available():
        w = weather()
        return w is not None and is_night(w)

    def __init__(self):
        p = moon_phase()
        self.pix = moon_pixels(4, p)
        self.words = moon_name(p).upper().split()
        self.pct = "%d%% lit" % round((1 - math.cos(2 * math.pi * p)) / 2 * 100)
        self.stars = Stars(10, H)
        self.lit, self.dark = pen(245, 240, 210), pen(28, 28, 40)

    def draw(self, t, dt):
        self.stars.draw(t)
        for dx, dy, on in self.pix:
            gfx.set_pen(self.lit if on else self.dark)
            gfx.pixel(7 + dx, 5 + dy)
        v = min(1, t, self.dur - t)
        ink = pen(240 * v, 230 * v, 190 * v)
        if t < 7:
            for i, word in enumerate(self.words):
                tiny_text(word, 14 + (W - 14 - tiny_width(word)) // 2, i * 6, ink)
        else:
            text(self.pct, 14 + (W - 14 - text_width(self.pct, "bitmap6")) // 2, 3, ink, "bitmap6")


# ---------------------------------------------------------------- alarms, timers and your own animations

alert = [None]          # text to show right away (an alarm went off, or a timer finished)
timer = [None, ""]      # [ticks_ms when it rings, label] while a kitchen timer is running


class Alert:
    """An alarm's (or a finished timer's) message, flashing, three times across. Any button stops it."""
    SPEED = 14

    def __init__(self):
        self.msg = alert[0] or ""
        alert[0] = None
        self.tw = text_width(self.msg)
        self.dur = 3 * (W + self.tw) / self.SPEED

    def draw(self, t, dt):
        k = wave(t, 8)
        gfx.set_pen(pen(60 * k, 20 * k, 0))
        gfx.rectangle(0, 0, W, 1)
        gfx.rectangle(0, H - 1, W, 1)
        text(self.msg, W - (t * self.SPEED) % (W + self.tw), 2, pen(255, 200 + 55 * k, 80 + 100 * k))


class Timer:
    """A kitchen timer ("TIMER 300 Tea"): its name and the minutes and seconds left, until it rings."""
    dur = 1e9           # stays until it rings (A cancels it)

    def __init__(self):
        self.label = timer[1]
        self.lw = text_width(self.label, "bitmap6") if self.label else 0

    @staticmethod
    def available():
        return timer[0] is not None

    def draw(self, t, dt):
        if timer[0] is None:
            return
        left = max(0, time.ticks_diff(timer[0], time.ticks_ms()) // 1000)
        s = "%d:%02d" % (left // 60, left % 60) if left < 3600 else "%d:%02d:%02d" % (left // 3600, left // 60 % 60,
                                                                                       left % 60)
        sw = text_width(s)
        if self.label and self.lw + sw + 4 <= W:
            text(self.label, 1, 3, pen(120, 200, 255), "bitmap6")
            text(s, W - sw, 2, pen(255, 190, 60))
        else:
            text(s, (W - sw) // 2, 2, pen(255, 190, 60))
        gfx.set_pen(pen(255 * wave(t, 6), 120, 0))           # a little ticking light in the corner
        gfx.pixel(0, 0)


def check_timer():
    if timer[0] is not None and time.ticks_diff(timer[0], time.ticks_ms()) <= 0:
        alert[0] = (timer[1] + " done!") if timer[1] else "Time's up!"
        timer[0] = None
        speaker.play(SETTINGS.get("timer_sound", "chime"))


_chimed = {}


def alarms():
    """The alarms from settings.json: {"time": "17:00", "days": [0..6, Monday = 0], "sound": "konbini", "text": ...}."""
    if not clock_synced():
        return
    lt = time.localtime()
    hm = "%02d:%02d" % (lt[3], lt[4])
    for i, a in enumerate(SETTINGS.get("alarms", ())):
        if a.get("time") == hm and lt[6] in a.get("days", (0, 1, 2, 3, 4, 5, 6)) and _chimed.get(i) != lt[2]:
            _chimed[i] = lt[2]
            if a.get("sound"):
                try:
                    speaker.play(a["sound"])
                except (KeyError, ValueError, IndexError):
                    pass
            if a.get("text"):
                alert[0] = a["text"]


class Pixels:
    """One of your own pixel animations, drawn in Unicorn Studio (art_<id>.json): frames of 53x11 pixels, each
    pixel a letter for its colour in the palette ("." is black), played at fps, with an optional scrolling text."""
    ID = ""

    def __init__(self):
        import json
        with open("art_%s.json" % self.ID) as f:
            a = json.load(f)
        pens = [pen(*c) for c in a["palette"]]
        self.frames = []
        for fr in a["frames"]:                    # each frame as runs of one colour, for quick drawing
            runs = []
            for y in range(H):
                row = fr[y * W:(y + 1) * W]
                x = 0
                while x < len(row):
                    n = 1
                    while x + n < len(row) and row[x + n] == row[x]:
                        n += 1
                    if row[x] != ".":
                        runs.append((pens[int(row[x], 36)], x, y, n))
                    x += n
            self.frames.append(runs)
        del a["frames"]
        self.fps = max(0.5, a.get("fps", 4))
        self.msg = a.get("text", "")
        self.ink = pen(*a.get("text_color", (255, 255, 255)))
        self.tw = text_width(self.msg) if self.msg else 0
        self.dur = a.get("dur") or ((W + self.tw) / 12 + 1 if self.msg else 12)

    def draw(self, t, dt):
        last = None
        for p, x, y, n in self.frames[int(t * self.fps) % len(self.frames)]:
            if p is not last:
                gfx.set_pen(p)
                last = p
            gfx.rectangle(x, y, n, 1)
        if self.msg:
            text(self.msg, W - t * 12, 2, self.ink)


def art_scene(e):
    class Art(Pixels):
        ID = e["id"]
    return Art


def name_of(cls):
    return getattr(cls, "ID", "") or cls.__name__


# ---------------------------------------------------------------- what plays when

ALWAYS = [Clock, Kotoba, Forecast, Countdown, Clock, Kotoba, Note, Forecast, Countdown]   # between seasonal scenes

SCENES = [  # (scene, when, how many times per round): the seasonal ones from this file
    (Leaves, during(9, 10, 11, 30), 1),
    (Latte, during(9, 20, 11, 30), 1),
    (Campfire, during(6, 1, 11, 10), 1),
    (Pumpkins, during(10, 1, 11, 8), 1),
    (Ghost, during(10, 1, 11, 1), 1),
    (Torii, during(10, 1, 11, 30), 1),           # autumn in Japan
    (Kinkaku, during(10, 1, 11, 30), 1),
    (Fuji, during(10, 1, 11, 30), 1),
    (Fireworks, during(12, 31, 1, 2), 2),
    (Fireworks, during(6, 30, 7, 5), 2),
    (Flag, during(6, 28, 7, 5), 2),
    (Flag, around("Memorial Day", 3), 2),
    (Flag, around("Labor Day", 2), 1),
    (Flag, around("Presidents' Day", 0), 1),
    (Flag, around("Veterans Day", 0), 1),
]

SEASON_FILES = ("winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer",
                "fall", "fall", "fall", "winter")       # more scenes for each month, in their own files
_season = [None, None]                                   # [name, module], one loaded at a time to save memory
season_error = ""


def season_module(m):
    global season_error
    name = SEASON_FILES[m - 1]
    if _season[0] != name:
        if _season[0]:
            sys.modules.pop(_season[0], None)
        _season[0], _season[1] = name, None
        gc.collect()
        try:
            _season[1] = __import__(name)
            season_error = ""
        except Exception as e:                           # a missing or broken file just means fewer scenes
            season_error = "%s: %r" % (name, e)
    return _season[1]


_mine = []              # [my_scenes module or None], loaded the first time it's needed
mine_error = ""
ARTS = [art_scene(e) for e in SETTINGS.get("art", ()) if e.get("id")]


def mine():
    """Your own scenes in my_scenes.py (see my_scenes_example.py), if there is one."""
    global mine_error
    if not _mine:
        try:
            import my_scenes
            _mine.append(my_scenes)
        except ImportError as e:
            _mine.append(None)
            if "my_scenes" not in str(e):
                mine_error = "my_scenes: %r" % e
        except Exception as e:
            _mine.append(None)
            mine_error = "my_scenes: %r" % e
    return _mine[0]


def find_scene(name):
    """A scene by its class name (or an animation's id), from anywhere: for "G Name"."""
    if name in globals() and hasattr(globals()[name], "draw"):
        return globals()[name]
    for cls in ARTS:
        if cls.ID == name:
            return cls
    for mod in (mine(), season_module(today()[1])):
        if mod and hasattr(getattr(mod, name, None), "draw"):
            return getattr(mod, name)
    for m in range(1, 13, 3):                           # another season's scene: load that season for a moment
        mod = season_module(m)
        if mod and hasattr(getattr(mod, name, None), "draw"):
            return getattr(mod, name)


def art_when(e):
    w = e.get("when")
    return during(*w) if w else lambda y, m, d: True


def build_playlist():
    """Today's round: the scenes in season, shuffled, with the everyday ones mixed in."""
    if not clock_synced() and not date_override:    # just switched on: it thinks it's 1 Jan 2021 until it learns
        return [c for c in (Campfire, Kotoba) if c.__name__ not in OFF] or [Clock]   # the time: nothing dated yet
    y, m, d = today()
    mod = season_module(m)
    my = mine()
    pool = []
    arts = [(cls, art_when(e), int(e.get("times", 1))) for cls, e in zip(ARTS, SETTINGS.get("art", ()))]
    for cls, when, n in SCENES + (getattr(mod, "SCENES", []) if mod else []) + getattr(my, "SCENES", []) + arts:
        if name_of(cls) in OFF:
            continue
        try:
            if when(y, m, d):
                pool += [cls] * n
        except Exception:
            pass
    w = weather()                                       # what's actually happening outside
    if w and "Outside" not in OFF:
        wet = w["kind"] in ("rain", "snow", "storm", "fog") or w.get("storm_soon")
        pool += [Outside] * (3 if wet else 1)
        if is_night(w) and w["kind"] in ("clear", "partly") and "Moon" not in OFF:
            pool.append(Moon)
        if mod:
            kinds = [w["kind"]] + (["storm"] if w.get("storm_soon") else [])
            if w["kind"] == "clear" and not is_night(w):
                kinds[0] = "sunny"                      # "clear" is for clear nights (aurora, fireflies)
            for k in kinds:
                for cls in getattr(mod, "WEATHER", {}).get(k, ()):
                    if cls in pool:                         # only scenes in season (and switched on) today: a
                        pool += [cls] * 2                   # sunny day in late October is no reason for apples
    if gift_reminders() and "Reminder" not in OFF:      # reminder days: it comes round again and again
        pool += [Reminder] * max(3, len(pool) // 2)
    if not pool:
        pool = [Campfire] if "Campfire" not in OFF else [Clock]
    order = []
    while len(order) < 12:
        left = pool[:]
        while left:
            cls = left.pop(random.randrange(len(left)))
            if order and order[-1] is cls and left:      # no scene twice in a row
                left.append(cls)
                cls = left.pop(0)
            order.append(cls)
    always = [cls for cls in ALWAYS + getattr(my, "ALWAYS", []) if name_of(cls) not in OFF] or [Clock]
    out = []
    for i, cls in enumerate(order):
        out.append(cls)
        if i % 2:
            out.append(always[(i // 2) % len(always)])
    for cls in always[len(order) // 2:]:                 # everything everyday gets a turn
        out.append(cls)
    return out


# ---------------------------------------------------------------- speaker

VOLUME = 0.3
try:
    with open("volume.txt") as f:
        VOLUME = max(0.0, min(1.0, float(f.read())))
except (OSError, ValueError):
    pass

BEAT_MS = 150
TUNES = {
    "beep": "A5:1",
    "chime": "E5:3 C5:3 D5:3 G4:6 -:2 G4:3 D5:3 E5:3 C5:6",
    "love": "C5:2 E5:2 G5:2 C6:4 -:1 G5:1 C6:6",
    "sakura": "A4:3 A4:3 B4:6 A4:3 A4:3 B4:6 A4:3 B4:3 C5:3 B4:3 A4:3 B4:2 A4:2 F4:6",
    "spooky": "E4:3 G4:3 A#4:3 A4:6 -:2 E4:2 D#4:8",
    "fanfare": "G4:2 C5:2 E5:2 G5:4 E5:2 G5:6",
    "doorbell": "E5:4 C5:6",
    "konbini": "E5:3 C5:3 G4:3 C5:3 D5:3 G5:5 -:1 D5:3 E5:3 D5:3 G4:3 C5:8",     # the FamilyMart door chime
}
TUNES.update(SETTINGS.get("tunes", {}))     # your own, from Unicorn Studio
SEMITONE = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0,
            "A#": 1, "B": 2}


def parse_tune(spec):
    """"C5:2 E5:2 -:1 G5:4" -> [(frequency or 0 for a rest, beats), ...]"""
    notes = []
    for word in TUNES.get(spec, spec).split():
        name, _, beats = word.partition(":")
        beats = float(beats) if beats else 2
        if name == "-":
            notes.append((0, beats))
        else:
            semis = SEMITONE[name[:-1].upper()] + (int(name[-1]) - 4) * 12
            notes.append((int(440 * 2 ** (semis / 12)), beats))
    return notes


class Speaker:
    """Plays a tune in the background while the scenes keep animating."""

    def __init__(self):
        self.ch = None
        self.notes = []
        self.next_at = 0
        self.release_at = None
        self.stop_at = None

    def play(self, spec):
        notes = parse_tune(spec)
        if not notes:
            return
        if self.ch is None:
            try:
                from galactic import Channel
                soft = Channel.TRIANGLE + Channel.SINE
            except ImportError:
                soft = 1 + 2
            self.ch = gu.synth_channel(0)
            self.ch.configure(waveforms=soft, attack=0.01, decay=0.12, sustain=0.6, release=0.12, volume=1.0)
        stream.stop()                               # the chime takes over the speaker (the stream waits)
        gu.set_volume(VOLUME)
        self.notes = notes
        self.next_at = time.ticks_ms()
        self.stop_at = None
        gu.play_synth()

    def busy(self):
        return bool(self.notes) or self.stop_at is not None

    def tick(self):
        if self.ch is None:
            return
        now = time.ticks_ms()
        if self.release_at is not None and time.ticks_diff(now, self.release_at) >= 0:
            self.ch.trigger_release()               # a short gap so repeated notes sound separate
            self.release_at = None
        if self.notes and time.ticks_diff(now, self.next_at) >= 0:
            freq, beats = self.notes.pop(0)
            length = int(beats * BEAT_MS)
            if freq:
                self.ch.frequency(freq)
                self.ch.trigger_attack()
                self.release_at = time.ticks_add(now, max(30, length - 40))
            self.next_at = time.ticks_add(now, length)
            if not self.notes:
                self.stop_at = time.ticks_add(self.next_at, 400)
        if self.stop_at is not None and time.ticks_diff(now, self.stop_at) >= 0:
            gu.stop_playing()
            self.stop_at = None


speaker = Speaker()


def set_volume(v):
    global VOLUME
    VOLUME = max(0.0, min(1.0, v))
    gu.set_volume(VOLUME)
    try:
        with open("volume.txt", "w") as f:
            f.write(str(VOLUME))
    except OSError:
        pass


# ---------------------------------------------------------------- the Pi's speaker (sound streamed over Wi-Fi)

where = [""]            # what the main loop is busy with (reported with the speaker's longest wait)


class Stream:
    """The Pi's speaker: it sends its sound here (TCP port 4243: raw 16-bit mono at 22050 Hz, from
    speaker/unicorn_speaker.py) whenever something is playing, already at the right volume.

    Works on the stock firmware. The sound buffer (audioring.py, grabbed at start-up) is played endlessly by the
    Unicorn's own audio DMA in hardware ring mode: it wraps around the buffer by itself, so the sound keeps going
    while the animation draws. The main loop tops it up every frame (and around scene changes), and clears what
    has already been played, so if Wi-Fi falls behind for a moment it's a short silence rather than an echo.
    (Not from a machine.Timer: on MicroPython 1.21 a Timer callback alongside Wi-Fi froze the Pico W.)"""
    PORT = 4243
    DMA = 0x50000000
    ENDLESS = 0x7ffffffe    # bytes: the transfer we start is "13 hours long" and wraps around the ring
    LEAD = 4000             # bytes (90 ms) queued ahead when starting, or after Wi-Fi falls behind
    SLACK = 512             # bytes never filled, so new sound can't overwrite what's about to play

    def __init__(self):
        import audioring
        self.ok = audioring.raw is not None
        self.server = self.conn = None
        self.playing = False
        self.heard = 0          # ticks_ms when audio last arrived
        self.underruns = 0
        self.drops = 0          # bits of sound skipped for arriving too far ahead
        self.gap = self.maxgap = 0  # longest wait between top-ups (ms)
        self.lowest = 99999     # least sound queued at a top-up (bytes)
        self.ch = None          # the audio DMA channel (found the first time we play)
        self.pumping = False
        self.underruns = self.drops = self.gap = self.maxgap = 0
        self.gapat = ""
        self.lowest = 99999
        if not self.ok:
            return
        import uctypes
        raw, size = audioring.raw, audioring.SIZE
        addr = uctypes.addressof(raw)
        self.base = (addr + size - 1) & ~(size - 1)
        off = self.base - addr
        mv = memoryview(raw)
        self.size = size
        self.ring = mv[off:off + size]
        spare = mv[:off] if off >= size - off else mv[off + size:]     # the other half of the allocation
        self.rx = spare[:4096]
        self.zeros = memoryview(bytes(256))

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except OSError:
                pass
        self.conn = None
        self.stop()

    def stop(self):
        """Stop the sound and put the DMA back to normal (the chimes need it without the ring)."""
        if self.playing:
            import machine
            gu.stop_playing()
            ctrl = self.DMA + self.ch * 0x40 + 0x10
            machine.mem32[ctrl] = machine.mem32[ctrl] & ~(0xf << 6) & 0x1fffffff
            self.playing = False

    def start(self):
        global wdt
        import machine, uctypes, audioring
        if wdt is None:
            wdt = machine.WDT(timeout=8000)
        self.clear(0, self.size)
        gu.play_sample(uctypes.bytearray_at(self.base, self.ENDLESS))
        if self.ch is None:
            for c in range(12):
                if self.base <= machine.mem32[self.DMA + c * 0x40] < self.base + self.size:
                    self.ch = c
                    break
            if self.ch is None:
                gu.stop_playing()
                self.ok = False
                return
        ctrl = self.DMA + self.ch * 0x40 + 0x10
        machine.mem32[ctrl] = (machine.mem32[ctrl] & ~(0x1f << 6) & 0x1fffffff) | (audioring.BITS << 6)
        self.count = self.DMA + self.ch * 0x40 + 8
        self.cleared = 0        # bytes played and since zeroed (counted from the start)
        self.w = self.LEAD      # where the next sound goes (bytes from the start)
        self.got = 0            # bytes received: w and got must stay both even or both odd, or every sample
                                # would be read from the wrong half (loud static)
        self.underruns = self.drops = self.gap = self.maxgap = 0
        self.gapat = ""
        self.lowest = 99999
        self.playing = True

    def clear(self, frm, to):
        """Zero the ring from byte frm up to byte to (counted from the start, so they wrap)."""
        while frm < to:
            i = frm % self.size
            n = min(to - frm, self.size - i, len(self.zeros))
            self.ring[i:i + n] = self.zeros[:n]
            frm += n

    def pump(self, _=None):
        if not self.playing or self.pumping or not self.conn:
            return
        self.pumping = True
        mem32[PUMPS] = (mem32[PUMPS] + 1) & 0xffffff
        mem32[PUMP_AT] = 20
        try:
            import machine
            played = (self.ENDLESS // 2 - machine.mem32[self.count]) * 2
            if played - self.cleared > self.size:
                self.cleared = played - self.size
            self.clear(self.cleared, played)
            self.cleared = played
            mem32[PUMP_AT] = 21
            now = time.ticks_ms()
            if self.gap and time.ticks_diff(now, self.gap) > self.maxgap:
                self.maxgap = time.ticks_diff(now, self.gap)
                self.gapat = where[0]
            self.gap = now
            self.lowest = min(self.lowest, self.w - played)
            if self.w < played:                     # Wi-Fi fell behind: it played silence, start a fresh lead
                self.w = played + self.LEAD
                self.underruns += 1
            for _ in range(4):
                mem32[PUMP_AT] = 22
                try:
                    n = self.conn.readinto(self.rx)
                except OSError:
                    break
                mem32[PUMP_AT] = 23
                if n is None:
                    break
                if n == 0:                          # the Pi hung up: the sound has stopped
                    self.heard = -1
                    break
                self.heard = time.ticks_ms()
                if self.w + n - played > self.size - self.SLACK:
                    self.drops += 1
                    self.got += n
                    continue                        # too far ahead (the Pi's clock runs a hair fast): skip this bit
                if (self.w - self.got) & 1:
                    self.w += 1                     # keep the bytes of each sample together
                i, k = self.w % self.size, 0
                while k < n:
                    m = min(n - k, self.size - i)
                    self.ring[i:i + m] = self.rx[k:k + m]
                    k += m
                    i = 0
                self.w += n
                self.got += n
        finally:
            self.pumping = False
            mem32[PUMP_AT] = 24

    def poll(self):
        if not self.ok or not net.ip():
            return
        if self.server is None:
            import socket
            try:
                s = socket.socket()
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", self.PORT))
                s.listen(1)
                s.setblocking(False)
                self.server = s
            except OSError:
                return
        try:
            c, _ = self.server.accept()             # a new stream replaces the old one
            self.close()
            c.setblocking(False)
            try:
                c.send(("VOL %d\n" % int(VOLUME * 100)).encode())     # the Pi scales the sound to our volume
            except OSError:
                pass
            self.conn, self.heard = c, time.ticks_ms()
        except OSError:
            pass
        if not self.conn:
            return
        if speaker.busy():                          # a chime is playing: let it finish, skip the stream meanwhile
            self.stop()
            try:
                while self.conn.readinto(self.rx):
                    self.heard = time.ticks_ms()
            except OSError:
                pass
        elif not self.playing:
            self.start()
        self.pump()
        if self.heard == -1 or time.ticks_diff(time.ticks_ms(), self.heard) > 5000:
            self.close()                            # hung up, or nothing for 5 s: the Pi must have gone away


stream = Stream()


# ---------------------------------------------------------------- commands from the Pi (USB or Wi-Fi)

_buf = ""
_poll = None
skip = [False]  # "N": on to the next scene, like the A button
perf = {}       # how long each scene took to draw a frame last time it played (average, slowest ms): "P" reports them


def handle_line(line, usb=False):
    """Run one command; returns a short reply (sent back over Wi-Fi, or printed over USB)."""
    global custom_msg, BRIGHTNESS, date_override
    line = line.strip()
    if not line:
        return "OK"
    if line[0] == "T" and line[:5] != "TIMER":
        try:
            y, m, d, h, mi, s, wd = [int(v) for v in line[1:].split()]
            import machine
            machine.RTC().datetime((y, m, d, wd, h, mi, s, 0))
        except Exception:
            pass
    elif line[0] == "M":
        custom_msg = line[1:].strip()
    elif line[0] == "B":
        try:
            BRIGHTNESS = max(0.02, min(1.0, float(line[1:]) / 100))
            with open("brightness.txt", "w") as f:
                f.write(str(BRIGHTNESS))
        except (ValueError, OSError):
            pass
    elif line[0] == "S":
        try:
            speaker.play(line[1:].strip() or "beep")
        except (KeyError, ValueError, IndexError):
            return "ERR unknown tune or note (tunes: %s)" % " ".join(TUNES)
        return "OK playing"
    elif line[0] == "V":
        try:
            set_volume(float(line[1:]) / 100)
        except ValueError:
            return "ERR volume is 0-100"
    elif line[0] == "D":
        try:
            date_override = tuple(int(v) for v in line[1:].split()) or None
            if date_override and len(date_override) != 3:
                raise ValueError
        except ValueError:
            date_override = None
            return "ERR D year month day"
        return "OK pretending it's %s" % (date_override,) if date_override else "OK back to the real date"
    elif line[0] == "X":                                # run a test module pushed from the Pi (for development)
        name = line[1:].strip()
        sys.modules.pop(name, None)
        try:
            return "OK %s" % __import__(name).run(gu)
        except Exception as e:
            return "ERR %r" % e
    elif line == "N":
        skip[0] = True
    elif line[:4] == "CAT " and usb:                  # read one of the settings files (USB only), as base64
        name = line[4:].strip()
        if "/" in name or not (name.endswith(".json") or name.endswith(".txt")):
            return "ERR not that file"
        try:
            import binascii
            with open(name, "rb") as f:
                return "OK " + binascii.b2a_base64(f.read()).decode().strip()
        except OSError:
            return "ERR no file " + name
    elif line[:2] == "G ":
        cls = find_scene(line[2:].strip())
        if not cls:
            return "ERR no scene called %s" % line[2:].strip()
        goto[0] = cls
        return "OK showing " + line[2:].strip()
    elif line[:5] == "TIMER":
        try:
            secs, _, label = (line[5:].strip() + " ").partition(" ")
            secs = int(float(secs))
        except ValueError:
            return "ERR TIMER seconds [name]"
        if secs <= 0:
            timer[0] = None
            return "OK timer cancelled"
        timer[0], timer[1] = time.ticks_add(time.ticks_ms(), secs * 1000), label.strip()
        return "OK timer %d s" % secs
    elif line == "P":
        gc.collect()
        return " ".join("%s:%d/%d" % (k, v[0], v[1]) for k, v in sorted(perf.items())) + " | free %d" % gc.mem_free()
    elif line == "?":
        return "brightness %d volume %d message %r season %s%s%s%s online %s wifi %s" % (
            BRIGHTNESS * 100, VOLUME * 100, custom_msg, _season[0],
            " speaker %s underruns %d%s" % ("playing" if stream.playing else "ready" if stream.ok else "off",
                                            stream.underruns, last_freeze())
            + " drops %d maxgap %d at %s lowest %d" % (stream.drops, stream.maxgap, stream.gapat, stream.lowest),
            " pretend %s" % (date_override,) if date_override else "",
            "".join(" ERROR " + e for e in (season_error, mine_error, scene_error[0]) if e),
            online_status(), net.ip() or "-")
    return "OK"


def last_freeze():
    import audioring
    return " FROZE (restarted): main %d frames %d pumps %d pump %d" % tuple(audioring.crumbs) if audioring.froze else ""


goto = [None]           # "G Name": the scene to show next
scene_error = [""]      # the last scene that failed to start (a broken animation file, say): it's skipped


def online_status():
    m = sys.modules.get("online")
    return m.status() if m else "-"


def _online_needed():
    if SETTINGS.get("place") or "utc_offset" in SETTINGS:
        return True
    try:
        import os
        os.stat("words.txt")
        return True
    except OSError:
        return False                                # a Pi looks after all that: don't spend the memory


ONLINE = _online_needed()


def go_online():
    """Between scenes: let online.py keep the clock and the weather up to date by itself, if it's needed."""
    if not ONLINE or not net.ip():
        return
    try:
        import online
        online.tick(SETTINGS, wdt)
    except Exception as e:
        scene_error[0] = "online: %r" % e


def check_usb():
    global _buf, _poll
    if _poll is None:
        import select
        _poll = select.poll()
        _poll.register(sys.stdin, select.POLLIN)
    if wdt:
        wdt.feed()
    crumb(10)
    while _poll.poll(0):
        ch = sys.stdin.read(1)
        if ch == "\n":
            print("@@", handle_line(_buf, True) or "OK")    # (Unicorn Studio reads the replies)
            _buf = ""
        elif len(_buf) < 200:
            _buf += ch
    crumb(11)
    net.poll(handle_line)
    crumb(12)
    alarms()
    check_timer()
    speaker.tick()
    crumb(13)
    stream.poll()
    crumb(14)


# ---------------------------------------------------------------- main loop

def asleep():
    """In the screen's sleep hours (settings.json "sleep": ["23:00", "07:00"])?"""
    hours = SETTINGS.get("sleep")
    if not hours or not clock_synced():
        return False
    lt = time.localtime()
    now = "%02d:%02d" % (lt[3], lt[4])
    a, b = hours
    return a <= now < b if a <= b else (now >= a or now < b)


def level():
    """Daytime brightness, ramping up to EVENING_BRIGHTNESS through the evening and holding until morning."""
    if not clock_synced():
        return BRIGHTNESS
    lt = time.localtime()
    hour = lt[3] + lt[4] / 60
    if MORNING <= hour < RAMP_START:
        return BRIGHTNESS
    top = max(BRIGHTNESS, EVENING_BRIGHTNESS)
    if RAMP_START <= hour < RAMP_END:
        return BRIGHTNESS + (top - BRIGHTNESS) * (hour - RAMP_START) / (RAMP_END - RAMP_START)
    return top


def run():
    global BRIGHTNESS
    idx = 0
    hold = False
    screen_on = True
    jump = None
    prev = {}

    def pressed(btn):
        now = gu.is_pressed(btn)
        was = prev.get(btn, False)
        prev[btn] = now
        return now and not was

    playlist, built_for = [], None
    while True:
        go_online()
        w = weather()
        key = (today(), w["t"] if w else None)
        if key != built_for:                        # a new day, new weather, or a "D" date to try: a fresh round
            built_for = key
            playlist, idx = build_playlist(), 0
            stream.pump()
        if alert[0]:
            cls = Alert
        elif timer[0] is not None:
            cls = Timer
        elif goto[0]:
            cls, goto[0] = goto[0], None
        elif jump is not None:
            cls, jump = jump, None
        else:
            cls = playlist[idx % len(playlist)]
            idx += 1
            if hasattr(cls, "available") and not cls.available():
                continue
        stream.pump()                               # (the speaker's buffer only lasts 186 ms: top it up often)
        gc.collect()
        stream.pump()
        where[0] = cls.__name__ + " start"
        try:
            scene = cls()
        except Exception as e:                      # a broken scene of your own: skip it, say so in "?"
            scene_error[0] = "%s: %r" % (name_of(cls), e)
            if cls in playlist:
                playlist = [c for c in playlist if c is not cls] or [Clock]
            continue
        where[0] = cls.__name__
        stream.pump()
        start = last = time.ticks_ms()
        worst = total = frames = 0
        while True:
            now = time.ticks_ms()
            t = time.ticks_diff(now, start) / 1000
            dt = min(0.1, time.ticks_diff(now, last) / 1000)
            last = now
            check_usb()

            if pressed(GalacticUnicorn.SWITCH_A) or skip[0]:
                hold = skip[0] = False
                if cls is Timer:
                    timer[0] = None                 # A on the timer cancels it
                break
            if (alert[0] and cls is not Alert) or (timer[0] is not None and cls not in (Timer, Alert)) or goto[0]:
                break
            if pressed(GalacticUnicorn.SWITCH_B):
                b = getattr(mine(), "BUTTON_B", None) or Forecast    # (my_scenes.py can choose its own)
                if not hasattr(b, "available") or b.available():
                    jump = b
                break
            if pressed(GalacticUnicorn.SWITCH_C) and clock_synced():
                jump = Clock
                break
            if pressed(GalacticUnicorn.SWITCH_D):
                hold = not hold
            if pressed(GalacticUnicorn.SWITCH_SLEEP):
                screen_on = not screen_on
            if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_UP):
                BRIGHTNESS = min(1.0, BRIGHTNESS + 0.01)
            if gu.is_pressed(GalacticUnicorn.SWITCH_BRIGHTNESS_DOWN):
                BRIGHTNESS = max(0.05, BRIGHTNESS - 0.01)
            if pressed(GalacticUnicorn.SWITCH_VOLUME_UP):
                set_volume(VOLUME + 0.1)
                speaker.play("beep")
            if pressed(GalacticUnicorn.SWITCH_VOLUME_DOWN):
                set_volume(VOLUME - 0.1)
                speaker.play("beep")

            if hold and t >= scene.dur:
                start = now                         # loop the same scene
                t = 0
            if t >= scene.dur:
                break

            gfx.set_pen(BLACK)
            gfx.clear()
            drawn = time.ticks_ms()
            crumb(2)
            scene.draw(t, dt)
            crumb(3)
            took = time.ticks_diff(time.ticks_ms(), drawn)
            worst, total, frames = max(worst, took), total + took, frames + 1

            b = level()
            fade = 1 if hold else max(0, min(1, t / FADE, (scene.dur - t) / FADE))
            dark = not screen_on or (asleep() and cls not in (Alert, Timer))     # sleep hours: screen off
            gu.set_brightness(0 if dark else b * fade)
            crumb(4)
            gu.update(gfx)
            crumb(5)
            mem32[FRAMES] = (mem32[FRAMES] + 1) & 0xffffff
            time.sleep_ms(max(0, 33 - time.ticks_diff(time.ticks_ms(), now)))
            crumb(6)
        if frames:
            perf[cls.__name__] = (total // frames, worst)


def _roomy():
    """MicroPython only makes a dict bigger once it's completely full, and every look-up of a built-in (min, max, int,
    range...) first searches the module's globals all the way to an empty slot: in a nearly full table, that's most
    of it. So pad the globals just past a size step (MicroPython's sizes, py/map.c), leaving a quarter of the table
    free. It made the campfire draw 40% faster."""
    g = globals()
    for size in (17, 23, 29, 37, 47, 59, 73, 97, 127, 167, 223, 293, 389, 521, 691, 919):
        if size >= len(g):
            i = 0
            while len(g) > size * 0.8 and len(g) <= size:
                g["_pad%d" % i] = None
                i += 1
            return


_roomy()


if __name__ == "__main__":
    net.start()
    run()
