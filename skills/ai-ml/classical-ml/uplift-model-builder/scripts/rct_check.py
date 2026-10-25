#!/usr/bin/env python3
"""Check a randomised experiment before uplift modelling: randomisation, balance, average and segment effects.

Input: CSV with a treatment indicator (1 = treated, 0 = control), a binary or numeric outcome, and
optional covariates / segments.

Reports:
  randomisation  treated share and a sample-ratio-mismatch test against --expected-share (chi-square, 1 df):
                 p < 0.001 means the assignment or the logging is broken - stop and investigate
  balance        standardised mean difference (SMD) per numeric covariate and per level of categorical ones;
                 |SMD| > 0.1 is imbalance worth explaining in a randomised test
  ATE            treated mean - control mean with a 95% CI (difference in means, Welch / Wald) and the
                 relative lift
  segments       the same effect per level of each --segments column, with CI; a heterogeneity test across
                 levels (Cochran's Q on the segment effects, df = levels - 1): uplift modelling only pays off
                 when effects differ
  power          the minimum detectable effect (80% power, 5% two-sided) for the overall comparison

Usage:
    python rct_check.py uplift.csv --treatment-col treatment --outcome-col converted --covariates age segment --segments segment
    python rct_check.py exp.csv --treatment-col variant --outcome-col revenue --expected-share 0.2 --json

Exit codes: 0 checks passed, 1 sample-ratio mismatch (p < 0.001) or a covariate with |SMD| > 0.1, 2 usage error.
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _uplift_io import chi2_sf, num  # noqa: E402


def mean_var(xs):
    n = len(xs)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / (n - 1) if n > 1 else 0.0
    return m, v


def effect(t, c):
    mt, vt = mean_var(t)
    mc, vc = mean_var(c)
    d = mt - mc
    se = math.sqrt(vt / len(t) + vc / len(c))
    return {"treated_mean": mt, "control_mean": mc, "n_treated": len(t), "n_control": len(c), "effect": d, "se": se,
            "ci": (d - 1.959964 * se, d + 1.959964 * se), "relative": d / mc if mc else None}


def main():
    ap = argparse.ArgumentParser(description="Check a randomised experiment.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--treatment-col", default="treatment")
    ap.add_argument("--outcome-col", default="converted")
    ap.add_argument("--covariates", nargs="*", default=[])
    ap.add_argument("--segments", nargs="*", default=[])
    ap.add_argument("--expected-share", type=float, default=0.5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        need = [a.treatment_col, a.outcome_col] + a.covariates + a.segments
        miss = [c for c in need if c not in rows[0]]
        if miss:
            raise ValueError(f"columns not found: {', '.join(miss)}")
        data = []
        for r in rows:
            t, y = num(r[a.treatment_col]), num(r[a.outcome_col])
            if t is None or y is None:
                continue
            if t not in (0, 1):
                raise ValueError("treatment must be 0/1")
            data.append((int(t), y, r))
        tr = [d for d in data if d[0] == 1]
        co = [d for d in data if d[0] == 0]
        if len(tr) < 2 or len(co) < 2:
            raise ValueError("need treated and control rows")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    n = len(data)
    res = {"n": n, "flags": []}
    exp_t = n * a.expected_share
    chi = (len(tr) - exp_t) ** 2 / exp_t + (len(co) - (n - exp_t)) ** 2 / (n - exp_t)
    res["srm"] = {"treated_share": len(tr) / n, "expected": a.expected_share, "chi2": chi, "p": chi2_sf(chi, 1)}
    if res["srm"]["p"] < 0.001:
        res["flags"].append(f"sample ratio mismatch: treated share {len(tr) / n:.3f} vs expected {a.expected_share} "
                            f"(p = {res['srm']['p']:.2g}) - check assignment and logging before analysing")
    res["balance"] = []
    for c in a.covariates:
        vt = [num(d[2][c]) for d in tr]
        vc = [num(d[2][c]) for d in co]
        if all(v is not None for v in vt + vc):
            mt, s2t = mean_var(vt)
            mc, s2c = mean_var(vc)
            pooled = math.sqrt((s2t + s2c) / 2) or 1.0
            res["balance"].append({"covariate": c, "smd": (mt - mc) / pooled})
        else:
            levels = sorted({d[2][c] for d in data})
            for lv in levels:
                pt = sum(1 for d in tr if d[2][c] == lv) / len(tr)
                pc = sum(1 for d in co if d[2][c] == lv) / len(co)
                pooled = math.sqrt((pt * (1 - pt) + pc * (1 - pc)) / 2) or 1.0
                res["balance"].append({"covariate": f"{c}={lv}", "smd": (pt - pc) / pooled})
    for b in res["balance"]:
        if abs(b["smd"]) > 0.1:
            res["flags"].append(f"imbalance on {b['covariate']} (SMD {b['smd']:+.3f})")
    res["ate"] = effect([d[1] for d in tr], [d[1] for d in co])
    sd_pooled = math.sqrt((mean_var([d[1] for d in tr])[1] + mean_var([d[1] for d in co])[1]) / 2)
    res["mde"] = (1.959964 + 0.841621) * sd_pooled * math.sqrt(1 / len(tr) + 1 / len(co))
    res["segments"] = {}
    for c in a.segments:
        by = defaultdict(lambda: ([], []))
        for t, y, r in data:
            by[r[c]][0 if t else 1].append(y)
        effs = {}
        for lv, (yt, yc) in sorted(by.items()):
            if len(yt) >= 2 and len(yc) >= 2:
                effs[lv] = effect(yt, yc)
        ws = [(e["effect"], 1 / e["se"] ** 2) for e in effs.values() if e["se"] > 0]
        q = p = None
        if len(ws) >= 2:
            pooled = sum(e * w for e, w in ws) / sum(w for _, w in ws)
            q = sum(w * (e - pooled) ** 2 for e, w in ws)
            p = chi2_sf(q, len(ws) - 1)
        res["segments"][c] = {"effects": effs, "q": q, "df": len(ws) - 1, "p": p}
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        s = res["srm"]
        print(f"n {n}   treated {len(tr)} ({s['treated_share']:.1%}, expected {a.expected_share:.0%})   "
              f"SRM chi2 {s['chi2']:.3f} p {s['p']:.3g}")
        if res["balance"]:
            print("balance (SMD treated vs control): " + ", ".join(f"{b['covariate']} {b['smd']:+.3f}" for b in res["balance"]))
        e = res["ate"]
        rel = f", relative {e['relative']:+.1%}" if e["relative"] is not None else ""
        print(f"ATE: treated {e['treated_mean']:.4f} vs control {e['control_mean']:.4f} -> {e['effect']:+.4f} "
              f"[95% CI {e['ci'][0]:+.4f}, {e['ci'][1]:+.4f}]{rel}   (MDE at 80% power: {res['mde']:.4f})")
        for c, d in res["segments"].items():
            print(f"\nby {c}:")
            for lv, e in d["effects"].items():
                sig = "  *" if e["ci"][0] > 0 or e["ci"][1] < 0 else ""
                print(f"  {lv:<12} n {e['n_treated']}/{e['n_control']}   effect {e['effect']:+.4f} "
                      f"[{e['ci'][0]:+.4f}, {e['ci'][1]:+.4f}]{sig}")
            if d["q"] is not None:
                verdict = ("effects differ: uplift modelling / targeting can help" if d["p"] < 0.05
                           else "no evidence that effects differ")
                print(f"  heterogeneity: Q = {d['q']:.3f}, df = {d['df']}, p = {d['p']:.4g} -> {verdict}")
        for fl in res["flags"]:
            print(f"FLAG: {fl}")
    return 1 if res["flags"] else 0


if __name__ == "__main__":
    sys.exit(main())
