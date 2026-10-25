#!/usr/bin/env python3
"""Diagnose a learning curve: is the model data-limited, variance-limited or bias-limited?

Input: CSV with one row per (training size, fold) and the training and validation score, as written by
gen_learning_curve.py or exported from sklearn.model_selection.learning_curve:
    train_size,fold,train_score,val_score
Column names can be changed with --size-col/--train-col/--val-col. A row per size (no fold column) works too.

Reports, per training size: mean train and validation score, validation fold std and the gap. Then:
  gap        train - validation at the largest size (sign-adjusted for --lower-better)
  slope      validation gain per doubling of the training set over the last half of the curve; the expected
             gain from 2x data is the fitted gain when the fit is good (R^2 >= 0.9), else the slope capped
             by the headroom to the ceiling
  fit        inverse power law  val(n) = a - b * n^-c  (a = asymptote) fitted by grid search over c and least
             squares for a, b on the largest four sizes, with a capped at the final training score (the training curve descends
             towards the same asymptote, so validation cannot be extrapolated above it); predictions for 2x, 4x and 10x data and, with --target, the size needed
  verdict    HIGH VARIANCE - DATA-LIMITED   large gap, validation still rising: more data helps
             HIGH VARIANCE                  large gap, validation flat: regularise / simplify / fewer features
             HIGH BIAS                      gap closed: training score is the ceiling; more data will not help,
                                            add capacity or features
             CONVERGED                      gap closed and the score meets --target (or, without a target,
                                            a bounded score >= 0.97)
  warnings   validation decreasing with size (ordering/shift in the subsets), standard error of the validation
             mean larger than the gain from doubling (noisy curve: more folds or repeats), a perfect training
             score (memorisation), validation above training at small sizes, a poor power-law fit

The gap threshold defaults to 0.02 x max(1, |final validation score|): two points for AUC/accuracy, 2% of the
value for RMSE-like metrics. Override with --gap-threshold.

Usage:
    python diagnose_curve.py learning_curve.csv
    python diagnose_curve.py lc.csv --target 0.95
    python diagnose_curve.py lc.csv --lower-better --gap-threshold 500 --json

Exit codes: 0 diagnosed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict


def mean(xs):
    return sum(xs) / len(xs)


def std(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def load(path, size_col, train_col, val_col):
    f = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    for c in (size_col, train_col, val_col):
        if c not in rows[0]:
            raise ValueError(f"column {c!r} not found (have: {', '.join(rows[0])})")
    by = defaultdict(lambda: ([], []))
    for r in rows:
        try:
            n = float(r[size_col])
            t, v = float(r[train_col]), float(r[val_col])
        except (TypeError, ValueError):
            continue
        by[n][0].append(t)
        by[n][1].append(v)
    pts = []
    for n in sorted(by):
        t, v = by[n]
        pts.append({"size": n, "train": mean(t), "val": mean(v), "val_std": std(v), "train_std": std(t),
                    "folds": len(v)})
    if len(pts) < 2:
        raise ValueError("need at least two training sizes")
    return pts


def fit_power_law(ns, ys, ceiling=None):
    """Fit y = a - b * n^-c (b >= 0, a <= ceiling). Returns (a, b, c, r2) or None."""
    best = None
    ybar = mean(ys)
    sst = sum((y - ybar) ** 2 for y in ys) or 1e-12
    for i in range(1, 301):
        c = i / 200                                         # 0.005 .. 1.5
        xs = [n ** -c for n in ns]
        xbar = mean(xs)
        sxx = sum((x - xbar) ** 2 for x in xs)
        if sxx <= 0:
            continue
        slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
        b = max(0.0, -slope)                                # y = a - b x
        a = ybar + b * xbar
        if ceiling is not None and a > ceiling:             # least squares for b with a fixed at the ceiling
            a = ceiling
            b = max(0.0, sum(x * (a - y) for x, y in zip(xs, ys)) / sum(x * x for x in xs))
        sse = sum((y - (a - b * x)) ** 2 for x, y in zip(xs, ys))
        if best is None or sse < best[3]:
            best = (a, b, c, sse)
    if best is None:
        return None
    a, b, c, sse = best
    return a, b, c, 1 - sse / sst


def fmt(x):
    return f"{x:.4g}" if abs(x) < 1e4 else f"{x:.0f}"


def diagnose(pts, lower_better=False, target=None, gap_threshold=None, min_gain=None):
    sign = -1.0 if lower_better else 1.0
    ns = [p["size"] for p in pts]
    tr = [sign * p["train"] for p in pts]
    va = [sign * p["val"] for p in pts]
    gaps = [t - v for t, v in zip(tr, va)]
    last = pts[-1]
    scale = max(1.0, abs(last["val"]))
    gthr = gap_threshold if gap_threshold is not None else 0.02 * scale
    mgain = min_gain if min_gain is not None else 0.005 * scale
    half = pts[len(pts) // 2 - (1 if len(pts) % 2 == 0 else 0):] if len(pts) >= 3 else pts
    k = len(half)
    lx = [math.log2(p["size"]) for p in half]
    ly = [sign * p["val"] for p in half]
    lxm, lym = mean(lx), mean(ly)
    sxx = sum((x - lxm) ** 2 for x in lx)
    slope = sum((x - lxm) * (y - lym) for x, y in zip(lx, ly)) / sxx if sxx else 0.0
    res = {"points": pts, "gap": gaps[-1] , "gap_threshold": gthr, "slope_per_doubling": slope,
           "lower_better": lower_better, "warnings": [], "fit": None}
    if k < 2:
        res["warnings"].append("too few sizes for a slope")
    ceiling = max(tr[-1], va[-1])                           # the training curve descends towards the asymptote
    if not lower_better and all(0 <= p["train"] <= 1 and 0 <= p["val"] <= 1 for p in pts):
        ceiling = min(ceiling, 1.0)
    tail = slice(max(0, len(pts) - 4), None)                # the smallest sizes distort the extrapolation
    fit = fit_power_law(ns[tail], va[tail], ceiling) if len(pts) >= 3 else None
    gain2 = max(0.0, min(slope, ceiling - va[-1]))          # cannot climb above the ceiling
    if fit:
        a, b, c, r2 = fit
        pred = lambda n: sign * (a - b * n ** -c)
        nmax = ns[-1]
        fitres = {"asymptote": sign * a, "b": b, "c": c, "r2": r2,
                  "pred_2x": pred(2 * nmax), "pred_4x": pred(4 * nmax), "pred_10x": pred(10 * nmax)}
        if r2 >= 0.9 and b > 0:
            gain2 = (a - b * (2 * nmax) ** -c) - (a - b * nmax ** -c)
        if target is not None:
            t = sign * target
            if t >= a:
                fitres["size_for_target"] = None
            elif b > 0:
                fitres["size_for_target"] = (b / (a - t)) ** (1 / c)
        res["fit"] = fitres
        if r2 < 0.9:
            res["warnings"].append(f"power-law fit on the last sizes is poor (R^2 {r2:.2f}): treat extrapolations as rough")
    res["gain_2x"] = gain2
    drops = [i for i in range(1, len(va)) if va[i] < va[i - 1] - max(pts[i]["val_std"], 1e-9) * 2]
    if drops:
        res["warnings"].append("validation score gets worse with more data at size(s) "
                               + ", ".join(fmt(ns[i]) for i in drops)
                               + ": subsets may not be random (sorted data with shuffle=False) or the data drifts")
    se = last["val_std"] / math.sqrt(last["folds"]) if last["folds"] > 1 else 0.0
    if se > abs(gain2) and last["folds"] > 1:
        res["warnings"].append(f"standard error of the validation mean at the largest size ({fmt(se)}) exceeds the "
                               f"gain from doubling ({fmt(gain2)}): noisy curve, use more folds or repeated splits")
    bounded = all(0 <= p["train"] <= 1 and 0 <= p["val"] <= 1 for p in pts)
    if not lower_better and bounded and last["train"] >= 0.999:
        res["warnings"].append("training score is perfect: the model memorises the training rows, so the gap shows "
                               "variance but the training curve says nothing about the ceiling")
    if gaps[0] < -gthr:
        res["warnings"].append("validation beats training at small sizes: check regularisation on tiny data, "
                               "dropout/augmentation, or swapped columns")
    reached = target is not None and sign * last["val"] >= sign * target
    if gaps[-1] > gthr:
        if gain2 > mgain:
            res["verdict"] = "HIGH VARIANCE - DATA-LIMITED"
            res["advice"] = ("the model still learns from more rows: collecting data pays off; meanwhile regularise "
                             "(stronger penalties, min leaf size, fewer features) to close the gap")
        else:
            res["verdict"] = "HIGH VARIANCE"
            res["advice"] = ("validation has flattened while the gap stays open: more data of the same kind adds "
                             "little; regularise, simplify the model, remove noisy or leaky-looking features")
    elif reached or (target is None and bounded and not lower_better and last["val"] >= 0.97):
        res["verdict"] = "CONVERGED"
        res["advice"] = ("train and validation agree at a " + ("score that meets the target" if reached else
                         "near-perfect score") + "; more data or capacity will not change much")
    else:
        res["verdict"] = "HIGH BIAS"
        res["advice"] = (f"train and validation have met near {fmt(last['train'])}: the training score is the "
                         "ceiling, so more data will not help; add capacity (deeper trees, more boosting rounds, "
                         "interactions, a non-linear model), better features, or relax regularisation"
                         + ("" if target is not None else " (if this score is already good enough, pass --target: "
                            "the model has simply converged)"))
    if target is not None and not reached:
        res["target"] = target
    return res


def report(res, target):
    lines = [f"{'size':>10} {'train':>9} {'val':>9} {'val_std':>8} {'gap':>9}"]
    sign = -1 if res["lower_better"] else 1
    for p in res["points"]:
        lines.append(f"{fmt(p['size']):>10} {fmt(p['train']):>9} {fmt(p['val']):>9} {fmt(p['val_std']):>8} "
                     f"{fmt(sign * (p['train'] - p['val'])):>9}")
    lines.append("")
    lines.append(f"gap at largest size: {fmt(res['gap'])} (threshold {fmt(res['gap_threshold'])})")
    lines.append(f"validation gain per doubling (last half): {fmt(res['slope_per_doubling'])}; "
                 f"expected gain from 2x data: {fmt(res['gain_2x'])}")
    f = res["fit"]
    if f:
        lines.append(f"power-law fit: asymptote {fmt(f['asymptote'])}, exponent {f['c']:.3f}, R^2 {f['r2']:.3f}; "
                     f"predicted at 2x {fmt(f['pred_2x'])}, 4x {fmt(f['pred_4x'])}, 10x {fmt(f['pred_10x'])} (rough)")
        if target is not None and "size_for_target" in f:
            st = f["size_for_target"]
            lines.append(f"target {fmt(target)}: " + ("above the ceiling (asymptote) - not reachable with more data alone; change the model or features"
                                                      if st is None else f"needs about {fmt(st)} training rows"))
    lines.append("")
    lines.append(f"VERDICT: {res['verdict']}")
    lines.append(f"  {res['advice']}")
    for w in res["warnings"]:
        lines.append(f"WARNING: {w}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Diagnose a learning curve.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="learning curve CSV, or - for stdin")
    ap.add_argument("--size-col", default="train_size")
    ap.add_argument("--train-col", default="train_score")
    ap.add_argument("--val-col", default="val_score")
    ap.add_argument("--lower-better", action="store_true", help="scores are losses/errors")
    ap.add_argument("--target", type=float, help="score you need to reach")
    ap.add_argument("--gap-threshold", type=float)
    ap.add_argument("--min-gain", type=float, help="gain from doubling that counts as still learning "
                    "(default 0.005 x max(1, |score|))")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        pts = load(a.csv, a.size_col, a.train_col, a.val_col)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    res = diagnose(pts, a.lower_better, a.target, a.gap_threshold, a.min_gain)
    print(json.dumps(res, indent=2) if a.json else report(res, a.target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
