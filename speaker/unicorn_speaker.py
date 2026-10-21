#!/usr/bin/env python3
"""Make the Galactic Unicorn the Pi's speaker, over Wi-Fi.

Adds a "Galactic Unicorn" output to PulseAudio and makes it the default, then streams whatever plays on it
to the Unicorn (raw 16-bit mono, 22050 Hz, TCP port 4243). It only sends while there's actual sound, so the
Unicorn is free the rest of the time. Runs as the unicorn-speaker user service; it reconnects on its own.
Needs the Unicorn firmware with audio streaming (~/unicorn-firmware).
"""
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unicorn                                    # noqa: E402  (finds the Unicorn on the network)

SINK = "unicorn"
RATE = 22050
CHUNK = RATE * 2 // 50                            # 20 ms of audio
QUIET = 40                                        # below this the sound counts as silence
LINGER = 3.0                                      # seconds of silence before hanging up


def pactl(*args):
    return subprocess.run(["pactl", *args], capture_output=True, text=True).stdout


def set_up_sink():
    if SINK not in pactl("list", "short", "sinks"):
        pactl("load-module", "module-null-sink", "sink_name=" + SINK,
              "sink_properties=device.description=Galactic_Unicorn")
    pactl("set-default-sink", SINK)
    for line in pactl("list", "short", "sink-inputs").splitlines():  # anything already playing moves over too
        pactl("move-sink-input", line.split()[0], SINK)


def loud(chunk):
    step = 2 * 16                                 # check every 16th sample: plenty to tell sound from silence
    for i in range(0, len(chunk) - 1, step):
        v = int.from_bytes(chunk[i:i + 2], "little", signed=True)
        if v > QUIET or v < -QUIET:
            return True
    return False


def connect():
    host = unicorn.known_host() or unicorn.find()
    if not host:
        return None
    try:
        s = socket.create_connection((host, 4243), timeout=3)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.settimeout(2)
        return s
    except OSError:
        return None


def main():
    set_up_sink()
    rec = subprocess.Popen(["parec", "-d", SINK + ".monitor", "--raw", "--format=s16le", "--rate=%d" % RATE,
                            "--channels=1", "--latency-msec=20"], stdout=subprocess.PIPE)
    conn, last_sound, retry_at = None, 0.0, 0.0
    while True:
        chunk = rec.stdout.read(CHUNK)
        if not chunk:
            sys.exit("parec stopped")
        now = time.time()
        if loud(chunk):
            last_sound = now
        if now - last_sound > LINGER:             # quiet: let the Unicorn go
            if conn:
                conn.close()
                conn = None
            continue
        if conn is None and now >= retry_at:
            conn = connect()
            retry_at = now + 5
        if conn:
            try:
                conn.sendall(chunk)
            except OSError:
                conn.close()
                conn = None


if __name__ == "__main__":
    main()
