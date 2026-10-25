#!/usr/bin/env python3
"""Measure how scaling changes a distance-based model on your data: raw vs standard vs robust vs log.

Runs a k-nearest-neighbours model (pure Python, Euclidean distance) with K-fold cross-validation
on the numeric columns of a CSV, once per scaling scheme, with the scaler fitted on each training
fold only:
  raw        no scaling
  standard   (x - mean) / std
  robust     (x - median) / IQR
  log_std    log1p for non-negative right-skewed columns (skew > 1), then standard
  minmax     (x - min) / (max - min)
Binary targets are scored with ROC-AUC (share of positive neighbours as the score), numeric targets
with MAE. It also reports which column dominates the raw distances (share of the summed squared
differences), the usual reason raw k-NN, k-means, SVM-RBF and PCA results look odd.

Usage:
    python scale_impact.py data.csv --target churned --drop customer_id
    python scale_impact.py data.csv --target price --k 10 --folds 5 --max-rows 1500

Exit codes: 0 measured, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import random
import sys

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def col_stats(col):
    s = sorted(col)
    n = len(s)
    mean = sum(s) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in s) / n) or 1.0
    q = lambda p: s[min(n - 1, int(p * (n - 1)))]
    iqr = (q(0.75) - q(0.25)) or sd
    skew = sum(((x - mean) / sd) ** 3 for x in s) / n
    return {"mean": mean, "sd": sd, "median": q(0.5), "iqr": iqr, "min": s[0], "max": s[-1], "skew": skew}


def fit_scaler(X, scheme):
    cols = list(zip(*X))
    st = [col_stats(c) for c in cols]
    logs = [scheme == "log_std" and s["min"] >= 0 and s["skew"] > 1 for s in st]
    if any(logs):
        cols = [[math.log1p(x) for x in c] if lg else list(c) for c, lg in zip(cols, logs)]
        st = [col_stats(c) for c in cols]

    def transform(rows):
        out = []
        for r in rows:
            v = []
            for x, s, lg in zip(r, st, logs):
                x = math.log1p(x) if lg else x
                if scheme == "raw":
                    v.append(x)
                elif scheme in ("standard", "log_std"):
                    v.append((x - s["mean"]) / s["sd"])
                elif scheme == "robust":
                    v.append((x - s["median"]) / s["iqr"])
                else:
                    rng = (s["max"] - s["min"]) or 1.0
                    v.append((x - s["min"]) / rng)
            out.append(v)
        return out
    return transform


def knn_predict(train_X, train_y, test_X, k):
    preds = []
    for t in test_X:
        d = sorted((sum((a - b) ** 2 for a, b in zip(t, x)), y) for x, y in zip(train_X, train_y))[:k]
        preds.append(sum(y for _, y in d) / len(d))
    return preds


def auc(s, y):
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return float("nan")
    pairs = sorted(zip(s, y))
    rank, i = [0.0] * len(pairs), 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        for k in range(i, j + 1):
            rank[k] = (i + j) / 2 + 1
        i = j + 1
    return (sum(r for r, (_, t) in zip(rank, pairs) if t) - pos * (pos + 1) / 2) / (pos * neg)


def main():
    ap = argparse.ArgumentParser(description="Compare k-NN performance under different scalings.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--max-rows", type=int, default=1200, help="random sample cap (k-NN is O(n^2))")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.target not in header:
        print(f"error: target {a.target!r} not found", file=sys.stderr)
        return 2
    feats = [c for c in header if c != a.target and c not in a.drop
             and all(num(r[c]) is not None for r in rows if (r[c] or "").strip().lower() not in MISSING)
             and any((r[c] or "").strip() for r in rows)]
    data = []
    for r in rows:
        x = [num(r[c]) for c in feats]
        t = (r[a.target] or "").strip()
        if t.lower() not in MISSING and all(v is not None for v in x):
            data.append((x, t))
    if len(data) < 2 * a.folds or not feats:
        print("error: not enough complete numeric rows", file=sys.stderr)
        return 2
    rnd = random.Random(a.seed)
    rnd.shuffle(data)
    data = data[:a.max_rows]
    labels = sorted({t for _, t in data})
    binary = len(labels) == 2
    if binary:
        pos = min(labels, key=lambda l: sum(t == l for _, t in data))
        ys = [1.0 if t == pos else 0.0 for _, t in data]
    else:
        try:
            ys = [float(t) for _, t in data]
        except ValueError:
            print("error: target must be binary or numeric", file=sys.stderr)
            return 2
    X = [x for x, _ in data]
    st = [col_stats(c) for c in zip(*X)]
    var_share = [s["sd"] ** 2 for s in st]
    total = sum(var_share) or 1.0
    dominance = sorted(((v / total, c) for v, c in zip(var_share, feats)), reverse=True)
    results = {}
    for scheme in ("raw", "standard", "robust", "log_std", "minmax"):
        preds, truth = [0.0] * len(X), ys
        for f in range(a.folds):
            tr = [i for i in range(len(X)) if i % a.folds != f]
            te = [i for i in range(len(X)) if i % a.folds == f]
            tf = fit_scaler([X[i] for i in tr], scheme)
            p = knn_predict(tf([X[i] for i in tr]), [ys[i] for i in tr], tf([X[i] for i in te]), a.k)
            for i, v in zip(te, p):
                preds[i] = v
        results[scheme] = auc(preds, truth) if binary else sum(abs(p - t) for p, t in zip(preds, truth)) / len(truth)
    metric = "ROC-AUC (higher is better)" if binary else "MAE (lower is better)"
    best = max(results, key=results.get) if binary else min(results, key=results.get)
    if a.json:
        print(json.dumps({"metric": metric, "results": results, "best": best,
                          "raw_distance_share": [{"column": c, "share": round(s, 4)} for s, c in dominance]}, indent=2))
        return 0
    print(f"{len(X)} rows, {len(feats)} numeric features, {a.k}-NN, {a.folds}-fold CV, metric: {metric}")
    print("Share of raw squared-distance variance by column (unscaled):")
    for s, c in dominance[:5]:
        print(f"  {c:<22} {s:6.1%}")
    print("\nScheme      score")
    for k, v in results.items():
        print(f"  {k:<10} {v:10.4f}{'   <- best' if k == best else ''}")
    gap = abs(results[best] - results["raw"])
    print(f"\nScaling changes the score by {gap:.4f} vs raw." + (
        " Raw distances are dominated by one column; always scale for k-NN, k-means, SVM, PCA and penalised models."
        if dominance[0][0] > 0.9 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
