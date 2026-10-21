# Galactic Unicorn start-up (copied to the board as main.py).
# Wi-Fi comes up first, then the carousel (carousel.py) starts. If the carousel ever crashes, the Unicorn
# goes into safe mode instead: a slow red dot in the corner, still listening on Wi-Fi so it can be fixed
# from the Pi without a data cable.
import sys
import time

import net

net.start()
try:
    import carousel
    carousel.run()
except Exception as e:
    sys.print_exception(e)
    problem = repr(e)
    try:
        with open("crash.txt", "w") as f:
            f.write(problem)
    except OSError:
        pass
    gu = gfx = None
    try:
        from galactic import GalacticUnicorn
        from picographics import PicoGraphics, DISPLAY_GALACTIC_UNICORN
        gu = sys.modules["carousel"].gu if "carousel" in sys.modules and hasattr(sys.modules["carousel"], "gu") \
            else GalacticUnicorn()
        gfx = PicoGraphics(display=DISPLAY_GALACTIC_UNICORN)
        gu.set_brightness(0.3)
    except Exception:
        pass
    while True:
        net.poll(lambda line: "SAFE MODE " + problem)
        if gfx:
            on = (time.ticks_ms() // 1000) % 2
            gfx.set_pen(gfx.create_pen(0, 0, 0))
            gfx.clear()
            gfx.set_pen(gfx.create_pen(180 * on, 0, 0))
            gfx.pixel(0, 0)
            gu.update(gfx)
        time.sleep_ms(50)
