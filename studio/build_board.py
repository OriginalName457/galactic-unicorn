"""Gathers the files that go onto the Unicorn into studio/board_files/, compiling the big ones ahead of time (.mpy:
the Unicorn hasn't the memory to compile them itself). Unicorn Studio runs this by itself when you start it from
the source; the downloadable apps come with the files already made.

  python3 studio/build_board.py         (needs: pip install mpy-cross==1.21.0)
"""
import json
import os
import shutil
import subprocess
import sys

STUDIO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(STUDIO)
OUT = os.path.join(STUDIO, "board_files")

COMPILED = {"carousel_app.mpy": "carousel.py", "online.mpy": "online.py", "winter.mpy": "winter.py",
            "spring.mpy": "spring.py", "summer.mpy": "summer.py", "fall.mpy": "fall.py"}
COPIED = {"carousel.py": "carousel_stub.py", "main.py": "main.py", "net.py": "net.py", "audioring.py": "audioring.py"}


def mpy_cross():
    try:
        import mpy_cross as m
        return [m.mpy_cross]
    except ImportError:
        found = shutil.which("mpy-cross")
        if found:
            return [found]
    sys.exit("Needs mpy-cross 1.21: pip install mpy-cross==1.21.0")


def words():
    """kotoba/words.tsv (kanji, kana, romaji, meaning) -> "romaji<TAB>meaning" lines, all the Unicorn can show."""
    out = []
    with open(os.path.join(ROOT, "kotoba", "words.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                cols = line.rstrip("\n").split("\t")
                if len(cols) >= 4:
                    out.append(cols[2] + "\t" + cols[3])
    return "\n".join(out) + "\n"


def build():
    os.makedirs(OUT, exist_ok=True)
    tool = mpy_cross()
    for dest, src in COMPILED.items():
        subprocess.run(tool + ["-o", os.path.join(OUT, dest), src], check=True, cwd=ROOT)    # (just the name in
                                                                                            # error messages)
    for dest, src in COPIED.items():
        shutil.copyfile(os.path.join(ROOT, src), os.path.join(OUT, dest))
    with open(os.path.join(OUT, "words.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(words())
    files = sorted(COMPILED) + sorted(COPIED) + ["words.txt"]
    files.remove("main.py")
    files.append("main.py")                     # last: it's what starts everything
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump({"files": files}, f, indent=1)
    return OUT


if __name__ == "__main__":
    print("Made", build())
