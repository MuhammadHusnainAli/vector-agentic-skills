#!/usr/bin/env python3
"""Starting hyperparameters, a search space and early-stopping settings for XGBoost or LightGBM,
scaled to the dataset (rows, features, positives, categorical share, time budget).

The logic encodes the usual tuning order:
  1. fix a learning rate (0.05-0.1 while searching; lower for the final fit) and use early stopping
     for the number of trees
  2. capacity: num_leaves / max_depth and min_child_samples / min_child_weight (sized to the data)
  3. randomness: subsample (bagging) and colsample_bytree (feature fraction)
  4. regularisation: lambda_l2 / reg_lambda, lambda_l1 / reg_alpha, min_gain_to_split / gamma
  5. refit with a lower learning rate and proportionally more trees

Also prints the parameter-name map between LightGBM, XGBoost and CatBoost, and imbalance
handling (scale_pos_weight vs is_unbalance vs leaving the data alone).

Usage:
    python gbm_param_advisor.py --library lightgbm --rows 200000 --features 80 --task binary --positives 4000
    python gbm_param_advisor.py --library xgboost --rows 3000 --features 25 --task regression --json
    python gbm_param_advisor.py --map            # parameter equivalence table only

Exit codes: 0 printed, 2 usage error.
"""

import argparse
import json
import math
import sys

MAP = [
    ("learning rate", "learning_rate (eta)", "learning_rate (eta)", "learning_rate"),
    ("number of trees", "n_estimators / num_boost_round", "n_estimators / num_boost_round", "iterations"),
    ("tree size", "num_leaves (+ max_depth=-1)", "max_depth (or max_leaves with grow_policy=lossguide)", "depth"),
    ("min data in leaf", "min_child_samples (min_data_in_leaf)", "min_child_weight (hessian sum)", "min_data_in_leaf"),
    ("row subsampling", "subsample (bagging_fraction) + subsample_freq >= 1", "subsample", "subsample / bootstrap_type"),
    ("feature subsampling", "colsample_bytree (feature_fraction)", "colsample_bytree / colsample_bylevel / bynode", "rsm"),
    ("L2 on leaf weights", "reg_lambda (lambda_l2)", "reg_lambda (lambda)", "l2_leaf_reg"),
    ("L1 on leaf weights", "reg_alpha (lambda_l1)", "reg_alpha (alpha)", "-"),
    ("min split gain", "min_split_gain (min_gain_to_split)", "gamma (min_split_loss)", "-"),
    ("histogram bins", "max_bin", "max_bin", "border_count"),
    ("categoricals", "categorical_feature / category dtype", "enable_categorical=True + category dtype", "cat_features"),
    ("class imbalance", "scale_pos_weight or is_unbalance", "scale_pos_weight", "auto_class_weights / scale_pos_weight"),
    ("monotonicity", "monotone_constraints", "monotone_constraints", "monotone_constraints"),
    ("early stopping", "callbacks=[lgb.early_stopping(n)]", "early_stopping_rounds=n (constructor)", "od_type='Iter', od_wait=n"),
    ("objective (binary)", "objective='binary'", "objective='binary:logistic'", "loss_function='Logloss'"),
    ("objective (multiclass)", "objective='multiclass', num_class=K", "objective='multi:softprob'", "loss_function='MultiClass'"),
    ("objective (regression)", "objective='regression'", "objective='reg:squarederror'", "loss_function='RMSE'"),
]


def advise(a):
    n, p = a.rows, a.features
    lr_search = 0.1 if n < 100_000 else 0.05
    lr_final = lr_search / 2 if a.budget != "low" else lr_search
    # leaf sizes scale with data: ~0.1-1% of rows per leaf, clamped
    mcs = int(min(1000, max(5, n * 0.002)))
    mcs_lo, mcs_hi = max(2, mcs // 4), min(2000, mcs * 4)
    leaves = 31 if n > 20_000 else 15
    leaves_hi = 255 if n > 1_000_000 else (127 if n > 100_000 else 63)
    depth = 6 if n > 20_000 else 4
    col = 0.8 if p > 20 else 1.0
    patience = int(min(300, max(50, 10 / lr_search)))
    imb = {}
    if a.task == "binary" and a.positives:
        rate = a.positives / n
        imb = {"positive_rate": round(rate, 5), "scale_pos_weight_if_needed": round((n - a.positives) / a.positives, 2),
               "advice": ("leave the data alone and evaluate with PR-AUC; only set scale_pos_weight (or is_unbalance) "
                          "if recall at the default threshold matters more than calibrated probabilities")
               if rate < 0.2 else "balanced enough: no weighting"}
        if a.positives < 1000:
            mcs = max(5, min(mcs, a.positives // 20))
            mcs_lo, mcs_hi = max(2, mcs // 4), max(mcs * 4, 20)
    if a.library == "lightgbm":
        start = {"objective": {"binary": "binary", "multiclass": "multiclass", "regression": "regression"}[a.task],
                 "learning_rate": lr_search, "n_estimators": 10000, "num_leaves": leaves, "max_depth": -1,
                 "min_child_samples": mcs, "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": col,
                 "reg_lambda": 1.0, "reg_alpha": 0.0, "min_split_gain": 0.0, "max_bin": 255, "n_jobs": -1,
                 "random_state": 0, "verbose": -1}
        space = {"num_leaves": ["int", 7, leaves_hi, "log"], "min_child_samples": ["int", mcs_lo, mcs_hi, "log"],
                 "subsample": ["float", 0.5, 1.0], "colsample_bytree": ["float", 0.3, 1.0],
                 "reg_lambda": ["float", 1e-3, 30.0, "log"], "reg_alpha": ["float", 1e-3, 10.0, "log"],
                 "min_split_gain": ["float", 0.0, 1.0], "learning_rate": ["fixed", lr_search]}
        early = f"callbacks=[lightgbm.early_stopping({patience}), lightgbm.log_evaluation(0)] with eval_set on a validation fold"
    else:
        start = {"objective": {"binary": "binary:logistic", "multiclass": "multi:softprob",
                               "regression": "reg:squarederror"}[a.task],
                 "tree_method": "hist", "learning_rate": lr_search, "n_estimators": 10000, "max_depth": depth,
                 "min_child_weight": max(1, mcs // 10), "subsample": 0.8, "colsample_bytree": col,
                 "reg_lambda": 1.0, "reg_alpha": 0.0, "gamma": 0.0, "max_bin": 256, "n_jobs": -1,
                 "random_state": 0, "early_stopping_rounds": patience}
        space = {"max_depth": ["int", 3, 10], "min_child_weight": ["float", 1.0, max(2.0, mcs / 2), "log"],
                 "subsample": ["float", 0.5, 1.0], "colsample_bytree": ["float", 0.3, 1.0],
                 "reg_lambda": ["float", 1e-3, 30.0, "log"], "reg_alpha": ["float", 1e-3, 10.0, "log"],
                 "gamma": ["float", 0.0, 5.0], "learning_rate": ["fixed", lr_search]}
        early = f"early_stopping_rounds={patience} in the constructor; eval_set=[(X_valid, y_valid)] in fit"
    if a.cat_share > 0.3:
        start_note = ("many categoricals: use native categorical support (category dtype); for LightGBM tune "
                      "cat_smooth (1-100) and min_data_per_group; consider CatBoost as a comparison")
    else:
        start_note = ""
    trials = {"low": 30, "medium": 80, "high": 200}[a.budget]
    if n < 2000:
        trials = min(trials, 50)
    plan = [
        f"1. CV or a validation split mirroring deployment; early stopping inside each fold ({early})",
        f"2. search {trials} trials (TPE / random) over the space below at learning_rate={lr_search}",
        "3. read the importance of each hyperparameter; fix the unimportant ones; narrow ranges if the best sits at a bound",
        f"4. final fit: learning_rate={lr_final}, n_estimators = best_iteration x {lr_search / lr_final:.0f} x 1.1 "
        "(or early-stop again on a validation split), on all training data",
        "5. confirm on the untouched holdout; compare with the untuned default (tuning gains are often 1-3%)",
    ]
    return {"library": a.library, "task": a.task, "rows": n, "features": p, "start": start, "search_space": space,
            "early_stopping": early, "trials": trials, "final_learning_rate": lr_final, "imbalance": imb,
            "notes": [x for x in [start_note] if x], "plan": plan}


def main():
    ap = argparse.ArgumentParser(description="GBM starting parameters and search space sized to the data.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--library", choices=["lightgbm", "xgboost"], default="lightgbm")
    ap.add_argument("--task", choices=["binary", "multiclass", "regression"], default="binary")
    ap.add_argument("--rows", type=int)
    ap.add_argument("--features", type=int)
    ap.add_argument("--positives", type=int, help="positive-class count (binary)")
    ap.add_argument("--cat-share", type=float, default=0.0)
    ap.add_argument("--budget", choices=["low", "medium", "high"], default="medium")
    ap.add_argument("--map", action="store_true", help="print only the LightGBM / XGBoost / CatBoost name map")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.map:
        print(f"{'concept':<24} {'LightGBM':<42} {'XGBoost':<46} CatBoost")
        for row in MAP:
            print(f"{row[0]:<24} {row[1]:<42} {row[2]:<46} {row[3]}")
        return 0
    if not a.rows or not a.features:
        print("error: --rows and --features are required (or --map)", file=sys.stderr)
        return 2
    if a.positives and a.positives >= a.rows:
        print("error: --positives must be smaller than --rows", file=sys.stderr)
        return 2
    r = advise(a)
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    print(f"{a.library} / {a.task}: {a.rows:,} rows x {a.features} features")
    print("\nStarting parameters:")
    for k, v in r["start"].items():
        print(f"  {k} = {v!r}")
    print("\nSearch space (type, low, high, scale):")
    for k, v in r["search_space"].items():
        print(f"  {k:<18} {v}")
    if r["imbalance"]:
        im = r["imbalance"]
        print(f"\nImbalance: positive rate {im['positive_rate']:.3%}; scale_pos_weight would be "
              f"{im['scale_pos_weight_if_needed']} - {im['advice']}")
    for nte in r["notes"]:
        print(f"\nnote: {nte}")
    print("\nPlan:")
    for step in r["plan"]:
        print(f"  {step}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
