#!/usr/bin/env python3
"""Recommend a cross-validation scheme from the data itself, with the scikit-learn code.

It inspects the CSV for the three things that decide a CV design:
  repeated entities   columns whose values repeat across rows (customer_id, patient, store) -> grouped folds
                      (--group-col, or auto-detected ID-like columns with many repeats)
  time order          a datetime column (--time-col or auto-detected) -> forward-chaining folds,
                      with a gap of --label-window rows/days when labels look ahead
  target              binary / multiclass / numeric, imbalance and minority count -> stratification,
                      number of folds and repeats
and the deployment question (--deploy forward|new-entities|same-entities|iid) when given.

Output: the recommended splitter, folds/repeats, gap, nested-CV advice when tuning, a warning list
(e.g. "random K-fold on data with repeated customers"), and copy-paste code.

Usage:
    python cv_advisor.py data.csv --target churned
    python cv_advisor.py snapshots.csv --target churned --group-col customer_id --time-col score_date --label-window 30
    python cv_advisor.py data.csv --target price --deploy iid --tuning --json

Exit codes: 0 printed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}
DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def is_num(v):
    try:
        return math.isfinite(float(v))
    except ValueError:
        return False


def detect(header, rows, target):
    groups, times = [], []
    n = len(rows)
    for c in header:
        if c == target:
            continue
        vals = [(r[c] or "").strip() for r in rows if (r[c] or "").strip().lower() not in MISSING]
        if not vals:
            continue
        if sum(bool(DATE_RE.match(v)) for v in vals) / len(vals) > 0.9:
            times.append(c)
            continue
        k = len(set(vals))
        if re.search(r"(_id$|^id_|^id$|user|customer|patient|account|store|device|session|card|subject)", c, re.I) \
                and 1 < k < 0.8 * n:
            groups.append((c, n / k))
    return sorted(groups, key=lambda g: -g[1]), times


def main():
    ap = argparse.ArgumentParser(description="Recommend a CV scheme and emit scikit-learn code.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--group-col")
    ap.add_argument("--time-col")
    ap.add_argument("--label-window", type=int, default=0, help="label look-ahead in rows (gap between train and test)")
    ap.add_argument("--deploy", choices=["auto", "forward", "new-entities", "same-entities", "iid"], default="auto")
    ap.add_argument("--tuning", action="store_true", help="hyperparameters will be tuned (nested CV advice)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rd = csv.DictReader(fh)
            header = rd.fieldnames or []
            rows = list(rd)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for c in (a.target, a.group_col, a.time_col):
        if c and c not in header:
            print(f"error: column {c!r} not found", file=sys.stderr)
            return 2
    n = len(rows)
    groups, times = detect(header, rows, a.target)
    group = a.group_col or (groups[0][0] if groups and groups[0][1] >= 1.5 else None)
    tcol = a.time_col or (times[0] if times else None)
    tv = [(r[a.target] or "").strip() for r in rows if (r[a.target] or "").strip()]
    cnt = Counter(tv)
    classification = len(cnt) <= 20 or not all(is_num(v) for v in tv)
    minority = min(cnt.values()) if classification else None
    deploy = a.deploy
    if deploy == "auto":
        deploy = "forward" if a.time_col else ("new-entities" if group else "iid")
    warnings = []
    if group and deploy not in ("new-entities", "same-entities", "forward"):
        warnings.append(f"{group} repeats ({n / len(set(r[group] for r in rows)):.1f} rows per value): random K-fold "
                        "would put the same entity in train and test and inflate scores")
    if tcol and deploy != "forward":
        warnings.append(f"{tcol} looks like a time column: if the model predicts later periods, use forward-chaining "
                        f"folds (--time-col {tcol} or --deploy forward); random or grouped folds mix past and future")
    if deploy == "forward" and not tcol:
        warnings.append("forward deployment but no time column found: give --time-col")
    if classification and minority is not None and minority < 50:
        warnings.append(f"only {minority} rows in the smallest class: use fewer folds, repeats and report intervals")
    # choose
    folds = 5
    repeats = 1
    if n < 1000:
        repeats = 5 if deploy != "forward" else 1
        folds = 5 if (minority or 100) >= 25 else 3
    elif n > 1_000_000:
        folds = 3
    if deploy == "forward":
        splitter = f"TimeSeriesSplit(n_splits={folds}, gap={a.label_window})"
        why = "the model predicts later periods: train on the past, test on the next block"
        code = (f"df = df.sort_values({tcol!r}).reset_index(drop=True)\n"
                f"cv = TimeSeriesSplit(n_splits={folds}, gap={a.label_window})   # gap = label window in rows\n"
                "for tr, te in cv.split(df):\n    ...")
        if group:
            why += f"; {group} also repeats: entities appear across time, which matches deployment (same entities, later "  \
                   "time) - if new entities must be predicted, also exclude test entities from training"
        if a.label_window == 0:
            warnings.append("labels with a look-ahead window (e.g. churn in 30 days) need gap >= window, otherwise the "
                            "last training rows' labels overlap the test period")
    elif deploy == "new-entities":
        if classification:
            splitter = f"StratifiedGroupKFold(n_splits={folds}, shuffle=True, random_state=0)"
        else:
            splitter = f"GroupKFold(n_splits={folds})"
        why = f"production scores entities never seen in training: every {group} is in one fold only"
        code = f"cv = {splitter}\nscores = cross_val_score(pipe, X, y, cv=cv, groups=df[{group!r}])"
    else:
        if classification:
            splitter = (f"RepeatedStratifiedKFold(n_splits={folds}, n_repeats={repeats}, random_state=0)" if repeats > 1
                        else f"StratifiedKFold(n_splits={folds}, shuffle=True, random_state=0)")
            why = "i.i.d. rows: stratify so every fold keeps the class balance"
        else:
            splitter = (f"RepeatedKFold(n_splits={folds}, n_repeats={repeats}, random_state=0)" if repeats > 1
                        else f"KFold(n_splits={folds}, shuffle=True, random_state=0)")
            why = "i.i.d. rows, numeric target"
        if deploy == "same-entities" and group:
            why += f"; {group} repeats but production scores the same entities again, so mixing is acceptable"
        code = f"cv = {splitter}\nscores = cross_val_score(pipe, X, y, cv=cv)"
    nested = None
    if a.tuning:
        nested = ("tune inside each outer training fold: cross_validate(GridSearchCV(pipe, grid, cv=inner), X, y, cv=outer); "
                  "inner and outer splitters must respect the same groups / time order")
    out = {"rows": n, "target_kind": "classification" if classification else "regression", "minority_count": minority,
           "detected_groups": [g for g, _ in groups], "detected_time_columns": times, "group_col": group,
           "time_col": tcol, "deploy": deploy, "splitter": splitter, "folds": folds, "repeats": repeats,
           "why": why, "nested": nested, "warnings": warnings, "code": code}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{n} rows, {out['target_kind']} target" + (f" (smallest class {minority})" if minority else "") +
          f"; repeated-entity columns: {', '.join(g for g, _ in groups) or 'none'}; time columns: {', '.join(times) or 'none'}")
    print(f"deployment assumed: {deploy}")
    print(f"\nRECOMMENDED: {splitter}\n  why: {why}")
    if nested:
        print(f"  tuning: {nested}")
    for w in warnings:
        print(f"warning: {w}")
    print("\ncode:\nfrom sklearn.model_selection import (GroupKFold, KFold, RepeatedKFold, RepeatedStratifiedKFold,\n"
          "    StratifiedGroupKFold, StratifiedKFold, TimeSeriesSplit, cross_val_score)\n" + code)
    print("\nCheck the folds before trusting scores: python fold_preview.py ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
