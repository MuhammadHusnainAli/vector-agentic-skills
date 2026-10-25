#!/usr/bin/env python3
"""Evaluate anomaly scores, with labels (precision at the alert budget) or without (agreement, thresholds).

Input: a CSV with one or more score columns (higher = more anomalous; e.g. the output of
anomaly_scores.py --out) and optionally a 0/1 label column of known anomalies.
With --label, per score column:
  ROC-AUC, PR-AUC (average precision), precision@k and recall@k for each alert budget in --k
  and the best detector per budget
Without labels:
  Spearman rank correlation between detectors and the Jaccard overlap of their top-k sets
  (detectors that agree are seeing the same thing; disagreement = different anomaly types)
Always: threshold suggestions per score - the score at each --k (alert budget), the 99th / 99.5th
percentile, and median + 3 MAD (robust cut on the score distribution) with how many rows each flags.

Usage:
    python anomaly_eval.py scores.csv --scores score_iforest score_knn score_ensemble --label is_anomaly --k 5 10 20
    python anomaly_eval.py scores.csv --scores score_robust_z score_mahalanobis --k 10
    python anomaly_eval.py scores.csv --scores s1 s2 --json

Exit codes: 0 evaluated, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ranks(v):
    order = sorted(range(len(v)), key=v.__getitem__)
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def auc(s, y):
    pos = sum(y)
    neg = len(y) - pos
    r = ranks(s)
    return (sum(ri for ri, t in zip(r, y) if t) - pos * (pos + 1) / 2) / (pos * neg)


def ap(s, y):
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


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    m = (n + 1) / 2
    cov = sum((x - m) * (z - m) for x, z in zip(ra, rb))
    va = math.sqrt(sum((x - m) ** 2 for x in ra))
    vb = math.sqrt(sum((z - m) ** 2 for z in rb))
    return cov / (va * vb) if va and vb else 0.0


def main():
    ap_ = argparse.ArgumentParser(description="Evaluate anomaly scores with or without labels.", epilog=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("csv")
    ap_.add_argument("--scores", nargs="+", required=True)
    ap_.add_argument("--label")
    ap_.add_argument("--k", nargs="+", type=int, default=[10, 20, 50])
    ap_.add_argument("--json", action="store_true")
    a = ap_.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rd = csv.DictReader(fh)
            miss = [c for c in a.scores + ([a.label] if a.label else []) if c not in (rd.fieldnames or [])]
            if miss:
                raise ValueError(f"missing column(s) {miss}")
            rows = list(rd)
        S = {c: [num(r[c]) for r in rows] for c in a.scores}
        if any(v is None for vals in S.values() for v in vals):
            raise ValueError("non-numeric score values")
        y = [int(float(r[a.label])) for r in rows] if a.label else None
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    n = len(rows)
    ks = [k for k in a.k if 0 < k <= n]
    out = {"rows": n, "scores": {}}
    for c, s in S.items():
        order = sorted(range(n), key=lambda i: -s[i])
        srt = sorted(s)
        med = srt[n // 2]
        mad = sorted(abs(v - med) for v in s)[n // 2] * 1.4826
        cut_mad = med + 3 * mad
        th = {"at_k": {k: s[order[k - 1]] for k in ks},
              "p99": srt[min(n - 1, int(0.99 * n))], "p995": srt[min(n - 1, int(0.995 * n))],
              "median_plus_3mad": cut_mad, "flagged_by_3mad": sum(1 for v in s if v > cut_mad)}
        e = {"thresholds": th}
        if y:
            if sum(y) in (0, n):
                print("error: label column needs both classes", file=sys.stderr)
                return 2
            e["roc_auc"] = auc(s, y)
            e["pr_auc"] = ap(s, y)
            e["at_k"] = {k: {"precision": sum(y[i] for i in order[:k]) / k, "recall": sum(y[i] for i in order[:k]) / sum(y)}
                         for k in ks}
        out["scores"][c] = e
    if not y and len(S) > 1:
        names = list(S)
        agree = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a1, a2 = S[names[i]], S[names[j]]
                k0 = ks[0] if ks else min(10, n)
                t1 = set(sorted(range(n), key=lambda q: -a1[q])[:k0])
                t2 = set(sorted(range(n), key=lambda q: -a2[q])[:k0])
                agree.append({"a": names[i], "b": names[j], "spearman": spearman(a1, a2),
                              f"top{k0}_jaccard": len(t1 & t2) / len(t1 | t2)})
        out["agreement"] = agree
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{n} rows" + (f", {sum(y)} labelled anomalies ({sum(y) / n:.2%})" if y else ", no labels"))
    if y:
        head = f"{'score':<20} {'ROC-AUC':>8} {'PR-AUC':>7}" + "".join(f" {'P@' + str(k):>6} {'R@' + str(k):>6}" for k in ks)
        print(head)
        for c, e in out["scores"].items():
            print(f"{c:<20} {e['roc_auc']:>8.3f} {e['pr_auc']:>7.3f}" +
                  "".join(f" {e['at_k'][k]['precision']:>6.2f} {e['at_k'][k]['recall']:>6.2f}" for k in ks))
        for k in ks:
            top = max(out["scores"][c]["at_k"][k]["precision"] for c in out["scores"])
            tied = [c for c in out["scores"] if out["scores"][c]["at_k"][k]["precision"] == top]
            label = tied[0] if len(tied) == 1 else f"tie between {', '.join(tied)}"
            print(f"  best at a budget of {k} alerts: {label} (precision {top:.2f})")
    for row in out.get("agreement", []):
        jk = [k for k in row if k.endswith("_jaccard")][0]
        print(f"agreement {row['a']} vs {row['b']}: Spearman {row['spearman']:.2f}, {jk.replace('_', ' ')} {row[jk]:.2f}")
    print("\nthreshold suggestions:")
    for c, e in out["scores"].items():
        th = e["thresholds"]
        atk = ", ".join(f"top-{k} >= {v:.4g}" for k, v in th["at_k"].items())
        print(f"  {c}: {atk}; p99 {th['p99']:.4g}; median+3MAD {th['median_plus_3mad']:.4g} "
              f"(flags {th['flagged_by_3mad']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
