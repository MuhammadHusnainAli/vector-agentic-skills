#!/usr/bin/env python3
"""Read a validation curve (train and validation score across one hyperparameter) for under- and overfitting.

Input: CSV with one row per (parameter value, fold), as written by sklearn.model_selection.validation_curve:
    max_depth,fold,train_score,val_score
The parameter column is the first column that is not fold/train/val (or --param-col). Rows per value without a
fold column also work. Scores are higher-is-better (scikit-learn convention) unless --lower-better.

Reports for each value: mean train and validation score, validation fold std and the gap, plus a zone:
  underfit   less complex than the best value and worse than best - 1 SE
  sweet spot within 1 SE of the best validation score
  overfit    more complex than the best value, worse than best - 1 SE, with a larger gap than at the best
Then:
  best       value with the best mean validation score
  1-SE pick  the least complex value within one standard error of the best (std / sqrt(folds))
  boundary   best value at the edge of the swept range: extend the sweep
  current    with --current, which zone the value in use falls in and which way to move it
Complexity direction (does a larger value mean a more flexible model?) is taken from the parameter name
(max_depth, num_leaves, C, n_estimators... increase; min_samples_leaf, alpha, reg_lambda, n_neighbors...
decrease) or, if unknown or ambiguous (gamma means opposite things in SVMs and XGBoost), from the
training-score trend; override with --complexity.

Usage:
    python validation_curve_report.py validation_curve.csv
    python validation_curve_report.py vc.csv --param-col param_C --current 100
    python validation_curve_report.py vc.csv --complexity decreasing --json

Exit codes: 0 reported, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import OrderedDict

MORE_COMPLEX = re.compile(r"(max_depth|depth|num_leaves|max_leaf_nodes|n_estimators|iterations|num_boost_round|"
                          r"^c$|_c$|max_features|degree|n_components|hidden|units|layers|max_bins|"
                          r"learning_rate|colsample|subsample|epochs)", re.I)
LESS_COMPLEX = re.compile(r"(min_samples_leaf|min_samples_split|min_child|min_data|alpha|lambda|reg_|l2|l1|"
                          r"n_neighbors|k_neighbors|ccp_alpha|min_impurity|dropout|smoothing|l2_leaf_reg|"
                          r"min_gain|weight_decay)", re.I)
SKIP = re.compile(r"^(fold|split|cv|seed|repeat)$", re.I)


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def mean(xs):
    return sum(xs) / len(xs)


def std(xs):
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def load(path, param_col, train_col, val_col):
    f = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8")
    with f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    cols = list(rows[0])
    if param_col is None:
        param_col = next((c for c in cols if c not in (train_col, val_col) and not SKIP.match(c)), None)
    for c in (param_col, train_col, val_col):
        if c is None or c not in cols:
            raise ValueError(f"column {c!r} not found (have: {', '.join(cols)})")
    groups = OrderedDict()
    for r in rows:
        t, v = num(r[train_col]), num(r[val_col])
        if t is None or v is None:
            continue
        groups.setdefault(r[param_col], ([], []))
        groups[r[param_col]][0].append(t)
        groups[r[param_col]][1].append(v)
    if len(groups) < 3:
        raise ValueError("need at least three parameter values")
    keys = list(groups)
    numeric = all(num(k) is not None for k in keys)
    if numeric:
        keys.sort(key=num)
    pts = [{"value": k, "train": mean(groups[k][0]), "val": mean(groups[k][1]), "val_std": std(groups[k][1]),
            "folds": len(groups[k][1])} for k in keys]
    return param_col, numeric, pts


def fmt(x):
    return f"{x:.4g}" if abs(x) < 1e5 else f"{x:.0f}"


def analyse(param, numeric, pts, lower=False, complexity=None, current=None):
    s = -1.0 if lower else 1.0
    for p in pts:
        p["gap"] = s * (p["train"] - p["val"])
    vals = [s * p["val"] for p in pts]
    ib = max(range(len(pts)), key=lambda i: vals[i])
    best = pts[ib]
    se = best["val_std"] / math.sqrt(best["folds"]) if best["folds"] > 1 else 0.0
    source = "given"
    if complexity is None:
        if MORE_COMPLEX.search(param) and not LESS_COMPLEX.search(param):
            complexity, source = "increasing", "parameter name"
        elif LESS_COMPLEX.search(param):
            complexity, source = "decreasing", "parameter name"
        else:
            tr = [s * p["train"] for p in pts]
            complexity = "increasing" if tr[-1] >= tr[0] else "decreasing"
            source = "training-score trend"
    order = list(range(len(pts))) if complexity == "increasing" else list(range(len(pts)))[::-1]
    rank = {i: r for r, i in enumerate(order)}              # 0 = least complex
    within = [i for i in range(len(pts)) if vals[i] >= vals[ib] - se]
    pick = min(within, key=lambda i: rank[i])
    for i, p in enumerate(pts):
        if i in within:
            p["zone"] = "sweet spot"
        elif rank[i] < rank[ib]:
            p["zone"] = "underfit"
        else:
            p["zone"] = "overfit" if p["gap"] > best["gap"] else "worse"
    res = {"param": param, "numeric": numeric, "complexity": complexity, "complexity_source": source,
           "points": pts, "best": best["value"], "best_val": best["val"], "se": se, "pick_1se": pts[pick]["value"],
           "pick_1se_val": pts[pick]["val"], "lower_better": lower, "warnings": []}
    if best["folds"] < 2:
        res["warnings"].append("one score per value: the 1-SE rule needs fold scores; export per-fold results")
    if ib in (0, len(pts) - 1) and numeric:
        side = "low" if ib == 0 else "high"
        res["warnings"].append(f"best {param}={best['value']} is at the {side} end of the sweep: extend the range "
                               f"{'below' if side == 'low' else 'above'} it")
    over = [p for p in pts if p["zone"] == "overfit"]
    under = [p for p in pts if p["zone"] == "underfit"]
    if not over and not under:
        res["warnings"].append("every value is within 1 SE of the best: this parameter barely matters over this range")
    if current is not None:
        key = next((p for p in pts if p["value"] == current or (numeric and num(current) is not None
                                                                  and num(p["value"]) == num(current))), None)
        if key is None:
            res["warnings"].append(f"--current {current} is not one of the swept values")
        else:
            z = key["zone"]
            move = ("more complex" if z == "underfit" else "less complex" if z in ("overfit", "worse") else None)
            if move:
                larger = (move == "more complex") == (complexity == "increasing")
                move += f" setting ({'larger' if larger else 'smaller'} {param}, towards {pts[pick]['value']})"
            res["current"] = {"value": current, "zone": z, "move": move}
    return res


def report(r):
    lines = [f"parameter: {r['param']}   complexity grows with {'larger' if r['complexity'] == 'increasing' else 'smaller'}"
             f" values ({r['complexity_source']})",
             f"{'value':>10} {'train':>9} {'val':>9} {'val_std':>8} {'gap':>9}  zone"]
    for p in r["points"]:
        mark = " <- best" if p["value"] == r["best"] else (" <- 1-SE pick" if p["value"] == r["pick_1se"] else "")
        lines.append(f"{p['value']:>10} {fmt(p['train']):>9} {fmt(p['val']):>9} {fmt(p['val_std']):>8} "
                     f"{fmt(p['gap']):>9}  {p['zone']}{mark}")
    lines.append("")
    lines.append(f"BEST: {r['param']}={r['best']} (validation {fmt(r['best_val'])}, 1 SE = {fmt(r['se'])})")
    lines.append(f"1-SE PICK: {r['param']}={r['pick_1se']} (validation {fmt(r['pick_1se_val'])}): the least complex "
                 "value statistically tied with the best")
    c = r.get("current")
    if c:
        lines.append(f"CURRENT: {r['param']}={c['value']} is in the {c['zone']} zone"
                     + (f": move to a {c['move']}" if c["move"] else ": keep it"))
    for w in r["warnings"]:
        lines.append(f"WARNING: {w}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Read a validation curve.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="validation curve CSV, or - for stdin")
    ap.add_argument("--param-col")
    ap.add_argument("--train-col", default="train_score")
    ap.add_argument("--val-col", default="val_score")
    ap.add_argument("--lower-better", action="store_true")
    ap.add_argument("--complexity", choices=["increasing", "decreasing"],
                    help="whether larger parameter values make the model more flexible")
    ap.add_argument("--current", help="value currently in use")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        param, numeric, pts = load(a.csv, a.param_col, a.train_col, a.val_col)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    res = analyse(param, numeric, pts, a.lower_better, a.complexity, a.current)
    print(json.dumps(res, indent=2) if a.json else report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
