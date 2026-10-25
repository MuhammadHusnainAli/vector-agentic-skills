#!/usr/bin/env python3
"""Process capability: Cp, Cpk, Pp, Ppk, Cpm, expected and observed ppm, a confidence interval for Cpk,
and an Anderson-Darling normality check, from a column of measurements.

Within-subgroup sigma (Cp, Cpk): R-bar/d2 with --subgroup or --size (n = 2..10), pooled S for n > 10,
or MR-bar/1.128 for individuals. Overall sigma (Pp, Ppk): sample standard deviation.
One-sided specifications are supported (give only --lsl or --usl). --method percentile uses the 0.135% and
99.865% empirical percentiles (ISO 22514-2 style) for non-normal data; it needs several hundred values.

Usage:
    python capability.py bore.csv --value diameter --lsl 12.000 --usl 12.018 --subgroup hour
    python capability.py flatness.csv --value flatness --usl 0.05 --target-index 1.67
    python capability.py data.csv --value x --lsl 10 --usl 20 --target 15 --method percentile --json

Exit codes: 0 Cpk (or Ppk) meets --target-index, 1 below target or not normal, 2 usage or data error.
"""

import argparse
import csv
import json
import math
import sys
from statistics import NormalDist, mean, stdev

D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}
N = NormalDist()


def c4(n):
    return math.sqrt(2 / (n - 1)) * math.exp(math.lgamma(n / 2) - math.lgamma((n - 1) / 2))


def within_sigma(values, groups):
    if groups and len(groups[0]) > 1:
        n = len(groups[0])
        if n <= 10:
            return mean(max(g) - min(g) for g in groups) / D2[n], f"R-bar/d2 (n={n})"
        s2 = sum(stdev(g) ** 2 * (len(g) - 1) for g in groups) / sum(len(g) - 1 for g in groups)
        return math.sqrt(s2) / c4(sum(len(g) - 1 for g in groups) + 1), f"pooled S (n={n})"
    mr = [abs(b - a) for a, b in zip(values, values[1:])]
    return mean(mr) / D2[2], "MR-bar/1.128 (individuals)"


def anderson_darling(values):
    """A^2* (small-sample adjusted) and approximate p-value (D'Agostino & Stephens 1986)."""
    x = sorted(values)
    n = len(x)
    m, s = mean(x), stdev(x)
    if s == 0:
        return float("inf"), 0.0
    cdf = [min(max(N.cdf((v - m) / s), 1e-12), 1 - 1e-12) for v in x]
    a2 = -n - sum((2 * i + 1) * (math.log(cdf[i]) + math.log(1 - cdf[n - 1 - i])) for i in range(n)) / n
    a = a2 * (1 + 0.75 / n + 2.25 / n ** 2)
    if a >= 0.6:
        p = math.exp(1.2937 - 5.709 * a + 0.0186 * a * a)
    elif a >= 0.34:
        p = math.exp(0.9177 - 4.279 * a - 1.38 * a * a)
    elif a >= 0.2:
        p = 1 - math.exp(-8.318 + 42.796 * a - 59.938 * a * a)
    else:
        p = 1 - math.exp(-13.436 + 101.14 * a - 223.73 * a * a)
    return a, min(max(p, 0.0), 1.0)


def percentile(sorted_x, q):
    pos = q * (len(sorted_x) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_x) - 1)
    return sorted_x[lo] + (sorted_x[hi] - sorted_x[lo]) * (pos - lo)


def indices(mu, sigma, lsl, usl):
    cp = (usl - lsl) / (6 * sigma) if lsl is not None and usl is not None else None
    cpl = (mu - lsl) / (3 * sigma) if lsl is not None else None
    cpu = (usl - mu) / (3 * sigma) if usl is not None else None
    k = min(v for v in (cpl, cpu) if v is not None)
    ppm = 1e6 * ((N.cdf((lsl - mu) / sigma) if lsl is not None else 0) + (1 - N.cdf((usl - mu) / sigma) if usl is not None else 0))
    return cp, k, ppm


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--value", required=True)
    ap.add_argument("--lsl", type=float)
    ap.add_argument("--usl", type=float)
    ap.add_argument("--target", type=float, help="nominal for Cpm")
    ap.add_argument("--subgroup", help="subgroup column for within sigma")
    ap.add_argument("--size", type=int, help="consecutive subgroup size for within sigma")
    ap.add_argument("--target-index", type=float, default=1.33, help="required Cpk/Ppk (default 1.33; 1.67 for new processes)")
    ap.add_argument("--confidence", type=float, default=0.95)
    ap.add_argument("--method", choices=["normal", "percentile"], default="normal")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.lsl is None and a.usl is None:
        print("error: give --lsl and/or --usl", file=sys.stderr)
        return 2
    if a.lsl is not None and a.usl is not None and a.lsl >= a.usl:
        print("error: --lsl must be below --usl", file=sys.stderr)
        return 2
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        vals = [float(r[a.value]) for r in rows if (r.get(a.value) or "").strip()]
    except (OSError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(vals) < 25:
        print(f"error: {len(vals)} values; capability needs at least 25 (100+ recommended)", file=sys.stderr)
        return 2
    groups = None
    if a.subgroup:
        g = {}
        for r in rows:
            if (r.get(a.value) or "").strip():
                g.setdefault(r[a.subgroup], []).append(float(r[a.value]))
        groups = [v for v in g.values() if len(v) == len(next(iter(g.values())))]
    elif a.size and a.size > 1:
        groups = [vals[i:i + a.size] for i in range(0, len(vals) - a.size + 1, a.size)]
    n, mu, s_all = len(vals), mean(vals), stdev(vals)
    s_within, how = within_sigma(vals, groups)
    cp, cpk, ppm_w = indices(mu, s_within, a.lsl, a.usl)
    pp, ppk, ppm_o = indices(mu, s_all, a.lsl, a.usl)
    obs = sum((a.lsl is not None and v < a.lsl) or (a.usl is not None and v > a.usl) for v in vals)
    z = N.inv_cdf(1 - (1 - a.confidence) / 2)
    half = z * math.sqrt(1 / (9 * n) + cpk ** 2 / (2 * (n - 1)))      # Bissell (1990)
    ad, p_ad = anderson_darling(vals)
    res = {"n": n, "mean": mu, "sigma_within": s_within, "sigma_within_method": how, "sigma_overall": s_all,
           "Cp": cp, "Cpk": cpk, "Pp": pp, "Ppk": ppk, "ppm_within": ppm_w, "ppm_overall": ppm_o,
           "ppm_observed": 1e6 * obs / n, "Cpk_ci": [cpk - half, cpk + half], "AD": ad, "AD_p": p_ad}
    if a.target is not None and cp is not None:
        res["Cpm"] = (a.usl - a.lsl) / (6 * math.sqrt(s_all ** 2 + (mu - a.target) ** 2))
    if a.method == "percentile":
        xs = sorted(vals)
        p_lo, p50, p_hi = percentile(xs, 0.00135), percentile(xs, 0.5), percentile(xs, 0.99865)
        parts = []
        if a.lsl is not None:
            parts.append((p50 - a.lsl) / (p50 - p_lo))
        if a.usl is not None:
            parts.append((a.usl - p50) / (p_hi - p50))
        res["Ppk_percentile"] = min(parts)
        if cp is not None:
            res["Pp_percentile"] = (a.usl - a.lsl) / (p_hi - p_lo)
    key = "Ppk_percentile" if a.method == "percentile" else "Cpk"
    ok = res[key] >= a.target_index and (a.method == "percentile" or p_ad >= 0.05)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0 if ok else 1
    f = lambda v: "-" if v is None else f"{v:.2f}"
    print(f"n = {n}   mean = {mu:.6g}   sigma within = {s_within:.5g} [{how}]   sigma overall = {s_all:.5g}")
    print(f"Spec: LSL {a.lsl if a.lsl is not None else '-'}  USL {a.usl if a.usl is not None else '-'}\n")
    print(f"Cp  {f(cp):>6}   Cpk {f(cpk):>6}   ({a.confidence:.0%} CI {cpk - half:.2f} to {cpk + half:.2f})")
    print(f"Pp  {f(pp):>6}   Ppk {f(ppk):>6}" + (f"   Cpm {res['Cpm']:.2f}" if "Cpm" in res else ""))
    if a.method == "percentile":
        print(f"Percentile method: Pp {f(res.get('Pp_percentile'))}  Ppk {res['Ppk_percentile']:.2f}")
    print(f"Expected ppm: within {ppm_w:,.0f}   overall {ppm_o:,.0f}   observed {res['ppm_observed']:,.0f}")
    print(f"Normality (Anderson-Darling): A2* = {ad:.3f}, p = {p_ad:.3f}" + ("  -> NOT normal" if p_ad < 0.05 else ""))
    if p_ad < 0.05 and a.method == "normal":
        print("  Normal-based indices and ppm are unreliable: find the cause (mixture, drift, skew), or use "
              "--method percentile / a Box-Cox transform.")
    if cp is not None and cpk < 0.75 * cp:
        print(f"  Process is off-centre: centring at {(a.lsl + a.usl) / 2:.6g} would raise Cpk to about {cp:.2f}.")
    if ppk < 0.85 * cpk:
        print("  Ppk well below Cpk: between-subgroup variation (shifts, drift) - check the control chart.")
    if obs and res["ppm_observed"] > 3 * max(ppm_o, 1):
        print(f"  Observed {obs} out-of-spec value(s) - far more than the normal model predicts: special causes or heavy tails.")
    print("  Indices are valid only for a process in statistical control: check the control chart first.")
    label = "Ppk (percentile)" if a.method == "percentile" else "Cpk"
    print(f"\n{label} {res[key]:.2f} vs required {a.target_index:g}: " + ("CAPABLE" if ok else "NOT CAPABLE / NOT VALID"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
