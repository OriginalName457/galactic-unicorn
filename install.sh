#!/bin/bash
# Put the carousel on the Galactic Unicorn and set up clock syncing on the Pi.
#
# (Most people use Unicorn Studio instead: studio/. This is the way for a Raspberry Pi that looks after the Unicorn.)
#
# Over Wi-Fi (normal):  ./install.sh            copies the carousel, the season scenes and main.py, then restarts it
# Over USB (first time, or if Wi-Fi is broken):  ./install.sh --usb   (needs a data cable)
set -e
cd "$(dirname "$0")"
# The files for the Unicorn are gathered (and the big ones compiled: the Unicorn can't compile them itself) by
# studio/build_board.py, the same as Unicorn Studio uses. Needs mpy-cross 1.21 (pip install mpy-cross==1.21.0).
python3 studio/build_board.py >/dev/null
FILES=$(python3 -c "import json; print(' '.join('studio/board_files/' + f for f in json.load(open('studio/board_files/manifest.json'))['files']))")
[ -f my_scenes.py ] && FILES="my_scenes.py $FILES"     # your own scenes, if you've made some (my_scenes_example.py)
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
