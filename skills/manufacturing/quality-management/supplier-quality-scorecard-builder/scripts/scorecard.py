#!/usr/bin/env python3
"""Build a supplier quality scorecard: PPM, on-time delivery, responsiveness, weighted score, grade and trend.

CSV columns (one row per supplier per period): supplier, period, received, rejected, deliveries, on_time,
scars, scars_on_time (corrective action requests answered on time; optional)

Scores (0-100):
  quality         PPM vs --ppm-target: <= target 100, <= 2x 85, <= 5x 70, <= 10x 50, else 0
  delivery        OTD %: >= 98 100, >= 95 85, >= 90 70, >= 85 50, else 0
  responsiveness  share of SCARs answered on time (100 when none were issued)
Weighted total with --weights (quality, delivery, responsiveness; default 50 30 20).
Grade: A >= 90 preferred, B >= 80 approved, C >= 70 improvement plan, D < 70 probation / SCAR / development.

Flags:
  SC001  grade D in the latest period
  SC002  score fell in each of the last two periods
  SC003  PPM above target in the latest period but no SCAR issued

Usage:
    python scorecard.py supplier_perf.csv --ppm-target 500
    python scorecard.py supplier_perf.csv --period 2026-Q3 --weights 40 40 20

Exit codes: 0 scorecard printed (no flags), 1 flags raised, 2 usage or data error.
"""

import argparse
import csv
import sys
from collections import defaultdict


def band(v, steps):
    for lim, pts in steps:
        if v is not None and lim(v):
            return pts
    return 0


def score(r, target, w):
    rec, rej = float(r["received"] or 0), float(r["rejected"] or 0)
    ppm = 1e6 * rej / rec if rec else 0.0
    dl, ot = float(r["deliveries"] or 0), float(r["on_time"] or 0)
    otd = 100 * ot / dl if dl else 100.0
    sc, sct = float(r.get("scars") or 0), float(r.get("scars_on_time") or 0)
    q = band(ppm, [(lambda v: v <= target, 100), (lambda v: v <= 2 * target, 85), (lambda v: v <= 5 * target, 70),
                   (lambda v: v <= 10 * target, 50)])
    d = band(otd, [(lambda v: v >= 98, 100), (lambda v: v >= 95, 85), (lambda v: v >= 90, 70), (lambda v: v >= 85, 50)])
    resp = 100 * sct / sc if sc else 100.0
    total = (w[0] * q + w[1] * d + w[2] * resp) / sum(w)
    return {"ppm": ppm, "otd": otd, "q": q, "d": d, "r": resp, "total": total, "scars": sc}


def grade(t):
    return "A" if t >= 90 else "B" if t >= 80 else "C" if t >= 70 else "D"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--ppm-target", type=float, default=500)
    ap.add_argument("--weights", type=float, nargs=3, default=[50, 30, 20], metavar=("Q", "D", "R"))
    ap.add_argument("--period", help="period to report (default: latest in the file)")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        need = {"supplier", "period", "received", "rejected", "deliveries", "on_time"}
        if not rows or not need <= set(rows[0]):
            raise ValueError(f"CSV needs columns {', '.join(sorted(need))}")
        hist = defaultdict(dict)
        for r in rows:
            hist[r["supplier"].strip()][r["period"].strip()] = score(r, a.ppm_target, a.weights)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    periods = sorted({p for h in hist.values() for p in h})
    period = a.period or periods[-1]
    if period not in periods:
        print(f"error: period {period!r} not in the data ({', '.join(periods)})", file=sys.stderr)
        return 2
    print(f"Supplier scorecard {period}  (PPM target {a.ppm_target:g}; weights Q/D/R {'/'.join(f'{x:g}' for x in a.weights)})\n")
    print(f"{'Supplier':<20}{'PPM':>8}{'OTD %':>8}{'Q':>5}{'D':>5}{'R':>5}{'Score':>7}  Grade  Trend")
    flags, table = [], []
    for sup, h in hist.items():
        if period not in h:
            continue
        s = h[period]
        prior = [h[p]["total"] for p in periods if p in h and p <= period]
        trend = "-" if len(prior) < 2 else ("up" if prior[-1] > prior[-2] else "down" if prior[-1] < prior[-2] else "flat")
        table.append((s["total"], sup, s, trend))
        if grade(s["total"]) == "D":
            flags.append(f"SC001 {sup}: grade D ({s['total']:.0f}) - probation, SCAR and development plan")
        if len(prior) >= 3 and prior[-1] < prior[-2] < prior[-3]:
            flags.append(f"SC002 {sup}: score fell two periods running ({prior[-3]:.0f} -> {prior[-2]:.0f} -> {prior[-1]:.0f})")
        if s["ppm"] > a.ppm_target and not s["scars"]:
            flags.append(f"SC003 {sup}: PPM {s['ppm']:,.0f} above target with no SCAR issued")
    for total, sup, s, trend in sorted(table, key=lambda x: -x[0]):
        print(f"{sup[:19]:<20}{s['ppm']:>8,.0f}{s['otd']:>8.1f}{s['q']:>5.0f}{s['d']:>5.0f}{s['r']:>5.0f}{total:>7.1f}  {grade(total):^5}  {trend}")
    counts = defaultdict(int)
    for total, *_ in table:
        counts[grade(total)] += 1
    print("\nGrades: " + "  ".join(f"{g}:{counts[g]}" for g in "ABCD"))
    for f in flags:
        print(f)
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main())
