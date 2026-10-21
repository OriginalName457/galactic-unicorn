#!/bin/bash
# Put the carousel on the Galactic Unicorn and set up clock syncing on the Pi.
#
# Over Wi-Fi (normal):  ./install.sh            copies carousel.py, net.py, the season scenes and main.py, then restarts it
# Over USB (first time, or if Wi-Fi is broken):  ./install.sh --usb   (needs a data cable)
set -e
cd "$(dirname "$0")"
# The carousel and season scenes are compiled here first (.mpy): they're too big for the Unicorn to compile itself.
# carousel.py on the Unicorn is just carousel_stub.py, which loads carousel_app.mpy.
SEASONS="winter spring summer fall"
MPY=$(command -v mpy-cross || echo ~/.local/bin/mpy-cross)     # must be mpy-cross 1.21 (pip install mpy-cross==1.21.0)
mkdir -p build
$MPY -o build/carousel_app.mpy carousel.py
for s in $SEASONS; do $MPY -o build/$s.mpy $s.py; done
cp carousel_stub.py build/carousel.py
FILES="net.py build/carousel_app.mpy $(for s in $SEASONS; do echo build/$s.mpy; done) build/carousel.py main.py"
# (secrets.py, the Wi-Fi passwords, only needs copying once, over USB)

if [ "$1" = "--usb" ]; then
    MP=$(command -v mpremote || echo ~/.local/bin/mpremote)
    sudo systemctl stop unicorn-sync 2>/dev/null || true
    for f in secrets.py $FILES; do $MP cp "$f" ":$(basename "$f")"; done     # main.py last: it starts everything
    $MP reset || true
else
    for f in $FILES; do python3 unicorn.py push "$f"; done
    python3 unicorn.py reset
fi
echo "Copied to the Unicorn."

# the Pi's helpers: clock sync, weather every 20 minutes, Japanese words each day (paths and user filled in here)
service() { sed "s#/home/pi/galactic-unicorn#$PWD#; s/^User=pi/User=$USER/" "$1" | sudo tee /etc/systemd/system/$(basename "$1") >/dev/null; }
for f in unicorn-sync.service weather/weather.service weather/weather.timer kotoba/kotoba.service kotoba/kotoba.timer; do service $f; done
sudo systemctl daemon-reload
sudo systemctl enable unicorn-sync.service weather.timer kotoba.timer
sudo systemctl restart unicorn-sync.service weather.timer kotoba.timer
sleep 12
python3 unicorn.py time && echo "Clock synced. Enjoy :)"
