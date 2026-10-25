#!/usr/bin/env python3
"""Check an analytic speaking (or writing) rubric for complete, distinct, observable band descriptors.

CSV columns: criterion, band (number), descriptor

Checks:
  SR001 high    criterion missing a band that other criteria have
  SR002 medium  adjacent bands of a criterion are nearly identical (raters cannot separate them)
  SR003 medium  descriptor is only evaluative words (good, adequate, excellent) with no observable feature
  SR004 medium  descriptor uses a native-speaker benchmark
  SR005 low     fewer than 3 or more than 6 bands
  SR006 low     fewer than 3 or more than 6 criteria

Usage:
    python rubric_check.py rubric.csv

Exit codes: 0 no high findings, 1 high findings, 2 read error or bad CSV.
"""

import argparse
import csv
import re
import sys
from collections import defaultdict

EVAL = {"good", "very", "excellent", "adequate", "poor", "weak", "satisfactory", "limited", "some", "fair", "strong",
        "sufficient", "insufficient", "average", "basic", "great", "ok", "acceptable", "use", "of", "and", "the",
        "a", "with", "is", "shows", "has", "language", "performance", "level", "ability", "grammar", "vocabulary",
        "pronunciation", "fluency", "accuracy", "range", "overall", "control", "communication"}


def words(t):
    return set(re.findall(r"[a-z]+", t.lower()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        grid = defaultdict(dict)
        for r in rows:
            grid[r["criterion"].strip()][int(r["band"])] = (r["descriptor"] or "").strip()
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: needs criterion, band (number) and descriptor columns ({e})", file=sys.stderr)
        return 2
    if not grid:
        print("error: empty rubric", file=sys.stderr)
        return 2
    f = []
    bands = sorted({b for c in grid.values() for b in c})
    print(f"{len(grid)} criteria x {len(bands)} bands ({bands[0]}-{bands[-1]})")
    for crit, by in grid.items():
        for b in bands:
            if not by.get(b):
                f.append(("SR001", "high", f"{crit}: no descriptor for band {b}"))
        present = sorted(b for b in by if by[b])
        for lo, hi in zip(present, present[1:]):
            x, y = words(by[lo]), words(by[hi])
            if x and y and len(x & y) / len(x | y) > 0.8:
                f.append(("SR002", "medium", f"{crit}: bands {lo} and {hi} are nearly identical"))
        for b in present:
            if not (words(by[b]) - EVAL):
                f.append(("SR003", "medium", f"{crit} band {b} '{by[b][:40]}': describe what the speaker does"))
            if re.search(r"native[- ]?(like|speaker)|like a native", by[b], re.I):
                f.append(("SR004", "medium", f"{crit} band {b}: replace the native-speaker benchmark with observable features"))
    if not 3 <= len(bands) <= 6:
        f.append(("SR005", "low", f"{len(bands)} bands; 3-6 are easier to rate consistently"))
    if not 3 <= len(grid) <= 6:
        f.append(("SR006", "low", f"{len(grid)} criteria; 3-6 keep raters' attention manageable"))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: complete, distinct, observable descriptors")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
