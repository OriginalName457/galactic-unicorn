# Wi-Fi for the Galactic Unicorn: lets the Pi talk to it without a data cable.
#
# Joins the home Wi-Fi (networks in secrets.py) and listens on TCP port 4242 for the same
# one-line commands the USB link takes (T clock, M message, B brightness, S sound, V volume), plus:
#   PING                 -> "PONG <ip>"
#   PUT <name> <bytes>   then exactly <bytes> of file data: saves the file (used to update the carousel)
#   RESET                restart the Unicorn
# Every command gets a one-line reply. Nothing here blocks the animation for long.
#
# If secrets.py has a KEY (Unicorn Studio makes one), the commands that change files or run code (PUT, RESET, X)
# only work with it in front: "KEY <key> PUT ...". Anyone else on the Wi-Fi can still change the scene or the
# message, but can't change the Unicorn's code or read its Wi-Fi password.

import network
import socket
import time

PORT = 4242
HOSTNAME = "unicorn"

try:
    from secrets import WIFI
except ImportError:
    WIFI = []
try:
    from secrets import KEY
except ImportError:
    KEY = ""

wlan = None
server = None
_tried = 0
_which = 0
reset_requested = False
_pending = [None, b"", 0]  # a command connection still arriving: [socket, line so far, ticks_ms when accepted]


def start():
    global wlan
    try:
        network.hostname(HOSTNAME)
    except Exception:
        pass
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        wlan.config(pm=0xa11140)            # no power saving: replies come back quickly
    except Exception:
        pass
    _connect()


def _connect():
    """Join the next network in the list (the same one again after a timeout; the next one if it was refused)."""
    global _tried, _which
    if not WIFI:
        return
    try:
        wlan.disconnect()
    except Exception:
        pass
    ssid, psk = WIFI[_which % len(WIFI)]
    _which += 1
    _tried = time.ticks_ms()
    try:
        wlan.connect(ssid, psk)
    except Exception:
        pass


def ip():
    return wlan.ifconfig()[0] if wlan and wlan.isconnected() else ""


def _listen():
    global server
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(2)
    s.setblocking(False)
    server = s


def _save(c, name, size):
    if "/" in name or not name or size > 200000:
        return "ERR bad file"
    left = size
    with open(name + ".tmp", "wb") as f:
        while left:
            chunk = c.recv(min(1024, left))
            if not chunk:
                return "ERR short"
            f.write(chunk)
            left -= len(chunk)
    import os
    try:
        os.remove(name)
    except OSError:
        pass
    os.rename(name + ".tmp", name)
    return "OK saved %s %d" % (name, size)


def poll(handle_line):
    """Call often. Keeps Wi-Fi up and runs any command that has arrived through handle_line(line)."""
    global server, reset_requested, _which
    if wlan is None:
        return
    if not wlan.isconnected():
        if server is not None:
            try:
                server.close()
            except Exception:
                pass
            server = None
        status = wlan.status()                      # 1 joining, 2 waiting for an address, <0 failed
        if status < 0 or time.ticks_diff(time.ticks_ms(), _tried) > 45000:
            if status not in (-2, -3):              # not "no such network" / "wrong password":
                _which -= 1                         # try the same network again
            _connect()
        return
    if server is None:
        try:
            _listen()
        except OSError:
            return
    if _pending[0] is None:
        try:
            c, _ = server.accept()
        except OSError:
            return                                  # nobody knocking
        c.setblocking(False)
        _pending[:] = [c, b"", time.ticks_ms()]
    c = _pending[0]
    try:                                            # gather the command line without waiting for it, so the
        while not _pending[1].endswith(b"\n") and len(_pending[1]) < 600:     # animation (and sound) keep going
            ch = c.recv(1)
            if not ch:
                break
            _pending[1] += ch
    except OSError:
        if time.ticks_diff(time.ticks_ms(), _pending[2]) < 5000:
            return                                  # the rest hasn't arrived yet: carry on, look again next time
    raw = _pending[1]
    _pending[:] = [None, b"", 0]
    try:
        c.settimeout(5)
        line = raw.decode().strip()
        trusted = not KEY
        if line.startswith("KEY "):
            _, key, line = (line + " ").split(" ", 2)
            line = line.strip()
            trusted = trusted or key == KEY
        if not trusted and (line.startswith("PUT ") or line == "RESET" or line[:1] == "X"):
            reply = "ERR this needs the key from secrets.py"
        elif line == "PING":
            reply = "PONG " + ip()
        elif line.startswith("PUT "):
            _, name, size = line.split()
            reply = _save(c, name, int(size))
        elif line == "RESET":
            reply = "OK resetting"
            reset_requested = True
        else:
            reply = handle_line(line) or "OK"
        c.send((reply + "\n").encode())
    except Exception as e:
        try:
            c.send(("ERR %s\n" % e).encode())
        except Exception:
            pass
    finally:
        c.close()
    if reset_requested:
        time.sleep_ms(200)
        import machine
        machine.mem32[0x4005800c] = 99             # a restart on purpose, not a freeze (see audioring.py)
        machine.reset()
