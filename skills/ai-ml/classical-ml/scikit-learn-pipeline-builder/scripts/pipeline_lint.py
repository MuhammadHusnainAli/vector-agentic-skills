#!/usr/bin/env python3
"""Lint scikit-learn code for API misuse that silently produces wrong numbers or breaks in production.

(For data leakage use target-leakage-detector/scripts/code_leak_lint.py.)

Rules:
  SK001 high    ranking/probability metric fed hard labels: roc_auc_score / average_precision_score /
                log_loss / brier_score_loss(..., model.predict(X))  -> use predict_proba(X)[:, 1]
  SK002 high    removed or renamed parameters that raise in current scikit-learn: OneHotEncoder(sparse=),
                LogisticRegression(penalty="none"), normalize= in linear models, base_estimator=,
                max_features="auto", criterion="mse"/"mae", loss="deviance"/"ls"/"log", affinity=,
                mean_squared_error(squared=False), fit_params= in cross_val_score, algorithm="SAMME.R"
  SK003 medium  LabelEncoder used on feature columns (it is for targets; use OrdinalEncoder/OneHotEncoder)
  SK004 medium  pd.get_dummies in training code: columns differ between train and inference
  SK005 medium  FunctionTransformer(lambda ...): lambdas cannot be pickled with the model
  SK006 medium  model scored on the same data it was fitted on (.fit(X, y) then .score(X, y) / metric on
                predict(X)) - reports training performance
  SK007 low     stochastic estimator / splitter / search without random_state
  SK008 low     n_jobs=-1 on both a search and its estimator (nested parallelism oversubscribes cores)
  SK009 low     LogisticRegression without max_iter on unscaled data risks ConvergenceWarning
  SK010 info    ColumnTransformer without remainder=: unlisted columns are dropped silently

Usage:
    python pipeline_lint.py train.py
    python pipeline_lint.py src/*.py --json

Exit codes: 0 no high findings, 1 high findings, 2 read or syntax error.
"""

import argparse
import ast
import json
import sys

PROB_METRICS = {"roc_auc_score", "average_precision_score", "log_loss", "brier_score_loss"}
LABEL_METRICS = {"accuracy_score", "f1_score", "precision_score", "recall_score", "r2_score",
                 "mean_absolute_error", "mean_squared_error", "balanced_accuracy_score"}
STOCHASTIC = {"RandomForestClassifier", "RandomForestRegressor", "ExtraTreesClassifier", "ExtraTreesRegressor",
              "GradientBoostingClassifier", "GradientBoostingRegressor", "HistGradientBoostingClassifier",
              "HistGradientBoostingRegressor", "KMeans", "MiniBatchKMeans", "IsolationForest", "SGDClassifier",
              "SGDRegressor", "MLPClassifier", "MLPRegressor", "train_test_split", "RandomizedSearchCV",
              "HalvingRandomSearchCV", "TSNE", "BaggingClassifier", "BaggingRegressor", "XGBClassifier",
              "XGBRegressor", "LGBMClassifier", "LGBMRegressor", "CatBoostClassifier", "CatBoostRegressor"}
STOCH_KW = {"LGBMClassifier": "random_state", "LGBMRegressor": "random_state", "CatBoostClassifier": "random_seed",
            "CatBoostRegressor": "random_seed"}
SEARCHES = {"GridSearchCV", "RandomizedSearchCV", "HalvingGridSearchCV", "HalvingRandomSearchCV"}
LINEAR = {"LinearRegression", "Ridge", "Lasso", "ElasticNet", "Lars", "LassoLars", "OrthogonalMatchingPursuit"}


def name(node):
    f = node.func if isinstance(node, ast.Call) else node
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def src(node):
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def kw(call, key):
    for k in call.keywords:
        if k.arg == key:
            return k.value
    return None


def const(v):
    if isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.USub) and isinstance(v.operand, ast.Constant):
        return -v.operand.value                      # -1 parses as USub(1)
    return v.value if isinstance(v, ast.Constant) else None


def lint(code, path):
    tree = ast.parse(code, filename=path)
    out = []

    def add(rule, sev, node, msg):
        out.append({"file": path, "line": node.lineno, "code": rule, "severity": sev, "message": msg})

    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
    fitted = {}   # data arg text -> line of .fit
    for c in calls:
        n = name(c)
        # SK001
        if n in PROB_METRICS and len(c.args) >= 2:
            a2 = c.args[1]
            if isinstance(a2, ast.Call) and name(a2) == "predict":
                add("SK001", "high", c, f"{n}() given hard labels from .predict(); use .predict_proba(X)[:, 1] "
                    "(or decision_function) - the number is wrong, not just worse")
        # SK002
        if n == "OneHotEncoder" and kw(c, "sparse") is not None:
            add("SK002", "high", c, "OneHotEncoder(sparse=) was removed in 1.4; use sparse_output=")
        if n == "LogisticRegression" and const(kw(c, "penalty")) == "none":
            add("SK002", "high", c, 'penalty="none" was removed; use penalty=None')
        if n in LINEAR and kw(c, "normalize") is not None:
            add("SK002", "high", c, "normalize= was removed (1.2); put StandardScaler in a Pipeline")
        if kw(c, "base_estimator") is not None:
            add("SK002", "high", c, "base_estimator= was renamed to estimator= (removed in 1.4)")
        if const(kw(c, "max_features")) == "auto":
            add("SK002", "high", c, 'max_features="auto" was removed (1.3); use "sqrt" (classifier) or 1.0 (regressor)')
        if const(kw(c, "criterion")) in ("mse", "mae"):
            add("SK002", "high", c, 'criterion="mse"/"mae" were removed; use "squared_error"/"absolute_error"')
        if const(kw(c, "loss")) in ("deviance", "ls", "lad") or (n.startswith("SGD") and const(kw(c, "loss")) == "log"):
            add("SK002", "high", c, f'loss="{const(kw(c, "loss"))}" was removed; use "log_loss", "squared_error" '
                'or "absolute_error"')
        if kw(c, "affinity") is not None and n in ("AgglomerativeClustering", "FeatureAgglomeration"):
            add("SK002", "high", c, "affinity= was removed (1.4); use metric=")
        if n == "mean_squared_error" and kw(c, "squared") is not None:
            add("SK002", "high", c, "squared= was removed (1.6); use root_mean_squared_error()")
        if n in ("cross_val_score", "cross_validate", "cross_val_predict") and kw(c, "fit_params") is not None:
            add("SK002", "high", c, "fit_params= was removed (1.6); use params=")
        if const(kw(c, "algorithm")) == "SAMME.R":
            add("SK002", "high", c, 'AdaBoost algorithm="SAMME.R" is gone (deprecated 1.4; the algorithm parameter itself was later removed): drop it')
        # SK003
        if n in ("fit_transform", "fit") and isinstance(c.func, ast.Attribute):
            recv = c.func.value
            if (isinstance(recv, ast.Call) and name(recv) == "LabelEncoder") and c.args and \
                    not src(c.args[0]).lower().startswith(("y", "target", "label")):
                add("SK003", "medium", c, "LabelEncoder on a feature: it is meant for targets and cannot handle unseen "
                    "values; use OrdinalEncoder(handle_unknown=...) or OneHotEncoder inside the Pipeline")
        # SK004
        if n == "get_dummies":
            add("SK004", "medium", c, "pd.get_dummies: train and inference columns diverge when levels differ; use "
                "OneHotEncoder(handle_unknown='ignore') in the Pipeline")
        # SK005
        if n == "FunctionTransformer" and c.args and isinstance(c.args[0], ast.Lambda) or (
                n == "FunctionTransformer" and isinstance(kw(c, "func"), ast.Lambda)):
            add("SK005", "medium", c, "FunctionTransformer(lambda ...) cannot be pickled with joblib/pickle; use a "
                "named module-level function")
        # SK006
        if n == "fit" and len(c.args) >= 1:
            fitted.setdefault(src(c.args[0]), c.lineno)
        if n == "score" and c.args and src(c.args[0]) in fitted and "train" not in src(c.args[0]).lower():
            add("SK006", "medium", c, f".score({src(c.args[0])}, ...) on the data the model was fitted on: this is "
                "training performance; score a held-out split or use cross-validation")
        if n in (PROB_METRICS | LABEL_METRICS) and len(c.args) >= 2:
            pred = c.args[1]
            if isinstance(pred, ast.Call) and name(pred) in ("predict", "predict_proba") and pred.args and \
                    src(pred.args[0]) in fitted and "train" not in src(pred.args[0]).lower():
                add("SK006", "medium", c, f"{n}() computed on predictions for {src(pred.args[0])}, the data the model "
                    "was fitted on")
        # SK007
        if n in STOCHASTIC:
            key = STOCH_KW.get(n, "random_state")
            if kw(c, key) is None and not (n.startswith("XGB") and kw(c, "seed") is not None):
                add("SK007", "low", c, f"{n} without {key}=: results change on every run")
        if n in ("KFold", "StratifiedKFold") and const(kw(c, "shuffle")) is True and kw(c, "random_state") is None:
            add("SK007", "low", c, f"{n}(shuffle=True) without random_state: folds change on every run")
        # SK008
        if n in SEARCHES and const(kw(c, "n_jobs")) == -1 and c.args:
            est = c.args[0]
            if isinstance(est, ast.Call) and const(kw(est, "n_jobs")) == -1:
                add("SK008", "low", c, "n_jobs=-1 on the search and its estimator: nested parallelism oversubscribes; "
                    "parallelise one level")
        # SK009
        if n == "LogisticRegression" and kw(c, "max_iter") is None:
            add("SK009", "low", c, "LogisticRegression without max_iter (default 100): scale features and/or raise "
                "max_iter to avoid ConvergenceWarning and an under-fitted model")
        # SK010
        if n == "ColumnTransformer" and kw(c, "remainder") is None:
            add("SK010", "info", c, "ColumnTransformer drops unlisted columns by default; set remainder= explicitly")
    uniq = {(f["line"], f["code"]): f for f in out}
    return sorted(uniq.values(), key=lambda f: (f["line"], f["code"]))


def main():
    ap = argparse.ArgumentParser(description="Lint scikit-learn code for API misuse.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings = []
    for p in a.files:
        try:
            code = sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()
            findings += lint(code, "<stdin>" if p == "-" else p)
        except (OSError, SyntaxError) as e:
            print(f"error: {p}: {e}", file=sys.stderr)
            return 2
    high = sum(f["severity"] == "high" for f in findings)
    if a.json:
        print(json.dumps({"findings": findings, "high": high}, indent=2))
    else:
        for f in findings:
            print(f"{f['file']}:{f['line']}: {f['code']} [{f['severity']}] {f['message']}")
        print(f"\n{len(findings)} finding(s), {high} high" + ("" if findings else ": no scikit-learn API issues found"))
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
