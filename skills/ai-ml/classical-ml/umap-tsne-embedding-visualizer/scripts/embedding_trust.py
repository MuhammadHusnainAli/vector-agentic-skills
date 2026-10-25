#!/usr/bin/env python3
"""Measure how faithfully a 2-D/3-D embedding (UMAP, t-SNE, PCA) represents the original data.

Inputs: the high-dimensional CSV and the embedding CSV, same rows in the same order. Metrics:
  trustworthiness (Venna & Kaski)  are the embedding's k nearest neighbours also near in the original
                                   space? 1.0 = no false neighbours (sklearn.manifold.trustworthiness)
  continuity                       are original neighbours kept as neighbours? 1.0 = none torn apart
  kNN preservation                 mean share of the k original neighbours found among the k embedding
                                   neighbours
  distance correlation             Spearman correlation of pairwise distances (sampled pairs): global
                                   structure; t-SNE and UMAP typically score low here by design
  label checks (--label)           k-NN classification accuracy (leave-one-out, majority of k) in the
                                   original space vs in the embedding: a big gain in 2-D means the map
                                   exaggerates separation; a big loss means it hides it
Original features are standardised (--no-scale to skip).

Usage:
    python embedding_trust.py --high emb_high.csv --low emb_2d.csv --drop label --label label
    python embedding_trust.py --high X.csv --low umap.csv --k 15 --max-rows 1000 --json

Exit codes: 0 computed, 2 usage error (row counts differ, no numeric columns).
"""

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def read(path, drop, label):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    cols = [c for c in header if c not in drop and c != label and all(num(r[c]) is not None for r in rows)]
    return [[num(r[c]) for c in cols] for r in rows], ([r[label] for r in rows] if label and label in header else None), cols


def standardise(X):
    d = len(X[0])
    mu = [sum(x[j] for x in X) / len(X) for j in range(d)]
    sd = [math.sqrt(sum((x[j] - mu[j]) ** 2 for x in X) / len(X)) or 1.0 for j in range(d)]
    return [[(x[j] - mu[j]) / sd[j] for j in range(d)] for x in X]


def dist_matrix(X):
    return [[math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q))) for q in X] for p in X]


def rank_rows(D):
    """rank[i][j] = rank of j among i's neighbours (1 = nearest, self excluded)."""
    n = len(D)
    ranks = []
    for i in range(n):
        order = sorted((j for j in range(n) if j != i), key=D[i].__getitem__)
        r = [0] * n
        for pos, j in enumerate(order, 1):
            r[j] = pos
        ranks.append(r)
    return ranks


def trust(rank_ref, rank_emb, k):
    """Venna-Kaski: penalise points in the emb k-NN that are far in the reference space."""
    n = len(rank_ref)
    pen = 0
    for i in range(n):
        for j in range(n):
            if j != i and rank_emb[i][j] <= k and rank_ref[i][j] > k:
                pen += rank_ref[i][j] - k
    return 1 - 2 / (n * k * (2 * n - 3 * k - 1)) * pen


def spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=v.__getitem__)
        r = [0.0] * len(v)
        for p, i in enumerate(o):
            r[i] = p
        return r
    ra, rb = rk(a), rk(b)
    m = (len(a) - 1) / 2
    cov = sum((x - m) * (y - m) for x, y in zip(ra, rb))
    var = sum((x - m) ** 2 for x in ra)
    return cov / var if var else 0.0


def knn_accuracy(rank, labels, k):
    n = len(rank)
    ok = 0
    for i in range(n):
        neigh = [j for j in range(n) if j != i and rank[i][j] <= k]
        vote = Counter(labels[j] for j in neigh).most_common(1)[0][0]
        ok += vote == labels[i]
    return ok / n


def main():
    ap = argparse.ArgumentParser(description="Trustworthiness and neighbourhood checks for embeddings.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--high", required=True)
    ap.add_argument("--low", required=True)
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--label", help="label column (in either file) for k-NN accuracy checks")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--max-rows", type=int, default=800)
    ap.add_argument("--no-scale", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        Xh, lab_h, ch = read(a.high, set(a.drop), a.label)
        Xl, lab_l, cl = read(a.low, set(a.drop), a.label)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(Xh) != len(Xl) or not ch or not cl:
        print(f"error: row counts differ ({len(Xh)} vs {len(Xl)}) or no numeric columns", file=sys.stderr)
        return 2
    labels = lab_h or lab_l
    n = len(Xh)
    idx = list(range(n))
    if n > a.max_rows:
        idx = sorted(random.Random(a.seed).sample(idx, a.max_rows))
    Xh = [Xh[i] for i in idx]
    Xl = [Xl[i] for i in idx]
    labels = [labels[i] for i in idx] if labels else None
    if not a.no_scale:
        Xh = standardise(Xh)
    k = min(a.k, len(Xh) // 4)
    Dh, Dl = dist_matrix(Xh), dist_matrix(Xl)
    Rh, Rl = rank_rows(Dh), rank_rows(Dl)
    t = trust(Rh, Rl, k)
    c = trust(Rl, Rh, k)
    keep = sum(sum(1 for j in range(len(Xh)) if j != i and Rh[i][j] <= k and Rl[i][j] <= k) / k
               for i in range(len(Xh))) / len(Xh)
    rng = random.Random(a.seed)
    pairs = [(rng.randrange(len(Xh)), rng.randrange(len(Xh))) for _ in range(min(20000, len(Xh) ** 2))]
    pairs = [(i, j) for i, j in pairs if i != j]
    dc = spearman([Dh[i][j] for i, j in pairs], [Dl[i][j] for i, j in pairs])
    out = {"rows": len(Xh), "high_dims": len(ch), "low_dims": len(cl), "k": k, "trustworthiness": t,
           "continuity": c, "knn_preservation": keep, "distance_spearman": dc}
    if labels:
        out["knn_accuracy_high"] = knn_accuracy(Rh, labels, k)
        out["knn_accuracy_low"] = knn_accuracy(Rl, labels, k)
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{len(Xh)} rows: {len(ch)}-D original vs {len(cl)}-D embedding, k = {k}")
    print(f"trustworthiness  {t:.3f}   (false neighbours in the map; > 0.9 good, < 0.8 the map invents closeness)")
    print(f"continuity       {c:.3f}   (original neighbours torn apart; > 0.9 good)")
    print(f"kNN preservation {keep:.3f}   (share of the {k} original neighbours kept)")
    print(f"distance Spearman {dc:.3f}  (global geometry; low values are normal for t-SNE/UMAP - do not read "
          "distances between clusters)")
    if labels:
        hi, lo = out["knn_accuracy_high"], out["knn_accuracy_low"]
        print(f"{k}-NN label accuracy: original {hi:.3f}, embedding {lo:.3f}" + (
            "  <- the map separates labels much more than the data does" if lo - hi > 0.1 else
            "  <- the map hides separation present in the data" if hi - lo > 0.1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
