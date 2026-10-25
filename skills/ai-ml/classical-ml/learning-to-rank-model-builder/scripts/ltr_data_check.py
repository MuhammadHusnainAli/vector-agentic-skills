#!/usr/bin/env python3
"""Check a learning-to-rank dataset before training: groups, labels, ordering and feature usefulness.

Input: CSV with a query id column, a relevance label column (graded integers, e.g. 0-4) and feature columns
(every other numeric column unless --features is given; --exclude for ids and scores).

Checks:
  groups        number of queries, documents per query (min / median / max), singleton queries
  ordering      whether rows of each query are contiguous; LightGBM and XGBoost rankers take group SIZES in
                row order, so unsorted data silently mixes queries - sort by query id before building groups
  labels        label distribution, queries where all documents share one label (no ranking signal for
                pairwise/listwise losses: they contribute nothing to training and NDCG is undefined or 1),
                queries without any relevant document (label >= --rel-min)
  duplicates    the same document twice in one query
  features      per feature: NDCG@k of ranking each query by that feature alone (a single-feature baseline,
                both directions), constant-within-query features (query-level: they cannot reorder documents
                inside a query on their own, only through interactions), and near-perfect rankers
                (NDCG@k >= 0.98: likely label leakage, e.g. a click or rating derived from the label)

Usage:
    python ltr_data_check.py ltr.csv --qid-col qid --label-col label --exclude doc_id score
    python ltr_data_check.py train.csv --qid-col query --label-col rel --features bm25 pagerank ctr --k 5 --json

Exit codes: 0 no blocking issue, 1 blocking issue (unsorted groups, duplicates or a leakage-like feature),
2 usage or read error.
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rank_metrics import ndcg, rank_by  # noqa: E402


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="Check a learning-to-rank dataset.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--qid-col", default="qid")
    ap.add_argument("--label-col", default="label")
    ap.add_argument("--doc-col", help="document id column for duplicate checks")
    ap.add_argument("--features", nargs="*")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--rel-min", type=float, default=1)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        cols = list(rows[0])
        for c in (a.qid_col, a.label_col):
            if c not in cols:
                raise ValueError(f"column {c!r} not found (have: {', '.join(cols)})")
        doc_col = a.doc_col or next((c for c in cols if c.lower() in ("doc_id", "docid", "item_id", "document")), None)
        skip = {a.qid_col, a.label_col, doc_col, *a.exclude}
        feats = a.features or [c for c in cols if c not in skip and all(num(r[c]) is not None for r in rows[:200])]
        missing = [c for c in feats if c not in cols]
        if missing:
            raise ValueError(f"features not found: {', '.join(missing)}")
        labels = [num(r[a.label_col]) for r in rows]
        if any(v is None for v in labels):
            raise ValueError("labels must be numeric")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    res = {"warnings": [], "blocking": []}
    seen, order_ok, last = set(), True, None
    for r in rows:
        q = r[a.qid_col]
        if q != last:
            if q in seen:
                order_ok = False
            seen.add(q)
            last = q
    groups = defaultdict(list)
    for r, lab in zip(rows, labels):
        groups[r[a.qid_col]].append((r, lab))
    sizes = sorted(len(g) for g in groups.values())
    res["queries"] = len(groups)
    res["docs_per_query"] = {"min": sizes[0], "median": sizes[len(sizes) // 2], "max": sizes[-1]}
    res["label_dist"] = {str(int(k) if float(k).is_integer() else k): v for k, v in sorted(Counter(labels).items())}
    res["contiguous_groups"] = order_ok
    if not order_ok:
        res["blocking"].append("rows of some queries are not contiguous: sort by query id before computing group sizes "
                               "(LightGBM group= / XGBoost qid= assume contiguous blocks)")
    same = [q for q, g in groups.items() if len({lab for _, lab in g}) == 1]
    norel = [q for q, g in groups.items() if not any(lab >= a.rel_min for _, lab in g)]
    singles = [q for q, g in groups.items() if len(g) == 1]
    res["single_label_queries"], res["no_relevant_queries"], res["singleton_queries"] = same, norel, singles
    if same:
        res["warnings"].append(f"{len(same)} query(ies) where every document has the same label "
                               f"({', '.join(same[:5])}): no signal for pairwise/listwise training; exclude them from "
                               "NDCG averages or report them separately")
    if doc_col:
        dups = [q for q, g in groups.items() if len({r[doc_col] for r, _ in g}) < len(g)]
        if dups:
            res["blocking"].append(f"duplicate documents within {len(dups)} query(ies): {', '.join(dups[:5])}")
    res["features"] = []
    for f in feats:
        vals_by_q = {q: [num(r[f]) for r, _ in g] for q, g in groups.items()}
        const = sum(1 for v in vals_by_q.values() if len(set(v)) == 1) / len(groups)
        nd_up, nd_down = [], []
        for q, g in groups.items():
            docs = [(lab, num(r[f]) or 0.0) for r, lab in g]
            x = ndcg(rank_by(docs), a.k)
            if x is None:
                continue
            nd_up.append(x)
            nd_down.append(ndcg(rank_by([(lab, -s) for lab, s in docs]), a.k))
        up = sum(nd_up) / len(nd_up) if nd_up else None
        down = sum(nd_down) / len(nd_down) if nd_down else None
        d = {"feature": f, "ndcg_higher_better": up, "ndcg_lower_better": down, "constant_within_query": const}
        res["features"].append(d)
        best = max(x for x in (up, down) if x is not None) if nd_up else None
        if best is not None and best >= 0.98:
            res["blocking"].append(f"{f} alone ranks queries almost perfectly (NDCG@{a.k} {best:.3f}): check for label "
                                   "leakage (clicks or judgements derived from the label)")
        if const >= 0.95:
            res["warnings"].append(f"{f} is constant within {const:.0%} of queries: a query-level feature (useful only "
                                   "through interactions with document features)")
    rnd = []
    for q, g in groups.items():
        labs = [lab for _, lab in g]
        x = ndcg(sorted(labs), a.k)                          # worst ordering as a floor
        if x is not None:
            rnd.append(x)
    res["worst_order_ndcg"] = sum(rnd) / len(rnd) if rnd else None
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"queries {res['queries']}   docs per query: min {sizes[0]}, median {res['docs_per_query']['median']}, "
              f"max {sizes[-1]}   singleton queries: {len(singles)}")
        print(f"labels: {res['label_dist']}   queries without relevant docs (label >= {a.rel_min:g}): {len(norel)}")
        print(f"groups contiguous: {'yes' if order_ok else 'NO'}")
        print("")
        print(f"single-feature baselines (NDCG@{a.k}; worst possible ordering averages {res['worst_order_ndcg']:.3f}):")
        print(f"  {'feature':<20} {'higher=better':>14} {'lower=better':>13} {'const in query':>15}")
        for d in sorted(res["features"], key=lambda d: -max(d["ndcg_higher_better"] or 0, d["ndcg_lower_better"] or 0)):
            print(f"  {d['feature']:<20} {d['ndcg_higher_better'] or 0:>14.4f} {d['ndcg_lower_better'] or 0:>13.4f} "
                  f"{d['constant_within_query']:>15.0%}")
        print("")
        for b in res["blocking"]:
            print(f"BLOCKING: {b}")
        for w in res["warnings"]:
            print(f"WARNING: {w}")
        if not res["blocking"] and not res["warnings"]:
            print("no issues found")
    return 1 if res["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
