#!/usr/bin/env python3
"""Combine analytic writing scores into weighted totals, levels and feedback flags.

CSV: student, then one column per criterion with band scores (0..--max-band). Weights default to equal.
A score of 0 on the --gate criterion (default: task) means off-task: the total is 0.

Flags per script:
  jagged   a criterion is 2+ bands from the student's own mean (target it in feedback)
  border   the percentage is within 3 points of a level cut

Usage:
    python writing_score.py scores.csv --max-band 5 --cuts A2:40 B1:60 B2:80
    python writing_score.py scores.csv --weights task:2 coherence:1 lexis:1 grammar:1 --gate task

Exit codes: 0 scored, 2 read error, bad weights or a score above --max-band.
"""

import argparse
import csv
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--max-band", type=float, default=5)
    ap.add_argument("--weights", nargs="*", default=[], help="criterion:weight pairs (default equal)")
    ap.add_argument("--cuts", nargs="*", default=[], help="LEVEL:minimum percent, e.g. B1:60")
    ap.add_argument("--gate", default="task", help="criterion that zeroes the total when 0 (default task)")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        crits = [c for c in rows[0] if c != "student"]
        w = {c: 1.0 for c in crits}
        for spec in a.weights:
            c, _, v = spec.partition(":")
            if c not in w:
                raise ValueError(f"unknown criterion in --weights: {c}")
            w[c] = float(v)
        cuts = sorted(((float(s.partition(":")[2]), s.partition(":")[0]) for s in a.cuts), reverse=True)
        data = [(r["student"], {c: float(r[c]) for c in crits}) for r in rows]
        bad = [(s, c) for s, sc in data for c in crits if not 0 <= sc[c] <= a.max_band]
        if bad:
            raise ValueError(f"{bad[0][0]} {bad[0][1]} is outside 0-{a.max_band:g}")
    except (OSError, csv.Error, KeyError, ValueError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print("| Student | " + " | ".join(crits) + " | Total % | Level | Flags |")
    print("|---------|" + "|".join("---" for _ in crits) + "|---------|-------|-------|")
    for s, sc in data:
        pct = 100 * sum(w[c] * sc[c] for c in crits) / (a.max_band * sum(w.values()))
        flags = []
        if a.gate in sc and sc[a.gate] == 0:
            pct, flags = 0.0, ["off-task"]
        mean = sum(sc.values()) / len(sc)
        flags += [f"jagged {c}" for c in crits if abs(sc[c] - mean) >= 2]
        level = next((lvl for cut, lvl in cuts if pct >= cut), "below" if cuts else "-")
        if any(abs(pct - cut) <= 3 for cut, _ in cuts) and "off-task" not in flags:
            flags.append("border")
        print(f"| {s} | " + " | ".join(f"{sc[c]:g}" for c in crits) + f" | {pct:.0f} | {level} | {', '.join(flags)} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
