#!/usr/bin/env python3
"""Analyse ICE curves: the partial dependence they average to, and what the average hides.

Input: a long CSV with one row per (row_id, grid value) and the model prediction when the feature is set to
that value for that row (as written by the gen_pdp_script.py output, or sklearn partial_dependence with
kind="individual"):
    row_id,tenure_months,prediction
The grid column is the column that is not row_id/prediction (or --feature). A non-numeric grid is treated as
categorical levels in file order (centred on the first level).

Reports:
  pdp          mean prediction per grid value; total change, monotonicity (share of steps in the main
               direction) and the steepest segment (threshold-like effects)
  heterogeneity centred ICE (each curve minus its value at the first grid point): the spread of the end
               points relative to the PDP's range; share of rows going up, down and flat
  opposite     when >= 10% of rows move against the PDP's direction by more than the noise, the PDP hides
               opposite effects: an interaction
  subgroups    otherwise, an exact two-group split of the curves' total changes; reported when the groups
               are >= 3 pooled sds apart, the smaller holds >= 10% of rows and the gap is >= 20% of the PDP
               range: two strengths of the same effect
  separators   with --features (one row per row_id), the features that best separate the up/down curves or
               the two subgroups (AUC of each feature for the group label)
  support      with --features containing the PDP feature, grid points outside the 5th-95th percentile of
               the observed values are marked low-support: the curve there is extrapolation

Usage:
    python ice_analysis.py ice_tenure.csv
    python ice_analysis.py ice.csv --features rows.csv --id-col row_id
    python ice_analysis.py ice.csv --feature tenure_months --json

Exit codes: 0 analysed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def auc(scores, labels):
    """Mann-Whitney AUC of scores for label 1 vs 0 (ties count half)."""
    pairs = sorted(zip(scores, labels))
    n1 = sum(labels)
    n0 = len(labels) - n1
    if not n1 or not n0:
        return 0.5
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        rank_sum += r * sum(lab for _, lab in pairs[i:j + 1])
        i = j + 1
    return (rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0)


def quantile(xs, q):
    s = sorted(xs)
    k = (len(s) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def two_groups(values):
    """Exact 1-D 2-means: returns (threshold, mean_low, mean_high, n_low, n_high, separation in pooled sds)."""
    v = sorted(values)
    n = len(v)
    best = None
    for k in range(1, n):
        a, b = v[:k], v[k:]
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        ss = sum((x - ma) ** 2 for x in a) + sum((x - mb) ** 2 for x in b)
        if best is None or ss < best[0]:
            best = (ss, k, ma, mb)
    ss, k, ma, mb = best
    pooled = math.sqrt(ss / max(1, n - 2)) or 1e-12
    return (v[k - 1] + v[k]) / 2, ma, mb, k, n - k, (mb - ma) / pooled


def load_ice(path, id_col, feature, pred_col):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    cols = list(rows[0])
    for c in (id_col, pred_col):
        if c not in cols:
            raise ValueError(f"column {c!r} not found (have: {', '.join(cols)})")
    feature = feature or next((c for c in cols if c not in (id_col, pred_col)), None)
    if feature not in cols:
        raise ValueError(f"grid column {feature!r} not found")
    numeric = all(num(r[feature]) is not None for r in rows if r[feature] != "")
    curves = defaultdict(dict)
    levels = []                                          # categorical grids keep their order of appearance
    for r in rows:
        g = num(r[feature]) if numeric else r[feature]
        p = num(r[pred_col])
        if g is None or g == "" or p is None:
            continue
        if g not in curves[r[id_col]] and g not in levels:
            levels.append(g)
        curves[r[id_col]][g] = p
    grid = sorted(levels) if numeric else levels
    curves = {k: [v[g] for g in grid] for k, v in curves.items() if len(v) == len(grid)}
    if len(grid) < 2 or len(curves) < 5:
        raise ValueError("need at least 2 grid values and 5 complete curves")
    return feature, grid, curves, numeric


def analyse(feature, grid, curves, feats=None, id_col="row_id", numeric=True):
    ids = list(curves)
    labels_grid = grid
    if not numeric:
        grid = list(range(len(grid)))                    # categorical levels as positions
    m = len(grid)
    pdp = [sum(curves[i][k] for i in ids) / len(ids) for k in range(m)]
    total = pdp[-1] - pdp[0]
    rng = max(pdp) - min(pdp)
    steps = [pdp[k + 1] - pdp[k] for k in range(m - 1)]
    main_dir = 1 if total >= 0 else -1
    mono = sum(1 for d in steps if d * main_dir >= 0) / len(steps)
    ks = max(range(m - 1), key=lambda k: abs(steps[k]) / max(grid[k + 1] - grid[k], 1e-12)) if m > 1 else 0
    ends = {i: curves[i][-1] - curves[i][0] for i in ids}
    # noise: typical step-to-step wiggle of individual curves around their own trend
    wiggle = []
    for i in ids:
        c = curves[i]
        for k in range(1, m - 1 if numeric else 1):     # categorical levels have no neighbours to smooth
            wiggle.append(abs(c[k] - (c[k - 1] + c[k + 1]) / 2))
    noise = (sum(wiggle) / len(wiggle)) * 2 if wiggle else 0.0
    tol = max(noise, 0.1 * rng, 1e-9)
    up = [i for i in ids if ends[i] > tol]
    down = [i for i in ids if ends[i] < -tol]
    flat = [i for i in ids if -tol <= ends[i] <= tol]
    ev = list(ends.values())
    mean_e = sum(ev) / len(ev)
    sd_e = math.sqrt(sum((e - mean_e) ** 2 for e in ev) / max(1, len(ev) - 1))
    res = {"feature": feature, "grid": labels_grid, "numeric": numeric, "pdp": pdp, "total_change": total, "pdp_range": rng,
           "monotonic_share": mono, "steepest": {"from": labels_grid[ks], "to": labels_grid[ks + 1], "change": steps[ks]},
           "curves": len(ids), "up": len(up), "down": len(down), "flat": len(flat),
           "end_spread_sd": sd_e, "heterogeneity": sd_e / rng if rng > 0 else float("inf"), "warnings": []}
    against = down if main_dir > 0 else up
    res["against_share"] = len(against) / len(ids)
    res["opposite"] = res["against_share"] >= 0.10
    thr, ma, mb, na, nb, sep = two_groups(ev)
    res["subgroups"] = None
    if not res["opposite"] and sep >= 3 and min(na, nb) >= max(3, 0.1 * len(ids)) and abs(mb - ma) >= 0.2 * rng:
        res["subgroups"] = {"threshold": thr, "low_mean": ma, "high_mean": mb, "n_low": na, "n_high": nb,
                            "separation": sep}
    if feats:
        if res["opposite"]:
            labels = {i: 1 for i in up}
            labels.update({i: 0 for i in down})
        elif res["subgroups"]:
            labels = {i: int(ends[i] > thr) for i in ids}       # 1 = the group with the larger change
        else:
            labels = {}
        cand = []
        cols = [c for c in next(iter(feats.values())) if c != id_col]
        for c in cols:
            if c == feature:
                continue
            xs, ys = [], []
            for i, lab in labels.items():
                v = num(feats.get(i, {}).get(c))
                if v is not None:
                    xs.append(v)
                    ys.append(lab)
            if len(set(ys)) == 2 and len(xs) >= 10:
                a = auc(xs, ys)
                if abs(a - 0.5) >= 0.2:                 # AUC >= 0.7 or <= 0.3: weaker is often chance
                    cand.append((abs(a - 0.5), c, a))
        cand.sort(reverse=True)
        res["separators"] = [{"feature": c, "auc_up": a} for _, c, a in cand[:3]]
        if feature in cols and numeric:
            obs = [num(r.get(feature)) for r in feats.values()]
            obs = [v for v in obs if v is not None]
            if len(obs) >= 10:
                lo, hi = quantile(obs, 0.05), quantile(obs, 0.95)
                eps = 0.01 * (hi - lo)                  # sklearn grids end exactly at these percentiles
                low = [g for g in grid if g < lo - eps or g > hi + eps]
                res["support"] = {"p05": lo, "p95": hi, "low_support_grid": low}
                if low:
                    res["warnings"].append(f"{len(low)} grid value(s) outside the 5th-95th percentile "
                                           f"[{lo:.4g}, {hi:.4g}]: the curve there is extrapolation")
    if rng > 0 and res["heterogeneity"] > 1:
        res["warnings"].append("individual curves spread more than the PDP moves: the average is a poor summary; "
                               "show centred ICE")
    return res


def fmt(x):
    return f"{x:.4g}"


def report(r):
    lines = [f"feature: {r['feature']}   curves: {r['curves']}   grid points: {len(r['grid'])}", "",
             f"{'value':>10} {'PDP':>9}"]
    for g, p in zip(r["grid"], r["pdp"]):
        lines.append(f"{fmt(g) if r['numeric'] else str(g)[:10]:>10} {fmt(p):>9}")
    lines.append("")
    st = r["steepest"]
    if r["numeric"]:
        direction = "increases" if r["total_change"] > 0 else "decreases"
        lines.append(f"PDP {direction} by {fmt(abs(r['total_change']))} over the grid (range {fmt(r['pdp_range'])}); "
                     f"{r['monotonic_share']:.0%} of steps go the same way")
        lines.append(f"steepest segment: {fmt(st['from'])} -> {fmt(st['to'])} ({st['change']:+.4g})")
    else:
        hi = max(range(len(r["pdp"])), key=r["pdp"].__getitem__)
        lo = min(range(len(r["pdp"])), key=r["pdp"].__getitem__)
        lines.append(f"levels differ by up to {fmt(r['pdp_range'])}: highest {r['grid'][hi]}, lowest {r['grid'][lo]}; "
                     f"ICE groups below compare the last level with the first ({r['grid'][0]})")
    lines.append(f"centred ICE: {r['up']} up, {r['down']} down, {r['flat']} flat; end-point spread sd "
                 f"{fmt(r['end_spread_sd'])} ({r['heterogeneity']:.2f} x the PDP range)")
    if r["opposite"]:
        lines.append(f"OPPOSITE EFFECTS: {r['against_share']:.0%} of rows move against the PDP: the average hides an "
                     "interaction; plot centred ICE coloured by the separating feature")
        for s in r.get("separators", []):
            side = "higher" if s["auc_up"] > 0.5 else "lower"
            lines.append(f"  separator: {s['feature']} (AUC {s['auc_up']:.2f}: up-curves have {side} {s['feature']})")
    elif r.get("subgroups"):
        g = r["subgroups"]
        lines.append(f"SUBGROUPS: two groups of curves with different strength: {g['n_low']} rows change by "
                     f"{g['low_mean']:+.4g}, {g['n_high']} rows by {g['high_mean']:+.4g} (separation {g['separation']:.1f} "
                     "sd): the PDP averages two behaviours; an interaction is likely")
        for s in r.get("separators", []):
            side = "higher" if s["auc_up"] > 0.5 else "lower"
            lines.append(f"  separator: {s['feature']} (AUC {s['auc_up']:.2f}: the {g['high_mean']:+.4g} group has "
                         f"{side} {s['feature']})")
    else:
        lines.append("curves mostly agree with the PDP: the average is a fair summary")
    for w in r["warnings"]:
        lines.append(f"WARNING: {w}")
    lines.append("")
    lines.append("PDP/ICE show the model's response when only this feature changes; with correlated features "
                 "that includes unrealistic rows (prefer ALE) and it is never a causal effect.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Analyse ICE curves.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--feature", help="grid column (default: the non-id, non-prediction column)")
    ap.add_argument("--id-col", default="row_id")
    ap.add_argument("--pred-col", default="prediction")
    ap.add_argument("--features", help="CSV with one row per row_id: original feature values")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        feature, grid, curves, numeric = load_ice(a.csv, a.id_col, a.feature, a.pred_col)
        feats = None
        if a.features:
            with open(a.features, newline="", encoding="utf-8") as f:
                fr = list(csv.DictReader(f))
            if not fr or a.id_col not in fr[0]:
                raise ValueError(f"features file needs an {a.id_col!r} column")
            feats = {r[a.id_col]: r for r in fr}
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    r = analyse(feature, grid, curves, feats, a.id_col, numeric)
    print(json.dumps(r, indent=2) if a.json else report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
