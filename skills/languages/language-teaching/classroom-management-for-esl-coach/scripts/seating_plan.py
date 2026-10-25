#!/usr/bin/env python3
"""Make a seating plan for pair or group work that respects constraints and mixes first languages.

CSV columns: name, level (A1-C2 or a number), l1, keep_apart (names separated by ';'), front (y for learners who
need to sit near the board: sight, hearing, attention)

Learners who need the front go to the first tables. Tables are filled so that learners in keep_apart never sit
together and, where possible, neighbours do not share an L1 (more English) and stronger and weaker learners
alternate.

Usage:
    python seating_plan.py class.csv --size 2          # pairs
    python seating_plan.py class.csv --size 4 --seed 3  # groups of four, shuffled within levels

Exit codes: 0 plan printed, 1 constraints could not all be met (plan still printed), 2 read error.
"""

import argparse
import csv
import random
import sys

CEFR = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


def lvl(s):
    s = (s or "").strip().upper().rstrip("+")
    return CEFR.get(s) or float(s or 0)


def cost(table, x):
    """0 = fine, 1 = shares an L1, 100 = keep-apart clash."""
    c = 0
    for y in table:
        if y["name"] in x["apart"] or x["name"] in y["apart"]:
            c += 100
        if x["l1"] and x["l1"] == y["l1"]:
            c += 1
    return c


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--size", type=int, default=2, help="learners per table (default 2)")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            people = [{"name": r["name"].strip(), "level": lvl(r.get("level")), "l1": (r.get("l1") or "").strip().lower(),
                       "apart": {x.strip() for x in (r.get("keep_apart") or "").split(";") if x.strip()},
                       "front": (r.get("front") or "").strip().lower() in ("y", "yes", "1")} for r in csv.DictReader(fh)]
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: needs name and level columns ({e})", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    rng.shuffle(people)
    people.sort(key=lambda p: -p["level"])
    order, lo, hi = [], 0, len(people) - 1
    while lo <= hi:  # strongest, weakest, next strongest, ...
        order.append(people[lo])
        if lo != hi:
            order.append(people[hi])
        lo, hi = lo + 1, hi - 1
    order.sort(key=lambda p: not p["front"])  # front-needs first, stable
    n_tables = -(-len(order) // a.size)
    tables = [[] for _ in range(n_tables)]
    clashes = []
    for p in order:
        open_ = [t for t in tables if len(t) < a.size]
        best = min(open_, key=lambda t: (cost(t, p), len(t), tables.index(t) if p["front"] else 0))
        if cost(best, p) >= 100:
            clashes.append(p["name"])
        best.append(p)
    print(f"{len(order)} learners at {n_tables} tables of up to {a.size} (table 1 nearest the board)\n")
    for i, t in enumerate(tables, 1):
        mark = lambda p: p["name"] + (" (front)" if p["front"] else "")
        l1s = [p["l1"] for p in t if p["l1"]]
        note = " - shared L1" if len(l1s) != len(set(l1s)) else ""
        print(f"Table {i}: " + ", ".join(mark(p) for p in t) + note)
    if clashes:
        print(f"\nCould not keep apart: {', '.join(clashes)} - adjust by hand")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
