#!/usr/bin/env python3
"""Summarise each learner's progress by skill across terms, as evidence for report comments.

CSV columns: student, term, skill, score   (score 0-100; terms sort as text, so use 2026-T1, 2026-T2...)

For each student: latest score per skill, change since the previous term, strongest and weakest skill, and a draft
evidence sentence to build the comment on.

Usage:
    python progress_summary.py scores.csv [--student Ana] [--drop 5]

--drop flags skills that fell by at least this many points (default 5).

Exit codes: 0 printed, 2 read error, bad scores or unknown student.
"""

import argparse
import csv
import sys
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--student")
    ap.add_argument("--drop", type=float, default=5)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            data = defaultdict(lambda: defaultdict(dict))
            for r in csv.DictReader(fh):
                data[r["student"].strip()][r["skill"].strip().lower()][r["term"].strip()] = float(r["score"])
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: needs student, term, skill and numeric score columns ({e})", file=sys.stderr)
        return 2
    names = [a.student] if a.student else sorted(data)
    if a.student and a.student not in data:
        print(f"error: no scores for {a.student}", file=sys.stderr)
        return 2
    for name in names:
        rows = []
        for skill, terms in sorted(data[name].items()):
            ts = sorted(terms)
            last = terms[ts[-1]]
            change = last - terms[ts[-2]] if len(ts) > 1 else None
            rows.append((skill, ts[-1], last, change))
        print(f"## {name}")
        print("| Skill | Latest | Score | Change |\n|-------|--------|-------|--------|")
        for skill, term, last, change in rows:
            print(f"| {skill} | {term} | {last:g} | {'-' if change is None else f'{change:+g}'} |")
        best = max(rows, key=lambda r: r[2])
        worst = min(rows, key=lambda r: r[2])
        grew = [r for r in rows if r[3] is not None and r[3] > 0]
        fell = [r for r in rows if r[3] is not None and r[3] <= -a.drop]
        evidence = [f"strongest in {best[0]} ({best[2]:g})"]
        if grew:
            g = max(grew, key=lambda r: r[3])
            evidence.append(f"most progress in {g[0]} ({g[3]:+g})")
        if worst is not best:
            evidence.append(f"next focus: {worst[0]} ({worst[2]:g})")
        print(f"\nEvidence: {name} is " + "; ".join(evidence) + ".")
        for r in fell:
            print(f"Check: {r[0]} fell {-r[3]:g} points - absence, test difficulty or a real drop?")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
