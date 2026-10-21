#!/bin/bash
# Put new firmware on the Galactic Unicorn. Needs a USB *data* cable from the Pi to the Unicorn.
#   ./flash.sh                      the firmware with Wi-Fi audio streaming (galactic_unicorn.uf2, from build.sh)
#   ./flash.sh original             back to Pimoroni's stock v1.21.0 (download it from their releases page first)
# The Unicorn's files (the carousel, settings, Wi-Fi) are kept: firmware and files live in separate parts of flash.
set -e
cd "$(dirname "$0")"
UF2=galactic_unicorn.uf2                                      # from build.sh
[ "$1" = "original" ] && UF2=pimoroni-galactic_unicorn-v1.21.0-micropython.uf2
find_drive() { lsblk -rno NAME,LABEL | awk '$2=="RPI-RP2"{print "/dev/"$1}' | head -1; }
DEV=$(find_drive)
if [ -z "$DEV" ]; then
    echo "Asking the Unicorn to get ready for new firmware..."
    printf 'def run(gu):\n    import machine, time\n    gu.stop_playing()\n    time.sleep_ms(200)\n    machine.bootloader()\n' > /tmp/bootsel.py
    python3 ../unicorn.py push /tmp/bootsel.py >/dev/null
    python3 -c "import sys; sys.path.insert(0, '..'); import unicorn; unicorn.talk(unicorn.known_host(), 'X bootsel', timeout=3)" 2>/dev/null || true
    for i in $(seq 20); do sleep 1; DEV=$(find_drive); [ -n "$DEV" ] && break; done
fi
if [ -z "$DEV" ]; then
    echo "The Unicorn didn't show up as a USB drive. Is it connected to the Pi with a data cable?"
    echo "(Or: hold the BOOTSEL button on the back of the Unicorn while plugging it in, then run this again.)"
    exit 1
fi
MNT=$(lsblk -rno MOUNTPOINT "$DEV")
[ -z "$MNT" ] && MNT=$(udisksctl mount -b "$DEV" | sed -n 's/.* at \(.*\)\.\?$/\1/p' | sed 's/\.$//')
echo "Copying $UF2 to $MNT ..."
cp "$UF2" "$MNT/" && sync
echo "Done. The Unicorn restarts by itself in a few seconds."
