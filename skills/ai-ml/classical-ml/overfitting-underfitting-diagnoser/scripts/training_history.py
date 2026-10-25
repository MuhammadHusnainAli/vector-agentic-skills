#!/usr/bin/env python3
"""Diagnose a training history (metric per boosting round / epoch) for overfitting and underfitting.

Input: CSV with an iteration column and training and validation metric columns, e.g. exported from
LightGBM evals_result_, XGBoost evals_result(), CatBoost get_evals_result() or a Keras/PyTorch history:
    iteration,train_logloss,valid_logloss
Columns are detected automatically (train*/valid*|val*|eval*|test* pairs with the same metric suffix), or set
with --train-col/--val-col. Direction is inferred from the metric name (loss, error, rmse, mae... = lower is
better; auc, accuracy, ndcg, map, r2... = higher is better); override with --lower-better/--higher-better.

Reports:
  best        best validation iteration (on a centred moving average of --smooth points, so one noisy round
              does not decide) and the raw value there
  degradation how much the validation metric worsened from the best to the last iteration
  onset       first iteration after which the smoothed validation metric stays worse than best + noise
  gap         train - validation at the start, at the best and at the end
  noise       std of the validation metric around its moving average; suggests an early-stopping patience
  verdict     OVERFITTING                 validation worsens after the best iteration while training improves
              STILL IMPROVING             best within the last 5% of rounds: train longer / raise the learning rate
              PLATEAU                     validation flat (within noise) for the last third: stop earlier
              TRAINING DIVERGES           training metric worsens: learning rate too high or a bug
              NOT LEARNING                validation never beats its first value by more than the noise
              WELL FIT                    best in the middle, little degradation

Usage:
    python training_history.py history.csv
    python training_history.py history.csv --train-col training_auc --val-col valid_1_auc --smooth 9
    python training_history.py history.csv --json

Exit codes: 0 diagnosed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys

LOWER = re.compile(r"(loss|error|err\b|rmse|mse|mae|mape|deviance|logloss|l1|l2|huber|poisson|gamma|tweedie|brier)",
                   re.I)
HIGHER = re.compile(r"(auc|acc|accuracy|ndcg|map\b|precision|recall|f1|r2|aucpr)", re.I)
TRAIN = re.compile(r"^(train(ing)?|learn)[_\-. ]*", re.I)
VALID = re.compile(r"^(valid(ation)?(_\d+)?|val|eval|test)[_\-. ]*", re.I)


def detect(cols, train_col, val_col):
    if train_col and val_col:
        return train_col, val_col
    trains = {TRAIN.sub("", c): c for c in cols if TRAIN.match(c)}
    vals = {VALID.sub("", c): c for c in cols if VALID.match(c)}
    for metric, vc in vals.items():
        if metric in trains:
            return train_col or trains[metric], val_col or vc
    if val_col:
        return train_col, val_col
    if vals:
        return train_col, next(iter(vals.values()))
    raise ValueError("cannot find validation column; pass --val-col (and --train-col)")


def moving_average(xs, w):
    h = w // 2
    out = []
    for i in range(len(xs)):
        seg = xs[max(0, i - h): i + h + 1]
        out.append(sum(seg) / len(seg))
    return out


def fmt(x):
    return "n/a" if x is None else (f"{x:.5g}" if abs(x) < 1e5 else f"{x:.0f}")


def diagnose(its, tr, va, lower, smooth):
    s = 1.0 if lower else -1.0                              # work in "lower is better" space
    v = [s * x for x in va]
    t = [s * x for x in tr] if tr else None
    n = len(v)
    w = max(1, min(smooth, n // 5 or 1))
    vs = moving_average(v, w)
    resid = [a - b for a, b in zip(v, vs)]
    noise = math.sqrt(sum(r * r for r in resid) / max(1, n - 1))
    ib = min(range(n), key=lambda i: vs[i])
    best_s = vs[ib]
    tol = max(2 * noise, 1e-12)
    onset = None
    for i in range(ib + 1, n):
        if all(x > best_s + tol for x in vs[i:]):
            onset = i
            break
    res = {"iterations": n, "lower_better": lower, "smooth_window": w,
           "best_iteration": its[ib], "best_value": va[ib], "best_value_smoothed": s * best_s,
           "final_value": va[-1], "degradation": max(0.0, v[-1] - v[ib]),
           "noise": noise, "overfit_onset": its[onset] if onset is not None else None}
    if t is not None:
        gap = lambda i: v[i] - t[i]                         # validation worse than train by this much
        res["gap_start"], res["gap_best"], res["gap_end"] = gap(0), gap(ib), gap(n - 1)
        ts = moving_average(t, w)
        train_trend = ts[-1] - ts[n // 2]
    else:
        train_trend = None
    third = vs[2 * n // 3:]
    flat_tail = max(third) - min(third) <= tol if third else False
    improvement = vs[0] - best_s
    patience = max(10, int(round(3 * w)), int(round(0.05 * n)))
    res["suggested_patience"] = patience
    if t is not None and train_trend is not None and train_trend > tol:
        verdict = "TRAINING DIVERGES"
        advice = ("the training metric gets worse late in training: lower the learning rate, check for "
                  "exploding values or a bug in the custom objective/metric")
    elif improvement <= tol:
        verdict = "NOT LEARNING"
        advice = ("validation never improves beyond its noise: check the features and labels (shuffled target? "
                  "constant features?), the learning rate, and that the metric matches the objective")
    elif ib >= int(0.95 * (n - 1)):
        verdict = "STILL IMPROVING"
        advice = (f"the best validation value is at the end (iteration {its[ib]}): train for more rounds or raise "
                  "the learning rate; the model is under-trained, not over-fitted")
    elif onset is not None and res["degradation"] > tol:
        verdict = "OVERFITTING"
        advice = (f"validation is best at iteration {its[ib]} and worsens from about {its[onset]} while training "
                  f"keeps improving: use early stopping (patience ~{patience}) or set the rounds to ~{its[ib]}")
    elif flat_tail:
        verdict = "PLATEAU"
        advice = (f"no gain after iteration ~{its[ib]}: early stopping with patience ~{patience} saves the extra "
                  "rounds; gains now need capacity or features, not iterations")
    else:
        verdict = "WELL FIT"
        advice = f"best at iteration {its[ib]} with little degradation; keep early stopping at patience ~{patience}"
    res["verdict"], res["advice"] = verdict, advice
    if t is not None:
        rel = res["gap_best"] / max(abs(best_s), 1e-12)
        res["gap_relative_at_best"] = rel
        if rel > 0.25 and verdict in ("OVERFITTING", "PLATEAU", "WELL FIT"):
            res["advice"] += (f"; the gap at the best iteration is {rel:.0%} of the validation value: regularise "
                              "(min leaf size, subsampling, L2, shallower trees)")
    return res


def report(r):
    lines = [f"iterations: {r['iterations']}   direction: {'lower' if r['lower_better'] else 'higher'} is better   "
             f"smoothing window: {r['smooth_window']}",
             f"best iteration: {r['best_iteration']}  value {fmt(r['best_value'])} (smoothed "
             f"{fmt(r['best_value_smoothed'])})   final value {fmt(r['final_value'])}",
             f"degradation best -> end: {fmt(r['degradation'])}   noise: {fmt(r['noise'])}   "
             f"overfit onset: {r['overfit_onset'] if r['overfit_onset'] is not None else 'none'}"]
    if "gap_end" in r:
        lines.append(f"gap (validation worse than training): start {fmt(r['gap_start'])}, best {fmt(r['gap_best'])}, "
                     f"end {fmt(r['gap_end'])}")
    lines.append(f"suggested early-stopping patience: {r['suggested_patience']}")
    lines.append("")
    lines.append(f"VERDICT: {r['verdict']}")
    lines.append(f"  {r['advice']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Diagnose a training history.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="history CSV, or - for stdin")
    ap.add_argument("--iter-col", default=None, help="iteration column (default: iteration/epoch/round or row number)")
    ap.add_argument("--train-col")
    ap.add_argument("--val-col")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--lower-better", action="store_true")
    g.add_argument("--higher-better", action="store_true")
    ap.add_argument("--smooth", type=int, default=5, help="moving-average window (default 5)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        f = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8")
        with f:
            rows = list(csv.DictReader(f))
        if len(rows) < 5:
            raise ValueError("need at least 5 iterations")
        cols = list(rows[0])
        ic = a.iter_col or next((c for c in cols if c.lower() in ("iteration", "iter", "epoch", "round", "step")), None)
        tc, vc = detect([c for c in cols if c != ic], a.train_col, a.val_col)
        for c in (tc, vc, ic):
            if c and c not in cols:
                raise ValueError(f"column {c!r} not found (have: {', '.join(cols)})")
        its, tr, va = [], [], []
        for k, r in enumerate(rows):
            try:
                v = float(r[vc])
                tv = float(r[tc]) if tc else None
            except (TypeError, ValueError):
                continue
            its.append(int(float(r[ic])) if ic else k + 1)
            va.append(v)
            if tc:
                tr.append(tv)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.lower_better or a.higher_better:
        lower = a.lower_better
    elif LOWER.search(vc):
        lower = True
    elif HIGHER.search(vc):
        lower = False
    else:
        print(f"error: cannot infer the direction of {vc!r}; pass --lower-better or --higher-better", file=sys.stderr)
        return 2
    res = diagnose(its, tr or None, va, lower, a.smooth)
    res["train_col"], res["val_col"] = tc, vc
    print(json.dumps(res, indent=2) if a.json else f"train: {tc}   validation: {vc}\n" + report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
