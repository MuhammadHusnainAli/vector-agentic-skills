#!/usr/bin/env python3
"""Sequence a young learner lesson that alternates stir and settle activities within the children's attention span.

Activities come from references/yl-activity-bank.md and must suit the age. Each activity lasts no longer than
the attention span used here (about the child's age in minutes plus two, capped at 15). Lessons open and close
with routines (hello / goodbye songs for under-9s).

Usage:
    python yl_lesson_timer.py --age 6 --minutes 45 --seed 2
    python yl_lesson_timer.py --age 10 --minutes 60 --exclude "Board game"

Exit codes: 0 sequence printed, 2 bad arguments or too few suitable activities.
"""

import argparse
import random
import re
import sys
from pathlib import Path

BANK = Path(__file__).resolve().parent.parent / "references" / "yl-activity-bank.md"
ROUTINES = {"Hello song", "Goodbye song", "Weather and date routine"}


def read(path):
    rows, head = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s|:-]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif len(cells) == len(head):
            r = dict(zip(head, cells))
            lo, _, hi = r["ages"].partition("-")
            r["lo"], r["hi"], r["min"] = int(lo), int(hi or lo), int(r["minutes"])
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--age", type=int, required=True, help="typical age of the class (3-12)")
    ap.add_argument("--minutes", type=int, required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--bank", default=BANK)
    a = ap.parse_args()
    if not 3 <= a.age <= 12 or a.minutes < 15:
        print("error: --age 3-12 and --minutes >= 15", file=sys.stderr)
        return 2
    try:
        rows = [r for r in read(a.bank) if r["lo"] <= a.age <= r["hi"] and r["activity"] not in a.exclude]
    except (OSError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    span = min(15, a.age + 2)
    pool = {t: [r for r in rows if r["type"] == t and r["activity"] not in ROUTINES and r["min"] <= span]
            for t in ("stir", "settle")}
    if not pool["stir"] or not pool["settle"]:
        print(f"error: not enough stir and settle activities for age {a.age}", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    for v in pool.values():
        rng.shuffle(v)
    opening = [r for r in rows if r["activity"] in ("Hello song", "Weather and date routine")]
    closing = [r for r in rows if r["activity"] == "Goodbye song"]
    plan = opening[:]
    left = a.minutes - sum(r["min"] for r in opening + closing)
    kind = "settle" if opening and opening[-1]["type"] == "stir" else "stir"
    while True:
        fit = [r for r in pool[kind] if r["min"] <= left]
        if not fit:
            break
        r = fit[-1]
        pool[kind].remove(r)
        plan.append(r)
        left -= r["min"]
        kind = "settle" if kind == "stir" else "stir"
    plan += closing
    print(f"Age {a.age}: attention span about {span} min per activity; {a.minutes}-minute lesson\n")
    print("| Time | Activity | Type | Language | How |\n|------|----------|------|----------|-----|")
    t = 0
    for r in plan:
        print(f"| {t}-{t + r['min']} | {r['activity']} | {r['type']} | {r['language']} | {r['how it works']} |")
        t += r["min"]
    if a.minutes - t > 0:
        print(f"\n{a.minutes - t} min spare: extend the story or repeat a favourite game")
    return 0


if __name__ == "__main__":
    sys.exit(main())
