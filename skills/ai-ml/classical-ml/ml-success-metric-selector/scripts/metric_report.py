#!/usr/bin/env python3
"""Compute the full metric panel from a predictions CSV, at the operating point you care about.

Binary (columns y_true in {0,1} and y_score in [0,1]):
  ranking      ROC-AUC, PR-AUC (average precision), lift and precision/recall at top-K
  probability  log loss, Brier, expected calibration error (ECE, 10 equal-width bins)
  threshold    confusion matrix, precision, recall, F1, F-beta, balanced accuracy at --threshold
  cost         with --cost-fp/--cost-fn: expected cost per row at --threshold and the
               cost-minimising threshold found by scanning every distinct score
Regression (columns y_true and y_pred):
  MAE, RMSE, MedAE, bias (mean error), R2, WAPE, MAPE (skipping zeros, with a count), sMAPE,
  and per-segment MAE / bias with --segment

Usage:
    python metric_report.py preds.csv                                  # binary, columns y_true,y_score
    python metric_report.py preds.csv --k 50 --threshold 0.3 --beta 2
    python metric_report.py preds.csv --cost-fp 8 --cost-fn 600
    python metric_report.py reg.csv --regression --pred-col y_pred --segment segment
    python metric_report.py preds.csv --json

Exit codes: 0 computed, 2 usage or read error (missing columns, non-numeric values, one class only).
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict


def read(path, cols):
    fh = sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")
    reader = csv.DictReader(fh)
    missing = [c for c in cols if c and c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"missing column(s) {missing}; found {reader.fieldnames}")
    return list(reader)


def auc(s, y):
    pos = sum(y)
    neg = len(y) - pos
    order = sorted(range(len(s)), key=s.__getitem__)
    rank = [0.0] * len(s)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and s[order[j + 1]] == s[order[i]]:
            j += 1
        for k in range(i, j + 1):
            rank[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return (sum(r for r, t in zip(rank, y) if t) - pos * (pos + 1) / 2) / (pos * neg)


def avg_precision(s, y):
    groups = defaultdict(lambda: [0, 0])
    for v, t in zip(s, y):
        groups[v][0] += t
        groups[v][1] += 1
    pos, tp, seen, total = sum(y), 0, 0, 0.0
    for v in sorted(groups, reverse=True):
        h, n = groups[v]
        tp += h
        seen += n
        total += h / pos * tp / seen
    return total


def confusion(s, y, thr):
    tp = sum(1 for v, t in zip(s, y) if v >= thr and t)
    fp = sum(1 for v, t in zip(s, y) if v >= thr and not t)
    fn = sum(1 for v, t in zip(s, y) if v < thr and t)
    return tp, fp, fn, len(y) - tp - fp - fn


def binary_report(rows, a):
    try:
        y = [int(float(r[a.true_col])) for r in rows]
        s = [float(r[a.score_col]) for r in rows]
    except ValueError as e:
        raise ValueError(f"non-numeric value: {e}")
    if set(y) - {0, 1}:
        raise ValueError("y_true must be 0/1 for binary metrics (use --regression for numeric targets)")
    n, pos = len(y), sum(y)
    if pos in (0, n):
        raise ValueError("only one class present; ranking metrics are undefined")
    prev = pos / n
    eps = 1e-15
    out = {"rows": n, "positives": pos, "prevalence": prev, "roc_auc": auc(s, y), "pr_auc": avg_precision(s, y)}
    if all(0 <= v <= 1 for v in s):
        out["log_loss"] = -sum(t * math.log(max(eps, v)) + (1 - t) * math.log(max(eps, 1 - v)) for v, t in zip(s, y)) / n
        out["brier"] = sum((v - t) ** 2 for v, t in zip(s, y)) / n
        bins = defaultdict(lambda: [0.0, 0.0, 0])
        for v, t in zip(s, y):
            b = bins[min(9, int(v * 10))]
            b[0] += v
            b[1] += t
            b[2] += 1
        out["ece"] = sum(abs(sp - st) for sp, st, c in bins.values()) / n
        out["calibration"] = [{"bin": f"{k / 10:.1f}-{(k + 1) / 10:.1f}", "n": c, "mean_pred": sp / c, "frac_pos": st / c}
                              for k, (sp, st, c) in sorted(bins.items())]
    order = sorted(range(n), key=lambda i: -s[i])
    k = a.k or max(1, round(prev * n))
    hits = sum(y[i] for i in order[:k])
    out["at_k"] = {"k": k, "precision": hits / k, "recall": hits / pos, "lift": (hits / k) / prev}
    tp, fp, fn, tn = confusion(s, y, a.threshold)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / pos
    b2 = a.beta ** 2
    out["at_threshold"] = {
        "threshold": a.threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec,
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        f"f{a.beta:g}": (1 + b2) * prec * rec / (b2 * prec + rec) if prec + rec else 0.0,
        "balanced_accuracy": (rec + tn / (tn + fp)) / 2 if tn + fp else rec,
        "flagged_share": (tp + fp) / n}
    if a.cost_fp is not None and a.cost_fn is not None:
        def cost(thr):
            tp_, fp_, fn_, _ = confusion(s, y, thr)
            return (fp_ * a.cost_fp + fn_ * a.cost_fn) / n
        best = min(sorted(set(s)) + [float("inf")], key=cost)
        out["cost"] = {"cost_fp": a.cost_fp, "cost_fn": a.cost_fn, "at_threshold": cost(a.threshold),
                       "best_threshold": best, "best_cost": cost(best), "flag_nobody": pos * a.cost_fn / n,
                       "flag_everybody": (n - pos) * a.cost_fp / n,
                       "bayes_threshold_if_calibrated": a.cost_fp / (a.cost_fp + a.cost_fn)}
    deciles = []
    for d in range(10):
        part = order[d * n // 10:(d + 1) * n // 10]
        if part:
            deciles.append({"decile": d + 1, "n": len(part), "positive_rate": sum(y[i] for i in part) / len(part)})
    out["deciles"] = deciles
    return out


def regression_report(rows, a):
    try:
        y = [float(r[a.true_col]) for r in rows]
        p = [float(r[a.pred_col]) for r in rows]
    except ValueError as e:
        raise ValueError(f"non-numeric value: {e}")
    n = len(y)
    err = [pi - yi for pi, yi in zip(p, y)]
    mean = sum(y) / n
    sst = sum((v - mean) ** 2 for v in y)
    abs_err = sorted(abs(e) for e in err)
    nz = [(abs(e) / abs(t)) for e, t in zip(err, y) if t != 0]
    out = {"rows": n, "mae": sum(abs_err) / n, "rmse": math.sqrt(sum(e * e for e in err) / n),
           "medae": abs_err[n // 2] if n % 2 else (abs_err[n // 2 - 1] + abs_err[n // 2]) / 2,
           "bias": sum(err) / n, "r2": 1 - sum(e * e for e in err) / sst if sst else float("nan"),
           "wape": sum(abs_err) / sum(abs(v) for v in y) if any(y) else float("nan"),
           "mape": sum(nz) / len(nz) if nz else float("nan"), "mape_rows_skipped_zero": n - len(nz),
           "smape": sum(2 * abs(e) / (abs(t) + abs(pi)) for e, t, pi in zip(err, y, p) if abs(t) + abs(pi)) / n}
    if a.segment:
        seg = defaultdict(list)
        for r, e, t in zip(rows, err, y):
            seg[r.get(a.segment, "")].append((e, t))
        out["segments"] = [{"segment": k, "n": len(v), "mae": sum(abs(e) for e, _ in v) / len(v),
                            "bias": sum(e for e, _ in v) / len(v),
                            "bias_pct": sum(e for e, _ in v) / sum(t for _, t in v) if sum(t for _, t in v) else None}
                           for k, v in sorted(seg.items())]
    return out


def fmt(v):
    return f"{v:.4f}" if isinstance(v, float) else str(v)


def main():
    ap = argparse.ArgumentParser(description="Metric panel from a predictions CSV.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--regression", action="store_true")
    ap.add_argument("--true-col", default="y_true")
    ap.add_argument("--score-col", default="y_score")
    ap.add_argument("--pred-col", default="y_pred")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--beta", type=float, default=2.0, help="F-beta (default 2: recall twice as important)")
    ap.add_argument("--k", type=int, help="top-K for precision/recall/lift (default: number of positives)")
    ap.add_argument("--cost-fp", type=float)
    ap.add_argument("--cost-fn", type=float)
    ap.add_argument("--segment", help="regression: column to slice MAE and bias by")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        cols = [a.true_col, a.pred_col if a.regression else a.score_col, a.segment]
        rows = read(a.csv, cols)
        if not rows:
            raise ValueError("no rows")
        out = regression_report(rows, a) if a.regression else binary_report(rows, a)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    if a.regression:
        print(f"Regression metrics on {out['rows']} rows")
        for k in ("mae", "rmse", "medae", "bias", "r2", "wape", "mape", "smape"):
            print(f"  {k:<8} {fmt(out[k])}")
        if out["mape_rows_skipped_zero"]:
            print(f"  (MAPE skipped {out['mape_rows_skipped_zero']} rows with y_true = 0)")
        for sgm in out.get("segments", []):
            bp = "" if sgm["bias_pct"] is None else f" ({sgm['bias_pct']:+.1%})"
            print(f"  segment {sgm['segment']:<12} n={sgm['n']:<5} MAE {sgm['mae']:.4g}  bias {sgm['bias']:+.4g}{bp}")
        return 0
    print(f"Binary metrics on {out['rows']} rows, {out['positives']} positives (prevalence {out['prevalence']:.2%})")
    print(f"  ROC-AUC {out['roc_auc']:.4f}   PR-AUC {out['pr_auc']:.4f} (random = {out['prevalence']:.4f})")
    if "log_loss" in out:
        print(f"  log loss {out['log_loss']:.4f}   Brier {out['brier']:.4f}   ECE {out['ece']:.4f}")
    k = out["at_k"]
    print(f"  top-{k['k']}: precision {k['precision']:.3f}  recall {k['recall']:.3f}  lift {k['lift']:.2f}x")
    t = out["at_threshold"]
    fb = [x for x in t if x.startswith("f") and x not in ("f1", "fp", "fn", "flagged_share")][0]
    print(f"  @ {t['threshold']:g}: TP {t['tp']} FP {t['fp']} FN {t['fn']} TN {t['tn']}  precision {t['precision']:.3f}  "
          f"recall {t['recall']:.3f}  F1 {t['f1']:.3f}  {fb.upper()} {t[fb]:.3f}  bal.acc {t['balanced_accuracy']:.3f}  "
          f"flagged {t['flagged_share']:.1%}")
    if "cost" in out:
        c = out["cost"]
        print(f"  cost/row @ {t['threshold']:g}: {c['at_threshold']:.4f}   best threshold {c['best_threshold']:.4g} -> "
              f"{c['best_cost']:.4f}   (flag nobody {c['flag_nobody']:.4f}, flag everybody {c['flag_everybody']:.4f}; "
              f"calibrated Bayes threshold {c['bayes_threshold_if_calibrated']:.4f})")
    print("  positive rate by score decile: " + " ".join(f"{d['positive_rate']:.2f}" for d in out["deciles"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
