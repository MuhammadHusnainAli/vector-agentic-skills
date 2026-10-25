#!/usr/bin/env python3
"""Lint Python training code (scripts or notebook exports) for the classic leakage bugs.

Rules (AST-based, heuristic; line numbers point at the offending call):
  LK001 high    preprocessing fitted before the train/test split or CV (scaler, imputer, encoder, PCA,
                selector .fit / .fit_transform on the full data)
  LK002 high    resampling (SMOTE, ADASYN, Random*Sampler...) before the split or outside a pipeline
                that is cross-validated: synthetic copies of test rows end up in training
  LK003 high    feature selection fitted before the split / CV (SelectKBest, RFE, SelectFromModel...)
  LK004 high    the target column is left inside X (X = df, or df.drop(...) without the target)
  LK005 high    a model or transformer is fitted on test/validation data (.fit(X_test ...))
  LK006 high    target statistics computed in-sample: groupby(...)[target].transform("mean") / .mean()
  LK007 medium  random split or shuffled KFold in code that handles dates/timestamps (use time-ordered splits)
  LK008 medium  global statistics before the split: fillna(df[c].mean()), (x - x.mean()) / x.std() on full data
  LK009 medium  early stopping or model selection on the test set (eval_set=[(X_test, y_test)])
  LK010 low     cross_val_score / GridSearchCV given an estimator that is not a Pipeline while preprocessing
                objects exist in the file (preprocessing probably happened outside CV)

Usage:
    python code_leak_lint.py train.py
    python code_leak_lint.py notebooks/*.py --json
    cat train.py | python code_leak_lint.py -

Exit codes: 0 no high findings, 1 high findings, 2 read or syntax error.
"""

import argparse
import ast
import json
import re
import sys

PREPROC = {"StandardScaler", "MinMaxScaler", "RobustScaler", "MaxAbsScaler", "Normalizer", "PowerTransformer",
           "QuantileTransformer", "SimpleImputer", "KNNImputer", "IterativeImputer", "PCA", "TruncatedSVD",
           "OneHotEncoder", "OrdinalEncoder", "TargetEncoder", "KBinsDiscretizer", "TfidfVectorizer",
           "CountVectorizer", "PolynomialFeatures", "ColumnTransformer"}
SELECTORS = {"SelectKBest", "SelectPercentile", "RFE", "RFECV", "SelectFromModel", "SequentialFeatureSelector",
             "VarianceThreshold", "GenericUnivariateSelect", "BorutaPy"}
RESAMPLERS = {"SMOTE", "ADASYN", "BorderlineSMOTE", "SVMSMOTE", "SMOTENC", "SMOTETomek", "SMOTEENN",
              "RandomOverSampler", "RandomUnderSampler", "NearMiss", "TomekLinks", "ClusterCentroids"}
SPLITS = {"train_test_split", "KFold", "StratifiedKFold", "GroupKFold", "TimeSeriesSplit", "cross_val_score",
          "cross_validate", "cross_val_predict", "GridSearchCV", "RandomizedSearchCV", "ShuffleSplit",
          "StratifiedShuffleSplit", "GroupShuffleSplit", "RepeatedStratifiedKFold", "HalvingGridSearchCV"}
TESTISH = re.compile(r"(test|valid|val|holdout|hold_out)", re.I)
TRAINISH = re.compile(r"(train|tr\b|_tr$|fit)", re.I)
TIMEISH = re.compile(r"(date|time|_ts\b|timestamp|_at\b|month|week)", re.I)


def call_name(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def base_name(node):
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.value if not isinstance(node, ast.Call) else node.func
    return node.id if isinstance(node, ast.Name) else ""


def text_of(node):
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def lint(src, path):
    tree = ast.parse(src, filename=path)
    out = []

    def add(code, sev, node, msg):
        out.append({"file": path, "line": getattr(node, "lineno", 0), "code": code, "severity": sev, "message": msg})

    calls = sorted((n for n in ast.walk(tree) if isinstance(n, ast.Call)), key=lambda n: (n.lineno, n.col_offset))
    split_line = min((c.lineno for c in calls if call_name(c) in SPLITS), default=None)
    objs = {}          # variable -> constructor class name
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            cls = call_name(n.value)
            for t in n.targets:
                if isinstance(t, ast.Name):
                    objs[t.id] = cls
    pipeline_vars = {v for v, c in objs.items() if c in ("Pipeline", "make_pipeline", "ImbPipeline")}
    has_time = bool(TIMEISH.search(" ".join(n.value for n in ast.walk(tree)
                                           if isinstance(n, ast.Constant) and isinstance(n.value, str))))
    target_cols = {}   # df name -> target column
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            tgt, val = n.targets[0].id, n.value
            if re.fullmatch(r"y(_\w+)?|target|labels?", tgt) and isinstance(val, ast.Subscript) and \
                    isinstance(val.slice, ast.Constant) and isinstance(val.slice.value, str):
                target_cols[base_name(val.value)] = (val.slice.value, n.lineno)
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and \
                re.fullmatch(r"X(_\w+)?|features?", n.targets[0].id):
            val = n.value
            df = base_name(val)
            if df in target_cols:
                col, _ = target_cols[df]
                src_txt = text_of(val)
                if isinstance(val, ast.Name) or (f"'{col}'" not in src_txt and f'"{col}"' not in src_txt
                                                 and isinstance(val, ast.Call)):
                    add("LK004", "high", n, f"X built from {df} without removing the target column {col!r}")

    for c in calls:
        name = call_name(c)
        recv = c.func.value if isinstance(c.func, ast.Attribute) else None
        recv_name = base_name(recv) if recv is not None else ""
        recv_cls = objs.get(recv_name) or (call_name(recv) if isinstance(recv, ast.Call) else "")
        args_txt = " ".join(text_of(a) for a in c.args)
        before_split = split_line is not None and c.lineno < split_line
        if name in ("fit", "fit_transform", "fit_resample"):
            if c.args and TESTISH.search(text_of(c.args[0])) and not TRAINISH.search(text_of(c.args[0])):
                add("LK005", "high", c, f"{recv_name or recv_cls}.{name}() called on {text_of(c.args[0])}: never fit on "
                    "test or validation data")
            if name == "fit_resample" or recv_cls in RESAMPLERS:
                if before_split or not TRAINISH.search(args_txt):
                    add("LK002", "high", c, f"{recv_cls or 'resampler'}.{name}() before the split / on non-training "
                        "data: oversampled copies leak into the test folds; resample inside an imblearn Pipeline")
            elif recv_cls in SELECTORS and (before_split or not TRAINISH.search(args_txt)):
                add("LK003", "high", c, f"{recv_cls}.{name}() uses the target before the split/CV: selection must be "
                    "refitted inside each training fold (put it in the Pipeline)")
            elif recv_cls in PREPROC and before_split:
                add("LK001", "high", c, f"{recv_cls}.{name}() before the train/test split or CV: statistics of the "
                    "test rows leak into training; fit inside a Pipeline")
        if name in ("transform", "mean") and isinstance(c.func, ast.Attribute):
            chain = text_of(c)
            if "groupby" in chain and any(f"'{col}'" in chain or f'"{col}"' in chain
                                          for col, _ in target_cols.values()):
                if name == "mean" or "mean" in args_txt:
                    add("LK006", "high", c, "target mean per group computed on the same rows it encodes: use "
                        "out-of-fold target encoding (TargetEncoder) or only past rows")
        if name == "fillna" and before_split:
            if re.search(r"\.(mean|median|mode|std)\(", args_txt) and not TRAINISH.search(args_txt):
                add("LK008", "medium", c, "missing values filled with statistics of the full data before the split; "
                    "use SimpleImputer inside the Pipeline")
        if name in ("train_test_split", "KFold", "StratifiedKFold", "ShuffleSplit") and has_time:
            kw = {k.arg: k.value for k in c.keywords}
            shuffled = name in ("train_test_split", "ShuffleSplit") and not (
                isinstance(kw.get("shuffle"), ast.Constant) and kw["shuffle"].value is False)
            shuffled = shuffled or (isinstance(kw.get("shuffle"), ast.Constant) and kw["shuffle"].value is True)
            if shuffled:
                add("LK007", "medium", c, f"{name} shuffles rows in code that handles dates/times; if the model predicts "
                    "the future, use a time-ordered split (TimeSeriesSplit, cutoff date)")
        if any(k.arg == "eval_set" and TESTISH.search(text_of(k.value)) for k in c.keywords):
            add("LK009", "medium", c, "early stopping on the test set: the reported test score is optimistic; use a "
                "separate validation split")
        if name in ("cross_val_score", "cross_validate", "GridSearchCV", "RandomizedSearchCV") and c.args:
            est = c.args[0]
            est_name = base_name(est)
            est_cls = objs.get(est_name, call_name(est) if isinstance(est, ast.Call) else "")
            preproc_used = any(v in PREPROC | SELECTORS for v in objs.values())
            if preproc_used and est_name not in pipeline_vars and est_cls not in ("Pipeline", "make_pipeline"):
                add("LK010", "low", c, f"{name} on a bare estimator while preprocessing objects exist: if X was "
                    "preprocessed before, the CV score is optimistic; cross-validate a Pipeline")
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Sub, ast.Div)):
            t = text_of(n)
            if re.search(r"\.(mean|std)\(\)", t) and split_line and n.lineno < split_line and not TRAINISH.search(t):
                add("LK008", "medium", n, f"manual standardisation with full-data statistics before the split: {t[:60]}")
    uniq = {(f["line"], f["code"]): f for f in out}
    return sorted(uniq.values(), key=lambda f: (f["line"], f["code"]))


def main():
    ap = argparse.ArgumentParser(description="Lint ML training code for leakage bugs.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="Python files, or - for stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings = []
    for p in a.files:
        try:
            src = sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()
            findings += lint(src, "<stdin>" if p == "-" else p)
        except (OSError, SyntaxError) as e:
            print(f"error: {p}: {e}", file=sys.stderr)
            return 2
    high = sum(f["severity"] == "high" for f in findings)
    if a.json:
        print(json.dumps({"findings": findings, "high": high}, indent=2))
    else:
        for f in findings:
            print(f"{f['file']}:{f['line']}: {f['code']} [{f['severity']}] {f['message']}")
        print(f"\n{len(findings)} finding(s), {high} high" + ("" if findings else ": no leakage patterns found"))
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
