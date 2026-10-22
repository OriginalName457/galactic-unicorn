#!/usr/bin/env python3
"""Makes Unicorn Studio's library: studio/catalog.json (every scene, when it shows, what it is; the tunes; the
countdown pictures) and an animated preview of each scene in studio/previews/, drawn with the simulator. Also the
gallery to look through on GitHub: docs/SCENES.md, with a bigger, smoother animation of each scene in docs/scenes/.

  python3 tools/make_catalog.py          (needs Pillow: pip install pillow)

Run it again after adding or changing scenes.
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "studio")
sys.path.insert(0, ROOT)
import sim  # noqa: E402
from PIL import Image  # noqa: E402

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SEASONS = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring", 6: "Summer", 7: "Summer",
           8: "Summer", 9: "Fall", 10: "Fall", 11: "Fall"}
EVERYDAY = {   # the ones between the seasonal scenes all year: (title, what it is)
    "Clock": ("Clock", "The time with a little seasonal picture, then the date."),
    "Forecast": ("Forecast", "Today's weather: the temperature, the high and low, and what's coming."),
    "Countdown": ("Holiday countdowns", "Days until the big holidays (and your own dates), greetings on the day."),
    "Note": ("Your messages", "The messages you add in Unicorn Studio, scrolling by."),
    "Kotoba": ("Japanese words", "A Japanese flashcard: 10 new words a day, the word then its meaning."),
    "Outside": ("Outside", "The sky right now: sun or moon, clouds, rain, snow, lightning."),
    "Moon": ("Moon", "Tonight's moon in its phase (on clear nights)."),
    "Reminder": ("Gift reminders", "\"Did you get a gift?\" before Mother's Day and Father's Day."),
}
WEATHER = {"t": "", "place": "Springfield", "temp": 64, "kind": "partly", "day": 1, "cloud": 40, "wet": 0, "wind": 6,
           "rise": 420, "set": 1140, "storm_soon": False, "pages": ["64°", "some clouds", "H70 L52", "rain at 4pm"]}


TITLES = {"Leaves": "Falling leaves", "Latte": "Pumpkin spice latte", "Pumpkins": "Jack-o'-lanterns",
          "Torii": "Fushimi Inari gates", "Kinkaku": "Golden Pavilion", "Fuji": "Mt Fuji", "Flag": "Stars and stripes",
          "Cabin": "Snowy cabin", "Cocoa": "Hot cocoa", "XmasTree": "Christmas tree", "Sleigh": "Santa's sleigh",
          "Candy": "Valentine's hearts", "Groundhog": "Groundhog Day", "Aurora": "Northern lights", "Skater": "Ice skater",
          "Dream": "MLK Day", "Rainbow": "St. Patrick's rainbow", "Showers": "April showers", "Garden": "Spring garden",
          "Bunny": "Easter bunny", "PiDay": "Pi Day", "Sakura": "Cherry blossoms", "Fools": "April Fools'",
          "Earth": "Earth Day", "Picado": "Cinco de Mayo", "Bouquet": "Mother's Day bouquet", "IceCream": "Ice cream",
          "Meteors": "Shooting stars", "Grill": "Backyard grill", "Storm": "Summer storm", "Orchard": "Apple orchard",
          "Pie": "Pumpkin pie", "Bus": "Back to school", "Turkey": "Thanksgiving turkey"}


def first_sentence(doc):
    doc = " ".join((doc or "").split()).replace("St. ", "St.\u00a0")
    return (doc.split(". ")[0].rstrip(".") + ".").replace("\u00a0", " ") if doc else ""


def windows(entries, year=2027):
    """The stretches of the year each scene shows, as text like "Oct 1 - Nov 30", and the first day of one."""
    days = [datetime.date(year, 1, 1) + datetime.timedelta(i) for i in range(365)]
    on = [any(when(d.year, d.month, d.day) for when in entries) for d in days]
    spans, i = [], 0
    while i < 365:
        if on[i]:
            j = i
            while j + 1 < 365 and on[j + 1]:
                j += 1
            spans.append([days[i], days[j]])
            i = j + 1
        else:
            i += 1
    if len(spans) > 1 and spans[0][0] == days[0] and spans[-1][1] == days[-1]:     # wraps past New Year
        spans[0][0] = spans.pop()[0]
    text = ", ".join(("%s %d" % (MONTHS[a.month - 1], a.day)) if a == b else
                     "%s %d - %s %d" % (MONTHS[a.month - 1], a.day, MONTHS[b.month - 1], b.day) for a, b in spans)
    length = sum(((b - a).days % 365) + 1 for a, b in spans)
    return text, spans, length


def gif(ns, name, dur, when, path):
    """An animated preview: 16 frames through the scene (skipping the fades)."""
    n = 16
    span = min(max(dur - 2, 1), 16)
    times = [1 + span * k / n for k in range(n)]
    shots, _ = sim.frames(ns, name, times, when)
    pics = [sim.picture(fr, size=4, gap=0).convert("P", palette=1, colors=255) for fr in shots]
    pics[0].save(path, save_all=True, append_images=pics[1:], duration=int(span / n * 1000), loop=0)


def big_gif(ns, name, dur, when, path, start=1, n=36, fps=6, size=8):
    """The gallery's animation: round LEDs, a few seconds of the scene at 6 frames a second."""
    step = min(1 / fps, max(dur - 2, 1) / n)
    times = [start + step * k for k in range(n)]
    shots, _ = sim.frames(ns, name, times, when)
    pics = [sim.picture(fr, size=size, gap=size // 8, dots=True) for fr in shots]
    # one palette for every frame, so each frame only stores the LEDs that changed
    sheet = Image.new("RGB", (pics[0].width, pics[0].height * n))
    for k, p in enumerate(pics):
        sheet.paste(p, (0, k * p.height))
    pal = sheet.quantize(255, method=0)                 # median cut; index 255 stays free for "unchanged"
    idx = [p.quantize(palette=pal, dither=0) for p in pics]
    out, prev = [idx[0]], idx[0].tobytes()
    for im in idx[1:]:
        now = im.tobytes()
        keep = Image.frombytes("P", im.size, bytes(255 if a == b else a for a, b in zip(now, prev)))
        keep.putpalette(im.getpalette())
        out.append(keep)
        prev = now
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(step * 1000), loop=0, transparency=255,
                disposal=1, optimize=False)                  # optimize would renumber the colours


def gallery(scenes, order):
    """docs/SCENES.md: every scene by category, with its animation, when it shows and what it is."""
    lines = ["# The scenes", "",
             "Everything the Unicorn can show, drawn by the simulator. Each scene comes round only in its own part "
             "of the year; untick any you don't want in Unicorn Studio's **Scenes** tab.", "",
             " · ".join("[%s](#%s)" % (c, c.lower().replace(" & ", "--").replace(" ", "-")) for c in order), ""]
    for cat in order:
        lines += ["## " + cat, ""]
        for s in (s for s in scenes if s["category"] == cat):
            lines += ["### " + s["title"], "", "![%s](scenes/%s.gif)" % (s["title"], s["name"]), "",
                      "**%s.** %s" % (s["when"], s["about"]), ""]
    with open(os.path.join(ROOT, "docs", "SCENES.md"), "w") as f:
        f.write("\n".join(lines))


def main():
    work = tempfile.mkdtemp()
    os.chdir(work)                          # the scenes read weather.json and kotoba.json from where they run
    ns = sim.load(os.path.join(ROOT, "carousel.py"))
    ns["custom_msg"] = "Hello from your Unicorn!"
    with open("kotoba.json", "w") as f:
        json.dump({"words": [{"w": "sakura", "m": "cherry blossom"}]}, f)

    groups = {}             # class -> [module name, [when, ...]]
    for cls, when, n in ns["SCENES"]:
        groups.setdefault(cls, ["", []])[1].append(when)
    for mod_name in ("winter", "spring", "summer", "fall"):
        mod = __import__(mod_name)
        for cls, when, n in mod.SCENES:
            groups.setdefault(cls, [mod_name, []])[1].append(when)

    previews = os.path.join(OUT, "previews")
    shutil.rmtree(previews, ignore_errors=True)
    os.makedirs(previews)
    big = os.path.join(ROOT, "docs", "scenes")
    shutil.rmtree(big, ignore_errors=True)
    os.makedirs(big)
    scenes = []
    for cls, (mod_name, entries) in groups.items():
        text, spans, length = windows(entries)
        a, b = spans[0]
        mid = a + datetime.timedelta(((b - a).days % 365) // 2)
        category = "Holidays" if length <= 21 or any(
            getattr(w, "__name__", "") == "when" for w in entries) else SEASONS[mid.month]
        day = (2026 if a.month >= 6 else 2027, a.month, a.day)
        scenes.append({"name": cls.__name__, "title": TITLES.get(cls.__name__, cls.__name__), "category": category, "when": text,
                       "about": first_sentence(cls.__doc__), "file": mod_name or "carousel", "start": day[1:]})
        WEATHER["t"] = "%d-%02d-%02dT19:00" % day
        with open("weather.json", "w") as f:
            json.dump(WEATHER, f)
        ref = (mod_name + "." if mod_name else "") + cls.__name__
        ns["time"].localtime = lambda *a, d=day: (d[0], d[1], d[2], 19, 0, 0, 0, 1)
        ns["date_override"] = day
        sc = (getattr(__import__(mod_name), cls.__name__) if mod_name else cls)()
        gif(ns, ref, sc.dur, day, os.path.join(previews, cls.__name__ + ".gif"))
        big_gif(ns, ref, sc.dur, day, os.path.join(big, cls.__name__ + ".gif"))
        print("%-12s %-9s %s" % (cls.__name__, category, text))
    for name, (title, about) in EVERYDAY.items():
        day = (2026, 10, 24) if name != "Reminder" else (2027, 4, 29)
        WEATHER["t"] = "%d-%02d-%02dT19:00" % day
        with open("weather.json", "w") as f:
            json.dump(WEATHER, f)
        ns["time"].localtime = lambda *a, d=day: (d[0], d[1], d[2], 19, 0, 0, 5, 1)
        cat = "Weather & sky" if name in ("Outside", "Moon", "Forecast") else "Everyday"
        when = "Late April - mid June" if name == "Reminder" else "All year"
        scenes.append({"name": name, "title": title, "category": cat, "when": when, "about": about,
                       "file": "carousel"})
        ns["date_override"] = day
        gif(ns, name, ns[name]().dur, day, os.path.join(previews, name + ".gif"))
        big_gif(ns, name, ns[name]().dur, day, os.path.join(big, name + ".gif"))
        print("%-12s %-9s" % (name, cat))

    order = ["Everyday", "Weather & sky", "Fall", "Winter", "Spring", "Summer", "Holidays"]
    scenes.sort(key=lambda s: (order.index(s["category"]), s.get("start", (0, 0)), s["title"]))
    catalog = {"categories": order, "scenes": scenes, "tunes": ns["TUNES"], "icons": sorted(ns["ICONS"])}
    with open(os.path.join(OUT, "catalog.json"), "w") as f:
        json.dump(catalog, f, indent=1)
    gallery(scenes, order)
    # the README's picture: Mt Fuji at sunset as the shinkansen goes by, bigger and smoother
    big_gif(ns, "Fuji", ns["Fuji"]().dur, (2026, 10, 15), os.path.join(ROOT, "docs", "fuji.gif"), start=1.2, n=60,
            fps=20, size=12)
    shutil.rmtree(work, ignore_errors=True)
    print("%d scenes -> studio/catalog.json, studio/previews/, docs/SCENES.md" % len(scenes))


if __name__ == "__main__":
    main()
