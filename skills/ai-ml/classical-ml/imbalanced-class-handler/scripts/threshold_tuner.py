#!/usr/bin/env python3
"""Choose a decision threshold for an imbalanced binary classifier, and undo resampling bias.

From a CSV of y_true (0/1) and y_score it evaluates every distinct score as a threshold and reports the
best one under each policy:
  f-beta        maximise F-beta (--beta, default 1; 2 = recall twice as important)
  precision     highest recall with precision >= --min-precision
  recall        highest precision with recall >= --min-recall
  capacity      flag exactly the top --k rows (review / call capacity)
  cost          minimise FP * --cost-fp + FN * --cost-fn per row
  youden        maximise TPR - FPR
For each: threshold, precision, recall, F1, flagged share, FP and FN counts.

Prior-shift correction: if the model was trained on resampled or reweighted data with positive
rate --train-rate, but the real positive rate is --true-rate, probabilities are biased. With both
flags the scores are corrected with
    p' = p*a / (p*a + (1-p)*b),   a = true/train,  b = (1-true)/(1-train)
before thresholding, and expected calibration error (ECE) is shown before and after. --write FILE
saves the corrected scores.

Threshold choice on the evaluation set is optimistic: choose on validation data, report on test data.

Usage:
    python threshold_tuner.py preds.csv --beta 2 --min-precision 0.5 --k 50 --cost-fp 8 --cost-fn 600
    python threshold_tuner.py preds.csv --train-rate 0.5 --true-rate 0.02 --write corrected.csv
    python threshold_tuner.py preds.csv --true-col label --score-col p --json

Exit codes: 0 done, 2 usage or data error.
"""

import argparse
import csv
import json
import sys
from collections import defaultdict


def sweep(scores, y):
    """Yield (threshold, tp, fp, fn, tn) for every distinct score, flagging score >= threshold."""
    n, pos = len(y), sum(y)
    groups = defaultdict(lambda: [0, 0])
    for s, t in zip(scores, y):
        groups[s][0] += t
        groups[s][1] += 1
    tp = flagged = 0
    for s in sorted(groups, reverse=True):
        h, c = groups[s]
        tp += h
        flagged += c
        fp = flagged - tp
        yield s, tp, fp, pos - tp, n - pos - fp


def row(thr, tp, fp, fn, tn, n):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"threshold": thr, "precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "flagged_share": (tp + fp) / n, "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def ece(scores, y, bins=10):
    agg = defaultdict(lambda: [0.0, 0.0, 0])
    for s, t in zip(scores, y):
        b = agg[min(bins - 1, int(s * bins))]
        b[0] += s
        b[1] += t
        b[2] += 1
    return sum(abs(sp - st) for sp, st, _ in agg.values()) / len(y)


def main():
    ap = argparse.ArgumentParser(description="Pick thresholds for imbalanced classifiers; correct prior shift.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--true-col", default="y_true")
    ap.add_argument("--score-col", default="y_score")
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--min-precision", type=float)
    ap.add_argument("--min-recall", type=float)
    ap.add_argument("--k", type=int)
    ap.add_argument("--cost-fp", type=float)
    ap.add_argument("--cost-fn", type=float)
    ap.add_argument("--train-rate", type=float, help="positive rate the model was trained on (after resampling)")
    ap.add_argument("--true-rate", type=float, help="real positive rate in production")
    ap.add_argument("--write", help="write corrected scores to this CSV (needs --train-rate and --true-rate)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            if a.true_col not in (rd.fieldnames or []) or a.score_col not in (rd.fieldnames or []):
                raise ValueError(f"need columns {a.true_col!r} and {a.score_col!r}")
            rows = list(rd)
        y = [int(float(r[a.true_col])) for r in rows]
        s = [float(r[a.score_col]) for r in rows]
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if set(y) - {0, 1} or sum(y) in (0, len(y)):
        print("error: y_true must be 0/1 with both classes present", file=sys.stderr)
        return 2
    out = {"rows": len(y), "positives": sum(y), "prevalence": sum(y) / len(y)}
    if (a.train_rate is None) != (a.true_rate is None):
        print("error: give both --train-rate and --true-rate", file=sys.stderr)
        return 2
    if a.train_rate is not None:
        if not (0 < a.train_rate < 1 and 0 < a.true_rate < 1):
            print("error: rates must be in (0, 1)", file=sys.stderr)
            return 2
        ca, cb = a.true_rate / a.train_rate, (1 - a.true_rate) / (1 - a.train_rate)
        before = ece(s, y)
        s = [p * ca / (p * ca + (1 - p) * cb) for p in s]
        out["prior_correction"] = {"train_rate": a.train_rate, "true_rate": a.true_rate, "ece_before": before,
                                   "ece_after": ece(s, y), "mean_score_after": sum(s) / len(s)}
        if a.write:
            with open(a.write, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([a.true_col, a.score_col])
                w.writerows([[t, round(p, 6)] for t, p in zip(y, s)])
    n = len(y)
    curve = [row(thr, tp, fp, fn, tn, n) for thr, tp, fp, fn, tn in sweep(s, y)]
    b2 = a.beta ** 2
    best = {}
    fb = lambda r: (1 + b2) * r["precision"] * r["recall"] / (b2 * r["precision"] + r["recall"]) if r["precision"] + r["recall"] else 0
    best[f"f{a.beta:g}"] = max(curve, key=fb)
    best["youden"] = max(curve, key=lambda r: r["recall"] - r["fp"] / max(1, r["fp"] + r["tn"]))
    if a.min_precision is not None:
        ok = [r for r in curve if r["precision"] >= a.min_precision]
        best[f"precision>={a.min_precision:g}"] = max(ok, key=lambda r: r["recall"]) if ok else None
    if a.min_recall is not None:
        ok = [r for r in curve if r["recall"] >= a.min_recall]
        best[f"recall>={a.min_recall:g}"] = max(ok, key=lambda r: r["precision"]) if ok else None
    if a.k:
        ranked = sorted(s, reverse=True)
        thr = ranked[min(a.k, n) - 1]
        best[f"top-{a.k}"] = next(r for r in curve if r["threshold"] <= thr) if any(r["threshold"] <= thr for r in curve) else None
    if a.cost_fp is not None and a.cost_fn is not None:
        cost = lambda r: (r["fp"] * a.cost_fp + r["fn"] * a.cost_fn) / n
        flag_none = {"threshold": float("inf"), "tp": 0, "fp": 0, "fn": sum(y), "tn": n - sum(y), "precision": 0.0,
                     "recall": 0.0, "f1": 0.0, "flagged_share": 0.0}
        r = min(curve + [flag_none], key=cost)
        best["min-cost"] = {**r, "cost_per_row": cost(r)}
        out["bayes_threshold_if_calibrated"] = a.cost_fp / (a.cost_fp + a.cost_fn)
    out["policies"] = best
    if a.json:
        print(json.dumps(out, indent=2, default=float))
        return 0
    print(f"{n} rows, {out['positives']} positives (prevalence {out['prevalence']:.2%})")
    if "prior_correction" in out:
        pc = out["prior_correction"]
        print(f"prior correction {pc['train_rate']:g} -> {pc['true_rate']:g}: ECE {pc['ece_before']:.4f} -> "
              f"{pc['ece_after']:.4f}, mean score {pc['mean_score_after']:.4f}" + (f"; wrote {a.write}" if a.write else ""))
    print(f"\n{'policy':<18} {'threshold':>9} {'precision':>9} {'recall':>7} {'F1':>6} {'flagged':>8} {'FP':>6} {'FN':>5}")
    for name, r in best.items():
        if r is None:
            print(f"{name:<18} not reachable on this data")
            continue
        extra = f"  cost/row {r['cost_per_row']:.4f}" if "cost_per_row" in r else ""
        print(f"{name:<18} {r['threshold']:>9.4g} {r['precision']:>9.3f} {r['recall']:>7.3f} {r['f1']:>6.3f} "
              f"{r['flagged_share']:>8.1%} {r['fp']:>6} {r['fn']:>5}{extra}")
    if "bayes_threshold_if_calibrated" in out:
        print(f"\nBayes-optimal threshold for calibrated probabilities: {out['bayes_threshold_if_calibrated']:.4f}")
    print("Choose the threshold on validation data and report metrics on a separate test set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
