#!/usr/bin/env python3
"""Gage R&R by the Average and Range method (AIAG MSA 4th ed. worksheet), with the range-chart check.

EV (repeatability) = R-double-bar x K1; AV (reproducibility) = sqrt((X-diff x K2)^2 - EV^2 / (n r));
PV (part variation) = R_p x K3; GRR = sqrt(EV^2 + AV^2); TV = sqrt(GRR^2 + PV^2); ndc = 1.41 PV / GRR.
K1 by trials (2: 0.8862, 3: 0.5908), K2 by operators (2: 0.7071, 3: 0.5231), K3 by parts (2-10).
Ranges above UCL_R = D4 x R-double-bar mean a measurement went wrong: re-measure before trusting the result.
This method cannot separate the operator x part interaction; use gage_rr_anova.py when that matters.

CSV columns: part, operator, value (balanced crossed study).

Usage:
    python gage_rr_xbar_r.py grr.csv --tolerance 0.018

Exit codes: 0 acceptable, 1 conditional / not acceptable / ranges out of control, 2 usage or data error.
"""

import argparse
import math
import sys
from statistics import mean

from _msa import load_crossed, verdict

K1 = {2: 0.8862, 3: 0.5908}
K2 = {2: 0.7071, 3: 0.5231}
K3 = {2: 0.7071, 3: 0.5231, 4: 0.4467, 5: 0.4030, 6: 0.3742, 7: 0.3534, 8: 0.3375, 9: 0.3249, 10: 0.3146}
D4 = {2: 3.267, 3: 2.574}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--part", default="part")
    ap.add_argument("--operator", default="operator")
    ap.add_argument("--value", default="value")
    ap.add_argument("--tolerance", type=float, help="USL - LSL (gives %%tolerance)")
    a = ap.parse_args()
    try:
        data, parts, ops, r = load_crossed(a.csv, a.part, a.operator, a.value)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    n, o = len(parts), len(ops)
    if r not in K1 or o not in K2 or n not in K3:
        print("error: the worksheet constants cover 2-3 trials, 2-3 operators and 2-10 parts; use gage_rr_anova.py", file=sys.stderr)
        return 2
    ranges = {(p, op): max(data[p][op]) - min(data[p][op]) for p in parts for op in ops}
    rbb = mean(ranges.values())
    ucl = D4[r] * rbb
    bad = [f"part {p} / {op} (R = {v:.4g})" for (p, op), v in ranges.items() if v > ucl]
    op_means = [mean(v for p in parts for v in data[p][op]) for op in ops]
    part_means = [mean(v for op in ops for v in data[p][op]) for p in parts]
    ev = rbb * K1[r]
    av = math.sqrt(max(0.0, ((max(op_means) - min(op_means)) * K2[o]) ** 2 - ev ** 2 / (n * r)))
    pv = (max(part_means) - min(part_means)) * K3[n]
    grr = math.sqrt(ev ** 2 + av ** 2)
    tv = math.sqrt(grr ** 2 + pv ** 2)
    ndc = int(1.41 * pv / grr) if grr else 99
    print(f"Average and Range Gage R&R: {n} parts x {o} operators x {r} trials")
    print(f"R-double-bar {rbb:.4g}, UCL_R {ucl:.4g}, operator mean spread {max(op_means) - min(op_means):.4g}, part range {max(part_means) - min(part_means):.4g}\n")
    print(f"{'Source':<16}{'Sigma':>11}{'%TV':>8}" + (f"{'%Tolerance':>12}" if a.tolerance else ""))
    for name, v in (("EV repeat", ev), ("AV reproduce", av), ("GRR", grr), ("PV part", pv), ("TV total", tv)):
        print(f"{name:<16}{v:>11.4g}{100 * v / tv:>7.1f}%" + (f"{100 * 6 * v / a.tolerance:>11.1f}%" if a.tolerance else ""))
    pct = 100 * 6 * grr / a.tolerance if a.tolerance else 100 * grr / tv
    v = verdict(pct, ndc)
    print(f"\nndc = {ndc}   Verdict on {'%Tolerance' if a.tolerance else '%TV'} {pct:.1f}%: {v}")
    if bad:
        print("Ranges beyond UCL_R (re-measure these before accepting the study): " + "; ".join(bad))
    return 0 if v == "ACCEPTABLE" and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
