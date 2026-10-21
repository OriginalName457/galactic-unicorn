"""Tiny Galactic Unicorn simulator: renders scenes from main.py to a PNG strip (text drawn as width-accurate blocks)."""
import sys, types, time, random
from PIL import Image, ImageDraw
W6 = [4, 2, 4, 6, 6, 6, 7, 2, 3, 3, 4, 4, 2, 4, 2, 4, 6, 3, 5, 5, 6, 5, 6, 6, 6, 6, 2, 2, 4, 4, 4, 5, 7, 6, 6, 5, 6, 5, 5, 6, 5, 4, 5, 5, 5, 6, 6, 6, 6, 6, 6, 5, 6, 6, 6, 6, 5, 5, 5, 3, 4, 3, 4, 4, 3, 6, 6, 5, 6, 5, 5, 6, 5, 4, 5, 5, 5, 6, 6, 6, 6, 6, 6, 5, 6, 6, 6, 6, 5, 5, 5, 4, 2, 4, 4]
W8 = [4, 2, 4, 6, 5, 5, 5, 2, 4, 4, 4, 4, 3, 4, 3, 5, 5, 4, 5, 5, 5, 5, 5, 5, 5, 5, 2, 3, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 5, 5, 5, 6, 5, 5, 5, 5, 5, 5, 6, 5, 5, 6, 5, 5, 5, 3, 5, 3, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 5, 5, 4, 6, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 5, 5, 5, 4, 2, 4, 5]
W, H = 53, 11
class G:
    def __init__(self, display=None):
        self.buf = [[(0, 0, 0)] * W for _ in range(H)]; self.p = (0, 0, 0); self.font = "bitmap8"; self.clip = (0, 0, W, H)
    def create_pen(self, r, g, b): return (r, g, b)
    def set_pen(self, p): self.p = p
    def pixel(self, x, y):
        x, y = int(x), int(y); cx, cy, cw, ch = self.clip
        if cx <= x < cx + cw and cy <= y < cy + ch and 0 <= x < W and 0 <= y < H: self.buf[y][x] = self.p
    def clear(self): self.rectangle(0, 0, W, H)
    def rectangle(self, x, y, w, h):
        for j in range(int(y), int(y + h)):
            for i in range(int(x), int(x + w)): self.pixel(i, j)
    def circle(self, cx, cy, r):
        for j in range(-r, r + 1):
            for i in range(-r, r + 1):
                if i * i + j * j <= r * r + r * 0.8: self.pixel(cx + i, cy + j)
    def triangle(self, x1, y1, x2, y2, x3, y3):
        def s(ax, ay, bx, by, px, py): return (px - bx) * (ay - by) - (ax - bx) * (py - by)
        for j in range(min(y1, y2, y3), max(y1, y2, y3) + 1):
            for i in range(min(x1, x2, x3), max(x1, x2, x3) + 1):
                d1, d2, d3 = s(i, j, x1, y1, x2, y2), s(i, j, x2, y2, x3, y3), s(i, j, x3, y3, x1, y1)
                if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)): self.pixel(i, j)
    def line(self, x1, y1, x2, y2, *a):
        n = max(abs(x2 - x1), abs(y2 - y1), 1)
        for k in range(n + 1): self.pixel(round(x1 + (x2 - x1) * k / n), round(y1 + (y2 - y1) * k / n))
    def set_font(self, f): self.font = f
    def measure_text(self, s, scale=1):
        t = W6 if self.font == "bitmap6" else W8
        return sum(t[ord(c) - 32] if 32 <= ord(c) < 127 else 5 for c in s)
    def text(self, s, x, y, wrap=-1, scale=1):
        t = W6 if self.font == "bitmap6" else W8; hgt = 6 if self.font == "bitmap6" else 7
        for c in s:
            w = t[ord(c) - 32] if 32 <= ord(c) < 127 else 5
            if c != " ":
                for j in range(hgt):
                    for i in range(w - 1):
                        if (i + j + ord(c)) % 3: self.pixel(x + i, y + j)
            x += w
    def set_clip(self, x, y, w, h): self.clip = (x, y, w, h)
    def remove_clip(self): self.clip = (0, 0, W, H)
class GU:
    WIDTH, HEIGHT = W, H
    SWITCH_A = SWITCH_B = SWITCH_C = SWITCH_D = SWITCH_SLEEP = SWITCH_BRIGHTNESS_UP = SWITCH_BRIDGHTNESS_DOWN = 0
    def __init__(self): pass
sys.modules["galactic"] = types.SimpleNamespace(GalacticUnicorn=GU)
sys.modules["picographics"] = types.SimpleNamespace(PicoGraphics=G, DISPLAY_GALACTIC_UNICORN=0)
sys.modules["machine"] = types.SimpleNamespace(RTC=lambda: None)
sys.modules["net"] = types.SimpleNamespace(start=lambda: None, poll=lambda f: None)
src = open(sys.argv[1]).read().replace('if __name__ == "__main__":\n    run()', '')
ns = {"__name__": "sim"}; exec(compile(src, "main.py", "exec"), ns)
gfx = ns["gfx"]
sys.modules["carousel"] = types.SimpleNamespace(**ns)       # so winter.py etc. can `from carousel import ...`
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(sys.argv[1])))
S = 8
def render(scene_name, times, out, fake_date=None):
    if fake_date: ns["date_override"] = tuple(fake_date[:3])
    random.seed(1)
    if "." in scene_name:
        mod, cls = scene_name.split(".")
        scene = getattr(__import__(mod), cls)()
    else:
        scene = ns[scene_name]()
    dt = 1 / 30
    frames, t = [], 0.0
    for target in times:
        while t < target:
            t += dt
            gfx.p = (0, 0, 0); gfx.clear(); scene.draw(t, dt)
        frames.append([row[:] for row in gfx.buf])
    img = Image.new("RGB", (W * S, (H * S + 6) * len(frames)), (25, 25, 25)); d = ImageDraw.Draw(img)
    for k, fr in enumerate(frames):
        for y in range(H):
            for x in range(W):
                r, g, b = fr[y][x]; oy = k * (H * S + 6)
                d.rectangle((x * S + 1, oy + y * S + 1, x * S + S - 1, oy + y * S + S - 1), fill=(int(r), int(g), int(b)))
    img.save(out); print(out, getattr(scene, "dur", None))
if __name__ == "__main__":
    import ast
    render(sys.argv[2], [float(v) for v in sys.argv[3].split(",")], sys.argv[4], ast.literal_eval(sys.argv[5]) if len(sys.argv) > 5 else None)
