#!/bin/bash
# Build Pimoroni's galactic_unicorn MicroPython v1.21.0 (with our audio-streaming addition) -> galactic_unicorn.uf2
set -e -o pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HERE/toolchain/bin:$PATH"
PP="$HERE/pimoroni-pico"
cd "$PP" && git submodule update --init -q --depth 1
cd "$HERE/micropython"
git apply --check "$PP/micropython/micropython_nano_specs.patch" 2>/dev/null && git apply "$PP/micropython/micropython_nano_specs.patch"
make -s -C mpy-cross -j4
cd ports/rp2
cmake -S . -B build-galactic -DPICO_BUILD_DOCS=0 \
    -DUSER_C_MODULES="$PP/micropython/modules/micropython-galactic_unicorn.cmake" \
    -DMICROPY_BOARD_DIR="$PP/micropython/board/RPI_PICO_W" -DMICROPY_BOARD=RPI_PICO_W \
    -DMICROPY_GIT_TAG="v1.21.0, galactic_unicorn v1.21.0+stream" -DMICROPY_GIT_HASH="v1.21.0-stream" >/dev/null
cmake --build build-galactic -j4 2>&1 | { grep -E "error|Error" || true; } | head -40
cp build-galactic/firmware.uf2 "$HERE/galactic_unicorn.uf2" && ls -la "$HERE/galactic_unicorn.uf2"
