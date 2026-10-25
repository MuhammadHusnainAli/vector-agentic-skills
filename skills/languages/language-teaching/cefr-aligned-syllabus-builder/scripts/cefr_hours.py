#!/usr/bin/env python3
"""Estimate guided learning hours and course length to move between CEFR levels.

Uses Cambridge English's widely quoted cumulative guided-learning-hour ranges (A2 ~180-200, B1 ~350-400,
B2 ~500-600, C1 ~700-800, C2 ~1,000-1,200) as midpoints. Hours vary with L1 distance, age, intensity, exposure
and self-study; --distance applies a rough multiplier (near 0.85, medium 1.0, far 1.3), e.g. Spanish speakers
learning English are "near", Japanese or Arabic speakers "far".

Usage:
    python cefr_hours.py --from A2 --to B2 --hours-per-week 6
    python cefr_hours.py --from B1 --to C1 --weeks 30 --distance far

Exit codes: 0 printed, 2 target not above start or bad arguments.
"""

import argparse
import math
import sys

CUMULATIVE = {"A0": 0, "A1": 95, "A2": 190, "B1": 375, "B2": 550, "C1": 750, "C2": 1100}
DISTANCE = {"near": 0.85, "medium": 1.0, "far": 1.3}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=str.upper, choices=CUMULATIVE, required=True, help="A0 = beginner")
    ap.add_argument("--to", dest="end", type=str.upper, choices=CUMULATIVE, required=True)
    ap.add_argument("--hours-per-week", type=float, help="class hours per week")
    ap.add_argument("--weeks", type=int, help="weeks available (prints hours per week needed)")
    ap.add_argument("--distance", choices=DISTANCE, default="medium", help="L1 distance from English")
    a = ap.parse_args()
    if CUMULATIVE[a.end] <= CUMULATIVE[a.start]:
        print("error: --to must be above --from", file=sys.stderr)
        return 2
    hours = (CUMULATIVE[a.end] - CUMULATIVE[a.start]) * DISTANCE[a.distance]
    lo, hi = hours * 0.8, hours * 1.2
    print(f"{a.start} -> {a.end}: about {hours:.0f} guided hours (range {lo:.0f}-{hi:.0f}), L1 distance {a.distance}")
    steps = [lvl for lvl in CUMULATIVE if CUMULATIVE[a.start] < CUMULATIVE[lvl] <= CUMULATIVE[a.end]]
    prev = a.start
    for lvl in steps:
        print(f"  {prev} -> {lvl}: ~{(CUMULATIVE[lvl] - CUMULATIVE[prev]) * DISTANCE[a.distance]:.0f} h")
        prev = lvl
    if a.hours_per_week:
        weeks = math.ceil(hours / a.hours_per_week)
        print(f"At {a.hours_per_week:g} h/week: about {weeks} weeks ({weeks / 36:.1f} school years of 36 weeks)")
    if a.weeks:
        print(f"In {a.weeks} weeks: about {hours / a.weeks:.1f} class hours per week")
    print("Guided hours include class time and teacher-directed study; regular self-study and exposure shorten it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
