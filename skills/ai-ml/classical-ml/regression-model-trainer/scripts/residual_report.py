#!/usr/bin/env python3
"""Diagnose a regression model from its predictions: where it is biased, where errors grow, what it misses.

Input CSV with y_true and y_pred (names configurable), optionally a segment column, extra feature
columns to slice by, and lower/upper prediction-interval columns. Reports:
  metrics        MAE, RMSE, MedAE, bias (mean error), R2, WAPE
  calibration    mean prediction vs mean actual per decile of the prediction (a well-calibrated
                 regressor has ratio ~1.0 in every decile; systematic under-prediction of large
                 values is the most common failure)
  spread         correlation of |residual| with the prediction (heteroscedasticity): > 0.3 means
                 errors grow with the level; model log(y) or use a Gamma/Tweedie loss, report WAPE
  segments       MAE and bias per --segment value and per quartile of each --slice-by column
  intervals      coverage and mean width of [--lower, --upper] vs --nominal
  worst rows     the --top largest absolute errors with their row number
  gates          --max-abs-bias-pct P exits 1 if any decile or segment is biased by more than P%

Usage:
    python residual_report.py preds.csv
    python residual_report.py preds.csv --segment region --slice-by sqft year_built --top 5
    python residual_report.py preds.csv --lower p10 --upper p90 --nominal 0.8
    python residual_report.py preds.csv --max-abs-bias-pct 10 --json

Exit codes: 0 report printed (gates pass), 1 a bias gate failed, 2 usage or read error.
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


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return 0.0 if not va or not vb else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb)


def group_stats(pairs):
    n = len(pairs)
    err = [p - t for t, p in pairs]
    st = sum(t for t, _ in pairs)
    return {"n": n, "mae": sum(abs(e) for e in err) / n, "bias": sum(err) / n,
            "bias_pct": (sum(err) / st * 100) if st else None,
            "mean_true": st / n, "mean_pred": sum(p for _, p in pairs) / n}


def main():
    ap = argparse.ArgumentParser(description="Residual diagnostics for regression predictions.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--true-col", default="y_true")
    ap.add_argument("--pred-col", default="y_pred")
    ap.add_argument("--segment")
    ap.add_argument("--slice-by", nargs="*", default=[])
    ap.add_argument("--lower")
    ap.add_argument("--upper")
    ap.add_argument("--nominal", type=float, default=0.8)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--max-abs-bias-pct", type=float)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            need = [a.true_col, a.pred_col, a.segment, a.lower, a.upper, *a.slice_by]
            miss = [c for c in need if c and c not in cols]
            if miss:
                raise ValueError(f"missing column(s) {miss}")
            rows = [r for r in reader if num(r[a.true_col]) is not None and num(r[a.pred_col]) is not None]
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(rows) < 10:
        print("error: fewer than 10 rows with numeric y_true and y_pred", file=sys.stderr)
        return 2
    y = [num(r[a.true_col]) for r in rows]
    p = [num(r[a.pred_col]) for r in rows]
    n = len(y)
    err = [pi - yi for yi, pi in zip(y, p)]
    ae = sorted(abs(e) for e in err)
    mean_y = sum(y) / n
    sst = sum((v - mean_y) ** 2 for v in y)
    out = {"rows": n, "metrics": {
        "mae": sum(ae) / n, "rmse": math.sqrt(sum(e * e for e in err) / n), "medae": ae[n // 2],
        "bias": sum(err) / n, "r2": 1 - sum(e * e for e in err) / sst if sst else None,
        "wape": sum(ae) / sum(abs(v) for v in y) if any(y) else None}}
    order = sorted(range(n), key=lambda i: p[i])
    dec = []
    for d in range(10):
        idx = order[d * n // 10:(d + 1) * n // 10]
        if idx:
            g = group_stats([(y[i], p[i]) for i in idx])
            g["decile"] = d + 1
            g["ratio_pred_true"] = g["mean_pred"] / g["mean_true"] if g["mean_true"] else None
            dec.append(g)
    out["deciles"] = dec
    out["spread_corr"] = pearson(p, [abs(e) for e in err])
    segs = {}
    if a.segment:
        groups = defaultdict(list)
        for r, yi, pi in zip(rows, y, p):
            groups[r[a.segment]].append((yi, pi))
        segs[a.segment] = {k: group_stats(v) for k, v in sorted(groups.items())}
    for c in a.slice_by:
        vals = [(num(r[c]), yi, pi) for r, yi, pi in zip(rows, y, p) if num(r[c]) is not None]
        vals.sort(key=lambda t: t[0])
        m = len(vals)
        segs[c] = {}
        for qi in range(4):
            part = vals[qi * m // 4:(qi + 1) * m // 4]
            if part:
                segs[c][f"Q{qi + 1} [{part[0][0]:g}, {part[-1][0]:g}]"] = group_stats([(t, q) for _, t, q in part])
    out["segments"] = segs
    if a.lower and a.upper:
        lo = [num(r[a.lower]) for r in rows]
        hi = [num(r[a.upper]) for r in rows]
        inside = [l is not None and h is not None and l <= t <= h for l, h, t in zip(lo, hi, y)]
        widths = [h - l for l, h in zip(lo, hi) if l is not None and h is not None]
        out["intervals"] = {"coverage": sum(inside) / n, "nominal": a.nominal,
                            "mean_width": sum(widths) / len(widths) if widths else None}
    worst = sorted(range(n), key=lambda i: -abs(err[i]))[:a.top]
    out["worst"] = [{"row": i + 2, "y_true": y[i], "y_pred": p[i], "error": err[i]} for i in worst]
    failed = []
    if a.max_abs_bias_pct is not None:
        for g in dec:
            if g["bias_pct"] is not None and abs(g["bias_pct"]) > a.max_abs_bias_pct:
                failed.append(f"decile {g['decile']} bias {g['bias_pct']:+.1f}%")
        for col, gs in segs.items():
            for k, g in gs.items():
                if g["bias_pct"] is not None and abs(g["bias_pct"]) > a.max_abs_bias_pct:
                    failed.append(f"{col}={k} bias {g['bias_pct']:+.1f}%")
    out["gate_failures"] = failed
    if a.json:
        print(json.dumps(out, indent=2, default=float))
        return 1 if failed else 0
    m = out["metrics"]
    print(f"{n} rows   MAE {m['mae']:.4g}  RMSE {m['rmse']:.4g}  MedAE {m['medae']:.4g}  bias {m['bias']:+.4g}  "
          f"R2 {m['r2']:.4f}  WAPE {m['wape']:.2%}")
    print("\nCalibration by prediction decile (mean pred / mean true):")
    print("  " + "  ".join(f"D{g['decile']}:{g['ratio_pred_true']:.2f}" for g in dec if g["ratio_pred_true"]))
    top_ratio = dec[-1]["ratio_pred_true"]
    if top_ratio and top_ratio < 0.9:
        print(f"  the highest decile is under-predicted ({top_ratio:.2f}): typical of squared error on skewed targets, "
              "shrinkage, or a missing feature for large cases")
    if dec[0]["ratio_pred_true"] and dec[0]["ratio_pred_true"] > 1.1:
        print(f"  the lowest decile is over-predicted ({dec[0]['ratio_pred_true']:.2f}): regression to the mean")
    sc = out["spread_corr"]
    print(f"\n|residual| vs prediction correlation {sc:+.2f}" + (
        ": errors grow with the level (heteroscedastic) - log target / Gamma loss, report relative errors" if sc > 0.3 else ""))
    for col, gs in segs.items():
        print(f"\nBy {col}:")
        for k, g in gs.items():
            bp = "" if g["bias_pct"] is None else f" ({g['bias_pct']:+.1f}%)"
            print(f"  {k:<28} n={g['n']:<5} MAE {g['mae']:.4g}  bias {g['bias']:+.4g}{bp}")
    if "intervals" in out:
        iv = out["intervals"]
        print(f"\nInterval coverage {iv['coverage']:.1%} (nominal {iv['nominal']:.0%}), mean width {iv['mean_width']:.4g}"
              + ("  <- too narrow" if iv["coverage"] < iv["nominal"] - 0.05 else
                 "  <- wider than needed" if iv["coverage"] > iv["nominal"] + 0.05 else ""))
    print(f"\nLargest errors (CSV line numbers): " + ", ".join(
        f"line {w['row']}: true {w['y_true']:.4g} pred {w['y_pred']:.4g}" for w in out["worst"]))
    for f in failed:
        print(f"GATE FAILED: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
