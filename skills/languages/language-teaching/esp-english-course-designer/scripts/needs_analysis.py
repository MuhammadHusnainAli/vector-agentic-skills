#!/usr/bin/env python3
"""Rank workplace or study tasks for an ESP course from a needs-analysis survey.

CSV columns: respondent, task, frequency, importance, difficulty (each 1-5), role (optional)
Priority = mean frequency x mean importance x mean difficulty (1-125): tasks learners do often, that matter, and
that they find hard come first. Tasks are banded core (top third), secondary, or low; tasks where respondents
disagree a lot (standard deviation of importance >= 1.5) are flagged for follow-up interviews.

Usage:
    python needs_analysis.py survey.csv
    python needs_analysis.py survey.csv --by-role     # also show priorities per role

Exit codes: 0 printed, 2 read error or values outside 1-5.
"""

import argparse
import csv
import statistics
import sys
from collections import defaultdict

FIELDS = ("frequency", "importance", "difficulty")


def rank(rows):
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in FIELDS:
            by[r["task"]][k].append(r[k])
    out = []
    for task, v in by.items():
        m = {k: statistics.mean(v[k]) for k in FIELDS}
        sd = statistics.pstdev(v["importance"]) if len(v["importance"]) > 1 else 0
        out.append((task, m["frequency"] * m["importance"] * m["difficulty"], m, sd, len(v["importance"])))
    return sorted(out, key=lambda x: -x[1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--by-role", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = []
            for r in csv.DictReader(fh):
                rec = {"task": r["task"].strip(), "role": (r.get("role") or "").strip(),
                       "who": (r.get("respondent") or "").strip()}
                for k in FIELDS:
                    rec[k] = float(r[k])
                    if not 1 <= rec[k] <= 5:
                        raise ValueError(f"{k} {rec[k]:g} for '{rec['task']}' is outside 1-5")
                rows.append(rec)
        if not rows:
            raise ValueError("no responses")
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: needs task, frequency, importance, difficulty (1-5) ({e})", file=sys.stderr)
        return 2
    ranked = rank(rows)
    third = max(1, round(len(ranked) / 3))
    people = len({r["who"] for r in rows if r["who"]}) or len(rows)
    print(f"{people} respondents, {len(ranked)} tasks\n")
    print("| # | Task | Freq | Imp | Diff | Priority | Band | n |\n|---|------|------|-----|------|----------|------|---|")
    for i, (task, p, m, sd, n) in enumerate(ranked, 1):
        band = "core" if i <= third else "secondary" if i <= 2 * third else "low"
        print(f"| {i} | {task} | {m['frequency']:.1f} | {m['importance']:.1f} | {m['difficulty']:.1f} | {p:.0f} | {band} | {n} |")
    split = [t for t, _, _, sd, n in ranked if sd >= 1.5 and n >= 3]
    if split:
        print("\nRespondents disagree on importance (interview to find out why): " + ", ".join(split))
    if a.by_role and any(r["role"] for r in rows):
        for role in sorted({r["role"] for r in rows if r["role"]}):
            top = rank([r for r in rows if r["role"] == role])[:3]
            print(f"\nTop tasks for {role}: " + "; ".join(f"{t} ({p:.0f})" for t, p, *_ in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
