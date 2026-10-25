"""Ranking metrics shared by the learning-to-rank scripts (stdlib only).

Each function takes the labels of one query's documents in ranked order (best first).
"""

import math


def dcg(labels, k, gain="exp"):
    g = (lambda r: 2 ** r - 1) if gain == "exp" else (lambda r: r)
    return sum(g(r) / math.log2(i + 2) for i, r in enumerate(labels[:k]))


def ndcg(ranked, k, gain="exp"):
    ideal = dcg(sorted(ranked, reverse=True), k, gain)
    return dcg(ranked, k, gain) / ideal if ideal > 0 else None


def average_precision(ranked, k, rel_min):
    hits, s = 0, 0.0
    n_rel = sum(1 for r in ranked if r >= rel_min)
    if n_rel == 0:
        return None
    for i, r in enumerate(ranked[:k]):
        if r >= rel_min:
            hits += 1
            s += hits / (i + 1)
    return s / min(n_rel, k)


def reciprocal_rank(ranked, rel_min):
    if not any(r >= rel_min for r in ranked):
        return None
    return next(1 / (i + 1) for i, r in enumerate(ranked) if r >= rel_min)


def precision(ranked, k, rel_min):
    if not any(r >= rel_min for r in ranked):
        return None
    return sum(1 for r in ranked[:k] if r >= rel_min) / k


def err(ranked, k, max_label):
    """Expected reciprocal rank (Chapelle et al. 2009) with R = (2^g - 1) / 2^max."""
    p, s = 1.0, 0.0
    for i, r in enumerate(ranked[:k]):
        R = (2 ** r - 1) / (2 ** max_label) if max_label > 0 else 0.0
        s += p * R / (i + 1)
        p *= 1 - R
    return s


def rank_by(docs, ties="pessimistic"):
    """docs: list of (label, score) in input order. Tied scores are ordered worst label first (pessimistic,
    the default: a constant score cannot look good), best label first (optimistic) or in input order
    (input: reproduces LightGBM's own NDCG@k evaluation)."""
    if ties == "input":
        order = sorted(range(len(docs)), key=lambda i: -docs[i][1])        # stable: input order within ties
        return [docs[i][0] for i in order]
    sign = 1 if ties == "pessimistic" else -1
    return [lab for lab, _ in sorted(docs, key=lambda d: (-d[1], sign * d[0]))]
