#!/usr/bin/env python3
"""Recommend a scaler / transform for every numeric column, for a given model family.

Per column it measures: range, mean/std, median/IQR, skew, share of robust outliers
(|x - median| / (1.4826 * MAD) > 3.5), zero share, negatives, whether values are bounded in
[0, 1], and integer-ness. It also reports the spread of standard deviations across columns
(why unscaled distance-based models are dominated by the widest column).

Model families:
  tree      random forest, gradient boosting, decision trees: no scaling needed (monotone-invariant)
  linear    linear/logistic regression with regularisation, SVM, PCA, k-NN, k-means, neural nets:
            scale everything; choose the transform per column shape
  nn        like linear, but prefers bounded / Gaussian-like inputs (QuantileTransformer for heavy tails)
  sparse    sparse matrices (TF-IDF, one-hot heavy): MaxAbsScaler (keeps zeros)

Per-column choices: none, StandardScaler, RobustScaler, log1p -> StandardScaler,
PowerTransformer(yeo-johnson), PowerTransformer(box-cox), QuantileTransformer(normal), MinMaxScaler,
MaxAbsScaler, passthrough (binary 0/1).

Usage:
    python scaling_plan.py data.csv --model linear --drop customer_id --target churned
    python scaling_plan.py data.csv --model tree
    python scaling_plan.py data.csv --model linear --target price --code > prep.py

Exit codes: 0 plan printed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def q(xs, p):
    pos = (len(xs) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def stats(xs):
    xs = sorted(xs)
    n = len(xs)
    mean = sum(xs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / n)
    med = q(xs, 0.5)
    mad = q(sorted(abs(x - med) for x in xs), 0.5) * 1.4826
    skew = 0.0 if sd == 0 else sum(((x - mean) / sd) ** 3 for x in xs) / n
    out = sum(1 for x in xs if mad and abs(x - med) / mad > 3.5) / n
    return {"n": n, "min": xs[0], "max": xs[-1], "mean": mean, "std": sd, "median": med,
            "iqr": q(xs, 0.75) - q(xs, 0.25), "skew": skew, "outlier_share": out,
            "zero_share": sum(1 for x in xs if x == 0) / n, "negatives": xs[0] < 0,
            "integer": all(x.is_integer() for x in xs), "distinct": len(set(xs))}


def choose(s, model):
    if s["distinct"] <= 2:
        return "passthrough", "binary indicator: leave as 0/1"
    if model == "tree":
        return "none", "trees split on thresholds; any monotone rescaling gives the same model"
    if model == "sparse":
        return "MaxAbsScaler", "keeps sparsity (zeros stay zero), scales to [-1, 1]"
    heavy = abs(s["skew"]) > 1 or s["outlier_share"] > 0.05
    if 0 <= s["min"] and s["max"] <= 1 and not heavy:
        return ("none" if model == "nn" else "StandardScaler"), "already bounded in [0, 1]" + (
            "" if model == "nn" else "; standardise so its scale matches other features")
    if heavy:
        if s["min"] >= 0 and s["skew"] > 1:
            if model == "nn" and s["outlier_share"] > 0.05:
                return "QuantileTransformer(normal)", "heavy right tail with outliers: rank-based transform to N(0,1)"
            if s["zero_share"] > 0:
                return "log1p -> StandardScaler", f"right-skewed (skew {s['skew']:.1f}) with zeros: log1p then standardise"
            return "PowerTransformer(box-cox)", f"strictly positive, right-skewed (skew {s['skew']:.1f})"
        if s["outlier_share"] > 0.05 and abs(s["skew"]) <= 1:
            return "RobustScaler", f"{s['outlier_share']:.0%} robust outliers: centre on median, scale by IQR"
        return "PowerTransformer(yeo-johnson)", f"skewed (skew {s['skew']:.1f}) with negatives: Yeo-Johnson"
    return "StandardScaler", "roughly symmetric, few outliers: zero mean, unit variance"


CODE = {
    "StandardScaler": "StandardScaler()",
    "RobustScaler": "RobustScaler(quantile_range=(25.0, 75.0))",
    "log1p -> StandardScaler": 'make_pipeline(FunctionTransformer(np.log1p, inverse_func=np.expm1, '
                               'feature_names_out="one-to-one"), StandardScaler())',
    "PowerTransformer(box-cox)": 'PowerTransformer(method="box-cox")',
    "PowerTransformer(yeo-johnson)": 'PowerTransformer(method="yeo-johnson")',
    "QuantileTransformer(normal)": 'QuantileTransformer(output_distribution="normal", n_quantiles=1000, subsample=100_000)',
    "MaxAbsScaler": "MaxAbsScaler()",
    "MinMaxScaler": "MinMaxScaler()",
    "passthrough": '"passthrough"',
    "none": '"passthrough"',
}


def main():
    ap = argparse.ArgumentParser(description="Recommend per-column scaling for a model family.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--model", choices=["tree", "linear", "nn", "sparse"], default="linear")
    ap.add_argument("--target", help="excluded from scaling (scale a regression target separately)")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--code", action="store_true")
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
    plan = []
    for c in header:
        if c == a.target or c in a.drop:
            continue
        vals = [(r.get(c) or "").strip() for r in rows]
        present = [v for v in vals if v.lower() not in MISSING]
        xs = [num(v) for v in present]
        if not present or any(x is None for x in xs):
            continue
        s = stats(xs)
        s["missing"] = 1 - len(present) / len(vals)
        choice, why = choose(s, a.model)
        plan.append({"column": c, "transform": choice, "why": why, **{k: (round(v, 4) if isinstance(v, float) else v)
                                                                       for k, v in s.items()}})
    if not plan:
        print("error: no numeric columns found", file=sys.stderr)
        return 2
    stds = [p["std"] for p in plan if p["std"] > 0 and p["distinct"] > 2]
    ratio = max(stds) / min(stds) if stds else 1.0
    if a.code:
        groups = defaultdict(list)
        for p in plan:
            groups[p["transform"]].append(p["column"])
        print("import numpy as np\nfrom sklearn.compose import ColumnTransformer\nfrom sklearn.impute import SimpleImputer\n"
              "from sklearn.pipeline import make_pipeline\nfrom sklearn.preprocessing import (FunctionTransformer, MaxAbsScaler, "
              "MinMaxScaler, PowerTransformer,\n                                   QuantileTransformer, RobustScaler, "
              "StandardScaler)\n\nnumeric_steps = [")
        for t, cols in groups.items():
            name = re.sub(r"\W+", "_", t.lower()).strip("_")          # unique per transform, e.g. powertransformer_box_cox
            step = CODE[t]
            if step != '"passthrough"':
                step = f'make_pipeline(SimpleImputer(strategy="median"), {step})'
            print(f'    ("{name}", {step}, {cols!r}),')
        print("]\nprep = ColumnTransformer(numeric_steps, remainder=\"passthrough\")\n"
              "# Fit inside a Pipeline: scalers learn their statistics from the training fold only.")
        return 0
    if a.json:
        print(json.dumps({"model": a.model, "std_ratio": round(ratio, 2), "columns": plan}, indent=2))
        return 0
    print(f"Scaling plan for '{a.model}' models: {len(plan)} numeric column(s); largest/smallest std ratio "
          f"{ratio:,.0f}x")
    if a.model != "tree" and ratio > 10:
        print("  unscaled, distance- and penalty-based models would be dominated by the widest columns")
    print(f"{'column':<20} {'min':>10} {'max':>10} {'skew':>6} {'outl%':>6} {'zero%':>6}  transform")
    for p in plan:
        print(f"{p['column']:<20} {p['min']:>10.4g} {p['max']:>10.4g} {p['skew']:>6.2f} {p['outlier_share']:>6.1%} "
              f"{p['zero_share']:>6.1%}  {p['transform']:<28} {p['why']}")
    print("\nFit every scaler inside the Pipeline (training folds only). Run with --code for the ColumnTransformer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
