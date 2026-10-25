#!/usr/bin/env python3
"""Estimate the study needed to close an IELTS band gap, from overall or per-skill scores.

Overall band = mean of the four skills, rounded the IELTS way (.25 rounds up to .5, .75 rounds up to the next
band). Hours use a common rule of thumb of about 200 guided hours per band (range 150-250), weighted up for
gains above band 7. This is a planning estimate, not a promise: progress varies with exposure, intensity,
motivation and the gap between the weakest skill and the target.

Usage:
    python ielts_gap.py --current 5.5 --target 6.5 --hours-per-week 20
    python ielts_gap.py --skills L6 R6.5 W5 S5.5 --target 6.5 --min-skill 6 --weeks 10 --hours-per-week 20

Exit codes: 0 estimate fits the time available (or no time given), 1 not enough time, 2 bad arguments.
"""

import argparse
import math
import re
import sys

CEFR = [(8.5, "C2"), (7.0, "C1"), (5.5, "B2"), (4.0, "B1"), (0, "below B1")]  # IELTS published alignment (approx.)


def overall(scores):
    return math.floor(sum(scores) / len(scores) * 2 + 0.5) / 2


def hours(cur, tgt):
    h, b = 0.0, cur
    while b < tgt:
        step = min(0.5, tgt - b)
        h += step * 2 * (100 if b < 7 else 130)  # per half band; higher bands take longer
        b += step
    return h


def cefr(b):
    return next(level for cut, level in CEFR if b >= cut)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--current", type=float)
    ap.add_argument("--skills", nargs=4, help="L R W S scores like L6 R6.5 W5 S5.5")
    ap.add_argument("--target", type=float, required=True)
    ap.add_argument("--min-skill", type=float, help="minimum required in every skill (e.g. 6.0)")
    ap.add_argument("--hours-per-week", type=float)
    ap.add_argument("--weeks", type=int, help="weeks until the test or course start")
    a = ap.parse_args()
    skills = {}
    if a.skills:
        for s in a.skills:
            m = re.fullmatch(r"([LRWS])(\d(?:\.[05])?)", s.upper())
            if not m:
                print(f"error: skill score '{s}' should look like W5.5", file=sys.stderr)
                return 2
            skills[m.group(1)] = float(m.group(2))
        if len(skills) != 4:
            print("error: give L, R, W and S once each", file=sys.stderr)
            return 2
    cur = overall(list(skills.values())) if skills else a.current
    if cur is None or not 0 <= cur <= 9 or not 0 <= a.target <= 9:
        print("error: give --current or --skills, and bands between 0 and 9", file=sys.stderr)
        return 2
    print(f"Current overall {cur:.1f} ({cefr(cur)}) -> target {a.target:.1f} ({cefr(a.target)})")
    need = 0.0
    if skills:
        print("Skills: " + "  ".join(f"{k} {v:g}" for k, v in skills.items()))
        floor = a.min_skill or 0
        gaps = {k: max(floor, a.target - 0.5) - v for k, v in skills.items()}
        weak = sorted((k for k in gaps if gaps[k] > 0), key=lambda k: -gaps[k])
        if weak:
            print("Priority skills: " + ", ".join(f"{k} (+{gaps[k]:g})" for k in weak))
        need = max((hours(skills[k], skills[k] + gaps[k]) for k in weak), default=0)
    need = max(need, hours(cur, a.target))
    if need == 0:
        print("Target already met")
        return 0
    print(f"Estimated guided study: about {need:.0f} hours (range {need * 0.75:.0f}-{need * 1.25:.0f})")
    if a.hours_per_week:
        wk = math.ceil(need / a.hours_per_week)
        print(f"At {a.hours_per_week:g} h/week: about {wk} weeks")
        if a.weeks:
            ok = wk <= a.weeks
            print(f"Time available: {a.weeks} weeks - {'feasible' if ok else 'not enough; consider a longer course, more hours, or a later test date'}")
            return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
