# The Unicorn on its own, with no Pi around: it keeps its own clock (internet time) and fetches the weather itself
# from Open-Meteo (free, no key) for the town in settings.json ("place": {"name", "lat", "lon", "units"}), and picks
# the day's Japanese words from words.txt. Called by the carousel between scenes; each job only runs when it's due.
# (A Pi running the helpers in this repo does all this too; whichever is newer wins.)
import json
import socket
import struct
import time

import machine

WEATHER_EVERY = 20 * 60         # seconds
CLOCK_EVERY = 6 * 3600
RETRY = 5 * 60

_due = {"weather": 0, "clock": 0, "words": 0}
_last = {"weather": "", "clock": "", "words": ""}
_offset = [None]                # seconds east of UTC (from Open-Meteo, which knows about daylight saving time)


def status():
    return " ".join("%s:%s" % (k, v) for k, v in _last.items() if v) or "-"


_wdt = [None]           # the carousel's watchdog, fed while waiting on a slow network


def _feed(wdt):
    if wdt:
        wdt.feed()


def _uptime():
    return time.ticks_ms() // 1000


def tick(settings, wdt):
    _wdt[0] = wdt
    now = _uptime()
    if _offset[0] is None:
        try:
            with open("utc_offset.txt") as f:
                _offset[0] = int(f.read())
        except (OSError, ValueError):
            if "utc_offset" in settings:        # minutes, from Unicorn Studio (the computer's time zone)
                _offset[0] = int(settings["utc_offset"]) * 60
    place = settings.get("place")
    if place and now >= _due["weather"]:
        _feed(wdt)
        try:
            weather(place)
            _due["weather"] = now + WEATHER_EVERY
        except Exception as e:
            _last["weather"] = "failed(%r)" % e
            _due["weather"] = now + RETRY
        _feed(wdt)
        return                                  # one job per call: the animation shouldn't wait long
    if _offset[0] is not None and now >= _due["clock"]:
        _feed(wdt)
        try:
            set_clock()
            _due["clock"] = now + CLOCK_EVERY
        except Exception as e:
            _last["clock"] = "failed(%r)" % e
            _due["clock"] = now + 60 if time.localtime()[0] < 2025 else now + RETRY
        _feed(wdt)
        return
    if now >= _due["words"] and time.localtime()[0] >= 2025:
        _due["words"] = now + 3600
        try:
            words()
        except Exception as e:
            _last["words"] = "failed(%r)" % e


# ---------------------------------------------------------------- the clock (NTP)

def set_clock():
    addr = socket.getaddrinfo("pool.ntp.org", 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(3)
        q = bytearray(48)
        q[0] = 0x1B
        s.sendto(q, addr)
        reply = s.recv(48)
    finally:
        s.close()
    since_1900 = 3155673600 if time.gmtime(0)[0] == 2000 else 2208988800    # NTP counts from 1900
    secs = struct.unpack("!I", reply[40:44])[0] - since_1900 + _offset[0]
    t = time.gmtime(secs)
    machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
    _last["clock"] = "%02d:%02d" % (t[3], t[4])


# ---------------------------------------------------------------- the weather (Open-Meteo, plain HTTP: no TLS
# needed, which saves a lot of memory). The same summary weather/weather.py makes on a Pi.

def get(host, path):
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    try:
        s.settimeout(5)
        s.connect(addr)
        _feed(_wdt[0])
        s.send(("GET %s HTTP/1.0\r\nHost: %s\r\nConnection: close\r\n\r\n" % (path, host)).encode())
        data = b""
        while True:
            chunk = s.recv(1024)
            _feed(_wdt[0])
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    head, _, body = data.partition(b"\r\n\r\n")
    if b" 200 " not in head.split(b"\r\n")[0]:
        raise OSError(head.split(b"\r\n")[0].decode())
    return json.loads(body)


def kind(code):
    if code in (0, 1):
        return "clear"
    if code == 2:
        return "partly"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    return "cloudy"


WORDS = {"clear": "clear", "partly": "some clouds", "cloudy": "cloudy", "fog": "foggy", "rain": "rain",
         "snow": "snow", "storm": "storms"}
WET = ("rain", "snow", "storm")


def hm(iso):
    """"2026-10-21T14:30" -> (date, hour, minute)"""
    return iso[:10], int(iso[11:13]), int(iso[14:16])


def hour_name(h):
    return "%d%s" % (h % 12 or 12, "am" if h < 12 else "pm")


def clock(iso):
    _, h, m = hm(iso)
    return "%d:%02d" % (h % 12 or 12, m)


def weather(place):
    unit = "celsius" if place.get("units") == "celsius" else "fahrenheit"
    d = get("api.open-meteo.com", "/v1/forecast?latitude=%s&longitude=%s&timezone=auto&forecast_days=2"
            "&forecast_hours=14&temperature_unit=%s&wind_speed_unit=mph&current=temperature_2m,apparent_temperature,"
            "weather_code,is_day,cloud_cover,wind_speed_10m,precipitation&hourly=weather_code,precipitation_probability"
            "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset" % (place["lat"], place["lon"], unit))
    cur, daily, hourly = d["current"], d["daily"], d["hourly"]
    off = int(d.get("utc_offset_seconds", 0))
    if off != _offset[0]:                       # daylight saving time began or ended: set the clock again
        _offset[0] = off
        _due["clock"] = 0
        try:
            with open("utc_offset.txt", "w") as f:
                f.write(str(off))
        except OSError:
            pass
    now = cur["time"]
    day, h_now, _ = hm(now)
    k_now = kind(cur["weather_code"])
    temp = round(cur["temperature_2m"])

    ahead = [(t, kind(c), p or 0) for t, c, p in zip(hourly["time"], hourly["weather_code"],
                                                     hourly["precipitation_probability"]) if t > now][:12]
    later = ""
    if k_now in WET:
        dry = None
        for t, k, _ in ahead:
            if k not in WET:
                dry = t
                break
        later = ("dry by " + hour_name(hm(dry)[1])) if dry else (WORDS[k_now] + " all day")
    else:
        for t, k, p in ahead:
            if k in WET and p >= 30:
                d2, h2, _ = hm(t)
                later = "%s %s" % (WORDS[k], "tonight" if h2 >= 20 or d2 > day else "at " + hour_name(h2))
                break
        if not later and ahead and all(k == "clear" for _, k, _ in ahead[:8]) and cur["is_day"]:
            later = "sunny all day" if h_now < 15 else "clear tonight"
    storm_soon = k_now == "storm" or any(k == "storm" and p >= 40 for _, k, p in ahead[:3])

    pages = ["%d°" % temp, WORDS[k_now], "H%d L%d" % (round(daily["temperature_2m_max"][0]),
                                                      round(daily["temperature_2m_min"][0]))]
    if later:
        pages.append(later)
    if abs(cur["apparent_temperature"] - cur["temperature_2m"]) >= 5:
        pages.append("feels %d°" % round(cur["apparent_temperature"]))
    if cur["wind_speed_10m"] >= 18:
        pages.append("wind %dmph" % round(cur["wind_speed_10m"]))
    sunset = daily["sunset"][0]
    after_sunset = now > sunset
    sunrise = daily["sunrise"][1 if after_sunset else 0]
    pages.append(("sunup " + clock(sunrise)) if after_sunset or h_now < 5 else ("sunset " + clock(sunset)))
    _, rh, rm = hm(daily["sunrise"][0])
    _, sh, sm = hm(sunset)
    w = {"t": now, "place": place.get("name", ""), "temp": temp, "kind": k_now, "day": cur["is_day"],
         "cloud": cur["cloud_cover"], "wet": cur["precipitation"], "wind": round(cur["wind_speed_10m"]),
         "rise": rh * 60 + rm, "set": sh * 60 + sm, "storm_soon": storm_soon, "pages": pages}
    with open("weather.json", "w") as f:
        json.dump(w, f)
    _last["weather"] = now[11:]


# ---------------------------------------------------------------- Japanese words (words.txt: "romaji<TAB>meaning")

PER_DAY = 10


def words():
    lt = time.localtime()
    stamp = "%d-%02d-%02d" % lt[:3]
    try:
        with open("kotoba.json") as f:
            if json.load(f).get("day") == stamp:
                return
    except (OSError, ValueError):
        pass
    try:
        with open("words.txt") as f:
            n = sum(1 for _ in f)
    except OSError:
        return                                  # no word list on the Unicorn
    if not n:
        return
    y = lt[0] - 1
    leap = lt[1] > 2 and lt[0] % 4 == 0 and (lt[0] % 100 != 0 or lt[0] % 400 == 0)
    days = y * 365 + y // 4 - y // 100 + y // 400 + (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)[lt[1] - 1] \
        + lt[2] + leap
    first = days * PER_DAY % n                  # works through the whole list, 10 a day, then round again
    want = set((first + i) % n for i in range(min(PER_DAY, n)))
    picked = []
    with open("words.txt") as f:
        for i, line in enumerate(f):
            if i in want:
                w, _, m = line.rstrip("\n").partition("\t")
                picked.append({"w": w, "m": m})
    with open("kotoba.json", "w") as f:
        json.dump({"day": stamp, "words": picked}, f)
    _last["words"] = stamp
