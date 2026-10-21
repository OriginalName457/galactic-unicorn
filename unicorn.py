#!/usr/bin/env python3
"""Talk to the Galactic Unicorn, over Wi-Fi (no data cable needed) or USB as a fallback.

  unicorn.py sync              keep the Unicorn's clock in sync (runs as a service)
  unicorn.py say TEXT...       add a custom scrolling message to the carousel
  unicorn.py clear             remove the custom message
  unicorn.py bright N          set brightness to N percent (2-100), remembered on the Unicorn
  unicorn.py sound NAME        play a tune: beep chime love sakura spooky fanfare doorbell konbini
  unicorn.py sound C5:2 E5:4   ...or your own notes (note+octave:beats, "-" is a rest)
  unicorn.py volume N          speaker volume 0-100, remembered
  unicorn.py status            what it's set to right now
  unicorn.py pretend 2026 12 24  show the scenes for another day of the year ("pretend" alone goes back)
  unicorn.py perf              how fast each scene draws, and free memory
  unicorn.py next              skip to the next scene
  unicorn.py show NAME         show a scene now (e.g. Campfire)
  unicorn.py timer MIN [NAME]  a kitchen timer on the screen (minutes; 0 cancels)
  unicorn.py push FILE [NAME]  copy a file onto the Unicorn over Wi-Fi (e.g. carousel.py), then `reset`
  unicorn.py reset             restart it
  unicorn.py find              look for it on the network
"""
import concurrent.futures
import glob
import ipaddress
import os
import socket
import sys
import time

SYNC_EVERY = 60  # seconds (also how soon a freshly plugged-in Unicorn learns the date)
PORT = 4242
HOST_FILE = os.path.expanduser("~/.config/unicorn-host")


# ---------------------------------------------------------------- Wi-Fi

def known_host():
    try:
        with open(HOST_FILE) as f:
            return f.read().strip()
    except OSError:
        return None


def remember(host):
    os.makedirs(os.path.dirname(HOST_FILE), exist_ok=True)
    with open(HOST_FILE, "w") as f:
        f.write(host)


def key():
    """The Unicorn's KEY from secrets.py, if it has one: PUT, RESET and X need it."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from secrets import KEY
        return KEY
    except ImportError:
        return ""


def talk(host, line, data=None, timeout=5):
    if key() and (line.startswith("PUT ") or line == "RESET" or line[:1] == "X"):
        line = "KEY %s %s" % (key(), line)
    with socket.create_connection((host, PORT), timeout=timeout) as s:
        s.sendall((line + "\n").encode())
        if data:
            s.sendall(data)
        return s.makefile().readline().strip()


def find():
    """Ask every address on our network whether it's the Unicorn."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:     # (sends nothing: just picks our address)
        s.connect(("192.0.2.1", 9))
        net = ipaddress.ip_interface(s.getsockname()[0] + "/24").network

    def probe(ip):
        try:
            return str(ip) if talk(str(ip), "PING", timeout=0.6).startswith("PONG") else None
        except OSError:
            return None
    with concurrent.futures.ThreadPoolExecutor(64) as pool:
        for hit in pool.map(probe, net.hosts()):
            if hit:
                remember(hit)
                return hit
    return None


def wifi(line, data=None):
    """Send over Wi-Fi; returns the reply, or None if the Unicorn can't be reached that way."""
    host = known_host()
    for attempt in range(2):
        if host:
            try:
                return talk(host, line, data)
            except OSError:
                pass
        if attempt == 0:
            host = find()
    return None


# ---------------------------------------------------------------- USB

def find_port():
    ports = glob.glob("/dev/serial/by-id/*MicroPython*") + glob.glob("/dev/serial/by-id/*Pimoroni*")
    ports += sorted(glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


def usb(line):
    import serial
    port = find_port()
    if not port:
        raise OSError("Galactic Unicorn not reachable over Wi-Fi or USB")
    with serial.Serial(port, 115200, timeout=1, write_timeout=2) as s:
        s.write((line + "\n").encode())
        s.flush()
    return "OK (sent over USB)"


def send(line):
    reply = wifi(line)
    return reply if reply is not None else usb(line)


# ----------------------------------------------------------------

def time_line():
    lt = time.localtime()
    return "T %d %d %d %d %d %d %d" % (lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec, lt.tm_wday)


def sync_forever():
    while True:
        try:
            send(time_line())
            wait = SYNC_EVERY
        except OSError:
            wait = 30  # unreachable; retry soon so it syncs right after it comes back
        time.sleep(wait)


def push(path, name=None):
    name = name or os.path.basename(path)
    with open(path, "rb") as f:
        data = f.read()
    reply = wifi("PUT %s %d" % (name, len(data)), data)
    if reply is None:
        sys.exit("Couldn't reach the Unicorn over Wi-Fi.")
    print(reply)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    if cmd == "sync":
        sync_forever()
    elif cmd == "say":
        send("M " + " ".join(rest))
        print("Sent. It'll show up in the carousel shortly.")
    elif cmd == "clear":
        print(send("M"))
    elif cmd == "bright" and len(rest) == 1:
        send("B " + rest[0])
        print("Brightness set to %s%%." % rest[0])
    elif cmd == "sound":
        print(send("S " + " ".join(rest or ["beep"])))
    elif cmd == "volume" and len(rest) == 1:
        print(send("V " + rest[0]))
    elif cmd == "status":
        print(wifi("?") or "Not reachable over Wi-Fi.")
    elif cmd == "pretend":
        print(wifi(" ".join(["D"] + rest)) or "Not reachable over Wi-Fi.")
    elif cmd == "next":
        print(wifi("N") or "Not reachable over Wi-Fi.")
    elif cmd == "show" and rest:
        print(wifi("G " + rest[0]) or "Not reachable over Wi-Fi.")
    elif cmd == "timer" and rest:
        print(wifi("TIMER %d %s" % (float(rest[0]) * 60, " ".join(rest[1:]))) or "Not reachable over Wi-Fi.")
    elif cmd == "perf":
        print(wifi("P") or "Not reachable over Wi-Fi.")
    elif cmd == "push" and rest:
        push(rest[0], rest[1] if len(rest) > 1 else None)
    elif cmd == "reset":
        print(wifi("RESET") or "Not reachable over Wi-Fi.")
    elif cmd == "find":
        print(find() or "Not found on the network.")
    elif cmd == "time":
        print(send(time_line()))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
