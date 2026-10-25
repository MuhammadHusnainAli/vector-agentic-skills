#!/usr/bin/env python3
"""Plan a hyperparameter search: strategy, trial budget, search space with scales, what to fix, and code.

Inputs: model family, rows, CV folds, seconds per single fit (measure one!) and a wall-clock budget
(or a trial count), parallel workers. Output:
  strategy   grid (<= ~30 combinations, all discrete) | random (cheap fits, few params) |
             successive halving (many candidates, cheap partial fits on fewer rows) |
             TPE / Bayesian (expensive fits, 3+ continuous params) - with pruning when folds or
             boosting rounds give intermediate scores
  budget     trials that fit: budget / (fit_seconds x folds) x workers, capped by the space size
  space      ranges per family with log scales where the effect is multiplicative, the parameters
             to FIX (n_estimators via early stopping, random_state, n_jobs), and conditional parameters
  code       scikit-learn RandomizedSearchCV / HalvingRandomSearchCV distributions or Optuna suggest_* lines

Families: logreg, elasticnet, svm, knn, rf, et, hgb, lgbm, xgb, catboost, mlp.

Usage:
    python search_planner.py --model lgbm --rows 200000 --fit-seconds 40 --budget-hours 4 --folds 5 --workers 4
    python search_planner.py --model logreg --rows 5000 --fit-seconds 0.5 --trials 60
    python search_planner.py --model rf --rows 50000 --fit-seconds 20 --budget-hours 1 --format optuna

Exit codes: 0 printed, 2 usage error.
"""

import argparse
import json
import math
import sys

# (name, kind, low, high, scale) ; kind: float | int | cat ; scale: log | lin ; cat: choices in low
SPACES = {
    "logreg": [("C", "float", 1e-4, 1e2, "log"), ("penalty", "cat", ["l2", "l1"], None, None)],
    "elasticnet": [("alpha", "float", 1e-5, 1e1, "log"), ("l1_ratio", "float", 0.05, 0.95, "lin")],
    "svm": [("C", "float", 1e-2, 1e3, "log"), ("gamma", "float", 1e-4, 1e1, "log")],
    "knn": [("n_neighbors", "int", 3, 100, "log"), ("weights", "cat", ["uniform", "distance"], None, None)],
    "rf": [("max_features", "float", 0.1, 0.8, "lin"), ("min_samples_leaf", "int", 1, 50, "log"),
           ("max_depth", "cat", [None, 8, 16, 32], None, None)],
    "et": [("max_features", "float", 0.1, 0.9, "lin"), ("min_samples_leaf", "int", 1, 50, "log")],
    "hgb": [("learning_rate", "float", 0.02, 0.3, "log"), ("max_leaf_nodes", "int", 8, 128, "log"),
            ("min_samples_leaf", "int", 5, 300, "log"), ("l2_regularization", "float", 1e-4, 10.0, "log"),
            ("max_features", "float", 0.3, 1.0, "lin")],
    "lgbm": [("num_leaves", "int", 7, 255, "log"), ("min_child_samples", "int", 5, 500, "log"),
             ("subsample", "float", 0.5, 1.0, "lin"), ("colsample_bytree", "float", 0.3, 1.0, "lin"),
             ("reg_lambda", "float", 1e-3, 30.0, "log"), ("reg_alpha", "float", 1e-3, 10.0, "log")],
    "xgb": [("max_depth", "int", 3, 10, "lin"), ("min_child_weight", "float", 1.0, 50.0, "log"),
            ("subsample", "float", 0.5, 1.0, "lin"), ("colsample_bytree", "float", 0.3, 1.0, "lin"),
            ("reg_lambda", "float", 1e-3, 30.0, "log"), ("gamma", "float", 1e-3, 5.0, "log")],
    "catboost": [("depth", "int", 4, 9, "lin"), ("l2_leaf_reg", "float", 1.0, 20.0, "log"),
                 ("random_strength", "float", 0.1, 10.0, "log"), ("learning_rate", "float", 0.02, 0.15, "log")],
    "mlp": [("hidden_units", "int", 16, 512, "log"), ("alpha", "float", 1e-6, 1e-1, "log"),
            ("learning_rate_init", "float", 1e-4, 1e-2, "log")],
}
FIXED = {
    "lgbm": "learning_rate=0.05 during search (lower for the final fit); n_estimators via early stopping; subsample_freq=1",
    "xgb": "learning_rate=0.05 during search; n_estimators via early_stopping_rounds; tree_method='hist'",
    "catboost": "iterations via od_type='Iter', od_wait=150; bootstrap_type fixed or conditional (Bayesian vs subsample)",
    "hgb": "max_iter=1000 with early_stopping=True",
    "rf": "n_estimators=300-500 (more never hurts accuracy, only time)",
    "et": "n_estimators=300-500",
    "logreg": "solver='saga' (supports l1 and l2), max_iter=5000; scale features",
    "elasticnet": "max_iter=10000; scale features",
    "svm": "kernel='rbf'; scale features; consider a subsample for search",
    "knn": "scale features",
    "mlp": "early_stopping=True; hidden layers = (hidden_units, hidden_units // 2)",
}
PREFIX = {"logreg": "model__", "elasticnet": "model__", "svm": "model__", "knn": "model__", "rf": "model__",
          "et": "model__", "hgb": "model__", "lgbm": "model__", "xgb": "model__", "catboost": "model__", "mlp": "model__"}


def space_size(space, grid_points=5):
    size = 1
    for _, kind, lo, hi, _ in space:
        size *= len(lo) if kind == "cat" else (min(grid_points, hi - lo + 1) if kind == "int" else grid_points)
    return size


def main():
    ap = argparse.ArgumentParser(description="Plan a hyperparameter search.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=sorted(SPACES))
    ap.add_argument("--rows", type=int, required=True)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--fit-seconds", type=float, required=True, help="seconds for ONE fit on one training fold")
    ap.add_argument("--budget-hours", type=float)
    ap.add_argument("--trials", type=int, help="fixed number of trials instead of a time budget")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--format", choices=["sklearn", "optuna"], default="sklearn")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not a.budget_hours and not a.trials:
        print("error: give --budget-hours or --trials", file=sys.stderr)
        return 2
    space = SPACES[a.model]
    per_trial = a.fit_seconds * a.folds
    affordable = int(a.budget_hours * 3600 / per_trial * a.workers) if a.budget_hours else a.trials
    n_cont = sum(1 for p in space if p[1] in ("float", "int"))
    total_grid = space_size(space)
    if all(p[1] == "cat" for p in space) or total_grid <= min(30, affordable):
        strategy = "grid"
        trials = total_grid
    elif per_trial < 5 and n_cont <= 2:
        strategy = "random"
        trials = min(affordable, 60)
    elif affordable >= 4 * 30 and a.rows >= 20000 and a.model not in ("lgbm", "xgb", "catboost"):
        strategy = "successive halving (HalvingRandomSearchCV)"
        trials = min(affordable * 3, 300)
    else:
        strategy = "TPE (Optuna) with pruning" if a.model in ("lgbm", "xgb", "catboost", "hgb", "mlp") else "TPE (Optuna)"
        trials = min(affordable, 200)
    warnings = []
    if affordable < 20:
        warnings.append(f"only ~{affordable} trials fit the budget: fix more parameters, search on a sample of rows, "
                        "use fewer folds (3), or a smaller space; expect to find a decent region, not an optimum")
    if a.rows > 1_000_000:
        warnings.append("large data: search on a 10-20% sample with 3 folds, then refit the best config on all data")
    if trials > affordable and strategy == "grid":
        warnings.append(f"the grid ({trials}) is larger than the budget ({affordable}): switch to random/TPE")
    est_hours = trials * per_trial / 3600 / max(1, a.workers)
    pre = PREFIX[a.model]
    if a.format == "optuna":
        lines = []
        for name, kind, lo, hi, scale in space:
            if kind == "cat":
                lines.append(f'    {name} = trial.suggest_categorical("{name}", {lo!r})')
            elif kind == "int":
                lines.append(f'    {name} = trial.suggest_int("{name}", {lo}, {hi}' + (", log=True)" if scale == "log" else ")"))
            else:
                lines.append(f'    {name} = trial.suggest_float("{name}", {lo:g}, {hi:g}' + (", log=True)" if scale == "log" else ")"))
        code = "def objective(trial):\n" + "\n".join(lines) + "\n    ...  # build model, CV score, trial.report per fold for pruning"
    else:
        lines = []
        for name, kind, lo, hi, scale in space:
            if kind == "cat":
                lines.append(f'    "{pre}{name}": {lo!r},')
            elif kind == "int":
                lines.append(f'    "{pre}{name}": ' + (f"loguniform_int({lo}, {hi})," if scale == "log" else f"randint({lo}, {hi + 1}),"))
            else:
                lines.append(f'    "{pre}{name}": ' + (f"loguniform({lo:g}, {hi:g})," if scale == "log" else f"uniform({lo:g}, {hi - lo:g}),"))
        code = ("import numpy as np\n"
                "from scipy.stats import loguniform, randint, rv_discrete, uniform\n\n\n"
                "def loguniform_int(lo, hi):\n"
                "    \"\"\"Integers spread evenly on a log scale (scipy has no integer log-uniform).\"\"\"\n"
                "    values = np.unique(np.round(np.geomspace(lo, hi, 50)).astype(int))\n"
                "    return rv_discrete(values=(values, np.full(len(values), 1 / len(values))))\n\n\n"
                "param_distributions = {\n" + "\n".join(lines) + "\n}")
    out = {"model": a.model, "strategy": strategy, "trials": trials, "affordable_trials": affordable,
           "seconds_per_trial": per_trial, "estimated_hours": round(est_hours, 2), "fixed": FIXED[a.model],
           "space": [{"name": n, "kind": k, "low": lo, "high": hi, "scale": s} for n, k, lo, hi, s in space],
           "warnings": warnings, "code": code}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{a.model}: {a.rows:,} rows, {a.folds}-fold CV, {a.fit_seconds:g}s per fit -> {per_trial:g}s per trial; "
          f"~{affordable} trials affordable with {a.workers} worker(s)")
    print(f"\nSTRATEGY: {strategy}   trials: {trials}   (~{est_hours:.2f} h)")
    print(f"fix: {FIXED[a.model]}")
    print("space:")
    for n, k, lo, hi, s in space:
        rng_ = f"{lo}" if k == "cat" else f"[{lo:g}, {hi:g}] {s}"
        print(f"  {n:<20} {k:<6} {rng_}")
    for w in warnings:
        print(f"warning: {w}")
    print("\n" + code)
    print("\nAfter the search: python analyze_search.py cv_results.csv  (boundaries, sensitivity, 1-SE choice)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
