# Copied to the Unicorn as carousel.py. The real carousel (carousel.py here on the Pi) is too big for the
# Unicorn to compile itself any more, so install.sh compiles it ahead of time into carousel_app.mpy.
import audioring          # first, while memory is in one piece (the speaker's sound buffer)
from carousel_app import *
from carousel_app import run
