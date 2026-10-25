#!/usr/bin/env python3
"""Pace course units across a term calendar: lesson dates, holidays, review and assessment lessons.

Lessons fall on the given weekdays between --start and --end, minus holidays. Review lessons are inserted after
every N units and assessment lessons are kept at the end; the remaining lessons are shared between units in
proportion to their weights (default equal).

Usage:
    python pacing.py --start 2026-09-07 --end 2026-12-18 --days mon wed fri --units 8 \
        --holidays 2026-10-26:2026-10-30 2026-11-26 --review-every 3 --assessment 2
    python pacing.py --start 2027-01-11 --end 2027-03-26 --days tue thu --weights 2 1 1 2

Exit codes: 0 printed, 1 fewer lessons than units (or under 2 per unit), 2 bad dates or arguments.
"""

import argparse
import datetime as dt
import sys

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def holidays(specs):
    out = set()
    for s in specs:
        a, _, b = s.partition(":")
        d, end = dt.date.fromisoformat(a), dt.date.fromisoformat(b or a)
        while d <= end:
            out.add(d)
            d += dt.timedelta(days=1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=dt.date.fromisoformat, required=True)
    ap.add_argument("--end", type=dt.date.fromisoformat, required=True)
    ap.add_argument("--days", nargs="+", choices=DAYS, required=True, help="lesson weekdays")
    ap.add_argument("--units", type=int, help="number of units (equal weight)")
    ap.add_argument("--weights", nargs="*", type=float, help="relative size of each unit instead of --units")
    ap.add_argument("--holidays", nargs="*", default=[], help="YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD")
    ap.add_argument("--review-every", type=int, default=0, help="one review lesson after every N units")
    ap.add_argument("--assessment", type=int, default=0, help="lessons kept for tests at the end")
    try:
        a = ap.parse_args()
        off = holidays(a.holidays)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    weights = a.weights or [1.0] * (a.units or 0)
    if not weights or a.end <= a.start:
        print("error: need --units or --weights, and --end after --start", file=sys.stderr)
        return 2
    want = {DAYS.index(d) for d in a.days}
    lessons, d = [], a.start
    while d <= a.end:
        if d.weekday() in want and d not in off:
            lessons.append(d)
        d += dt.timedelta(days=1)
    n = len(weights)
    reviews = (n - 1) // a.review_every if a.review_every else 0
    teach = len(lessons) - reviews - a.assessment
    lost = sum(1 for x in off if x.weekday() in want and a.start <= x <= a.end)
    print(f"{len(lessons)} lessons ({lost} lost to holidays); {reviews} review, {a.assessment} assessment, "
          f"{teach} for {n} units\n")
    if teach < 2 * n:
        print(f"error: only {teach} teaching lessons for {n} units; cut units or add lessons", file=sys.stderr)
        return 1
    share = [int(teach * w / sum(weights)) for w in weights]
    for i in sorted(range(n), key=lambda i: teach * weights[i] / sum(weights) - share[i], reverse=True)[:teach - sum(share)]:
        share[i] += 1
    while min(share) == 0:  # a tiny weight still gets one lesson
        share[share.index(max(share))] -= 1
        share[share.index(0)] += 1
    print("| Block | Lessons | From | To |\n|-------|---------|------|----|")
    k = 0
    for u in range(n):
        block = lessons[k:k + share[u]]
        print(f"| Unit {u + 1} | {len(block)} | {block[0]} | {block[-1]} |")
        k += share[u]
        if a.review_every and (u + 1) % a.review_every == 0 and u + 1 < n:
            print(f"| Review | 1 | {lessons[k]} | {lessons[k]} |")
            k += 1
    if a.assessment:
        print(f"| Assessment | {a.assessment} | {lessons[k]} | {lessons[-1]} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
