#!/usr/bin/env python3
"""Unicorn Studio: set up and customise a Pimoroni Galactic Unicorn, no programming needed.

Plug the Unicorn into this computer with a USB *data* cable and open this app. It finds the Unicorn, puts the
carousel on it (and the right firmware, if it needs it), and lets you pick the scenes you like, draw your own
pixel animations, set alarms and timers, add birthdays and messages, and join it to your Wi-Fi. Press "Save to
Unicorn" and unplug: it carries on by itself, from any USB power supply.

  python3 studio/unicorn_studio.py          (needs: pip install pyserial; and mpy-cross==1.21.0 from the source)
"""
import json
import os
import queue
import secrets
import ssl
import sys
import tempfile
import threading
import time
import tkinter as tk
import traceback
import urllib.parse
import urllib.request
from tkinter import colorchooser, filedialog, messagebox, ttk
from tkinter import font as tkfont

HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import board as unicorn  # noqa: E402
import wifi_info  # noqa: E402

VERSION = "1.0"
W, H = 53, 11
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"          # palette letters in an animation's frames ("." is off)
PALETTE = [(255, 255, 255), (255, 40, 40), (255, 140, 0), (255, 220, 0), (60, 200, 60), (0, 140, 255),
           (140, 70, 255), (255, 80, 180), (120, 60, 20), (128, 128, 128), (0, 80, 0), (0, 0, 140),
           (255, 190, 150), (160, 255, 255), (60, 30, 80), (255, 255, 160)]

ACCENT, ACCENT_DARK, PAPER, INK, MUTED, GOOD, BAD = "#7c4dff", "#5a32d6", "#f6f4fb", "#1f1a2e", "#6b6680", \
    "#1a9e5c", "#d64545"


def load_catalog():
    with open(os.path.join(HERE, "catalog.json"), encoding="utf-8") as f:
        return json.load(f)


def board_files():
    """{name on the Unicorn: bytes} for the carousel itself (made by build_board.py)."""
    folder = os.path.join(HERE, "board_files")
    if not os.path.exists(os.path.join(folder, "manifest.json")):
        import build_board                                # running from the source: make them now
        build_board.build()
    with open(os.path.join(folder, "manifest.json")) as f:
        names = json.load(f)["files"]
    out = {}
    for n in names:
        with open(os.path.join(folder, n), "rb") as f:
            out[n] = f.read()
    return out


def open_url(url, timeout=15):
    """urlopen, with certifi's certificates when it's there (the Mac app has none of its own)."""
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = None
    return urllib.request.urlopen(url, timeout=timeout, context=ctx)


def fetch_json(url):
    """GET some JSON, over https (falling back to http if this computer's certificates are missing)."""
    try:
        with open_url(url) as r:
            return json.load(r)
    except (ssl.SSLError, urllib.error.URLError) as e:
        if "CERTIFICATE" not in str(e).upper() and not isinstance(e, ssl.SSLError):
            raise
        with urllib.request.urlopen(url.replace("https://", "http://", 1), timeout=15) as r:
            return json.load(r)


def remember_host(ip):
    """Where the Unicorn is on the Wi-Fi, for the other tools here (unicorn.py, the speaker)."""
    try:
        path = os.path.expanduser("~/.config/unicorn-host")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(ip)
    except OSError:
        pass


def hexcolor(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def new_id():
    return "a" + secrets.token_hex(3)


def blank_frame():
    return "." * (W * H)


# ================================================================ the window

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Unicorn Studio")
        self.geometry("1060x720")
        self.minsize(900, 600)
        self.configure(bg=PAPER)
        self.catalog = load_catalog()
        self.board = None
        self.live = False               # the carousel is running (try-it buttons work)
        self.on_wifi = False            # ...and it's on Wi-Fi
        self.mode = "none"              # none | live | raw | firmware | bootsel
        self.busy = False
        self.dirty = False
        self.jobs = queue.Queue()       # things for the UI thread to do, from the worker threads
        self.settings = self.fresh_settings()
        self.arts = {}                  # id -> animation (palette, frames, fps, text, text_color)
        self.wifi_changed = False
        self.my_scenes = None           # bytes of a my_scenes.py to put on the Unicorn, or b"" to take it off
        self.style_up()
        self.build()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.after(50, self.pump)
        self.after(300, self.connect)

    @staticmethod
    def fresh_settings():
        return {"off": [], "alarms": [], "dates": [], "messages": [], "art": [], "tunes": {}, "24h": False,
                "sleep": None, "timer_sound": "chime", "brightness": 30, "volume": 30,
                "utc_offset": time.localtime().tm_gmtoff // 60}     # until it knows the town's own time zone

    # ------------------------------------------------------------ looks

    def style_up(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        family = tkfont.nametofont("TkDefaultFont").actual("family")
        size = 10 if sys.platform == "win32" else 13 if sys.platform == "darwin" else 11
        base = tkfont.Font(self, family=family, size=size)
        self.fonts = {"base": base, "tab": tkfont.Font(self, family=family, size=size + 1),
                      "title": tkfont.Font(self, family=family, size=size + 9, weight="bold"),
                      "h": tkfont.Font(self, family=family, size=size + 2, weight="bold"),
                      "card": tkfont.Font(self, family=family, size=size + 1, weight="bold"),
                      "button": tkfont.Font(self, family=family, size=size + 2, weight="bold")}
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=family, size=size)
        s.configure(".", background=PAPER, foreground=INK, font=base)
        s.configure("TNotebook", background=PAPER, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 8), font=self.fonts["tab"])
        s.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", ACCENT_DARK)])
        s.configure("TFrame", background=PAPER)
        s.configure("Card.TFrame", background="white", relief="flat")
        s.configure("TLabel", background=PAPER, foreground=INK)
        s.configure("Card.TLabel", background="white")
        s.configure("Muted.TLabel", foreground=MUTED)
        s.configure("CardMuted.TLabel", background="white", foreground=MUTED)
        s.configure("Title.TLabel", font=self.fonts["title"], foreground=ACCENT_DARK)
        s.configure("H.TLabel", font=self.fonts["h"])
        s.configure("CardH.TLabel", background="white", font=self.fonts["card"])
        s.configure("TCheckbutton", background=PAPER)
        s.configure("Card.TCheckbutton", background="white")
        s.configure("TRadiobutton", background=PAPER)
        s.configure("Accent.TButton", background=ACCENT, foreground="white", padding=(18, 9),
                    font=self.fonts["button"])
        s.map("Accent.TButton", background=[("disabled", "#b9a8f0"), ("active", ACCENT_DARK)])
        s.configure("TButton", padding=(10, 5))
        s.configure("TLabelframe", background=PAPER)
        s.configure("TLabelframe.Label", background=PAPER, foreground=ACCENT_DARK, font=self.fonts["card"])

    # ------------------------------------------------------------ layout

    def build(self):
        top = ttk.Frame(self, padding=(18, 12, 18, 4))
        top.pack(fill="x")
        ttk.Label(top, text="Unicorn Studio", style="Title.TLabel").pack(side="left")
        self.dot = tk.Canvas(top, width=14, height=14, bg=PAPER, highlightthickness=0)
        self.dot.pack(side="left", padx=(18, 6))
        self.status = ttk.Label(top, text="Looking for your Unicorn...")
        self.status.pack(side="left")
        ttk.Button(top, text="Reconnect", command=self.connect).pack(side="right")

        bottom = ttk.Frame(self, padding=(18, 8, 18, 14))
        bottom.pack(side="bottom", fill="x")
        self.save_btn = ttk.Button(bottom, text="Save to Unicorn", style="Accent.TButton", command=self.save)
        self.save_btn.pack(side="right")
        self.note = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.note.pack(side="right", padx=12)
        self.progress = ttk.Progressbar(bottom, length=220, mode="determinate")
        self.progress.pack(side="left")
        self.progress_text = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.progress_text.pack(side="left", padx=8)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=12)
        self.scenes_tab = ScenesTab(self)
        self.art_tab = ArtTab(self)
        self.sound_tab = SoundTab(self)
        self.dates_tab = DatesTab(self)
        self.setup_tab = SetupTab(self)
        for tab, name in ((self.scenes_tab, "Scenes"), (self.art_tab, "My animations"),
                          (self.sound_tab, "Sounds, alarms & timers"), (self.dates_tab, "Dates & messages"),
                          (self.setup_tab, "Wi-Fi & settings")):
            self.tabs.add(tab, text=name)
        self.set_status("Looking for your Unicorn...", MUTED)
        self.refresh_all()

    def set_status(self, text, color):
        self.status.config(text=text)
        self.dot.delete("all")
        self.dot.create_oval(2, 2, 12, 12, fill=color, outline="")

    def changed(self, *_):
        self.dirty = True
        self.note.config(text="Changes not saved to the Unicorn yet")

    def refresh_all(self):
        for tab in (self.scenes_tab, self.art_tab, self.sound_tab, self.dates_tab, self.setup_tab):
            tab.load()

    # ------------------------------------------------------------ threads

    def pump(self):
        """Runs what the worker threads asked the window to do."""
        try:
            while True:
                fn = self.jobs.get_nowait()
                fn()
        except queue.Empty:
            pass
        self.after(50, self.pump)

    def ui(self, fn, *args):
        self.jobs.put(lambda: fn(*args))

    def work(self, fn, done=None, label=""):
        """Run fn in the background (serial work mustn't freeze the window)."""
        if self.busy:
            return
        self.busy = True
        self.save_btn.state(["disabled"])
        if label:
            self.progress_text.config(text=label)
            self.progress.config(mode="indeterminate")
            self.progress.start(12)

        def run():
            err = result = None
            try:
                result = fn()
            except Exception as e:                      # shown to the person, never a crash
                traceback.print_exc()
                err = e

            def finish():
                self.busy = False
                self.save_btn.state(["!disabled"])
                self.progress.stop()
                self.progress.config(mode="determinate", value=0)
                self.progress_text.config(text="")
                if err:
                    messagebox.showerror("Unicorn Studio", str(err) or repr(err))
                elif done:
                    done(result)
            self.jobs.put(finish)
        threading.Thread(target=run, daemon=True).start()

    def try_it(self, line, quiet=False):
        """Send a command (or a list of them) to the running Unicorn: the "try it" buttons."""
        if not self.live:
            if not quiet:
                messagebox.showinfo("Unicorn Studio", "This works once the Unicorn is set up and running. "
                                                      "Press \"Save to Unicorn\" first.")
            return
        b = self.board

        def run():
            for one in ([line] if isinstance(line, str) else line):
                try:
                    reply = b.command(one)
                except Exception as e:
                    reply = "ERR %s" % e
                if reply and reply.startswith("ERR") and not quiet:
                    self.ui(messagebox.showwarning, "Unicorn Studio", reply[4:])
                    return
        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------ connecting

    def connect(self):
        if self.busy:
            return
        if self.board:
            self.board.close()
            self.board = None
        self.live = False
        self.set_status("Looking for your Unicorn...", MUTED)
        self.work(self._connect, self._connected, "Connecting")

    def _connect(self):
        ports = unicorn.find_ports()
        if not ports:
            return {"mode": "bootsel" if unicorn.find_uf2_drive() else "none"}
        last = None
        for port in ports:
            try:
                b = unicorn.Board(port)
            except Exception as e:
                last = e
                continue
            reply = None
            end = time.time() + 15          # a carousel that's just started can be busy for a bit (Wi-Fi, weather)
            while not reply and not b.repl and time.time() < end:
                reply = b.command("?", 2.5)
            if reply:                                   # the carousel is running and answering
                got = {"mode": "live", "board": b, "status": reply}
                try:
                    raw = b.cat("settings.json")
                    got["settings"] = json.loads(raw) if raw else None
                    got["arts"] = {}
                    for e in (got["settings"] or {}).get("art", []):
                        data = b.cat("art_%s.json" % e["id"])
                        if data:
                            got["arts"][e["id"]] = json.loads(data)
                    for name in ("brightness.txt", "volume.txt"):
                        data = b.cat(name)
                        if data:
                            got[name] = data
                    return got
                except (unicorn.BoardError, ValueError):
                    pass                                # (a big animation file, say): read them the other way
            try:                                        # not answering: a new Unicorn, or a different program
                b.enter_raw()
                version, has_gu = b.info()
            except unicorn.BoardError:
                b.close()
                return {"mode": "firmware", "why": "It doesn't seem to be running MicroPython."}
            if not has_gu or unicorn.FIRMWARE not in version:
                return {"mode": "firmware", "board": b,
                        "why": "It has %s; the carousel needs Pimoroni's Galactic Unicorn firmware %s." % (
                            version.split(";")[-1].strip(), unicorn.FIRMWARE)}
            got = {"mode": "raw", "board": b}
            raw = b.read("settings.json")
            got["settings"] = json.loads(raw) if raw else None
            got["arts"] = {}
            for e in (got["settings"] or {}).get("art", []):
                data = b.read("art_%s.json" % e["id"])
                if data:
                    got["arts"][e["id"]] = json.loads(data)
            return got
        if last and "ermission" in str(last) and sys.platform.startswith("linux"):
            raise unicorn.BoardError("This computer won't let Unicorn Studio use the USB port. In a terminal, run\n\n"
                                     "    sudo usermod -aG dialout $USER\n\nthen log out and back in, and try again.")
        if last and "ermission" in str(last):
            raise unicorn.BoardError("The Unicorn's USB port is busy. Is another program (Thonny, say) using it?")
        raise last or unicorn.BoardError("couldn't open the Unicorn's USB port")

    def _connected(self, got):
        self.mode = got["mode"]
        self.board = got.get("board")
        self.live = self.mode == "live"
        if self.mode in ("live", "raw"):
            s = self.fresh_settings()
            s.update(got.get("settings") or {})
            for name, key in (("brightness.txt", "brightness"), ("volume.txt", "volume")):
                try:
                    s[key] = round(float(got[name]) * 100)
                except (KeyError, ValueError):
                    pass
            if not self.dirty:
                self.settings, self.arts = s, got.get("arts", {})
                self.refresh_all()
        if self.mode == "live":
            wifi = got["status"].rsplit(" wifi ", 1)[-1].strip() if " wifi " in got["status"] else "-"
            self.on_wifi = wifi not in ("-", "")
            if self.on_wifi:
                remember_host(wifi)
            self.set_status("Connected, and running" + (" (on Wi-Fi at %s)" % wifi if wifi not in ("-", "") else
                                                        " (not on Wi-Fi yet)"), GOOD)
        elif self.mode == "raw":
            self.set_status("Connected. Press \"Save to Unicorn\" to set it up.", ACCENT)
            if not got.get("settings"):
                self.tabs.select(self.setup_tab)
        elif self.mode == "firmware":
            self.set_status("Connected, but it needs new firmware", BAD)
            self.offer_firmware(got.get("why", ""))
        elif self.mode == "bootsel":
            self.set_status("Found a Unicorn in firmware-update mode", BAD)
            self.offer_firmware("It's waiting for new firmware.")
        else:
            self.set_status("No Unicorn found. Plug it in with a USB data cable, then press Reconnect.", BAD)

    # ------------------------------------------------------------ firmware

    def offer_firmware(self, why):
        if not messagebox.askyesno(
                "New firmware needed",
                why + "\n\nInstall Pimoroni's Galactic Unicorn firmware %s now? (It's downloaded from Pimoroni's "
                      "GitHub page and takes about a minute. Files already on the Unicorn are kept.)" % unicorn.FIRMWARE):
            return
        self.work(self._firmware, lambda _: self.after(1500, self.connect), "Installing firmware")

    def _firmware(self):
        path = os.path.join(tempfile.gettempdir(), os.path.basename(unicorn.FIRMWARE_URL))
        if not os.path.exists(path) or os.path.getsize(path) < 500000:
            self.ui(self.progress_text.config, {"text": "Downloading firmware"})
            with open_url(unicorn.FIRMWARE_URL, 60) as r, open(path + ".part", "wb") as f:
                while True:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(path + ".part", path)
        drive = unicorn.find_uf2_drive()
        if not drive and self.board:
            self.board.bootloader()                      # MicroPython can switch to update mode by itself
            self.board = None
        if not drive and not self.board:
            for _ in range(20):
                time.sleep(0.5)
                drive = unicorn.find_uf2_drive()
                if drive:
                    break
        if not drive:
            self.ui(messagebox.showinfo, "One more step",
                    "Unplug the Unicorn. Then hold down the little BOOTSEL button on the back of the Pico W (the "
                    "small board on the back), plug it back in, and let go.\n\nThe firmware goes on as soon as it "
                    "shows up (as a drive called RPI-RP2). Waiting for 2 minutes...")
            for _ in range(240):
                time.sleep(0.5)
                drive = unicorn.find_uf2_drive()
                if drive:
                    break
            else:
                raise unicorn.BoardError("The Unicorn didn't show up as an RPI-RP2 drive.")
        time.sleep(1.5)                                  # let the drive settle (mounting)
        with open(path, "rb") as src:
            data = src.read()
        dst = open(os.path.join(drive, "firmware.uf2"), "wb")
        try:
            dst.write(data)
            dst.flush()
            os.fsync(dst.fileno())
        except OSError:
            if dst.tell() < len(data):      # it restarts as soon as the last block lands, so an error after
                raise                       # that is fine; one before it isn't
        finally:
            try:
                dst.close()
            except OSError:
                pass
        for _ in range(80):                              # it restarts into the new firmware by itself
            time.sleep(0.5)
            if unicorn.find_ports():
                time.sleep(2)
                return True
        return True

    # ------------------------------------------------------------ saving

    def save(self):
        if self.busy:
            return
        if self.mode not in ("live", "raw"):
            self.connect()
            return
        s = self.settings
        if not s.get("wifi_name") and not self.wifi_changed and not self.on_wifi:
            if not messagebox.askyesno("No Wi-Fi yet", "The Unicorn isn't set up for Wi-Fi, so it can't get the "
                                                       "time or the weather by itself.\n\nSave anyway? (You can add "
                                                       "Wi-Fi in the \"Wi-Fi & settings\" tab.)"):
                self.tabs.select(self.setup_tab)
                return
        if not s.get("place"):
            if not messagebox.askyesno("No town yet", "Without a town the Unicorn can't show the weather, and it "
                                                      "uses this computer's time zone.\n\nSave anyway?"):
                self.tabs.select(self.setup_tab)
                return
        if self.wifi_changed:
            self.settings["wifi_name"] = self.setup_tab.wifi()[0]
        self.work(self._save, self._saved, "Saving")

    def _save(self):
        b = self.board
        files = board_files()
        if self.live:
            b.enter_raw()
            self.live = False
        self.ui(self.progress.stop)
        self.ui(self.progress.config, {"mode": "determinate", "value": 0})
        s = json.loads(json.dumps(self.settings))
        bright, vol = s.pop("brightness", 30), s.pop("volume", 30)
        s["art"] = [e for e in s["art"] if e["id"] in self.arts]
        mine = {"settings.json": json.dumps(s, separators=(",", ":")).encode(),
                "brightness.txt": str(max(2, min(100, bright)) / 100).encode(),
                "volume.txt": str(max(0, min(100, vol)) / 100).encode()}
        for e in s["art"]:
            a = self.arts[e["id"]]
            mine["art_%s.json" % e["id"]] = json.dumps({k: a[k] for k in ("palette", "frames", "fps", "text",
                                                                          "text_color")},
                                                       separators=(",", ":")).encode()
        if self.my_scenes:
            mine["my_scenes.py"] = self.my_scenes
        elif self.my_scenes == b"":
            b.remove("my_scenes.py")
        if self.wifi_changed:
            ssid, psk = self.setup_tab.wifi()
            mine["secrets.py"] = ("# Written by Unicorn Studio. Your Wi-Fi (the Unicorn only works on 2.4 GHz "
                                  "Wi-Fi), and the key\n# other computers need to change its files over Wi-Fi.\n"
                                  "WIFI = [(%r, %r)]\nKEY = %r\n" % (ssid, psk, secrets.token_hex(8))).encode()
        have = b.hashes(list(files) + list(mine))
        import hashlib
        todo = [(n, d) for n, d in list(mine.items()) + list(files.items())
                if have.get(n) != hashlib.sha256(d).hexdigest()]
        todo.sort(key=lambda nd: nd[0] == "main.py")     # main.py last: it's what starts everything
        total = sum(len(d) for _, d in todo) or 1
        sent = [0]
        for name, data in todo:
            self.ui(self.progress_text.config, {"text": "Copying %s" % name})

            def step(n, base=sent[0]):
                self.ui(self.progress.config, {"value": 100 * (base + n) / total})
            b.put(name, data, step)
            sent[0] += len(data)
        keep = {"art_%s.json" % e["id"] for e in s["art"]}
        for name in b.listdir():
            if name.startswith("art_") and name.endswith(".json") and name not in keep:
                b.remove(name)
        self.ui(self.progress_text.config, {"text": "Restarting the Unicorn"})
        b.reset()
        self.board = None
        time.sleep(4)
        return len(todo)

    def _saved(self, n):
        self.dirty = False
        self.wifi_changed = False
        self.my_scenes = None
        self.setup_tab.load()
        self.note.config(text="Saved. The Unicorn is restarting with your changes.")
        self.after(1500, self.connect)

    def quit_app(self):
        if self.dirty and not messagebox.askyesno("Unicorn Studio", "You have changes that aren't on the Unicorn "
                                                                    "yet. Close anyway?"):
            return
        if self.board:
            if self.mode == "raw" and not self.busy:
                try:
                    self.board.reset()                   # set it going again
                except Exception:
                    pass
            self.board.close()
        self.destroy()


# ================================================================ helpers

class Scrolling(ttk.Frame):
    """A frame that scrolls (for lists of cards)."""

    def __init__(self, parent, bg=PAPER):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(seq, self.wheel, add="+")

    def wheel(self, e):
        w = e.widget
        while w is not None and w is not self.canvas:
            w = getattr(w, "master", None)
        if w is None or not self.winfo_ismapped():
            return
        if e.num == 4 or e.delta > 0:
            self.canvas.yview_scroll(-1 if sys.platform != "darwin" else -max(1, abs(e.delta)), "units")
        else:
            self.canvas.yview_scroll(1 if sys.platform != "darwin" else max(1, abs(e.delta)), "units")


def gif_frames(path):
    frames = []
    while True:
        try:
            frames.append(tk.PhotoImage(file=path, format="gif -index %d" % len(frames)))
        except tk.TclError:
            break
    return frames


class Dialog(tk.Toplevel):
    """A small form: fields is [(key, label, kind, options)], kind: entry | combo | days | check."""

    def __init__(self, parent, title, fields, values):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PAPER, padx=18, pady=14)
        self.transient(parent)
        self.result = None
        self.vars = {}
        for row, (key, label, kind, opts) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 12))
            v = values.get(key)
            if kind == "days":
                box = ttk.Frame(self)
                box.grid(row=row, column=1, sticky="w")
                picks = []
                for i, d in enumerate(DAYS):
                    var = tk.BooleanVar(value=v is None or i in v)
                    ttk.Checkbutton(box, text=d, variable=var).pack(side="left")
                    picks.append(var)
                self.vars[key] = picks
            elif kind == "check":
                var = tk.BooleanVar(value=bool(v))
                ttk.Checkbutton(self, variable=var, text=opts or "").grid(row=row, column=1, sticky="w")
                self.vars[key] = var
            elif kind == "combo":
                var = tk.StringVar(value=v if v is not None else (opts[0] if opts else ""))
                ttk.Combobox(self, textvariable=var, values=opts, width=28).grid(row=row, column=1, sticky="w")
                self.vars[key] = var
            else:
                var = tk.StringVar(value="" if v is None else str(v))
                ttk.Entry(self, textvariable=var, width=32).grid(row=row, column=1, sticky="w")
                if opts:
                    ttk.Label(self, text=opts, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=8)
                self.vars[key] = var
        btns = ttk.Frame(self)
        btns.grid(row=len(fields), column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="OK", style="Accent.TButton", command=self.ok).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.wait_window()

    def ok(self):
        out = {}
        for k, v in self.vars.items():
            out[k] = [i for i, var in enumerate(v) if var.get()] if isinstance(v, list) else v.get()
        self.result = out
        self.destroy()


def parse_hm(s):
    """"7:05 pm" / "19:05" -> "19:05" (or None)."""
    s = s.strip().lower().replace(".", ":")
    pm, am = s.endswith("pm"), s.endswith("am")
    s = s.rstrip("apm ").strip()
    try:
        h, _, m = s.partition(":")
        h, m = int(h), int(m or 0)
    except ValueError:
        return None
    if pm and h < 12:
        h += 12
    if am and h == 12:
        h = 0
    return "%02d:%02d" % (h, m) if 0 <= h < 24 and 0 <= m < 60 else None


def nice_hm(hm):
    h, m = (int(v) for v in hm.split(":"))
    return "%d:%02d %s" % (h % 12 or 12, m, "am" if h < 12 else "pm")


# ================================================================ Scenes

class ScenesTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.tabs, padding=12)
        self.app = app
        self.vars = {}
        self.images = {}
        self.playing = []               # (label, frames) on screen now
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 12))
        ttk.Label(left, text="Categories", style="H.TLabel").pack(anchor="w", pady=(0, 6))
        self.cats = tk.Listbox(left, width=18, height=12, activestyle="none", bd=0, highlightthickness=0,
                               selectbackground=ACCENT, selectforeground="white", font=app.fonts["tab"])
        self.cats.pack(fill="both", expand=True)
        self.cats.bind("<<ListboxSelect>>", lambda e: self.show())
        ttk.Label(left, text="Tick the scenes you'd like.\nSeasonal ones only show\nin their season.",
                  style="Muted.TLabel", justify="left").pack(anchor="w", pady=10)
        row = ttk.Frame(left)
        row.pack(anchor="w")
        ttk.Button(row, text="All on", command=lambda: self.all(True)).pack(side="left")
        ttk.Button(row, text="All off", command=lambda: self.all(False)).pack(side="left", padx=4)
        self.list = Scrolling(self)
        self.list.pack(side="left", fill="both", expand=True)
        cats = self.app.catalog["categories"] + ["My animations"]
        self.cat_names = cats
        for c in cats:
            self.cats.insert("end", "  " + c)
        self.cats.selection_set(0)
        self.after(120, self.tick)

    def load(self):
        off = set(self.app.settings.get("off", []))
        for s in self.app.catalog["scenes"]:
            self.vars.setdefault(s["name"], tk.BooleanVar()).set(s["name"] not in off)
        self.show()

    def all(self, on):
        for s in self.scenes_here():
            self.vars[s["name"]].set(on)
        self.toggled()

    def toggled(self):
        art_ids = {e["id"] for e in self.app.settings.get("art", [])}
        self.app.settings["off"] = sorted([n for n, v in self.vars.items() if not v.get() and
                                           (n in art_ids or any(s["name"] == n for s in self.app.catalog["scenes"]))])
        self.app.changed()

    def scenes_here(self):
        cat = self.cat_names[(self.cats.curselection() or (0,))[0]]
        if cat == "My animations":
            out = []
            for e in self.app.settings.get("art", []):
                w = e.get("when")
                out.append({"name": e["id"], "title": e.get("name", "Untitled"), "art": True,
                            "when": "All year" if not w else "%s %d - %s %d" % (MONTHS[w[0] - 1], w[1],
                                                                                MONTHS[w[2] - 1], w[3]),
                            "about": "One of your own animations."})
                self.vars.setdefault(e["id"], tk.BooleanVar(value=e["id"] not in self.app.settings["off"]))
            return out
        return [s for s in self.app.catalog["scenes"] if s["category"] == cat]

    def show(self):
        for w in self.list.inner.winfo_children():
            w.destroy()
        self.playing = []
        scenes = self.scenes_here()
        if not scenes:
            ttk.Label(self.list.inner, text="Nothing here yet. Draw one in the \"My animations\" tab!",
                      style="Muted.TLabel").pack(pady=30)
        for i, s in enumerate(scenes):
            card = tk.Frame(self.list.inner, bg="white", padx=12, pady=10, highlightthickness=1,
                            highlightbackground="#e4e0ef")
            card.pack(fill="x", padx=6, pady=5)
            if s.get("art"):
                frames = self.app.art_tab.thumbnails(s["name"])
            else:
                if s["name"] not in self.images:
                    path = os.path.join(HERE, "previews", s["name"] + ".gif")
                    self.images[s["name"]] = gif_frames(path) if os.path.exists(path) else []
                frames = self.images[s["name"]]
            pic = tk.Label(card, bg="#121214", image=frames[0] if frames else "", width=212, height=44)
            pic.grid(row=0, column=0, rowspan=3, padx=(0, 14), sticky="n")
            if len(frames) > 1:
                self.playing.append([pic, frames, 0])
            ttk.Label(card, text=s["title"], style="CardH.TLabel").grid(row=0, column=1, sticky="w")
            ttk.Label(card, text=s["when"], style="CardMuted.TLabel").grid(row=1, column=1, sticky="w")
            ttk.Label(card, text=s["about"], style="Card.TLabel", wraplength=280, justify="left").grid(
                row=2, column=1, sticky="nw")
            side = tk.Frame(card, bg="white")
            side.grid(row=0, column=2, rowspan=3, sticky="ne", padx=(10, 0))
            ttk.Checkbutton(side, text="Show this one", style="Card.TCheckbutton", variable=self.vars[s["name"]],
                            command=self.toggled).pack(anchor="w")
            ttk.Button(side, text="Show it now", command=lambda n=s["name"]: self.app.try_it("G " + n)).pack(
                anchor="w", pady=(6, 0))
            card.grid_columnconfigure(1, weight=1)
        self.list.canvas.yview_moveto(0)

    def tick(self):
        for p in self.playing:
            p[2] = (p[2] + 1) % len(p[1])
            try:
                p[0].config(image=p[1][p[2]])
            except tk.TclError:
                pass
        self.after(110, self.tick)


# ================================================================ My animations (a little pixel editor)

class ArtTab(ttk.Frame):
    CELL = 15

    def __init__(self, app):
        super().__init__(app.tabs, padding=12)
        self.app = app
        self.current = None             # id being edited
        self.frame_no = 0
        self.color = 1
        self.tool = tk.StringVar(value="pen")
        self.playing = False
        self.thumbs = {}

        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 14))
        ttk.Label(left, text="Your animations", style="H.TLabel").pack(anchor="w")
        self.names = tk.Listbox(left, width=22, height=14, activestyle="none", bd=0, highlightthickness=0,
                                selectbackground=ACCENT, selectforeground="white")
        self.names.pack(fill="y", expand=True, pady=6)
        self.names.bind("<<ListboxSelect>>", lambda e: self.pick())
        for text, fn in (("New", self.new), ("Copy", self.duplicate), ("Delete", self.delete),
                         ("From a picture...", self.import_picture)):
            ttk.Button(left, text=text, command=fn).pack(fill="x", pady=2)

        self.editor = ttk.Frame(self)
        self.editor.pack(side="left", fill="both", expand=True)
        form = ttk.Frame(self.editor)
        form.pack(fill="x")
        self.name_var = tk.StringVar()
        self.fps_var = tk.DoubleVar(value=4)
        self.text_var = tk.StringVar()
        self.times_var = tk.IntVar(value=1)
        ttk.Label(form, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.name_var, width=22).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Speed (pictures a second)").grid(row=0, column=2, sticky="w", padx=(14, 0))
        ttk.Spinbox(form, from_=0.5, to=30, increment=0.5, textvariable=self.fps_var, width=5).grid(
            row=0, column=3, sticky="w", padx=6)
        ttk.Label(form, text="Words to scroll by").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.text_var, width=40).grid(row=1, column=1, columnspan=2, sticky="w",
                                                                    padx=6)
        self.text_color_btn = tk.Button(form, text="colour", width=6, relief="flat", command=self.pick_text_color)
        self.text_color_btn.grid(row=1, column=3, sticky="w", padx=6)
        when = ttk.Frame(form)
        when.grid(row=2, column=0, columnspan=4, sticky="w")
        self.all_year = tk.BooleanVar(value=True)
        ttk.Checkbutton(when, text="All year", variable=self.all_year, command=self.form_changed).pack(side="left")
        ttk.Label(when, text="   or from").pack(side="left")
        self.from_m, self.from_d, self.to_m, self.to_d = (tk.StringVar(value=v) for v in ("Jan", "1", "Dec", "31"))
        for var, vals, wdt in ((self.from_m, MONTHS, 5), (self.from_d, [str(i) for i in range(1, 32)], 3)):
            ttk.Combobox(when, textvariable=var, values=vals, width=wdt).pack(side="left", padx=2)
        ttk.Label(when, text="to").pack(side="left", padx=4)
        for var, vals, wdt in ((self.to_m, MONTHS, 5), (self.to_d, [str(i) for i in range(1, 32)], 3)):
            ttk.Combobox(when, textvariable=var, values=vals, width=wdt).pack(side="left", padx=2)
        ttk.Label(when, text="   turns per round").pack(side="left")
        ttk.Spinbox(when, from_=1, to=5, textvariable=self.times_var, width=3).pack(side="left", padx=4)
        for v in (self.name_var, self.fps_var, self.text_var, self.times_var, self.from_m, self.from_d, self.to_m,
                  self.to_d):
            v.trace_add("write", lambda *a: self.form_changed())

        self.canvas = tk.Canvas(self.editor, width=W * self.CELL, height=H * self.CELL, bg="#121214",
                                highlightthickness=0)
        self.canvas.pack(anchor="w", pady=10)
        self.cells = [[self.canvas.create_rectangle(x * self.CELL + 1, y * self.CELL + 1, (x + 1) * self.CELL - 1,
                                                    (y + 1) * self.CELL - 1, fill="#202024", outline="")
                       for x in range(W)] for y in range(H)]
        for seq in ("<Button-1>", "<B1-Motion>"):
            self.canvas.bind(seq, lambda e: self.paint(e, False))
        for seq in ("<Button-3>", "<B3-Motion>", "<Button-2>", "<B2-Motion>"):
            self.canvas.bind(seq, lambda e: self.paint(e, True))

        tools = ttk.Frame(self.editor)
        tools.pack(fill="x")
        for t, label in (("pen", "Draw"), ("fill", "Fill"), ("erase", "Erase")):
            ttk.Radiobutton(tools, text=label, value=t, variable=self.tool).pack(side="left", padx=(0, 8))
        ttk.Label(tools, text="(right-click erases)", style="Muted.TLabel").pack(side="left")
        ttk.Button(tools, text="Clear picture", command=self.clear).pack(side="right")
        self.swatches = ttk.Frame(self.editor)
        self.swatches.pack(fill="x", pady=8)
        ttk.Label(self.editor, text="Click a colour to draw with it; double-click one to change it.",
                  style="Muted.TLabel").pack(anchor="w")

        frames = ttk.Frame(self.editor)
        frames.pack(fill="x", pady=10)
        ttk.Button(frames, text="<", width=3, command=lambda: self.go(-1)).pack(side="left")
        self.frame_label = ttk.Label(frames, text="Picture 1 of 1", width=14, anchor="center")
        self.frame_label.pack(side="left")
        ttk.Button(frames, text=">", width=3, command=lambda: self.go(1)).pack(side="left")
        for text, fn in (("Add a picture", self.add_frame), ("Copy this picture", self.copy_frame),
                         ("Remove this picture", self.remove_frame)):
            ttk.Button(frames, text=text, command=fn).pack(side="left", padx=4)
        row = ttk.Frame(self.editor)
        row.pack(fill="x")
        self.play_btn = ttk.Button(row, text="Play", command=self.play)
        self.play_btn.pack(side="left")
        ttk.Button(row, text="Show on the Unicorn",
                   command=lambda: self.current and self.app.try_it("G " + self.current)).pack(side="left", padx=6)
        ttk.Label(row, text="(save first, so the Unicorn has it)", style="Muted.TLabel").pack(side="left")
        self.empty = ttk.Label(self, text="Press \"New\" to draw your own animation.\n\nIt's 53 x 11 pixels: draw a "
                                          "picture, add more pictures to make it move,\nand it joins the carousel "
                                          "with the other scenes.", style="Muted.TLabel", justify="center")
        self.set_enabled(False)

    # -- the list
    def entries(self):
        return self.app.settings.setdefault("art", [])

    def load(self):
        self.names.delete(0, "end")
        for e in self.entries():
            self.names.insert("end", e.get("name") or "Untitled")
        self.thumbs.clear()
        if self.entries():
            self.names.selection_set(0)
            self.pick()
        else:
            self.current = None
            self.set_enabled(False)

    def set_enabled(self, on):
        if on:
            self.empty.place_forget()
            self.editor.pack(side="left", fill="both", expand=True)
        else:
            self.editor.pack_forget()
            self.empty.place(relx=0.6, rely=0.4, anchor="center")

    def entry(self):
        return next((e for e in self.entries() if e["id"] == self.current), None)

    def art(self):
        return self.app.arts.get(self.current)

    def pick(self):
        sel = self.names.curselection()
        if not sel:
            return
        e = self.entries()[sel[0]]
        self.current = e["id"]
        if self.current not in self.app.arts:
            self.app.arts[self.current] = {"palette": [list(c) for c in PALETTE], "frames": [blank_frame()],
                                           "fps": 4, "text": "", "text_color": [255, 255, 255]}
        a = self.art()
        self.loading = True
        self.name_var.set(e.get("name", ""))
        self.fps_var.set(a.get("fps", 4))
        self.text_var.set(a.get("text", ""))
        self.times_var.set(e.get("times", 1))
        w = e.get("when")
        self.all_year.set(not w)
        if w:
            self.from_m.set(MONTHS[w[0] - 1])
            self.from_d.set(str(w[1]))
            self.to_m.set(MONTHS[w[2] - 1])
            self.to_d.set(str(w[3]))
        self.loading = False
        self.text_color_btn.config(bg=hexcolor(a.get("text_color", (255, 255, 255))))
        self.frame_no = 0
        self.set_enabled(True)
        self.draw_swatches()
        self.redraw()

    def new(self, art=None, name="My animation"):
        i = new_id()
        self.entries().append({"id": i, "name": name, "when": None, "times": 1})
        self.app.arts[i] = art or {"palette": [list(c) for c in PALETTE], "frames": [blank_frame()], "fps": 4,
                                   "text": "", "text_color": [255, 255, 255]}
        self.load()
        self.names.selection_clear(0, "end")
        self.names.selection_set("end")
        self.pick()
        self.app.changed()

    def duplicate(self):
        if self.current:
            self.new(json.loads(json.dumps(self.art())), (self.entry().get("name") or "Untitled") + " copy")

    def delete(self):
        e = self.entry()
        if e and messagebox.askyesno("Delete", "Delete \"%s\"?" % e.get("name")):
            self.entries().remove(e)
            self.app.arts.pop(e["id"], None)
            self.load()
            self.app.changed()

    def form_changed(self):
        if getattr(self, "loading", False) or not self.current:
            return
        e, a = self.entry(), self.art()
        e["name"] = self.name_var.get().strip() or "Untitled"
        try:
            a["fps"] = max(0.5, min(30.0, float(self.fps_var.get())))
            e["times"] = max(1, min(5, int(self.times_var.get())))
        except (tk.TclError, ValueError):
            pass
        a["text"] = self.text_var.get()
        if self.all_year.get():
            e["when"] = None
        else:
            try:
                e["when"] = [MONTHS.index(self.from_m.get()) + 1, int(self.from_d.get()),
                             MONTHS.index(self.to_m.get()) + 1, int(self.to_d.get())]
            except ValueError:
                pass
        sel = self.names.curselection()
        if sel and self.names.get(sel[0]) != e["name"]:
            self.names.delete(sel[0])
            self.names.insert(sel[0], e["name"])
            self.names.selection_set(sel[0])
        self.thumbs.pop(self.current, None)
        self.app.changed()

    def pick_text_color(self):
        if not self.current:
            return
        got = colorchooser.askcolor(hexcolor(self.art()["text_color"]), parent=self)[0]
        if got:
            self.art()["text_color"] = [int(v) for v in got]
            self.text_color_btn.config(bg=hexcolor(got))
            self.app.changed()

    # -- colours
    def draw_swatches(self):
        for w in self.swatches.winfo_children():
            w.destroy()
        pal = self.art()["palette"]
        for i, c in enumerate(pal):
            b = tk.Label(self.swatches, bg=hexcolor(c), width=3, height=1, relief="solid" if i == self.color else
                         "flat", bd=3 if i == self.color else 1)
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, i=i: self.choose(i))
            b.bind("<Double-Button-1>", lambda e, i=i: self.recolor(i))
        if len(pal) < len(DIGITS):
            ttk.Button(self.swatches, text="+", width=2, command=self.add_color).pack(side="left", padx=4)

    def choose(self, i):
        self.color = i
        self.tool.set("pen") if self.tool.get() == "erase" else None
        self.draw_swatches()

    def recolor(self, i):
        got = colorchooser.askcolor(hexcolor(self.art()["palette"][i]), parent=self)[0]
        if got:
            self.art()["palette"][i] = [int(v) for v in got]
            self.draw_swatches()
            self.redraw()
            self.app.changed()

    def add_color(self):
        got = colorchooser.askcolor("#ffffff", parent=self)[0]
        if got:
            self.art()["palette"].append([int(v) for v in got])
            self.color = len(self.art()["palette"]) - 1
            self.draw_swatches()
            self.app.changed()

    # -- drawing
    def frames(self):
        return self.art()["frames"]

    def redraw(self):
        a = self.art()
        fr = a["frames"][self.frame_no]
        pal = a["palette"]
        for y in range(H):
            for x in range(W):
                ch = fr[y * W + x]
                self.canvas.itemconfig(self.cells[y][x], fill="#202024" if ch == "." else
                                       hexcolor(pal[DIGITS.index(ch)]) if DIGITS.index(ch) < len(pal) else "#202024")
        self.frame_label.config(text="Picture %d of %d" % (self.frame_no + 1, len(a["frames"])))

    def paint(self, e, erase):
        if not self.current or self.playing:
            return
        x, y = e.x // self.CELL, e.y // self.CELL
        if not (0 <= x < W and 0 <= y < H):
            return
        ch = "." if erase or self.tool.get() == "erase" else DIGITS[self.color]
        fr = list(self.frames()[self.frame_no])
        if self.tool.get() == "fill" and not erase:
            old = fr[y * W + x]
            if old == ch:
                return
            todo = [(x, y)]
            while todo:
                px, py = todo.pop()
                if 0 <= px < W and 0 <= py < H and fr[py * W + px] == old:
                    fr[py * W + px] = ch
                    todo += [(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)]
        else:
            if fr[y * W + x] == ch:
                return
            fr[y * W + x] = ch
        self.frames()[self.frame_no] = "".join(fr)
        self.thumbs.pop(self.current, None)
        self.redraw()
        self.app.changed()

    def clear(self):
        if self.current:
            self.frames()[self.frame_no] = blank_frame()
            self.redraw()
            self.app.changed()

    def go(self, d):
        if self.current:
            self.frame_no = (self.frame_no + d) % len(self.frames())
            self.redraw()

    def add_frame(self):
        if self.current and len(self.frames()) < 24:
            self.frames().insert(self.frame_no + 1, blank_frame())
            self.go(1)
            self.app.changed()

    def copy_frame(self):
        if self.current and len(self.frames()) < 24:
            self.frames().insert(self.frame_no + 1, self.frames()[self.frame_no])
            self.go(1)
            self.app.changed()

    def remove_frame(self):
        if self.current and len(self.frames()) > 1:
            del self.frames()[self.frame_no]
            self.frame_no = min(self.frame_no, len(self.frames()) - 1)
            self.redraw()
            self.app.changed()

    def play(self):
        if not self.current:
            return
        self.playing = not self.playing
        self.play_btn.config(text="Stop" if self.playing else "Play")
        if self.playing:
            self.step()

    def step(self):
        if not self.playing or not self.current:
            return
        self.go(1)
        self.after(int(1000 / max(0.5, self.art().get("fps", 4))), self.step)

    # -- for the Scenes tab
    def thumbnails(self, i):
        if i not in self.thumbs:
            a = self.app.arts.get(i)
            out = []
            for fr in (a["frames"] if a else [])[:24]:
                img = tk.PhotoImage(width=W * 4, height=H * 4)
                rows = []
                for y in range(H):
                    row = []
                    for x in range(W):
                        ch = fr[y * W + x]
                        row += [hexcolor(a["palette"][DIGITS.index(ch)]) if ch != "." else "#202024"] * 4
                    rows += ["{" + " ".join(row) + "}"] * 4
                img.put(" ".join(rows))
                out.append(img)
            fps = a.get("fps", 4) if a else 4
            self.thumbs[i] = [f for f in out for _ in range(max(1, round(9 / fps)))]   # the cards tick at ~9/s
        return self.thumbs[i]

    # -- pictures from files
    def import_picture(self):
        path = filedialog.askopenfilename(title="Choose a picture (PNG or GIF; animated GIFs work too)",
                                          filetypes=[("Pictures", "*.png *.gif"), ("All files", "*.*")])
        if not path:
            return
        imgs = []
        while len(imgs) < 24:
            try:
                fmt = "gif -index %d" % len(imgs) if path.lower().endswith(".gif") else None
                imgs.append(tk.PhotoImage(file=path, format=fmt) if fmt else tk.PhotoImage(file=path))
            except tk.TclError:
                break
            if not path.lower().endswith(".gif"):
                break
        if not imgs:
            messagebox.showerror("Unicorn Studio", "Couldn't read that picture. PNG and GIF pictures work.")
            return
        palette, frames = [], []
        for img in imgs:
            iw, ih = img.width(), img.height()
            scale = min(W / iw, H / ih)
            ow, oh = max(1, round(iw * scale)), max(1, round(ih * scale))
            x0, y0 = (W - ow) // 2, (H - oh) // 2
            fr = ["."] * (W * H)
            for y in range(oh):
                for x in range(ow):
                    sx, sy = min(iw - 1, int((x + 0.5) / scale)), min(ih - 1, int((y + 0.5) / scale))
                    try:
                        if img.transparency_get(sx, sy):
                            continue
                    except (tk.TclError, AttributeError):
                        pass
                    c = img.get(sx, sy)
                    c = tuple(int(v) for v in (c.split() if isinstance(c, str) else c))
                    if sum(c) < 40:
                        continue                         # black is "off" on the Unicorn
                    fr[(y0 + y) * W + x0 + x] = DIGITS[self.nearest(palette, c)]
            frames.append("".join(fr))
        name = os.path.splitext(os.path.basename(path))[0][:20]
        self.new({"palette": palette or [[255, 255, 255]], "frames": frames, "fps": 6 if len(frames) > 1 else 1,
                  "text": "", "text_color": [255, 255, 255]}, name)

    @staticmethod
    def nearest(palette, c):
        """The palette slot for colour c: a close one already there, or a new one (up to 36)."""
        best, dist = 0, 1e9
        for i, p in enumerate(palette):
            d = sum((a - b) ** 2 for a, b in zip(p, c))
            if d < dist:
                best, dist = i, d
        if dist > 900 and len(palette) < len(DIGITS):
            palette.append(list(c))
            return len(palette) - 1
        return best


# ================================================================ Sounds, alarms & timers

class SoundTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.tabs, padding=12)
        self.app = app
        cols = ttk.Frame(self)
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure(0, weight=1, uniform="half")
        cols.grid_columnconfigure(1, weight=1, uniform="half")
        cols.grid_rowconfigure(0, weight=1)
        left = ttk.Frame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = ttk.Frame(cols)
        right.grid(row=0, column=1, sticky="nsew")

        tunes = ttk.LabelFrame(left, text="Tunes", padding=10)
        tunes.pack(fill="both", expand=True)
        self.tune_list = Scrolling(tunes)
        self.tune_list.pack(fill="both", expand=True)
        own = ttk.Frame(tunes)
        own.pack(fill="x", pady=(8, 0))
        ttk.Label(own, text="Make your own: notes like  C5:2 E5:2 G5:4\n(note and octave : beats; a - is a rest)",
                  style="Muted.TLabel", justify="left").pack(anchor="w")
        row = ttk.Frame(own)
        row.pack(fill="x", pady=4)
        self.tune_name = tk.StringVar(value="mytune")
        self.tune_notes = tk.StringVar(value="C5:2 E5:2 G5:2 C6:4")
        ttk.Entry(row, textvariable=self.tune_name, width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.tune_notes, width=18).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(row, text="Try", width=4, command=lambda: self.app.try_it("S " + self.tune_notes.get())).pack(
            side="left")
        ttk.Button(row, text="Add", width=4, command=self.add_tune).pack(side="left", padx=4)
        vol = ttk.Frame(tunes)
        vol.pack(fill="x", pady=(8, 0))
        ttk.Label(vol, text="Volume").pack(side="left")
        self.volume = tk.IntVar(value=30)
        ttk.Scale(vol, from_=0, to=100, variable=self.volume, command=self.volume_moved).pack(
            side="left", fill="x", expand=True, padx=8)
        self.vol_label = ttk.Label(vol, text="30%", width=5)
        self.vol_label.pack(side="left")

        alarms = ttk.LabelFrame(right, text="Alarms", padding=10)
        alarms.pack(fill="both", expand=True)
        self.alarms = ttk.Treeview(alarms, columns=("time", "days", "sound", "text"), show="headings", height=6)
        for c, label, w in (("time", "Time", 70), ("days", "Days", 110), ("sound", "Sound", 70),
                            ("text", "Message", 110)):
            self.alarms.heading(c, text=label)
            self.alarms.column(c, width=w, anchor="w")
        self.alarms.pack(fill="both", expand=True)
        self.alarms.bind("<Double-1>", lambda e: self.edit_alarm())
        row = ttk.Frame(alarms)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Add alarm", command=lambda: self.edit_alarm(new=True)).pack(side="left")
        ttk.Button(row, text="Change", command=self.edit_alarm).pack(side="left", padx=4)
        ttk.Button(row, text="Remove", command=self.remove_alarm).pack(side="left")

        timer = ttk.LabelFrame(right, text="Kitchen timer", padding=10)
        timer.pack(fill="x", pady=(12, 0))
        ttk.Label(timer, text="Counts down on the screen, then rings.", style="Muted.TLabel").pack(anchor="w")
        row = ttk.Frame(timer)
        row.pack(fill="x", pady=(6, 0))
        self.minutes = tk.StringVar(value="10")
        self.timer_name = tk.StringVar(value="Tea")
        ttk.Spinbox(row, from_=1, to=600, textvariable=self.minutes, width=5).pack(side="left")
        ttk.Label(row, text="minutes, called").pack(side="left", padx=6)
        ttk.Entry(row, textvariable=self.timer_name, width=8).pack(side="left")
        ttk.Button(row, text="Start", width=6, command=self.start_timer).pack(side="left", padx=6)
        ttk.Button(row, text="Stop", width=5, command=lambda: self.app.try_it("TIMER 0")).pack(side="left")
        row = ttk.Frame(timer)
        row.pack(fill="x", pady=(8, 0))
        ttk.Label(row, text="Timer sound").pack(side="left")
        self.timer_sound = tk.StringVar()
        self.timer_combo = ttk.Combobox(row, textvariable=self.timer_sound, width=12, state="readonly")
        self.timer_combo.pack(side="left", padx=6)
        self.timer_combo.bind("<<ComboboxSelected>>", lambda e: self.set_timer_sound())

    def tunes(self):
        t = dict(self.app.catalog["tunes"])
        t.update(self.app.settings.get("tunes", {}))
        return t

    def load(self):
        for w in self.tune_list.inner.winfo_children():
            w.destroy()
        mine = self.app.settings.get("tunes", {})
        for name, notes in self.tunes().items():
            row = tk.Frame(self.tune_list.inner, bg=PAPER)
            row.pack(fill="x", pady=2)
            ttk.Button(row, text="Play", width=5, command=lambda n=name: self.app.try_it("S " + n)).pack(side="left")
            ttk.Label(row, text=name, width=10).pack(side="left", padx=8)
            ttk.Label(row, text=notes if len(notes) < 30 else notes[:28] + "...", style="Muted.TLabel").pack(
                side="left")
            if name in mine:
                ttk.Button(row, text="Remove", command=lambda n=name: self.remove_tune(n)).pack(side="right")
        self.volume.set(self.app.settings.get("volume", 30))
        self.vol_label.config(text="%d%%" % self.volume.get())
        self.timer_combo.config(values=list(self.tunes()))
        self.timer_sound.set(self.app.settings.get("timer_sound", "chime"))
        self.alarms.delete(*self.alarms.get_children())
        for i, a in enumerate(self.app.settings.get("alarms", [])):
            days = a.get("days", list(range(7)))
            text = "Every day" if len(days) == 7 else "Weekdays" if days == [0, 1, 2, 3, 4] else \
                "Weekends" if days == [5, 6] else " ".join(DAYS[d] for d in days)
            self.alarms.insert("", "end", iid=str(i), values=(nice_hm(a["time"]), text, a.get("sound", ""),
                                                              a.get("text", "")))

    def volume_moved(self, _):
        v = int(float(self.volume.get()))
        self.vol_label.config(text="%d%%" % v)
        if v != self.app.settings.get("volume"):
            self.app.settings["volume"] = v
            if hasattr(self, "_vol_job"):
                self.after_cancel(self._vol_job)
            self._vol_job = self.after(400, lambda: self.app.try_it("V %d" % v, quiet=True))

    def add_tune(self):
        name = "".join(ch for ch in self.tune_name.get().strip().lower() if ch.isalnum())
        if not name:
            return
        self.app.settings.setdefault("tunes", {})[name] = " ".join(self.tune_notes.get().split())
        self.load()
        self.app.changed()

    def remove_tune(self, name):
        self.app.settings.get("tunes", {}).pop(name, None)
        self.load()
        self.app.changed()

    def set_timer_sound(self):
        self.app.settings["timer_sound"] = self.timer_sound.get()
        self.app.changed()

    def start_timer(self):
        try:
            secs = int(float(self.minutes.get()) * 60)
        except ValueError:
            return
        self.app.try_it("TIMER %d %s" % (secs, self.timer_name.get().strip()))

    def edit_alarm(self, new=False):
        alarms = self.app.settings.setdefault("alarms", [])
        sel = self.alarms.selection()
        if not new and not sel:
            return
        a = {"time": "07:00", "days": list(range(7)), "sound": "chime", "text": ""} if new else alarms[int(sel[0])]
        d = Dialog(self, "Alarm", [("time", "Time", "entry", "like 7:30 am or 19:30"),
                                   ("days", "Days", "days", None),
                                   ("sound", "Sound", "combo", [""] + list(self.tunes())),
                                   ("text", "Message (optional)", "entry", "shown when it goes off")],
                   {**a, "time": nice_hm(a["time"])})
        if not d.result:
            return
        hm = parse_hm(d.result["time"])
        if not hm:
            messagebox.showerror("Alarm", "That time didn't make sense: try something like 7:30 am.")
            return
        a = {"time": hm, "days": d.result["days"] or list(range(7)), "sound": d.result["sound"],
             "text": d.result["text"].strip()}
        if new:
            alarms.append(a)
        else:
            alarms[int(sel[0])] = a
        alarms.sort(key=lambda x: x["time"])
        self.load()
        self.app.changed()

    def remove_alarm(self):
        sel = self.alarms.selection()
        if sel:
            del self.app.settings["alarms"][int(sel[0])]
            self.load()
            self.app.changed()


# ================================================================ Dates & messages

class DatesTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.tabs, padding=12)
        self.app = app
        dates = ttk.LabelFrame(self, text="Your dates: birthdays, anniversaries, trips (with a countdown)",
                               padding=10)
        dates.pack(fill="both", expand=True)
        self.dates = ttk.Treeview(dates, columns=("name", "date", "lead", "icon", "greeting"), show="headings",
                                  height=7)
        for c, label, w in (("name", "Name", 160), ("date", "Date", 110), ("lead", "Countdown", 110),
                            ("icon", "Picture", 80), ("greeting", "On the day", 260)):
            self.dates.heading(c, text=label)
            self.dates.column(c, width=w, anchor="w")
        self.dates.pack(fill="both", expand=True)
        self.dates.bind("<Double-1>", lambda e: self.edit_date())
        row = ttk.Frame(dates)
        row.pack(fill="x", pady=(6, 0))
        ttk.Button(row, text="Add a date", command=lambda: self.edit_date(new=True)).pack(side="left")
        ttk.Button(row, text="Change", command=self.edit_date).pack(side="left", padx=4)
        ttk.Button(row, text="Remove", command=self.remove_date).pack(side="left")

        msgs = ttk.LabelFrame(self, text="Messages (they scroll by between the scenes)", padding=10)
        msgs.pack(fill="both", expand=True, pady=(12, 0))
        self.msgs = tk.Listbox(msgs, height=6, activestyle="none", bd=0, highlightthickness=0,
                               selectbackground=ACCENT, selectforeground="white")
        self.msgs.pack(fill="both", expand=True)
        row = ttk.Frame(msgs)
        row.pack(fill="x", pady=(6, 0))
        self.msg_var = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.msg_var, width=50)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.add_msg())
        ttk.Button(row, text="Add", command=self.add_msg).pack(side="left", padx=4)
        ttk.Button(row, text="Remove", command=self.remove_msg).pack(side="left")
        ttk.Button(row, text="Show it now", command=self.show_msg).pack(side="left", padx=4)

    def load(self):
        self.dates.delete(*self.dates.get_children())
        for i, d in enumerate(self.app.settings.get("dates", [])):
            p = d["date"].split("-")
            when = "%s %d" % (MONTHS[int(p[-2]) - 1], int(p[-1])) + (", " + p[0] if len(p) == 3 else " every year")
            lead = int(d.get("lead", 0))
            self.dates.insert("", "end", iid=str(i), values=(d["name"], when, "%d days before" % lead if lead
                                                             else "on the day", d.get("icon", "star"),
                                                             d.get("greeting") or d["name"] + "!"))
        self.msgs.delete(0, "end")
        for m in self.app.settings.get("messages", []):
            self.msgs.insert("end", m)

    def edit_date(self, new=False):
        dates = self.app.settings.setdefault("dates", [])
        sel = self.dates.selection()
        if not new and not sel:
            return
        d = {"name": "", "date": "", "lead": 14, "icon": "heart", "greeting": ""} if new else dict(dates[int(sel[0])])
        if d["date"]:
            p = d["date"].split("-")
            d["month"], d["day"], d["year"] = MONTHS[int(p[-2]) - 1], p[-1], p[0] if len(p) == 3 else ""
        dlg = Dialog(self, "A date", [("name", "Name", "entry", "e.g. Mom's birthday"),
                                      ("month", "Month", "combo", MONTHS),
                                      ("day", "Day", "entry", "1-31"),
                                      ("year", "Year (only once)", "entry", "leave empty for every year"),
                                      ("lead", "Count down from", "entry", "days before (0 = just on the day)"),
                                      ("icon", "Picture", "combo", self.app.catalog["icons"]),
                                      ("greeting", "On the day", "entry", "e.g. Happy birthday Mom!")], d)
        r = dlg.result
        if not r:
            return
        try:
            m, day = MONTHS.index(r["month"]) + 1, int(r["day"])
            year = int(r["year"]) if r["year"].strip() else None
            lead = max(0, min(366, int(r["lead"] or 0)))
            assert r["name"].strip() and 1 <= day <= 31
        except (ValueError, AssertionError):
            messagebox.showerror("A date", "Please fill in a name, a month and a day.")
            return
        out = {"name": r["name"].strip(), "date": ("%d-%02d-%02d" % (year, m, day)) if year else "%02d-%02d" % (m, day),
               "lead": lead, "icon": r["icon"], "greeting": r["greeting"].strip()}
        if new:
            dates.append(out)
        else:
            dates[int(sel[0])] = out
        self.load()
        self.app.changed()

    def remove_date(self):
        sel = self.dates.selection()
        if sel:
            del self.app.settings["dates"][int(sel[0])]
            self.load()
            self.app.changed()

    def add_msg(self):
        m = self.msg_var.get().strip()
        if m:
            self.app.settings.setdefault("messages", []).append(m)
            self.msg_var.set("")
            self.load()
            self.app.changed()

    def remove_msg(self):
        sel = self.msgs.curselection()
        if sel:
            del self.app.settings["messages"][sel[0]]
            self.load()
            self.app.changed()

    def show_msg(self):
        sel = self.msgs.curselection()
        text = self.msgs.get(sel[0]) if sel else self.msg_var.get().strip()
        if text:
            self.app.try_it(["M " + text, "G Note"])


# ================================================================ Wi-Fi & settings

class SetupTab(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.tabs, padding=12)
        self.app = app
        cols = ttk.Frame(self)
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure(0, weight=1, uniform="half")
        cols.grid_columnconfigure(1, weight=1, uniform="half")
        cols.grid_rowconfigure(0, weight=1)
        left = ttk.Frame(cols)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = ttk.Frame(cols)
        right.grid(row=0, column=1, sticky="nsew")

        wifi = ttk.LabelFrame(left, text="Wi-Fi", padding=12)
        wifi.pack(fill="x")
        ttk.Label(wifi, text="The Unicorn uses Wi-Fi for the time, the weather and the speaker. It works with "
                             "2.4 GHz Wi-Fi (most home routers have it).", wraplength=380, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.ssid = tk.StringVar()
        self.psk = tk.StringVar()
        self.show = tk.BooleanVar()
        ttk.Label(wifi, text="Network name").grid(row=1, column=0, sticky="w")
        ttk.Entry(wifi, textvariable=self.ssid, width=24).grid(row=1, column=1, sticky="w", padx=8, pady=3)
        ttk.Label(wifi, text="Password").grid(row=2, column=0, sticky="w")
        self.psk_entry = ttk.Entry(wifi, textvariable=self.psk, width=24, show="*")
        self.psk_entry.grid(row=2, column=1, sticky="w", padx=8, pady=3)
        ttk.Checkbutton(wifi, text="Show", variable=self.show, command=lambda: self.psk_entry.config(
            show="" if self.show.get() else "*")).grid(row=2, column=2, sticky="w")
        ttk.Button(wifi, text="Use this computer's Wi-Fi", command=self.use_mine).grid(
            row=3, column=1, sticky="w", padx=8, pady=(6, 0))
        self.wifi_note = ttk.Label(wifi, text="", style="Muted.TLabel", wraplength=380, justify="left")
        self.wifi_note.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        for v in (self.ssid, self.psk):
            v.trace_add("write", lambda *a: self.wifi_edited())

        place = ttk.LabelFrame(left, text="Your town (for the weather and the time zone)", padding=12)
        place.pack(fill="x", pady=(12, 0))
        self.search = tk.StringVar()
        row = ttk.Frame(place)
        row.pack(fill="x")
        e = ttk.Entry(row, textvariable=self.search, width=28)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: self.find_place())
        ttk.Button(row, text="Find", command=self.find_place).pack(side="left", padx=6)
        self.results = ttk.Combobox(place, state="readonly", width=46)
        self.results.pack(anchor="w", pady=6)
        self.results.bind("<<ComboboxSelected>>", lambda e: self.chose_place())
        self.place_label = ttk.Label(place, text="", style="Muted.TLabel")
        self.place_label.pack(anchor="w")
        units = ttk.Frame(place)
        units.pack(anchor="w", pady=(6, 0))
        self.units = tk.StringVar(value="fahrenheit")
        ttk.Radiobutton(units, text="Fahrenheit", value="fahrenheit", variable=self.units,
                        command=self.units_changed).pack(side="left")
        ttk.Radiobutton(units, text="Celsius", value="celsius", variable=self.units,
                        command=self.units_changed).pack(side="left", padx=10)

        disp = ttk.LabelFrame(right, text="The screen", padding=12)
        disp.pack(fill="x")
        ttk.Label(disp, text="Brightness").grid(row=0, column=0, sticky="w")
        self.bright = tk.IntVar(value=30)
        ttk.Scale(disp, from_=2, to=100, variable=self.bright, length=220, command=self.bright_moved).grid(
            row=0, column=1, sticky="w", padx=8)
        self.bright_label = ttk.Label(disp, text="30%", width=5)
        self.bright_label.grid(row=0, column=2, sticky="w")
        self.h24 = tk.BooleanVar()
        ttk.Checkbutton(disp, text="24-hour clock", variable=self.h24, command=self.other_changed).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=6)
        self.sleep_on = tk.BooleanVar()
        self.sleep_from, self.sleep_to = tk.StringVar(value="11:00 pm"), tk.StringVar(value="7:00 am")
        row = ttk.Frame(disp)
        row.grid(row=2, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(row, text="Screen off at night, from", variable=self.sleep_on,
                        command=self.other_changed).pack(side="left")
        for i, v in enumerate((self.sleep_from, self.sleep_to)):
            if i:
                ttk.Label(row, text="to").pack(side="left", padx=4)
            e = ttk.Entry(row, textvariable=v, width=9)
            e.pack(side="left", padx=4)
            e.bind("<FocusOut>", lambda ev: self.other_changed())
        ttk.Label(disp, text="Alarms and timers still show and ring while it's off.", style="Muted.TLabel").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        code = ttk.LabelFrame(right, text="Your own Python scenes (for programmers)", padding=12)
        code.pack(fill="x", pady=(12, 0))
        ttk.Label(code, text="Write scenes in Python in a my_scenes.py file (see my_scenes_example.py) and add it "
                             "here.", wraplength=380, justify="left").pack(anchor="w")
        row = ttk.Frame(code)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="Add my_scenes.py...", command=self.add_code).pack(side="left")
        ttk.Button(row, text="Take it off", command=self.remove_code).pack(side="left", padx=6)
        self.code_note = ttk.Label(code, text="", style="Muted.TLabel")
        self.code_note.pack(anchor="w")

        about = ttk.LabelFrame(right, text="About", padding=12)
        about.pack(fill="x", pady=(12, 0))
        ttk.Label(about, text="Unicorn Studio %s. Buttons on the Unicorn: A next scene, B weather, C clock, D hold "
                              "this scene, LUX +/- brightness, SLEEP screen on/off, VOL +/- volume.\n\nUnplug any "
                              "time after saving: the Unicorn keeps going on its own from any USB power. Plug it back "
                              "in here whenever you want to change things." % VERSION,
                  wraplength=380, justify="left").pack(anchor="w")

    def load(self):
        s = self.app.settings
        self.loading = True
        self.ssid.set(s.get("wifi_name", ""))
        self.psk.set("")
        self.wifi_note.config(text="Already set up for \"%s\". Leave the password empty to keep it." %
                              s["wifi_name"] if s.get("wifi_name") else "")
        p = s.get("place")
        self.place_label.config(text="Weather for %s" % p["name"] if p else "No town chosen yet.")
        self.units.set((p or {}).get("units", "fahrenheit"))
        self.bright.set(s.get("brightness", 30))
        self.bright_label.config(text="%d%%" % self.bright.get())
        self.h24.set(bool(s.get("24h")))
        sl = s.get("sleep")
        self.sleep_on.set(bool(sl))
        if sl:
            self.sleep_from.set(nice_hm(sl[0]))
            self.sleep_to.set(nice_hm(sl[1]))
        self.loading = False

    def add_code(self):
        path = filedialog.askopenfilename(title="Choose your my_scenes.py", filetypes=[("Python", "*.py")])
        if not path:
            return
        with open(path, "rb") as f:
            data = f.read()
        try:
            compile(data, "my_scenes.py", "exec")
        except SyntaxError as e:
            messagebox.showerror("my_scenes.py", "That file has a mistake on line %s: %s" % (e.lineno, e.msg))
            return
        self.app.my_scenes = data
        self.code_note.config(text="%s goes on when you save." % os.path.basename(path))
        self.app.changed()

    def remove_code(self):
        self.app.my_scenes = b""
        self.code_note.config(text="my_scenes.py comes off when you save.")
        self.app.changed()

    def wifi_edited(self):
        if getattr(self, "loading", False):
            return
        if self.psk.get() or self.ssid.get() != self.app.settings.get("wifi_name", ""):
            self.app.wifi_changed = bool(self.ssid.get().strip())
            self.app.changed()

    def wifi(self):
        return self.ssid.get().strip(), self.psk.get()

    def use_mine(self):
        self.wifi_note.config(text="Looking at this computer's Wi-Fi...")

        def run():
            ssid = wifi_info.current_network()
            self.app.ui(self.got_network, ssid)
            if ssid:
                self.app.ui(self.got_password, ssid, wifi_info.saved_password(ssid))
        threading.Thread(target=run, daemon=True).start()

    def got_network(self, ssid):
        if not ssid:
            self.wifi_note.config(text="")
            messagebox.showinfo("Wi-Fi", "Couldn't tell which Wi-Fi this computer is on (it may be on a cable). "
                                         "Please type the network name and password in.")
            return
        self.ssid.set(ssid)
        self.wifi_note.config(text="Reading the saved password for \"%s\"... (your computer may ask you first)" % ssid)

    def got_password(self, ssid, psk):
        if psk:
            self.psk.set(psk)
            self.wifi_note.config(text="Using \"%s\" with this computer's saved password. It only goes onto the "
                                       "Unicorn, over the cable." % ssid)
        else:
            self.wifi_note.config(text="Using \"%s\". Couldn't read its saved password here, so please type it in."
                                       % ssid)
            self.psk_entry.focus_set()

    def find_place(self):
        q = self.search.get().strip()
        if not q:
            return
        self.place_label.config(text="Looking...")

        def run():
            try:
                hits = fetch_json("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
                    {"name": q.split(",")[0].strip(), "count": 10})).get("results") or []
            except Exception as e:
                hits = e
            self.app.ui(self.got_places, hits)
        threading.Thread(target=run, daemon=True).start()

    def got_places(self, hits):
        if isinstance(hits, Exception):
            self.place_label.config(text="Couldn't search (is this computer online?)")
            return
        if not hits:
            self.place_label.config(text="No town by that name found. Try just the town's name.")
            return
        self.hits = hits
        self.results.config(values=[", ".join(v for v in (h.get("name"), h.get("admin1"), h.get("country")) if v)
                                    for h in hits])
        self.results.current(0)
        self.chose_place()

    def chose_place(self):
        h = self.hits[self.results.current()]
        units = "fahrenheit" if h.get("country_code") in ("US", "LR", "MM") else "celsius"
        self.units.set(units)
        self.app.settings["place"] = {"name": h["name"], "lat": round(h["latitude"], 3),
                                      "lon": round(h["longitude"], 3), "units": units}
        self.place_label.config(text="Weather for %s" % self.results.get())
        self.app.changed()

    def units_changed(self):
        if self.app.settings.get("place"):
            self.app.settings["place"]["units"] = self.units.get()
            self.app.changed()

    def bright_moved(self, _):
        v = int(float(self.bright.get()))
        self.bright_label.config(text="%d%%" % v)
        if v != self.app.settings.get("brightness"):
            self.app.settings["brightness"] = v
            if hasattr(self, "_job"):
                self.after_cancel(self._job)
            self._job = self.after(300, lambda: self.app.try_it("B %d" % v, quiet=True))

    def other_changed(self):
        if getattr(self, "loading", False):
            return
        s = self.app.settings
        s["24h"] = self.h24.get()
        if self.sleep_on.get():
            a, b = parse_hm(self.sleep_from.get()), parse_hm(self.sleep_to.get())
            if a and b:
                s["sleep"] = [a, b]
            else:
                messagebox.showerror("Unicorn Studio", "The night-time hours didn't make sense: try 11:00 pm and "
                                                       "7:00 am.")
                return
        else:
            s["sleep"] = None
        self.app.changed()


def main():
    app = Studio()
    app.mainloop()


if __name__ == "__main__":
    main()
