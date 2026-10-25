#!/usr/bin/env python3
"""Track observation ratings over time: per teacher and area, the latest rating, change and development points.

CSV columns: teacher, date (YYYY-MM-DD), area, rating (1-4; blank or n/o = not observed)

Flags:
  support   the area's last two observed ratings are 2 or lower: plan CPD or coaching
  improved  the latest rating is at least 1 point above the first
  share     rated 4 at least twice: invite the teacher to share practice

Usage:
    python observation_trends.py observations.csv [--teacher "J. Doe"]

Exit codes: 0 printed, 2 read error or bad rating.
"""

import argparse
import csv
import sys
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--teacher")
    a = ap.parse_args()
    data = defaultdict(lambda: defaultdict(list))
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                rating = (r["rating"] or "").strip().lower()
                if rating in ("", "n/o", "no"):
                    continue
                v = int(rating)
                if not 1 <= v <= 4:
                    raise ValueError(f"rating {v} outside 1-4")
                data[r["teacher"].strip()][r["area"].strip()].append((r["date"].strip(), v))
    except (OSError, csv.Error, KeyError, ValueError) as e:
        print(f"error: needs teacher, date, area and rating (1-4) columns ({e})", file=sys.stderr)
        return 2
    teachers = [a.teacher] if a.teacher else sorted(data)
    for t in teachers:
        if t not in data:
            print(f"error: no observations for {t}", file=sys.stderr)
            return 2
        print(f"## {t}")
        print("| Area | Ratings (oldest -> latest) | Latest | Note |\n|------|----------------------------|--------|------|")
        notes = []
        for area, obs in sorted(data[t].items()):
            obs.sort()
            vals = [v for _, v in obs]
            flag = []
            if len(vals) >= 2 and all(v <= 2 for v in vals[-2:]):
                flag.append("support")
            if len(vals) >= 2 and vals[-1] - vals[0] >= 1:
                flag.append("improved")
            if vals.count(4) >= 2:
                flag.append("share")
            print(f"| {area} | {' -> '.join(map(str, vals))} | {vals[-1]} | {', '.join(flag)} |")
            if "support" in flag:
                notes.append(f"{area}: two low ratings in a row - agree a CPD or coaching action")
        for n in notes:
            print(f"Action: {n}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
