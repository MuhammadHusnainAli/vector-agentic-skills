#!/usr/bin/env python3
"""Suggest warmers or icebreakers from references/warmer-bank.md for a purpose, level, class size and time.

With --seed the choice is shuffled reproducibly, so a teacher can get fresh warmers each lesson; --exclude skips
warmers already used this term.

Usage:
    python warmer_picker.py --purpose icebreaker --level A2 --students 14 --minutes 10
    python warmer_picker.py --purpose review --level B1 --online --seed 7 --exclude "Backs to the board"

Exit codes: 0 warmers found, 1 nothing matches, 2 bank unreadable or bad arguments.
"""

import argparse
import random
import re
import sys
from pathlib import Path

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
PURPOSES = ["icebreaker", "energiser", "settler", "review", "lead-in"]
DEFAULT_BANK = Path(__file__).resolve().parent.parent / "references" / "warmer-bank.md"


def read_bank(path):
    rows, head = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s|:-]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    if not rows:
        raise ValueError(f"no warmer table in {path}")
    return rows


def fits(r, a, excluded):
    lo, _, hi = r["levels"].upper().partition("-")
    if a.level and not LEVELS.index(lo) <= LEVELS.index(a.level) <= LEVELS.index(hi or lo):
        return False
    if a.purpose and a.purpose not in r["purposes"].lower():
        return False
    if a.students and a.students < int(r["min ss"]):
        return False
    if a.minutes and int(r["minutes"]) > a.minutes:
        return False
    if a.online and r["online"].lower() != "yes":
        return False
    return r["warmer"].lower() not in excluded


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--purpose", choices=PURPOSES)
    ap.add_argument("--level", type=str.upper, help="CEFR level A1-C2")
    ap.add_argument("--students", type=int, help="class size")
    ap.add_argument("--minutes", type=int, help="time available (maximum)")
    ap.add_argument("--online", action="store_true", help="must work in a video call")
    ap.add_argument("--seed", type=int, help="shuffle matches reproducibly")
    ap.add_argument("--exclude", nargs="*", default=[], help="warmer names already used")
    ap.add_argument("--show", type=int, default=3)
    ap.add_argument("--bank", default=DEFAULT_BANK)
    a = ap.parse_args()
    if a.level and a.level not in LEVELS:
        print(f"error: level must be one of {', '.join(LEVELS)}", file=sys.stderr)
        return 2
    try:
        rows = read_bank(a.bank)
        hits = [r for r in rows if fits(r, a, {e.lower() for e in a.exclude})]
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not hits:
        print("No warmer matches; relax --minutes or --purpose.")
        return 1
    if a.seed is not None:
        random.Random(a.seed).shuffle(hits)
    for r in hits[:a.show]:
        print(f"## {r['warmer']}  ({r['purposes']}; {r['levels']}; {r['minutes']} min; prep {r['prep']}; online {r['online']})")
        print(f"{r['how it works']}\n")
    print(f"{len(hits)} match(es) in {len(rows)} warmers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
