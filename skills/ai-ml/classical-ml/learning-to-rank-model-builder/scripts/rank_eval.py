#!/usr/bin/env python3
"""Evaluate rankings per query: NDCG, MAP, MRR, ERR, precision@k, and whether model A really beats model B.

Input: CSV with query id, graded relevance label and one or more score columns (higher = ranked higher), e.g.
the predictions of several rankers on the same test documents: qid,label,bm25,lgbm_score,xgb_score.

Per score column (averaged over queries):
  NDCG@k   gain 2^label - 1 (--gain exp, the LightGBM/XGBoost/TREC default) or label (--gain linear, the
           scikit-learn ndcg_score convention), log2 discount
  MAP@k, MRR, P@k   binary relevance: label >= --rel-min
  ERR@k    expected reciprocal rank (cascade model; graded labels)
Queries without any relevant document have undefined NDCG: --empty skip (default, excluded and counted),
one (LightGBM's convention: counts as 1.0) or zero. Score ties are broken pessimistically by default (lower
label first, so a constant or coarse score cannot look good); --ties input keeps file order within ties, which
reproduces LightGBM's own NDCG@k evaluation (rows in group order), --ties optimistic the upper bound.
Comparison (--baseline COLUMN): for every other column, the mean per-query NDCG@k difference with a
95% bootstrap CI over queries and a paired randomisation (sign-flip) test p-value (10,000 permutations,
seeded) - queries are the unit of analysis, not documents.

Usage:
    python rank_eval.py ltr.csv --qid-col qid --label-col label --scores bm25 clicks score --k 5 10
    python rank_eval.py preds.csv --scores lgbm xgb --baseline bm25 --k 10 --gain linear
    python rank_eval.py preds.csv --scores model --k 10 --per-query worst.csv --json

Exit codes: 0 evaluated, 1 with --baseline when no model is significantly better (p < 0.05), 2 usage error.
"""

import argparse
import csv
import json
import math
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rank_metrics import average_precision, err, ndcg, precision, rank_by, reciprocal_rank  # noqa: E402


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def per_query(groups, col, k, a, max_label):
    out = {}
    for q, docs in groups.items():
        d = [(lab, s[col]) for lab, s in docs]
        ranked = rank_by(d, a.ties)
        nd = ndcg(ranked, k, a.gain)
        if nd is None:
            nd = {"skip": None, "one": 1.0, "zero": 0.0}[a.empty]
        out[q] = {"ndcg": nd, "map": average_precision(ranked, k, a.rel_min), "mrr": reciprocal_rank(ranked, a.rel_min),
                  "p": precision(ranked, k, a.rel_min), "err": err(ranked, k, max_label)}
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def compare(base, other, seed=0, boots=2000, perms=10000):
    qs = [q for q in base if base[q]["ndcg"] is not None and other[q]["ndcg"] is not None]
    diffs = [other[q]["ndcg"] - base[q]["ndcg"] for q in qs]
    n = len(diffs)
    md = sum(diffs) / n
    rng = random.Random(seed)
    bs = sorted(sum(diffs[rng.randrange(n)] for _ in range(n)) / n for _ in range(boots))
    ci = (bs[int(0.025 * boots)], bs[int(0.975 * boots) - 1])
    obs = abs(md)
    extreme = 0
    for _ in range(perms):
        s = sum(d if rng.random() < 0.5 else -d for d in diffs) / n
        if abs(s) >= obs - 1e-15:
            extreme += 1
    return {"queries": n, "mean_diff": md, "ci": ci, "p": (extreme + 1) / (perms + 1),
            "wins": sum(1 for d in diffs if d > 1e-12), "losses": sum(1 for d in diffs if d < -1e-12)}


def main():
    ap = argparse.ArgumentParser(description="Evaluate rankings per query.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--qid-col", default="qid")
    ap.add_argument("--label-col", default="label")
    ap.add_argument("--scores", nargs="+", required=True)
    ap.add_argument("--k", type=int, nargs="+", default=[10])
    ap.add_argument("--gain", choices=["exp", "linear"], default="exp")
    ap.add_argument("--rel-min", type=float, default=1)
    ap.add_argument("--empty", choices=["skip", "one", "zero"], default="skip")
    ap.add_argument("--ties", choices=["pessimistic", "input", "optimistic"], default="pessimistic",
                    help="order of documents with equal scores (input = file order, as LightGBM does)")
    ap.add_argument("--baseline", help="score column to compare every other column against")
    ap.add_argument("--per-query", help="write per-query NDCG@k (first k) for each column to this CSV")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        cols = [a.qid_col, a.label_col] + a.scores + ([a.baseline] if a.baseline else [])
        miss = [c for c in cols if c not in rows[0]]
        if miss:
            raise ValueError(f"columns not found: {', '.join(miss)}")
        groups = defaultdict(list)
        for r in rows:
            lab = num(r[a.label_col])
            if lab is None:
                raise ValueError("labels must be numeric")
            groups[r[a.qid_col]].append((lab, {c: num(r[c]) if num(r[c]) is not None else -math.inf
                                               for c in set(a.scores) | ({a.baseline} if a.baseline else set())}))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    max_label = max(lab for g in groups.values() for lab, _ in g)
    columns = list(dict.fromkeys(([a.baseline] if a.baseline else []) + a.scores))
    res = {"queries": len(groups), "gain": a.gain, "results": {}, "comparisons": {}}
    pq_first = {}
    for k in a.k:
        res["results"][k] = {}
        for c in columns:
            pq = per_query(groups, c, k, a, max_label)
            if k == a.k[0]:
                pq_first[c] = pq
            vals = list(pq.values())
            res["results"][k][c] = {m: mean(v[m] for v in vals) for m in ("ndcg", "map", "mrr", "p", "err")}
            res["results"][k][c]["evaluated"] = sum(1 for v in vals if v["ndcg"] is not None)
    empty = sum(1 for g in groups.values() if not any(lab >= a.rel_min for lab, _ in g))
    if a.baseline:
        for c in a.scores:
            if c != a.baseline:
                res["comparisons"][c] = compare(pq_first[a.baseline], pq_first[c])
    if a.per_query:
        with open(a.per_query, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["qid"] + [f"{c}_ndcg@{a.k[0]}" for c in columns])
            for q in groups:
                w.writerow([q] + [pq_first[c][q]["ndcg"] for c in columns])
    if a.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        print(f"queries: {len(groups)}   gain: {a.gain}   relevant: label >= {a.rel_min:g}   "
              f"queries without relevant documents: {empty} ({'excluded' if a.empty == 'skip' else 'NDCG=' + a.empty})")
        for k in a.k:
            print(f"\n@{k}")
            print(f"{'model':<20} {'NDCG':>8} {'MAP':>8} {'MRR':>8} {'P':>8} {'ERR':>8}")
            for c, v in sorted(res["results"][k].items(), key=lambda kv: -(kv[1]["ndcg"] or 0)):
                print(f"{c:<20} " + " ".join(f"{(v[m] if v[m] is not None else float('nan')):>8.4f}"
                                             for m in ("ndcg", "map", "mrr", "p", "err")))
        if res["comparisons"]:
            print(f"\npaired comparison vs {a.baseline} (NDCG@{a.k[0]}, per query):")
            for c, d in res["comparisons"].items():
                verdict = "better" if d["p"] < 0.05 and d["mean_diff"] > 0 else (
                    "worse" if d["p"] < 0.05 else "no significant difference")
                print(f"  {c:<18} diff {d['mean_diff']:+.4f} [95% CI {d['ci'][0]:+.4f}, {d['ci'][1]:+.4f}]  "
                      f"p = {d['p']:.4f}  wins/losses {d['wins']}/{d['losses']}  -> {verdict}")
    if a.baseline and res["comparisons"]:
        if not any(d["p"] < 0.05 and d["mean_diff"] > 0 for d in res["comparisons"].values()):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
