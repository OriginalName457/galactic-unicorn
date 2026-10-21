#!/usr/bin/env python3
"""Local weather for the Galactic Unicorn: fetches the forecast (Open-Meteo, no key needed) and sends a small
summary to the Unicorn over Wi-Fi as weather.json. Its weather scenes show what it's like outside right now (sun
or moon in the right place, clouds, rain, snow, lightning) and what's coming later today.

  weather.py                      fetch and send (the weather.timer runs this every 20 minutes)
  weather.py show                 print what would be sent
  weather.py place "Portland, OR"     set the location by name (any town works)
  weather.py place 45.52 -122.68 "Portland"   ...or by latitude/longitude
"""
import datetime
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
OUT = os.path.join(HERE, "weather.json")
UNICORN = os.path.join(os.path.dirname(HERE), "unicorn.py")
DEFAULT = {"name": "New York", "lat": 40.71, "lon": -74.01, "units": "fahrenheit"}   # set yours with `place`


def load_config():
    try:
        with open(CONFIG) as f:
            return {**DEFAULT, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULT)


def save_config(cfg):
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=1)


def get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=20) as r:
        return json.load(r)


def kind(code):
    """WMO weather code -> one word the Unicorn understands."""
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


def hour_name(h):
    return "%d%s" % (h % 12 or 12, "am" if h < 12 else "pm")


def clock(iso):
    t = datetime.datetime.fromisoformat(iso)
    return "%d:%02d" % (t.hour % 12 or 12, t.minute)


def build(cfg):
    unit = "fahrenheit" if cfg.get("units", "fahrenheit") == "fahrenheit" else "celsius"
    d = get("https://api.open-meteo.com/v1/forecast", {
        "latitude": cfg["lat"], "longitude": cfg["lon"], "timezone": "auto", "forecast_days": 2,
        "temperature_unit": unit, "wind_speed_unit": "mph",
        "current": "temperature_2m,apparent_temperature,weather_code,is_day,cloud_cover,wind_speed_10m,precipitation",
        "hourly": "weather_code,temperature_2m,precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max"})
    cur, daily, hourly = d["current"], d["daily"], d["hourly"]
    now = datetime.datetime.fromisoformat(cur["time"])
    k_now = kind(cur["weather_code"])
    temp = round(cur["temperature_2m"])

    # the next 12 hours: when does the weather turn (or clear up)?
    start = next(i for i, t in enumerate(hourly["time"]) if datetime.datetime.fromisoformat(t) > now)
    ahead = [(datetime.datetime.fromisoformat(hourly["time"][i]), kind(hourly["weather_code"][i]),
              hourly["precipitation_probability"][i] or 0) for i in range(start, min(start + 12, len(hourly["time"])))]
    later = ""
    if k_now in WET:
        dry = next((t for t, k, _ in ahead if k not in WET), None)
        later = ("dry by " + hour_name(dry.hour)) if dry else (WORDS[k_now] + " all day")
    else:
        turn = next(((t, k) for t, k, p in ahead if k in WET and p >= 30), None)
        if turn:
            when = "tonight" if turn[0].hour >= 20 or turn[0].date() > now.date() else "at " + hour_name(turn[0].hour)
            later = "%s %s" % (WORDS[turn[1]], when)
        elif all(k == "clear" for _, k, _ in ahead[:8]) and cur["is_day"]:
            later = "sunny all day" if now.hour < 15 else "clear tonight"
    storm_soon = k_now == "storm" or any(k == "storm" and p >= 40 for _, k, p in ahead[:3])

    pages = ["%d°" % temp, WORDS[k_now]]          # each page must fit the Unicorn: about 10 letters at most
    pages.append("H%d L%d" % (round(daily["temperature_2m_max"][0]), round(daily["temperature_2m_min"][0])))
    if later:
        pages.append(later)
    if abs(cur["apparent_temperature"] - cur["temperature_2m"]) >= 5:
        pages.append("feels %d°" % round(cur["apparent_temperature"]))
    if cur["wind_speed_10m"] >= 18:
        pages.append("wind %dmph" % round(cur["wind_speed_10m"]))
    sunset = datetime.datetime.fromisoformat(daily["sunset"][0])
    sunrise = datetime.datetime.fromisoformat(daily["sunrise"][1 if now > sunset else 0])
    pages.append(("sunup " + clock(sunrise.isoformat())) if now > sunset or now.hour < 5
                 else ("sunset " + clock(sunset.isoformat())))

    rise = datetime.datetime.fromisoformat(daily["sunrise"][0])
    return {
        "t": cur["time"],
        "place": cfg["name"],
        "temp": temp,
        "kind": k_now,
        "day": cur["is_day"],
        "cloud": cur["cloud_cover"],
        "wet": cur["precipitation"],
        "wind": round(cur["wind_speed_10m"]),
        "rise": rise.hour * 60 + rise.minute,       # minutes after midnight, for the sun's path across the sky
        "set": sunset.hour * 60 + sunset.minute,
        "storm_soon": storm_soon,
        "pages": pages,
    }


def main():
    args = sys.argv[1:]
    cfg = load_config()
    if args and args[0] == "place":
        if len(args) >= 3 and args[1].lstrip("-").replace(".", "").isdigit():
            cfg.update(lat=float(args[1]), lon=float(args[2]), name=" ".join(args[3:]) or cfg["name"])
        else:
            hits = get("https://geocoding-api.open-meteo.com/v1/search",
                       {"name": " ".join(args[1:]).split(",")[0], "count": 5}).get("results") or []
            want = " ".join(args[1:]).lower()
            hit = next((h for h in hits if (h.get("admin1", "") + h.get("country_code", "")).lower()[:2] in want),
                       hits[0] if hits else None)
            if not hit:
                sys.exit("Couldn't find that place.")
            cfg.update(lat=hit["latitude"], lon=hit["longitude"], name=hit["name"])
            cfg["units"] = "fahrenheit" if hit.get("country_code") in ("US", "LR", "MM") else "celsius"
        save_config(cfg)
        print("Weather location: %s (%.2f, %.2f), %s" % (cfg["name"], cfg["lat"], cfg["lon"], cfg["units"]))
        args = []
    data = build(cfg)
    if args and args[0] == "show":
        print(json.dumps(data, indent=1, ensure_ascii=False))
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    r = subprocess.run([sys.executable, UNICORN, "push", OUT, "weather.json"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())


if __name__ == "__main__":
    main()
