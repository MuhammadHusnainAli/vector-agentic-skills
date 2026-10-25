#!/usr/bin/env python3
"""Check a CatBoost parameter set (JSON) for conflicts and risky choices before a long training run.

Rules (errors were confirmed to raise CatBoostError in CatBoost 1.2):
  CB001 error    more than one of iterations / n_estimators / num_boost_round / num_trees
  CB002 error    both learning_rate and eta
  CB003 error    more than one of scale_pos_weight / class_weights / auto_class_weights
  CB004 error    bootstrap_type="Bayesian" with subsample; bagging_temperature without Bayesian bootstrap
  CB005 error    depth > 16
  CB006 error    use_best_model=True without an eval set (pass --has-eval-set when you will provide one)
  CB007 warning  max_leaves set but grow_policy is not "Lossguide" (silently ignored)
  CB008 warning  no overfitting detector (od_type / early_stopping_rounds) with many iterations
  CB009 warning  loss_function / eval_metric do not match the task (--task)
  CB010 warning  depth >= 10 (symmetric trees: 2^depth leaves; slow, overfits)
  CB011 warning  learning_rate >= 0.3 with >= 1000 iterations, or <= 0.005 (very slow)
  CB012 info     task_type="GPU" with rsm (feature subsampling) on non-pairwise losses is unsupported on GPU
  CB013 info     one_hot_max_size > 255 or large: one-hot for many levels loses CatBoost's CTR advantage
  CB014 warning  l2_leaf_reg <= 0

Usage:
    python catboost_params_check.py params.json --task binary
    python catboost_params_check.py params.json --task regression --has-eval-set --json
    echo '{"iterations": 5000, "n_estimators": 100}' | python catboost_params_check.py -

Exit codes: 0 no errors, 1 errors, 2 read error.
"""

import argparse
import json
import sys

TASK_LOSSES = {
    "binary": {"Logloss", "CrossEntropy", "Focal"},
    "multiclass": {"MultiClass", "MultiClassOneVsAll"},
    "regression": {"RMSE", "MAE", "Quantile", "Expectile", "Huber", "Poisson", "Tweedie", "MAPE", "LogLinQuantile",
                   "Lq", "RMSEWithUncertainty", "LogCosh", "Cox", "SurvivalAft"},
    "ranking": {"YetiRank", "YetiRankPairwise", "PairLogit", "PairLogitPairwise", "QueryRMSE", "QuerySoftMax",
                "LambdaMart", "StochasticRank"},
}
TASK_METRICS = {
    "binary": {"AUC", "PRAUC", "Logloss", "CrossEntropy", "F1", "Precision", "Recall", "Accuracy", "BalancedAccuracy",
               "MCC", "BrierScore", "Kappa", "NormalizedGini"},
    "multiclass": {"MultiClass", "Accuracy", "TotalF1", "AUC", "MCC", "Kappa", "WKappa", "HammingLoss"},
    "regression": {"RMSE", "MAE", "R2", "MAPE", "SMAPE", "Quantile", "Poisson", "Tweedie", "Huber", "MSLE", "MedianAbsoluteError",
                   "Expectile", "LogCosh"},
    "ranking": {"NDCG", "PFound", "MAP", "MRR", "ERR", "QueryRMSE", "PrecisionAt", "RecallAt", "AUC"},
}


def base(name):
    return str(name).split(":")[0] if name is not None else None


def check(p, task, has_eval):
    out = []

    def add(code, sev, msg):
        out.append({"code": code, "severity": sev, "message": msg})

    iters = [k for k in ("iterations", "n_estimators", "num_boost_round", "num_trees") if k in p]
    if len(iters) > 1:
        add("CB001", "error", f"only one of {iters} may be set")
    if "learning_rate" in p and "eta" in p:
        add("CB002", "error", "set learning_rate or eta, not both")
    w = [k for k in ("scale_pos_weight", "class_weights", "auto_class_weights") if k in p]
    if len(w) > 1:
        add("CB003", "error", f"only one of {w} may be set")
    bt = p.get("bootstrap_type")
    if bt == "Bayesian" and "subsample" in p:
        add("CB004", "error", "Bayesian bootstrap does not support subsample (use bagging_temperature)")
    if "bagging_temperature" in p and bt not in (None, "Bayesian"):
        add("CB004", "error", f"bagging_temperature needs bootstrap_type='Bayesian' (got {bt!r})")
    depth = p.get("depth", p.get("max_depth"))
    if isinstance(depth, (int, float)):
        if depth > 16:
            add("CB005", "error", f"depth {depth} > 16 (CatBoost maximum)")
        elif depth >= 10:
            add("CB010", "warning", f"depth {depth}: symmetric trees have 2^depth leaves; try 4-8 first")
    if p.get("use_best_model") and not has_eval:
        add("CB006", "error", "use_best_model=True requires eval_set in fit() (or pass --has-eval-set)")
    if "max_leaves" in p and p.get("grow_policy") != "Lossguide":
        add("CB007", "warning", "max_leaves only applies with grow_policy='Lossguide'; it is ignored otherwise")
    n_it = next((p[k] for k in iters), 1000) if iters else 1000
    if not any(k in p for k in ("od_type", "od_wait", "early_stopping_rounds")) and n_it >= 500:
        add("CB008", "warning", f"{n_it} iterations without an overfitting detector: add od_type='Iter', od_wait=200 "
            "(or early_stopping_rounds) with an eval_set")
    loss, metric = base(p.get("loss_function")), base(p.get("eval_metric"))
    if task:
        if loss and loss not in TASK_LOSSES[task]:
            add("CB009", "warning", f"loss_function {p['loss_function']!r} is unusual for a {task} task "
                f"(expected one of {sorted(TASK_LOSSES[task])[:6]}...)")
        if metric and metric not in TASK_METRICS[task]:
            add("CB009", "warning", f"eval_metric {p['eval_metric']!r} is unusual for a {task} task")
    lr = p.get("learning_rate", p.get("eta"))
    if isinstance(lr, (int, float)):
        if lr >= 0.3 and n_it >= 1000:
            add("CB011", "warning", f"learning_rate {lr} with {n_it} iterations: expect early overfitting; use 0.03-0.1")
        if lr <= 0.005:
            add("CB011", "warning", f"learning_rate {lr} is very low: training will need many thousands of iterations")
    if p.get("task_type") == "GPU" and "rsm" in p and loss not in ("PairLogitPairwise", "YetiRankPairwise"):
        add("CB012", "info", "rsm (feature subsampling) on GPU is only supported for pairwise losses")
    ohs = p.get("one_hot_max_size")
    if isinstance(ohs, int) and ohs > 255:
        add("CB013", "info", f"one_hot_max_size {ohs}: one-hot encoding many levels gives up CatBoost's ordered CTRs")
    l2 = p.get("l2_leaf_reg")
    if isinstance(l2, (int, float)) and l2 <= 0:
        add("CB014", "warning", "l2_leaf_reg <= 0 removes leaf regularisation; typical range 1-10")
    return out


def main():
    ap = argparse.ArgumentParser(description="Check CatBoost parameters for conflicts.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("params", help="JSON object of CatBoost parameters, or - for stdin")
    ap.add_argument("--task", choices=["binary", "multiclass", "regression", "ranking"])
    ap.add_argument("--has-eval-set", action="store_true", help="you will pass eval_set to fit()")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        p = json.loads(sys.stdin.read() if a.params == "-" else open(a.params, encoding="utf-8").read())
        if not isinstance(p, dict):
            raise ValueError("parameters must be a JSON object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = check(p, a.task, a.has_eval_set)
    errors = sum(f["severity"] == "error" for f in findings)
    if a.json:
        print(json.dumps({"errors": errors, "findings": findings}, indent=2))
    else:
        for f in findings:
            print(f"{f['code']} [{f['severity']}] {f['message']}")
        print(f"\n{len(findings)} finding(s), {errors} error(s)" + ("" if findings else ": parameters look consistent"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
