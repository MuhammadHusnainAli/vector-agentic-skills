#!/usr/bin/env python3
"""Crossed Gage R&R by the ANOVA method (AIAG MSA 4th ed.): variance components, %contribution, %study
variation, %tolerance, number of distinct categories (ndc), and the operator x part interaction test.

The interaction term is pooled into repeatability when its p-value exceeds --alpha-interaction (default 0.25,
as in AIAG and Minitab). Study variation uses 6 sigma (--k 5.15 for the older 99% convention).

CSV columns: part, operator, value (one row per measurement; balanced: every operator measures every part the
same number of times). Use --part/--operator/--value to rename.

Usage:
    python gage_rr_anova.py grr.csv --tolerance 0.018
    python gage_rr_anova.py grr.csv --lsl 12.000 --usl 12.018 --json

Exit codes: 0 acceptable, 1 conditional or not acceptable, 2 usage or data error.
"""

import argparse
import json
import math
import sys
from statistics import mean

from _msa import load_crossed, verdict


def betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * betacf(a, b, x) / a
    return 1 - math.exp(lbt) * betacf(b, a, 1 - x) / b


def f_pvalue(f, d1, d2):
    return 1 - betainc(d1 / 2, d2 / 2, d1 * f / (d1 * f + d2)) if f > 0 else 1.0


def anova(data, parts, ops, r):
    p, o = len(parts), len(ops)
    allv = [v for pt in parts for op in ops for v in data[pt][op]]
    gm = mean(allv)
    pm = {pt: mean(v for op in ops for v in data[pt][op]) for pt in parts}
    om = {op: mean(v for pt in parts for v in data[pt][op]) for op in ops}
    cm = {(pt, op): mean(data[pt][op]) for pt in parts for op in ops}
    ss_p = o * r * sum((pm[x] - gm) ** 2 for x in parts)
    ss_o = p * r * sum((om[x] - gm) ** 2 for x in ops)
    ss_po = r * sum((cm[(pt, op)] - pm[pt] - om[op] + gm) ** 2 for pt in parts for op in ops)
    ss_e = sum((v - cm[(pt, op)]) ** 2 for pt in parts for op in ops for v in data[pt][op])
    df = {"part": p - 1, "operator": o - 1, "interaction": (p - 1) * (o - 1), "repeat": p * o * (r - 1)}
    ms = {"part": ss_p / df["part"], "operator": ss_o / df["operator"], "interaction": ss_po / df["interaction"],
          "repeat": ss_e / df["repeat"]}
    f_po = ms["interaction"] / ms["repeat"] if ms["repeat"] else float("inf")
    return ss_p, ss_o, ss_po, ss_e, df, ms, f_po


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--part", default="part")
    ap.add_argument("--operator", default="operator")
    ap.add_argument("--value", default="value")
    ap.add_argument("--tolerance", type=float, help="USL - LSL")
    ap.add_argument("--lsl", type=float)
    ap.add_argument("--usl", type=float)
    ap.add_argument("--k", type=float, default=6.0, help="study variation multiplier (6, or 5.15)")
    ap.add_argument("--alpha-interaction", type=float, default=0.25)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        data, parts, ops, r = load_crossed(a.csv, a.part, a.operator, a.value)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    tol = a.tolerance if a.tolerance else (a.usl - a.lsl if a.usl is not None and a.lsl is not None else None)
    p, o = len(parts), len(ops)
    ss_p, ss_o, ss_po, ss_e, df, ms, f_po = anova(data, parts, ops, r)
    p_po = f_pvalue(f_po, df["interaction"], df["repeat"])
    pooled = p_po > a.alpha_interaction
    if pooled:
        mse = (ss_po + ss_e) / (df["interaction"] + df["repeat"])
        var = {"repeatability": mse, "operator": max(0.0, (ms["operator"] - mse) / (p * r)), "interaction": 0.0,
               "part": max(0.0, (ms["part"] - mse) / (o * r))}
    else:
        var = {"repeatability": ms["repeat"], "operator": max(0.0, (ms["operator"] - ms["interaction"]) / (p * r)),
               "interaction": max(0.0, (ms["interaction"] - ms["repeat"]) / r),
               "part": max(0.0, (ms["part"] - ms["interaction"]) / (o * r))}
    var["reproducibility"] = var["operator"] + var["interaction"]
    var["grr"] = var["repeatability"] + var["reproducibility"]
    var["total"] = var["grr"] + var["part"]
    rows = []
    for k in ("grr", "repeatability", "reproducibility", "operator", "interaction", "part", "total"):
        sd = math.sqrt(var[k])
        rows.append((k, var[k], 100 * var[k] / var["total"], 100 * sd / math.sqrt(var["total"]),
                     100 * a.k * sd / tol if tol else None))
    ndc = int(1.41 * math.sqrt(var["part"]) / math.sqrt(var["grr"])) if var["grr"] else 99
    pct = rows[0][4] if tol else rows[0][3]
    v = verdict(pct, ndc)
    if a.json:
        print(json.dumps({"parts": p, "operators": o, "trials": r, "interaction_p": p_po, "interaction_pooled": pooled,
                          "components": {k: {"variance": vv, "pct_contribution": c, "pct_study_var": s, "pct_tolerance": t}
                                         for k, vv, c, s, t in rows}, "ndc": ndc, "verdict": v}, indent=2))
        return 0 if v == "ACCEPTABLE" else 1
    print(f"Crossed Gage R&R (ANOVA): {p} parts x {o} operators x {r} trials\n")
    print(f"Operator x part interaction: F = {f_po:.3f}, p = {p_po:.3f} -> " +
          ("pooled into repeatability" if pooled else "significant, kept in the model"))
    print(f"\n{'Source':<17}{'Variance':>12}{'%Contrib':>10}{'%StudyVar':>11}" + (f"{'%Tolerance':>12}" if tol else ""))
    names = {"grr": "Total Gage R&R", "repeatability": "  Repeatability", "reproducibility": "  Reproducibility",
             "operator": "    Operator", "interaction": "    Oper x Part", "part": "Part-to-part", "total": "Total variation"}
    for k, vv, c, s, t in rows:
        if k == "interaction" and pooled:
            continue
        print(f"{names[k]:<17}{vv:>12.4g}{c:>9.1f}%{s:>10.1f}%" + (f"{t:>11.1f}%" if t is not None else ""))
    print(f"\nNumber of distinct categories (ndc): {ndc}")
    basis = "%Tolerance" if tol else "%Study variation"
    print(f"Verdict on {basis} {pct:.1f}% and ndc {ndc}: {v}")
    if var["repeatability"] > 2 * var["reproducibility"]:
        print("Repeatability dominates: the gauge itself (fixture, resolution, wear, method) needs attention.")
    elif var["reproducibility"] > 2 * var["repeatability"]:
        print("Reproducibility dominates: operators measure differently - standardise the method and train.")
    return 0 if v == "ACCEPTABLE" else 1


if __name__ == "__main__":
    sys.exit(main())
