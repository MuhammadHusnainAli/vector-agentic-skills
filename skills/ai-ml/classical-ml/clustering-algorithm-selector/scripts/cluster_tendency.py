#!/usr/bin/env python3
"""Test whether numeric data has cluster structure at all before choosing a clustering algorithm.

Computes on standardised numeric columns (z-scores; --no-scale to skip):
  Hopkins statistic  H = sum(u) / (sum(u) + sum(w)), u = distance from uniform random points (in the
                     data's bounding box) to the nearest data point, w = distance from sampled data
                     points to their nearest other data point. H ~ 0.5: random / no structure;
                     H > 0.75: clustered; H < 0.3: regularly spaced. Averaged over --repeats runs.
  nearest-neighbour distance profile: coefficient of variation and the share of points whose
                     nearest-neighbour distance is > 3x the median (isolated points / noise)
  correlation check  column pairs with |r| > 0.7; strongly correlated features (points on a
                     low-dimensional manifold) also push H toward 1 without any clusters, so H is
                     reported with that caveat - re-run on a few principal components or uncorrelated
                     features to confirm
These are hints, not proof: clustering will always return clusters, this says whether they are likely
to mean anything.

Usage:
    python cluster_tendency.py data.csv --drop id label
    python cluster_tendency.py data.csv --columns x1 x2 x3 --sample 300 --repeats 10
    python cluster_tendency.py data.csv --json

Exit codes: 0 clustered (H > 0.7), 1 no clear structure, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import random
import sys


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def load(path, columns, drop):
    with (sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")) as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    cols = columns or [c for c in header if c not in drop and all(num(r[c]) is not None for r in rows if (r[c] or "").strip())]
    missing = [c for c in cols if c not in header]
    if missing:
        raise ValueError(f"columns not found: {missing}")
    data = []
    for r in rows:
        x = [num(r[c]) for c in cols]
        if all(v is not None for v in x):
            data.append(x)
    return cols, data


def standardise(data):
    d = len(data[0])
    means = [sum(r[j] for r in data) / len(data) for j in range(d)]
    sds = [math.sqrt(sum((r[j] - means[j]) ** 2 for r in data) / len(data)) or 1.0 for j in range(d)]
    return [[(r[j] - means[j]) / sds[j] for j in range(d)] for r in data]


def nn_dist(p, data, skip=None):
    best = float("inf")
    for i, q in enumerate(data):
        if i == skip:
            continue
        s = sum((a - b) ** 2 for a, b in zip(p, q))
        if s < best:
            best = s
    return math.sqrt(best)


def hopkins(data, m, rng, power=1):
    d = len(data[0])
    lo = [min(r[j] for r in data) for j in range(d)]
    hi = [max(r[j] for r in data) for j in range(d)]
    idx = rng.sample(range(len(data)), m)
    w = [nn_dist(data[i], data, skip=i) for i in idx]
    u = [nn_dist([rng.uniform(lo[j], hi[j]) for j in range(d)], data) for _ in range(m)]
    # power=1: original Hopkins; power=d: the dimension-adjusted form (sharper, but more sensitive to correlation)
    su, sw = sum(x ** power for x in u), sum(x ** power for x in w)
    return su / (su + sw)


def correlated_pairs(X, cols, cut=0.7):
    """Pairs of standardised columns with |correlation| > cut."""
    n, d = len(X), len(X[0])
    out = []
    for i in range(d):
        for j in range(i + 1, d):
            r = sum(row[i] * row[j] for row in X) / n
            if abs(r) > cut:
                out.append((cols[i], cols[j], round(r, 2)))
    return out


def main():
    ap = argparse.ArgumentParser(description="Cluster tendency (Hopkins statistic and friends).", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--sample", type=int, default=0, help="points per Hopkins run (default: 10%% of rows, 20..200)")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--max-rows", type=int, default=3000, help="random subsample cap for O(n^2) steps")
    ap.add_argument("--no-scale", action="store_true")
    ap.add_argument("--power", choices=["1", "d"], default="1", help="distance power: 1 (classic) or d (dimension)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        cols, data = load(a.csv, a.columns, set(a.drop))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(data) < 20 or not cols:
        print("error: need >= 20 complete numeric rows", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    if len(data) > a.max_rows:
        data = rng.sample(data, a.max_rows)
    X = data if a.no_scale else standardise(data)
    m = a.sample or max(20, min(200, len(X) // 10))
    pw = 1 if a.power == "1" else len(cols)
    hs = [hopkins(X, m, rng, pw) for _ in range(a.repeats)]
    H = sum(hs) / len(hs)
    nn = sorted(nn_dist(p, X, skip=i) for i, p in enumerate(X))
    med = nn[len(nn) // 2]
    mean_nn = sum(nn) / len(nn)
    cv = math.sqrt(sum((x - mean_nn) ** 2 for x in nn) / len(nn)) / mean_nn if mean_nn else 0.0
    isolated = sum(1 for x in nn if med and x > 3 * med) / len(nn)
    pairs = correlated_pairs(X if not a.no_scale else standardise(X), cols)
    verdict = ("clustered" if H > 0.75 else "weakly clustered" if H > 0.6 else
               "no clear structure (close to random)" if H > 0.3 else "regularly spaced (anti-clustered)")
    out = {"rows": len(X), "columns": cols, "hopkins": round(H, 4), "hopkins_runs": [round(h, 4) for h in hs],
           "verdict": verdict, "nn_distance_cv": round(cv, 3), "isolated_share": round(isolated, 4),
           "correlated_pairs": pairs}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0 if H > 0.7 else 1
    print(f"{len(X)} rows x {len(cols)} columns ({'raw' if a.no_scale else 'standardised'}); Hopkins sample {m} x {a.repeats}")
    print(f"Hopkins H = {H:.3f}  (runs {min(hs):.3f}..{max(hs):.3f}) -> {verdict}")
    print(f"nearest-neighbour distance CV {cv:.2f}; {isolated:.1%} of points are isolated (> 3x median NN distance)"
          + (" -> density-based methods (DBSCAN/HDBSCAN) can label them as noise" if isolated > 0.02 else ""))
    if pairs:
        print(f"{len(pairs)} column pair(s) with |r| > 0.7 (e.g. {pairs[0][0]}~{pairs[0][1]} r={pairs[0][2]}): correlated "
              "features alone push H toward 1; confirm on a few principal components or decorrelated features")
    if H <= 0.6:
        print("Clusters found on this data are likely arbitrary partitions; consider segmentation by business rules "
              "or different features.")
    return 0 if H > 0.7 else 1


if __name__ == "__main__":
    sys.exit(main())
