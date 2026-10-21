"""A tiny Galactic Unicorn simulator: runs the carousel's scenes on a computer (no board needed) and saves frames as a
PNG strip. Unicorn Studio's previews are made with it too (tools/make_catalog.py).

  python3 sim.py carousel.py Campfire 1,4,7 out.png                     # frames at 1 s, 4 s and 7 s
  python3 sim.py carousel.py winter.Cabin 1,4,7 out.png "(2026,12,20,19,0,0)"   # a season's scene, on a given day
"""
import os
import random
import sys
import time
import types

W, H = 53, 11

# Pimoroni's bitmap fonts (from pimoroni-pico, MIT licence, (c) 2021 Pimoroni Ltd): widths and column bits
# for the 96 printable ASCII characters plus their extras (the last is the degree sign).
FONTS = {
    "bitmap6": (6, 6, "313555612233131352445455551133346554544543444555555455554442323325545445434445555554555544431331554554443",
               "0000000000002e0000000000060006000000143e143e1400042a3e2a1000221008042200142a2a2c10280600000000001c2200000000221c00000000140814000000081c08000000600000000000080808000000200000000000300c020000001c2222221e00023e00000000322a2a2400002a2a2a1600000e10103e10002e2a2a1200003c2a2a2a1200060222120e00142a2a2a1600042a2a2a1e00240000000000640000000000081422000000141414000000221408000000022a0a0400003c021a2a221e3c1212123e003c2a2a2e10001c22222200003c2222221c003c2a2a2a00003c12121200003c22222a1a003e08083e0000223e220000003022221e00003e080c3200003e20202000003c023c023c003c0202023e001c2222221e003c1212120e001c2222621e003c1212320e00242a2a12000002023e0202001e2020201e000e1020100e003e201e201e003608083600002628281e0000322a2a2600003e2200000000020c30000000223e000000000402040000002020200000000204000000003c1212123e003c2a2a2e10001c22222200003c2222221c003c2a2a2a00003c12121200003c22222a1a003e08083e0000223e220000003022221e00003e080c3200003e20202000003c023c023e003c0202023e001c2222221e003c1212120e001c2222621e003c1212320e00242a2a12000002023e0202001e2020201e000e1020100e003e201e201e003608083600002628281e0000322a2a260000083e220000003e0000000000223e080000000402020000000000000000003c123c2a2a003f1212120e003e0a2a3400003c123c2a2a003f1212120e00083c2a2a00002628281e00001c2222220000020502000000"),
    "bitmap8": (8, 5, "313544413333232443444444441233344444444443444544444454454442423344444444434435444444444544431341544544443",
               "00000000005f000000000300030000287c287c28247a2f120066100866003649497c0003000000001c2241000041221c00005438540000103810000080600000001010100000606000000060180601003e41413e00427f400000625149460021494d33001816117f004f494931003c4a493000016119070036494936000649291e003300000000806c00000010284400002828280000442810000002510906003e49555e007e09097e007f494936003e414122007f41413e007f494941007f090901003e414979007f08087f00417f4100003040403f007f081463007f404040007f0204027f7f02047f003e41413e007f090906003e41215e007f09196600464949310001017f01013f40403f007f40201f003f4020403f77080877004748483f0071494543007f410000000106186000417f00000004020400004040400000010100000020545478007f4444380038444428003844447f0038545458007e0909020018a4a47c007f04047800047d4000006080807d007f10284400017f4000007c047804787c040478003844443800fc24241800182424fc007c0804040048545424003e444420003c40407c007c40201c003c4020403c6c10106c001ca0a07c0064544c0000083e4100007f00000000413e080000080408040000000000007e097f49497e242418007e0949360020547854587f24241800087e4941004748483f0038444428000205020000"),
}


def _glyph(font, ch):
    """(width, column bits) of a character in one of the fonts above."""
    height, max_w, widths, data = FONTS[font]
    i = 104 if ch == "\u00b0" else ord(ch) - 32
    if not 0 <= i < 105:
        i = ord("?") - 32
    return int(widths[i], 16), bytes.fromhex(data[i * max_w * 2:(i + 1) * max_w * 2])


class G:
    """Stands in for PicoGraphics: draws into a 53x11 list of (r, g, b) rows."""

    def __init__(self, display=None):
        self.buf = [[(0, 0, 0)] * W for _ in range(H)]
        self.p = (0, 0, 0)
        self.font = "bitmap8"
        self.clip = (0, 0, W, H)

    def create_pen(self, r, g, b):
        return (r, g, b)

    def set_pen(self, p):
        self.p = p

    def pixel(self, x, y):
        x, y = int(x), int(y)
        cx, cy, cw, ch = self.clip
        if cx <= x < cx + cw and cy <= y < cy + ch and 0 <= x < W and 0 <= y < H:
            self.buf[y][x] = self.p

    def clear(self):
        self.rectangle(0, 0, W, H)

    def rectangle(self, x, y, w, h):
        for j in range(int(y), int(y + h)):
            for i in range(int(x), int(x + w)):
                self.pixel(i, j)

    def circle(self, cx, cy, r):
        for j in range(-r, r + 1):
            for i in range(-r, r + 1):
                if i * i + j * j <= r * r + r * 0.8:
                    self.pixel(cx + i, cy + j)

    def triangle(self, x1, y1, x2, y2, x3, y3):
        def side(ax, ay, bx, by, px, py):
            return (px - bx) * (ay - by) - (ax - bx) * (py - by)
        for j in range(min(y1, y2, y3), max(y1, y2, y3) + 1):
            for i in range(min(x1, x2, x3), max(x1, x2, x3) + 1):
                d1, d2, d3 = side(i, j, x1, y1, x2, y2), side(i, j, x2, y2, x3, y3), side(i, j, x3, y3, x1, y1)
                if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
                    self.pixel(i, j)

    def line(self, x1, y1, x2, y2, *a):
        n = max(abs(x2 - x1), abs(y2 - y1), 1)
        for k in range(n + 1):
            self.pixel(round(x1 + (x2 - x1) * k / n), round(y1 + (y2 - y1) * k / n))

    def set_font(self, f):
        self.font = f

    def measure_text(self, s, scale=1):
        return sum(_glyph(self.font, c)[0] + 1 for c in s)

    def text(self, s, x, y, wrap=-1, scale=1):
        x, y = int(x), int(y)
        for c in s:
            w, cols = _glyph(self.font, c)
            for i in range(w):
                for j in range(8):
                    if cols[i] >> j & 1:
                        self.pixel(x + i, y + j)
            x += w + 1

    def set_clip(self, x, y, w, h):
        self.clip = (x, y, w, h)

    def remove_clip(self):
        self.clip = (0, 0, W, H)


class GU:
    WIDTH, HEIGHT = W, H
    SWITCH_A = SWITCH_B = SWITCH_C = SWITCH_D = SWITCH_SLEEP = SWITCH_BRIGHTNESS_UP = SWITCH_BRIGHTNESS_DOWN = 0
    SWITCH_VOLUME_UP = SWITCH_VOLUME_DOWN = 0

    def __init__(self):
        pass


def load(carousel_path):
    """Run carousel.py with stand-ins for the board's libraries; returns its namespace."""
    sys.modules["galactic"] = types.SimpleNamespace(GalacticUnicorn=GU)
    sys.modules["picographics"] = types.SimpleNamespace(PicoGraphics=G, DISPLAY_GALACTIC_UNICORN=0)
    sys.modules["machine"] = types.SimpleNamespace(RTC=lambda: None, mem32={})
    sys.modules["audioring"] = types.SimpleNamespace(raw=None, SIZE=8192, BITS=13, froze=False, crumbs=[0] * 4)
    sys.modules["net"] = types.SimpleNamespace(start=lambda: None, poll=lambda f: None, ip=lambda: "")
    for name, f in (("ticks_ms", lambda: int(time.monotonic() * 1000)), ("ticks_diff", lambda a, b: a - b),
                    ("ticks_add", lambda a, b: a + b), ("sleep_ms", lambda ms: None)):
        if not hasattr(time, name):
            setattr(time, name, f)
    with open(carousel_path) as f:
        src = f.read().replace('if __name__ == "__main__":', "if False:")
    ns = {"__name__": "sim"}
    exec(compile(src, carousel_path, "exec"), ns)
    sys.modules["carousel"] = types.SimpleNamespace(**ns)      # so winter.py etc. can `from carousel import ...`
    here = os.path.dirname(os.path.abspath(carousel_path))
    if here not in sys.path:
        sys.path.insert(0, here)
    return ns


def frames(ns, scene_name, times, fake_date=None):
    """The scene's pixels at each of the times (seconds): [[[(r, g, b)] * W] * H, ...]."""
    gfx = ns["gfx"]
    ns["date_override"] = tuple(fake_date[:3]) if fake_date else None
    random.seed(1)
    if "." in scene_name:
        mod, cls = scene_name.split(".")
        scene = getattr(__import__(mod), cls)()
    else:
        scene = ns[scene_name]()
    dt = 1 / 30
    out, t = [], 0.0
    for target in times:
        while t < target:
            t += dt
            gfx.p = (0, 0, 0)
            gfx.clear()
            scene.draw(t, dt)
        out.append([row[:] for row in gfx.buf])
    return out, scene


def picture(fr, size=8, gap=1):
    """One frame as a picture of the LEDs (a Pillow image)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W * size, H * size), (18, 18, 20))
    d = ImageDraw.Draw(img)
    for y in range(H):
        for x in range(W):
            r, g, b = (int(v) for v in fr[y][x])
            d.rectangle((x * size + gap, y * size + gap, x * size + size - 1 - gap, y * size + size - 1 - gap),
                        fill=(r, g, b) if r or g or b else (32, 32, 36))
    return img


if __name__ == "__main__":
    import ast
    from PIL import Image
    ns = load(sys.argv[1])
    when = ast.literal_eval(sys.argv[5]) if len(sys.argv) > 5 else None
    shots, scene = frames(ns, sys.argv[2], [float(v) for v in sys.argv[3].split(",")], when)
    pics = [picture(fr) for fr in shots]
    strip = Image.new("RGB", (pics[0].width, (pics[0].height + 6) * len(pics)), (25, 25, 25))
    for k, p in enumerate(pics):
        strip.paste(p, (0, k * (p.height + 6)))
    strip.save(sys.argv[4])
    print(sys.argv[4], getattr(scene, "dur", None))
