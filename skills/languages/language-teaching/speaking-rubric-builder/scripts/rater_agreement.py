#!/usr/bin/env python3
"""Measure agreement between two raters on band scores (speaking or writing).

CSV columns: student, rater_a, rater_b (optional: criterion). Scores are integers on the same band scale.

Reports exact and adjacent (within one band) agreement, quadratic weighted kappa, each rater's mean (severity),
and cases two or more bands apart that need a third rating.

Findings:
  RA001 high    exact + adjacent agreement under 90%
  RA002 medium  weighted kappa under 0.60
  RA003 low     raters' means differ by more than 0.5 band (one is harsher)
  RA004 low     scores two or more bands apart (listed: rate a third time)

Usage:
    python rater_agreement.py scores.csv

Exit codes: 0 no high findings, 1 high findings, 2 read error or bad CSV.
"""

import argparse
import csv
import sys


def weighted_kappa(a, b):
    cats = list(range(min(a + b), max(a + b) + 1))
    n, k = len(a), len(cats)
    if k < 2:
        return 1.0
    obs = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[x - cats[0]][y - cats[0]] += 1
    ra = [sum(row) for row in obs]
    rb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    w = lambda i, j: (i - j) ** 2 / (k - 1) ** 2
    o = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    e = sum(w(i, j) * ra[i] * rb[j] for i in range(k) for j in range(k)) / n ** 2
    return 1 - o / e if e else 1.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        pairs = [(r["student"].strip() + (f" ({r['criterion']})" if r.get("criterion") else ""),
                  int(r["rater_a"]), int(r["rater_b"])) for r in rows]
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: needs student, rater_a and rater_b with whole-number bands ({e})", file=sys.stderr)
        return 2
    if len(pairs) < 2:
        print("error: need at least two double-rated performances", file=sys.stderr)
        return 2
    xa, xb = [p[1] for p in pairs], [p[2] for p in pairs]
    n = len(pairs)
    exact = sum(x == y for x, y in zip(xa, xb)) / n
    adj = sum(abs(x - y) == 1 for x, y in zip(xa, xb)) / n
    kappa = weighted_kappa(xa, xb)
    ma, mb = sum(xa) / n, sum(xb) / n
    print(f"{n} double-rated performances")
    print(f"Exact agreement {100 * exact:.0f}%, adjacent {100 * adj:.0f}%, within one band {100 * (exact + adj):.0f}%")
    print(f"Quadratic weighted kappa {kappa:.2f}")
    print(f"Mean band: rater A {ma:.2f}, rater B {mb:.2f}")
    f = []
    if round(exact + adj, 6) < 0.9:
        f.append(("RA001", "high", f"only {100 * (exact + adj):.0f}% within one band: re-standardise raters"))
    if kappa < 0.6:
        f.append(("RA002", "medium", f"weighted kappa {kappa:.2f} is below 0.60"))
    if abs(ma - mb) > 0.5:
        f.append(("RA003", "low", f"rater {'A' if ma < mb else 'B'} is harsher by {abs(ma - mb):.2f} bands on average"))
    for name, x, y in pairs:
        if abs(x - y) >= 2:
            f.append(("RA004", "low", f"{name}: {x} vs {y}; needs a third rating"))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda z: (order[z[1]], z[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(z[1] == "high" for z in f) else 0


if __name__ == "__main__":
    sys.exit(main())
