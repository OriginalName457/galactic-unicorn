#!/usr/bin/env python3
"""Japanese vocabulary for the Galactic Unicorn: 10 new words each day from words.tsv.

Works through the whole library in a shuffled order, then reshuffles and goes round again, so every
word keeps coming back. Each word goes to the Unicorn (over Wi-Fi, as kotoba.json) as its romaji and a
short meaning, which it shows as a flashcard: the word on the front, the meaning on the back, each in the
biggest font that fits (so keep both short). The kanji and kana stay in words.tsv for reference: kanji is too
small to read on the Unicorn's 11 rows.

  kotoba.py           send today's words (picks them the first time it runs each day)
  kotoba.py today     print today's list
"""
import datetime
import json
import os
import random
import subprocess
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
WORDS = os.path.join(HERE, "words.tsv")
STATE = os.path.join(HERE, "progress.json")
OUT = os.path.join(HERE, "kotoba.json")
UNICORN = os.path.join(os.path.dirname(HERE), "unicorn.py")
PER_DAY = 10


def load_words():
    with open(WORDS, encoding="utf-8") as f:
        rows = [l.rstrip("\n").split("\t") for l in f if l.strip() and not l.startswith("#")]
    return [dict(kanji=r[0], kana=r[1], romaji=r[2], meaning=r[3]) for r in rows]


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"order": [], "pos": 0, "day": None, "today": [], "round": 0, "sent": None}


def save_state(st):
    with open(STATE + ".tmp", "w") as f:
        json.dump(st, f)
    os.replace(STATE + ".tmp", STATE)


def todays_words(words, st):
    """The same 10 all day; a new 10 the first time this runs on a new day."""
    today = datetime.date.today().isoformat()
    if st["day"] != today:
        picks = []
        while len(picks) < PER_DAY:
            if st["pos"] >= len(st["order"]) or len(st["order"]) != len(words):
                st["order"] = list(range(len(words)))
                random.shuffle(st["order"])
                st["pos"] = 0
                st["round"] += 1
            picks.append(st["order"][st["pos"]])
            st["pos"] += 1
        st["day"], st["today"] = today, picks
        save_state(st)
    return [words[i] for i in st["today"] if i < len(words)]


def build(words):
    return {"day": datetime.date.today().isoformat(),
            "words": [{"w": w["romaji"], "m": w["meaning"]} for w in words]}


def main():
    words = load_words()
    st = load_state()
    todays = todays_words(words, st)
    if "today" in sys.argv:
        print("Round %d, words %d-%d of %d:" % (st["round"], st["pos"] - PER_DAY + 1, st["pos"], len(words)))
        for w in todays:
            print("  %s (%s) %s - %s" % (w["kanji"], w["kana"], w["romaji"], w["meaning"]))
        return
    data = build(todays)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    if st.get("sent") == data["day"] and "--force" not in sys.argv:
        return                                              # already on the Unicorn today
    r = subprocess.run([sys.executable, UNICORN, "push", OUT, "kotoba.json"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if r.returncode == 0 and r.stdout.startswith("OK"):
        st["sent"] = data["day"]
        save_state(st)


if __name__ == "__main__":
    main()
