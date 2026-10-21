# Copy this to secrets.py, fill in your Wi-Fi, and copy it onto the Unicorn once over USB (./install.sh --usb).
# secrets.py is never committed (see .gitignore).
WIFI = [
    ("your-network", "your-password"),      # tried in order; add more networks if you like
]
# Optional: a password for changing the Unicorn's files over Wi-Fi (PUT, RESET and X). With one set, the Pi tools
# here send it for you (they read it from this file). Unicorn Studio makes one by itself.
# KEY = "make-up-something-long"
