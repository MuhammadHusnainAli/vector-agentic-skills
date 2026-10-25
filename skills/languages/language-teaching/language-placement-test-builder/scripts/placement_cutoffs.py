#!/usr/bin/env python3
"""Place students into levels from test scores using cut scores, flagging borderline cases for an interview.

A score within --sem points of a cut score is borderline: the test cannot separate the two levels reliably, so
check with a short speaking or writing task before placing.

CSV columns: student, score

Usage:
    python placement_cutoffs.py scores.csv --cuts A1:0 A2:15 B1:28 B2:40 C1:50
    python placement_cutoffs.py scores.csv --cuts A1:0 A2:15 B1:28 B2:40 --sem 3

Exit codes: 0 placed, 2 read error or bad cut scores.
"""

import argparse
import csv
import sys
from collections import Counter


def parse_cuts(specs):
    cuts = []
    for s in specs:
        name, _, val = s.partition(":")
        cuts.append((float(val), name.strip()))
    cuts.sort()
    if not cuts or len({c for c, _ in cuts}) != len(cuts):
        raise ValueError("cut scores must be distinct")
    return cuts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--cuts", nargs="+", required=True, help="LEVEL:minimum score, e.g. A1:0 A2:15 B1:28")
    ap.add_argument("--sem", type=float, default=2, help="standard error of measurement in points (default 2)")
    a = ap.parse_args()
    try:
        cuts = parse_cuts(a.cuts)
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = [(r["student"].strip(), float(r["score"])) for r in csv.DictReader(fh)]
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: {e} (need --cuts LEVEL:score and student,score columns)", file=sys.stderr)
        return 2
    counts, borderline = Counter(), []
    print("| Student | Score | Level | Note |\n|---------|-------|-------|------|")
    for name, score in sorted(rows, key=lambda r: -r[1]):
        level = next((lvl for c, lvl in reversed(cuts) if score >= c), f"below {cuts[0][1]}")
        counts[level] += 1
        near = [(c, lvl) for c, lvl in cuts[1:] if abs(score - c) <= a.sem]
        note = ""
        if near:
            c, lvl = near[0]
            below = cuts[[x[0] for x in cuts].index(c) - 1][1]
            note = f"borderline {below}/{lvl}: interview"
            borderline.append(name)
        print(f"| {name} | {score:g} | {level} | {note} |")
    print("\nPlaced: " + ", ".join(f"{lvl} {counts[lvl]}" for _, lvl in cuts if counts[lvl])
          + (f"; {len(borderline)} borderline to interview" if borderline else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
