"""The Wi-Fi this computer is on, so the Unicorn can join the same one.

Only ever read when you press "Use this computer's Wi-Fi"; it goes onto the Unicorn over the USB cable and nowhere
else. The password often can't be read without asking (macOS shows a keychain prompt; Windows and Linux may need
an administrator), in which case you type it in.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile


def _encoding():
    if sys.platform == "win32":                                 # netsh writes in the console's code page
        try:
            import ctypes
            return "cp%d" % ctypes.windll.kernel32.GetOEMCP()
        except Exception:
            pass
    return "utf-8"


def _run(*cmd, timeout=20):
    flags = 0x08000000 if sys.platform == "win32" else 0         # no console window popping up on Windows
    try:
        r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=timeout, creationflags=flags)
        return r.stdout.decode(_encoding(), "replace") if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, LookupError):
        return ""


def current_network():
    """The name (SSID) of the Wi-Fi network this computer is connected to, or ""."""
    if sys.platform == "win32":
        m = re.search(r"^\s*SSID\s*:\s*(.+?)\s*$", _run("netsh", "wlan", "show", "interfaces"), re.M)
        return m.group(1) if m else ""
    if sys.platform == "darwin":
        out = _run("networksetup", "-getairportnetwork", "en0")
        if ":" in out and "not associated" not in out:
            return out.split(":", 1)[1].strip()
        m = re.search(r"^\s*SSID : (.+)$", _run("ipconfig", "getsummary", "en0"), re.M)
        return m.group(1).strip() if m and m.group(1).strip() != "<redacted>" else ""
    for line in _run("nmcli", "-t", "-f", "active,ssid", "dev", "wifi").splitlines():
        if line.startswith("yes:"):
            return line[4:].replace("\\:", ":")
    return _run("iwgetid", "-r").strip()


def saved_password(ssid):
    """The saved password for that network, or "" if it can't be read."""
    if not ssid:
        return ""
    if sys.platform == "win32":
        # exported as XML: the same words in every language of Windows (unlike "Key Content"), and in UTF-8
        folder = tempfile.mkdtemp()
        try:
            _run("netsh", "wlan", "export", "profile", "name=" + ssid, "key=clear", "folder=" + folder)
            for path in glob.glob(os.path.join(folder, "*.xml")):
                with open(path, encoding="utf-8", errors="replace") as f:
                    m = re.search(r"<keyMaterial>(.*?)</keyMaterial>", f.read(), re.S)
                if m:
                    return m.group(1).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">") \
                        .replace("&quot;", '"').replace("&apos;", "'")
            return ""
        finally:
            shutil.rmtree(folder, ignore_errors=True)               # it has the password in it
    if sys.platform == "darwin":
        return _run("security", "find-generic-password", "-D", "AirPort network password", "-a", ssid, "-w",
                    timeout=120).strip()
    names = [ssid] + [line.rsplit(":", 1)[0] for line in _run("nmcli", "-t", "-f", "NAME,TYPE", "connection", "show",
                                                              "--active").splitlines() if line.endswith(":802-11-wireless")]
    for name in names:
        out = _run("nmcli", "-s", "-g", "802-11-wireless.ssid,802-11-wireless-security.psk", "connection", "show",
                   name).splitlines()
        if len(out) == 2 and out[0] == ssid and out[1]:
            return out[1]
    return ""
