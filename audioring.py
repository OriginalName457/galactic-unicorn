# The sound buffer for the Pi's speaker stream (see Stream in carousel.py). Grabbed first thing at start-up,
# while the Unicorn's memory is still in one piece: later on there's plenty free but only in small bits.
# The DMA's ring mode needs it aligned to its own size, so this takes twice that and uses the aligned half.
import machine
crumbs = [machine.mem32[0x4005800c + 4 * i] for i in range(4)]  # where it was (see crumb() in carousel.py)
froze = machine.reset_cause() == machine.WDT_RESET and crumbs[0] != 99 and crumbs[1] != 0   # the watchdog had to restart us
for i in range(4):
    machine.mem32[0x4005800c + 4 * i] = 0

BITS = 13                   # 8 KB = 4096 samples = 186 ms of sound
SIZE = 1 << BITS
try:
    raw = bytearray(2 * SIZE)
except MemoryError:
    raw = None
