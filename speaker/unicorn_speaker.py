#!/usr/bin/env python3
"""Make the Galactic Unicorn a Wi-Fi speaker for this computer.

On Linux (a Raspberry Pi, say): adds a "Galactic Unicorn" output to PulseAudio/PipeWire and makes it the default,
then streams whatever plays on it to the Unicorn (raw 16-bit mono, 22050 Hz, TCP port 4243). It can run as the
unicorn-speaker user service, and reconnects on its own.
On Windows (experimental): sends whatever the computer is playing (pip install soundcard numpy).

It only sends while there's actual sound, so the Unicorn is free the rest of the time. Works with the Unicorn's
stock firmware (see Stream in carousel.py).

  unicorn_speaker.py [UNICORN_IP]       (it finds the Unicorn on the network by itself if you leave the IP out)
"""
import os
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unicorn                                    # noqa: E402  (finds the Unicorn on the network)

try:
    import audioop                                # (gone from Python 3.13: numpy does the same job there)
except ImportError:
    audioop = None

SINK = "unicorn"
RATE = 22050
CHUNK = RATE * 2 // 50                            # parec hands us 20 ms at a time
TICK = 0.02                                       # we pass it on to the Unicorn 20 ms at a time, evenly
PIECE = CHUNK                                     # (always a whole number of samples: an even number of bytes)
LEAD = 0.08                                       # seconds held here before sending starts, to smooth out bumps
MOST = 0.30                                       # held more than this (we fell behind): skip ahead to LEAD
QUIET = 40                                        # below this the sound counts as silence
LINGER = 3.0                                      # seconds of silence before hanging up
BOOST = 5                                         # YouTube is much quieter than the Unicorn's chimes: at its
                                                  # volume 30 the sound is played at 1.5x, with a limiter
LIMIT = 24000


def pactl(*args):
    return subprocess.run(["pactl", *args], capture_output=True, text=True).stdout


def set_up_sink():
    if SINK not in pactl("list", "short", "sinks"):
        pactl("load-module", "module-null-sink", "sink_name=" + SINK,
              "sink_properties=device.description=Galactic_Unicorn")
    pactl("set-default-sink", SINK)
    for line in pactl("list", "short", "sink-inputs").splitlines():  # anything already playing moves over too
        pactl("move-sink-input", line.split()[0], SINK)


def peak(chunk):
    if audioop:
        return audioop.max(chunk, 2)
    import numpy
    return int(numpy.abs(numpy.frombuffer(chunk, "<i2").astype("i4")).max()) if chunk else 0


def louder(chunk, gain):
    if audioop:
        return audioop.mul(chunk, 2, gain)
    import numpy
    return (numpy.frombuffer(chunk, "<i2") * gain).clip(-32768, 32767).astype("<i2").tobytes()


def connect():
    host = (sys.argv[1] if len(sys.argv) > 1 else None) or unicorn.known_host() or unicorn.find()
    if not host:
        return None
    try:
        s = socket.create_connection((host, 4243), timeout=3)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(2)
        line = s.makefile("rb").readline()        # the Unicorn says its volume first: "VOL 30"
        vol = int(line.split()[1]) / 100 if line.startswith(b"VOL") else 0.3
        return s, vol
    except (OSError, ValueError, IndexError):
        return None


class Listener(threading.Thread):
    """Reads what's playing here, louder (see BOOST), into a queue for the steady sender."""

    def __init__(self):
        super().__init__(daemon=True)
        if sys.platform.startswith("linux"):
            self.rec = subprocess.Popen(["parec", "-d", SINK + ".monitor", "--raw", "--format=s16le",
                                         "--rate=%d" % RATE, "--channels=1", "--latency-msec=20"],
                                        stdout=subprocess.PIPE)
            self.read = lambda: self.rec.stdout.read(CHUNK)
        else:
            self.read = loopback()
        self.lock = threading.Lock()
        self.queue = bytearray()
        self.last_sound = 0.0
        self.vol = 0.3
        self.gain = 1.0
        self.dead = False

    def run(self):
        while True:
            chunk = self.read()
            if not chunk:
                self.dead = True
                return
            top = peak(chunk)
            if top > QUIET:
                self.last_sound = time.time()
            want = self.vol * BOOST
            if top * want > LIMIT:
                want = LIMIT / top                # the limiter: turn down at once for loud bits...
            if want < self.gain:
                self.gain = want
            else:
                self.gain += (want - self.gain) * 0.05    # ...and back up gently
            with self.lock:
                self.queue += louder(chunk, self.gain)
                if len(self.queue) > MOST * RATE * 2:     # fell behind: skip ahead
                    del self.queue[:len(self.queue) - int(LEAD * RATE * 2)]

    def take(self, n):
        with self.lock:
            piece = bytes(self.queue[:n])
            del self.queue[:n]
            return piece

    def held(self):
        return len(self.queue) / (RATE * 2)

    def drop_all(self):
        with self.lock:
            self.queue.clear()


def loopback():
    """What Windows is playing, 20 ms at a time as 16-bit mono (experimental: needs soundcard and numpy)."""
    try:
        import numpy
        import soundcard
    except ImportError:
        sys.exit("On Windows this needs: pip install soundcard numpy")
    mic = soundcard.get_microphone(str(soundcard.default_speaker().name), include_loopback=True)
    rec = mic.recorder(samplerate=RATE, channels=1, blocksize=CHUNK // 2)
    rec.__enter__()

    def read():
        data = rec.record(numframes=CHUNK // 2)
        return (numpy.asarray(data).reshape(-1) * 32767).clip(-32768, 32767).astype("<i2").tobytes()
    return read


def main():
    if sys.platform.startswith("linux"):
        set_up_sink()
    ear = Listener()
    ear.start()
    conn, retry_at, sending, next_at = None, 0.0, False, 0.0
    while not ear.dead:
        now = time.monotonic()
        if time.time() - ear.last_sound > LINGER:    # quiet: let the Unicorn go
            if conn:
                conn.close()
                conn = None
            ear.drop_all()
            time.sleep(0.05)
            continue
        if conn is None:
            if time.time() < retry_at:
                time.sleep(0.05)
                continue
            got = connect()
            retry_at = time.time() + 5
            if not got:
                continue
            conn, ear.vol = got
            sending = False
        if not sending:                           # gather a little first, then send at a steady pace
            if ear.held() < LEAD:
                time.sleep(TICK)
                continue
            sending, next_at = True, now
        piece = ear.take(PIECE)
        if piece:
            try:
                conn.sendall(piece)
            except OSError:
                conn.close()
                conn = None
                continue
        next_at += TICK
        delay = next_at - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        elif delay < -0.2:                        # we were held up: don't try to catch up all at once
            next_at = time.monotonic()
    sys.exit("parec stopped")


if __name__ == "__main__":
    main()
