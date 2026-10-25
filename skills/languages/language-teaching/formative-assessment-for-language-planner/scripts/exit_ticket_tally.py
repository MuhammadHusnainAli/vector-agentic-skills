#!/usr/bin/env python3
"""Turn exit-ticket or quick-check results into next-lesson decisions per objective.

CSV: student, then one column per objective (or item). Values: 1/0, Y/N, or a score out of --max.
A student has met an objective when their score reaches --pass (default: full marks for 0/1 data, 2 of 3...).

Decision per objective (share of students who met it):
  under 70%   RETEACH   whole class, a different way
  70-89%      GROUP     small-group reteach for the listed students; others practise or extend
  90%+        MOVE ON   individual follow-up for the few listed

Usage:
    python exit_ticket_tally.py ticket.csv
    python exit_ticket_tally.py ticket.csv --max 3 --pass 2

Exit codes: 0 printed, 2 read error or bad values.
"""

import argparse
import csv
import sys

TRUE = {"1", "y", "yes", "true", "✓"}
FALSE = {"0", "n", "no", "false", "x", ""}


def value(v):
    s = (v or "").strip().lower()
    if s in TRUE:
        return 1.0
    if s in FALSE:
        return 0.0
    return float(s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--max", type=float, default=1, help="maximum score per objective (default 1)")
    ap.add_argument("--pass", dest="pass_", type=float, help="score that counts as met (default --max)")
    a = ap.parse_args()
    need = a.pass_ if a.pass_ is not None else a.max
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        objs = [c for c in rows[0] if c != "student"]
        data = {r["student"].strip(): {o: value(r[o]) for o in objs} for r in rows}
    except (OSError, csv.Error, KeyError, ValueError, IndexError) as e:
        print(f"error: needs student + objective columns with 1/0, Y/N or numbers ({e})", file=sys.stderr)
        return 2
    n = len(data)
    print(f"{n} students, {len(objs)} objectives (met = {need:g}/{a.max:g})\n")
    print("| Objective | Met | Decision | Students to follow up |\n|-----------|-----|----------|-----------------------|")
    struggling = {s: 0 for s in data}
    for o in objs:
        miss = [s for s, sc in data.items() if sc[o] < need]
        for s in miss:
            struggling[s] += 1
        share = 100 * (n - len(miss)) / n
        decision = "RETEACH" if share < 70 else "GROUP" if share < 90 else "MOVE ON"
        names = "whole class" if decision == "RETEACH" else ", ".join(miss) or "-"
        print(f"| {o} | {share:.0f}% | {decision} | {names} |")
    flagged = [s for s, k in struggling.items() if k >= max(2, (len(objs) + 1) // 2)]
    top = [s for s, k in struggling.items() if k == 0]
    if flagged:
        print(f"\nMissed most objectives: {', '.join(flagged)} - check in one-to-one; consider level or attendance")
    if top:
        print(f"Met everything: {', '.join(top)} - give an extension task")
    return 0


if __name__ == "__main__":
    sys.exit(main())
