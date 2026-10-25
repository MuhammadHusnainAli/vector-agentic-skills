#!/usr/bin/env python3
"""Classical item analysis for a multiple-choice language test: facility, discrimination, distractors, KR-20.

CSV: first column student id, then one column per item with the option chosen (A, B, C, D; blank = no answer).
One row with id KEY holds the correct options; an optional row with id LEVEL tags items with a CEFR level, so
the script can spot items that are easier than items at a lower level (useful for placement tests).

Checks:
  IA001 high    negative discrimination: weaker students do better (miskeyed or ambiguous item)
  IA002 medium  discrimination below 0.20
  IA003 medium  facility above 0.90 or below 0.20 (item tells you little)
  IA004 low     distractor chosen by under 5% (not working) or chosen more by the top group than the bottom group
  IA005 low     item tagged at a level is easier than the average item one level below

Discrimination = facility in the top 27% minus facility in the bottom 27% (by total score).

Usage:
    python item_analysis.py responses.csv

Exit codes: 0 no high findings, 1 high findings, 2 read error or no KEY row.
"""

import argparse
import csv
import sys

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = [r for r in csv.reader(fh) if r]
        head, body = rows[0], rows[1:]
        key = next(r for r in body if r[0].strip().upper() == "KEY")
    except (OSError, csv.Error, IndexError, StopIteration):
        print("error: need a header row, a KEY row and student rows", file=sys.stderr)
        return 2
    tags = next((r for r in body if r[0].strip().upper() == "LEVEL"), None)
    students = [r for r in body if r[0].strip().upper() not in ("KEY", "LEVEL")]
    items = head[1:]
    if len(students) < 10:
        print(f"note: {len(students)} students; statistics are unstable below about 30", file=sys.stderr)
    ans = [[(r[i + 1].strip().upper() if i + 1 < len(r) else "") for i in range(len(items))] for r in students]
    correct = [[int(x == key[i + 1].strip().upper()) for i, x in enumerate(s)] for s in ans]
    totals = [sum(c) for c in correct]
    order = sorted(range(len(students)), key=lambda i: totals[i])
    g = max(1, round(0.27 * len(students)))
    low, high = order[:g], order[-g:]
    n, k = len(students), len(items)
    f, fac = [], {}
    print("| Item | Key | Facility | Discrimination | Options (% chosen) |\n|------|-----|----------|----------------|--------------------|")
    for i, item in enumerate(items):
        p = sum(c[i] for c in correct) / n
        d = sum(correct[j][i] for j in high) / g - sum(correct[j][i] for j in low) / g
        fac[item] = p
        opts = sorted({x for s in ans for x in [s[i]] if x})
        share = {o: sum(s[i] == o for s in ans) / n for o in opts}
        print(f"| {item} | {key[i + 1]} | {p:.2f} | {d:+.2f} | " + " ".join(f"{o}:{100 * share[o]:.0f}" for o in opts) + " |")
        if d < 0:
            f.append(("IA001", "high", f"{item}: discrimination {d:+.2f}; check the key and look for two right answers"))
        elif d < 0.2:
            f.append(("IA002", "medium", f"{item}: discrimination {d:.2f} is weak"))
        if p > 0.9 or p < 0.2:
            f.append(("IA003", "medium", f"{item}: facility {p:.2f} ({'too easy' if p > 0.9 else 'too hard'})"))
        for o in opts:
            if o == key[i + 1].strip().upper():
                continue
            if share[o] < 0.05:
                f.append(("IA004", "low", f"{item}: distractor {o} chosen by {100 * share[o]:.0f}%; replace it"))
            elif sum(ans[j][i] == o for j in high) > sum(ans[j][i] == o for j in low):
                f.append(("IA004", "low", f"{item}: distractor {o} attracts the top group more than the bottom group"))
    var = sum((t - sum(totals) / n) ** 2 for t in totals) / n
    pq = sum(fac[it] * (1 - fac[it]) for it in items)
    kr20 = k / (k - 1) * (1 - pq / var) if var and k > 1 else 0
    if tags:
        by = {}
        for i, item in enumerate(items):
            lvl = tags[i + 1].strip().upper() if i + 1 < len(tags) else ""
            if lvl in LEVELS:
                by.setdefault(lvl, []).append(item)
        for lvl, its in by.items():
            below = LEVELS[LEVELS.index(lvl) - 1] if LEVELS.index(lvl) else None
            if below in by:
                mean_below = sum(fac[x] for x in by[below]) / len(by[below])
                for it in its:
                    if fac[it] > mean_below:
                        f.append(("IA005", "low", f"{it} ({lvl}) facility {fac[it]:.2f} is above the {below} mean {mean_below:.2f}"))
    print(f"\n{n} students, {k} items, mean {sum(totals) / n:.1f}, KR-20 reliability {kr20:.2f}")
    sev = {"high": 0, "medium": 1, "low": 2}
    for code, s, msg in sorted(f, key=lambda x: (sev[x[1]], x[0])):
        print(f"{code} [{s}] {msg}")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
