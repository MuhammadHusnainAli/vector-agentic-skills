#!/usr/bin/env python3
"""Profile class imbalance in a CSV target and recommend a handling strategy, cheapest first.

Reports class counts and shares, the imbalance ratio, minority count, how many minority examples
each CV fold would get, and the severity:
  mild      minority >= 20%                     usually nothing special beyond good metrics
  moderate  5% - 20%                            metrics + stratified CV + threshold tuning
  severe    0.5% - 5%                           + class weights or focal-style losses; PR-AUC; capacity metrics
  extreme   < 0.5% or < 100 minority examples   + consider anomaly detection, collecting labels, rules
Then the strategy ladder (each step only if the previous is not enough):
  1 metrics (PR-AUC, recall@K, cost) and a natural-prevalence test set
  2 stratified / grouped CV with enough minority rows per fold
  3 threshold from capacity or costs (threshold_tuner.py)
  4 class weights (class_weight="balanced", scale_pos_weight) - recalibrate if probabilities are used
  5 resampling inside an imblearn Pipeline (random undersampling of negatives for speed,
    SMOTE / ADASYN rarely better than weights for GBMs)
  6 different framing (anomaly detection, two-stage models) or more labels
and, with --code, an imblearn/scikit-learn snippet for steps 4-5.

Usage:
    python imbalance_report.py data.csv --target is_fraud
    python imbalance_report.py data.csv --target churned --folds 5 --model gbm --code
    python imbalance_report.py data.csv --target segment --json        # multiclass

Exit codes: 0 report printed, 2 usage or read error.
"""

import argparse
import csv
import json
import sys
from collections import Counter

LADDER = [
    ("metrics", "Use PR-AUC / recall at the operating point / expected cost; keep the test set at the natural prevalence"),
    ("cv", "Stratified (or StratifiedGroup) K-fold so every fold has enough minority rows; repeat CV when folds are small"),
    ("threshold", "Pick the threshold from capacity or costs on validation data (threshold_tuner.py), not 0.5"),
    ("weights", "Class weights (class_weight='balanced', scale_pos_weight, auto_class_weights) - cheap, no data copies; "
                "probabilities become biased: recalibrate or prior-correct"),
    ("resample", "Resample only the training folds inside an imblearn Pipeline; undersampling negatives speeds training; "
                 "SMOTE helps mainly linear / kNN models on dense numeric data"),
    ("reframe", "Too few positives to learn from: anomaly detection, rules + label collection, or a two-stage model"),
]


def main():
    ap = argparse.ArgumentParser(description="Profile class imbalance and recommend a strategy.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--model", choices=["linear", "gbm", "rf", "knn"], default="gbm")
    ap.add_argument("--code", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            if a.target not in (rd.fieldnames or []):
                raise ValueError(f"target {a.target!r} not found")
            counts = Counter((r[a.target] or "").strip() for r in rd if (r[a.target] or "").strip())
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(counts) < 2:
        print("error: need at least two classes", file=sys.stderr)
        return 2
    n = sum(counts.values())
    minority, m_count = min(counts.items(), key=lambda kv: kv[1])
    majority, M_count = max(counts.items(), key=lambda kv: kv[1])
    share = m_count / n
    per_fold = m_count / a.folds
    if share < 0.005 or m_count < 100:
        sev, steps = "extreme", ["metrics", "cv", "threshold", "weights", "reframe"]
    elif share < 0.05:
        sev, steps = "severe", ["metrics", "cv", "threshold", "weights", "resample"]
    elif share < 0.2:
        sev, steps = "moderate", ["metrics", "cv", "threshold"]
    else:
        sev, steps = "mild", ["metrics", "cv"]
    notes = []
    if per_fold < 30:
        notes.append(f"only ~{per_fold:.0f} minority rows per fold: use fewer folds, RepeatedStratifiedKFold, and report "
                     "confidence intervals")
    if len(counts) > 2:
        rare = [c for c, k in counts.items() if k < 50]
        if rare:
            notes.append(f"{len(rare)} class(es) with < 50 rows ({', '.join(rare[:5])}): merge, collect more, or evaluate "
                         "with per-class recall and macro averages")
    if a.model == "gbm" and "resample" in steps:
        notes.append("for gradient boosting, class weights or plain unweighted training + threshold usually match or "
                     "beat SMOTE; undersample negatives only to cut training time (then prior-correct)")
    if a.model in ("linear", "knn") and "resample" in steps:
        notes.append("linear / kNN models can benefit from SMOTE on dense numeric features; compare with "
                     "class_weight='balanced' on the same folds")
    out = {"rows": n, "classes": dict(counts.most_common()), "minority": minority, "minority_count": m_count,
           "minority_share": share, "imbalance_ratio": M_count / m_count, "minority_per_fold": per_fold,
           "severity": sev, "ladder": [{"step": k, "action": v} for k, v in LADDER if k in steps], "notes": notes}
    if a.code:
        spw = round(M_count / m_count, 2)
        # sampling_strategy = minority/majority ratio after undersampling; must exceed the current ratio
        ratio_now = m_count / M_count
        target = round(min(1.0, max(0.1, 2 * ratio_now)), 3)
        print(f'''# Imbalance handling for {a.target!r}: minority {minority!r} = {share:.2%} ({sev})
from imblearn.pipeline import Pipeline                 # pip install imbalanced-learn; samplers run on training folds only
from imblearn.under_sampling import RandomUnderSampler
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

cv = StratifiedKFold(n_splits={a.folds}, shuffle=True, random_state=0)

# Step 4: class weights (no resampling)
weighted = Pipeline([("prep", prep), ("model", LogisticRegression(class_weight="balanced", max_iter=5000))])
# LightGBM: LGBMClassifier(scale_pos_weight={spw})   XGBoost: XGBClassifier(scale_pos_weight={spw})
# CatBoost: CatBoostClassifier(auto_class_weights="Balanced")

# Step 5: resampling inside the pipeline (never before the split)
under = Pipeline([("prep", prep), ("under", RandomUnderSampler(sampling_strategy={target}, random_state=0)),   # now {ratio_now:.3f}
                  ("model", LogisticRegression(max_iter=5000))])
smote = Pipeline([("prep", prep), ("smote", SMOTE(k_neighbors=5, random_state=0)),
                  ("model", LogisticRegression(max_iter=5000))])

for name, pipe in {{"weighted": weighted, "under": under, "smote": smote}}.items():
    print(name, cross_val_score(pipe, X, y, cv=cv, scoring="average_precision").mean().round(4))
# Undersampling changes probabilities: training positive rate becomes {target / (1 + target):.4f};
# correct with threshold_tuner.py --train-rate {target / (1 + target):.4f} --true-rate {share:.4f}
''')
        return 0
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"Target {a.target!r}: {len(counts)} classes, {n} rows")
    for c, k in counts.most_common(10):
        print(f"  {c!s:<16} {k:>8}  {k / n:7.2%}")
    print(f"minority {minority!r}: {m_count} rows ({share:.2%}), imbalance ratio {M_count / m_count:.1f}:1, "
          f"~{per_fold:.0f} per fold with {a.folds} folds -> severity: {sev.upper()}")
    print("\nStrategy (stop at the first step that meets the goal):")
    for i, st in enumerate(out["ladder"], 1):
        print(f"  {i}. {st['action']}")
    for nt in notes:
        print(f"note: {nt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
