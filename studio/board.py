"""Talking to a Galactic Unicorn over its USB data cable, for Unicorn Studio.

Two ways in:
  * live: the carousel keeps running and answers one-line commands ("S konbini", "G Campfire", "?") with a line
    starting "@@ " (see handle_line in carousel.py). Used to try things out and to read the settings.
  * raw REPL: MicroPython's own way in for tools (the same one mpremote uses). It stops the carousel, so it's only
    used to copy files over and set up a new Unicorn, followed by a restart.
"""
import base64
import glob
import os
import string
import sys
import threading
import time

import serial
import serial.tools.list_ports

PICO_VID = 0x2E8A                   # Raspberry Pi: every Pico, in MicroPython or in its USB-drive mode
MICROPYTHON_PID = 0x0005            # MicroPython's own (not a Debug Probe or another Pico program)
FIRMWARE = "v1.21.0"                # the Pimoroni release this carousel is made for
FIRMWARE_URL = ("https://github.com/pimoroni/pimoroni-pico/releases/download/v1.21.0/"
                "pimoroni-galactic_unicorn-v1.21.0-micropython.uf2")


class BoardError(Exception):
    pass


def find_ports():
    """Serial ports that look like a Pico running MicroPython."""
    return [p.device for p in serial.tools.list_ports.comports()
            if p.vid == PICO_VID and p.pid in (MICROPYTHON_PID, None)]


def _is_rp2040(root):
    """Is this drive a Pico in firmware-update mode? (Other boards have an INFO_UF2.TXT too.)"""
    try:
        with open(os.path.join(root, "INFO_UF2.TXT")) as f:
            return "RPI-RP2" in f.read(512)
    except OSError:
        return False


def _removable_drives():
    """Windows: the letters of removable drives (looking at network drives can hang)."""
    import ctypes
    k = ctypes.windll.kernel32
    mask = k.GetLogicalDrives()
    return [L + ":\\" for i, L in enumerate(string.ascii_uppercase) if mask >> i & 1 and i >= 2
            and k.GetDriveTypeW(L + ":\\") == 2]       # DRIVE_REMOVABLE


def find_uf2_drive():
    """The RPI-RP2 drive a Pico shows up as in its firmware-update mode (BOOTSEL), or None."""
    if sys.platform == "win32":
        candidates = _removable_drives()
    else:
        candidates = ["/Volumes/RPI-RP2"] + glob.glob("/media/*/RPI-RP2") + glob.glob("/run/media/*/RPI-RP2") \
            + glob.glob("/media/RPI-RP2")
    for c in candidates:
        if _is_rp2040(c):
            return c
    return None


class Board:
    def __init__(self, port):
        self.port = port
        self.s = serial.Serial(port, 115200, timeout=0.05, write_timeout=5)
        self.lock = threading.RLock()
        self.raw = False
        self.wdt = False
        self.repl = False                       # saw MicroPython's ">>>" prompt: nothing is running
        self._buf = b""
        self._used = time.time()
        threading.Thread(target=self._feeder, daemon=True).start()

    def close(self):
        try:
            if self.raw:
                self.s.write(b"\x02")           # back to the normal REPL,
                time.sleep(0.1)
                self.s.write(b"\x04")           # and a soft restart there starts the carousel again
                self.raw = False
            self.s.close()
        except Exception:
            pass

    def _feeder(self):
        """While the carousel is stopped, keep feeding a watchdog the speaker stream may have started."""
        while self.s.is_open:
            time.sleep(1)
            if self.raw and self.wdt and time.time() - self._used > 3:
                try:
                    self.exec_("pass", 5)
                except Exception:
                    pass

    # ------------------------------------------------------------ live

    def command(self, line, timeout=3.0):
        """Send a command to the running carousel. Returns its reply, or None if nothing answered."""
        with self.lock:
            if self.raw:
                raise BoardError("the carousel isn't running")
            self.s.reset_input_buffer()
            self.s.write((line + "\n").encode())
            buf, end = b"", time.time() + timeout
            while time.time() < end:
                buf += self.s.read(65536)
                if b">>> " in buf:              # MicroPython's prompt: no carousel to answer
                    self.repl = True
                    return None
                while b"\n" in buf:
                    got, buf = buf.split(b"\n", 1)
                    got = got.strip()
                    if got.startswith(b"@@ "):
                        return got[3:].decode("utf-8", "replace")
            return None

    def cat(self, name):
        """A settings file's contents (bytes) via the running carousel, or None if it isn't there."""
        reply = self.command("CAT " + name, timeout=5)
        if reply and reply.startswith("OK "):
            return base64.b64decode(reply[3:])
        if reply and reply.startswith("ERR no file"):
            return None
        raise BoardError("couldn't read %s: %s" % (name, reply or "no answer from the Unicorn"))

    # ------------------------------------------------------------ raw REPL

    def _read_until(self, ending, timeout):
        end = time.time() + timeout
        while ending not in self._buf:
            if time.time() > end:
                raise BoardError("the Unicorn stopped answering (waiting for %r, got %r)" % (ending, self._buf[-80:]))
            self._buf += self.s.read(max(1, self.s.in_waiting))
        i = self._buf.index(ending) + len(ending)
        got, self._buf = self._buf[:i], self._buf[i:]
        return got

    def enter_raw(self):
        """Stop whatever is running and get MicroPython's attention."""
        with self.lock:
            for _ in range(3):
                self.s.write(b"\r\x03")
                time.sleep(0.15)
                self.s.write(b"\x03")
                time.sleep(0.25)
                self.s.reset_input_buffer()
                self._buf = b""
                self.s.write(b"\r\x01")
                try:
                    self._read_until(b"raw REPL; CTRL-B to exit\r\n>", 3)
                    break
                except BoardError:
                    continue
            else:
                raise BoardError("couldn't get the Unicorn's attention: is it running MicroPython?")
            self.raw = True
        # a watchdog left running by the speaker stream would restart the board mid-copy: keep it fed
        self.wdt = self.exec_("import machine\nprint(machine.mem32[0x40058000] >> 30 & 1)").strip() == "1"
        self.exec_("import sys\nc = sys.modules.get('carousel_app')\ntry:\n c.stream.stop()\n c.gu.stop_playing()\n"
                   "except Exception:\n pass\ndel c")
        # then a soft restart, for all of the memory back (the carousel's still loaded). In raw mode main.py
        # doesn't run again, so the carousel stays stopped.
        with self.lock:
            self._buf = b""
            self.s.write(b"\x04")
            self._read_until(b"soft reboot\r\n", 5)
            self._read_until(b"raw REPL; CTRL-B to exit\r\n>", 5)

    def exec_(self, code, timeout=20):
        """Run code on the Unicorn; returns what it printed. Errors come back as BoardError."""
        if self.wdt:
            code = "import machine\nmachine.WDT(timeout=8000).feed()\n" + code
        data = code.encode()
        with self.lock:
            if not self.raw:
                raise BoardError("not in raw REPL")
            self._used = time.time()
            for i in range(0, len(data), 256):
                self.s.write(data[i:i + 256])
                time.sleep(0.002)
            self.s.write(b"\x04")
            if self._read_until(b"OK", 5)[-2:] != b"OK":
                raise BoardError("the Unicorn didn't take the command")
            out = self._read_until(b"\x04", timeout)[:-1]
            err = self._read_until(b"\x04", timeout)[:-1]
            self._read_until(b">", 5)
            self._used = time.time()
        if err:
            raise BoardError(err.decode("utf-8", "replace").strip().splitlines()[-1])
        return out.decode("utf-8", "replace")

    def info(self):
        """(MicroPython version line, has the Galactic Unicorn library)."""
        out = self.exec_("import sys\nprint(sys.version)\ntry:\n import galactic\n print('GU')\nexcept ImportError:\n"
                         " print('-')").strip().splitlines()
        return out[0], out[-1] == "GU"

    def listdir(self):
        return self.exec_("import os\nprint('\\n'.join(os.listdir()))").split()

    def hashes(self, names):
        """{name: sha256 hex, or None if it isn't there} for files on the Unicorn."""
        out = self.exec_(
            "import hashlib, binascii\nfor n in %r:\n try:\n  h = hashlib.sha256()\n  with open(n, 'rb') as f:\n"
            "   while True:\n    b = f.read(1024)\n    if not b:\n     break\n    h.update(b)\n"
            "  print(n, binascii.hexlify(h.digest()).decode())\n except OSError:\n  print(n, '-')" % list(names))
        got = {}
        for line in out.splitlines():
            n, _, h = line.strip().rpartition(" ")
            got[n] = None if h == "-" else h
        return got

    def read(self, name):
        """A file's contents (bytes), or None if it isn't there."""
        out = self.exec_("import binascii\ntry:\n with open(%r, 'rb') as f:\n  while True:\n   b = f.read(600)\n"
                         "   if not b:\n    break\n   print(binascii.b2a_base64(b).decode().strip())\n"
                         "except OSError:\n print('-')" % name)
        if out.strip() == "-":
            return None
        return b"".join(base64.b64decode(line) for line in out.split())

    def put(self, name, data, progress=None):
        """Copy a file onto the Unicorn (written to name.tmp first, so a cut-off copy never leaves half a file)."""
        self.exec_("import binascii\nf = open(%r, 'wb')\nw = f.write\na = binascii.a2b_base64" % (name + ".tmp"))
        step = 1536
        for i in range(0, len(data), step):
            self.exec_("w(a(%r))" % base64.b64encode(data[i:i + step]).decode())
            if progress:
                progress(min(len(data), i + step))
        self.exec_("f.close()\nimport os\ntry:\n os.remove(%r)\nexcept OSError:\n pass\nos.rename(%r, %r)"
                   % (name, name + ".tmp", name))

    def remove(self, name):
        self.exec_("import os\ntry:\n os.remove(%r)\nexcept OSError:\n pass" % name)

    def reset(self):
        """Restart the Unicorn (it starts the carousel again; the USB connection drops for a moment)."""
        with self.lock:
            self.s.write(b"import machine\nmachine.reset()\x04")
            time.sleep(0.3)
            self.raw = False
        self.close()

    def bootloader(self):
        """Into firmware-update mode: the Unicorn shows up as an RPI-RP2 drive."""
        with self.lock:
            self.s.write(b"import machine\nmachine.bootloader()\x04")
            time.sleep(0.3)
            self.raw = False
        self.close()
