#!/usr/bin/env python3
"""Item-based collaborative filtering (item-kNN) with shrinkage, producing top-k lists with explanations.

Input: training interactions CSV (user_id,item_id[,rating]).
Signal:
  implicit (default)  every interaction counts 1 (repeats add up with --count-repeats)
  --min-rating R      explicit ratings: only ratings >= R count as positive (weight 1); others are ignored
  --weighted          use the rating / value itself as the weight (mean-centred per user for explicit data)
Similarity between items i and j (over users):
  cosine            dot(i, j) / (|i| |j|)
  jaccard           |users(i) & users(j)| / |users(i) | users(j)|
  asymmetric        dot(i, j) / (|i|^(2*alpha) |j|^(2*(1-alpha))) with --alpha (0.5 = cosine), which
                    favours or penalises popular neighbours
then shrunk towards 0 for item pairs with few common users: sim * n / (n + --shrink).
Each item keeps its --neighbors most similar items. A user's score for an unseen item is the sum of the
similarities to the items they interacted with (weighted); the item contributing most is the explanation
("because you liked ...").

Output: CSV user_id,item_id,rank,score,because (the rec_eval.py format), --k items per user, seen items
excluded. Users with no positive history get the most popular items (marked "popular").

Usage:
    python itemknn.py train.csv --k 10 -o recs.csv
    python itemknn.py ratings_train.csv --min-rating 4 --similarity cosine --shrink 10 --neighbors 50 -o recs.csv
    python itemknn.py events.csv --user-col visitor --item-col product --similarity asymmetric --alpha 0.7

Exit codes: 0 written, 2 usage or read error.
"""

import argparse
import csv
import heapq
import math
import sys
from collections import Counter, defaultdict


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def build(rows, a):
    users = defaultdict(dict)
    for r in rows:
        u, i = r[a.user_col], r[a.item_col]
        if a.min_rating is not None:
            v = num(r.get(a.rating_col))
            if v is None or v < a.min_rating:
                continue
            w = 1.0
        elif a.weighted:
            w = num(r.get(a.rating_col)) or 1.0
        else:
            w = 1.0
        if a.count_repeats or a.weighted:
            users[u][i] = users[u].get(i, 0.0) + w if a.count_repeats else w
        else:
            users[u][i] = 1.0
    if a.weighted and a.min_rating is None and a.center:
        for u, d in users.items():
            m = sum(d.values()) / len(d)
            for i in d:
                d[i] -= m
    return users


def similarities(users, a):
    items = defaultdict(dict)
    for u, d in users.items():
        for i, w in d.items():
            items[i][u] = w
    norm = {i: math.sqrt(sum(w * w for w in d.values())) for i, d in items.items()}
    count = {i: len(d) for i, d in items.items()}
    dot = defaultdict(float)
    common = defaultdict(int)
    for u, d in users.items():
        lst = list(d.items())
        for x in range(len(lst)):
            i, wi = lst[x]
            for y in range(x + 1, len(lst)):
                j, wj = lst[y]
                key = (i, j) if i < j else (j, i)
                dot[key] += wi * wj
                common[key] += 1
    neigh = defaultdict(list)
    for (i, j), d in dot.items():
        n = common[(i, j)]
        if a.similarity == "jaccard":
            s = n / (count[i] + count[j] - n)
            sij = sji = s
        elif a.similarity == "asymmetric":
            sij = d / ((norm[i] ** (2 * a.alpha)) * (norm[j] ** (2 * (1 - a.alpha))) or 1.0)
            sji = d / ((norm[j] ** (2 * a.alpha)) * (norm[i] ** (2 * (1 - a.alpha))) or 1.0)
        else:
            s = d / (norm[i] * norm[j]) if norm[i] and norm[j] else 0.0
            sij = sji = s
        shrink = n / (n + a.shrink) if a.shrink else 1.0
        neigh[i].append((sij * shrink, j))
        neigh[j].append((sji * shrink, i))
    return {i: heapq.nlargest(a.neighbors, lst) for i, lst in neigh.items()}, items


def recommend(users, neigh, popular, a, all_users):
    out = []
    for u in all_users:
        hist = users.get(u, {})
        scores, because = defaultdict(float), {}
        best_contrib = defaultdict(float)
        for j, w in hist.items():
            for s, i in neigh.get(j, []):
                if i in hist or s <= 0:
                    continue
                c = s * w
                scores[i] += c
                if c > best_contrib[i]:
                    best_contrib[i], because[i] = c, j
        ranked = heapq.nlargest(a.k, scores.items(), key=lambda kv: kv[1])
        seen = set(a.seen.get(u, ())) | set(hist)
        if len(ranked) < a.k:                               # fill with popular unseen items
            have = {i for i, _ in ranked}
            for i in popular:
                if len(ranked) >= a.k:
                    break
                if i not in have and i not in seen:
                    ranked.append((i, 0.0))
                    because[i] = "popular"
        for rank, (i, s) in enumerate(ranked, 1):
            out.append((u, i, rank, round(s, 6), because.get(i, "popular")))
    return out


def main():
    ap = argparse.ArgumentParser(description="Item-kNN collaborative filtering.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("train")
    ap.add_argument("--user-col", default="user_id")
    ap.add_argument("--item-col", default="item_id")
    ap.add_argument("--rating-col", default="rating")
    ap.add_argument("--min-rating", type=float)
    ap.add_argument("--weighted", action="store_true")
    ap.add_argument("--no-center", dest="center", action="store_false", help="do not mean-centre --weighted ratings")
    ap.add_argument("--count-repeats", action="store_true")
    ap.add_argument("--similarity", choices=["cosine", "jaccard", "asymmetric"], default="cosine")
    ap.add_argument("--alpha", type=float, default=0.5)
    ap.add_argument("--shrink", type=float, default=10.0)
    ap.add_argument("--neighbors", type=int, default=50)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--users", help="CSV with a user_id column: only recommend for these users")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()
    try:
        with open(a.train, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        for c in (a.user_col, a.item_col):
            if c not in rows[0]:
                raise ValueError(f"column {c!r} not found (have: {', '.join(rows[0])})")
        if (a.min_rating is not None or a.weighted) and a.rating_col not in rows[0]:
            raise ValueError(f"rating column {a.rating_col!r} not found")
        target = None
        if a.users:
            with open(a.users, newline="", encoding="utf-8") as f:
                target = sorted({r[a.user_col] for r in csv.DictReader(f)})
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    a.seen = defaultdict(set)
    for r in rows:
        a.seen[r[a.user_col]].add(r[a.item_col])
    users = build(rows, a)
    neigh, items = similarities(users, a)
    popular = [i for i, _ in Counter(r[a.item_col] for r in rows).most_common()]
    all_users = target or sorted(a.seen)
    recs = recommend(users, neigh, popular, a, all_users)
    f = open(a.output, "w", newline="", encoding="utf-8") if a.output else sys.stdout
    w = csv.writer(f)
    w.writerow(["user_id", "item_id", "rank", "score", "because"])
    w.writerows(recs)
    if a.output:
        f.close()
        n_pop = sum(1 for r in recs if r[4] == "popular")
        print(f"wrote {a.output}: {len(all_users)} users x {a.k}, {len(neigh)} items with neighbours, "
              f"{n_pop} popularity fill-ins", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
