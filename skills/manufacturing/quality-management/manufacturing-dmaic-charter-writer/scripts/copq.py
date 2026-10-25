#!/usr/bin/env python3
"""Estimate the cost of poor quality (COPQ) for a DMAIC business case, and the savings at the goal.

Internal failure: defects x (scrap share x scrap cost + rework share x rework cost)
External failure: defects escaping x external cost (sorting, charge-backs, premium freight, warranty)
Appraisal: extra inspection cost attributable to the problem (annual, optional)
Savings = COPQ now - COPQ at the target defect rate (appraisal kept unless --appraisal-at-target is given).

Usage:
    python copq.py --units 240000 --defect-rate 0.031 --scrap-share 0.6 --scrap-cost 9.50 --rework-cost 3.20 \
                   --escape-share 0.02 --external-cost 85 --appraisal 12000 --target-rate 0.008 --project-cost 15000
    python copq.py --units 50000 --defect-rate 2500ppm --scrap-share 1 --scrap-cost 40

Exit codes: 0 computed, 2 usage error.
"""

import argparse
import sys


def rate(s):
    s = str(s).strip().lower()
    v = float(s[:-3]) / 1e6 if s.endswith("ppm") else float(s.rstrip("%")) / 100 if s.endswith("%") else float(s)
    if not 0 <= v < 1:
        raise argparse.ArgumentTypeError("rate must be a fraction (0.031), a percent (3.1%) or ppm (2500ppm)")
    return v


def cost(units, r, a):
    defects = units * r
    internal = defects * (a.scrap_share * a.scrap_cost + (1 - a.scrap_share) * a.rework_cost)
    external = defects * a.escape_share * a.external_cost
    return defects, internal, external


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--units", type=float, required=True, help="units produced per year")
    ap.add_argument("--defect-rate", type=rate, required=True, help="current defect rate: 0.031, 3.1%% or 31000ppm")
    ap.add_argument("--scrap-share", type=float, default=1.0, help="share of defects scrapped (rest reworked)")
    ap.add_argument("--scrap-cost", type=float, default=0.0, help="cost per scrapped unit (material + value added)")
    ap.add_argument("--rework-cost", type=float, default=0.0, help="cost per reworked unit (labour + re-inspection)")
    ap.add_argument("--escape-share", type=float, default=0.0, help="share of defects reaching the customer")
    ap.add_argument("--external-cost", type=float, default=0.0, help="cost per escaped defect")
    ap.add_argument("--appraisal", type=float, default=0.0, help="annual extra inspection cost now")
    ap.add_argument("--appraisal-at-target", type=float, help="annual extra inspection cost at the target")
    ap.add_argument("--target-rate", type=rate, help="goal defect rate")
    ap.add_argument("--project-cost", type=float, default=0.0)
    ap.add_argument("--currency", default="")
    a = ap.parse_args()
    if not (0 <= a.scrap_share <= 1 and 0 <= a.escape_share <= 1) or a.units <= 0:
        print("error: shares must be 0-1 and --units > 0", file=sys.stderr)
        return 2
    cur = a.currency
    d, i, e = cost(a.units, a.defect_rate, a)
    total = i + e + a.appraisal
    print(f"Current: {a.defect_rate:.2%} of {a.units:,.0f} units = {d:,.0f} defects per year")
    print(f"  Internal failure (scrap + rework): {cur}{i:,.0f}")
    print(f"  External failure (escapes):        {cur}{e:,.0f}")
    print(f"  Appraisal (extra inspection):      {cur}{a.appraisal:,.0f}")
    print(f"  COPQ per year:                     {cur}{total:,.0f}")
    if a.target_rate is not None:
        if a.target_rate >= a.defect_rate:
            print("error: --target-rate must be below --defect-rate", file=sys.stderr)
            return 2
        d2, i2, e2 = cost(a.units, a.target_rate, a)
        ap2 = a.appraisal if a.appraisal_at_target is None else a.appraisal_at_target
        t2 = i2 + e2 + ap2
        save = total - t2
        print(f"\nAt target {a.target_rate:.2%}: COPQ {cur}{t2:,.0f} per year -> savings {cur}{save:,.0f} per year")
        if a.project_cost:
            print(f"Project cost {cur}{a.project_cost:,.0f}: payback {12 * a.project_cost / save:.1f} months, "
                  f"first-year return {save / a.project_cost:.1f}x" if save > 0 else "No savings at this target.")
        print("Count only hard savings (scrap, rework labour, charge-backs) in the charter; list soft savings separately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
