#!/usr/bin/env python3
"""Score the baselines every model must beat, on a holdout, with no ML libraries.

Classification (binary target):
  majority      always predict the most frequent class (accuracy floor, AUC 0.5)
  prior         predict the training positive rate as the probability (log loss / Brier floor)
  one_r         best single feature, chosen on an inner split of the training rows: smoothed
                positive rate per level (categorical) or per 10 quantile bins (numeric)
  rule          your current business rule, e.g. --rule "support_calls >= 3 or plan == basic"
Regression (numeric target):
  mean, median  constant predictions
  one_r         best single feature: mean target per level or per 10 quantile bins
  rule          not used for regression

Split: last --test-frac of rows by --time-col (time-ordered holdout, the honest default for
anything deployed forward in time), or a seeded random split without --time-col.

Usage:
    python baseline_scores.py data.csv --target churned --time-col signup_date --drop customer_id
    python baseline_scores.py data.csv --target churned --rule "support_calls >= 3 or last_login_days > 30"
    python baseline_scores.py data.csv --target price --drop house_id --json

Exit codes: 0 scored, 2 usage/read error or unusable target.
"""

import argparse
import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}
RULE_TERM = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*(>=|<=|==|!=|>|<)\s*(.+?)\s*$")


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def missing(v):
    return v is None or v.strip().lower() in MISSING


# ---------------------------------------------------------------- metrics
def roc_auc(s, y):
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


def avg_precision(s, y):
    """Average precision with tied scores treated as one threshold (a constant score gives the prevalence)."""
    pos = sum(y)
    if not pos:
        return float("nan")
    by_score = defaultdict(lambda: [0, 0])
    for v, t in zip(s, y):
        by_score[v][0] += t
        by_score[v][1] += 1
    tp = seen = 0
    total = 0.0
    for v in sorted(by_score, reverse=True):
        hits, n = by_score[v]
        tp += hits
        seen += n
        total += hits / pos * (tp / seen)
    return total


def cls_metrics(prob, y, thr):
    """accuracy at 0.5; balanced accuracy at thr (the training positive rate)."""
    pos, neg = sum(y), len(y) - sum(y)
    acc = sum(1 for p, t in zip(prob, y) if (p >= 0.5) == bool(t)) / len(y)
    tp = sum(1 for p, t in zip(prob, y) if p >= thr and t)
    tn = sum(1 for p, t in zip(prob, y) if p < thr and not t)
    eps = 1e-15
    return {
        "accuracy": acc,
        "balanced_acc": ((tp / pos if pos else 0) + (tn / neg if neg else 0)) / 2,
        "roc_auc": roc_auc(prob, y),
        "pr_auc": avg_precision(prob, y),
        "log_loss": -sum(t * math.log(min(1 - eps, max(eps, p))) + (1 - t) * math.log(min(1 - eps, max(eps, 1 - p)))
                         for p, t in zip(prob, y)) / len(y),
        "brier": sum((p - t) ** 2 for p, t in zip(prob, y)) / len(y),
    }


def reg_metrics(pred, y):
    n = len(y)
    mean = sum(y) / n
    sse = sum((p - t) ** 2 for p, t in zip(pred, y))
    sst = sum((t - mean) ** 2 for t in y)
    abs_err = sum(abs(p - t) for p, t in zip(pred, y))
    return {"mae": abs_err / n, "rmse": math.sqrt(sse / n), "r2": 1 - sse / sst if sst else float("nan"),
            "wape": abs_err / sum(abs(t) for t in y) if any(y) else float("nan")}


# ---------------------------------------------------------------- one-feature learners
def fit_one_feature(train, col, y_tr, label):
    """Smoothed mean target per level (categorical) or per 10 quantile bins (numeric) of one column."""
    vals = [r.get(col, "") for r in train]
    nums = [num(v) for v in vals]
    prior = sum(y_tr) / len(y_tr)
    if sum(x is not None for x in nums) / len(nums) > 0.95:
        xs = sorted(x for x in nums if x is not None)
        edges = sorted({xs[int(len(xs) * q / 10)] for q in range(1, 10)})

        def key(r):
            x = num(r.get(col, ""))
            return None if x is None else sum(1 for e in edges if x >= e)
        desc = f"{label} by {len(edges) + 1} bins of {col}"
    else:
        def key(r):
            return r.get(col, "")
        desc = f"{label} by {col} ({len(set(vals))} levels)"
    sums = defaultdict(lambda: [0.0, 0])
    for r, t in zip(train, y_tr):
        b = sums[key(r)]
        b[0] += t
        b[1] += 1
    means = {k: (sm + 5 * prior) / (n + 5) for k, (sm, n) in sums.items()}
    return {"desc": desc, "score": lambda r: means.get(key(r), prior)}


def pick_one_feature(train, feats, y_tr, binary):
    """Choose the column on an inner split of the training rows (never on the test set), refit on all of train."""
    cut = int(len(train) * 0.7)
    fit, val, y_fit, y_val = train[:cut], train[cut:], y_tr[:cut], y_tr[cut:]
    best = None
    for c in feats:
        m = fit_one_feature(fit, c, y_fit, "rate" if binary else "mean")
        pr = [m["score"](r) for r in val]
        q = roc_auc(pr, y_val) if binary else -reg_metrics(pr, y_val)["mae"]
        if q == q and (best is None or q > best[0]):
            best = (q, c)
    if best is None:
        return None
    return fit_one_feature(train, best[1], y_tr, "positive rate" if binary else "mean")


# ---------------------------------------------------------------- rule
def compile_rule(text, header):
    """'a >= 3 and b == x or c < 2' -> predicate; 'and' binds tighter than 'or'; no parentheses."""
    ors = []
    for disj in re.split(r"\s+or\s+", text.strip()):
        ands = []
        for term in re.split(r"\s+and\s+", disj):
            m = RULE_TERM.match(term)
            if not m:
                raise ValueError(f"cannot parse rule term {term!r}; use 'column op value'")
            col, op, val = m.group(1), m.group(2), m.group(3).strip("'\"")
            if col not in header:
                raise ValueError(f"rule column {col!r} not in data")
            ands.append((col, op, val))
        ors.append(ands)

    def holds(r, col, op, val):
        a, b = num(r.get(col, "")), num(val)
        if a is not None and b is not None:
            return {">=": a >= b, "<=": a <= b, ">": a > b, "<": a < b, "==": a == b, "!=": a != b}[op]
        s = (r.get(col) or "").strip()
        return {"==": s == val, "!=": s != val}.get(op, False)
    return lambda r: any(all(holds(r, *t) for t in ands) for ands in ors)


def main():
    ap = argparse.ArgumentParser(description="Score dummy, one-feature and rule baselines on a holdout.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--time-col", help="sort by this column and hold out the latest rows")
    ap.add_argument("--test-frac", type=float, default=0.25)
    ap.add_argument("--drop", nargs="*", default=[], help="columns that are not features (IDs, leaks)")
    ap.add_argument("--rule", help="current business rule for binary targets, e.g. \"calls >= 3 or plan == basic\"")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = [r for r in reader if not missing(r.get(a.target))]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.target not in header or len(rows) < 20:
        print(f"error: target {a.target!r} missing or fewer than 20 labelled rows", file=sys.stderr)
        return 2
    if a.time_col:
        rows.sort(key=lambda r: r.get(a.time_col, ""))
        split = "time-ordered (latest rows are the test set)"
    else:
        random.Random(a.seed).shuffle(rows)
        split = f"random (seed {a.seed}); use --time-col if the model will predict forward in time"
    cut = int(len(rows) * (1 - a.test_frac))
    train, test = rows[:cut], rows[cut:]
    classes = Counter(r[a.target].strip() for r in rows)
    binary = len(classes) == 2
    feats = [c for c in header if c not in (a.target, a.time_col, *a.drop)]
    results = []

    if binary:
        pos = min(classes, key=classes.get)
        y_tr = [1 if r[a.target].strip() == pos else 0 for r in train]
        y_te = [1 if r[a.target].strip() == pos else 0 for r in test]
        prior = sum(y_tr) / len(y_tr)
        maj = 1 if prior >= 0.5 else 0
        results.append({"baseline": "majority", "detail": f"always {pos if maj else 'not ' + pos}",
                        **cls_metrics([float(maj)] * len(test), y_te, prior)})
        results.append({"baseline": "prior", "detail": f"p = {prior:.3f} for every row",
                        **cls_metrics([prior] * len(test), y_te, prior)})
        m = pick_one_feature(train, feats, y_tr, True)
        if m:
            results.append({"baseline": "one_r", "detail": m["desc"],
                            **cls_metrics([m["score"](r) for r in test], y_te, prior)})
        if a.rule:
            try:
                pred = compile_rule(a.rule, header)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
            results.append({"baseline": "rule", "detail": a.rule,
                            **cls_metrics([1.0 if pred(r) else 0.0 for r in test], y_te, prior)})
        keys = ["accuracy", "balanced_acc", "roc_auc", "pr_auc", "log_loss", "brier"]
        head = (f"positive class {pos!r}: train rate {prior:.3f}, test rate {sum(y_te) / len(y_te):.3f}; accuracy at "
                f"0.5, balanced_acc at the train rate")
    else:
        try:
            y_tr = [float(r[a.target]) for r in train]
            y_te = [float(r[a.target]) for r in test]
        except ValueError:
            print("error: target is neither binary nor numeric; for multiclass use the majority class "
                  "per one-vs-rest target", file=sys.stderr)
            return 2
        mean = sum(y_tr) / len(y_tr)
        med = sorted(y_tr)[len(y_tr) // 2]
        results.append({"baseline": "mean", "detail": f"{mean:.4g}", **reg_metrics([mean] * len(test), y_te)})
        results.append({"baseline": "median", "detail": f"{med:.4g}", **reg_metrics([med] * len(test), y_te)})
        m = pick_one_feature(train, feats, y_tr, False)
        if m:
            results.append({"baseline": "one_r", "detail": m["desc"],
                            **reg_metrics([m["score"](r) for r in test], y_te)})
        keys = ["mae", "rmse", "r2", "wape"]
        head = f"numeric target: train mean {mean:.4g}, median {med:.4g}"

    out = {"split": split, "train_rows": len(train), "test_rows": len(test), "summary": head, "baselines": results}
    if a.json:
        print(json.dumps(out, indent=2, default=lambda x: None))
        return 0
    print(f"Split: {split}; train {len(train)}, test {len(test)}")
    print(head)
    print(f"\n{'baseline':<10} " + " ".join(f"{k:>12}" for k in keys) + "  detail")
    for r in results:
        print(f"{r['baseline']:<10} " + " ".join(f"{r[k]:>12.4f}" for k in keys) + f"  {r['detail']}")
    print("\nA model is worth shipping only if it beats the best row here on the primary metric, by more than the "
          "noise (compare with a CI or repeated splits).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
