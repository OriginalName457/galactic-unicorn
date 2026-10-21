#!/bin/bash
# Everything needed to build the Galactic Unicorn's MicroPython firmware with Wi-Fi audio streaming added.
set -e
cd "$(dirname "$0")"
[ -d toolchain ] || { curl -sL -o tc.tar.xz "https://developer.arm.com/-/media/Files/downloads/gnu/13.2.rel1/binrel/arm-gnu-toolchain-13.2.rel1-aarch64-arm-none-eabi.tar.xz" && mkdir toolchain && tar -xf tc.tar.xz -C toolchain --strip-components=1 && rm tc.tar.xz; }
[ -d pimoroni-pico ] || git clone -q https://github.com/pimoroni/pimoroni-pico.git
[ -d micropython ] || git clone -q --branch v1.21.0 --depth 1 https://github.com/micropython/micropython.git
[ -d pico-sdk ] || git clone -q --branch 1.5.1 --depth 1 https://github.com/raspberrypi/pico-sdk.git
(cd pico-sdk && git submodule update --init -q --depth 1)
(cd micropython && git submodule update --init -q --depth 1 lib/pico-sdk lib/tinyusb lib/mbedtls lib/micropython-lib lib/cyw43-driver lib/lwip lib/btstack 2>/dev/null || true)
echo fetched
