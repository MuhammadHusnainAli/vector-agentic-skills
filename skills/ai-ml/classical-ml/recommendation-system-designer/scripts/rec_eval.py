#!/usr/bin/env python3
"""Evaluate top-k recommendation lists: accuracy, beyond-accuracy metrics and a popularity baseline.

Inputs:
  --recs    CSV user_id,item_id[,rank|score]: each user's recommendation list (rank 1 = top; or a score,
            higher = better). Several models: add a `model` column.
  --test    held-out interactions (user_id,item_id[,rating]); with --min-rating only rows with
            rating >= the threshold are relevant
  --train   training interactions: used to exclude already-seen items from the lists (--keep-seen to
            disable), to build the popularity baseline, and for novelty / popularity-bias / coverage

Metrics @k (averaged over test users who have at least one relevant item):
  precision, recall, hit rate, MRR, MAP, NDCG (binary relevance; graded by rating with --graded)
Beyond accuracy:
  coverage         share of the catalogue (items in train) that appears in any list
  novelty          mean self-information -log2(popularity) of recommended items (higher = less obvious)
  popularity bias  mean train popularity of recommended items / mean popularity of the catalogue
  personalisation  1 - mean Jaccard overlap between users' lists (0 = everyone gets the same list)
  diversity        with --item-features (item_id,category): mean share of distinct categories in a list
Baseline: the most popular unseen train items for each user ("popularity"), always evaluated alongside.
Users in test with no recommendations count as zero (reported as missing users).

Usage:
    python rec_eval.py --recs recs.csv --test test.csv --train train.csv --k 10
    python rec_eval.py --recs recs.csv --test test.csv --train train.csv --k 10 --min-rating 4 --item-features items.csv
    python rec_eval.py --recs all_models.csv --test test.csv --train train.csv --k 5 20 --json

Exit codes: 0 evaluated (the best model beats popularity on NDCG@k), 1 no model beats the popularity
baseline, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def num(v, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def lists_from(rows, ucol, icol):
    by = defaultdict(lambda: defaultdict(list))
    has_rank = "rank" in rows[0]
    has_score = "score" in rows[0]
    for i, r in enumerate(rows):
        key = num(r["rank"], i) if has_rank else (-num(r["score"], 0.0) if has_score else i)
        by[r.get("model", "model")][r[ucol]].append((key, r[icol]))
    out = {}
    for m, users in by.items():
        out[m] = {u: [it for _, it in sorted(v)] for u, v in users.items()}
    return out


def evaluate(lists, relevant, grades, k, seen, pop, n_users_train, catalog, cats, keep_seen):
    users = list(relevant)
    p = r = hit = mrr = ap = nd = 0.0
    rec_items = Counter()
    nov, popb, div = [], [], []
    tops = []
    missing = 0
    max_pop = max(pop.values()) if pop else 1
    mean_cat_pop = sum(pop.values()) / len(catalog) if catalog else 1
    for u in users:
        lst = lists.get(u)
        if lst is None:
            missing += 1
            continue
        if not keep_seen:
            lst = [it for it in lst if it not in seen.get(u, set())]
        lst = lst[:k]
        rel = relevant[u]
        hits = [1 if it in rel else 0 for it in lst]
        nh = sum(hits)
        p += nh / k
        r += nh / len(rel)
        hit += 1 if nh else 0
        first = next((i for i, h in enumerate(hits) if h), None)
        mrr += 1 / (first + 1) if first is not None else 0
        s, c = 0.0, 0
        for i, h in enumerate(hits):
            if h:
                c += 1
                s += c / (i + 1)
        ap += s / min(len(rel), k)
        gains = [grades.get((u, it), 1.0) if it in rel else 0.0 for it in lst]
        dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
        ideal = sorted((grades.get((u, it), 1.0) for it in rel), reverse=True)[:k]
        idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
        nd += dcg / idcg if idcg else 0
        rec_items.update(lst)
        for it in lst:
            pr = pop.get(it, 0) / max(1, n_users_train)
            nov.append(-math.log2(pr) if pr > 0 else -math.log2(1 / max(1, n_users_train)))
            popb.append(pop.get(it, 0) / mean_cat_pop if mean_cat_pop else 0)
        if cats and lst:
            div.append(len({cats.get(it) for it in lst}) / len(lst))
        tops.append(set(lst))
    n = len(users)
    res = {"users": n, "missing_users": missing, "precision": p / n, "recall": r / n, "hit_rate": hit / n,
           "mrr": mrr / n, "map": ap / n, "ndcg": nd / n,
           "coverage": len(set(rec_items) & catalog) / len(catalog) if catalog else None,
           "novelty": sum(nov) / len(nov) if nov else None,
           "popularity_bias": sum(popb) / len(popb) if popb else None}
    if len(tops) >= 2:
        sample = tops[:300]
        pairs = [(a, b) for i, a in enumerate(sample) for b in sample[i + 1:]]
        res["personalisation"] = 1 - sum(len(a & b) / len(a | b) for a, b in pairs if a | b) / len(pairs)
    if div:
        res["diversity"] = sum(div) / len(div)
    return res


def main():
    ap = argparse.ArgumentParser(description="Evaluate top-k recommendations.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recs", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--k", type=int, nargs="+", default=[10])
    ap.add_argument("--user-col", default="user_id")
    ap.add_argument("--item-col", default="item_id")
    ap.add_argument("--rating-col", default="rating")
    ap.add_argument("--min-rating", type=float)
    ap.add_argument("--graded", action="store_true", help="NDCG gain from the rating instead of 1")
    ap.add_argument("--item-features", help="CSV item_id,category for diversity")
    ap.add_argument("--keep-seen", action="store_true", help="do not filter items the user had in train")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        recs, test, train = read(a.recs), read(a.test), read(a.train)
        for name, rows in (("recs", recs), ("test", test), ("train", train)):
            for c in (a.user_col, a.item_col):
                if c not in rows[0]:
                    raise ValueError(f"{name} file lacks column {c!r}")
        cats = None
        if a.item_features:
            fr = read(a.item_features)
            cc = next((c for c in fr[0] if c != a.item_col), None)
            cats = {r[a.item_col]: r[cc] for r in fr}
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    relevant, grades = defaultdict(set), {}
    for r in test:
        rating = num(r.get(a.rating_col), 1.0)
        if a.min_rating is not None and rating < a.min_rating:
            continue
        relevant[r[a.user_col]].add(r[a.item_col])
        if a.graded:
            grades[(r[a.user_col], r[a.item_col])] = rating
    seen = defaultdict(set)
    pop = Counter()
    for r in train:
        seen[r[a.user_col]].add(r[a.item_col])
        pop[r[a.item_col]] += 1
    catalog = set(pop)
    n_train_users = len(seen)
    lists = lists_from(recs, a.user_col, a.item_col)
    ranked_pop = [it for it, _ in pop.most_common()]
    kmax = max(a.k)
    lists["popularity"] = {u: [it for it in ranked_pop if it not in seen[u]][:kmax + 50] for u in relevant}
    out = {}
    for k in a.k:
        out[k] = {m: evaluate(l, relevant, grades, k, seen, pop, n_train_users, catalog, cats, a.keep_seen)
                  for m, l in lists.items()}
    if a.json:
        print(json.dumps({str(k): v for k, v in out.items()}, indent=2))
    else:
        for k, res in out.items():
            cols = ["precision", "recall", "hit_rate", "mrr", "map", "ndcg", "coverage", "novelty", "popularity_bias",
                    "personalisation"] + (["diversity"] if cats else [])
            print(f"@{k}  ({next(iter(res.values()))['users']} test users with relevant items)")
            print(f"{'model':<16}" + "".join(f"{c[:11]:>12}" for c in cols))
            for m, v in sorted(res.items(), key=lambda kv: -kv[1]["ndcg"]):
                print(f"{m:<16}" + "".join(f"{v.get(c):>12.4f}" if isinstance(v.get(c), float) else f"{'n/a':>12}"
                                           for c in cols))
                if v["missing_users"]:
                    print(f"{'':<16}  {v['missing_users']} test user(s) without recommendations (scored as 0)")
            print()
    k0 = a.k[0]
    models = {m: v for m, v in out[k0].items() if m != "popularity"}
    best = max(models.values(), key=lambda v: v["ndcg"]) if models else None
    if best is not None and best["ndcg"] <= out[k0]["popularity"]["ndcg"]:
        if not a.json:
            print(f"NO MODEL BEATS POPULARITY on NDCG@{k0}: check the split, the seen-item filter and the model")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
