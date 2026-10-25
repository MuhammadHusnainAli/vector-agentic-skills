#!/usr/bin/env python3
"""Learn a small, human-readable rule set from a CSV and say how much signal it captures.

Fits a shallow binary decision tree (CART, Gini, depth <= --max-depth, every leaf has at
least --min-leaf rows) in pure Python, then prints:
  - the rules as IF ... THEN lines with each leaf's positive rate, size and lift
  - holdout ROC-AUC, PR-AUC and precision/recall when flagging leaves above --flag-rate
  - a SQL CASE expression you can deploy as a rule, and the same rule for --rule input
  - optional comparison with your ML model's holdout metric (--ml-auc)

If a depth-2/3 tree gets close to the model, rules may be the better product: cheaper,
auditable and easy to change. If the gap is large, the signal is in interactions or many
weak features and ML earns its cost.

Usage:
    python rule_learner.py data.csv --target churned --drop customer_id --time-col signup_date
    python rule_learner.py data.csv --target is_fraud --max-depth 2 --min-leaf 30 --ml-auc 0.91
    python rule_learner.py data.csv --target churned --json

Exit codes: 0 fitted, 2 usage/read error or target not binary.
"""

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def gini(pos, n):
    if n == 0:
        return 0.0
    p = pos / n
    return 2 * p * (1 - p)


def candidate_splits(rows, ys, col, numeric):
    """Yield (description, predicate) pairs for one column."""
    if numeric:
        xs = sorted({num(r[col]) for r in rows if num(r[col]) is not None})
        if len(xs) > 32:
            xs = sorted({xs[int(len(xs) * q / 32)] for q in range(1, 32)})
        for x in xs[1:]:
            yield (col, ">=", x), (lambda r, c=col, t=x: (num(r[c]) is not None and num(r[c]) >= t))
    else:
        for level, cnt in Counter(r[col] for r in rows).most_common(20):
            if cnt >= 2:
                yield (col, "==", level), (lambda r, c=col, lv=level: r[c] == lv)


def best_split(rows, ys, cols, kinds, min_leaf):
    n, pos = len(ys), sum(ys)
    parent = gini(pos, n)
    best = None
    for col in cols:
        for cond, pred in candidate_splits(rows, ys, col, kinds[col]):
            lp = ln = 0
            for r, y in zip(rows, ys):
                if pred(r):
                    ln += 1
                    lp += y
            rn = n - ln
            if ln < min_leaf or rn < min_leaf:
                continue
            gain = parent - (ln / n) * gini(lp, ln) - (rn / n) * gini(pos - lp, rn)
            if best is None or gain > best[0]:
                best = (gain, cond, pred)
    return best


def grow(rows, ys, cols, kinds, depth, max_depth, min_leaf):
    node = {"n": len(ys), "pos": sum(ys)}
    if depth < max_depth and 0 < node["pos"] < node["n"]:
        s = best_split(rows, ys, cols, kinds, min_leaf)
        if s and s[0] > 1e-4:
            _, cond, pred = s
            left = [(r, y) for r, y in zip(rows, ys) if pred(r)]
            right = [(r, y) for r, y in zip(rows, ys) if not pred(r)]
            node.update(cond=cond, pred=pred,
                        yes=grow([r for r, _ in left], [y for _, y in left], cols, kinds, depth + 1, max_depth, min_leaf),
                        no=grow([r for r, _ in right], [y for _, y in right], cols, kinds, depth + 1, max_depth, min_leaf))
    return node


def leaves(node, path=()):
    if "cond" not in node:
        yield path, node
        return
    yield from leaves(node["yes"], path + ((node["cond"], True),))
    yield from leaves(node["no"], path + ((node["cond"], False),))


def score(node, r, prior):
    while "cond" in node:
        node = node["yes"] if node["pred"](r) else node["no"]
    return (node["pos"] + 2 * prior) / (node["n"] + 2)


def simplify(path):
    """Merge a root-to-leaf path into one interval per numeric column and the categorical tests.

    Missing numeric values fail every '>=' test, so they follow the 'no' branches: a column
    with no lower bound on the path also admits NULL.
    """
    lo, hi, cats = {}, {}, []
    for (col, op, val), truth in path:
        if op == ">=":
            if truth:
                lo[col] = max(lo.get(col, val), val)
            else:
                hi[col] = min(hi.get(col, val), val)
        else:
            cats.append((col, val, truth))
    parts = []
    for col in dict.fromkeys(list(lo) + list(hi)):
        parts.append(("num", col, lo.get(col), hi.get(col)))
    return parts + [("cat", col, val, truth) for col, val, truth in cats]


def rule_text(parts, sql=False):
    out = []
    for kind, col, a, b in parts:
        if kind == "num":
            lo, hi = a, b
            if sql:
                if lo is not None:
                    out.append(f"{col} >= {lo:g}" + (f" AND {col} < {hi:g}" if hi is not None else ""))
                else:
                    out.append(f"({col} < {hi:g} OR {col} IS NULL)")
            else:
                out.append(f"{lo:g} <= {col} < {hi:g}" if lo is not None and hi is not None else
                           f"{col} >= {lo:g}" if lo is not None else f"{col} < {hi:g} (or missing)")
        else:
            val, truth = a, b
            if sql:
                q = "'" + str(val).replace("'", "''") + "'"
                out.append(f"{col} = {q}" if truth else f"({col} <> {q} OR {col} IS NULL)")
            else:
                out.append(f"{col} == {val!r}" if truth else f"{col} != {val!r}")
    return " AND ".join(out)


def auc(s, y):
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
    g = defaultdict(lambda: [0, 0])
    for v, t in zip(s, y):
        g[v][0] += t
        g[v][1] += 1
    P, tp, seen, tot = sum(y), 0, 0, 0.0
    for v in sorted(g, reverse=True):
        tp += g[v][0]
        seen += g[v][1]
        tot += g[v][0] / P * tp / seen
    return tot


def main():
    ap = argparse.ArgumentParser(description="Learn a shallow readable rule set and measure it on a holdout.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--time-col", help="hold out the latest rows by this column (else seeded random)")
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--min-leaf", type=int, default=20)
    ap.add_argument("--test-frac", type=float, default=0.3)
    ap.add_argument("--flag-rate", type=float, help="flag leaves whose positive rate is >= this (default 2x prior)")
    ap.add_argument("--ml-auc", type=float, help="your ML model's ROC-AUC on the same holdout, for the comparison")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = [r for r in reader if (r.get(a.target) or "").strip().lower() not in MISSING]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    classes = Counter(r[a.target].strip() for r in rows)
    if a.target not in header or len(classes) != 2:
        print(f"error: target {a.target!r} must exist and have exactly 2 values (found {len(classes)})", file=sys.stderr)
        return 2
    pos_label = min(classes, key=classes.get)
    if a.time_col:
        rows.sort(key=lambda r: r.get(a.time_col, ""))
    else:
        random.Random(a.seed).shuffle(rows)
    cut = int(len(rows) * (1 - a.test_frac))
    train, test = rows[:cut], rows[cut:]
    y_tr = [1 if r[a.target].strip() == pos_label else 0 for r in train]
    y_te = [1 if r[a.target].strip() == pos_label else 0 for r in test]
    cols = [c for c in header if c not in (a.target, a.time_col, *a.drop)]
    kinds = {}
    for c in cols:
        vals = [r[c] for r in train if (r[c] or "").strip().lower() not in MISSING]
        kinds[c] = bool(vals) and sum(num(v) is not None for v in vals) / len(vals) > 0.95
    cols = [c for c in cols if kinds[c] or len({r[c] for r in train}) <= 50]   # skip ID-like text
    tree = grow(train, y_tr, cols, kinds, 0, a.max_depth, a.min_leaf)
    prior = sum(y_tr) / len(y_tr)
    flag = a.flag_rate if a.flag_rate is not None else min(0.99, 2 * prior)
    s_te = [score(tree, r, prior) for r in test]
    flagged = [s >= flag for s in s_te]
    tp = sum(1 for f, y in zip(flagged, y_te) if f and y)
    nf = sum(flagged)
    res = {"positive_label": pos_label, "train_rows": len(train), "test_rows": len(test), "train_rate": prior,
           "test_auc": auc(s_te, y_te), "test_pr_auc": avg_precision(s_te, y_te), "flag_rate": flag,
           "flagged": nf, "precision": tp / nf if nf else 0.0, "recall": tp / sum(y_te) if sum(y_te) else 0.0,
           "rules": []}
    sql_when = []
    for path, leaf in sorted(leaves(tree), key=lambda pl: -(pl[1]["pos"] / pl[1]["n"])):
        rate = leaf["pos"] / leaf["n"]
        parts = simplify(path)
        text = rule_text(parts) or "(all rows)"
        res["rules"].append({"if": text, "rows": leaf["n"], "positive_rate": rate, "lift": rate / prior if prior else 0,
                             "flag": rate >= flag})
        if rate >= flag:
            sql_when.append("(" + (rule_text(parts, sql=True) or "1 = 1") + ")")
    res["sql"] = ("CASE WHEN " + "\n       OR ".join(sql_when) + " THEN 1 ELSE 0 END AS rule_flag") if sql_when else None
    if a.ml_auc:
        gap = a.ml_auc - res["test_auc"]
        res["ml_auc"], res["gap"] = a.ml_auc, gap
        res["verdict"] = ("rules are competitive (gap < 0.03 AUC): prefer rules unless ML adds other value" if gap < 0.03
                          else "ML adds a moderate lift (0.03-0.08 AUC): hybrid or ML if the lift pays its cost"
                          if gap < 0.08 else "ML clearly ahead (> 0.08 AUC): the signal is beyond a few rules")
    if a.json:
        out = dict(res)
        print(json.dumps(out, indent=2))
        return 0
    print(f"Rule tree (depth <= {a.max_depth}, min leaf {a.min_leaf}) for {a.target} == {pos_label!r}; "
          f"train rate {prior:.3f}")
    for rule in res["rules"]:
        mark = "FLAG" if rule["flag"] else "    "
        print(f"  {mark} IF {rule['if']}\n         THEN rate {rule['positive_rate']:.3f}  (n={rule['rows']}, "
              f"lift {rule['lift']:.2f}x)")
    print(f"\nHoldout ({len(test)} rows): ROC-AUC {res['test_auc']:.3f}  PR-AUC {res['test_pr_auc']:.3f}  "
          f"flagging leaves >= {flag:.3f}: {nf} flagged, precision {res['precision']:.3f}, recall {res['recall']:.3f}")
    if a.ml_auc:
        print(f"ML model AUC {a.ml_auc:.3f} vs rules {res['test_auc']:.3f} (gap {res['gap']:+.3f}): {res['verdict']}")
    if res["sql"]:
        print("\nDeployable rule:\n" + res["sql"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
