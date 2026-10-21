# Your own scenes, in Python. Copy this file to my_scenes.py, change it, and put it on the Unicorn with the
# others (Unicorn Studio does that for you: it's in "Wi-Fi & settings", "Add my_scenes.py"; or `unicorn.py push`).
# The carousel loads it when it starts. If it has a mistake, the carousel carries on without it and says why in
# its status (`unicorn.py status`).
#
# A scene is a class with `dur` (seconds on screen) and `draw(self, t, dt)`, which paints one frame: t is the
# seconds since the scene started, dt the seconds since the last frame. Everything in carousel.py is yours to use:
# gfx (PicoGraphics), W and H (53 x 11), pen(r, g, b), px(x, y, pen), text(s, x, y, pen), sprite(rows, x, y,
# {letter: pen}), wave(t, speed), Stars, and the date helpers during(), around() and today().
import random

from carousel import gfx, W, H, pen, px, text, text_width, wave, during


class Hello:
    """Hello in rainbow letters, over twinkling stars."""
    dur = 10

    def __init__(self):
        self.stars = [(random.randrange(W), random.randrange(H), random.uniform(0, 6)) for _ in range(12)]
        self.msg = "Hello!"

    def draw(self, t, dt):
        for x, y, ph in self.stars:
            v = wave(t, 2, 0, 120, ph)
            px(x, y, pen(v, v, v))
        x = (W - text_width(self.msg)) // 2
        for i, ch in enumerate(self.msg):
            k = wave(t, 3, phase=i)
            text(ch, x, 2, pen(255 * k, 120 + 120 * (1 - k), 255 - 200 * k))
            x += text_width(ch)


SCENES = [              # (scene, when it shows, turns per round): like the ones in carousel.py
    (Hello, during(1, 1, 12, 31), 1),
]
ALWAYS = []             # scenes for between the seasonal ones, all year (like the clock)
# BUTTON_B = Hello      # what the B button shows (the weather, if you leave this out)
