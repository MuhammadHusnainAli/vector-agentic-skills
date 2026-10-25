#!/usr/bin/env python3
"""Show how much naive (in-sample) target encoding inflates a categorical column's apparent signal.

For each categorical column, against a binary target, it computes the ROC-AUC of three
encodings used as the only feature:
  in_sample   level mean computed on all rows, including the row itself     (what people do by mistake)
  out_of_fold level mean from the other K folds, smoothed toward the prior  (what TargetEncoder(cv=K) does)
  holdout     level mean learned on the first 80% of rows (by --time-col if given), scored on the last 20%
The gap in_sample - out_of_fold is the optimism created by leakage; high-cardinality columns
with few rows per level show gaps of 0.1-0.4 AUC even when the column is pure noise.

Usage:
    python te_leakage_check.py data.csv --target is_fraud
    python te_leakage_check.py data.csv --target churned --columns zip_code plan --folds 5 --smooth 20
    python te_leakage_check.py data.csv --target churned --time-col signup_date --json

A column is flagged when the gap exceeds --max-gap (default 0.05) and it has fewer than
--min-rows-per-level rows per level (default 50). Low-cardinality columns show small gaps that
mostly come from the out-of-fold estimate dipping below 0.5 for pure-noise columns.

Exit codes: 0 no flagged column, 1 at least one flagged column, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
import zlib
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def auc(s, y):
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return float("nan")
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


def means(vals, ys, prior, m):
    st = defaultdict(lambda: [0.0, 0])
    for v, y in zip(vals, ys):
        st[v][0] += y
        st[v][1] += 1
    return {v: (s + m * prior) / (n + m) for v, (s, n) in st.items()}


def is_num(v):
    try:
        return math.isfinite(float(v))
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser(description="Measure target-encoding leakage per categorical column.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--columns", nargs="*", help="columns to check (default: every non-numeric column)")
    ap.add_argument("--time-col")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--smooth", type=float, default=10.0, help="smoothing strength m in (sum + m*prior)/(n + m)")
    ap.add_argument("--max-gap", type=float, default=0.05)
    ap.add_argument("--min-rows-per-level", type=float, default=50,
                    help="flag only columns with fewer rows per level than this (default 50)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = [r for r in reader if (r.get(a.target) or "").strip().lower() not in MISSING]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    classes = Counter(r[a.target].strip() for r in rows)
    if a.target not in header or len(classes) != 2:
        print("error: target must exist and be binary", file=sys.stderr)
        return 2
    pos = min(classes, key=classes.get)
    if a.time_col:
        rows.sort(key=lambda r: r.get(a.time_col, ""))
    y = [1 if r[a.target].strip() == pos else 0 for r in rows]
    prior = sum(y) / len(y)
    cols = a.columns or [c for c in header if c not in (a.target, a.time_col)
                         and not all(is_num(r[c]) for r in rows if r[c].strip())]
    folds = [zlib.crc32(str(i).encode()) % a.folds for i in range(len(rows))]
    cut = int(len(rows) * 0.8)
    results = []
    for c in cols:
        if c not in header:
            print(f"error: column {c!r} not found", file=sys.stderr)
            return 2
        vals = [r[c].strip() for r in rows]
        k = len(set(vals))
        ins = means(vals, y, prior, 0.0)
        a_in = auc([ins[v] for v in vals], y)
        oof = [0.0] * len(rows)
        for f in range(a.folds):
            tr = [(v, t) for v, t, k_ in zip(vals, y, folds) if k_ != f]
            mp = means([v for v, _ in tr], [t for _, t in tr], prior, a.smooth)
            for i, (v, k_) in enumerate(zip(vals, folds)):
                if k_ == f:
                    oof[i] = mp.get(v, prior)
        a_oof = auc(oof, y)
        mp = means(vals[:cut], y[:cut], prior, a.smooth)
        a_ho = auc([mp.get(v, prior) for v in vals[cut:]], y[cut:])
        gap = a_in - a_oof
        results.append({"column": c, "levels": k, "rows_per_level": round(len(rows) / k, 1),
                        "auc_in_sample": round(a_in, 4), "auc_out_of_fold": round(a_oof, 4),
                        "auc_holdout": round(a_ho, 4), "gap": round(gap, 4),
                        # With many rows per level the in-sample optimism is small; the OOF AUC of a pure-noise
                        # column can even dip below 0.5 (leave-fold-out bias), which inflates the gap.
                        "dangerous": gap > a.max_gap and len(rows) / k < a.min_rows_per_level})
    results.sort(key=lambda r: -r["gap"])
    bad = any(r["dangerous"] for r in results)
    if a.json:
        print(json.dumps({"prior": prior, "columns": results}, indent=2))
        return 1 if bad else 0
    print(f"Target {a.target!r} == {pos!r} (rate {prior:.3f}); single-feature ROC-AUC of target-encoded columns")
    print(f"{'column':<22} {'levels':>6} {'rows/lvl':>8} {'in-sample':>9} {'OOF':>7} {'holdout':>8} {'gap':>7}")
    for r in results:
        flag = "  <- in-sample encoding leaks" if r["dangerous"] else ""
        print(f"{r['column']:<22} {r['levels']:>6} {r['rows_per_level']:>8} {r['auc_in_sample']:>9.3f} "
              f"{r['auc_out_of_fold']:>7.3f} {r['auc_holdout']:>8.3f} {r['gap']:>+7.3f}{flag}")
    print("\nThe out-of-fold and holdout columns are the honest numbers. Encode with sklearn TargetEncoder (cross-fitted "
          "in fit_transform), category_encoders inside CV, or CatBoost ordered statistics - never a groupby mean over "
          "the full data.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
