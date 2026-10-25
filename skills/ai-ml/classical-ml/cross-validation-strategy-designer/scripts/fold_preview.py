#!/usr/bin/env python3
"""Build (or audit existing) cross-validation folds and check them before any model is trained.

Either generate folds with --strategy kfold | stratified | group | stratified-group | time, or audit a
column of existing fold ids with --fold-col. For every fold it reports the train/test sizes, the target
rate (classification) or mean (regression) in the test fold, and three leakage checks:
  group overlap   number of --group-col values present in both train and test (must be 0 for grouped CV)
  time order      latest training time vs earliest test time (forward folds need train_max < test_min,
                  and a gap of at least --label-window days when labels look ahead)
  coverage        classes missing from a test fold, very small test folds, unequal fold sizes
Generated folds follow scikit-learn's logic (shuffled stratification, greedy group balancing,
forward-chaining blocks with a gap), so the preview predicts what scikit-learn will do.

Usage:
    python fold_preview.py data.csv --target churned --strategy stratified --folds 5
    python fold_preview.py txns.csv --target is_fraud --strategy stratified-group --group-col card_id
    python fold_preview.py snaps.csv --target churned --strategy time --time-col score_date --label-window 30
    python fold_preview.py data.csv --target y --fold-col fold --group-col customer_id --time-col ts

Exit codes: 0 folds look sound, 1 a leakage or coverage problem was found, 2 usage error.
"""

import argparse
import csv
import datetime as dt
import json
import math
import random
import sys
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def parse_time(v):
    v = (v or "").strip()
    try:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return dt.datetime.fromtimestamp(float(v))
        except (ValueError, OverflowError, OSError):
            return None


def make_folds(rows, a, y_cls):
    n = len(rows)
    rng = random.Random(a.seed)
    k = a.folds
    fold = [0] * n
    if a.strategy == "kfold":
        idx = list(range(n))
        rng.shuffle(idx)
        for pos, i in enumerate(idx):
            fold[i] = pos * k // n
    elif a.strategy == "stratified":
        by = defaultdict(list)
        for i, c in enumerate(y_cls):
            by[c].append(i)
        for c, idx in by.items():
            rng.shuffle(idx)
            for pos, i in enumerate(idx):
                fold[i] = pos % k
    elif a.strategy in ("group", "stratified-group"):
        members = defaultdict(list)
        for i, r in enumerate(rows):
            members[r[a.group_col]].append(i)
        groups = list(members)
        rng.shuffle(groups)
        if a.strategy == "group":
            groups.sort(key=lambda g: -len(members[g]))            # greedy: largest group to the smallest fold
            sizes = [0] * k
            for g in groups:
                f = min(range(k), key=lambda j: sizes[j])
                for i in members[g]:
                    fold[i] = f
                sizes[f] += len(members[g])
        else:
            classes = sorted(set(y_cls))
            target = Counter(y_cls)
            counts = [Counter() for _ in range(k)]
            groups.sort(key=lambda g: -max(Counter(y_cls[i] for i in members[g]).values()))
            for g in groups:
                gc = Counter(y_cls[i] for i in members[g])
                def cost(j):
                    trial = [counts[j][c] + gc[c] if jj == j else counts[jj][c] for jj in range(k) for c in classes]
                    devs = []
                    for c_i, c in enumerate(classes):
                        per = [trial[jj * len(classes) + c_i] / target[c] for jj in range(k)]
                        m = sum(per) / k
                        devs.append(math.sqrt(sum((p - m) ** 2 for p in per) / k))
                    return sum(devs) / len(devs), sum(counts[j].values())
                f = min(range(k), key=cost)
                counts[f].update(gc)
                for i in members[g]:
                    fold[i] = f
    return fold


def main():
    ap = argparse.ArgumentParser(description="Preview or audit CV folds for leakage and balance.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--strategy", choices=["kfold", "stratified", "group", "stratified-group", "time"])
    ap.add_argument("--fold-col", help="audit this existing fold-id column instead of generating folds")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--group-col")
    ap.add_argument("--time-col")
    ap.add_argument("--label-window", type=float, default=0, help="days of label look-ahead (time folds)")
    ap.add_argument("--gap", type=int, default=0, help="rows dropped between train and test (time strategy)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not (a.strategy or a.fold_col):
        print("error: give --strategy or --fold-col", file=sys.stderr)
        return 2
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rd = csv.DictReader(fh)
            header = rd.fieldnames or []
            rows = [r for r in rd if (r.get(a.target) or "").strip().lower() not in MISSING]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for c in (a.target, a.fold_col, a.group_col, a.time_col):
        if c and c not in header:
            print(f"error: column {c!r} not found", file=sys.stderr)
            return 2
    if a.strategy in ("group", "stratified-group") and not a.group_col:
        print("error: group strategies need --group-col", file=sys.stderr)
        return 2
    if a.strategy == "time" and not a.time_col:
        print("error: --strategy time needs --time-col", file=sys.stderr)
        return 2
    yv = [r[a.target].strip() for r in rows]
    classes = Counter(yv)
    classification = len(classes) <= 20
    times = [parse_time(r[a.time_col]) for r in rows] if a.time_col else None
    n = len(rows)
    splits = []           # list of (train_idx, test_idx)
    if a.fold_col:
        ids = sorted({r[a.fold_col] for r in rows}, key=lambda v: (len(v), v))
        for f in ids:
            te = [i for i, r in enumerate(rows) if r[a.fold_col] == f]
            tr = [i for i, r in enumerate(rows) if r[a.fold_col] != f]
            if times:
                tr = [i for i in tr if times[i] and times[i] < min(times[j] for j in te if times[j])] \
                    if a.strategy == "time" else tr
            splits.append((tr, te))
    elif a.strategy == "time":
        order = sorted(range(n), key=lambda i: times[i] or dt.datetime.min)
        test_size = n // (a.folds + 1)
        for f in range(a.folds):
            te_start = n - (a.folds - f) * test_size
            te = order[te_start:te_start + test_size]
            tr = order[:max(0, te_start - a.gap)]
            splits.append((tr, te))
    else:
        fold = make_folds(rows, a, yv)
        for f in range(a.folds):
            splits.append(([i for i in range(n) if fold[i] != f], [i for i in range(n) if fold[i] == f]))
    problems, report = [], []
    for f, (tr, te) in enumerate(splits):
        e = {"fold": f, "train": len(tr), "test": len(te)}
        if classification:
            tc = Counter(yv[i] for i in te)
            minority = min(classes, key=classes.get)
            e["test_minority_rate"] = tc.get(minority, 0) / max(1, len(te))
            miss = [c for c in classes if tc.get(c, 0) == 0]
            if miss:
                problems.append(f"fold {f}: classes {miss} absent from the test fold")
        else:
            vals = [float(yv[i]) for i in te]
            e["test_target_mean"] = sum(vals) / max(1, len(vals))
        if a.group_col:
            gtr = {rows[i][a.group_col] for i in tr}
            overlap = sum(1 for g in {rows[i][a.group_col] for i in te} if g in gtr)
            e["group_overlap"] = overlap
            if overlap and a.strategy in ("group", "stratified-group", None):
                problems.append(f"fold {f}: {overlap} {a.group_col} value(s) in both train and test")
            elif overlap and a.strategy in ("kfold", "stratified"):
                problems.append(f"fold {f}: {overlap} {a.group_col} value(s) shared between train and test "
                                "(random folds with repeated entities)")
        if times and tr and te:
            tmax = max(times[i] for i in tr if times[i])
            tmin = min(times[i] for i in te if times[i])
            gap_days = (tmin - tmax).total_seconds() / 86400
            e["train_max"], e["test_min"], e["gap_days"] = str(tmax), str(tmin), round(gap_days, 2)
            if a.strategy == "time" or a.fold_col:
                if gap_days < 0:
                    problems.append(f"fold {f}: training data ends after the test fold starts ({gap_days:.1f} days)")
                elif gap_days < a.label_window:
                    problems.append(f"fold {f}: gap {gap_days:.1f} days < label window {a.label_window:g}: training "
                                    "labels overlap the test period")
        if len(te) < 0.5 * n / max(1, len(splits)) and a.strategy != "time":
            problems.append(f"fold {f}: test fold has only {len(te)} rows")
        report.append(e)
    out = {"rows": n, "strategy": a.strategy or f"existing column {a.fold_col}", "folds": report, "problems": problems}
    if a.json:
        print(json.dumps(out, indent=2))
        return 1 if problems else 0
    print(f"{n} rows, {out['strategy']}, {len(splits)} folds")
    for e in report:
        bits = [f"train {e['train']:>6}", f"test {e['test']:>5}"]
        if "test_minority_rate" in e:
            bits.append(f"minority {e['test_minority_rate']:.3f}")
        if "test_target_mean" in e:
            bits.append(f"mean {e['test_target_mean']:.4g}")
        if "group_overlap" in e:
            bits.append(f"group overlap {e['group_overlap']}")
        if "gap_days" in e:
            bits.append(f"train<= {e['train_max'][:10]} test>= {e['test_min'][:10]} gap {e['gap_days']:g} d")
        print(f"  fold {e['fold']}: " + "  ".join(bits))
    for p in problems:
        print(f"PROBLEM: {p}")
    if not problems:
        print("folds look sound: no group overlap, correct time order, every class present")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
