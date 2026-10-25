#!/usr/bin/env python3
"""Six Sigma defect metrics: DPU, DPO, DPMO, yields, sigma level, rolled throughput yield.

Sigma level convention: short-term Z = Z_long-term + 1.5 (the Motorola 1.5 sigma shift); --no-shift reports
the long-term Z only. 3.4 DPMO = 6 sigma short-term = 4.5 long-term.

Subcommands:
  dpmo   --defects D --units U --opportunities O   DPU, DPO, DPMO, first-time yield, sigma
  sigma  --dpmo X | --yield Y | --level Z           convert between DPMO, yield and sigma level
  rty    --steps steps.csv (step, units_in, defective_units[, defects]) or --yields y1 y2 ...
         RTY, normalised yield per step, hidden factory share
  table  sigma level / DPMO / yield table

Usage:
    python dpmo.py dpmo --defects 38 --units 1200 --opportunities 14
    python dpmo.py sigma --dpmo 6210
    python dpmo.py rty --yields 0.98 0.95 0.995 0.97
    python dpmo.py rty --steps steps.csv

Exit codes: 0 computed, 2 usage error.
"""

import argparse
import csv
import math
import sys
from statistics import NormalDist

N = NormalDist()


def sigma_from_dpmo(d, shift):
    p = d / 1e6
    if p <= 0:
        return float("inf")
    if p >= 1:
        return float("-inf")
    return N.inv_cdf(1 - p) + shift


def dpmo_from_sigma(z, shift):
    return 1e6 * (1 - N.cdf(z - shift))


def fmt_z(z):
    return "inf" if math.isinf(z) else f"{z:.2f}"


def cmd_dpmo(a):
    if a.units <= 0 or a.opportunities <= 0 or a.defects < 0:
        return err("need units > 0, opportunities > 0, defects >= 0")
    dpu = a.defects / a.units
    dpo = a.defects / (a.units * a.opportunities)
    d = dpo * 1e6
    print(f"Defects {a.defects}, units {a.units}, opportunities per unit {a.opportunities}")
    print(f"  DPU  = {dpu:.4f}")
    print(f"  DPO  = {dpo:.6f}")
    print(f"  DPMO = {d:,.0f}")
    print(f"  Yield per opportunity = {1 - dpo:.4%};  first-time yield (Poisson e^-DPU) = {math.exp(-dpu):.2%}")
    if a.defective_units is not None:
        print(f"  First-time yield (observed) = {1 - a.defective_units / a.units:.2%}")
    print(f"  Sigma level = {fmt_z(sigma_from_dpmo(d, a.shift))}" + (" (short-term, 1.5 shift)" if a.shift else " (long-term)"))
    print("Count only opportunities that are real, measured and can each fail; inflating them flatters the sigma.")
    return 0


def cmd_sigma(a):
    if a.dpmo is not None:
        if not 0 <= a.dpmo <= 1e6:
            return err("--dpmo must be between 0 and 1,000,000")
        z = sigma_from_dpmo(a.dpmo, a.shift)
        print(f"DPMO {a.dpmo:,.1f} -> yield {1 - a.dpmo / 1e6:.4%} -> sigma level {fmt_z(z)}")
    elif a.yield_ is not None:
        if not 0 < a.yield_ <= 1:
            return err("--yield must be a fraction between 0 and 1")
        d = (1 - a.yield_) * 1e6
        print(f"Yield {a.yield_:.4%} -> DPMO {d:,.1f} -> sigma level {fmt_z(sigma_from_dpmo(d, a.shift))}")
    elif a.level is not None:
        d = dpmo_from_sigma(a.level, a.shift)
        print(f"Sigma level {a.level:g} -> DPMO {d:,.1f} -> yield {1 - d / 1e6:.4%}")
    else:
        return err("give --dpmo, --yield or --level")
    return 0


def cmd_rty(a):
    steps = []
    if a.yields:
        steps = [(f"step {i + 1}", y, None) for i, y in enumerate(a.yields)]
    elif a.steps:
        try:
            with open(a.steps, newline="", encoding="utf-8-sig") as fh:
                for r in csv.DictReader(fh):
                    u, b = float(r["units_in"]), float(r["defective_units"])
                    steps.append((r.get("step") or f"step {len(steps) + 1}", 1 - b / u, b))
        except (OSError, KeyError, ValueError) as e:
            return err(f"{e} (columns: step, units_in, defective_units)")
    if not steps or any(not 0 < y <= 1 for _, y, _ in steps):
        return err("need step yields between 0 and 1")
    rty = math.prod(y for _, y, _ in steps)
    print(f"{'Step':<20}{'First-pass yield':>18}")
    for name, y, _ in steps:
        print(f"{name[:19]:<20}{y:>17.2%}")
    worst = min(steps, key=lambda s: s[1])
    print(f"\nRolled throughput yield = {rty:.2%}  (probability a unit passes every step first time)")
    print(f"Normalised yield per step = {rty ** (1 / len(steps)):.2%}")
    print(f"Hidden factory: {1 - rty:.1%} of units are scrapped or reworked somewhere; worst step: {worst[0]} ({worst[1]:.2%})")
    return 0


def cmd_table(a):
    print(f"{'Sigma':>6}{'DPMO':>14}{'Yield':>11}")
    for z in (1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6):
        d = dpmo_from_sigma(z, a.shift)
        print(f"{z:>6g}{d:>14,.1f}{1 - d / 1e6:>10.4%}")
    return 0


def err(msg):
    print(f"error: {msg}", file=sys.stderr)
    return 2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-shift", dest="shift", action="store_const", const=0.0, default=1.5,
                    help="report long-term sigma (no 1.5 shift)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dpmo")
    d.add_argument("--defects", type=int, required=True)
    d.add_argument("--units", type=int, required=True)
    d.add_argument("--opportunities", type=int, required=True, help="defect opportunities per unit")
    d.add_argument("--defective-units", type=int, help="units with one or more defects (observed FTY)")
    s = sub.add_parser("sigma")
    s.add_argument("--dpmo", type=float)
    s.add_argument("--yield", dest="yield_", type=float)
    s.add_argument("--level", type=float)
    r = sub.add_parser("rty")
    r.add_argument("--yields", type=float, nargs="+")
    r.add_argument("--steps")
    sub.add_parser("table")
    a = ap.parse_args()
    return {"dpmo": cmd_dpmo, "sigma": cmd_sigma, "rty": cmd_rty, "table": cmd_table}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
