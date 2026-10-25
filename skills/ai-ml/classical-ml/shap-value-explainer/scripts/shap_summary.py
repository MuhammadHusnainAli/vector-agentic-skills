#!/usr/bin/env python3
"""Global summary of SHAP values: importance, direction, shape, interactions and an additivity check.

Inputs: a SHAP CSV (one column per feature, optional base_value and prediction columns) and, optionally, the
matching feature values (same columns, same row order) - see gen_shap_script.py for exporting both.

Reports per feature:
  mean|SHAP|   global importance, and its share of the total
  mean SHAP    signed average (near 0 for centred explanations; large values mean a shifted background)
  direction    Spearman correlation between feature value and SHAP value: "higher -> raises", "lowers",
               or "mixed" (|rho| < 0.3: non-monotonic effect or interactions)
  spread       share of the SHAP variance NOT explained by the feature's own value (binned): high spread means
               the effect depends on other features; the most likely partner is the feature whose values
               correlate most with the SHAP values within chunks of similar feature values (mean |r| at least
               max(0.3, twice the chance level); the method of shap.utils.approximate_interactions). Features
               under 5% of the total importance are not interpreted (their shape is mostly noise)
Checks:
  additivity   base_value + sum(SHAP) == prediction within --tol for every row; a mismatch usually means the
               SHAP values are in a different output space (probability vs log-odds), a column is missing, or
               the explainer ran with check_additivity=False on an approximate method
  base value   constant across rows (if not, several explainers or backgrounds were mixed)

Usage:
    python shap_summary.py shap_values.csv
    python shap_summary.py shap_values.csv --features shap_features.csv --top 10
    python shap_summary.py shap_values.csv --features x.csv --json

Exit codes: 0 summarised, 1 additivity check failed, 2 usage or read error.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shap_io import load_shap, num  # noqa: E402


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    if n < 3:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def spearman(a, b):
    return pearson(ranks(a), ranks(b))


def within_bin_spread(x, s, bins=10):
    """Share of the SHAP variance left after removing the mean SHAP per value bin of x."""
    n = len(x)
    distinct = sorted(set(x))
    if len(distinct) <= bins:
        key = {v: i for i, v in enumerate(distinct)}
        b = [key[v] for v in x]
    else:
        order = sorted(range(n), key=lambda i: x[i])
        b = [0] * n
        for rank, i in enumerate(order):
            b[i] = min(bins - 1, rank * bins // n)
    sums, counts = {}, {}
    for bi, si in zip(b, s):
        sums[bi] = sums.get(bi, 0.0) + si
        counts[bi] = counts.get(bi, 0) + 1
    resid = [si - sums[bi] / counts[bi] for bi, si in zip(b, s)]
    m = sum(s) / n
    tot = sum((si - m) ** 2 for si in s)
    return sum(r * r for r in resid) / tot if tot > 0 else 0.0


def summarise(feats, shap, base, pred, xs, tol):
    n, p = len(shap), len(feats)
    cols = [[row[j] for row in shap] for j in range(p)]
    mabs = [sum(abs(v) for v in c) / n for c in cols]
    total = sum(mabs) or 1.0
    xnum = None
    if xs is not None:
        xnum = []
        for j in range(p):
            vals = [num(r[j]) for r in xs]
            ok = sum(v is not None for v in vals)
            blanks = sum(r[j] in ("", "nan", "NaN", "None") for r in xs)
            xnum.append(vals if ok >= 10 and ok + blanks == n else None)      # numeric, possibly with missing
    out = []
    for j, f in enumerate(feats):
        d = {"feature": f, "mean_abs": mabs[j], "share": mabs[j] / total, "mean": sum(cols[j]) / n}
        if xnum is not None and xnum[j] is not None:
            keep = [i for i, v in enumerate(xnum[j]) if v is not None]
            x, sj = [xnum[j][i] for i in keep], [cols[j][i] for i in keep]
            rho = spearman(x, sj)
            d["rho"] = rho
            d["direction"] = "raises" if rho >= 0.3 else ("lowers" if rho <= -0.3 else "mixed")
            if len(keep) < n:
                d["missing"] = n - len(keep)
                miss = [cols[j][i] for i in range(n) if xnum[j][i] is None]
                d["mean_shap_missing"] = sum(miss) / len(miss)
            spread = within_bin_spread(x, sj)
            d["spread"] = spread
            if spread >= 0.2 and p > 1:
                best, bc = None, 0.0
                order = sorted(range(len(keep)), key=lambda i: x[i])
                inc = max(min(len(order) // 10, 50), 5)
                for k in range(p):
                    if k == j or xnum[k] is None:
                        continue
                    cs = []                                     # |corr| within chunks of similar x values
                    for start in range(0, len(order) - inc + 1, inc):
                        idx = [keep[order[i]] for i in range(start, start + inc)]
                        pairs = [(xnum[k][i], cols[j][i]) for i in idx if xnum[k][i] is not None]
                        if len(pairs) >= 5:
                            cs.append(abs(pearson([q[0] for q in pairs], [q[1] for q in pairs])))
                    c = sum(cs) / len(cs) if cs else 0.0
                    if c > bc:
                        best, bc = feats[k], c
                null = math.sqrt(2 / (math.pi * (inc - 1)))      # expected mean |r| of unrelated features
                if best and bc >= max(0.3, 2 * null):
                    d["partner"], d["partner_corr"] = best, bc
        out.append(d)
    out.sort(key=lambda d: -d["mean_abs"])
    checks = {"rows": n}
    bases = [b for b in base if b is not None]
    if bases:
        checks["base_value"] = bases[0]
        checks["base_constant"] = max(bases) - min(bases) <= tol
    if bases and any(v is not None for v in pred):
        errs = [abs(b + sum(row) - pv) for b, row, pv in zip(base, shap, pred) if b is not None and pv is not None]
        checks["additivity_max_error"] = max(errs)
        checks["additivity_ok"] = max(errs) <= tol
        if not checks["additivity_ok"]:
            pr = [pv for pv in pred if pv is not None]
            if all(0 <= v <= 1 for v in pr) and any(b + sum(r) < 0 or b + sum(r) > 1 for b, r in zip(bases, shap)):
                checks["hint"] = ("predictions look like probabilities while SHAP values sum outside [0, 1]: the "
                                  "explanation is in log-odds; compare with the raw margin or explain the probability")
    return out, checks


def fmt(x):
    return f"{x:.4g}"


def report(out, checks, top):
    lines = [f"rows: {checks['rows']}" + (f"   base value: {fmt(checks['base_value'])}" if "base_value" in checks else "")]
    if "additivity_ok" in checks:
        lines.append(f"additivity: base + sum(SHAP) = prediction, max error {fmt(checks['additivity_max_error'])} -> "
                     + ("OK" if checks["additivity_ok"] else "FAILED"))
    if checks.get("base_constant") is False:
        lines.append("WARNING: base value varies across rows: explanations from different explainers or backgrounds")
    if checks.get("hint"):
        lines.append(f"HINT: {checks['hint']}")
    lines.append("")
    has_x = any("direction" in d for d in out)
    hdr = f"{'rank':>4}  {'feature':<24} {'mean|SHAP|':>10} {'share':>6} {'mean':>8}"
    if has_x:
        hdr += f" {'rho':>6}  direction  {'spread':>6}  partner"
    lines.append(hdr)
    for i, d in enumerate(out[:top], 1):
        s = f"{i:>4}  {d['feature']:<24} {fmt(d['mean_abs']):>10} {d['share']:>6.1%} {fmt(d['mean']):>8}"
        if has_x:
            if "direction" in d:
                s += f" {d['rho']:>6.2f}  {d['direction']:<9}  {d['spread']:>6.0%}  {d.get('partner', '')}"
            else:
                s += "    n/a  (non-numeric)"
        lines.append(s)
    if len(out) > top:
        rest = sum(d["share"] for d in out[top:])
        lines.append(f"      ... {len(out) - top} more features, {rest:.1%} of the total")
    if has_x:
        lines.append("")
        for d in out[:top]:
            if "direction" not in d:
                continue
            verb = {"raises": "higher values raise the output", "lowers": "higher values lower the output",
                    "mixed": "no single direction (non-monotonic effect or interactions)"}[d["direction"]]
            if "missing" in d:
                verb += (f"; {d['missing']} missing value(s) get a mean SHAP of {fmt(d['mean_shap_missing'])}"
                         " (missingness itself is informative)" if abs(d["mean_shap_missing"]) > d["mean_abs"] / 2
                         else f"; {d['missing']} missing value(s)")
            extra = ""
            if d["share"] < 0.05:
                extra = "; minor feature (< 5% of the total): its shape is mostly noise"
            elif d["spread"] >= 0.2:
                extra = (f"; {d['spread']:.0%} of its SHAP variance depends on other features"
                         + (f", most likely {d['partner']}" if "partner" in d
                            else " (no single partner: noise or higher-order interactions)"))
            lines.append(f"- {d['feature']}: {verb}{extra}")
    lines.append("")
    lines.append("SHAP shows how the model uses features, not causal effects; correlated features share credit.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Summarise SHAP values.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shap_csv")
    ap.add_argument("--features", help="feature values CSV aligned with the SHAP rows")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--tol", type=float, default=1e-3, help="additivity tolerance (default 1e-3)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        feats, shap, base, pred, xs = load_shap(a.shap_csv, a.features)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    out, checks = summarise(feats, shap, base, pred, xs, a.tol)
    if a.json:
        print(json.dumps({"features": out, "checks": checks}, indent=2))
    else:
        print(report(out, checks, a.top))
    return 1 if checks.get("additivity_ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
