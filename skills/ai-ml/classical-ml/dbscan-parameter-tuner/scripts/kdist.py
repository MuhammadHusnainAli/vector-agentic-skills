#!/usr/bin/env python3
"""Suggest DBSCAN's eps from the k-distance curve (distance to the k-th nearest neighbour).

For min_samples m, a core point needs m points (itself included) within eps, so the relevant curve
is the distance to the (m-1)-th nearest other point, sorted ascending. Points inside clusters have
small k-distances; noise has large ones; the knee of the curve is the classic eps choice (Ester et
al. 1996). Reports:
  - quantiles of the k-distance
  - the knee (kneedle on the sorted curve) as the suggested eps, and a bracket
    [p(1 - noise_hi), p(1 - noise_lo)] that would label roughly 2-15%% of points as noise
  - a coarse ASCII plot of the sorted curve
Defaults: min_samples = 2 x dimensions (Sander et al. 1998 heuristic), standardised features.

Usage:
    python kdist.py data.csv --drop id label
    python kdist.py data.csv --min-samples 10 --columns x y --no-scale
    python kdist.py data.csv --json

Exit codes: 0 printed, 2 usage or read error.
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


def load(path, columns, drop, scale, max_rows, seed):
    with (sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")) as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    cols = columns or [c for c in header if c not in drop and all(num(r[c]) is not None for r in rows if (r[c] or "").strip())]
    X = [[num(r[c]) for c in cols] for r in rows]
    X = [x for x in X if all(v is not None for v in x)]
    if len(X) > max_rows:
        X = random.Random(seed).sample(X, max_rows)
    if scale and X:
        d = len(cols)
        mu = [sum(x[j] for x in X) / len(X) for j in range(d)]
        sd = [math.sqrt(sum((x[j] - mu[j]) ** 2 for x in X) / len(X)) or 1.0 for j in range(d)]
        X = [[(x[j] - mu[j]) / sd[j] for j in range(d)] for x in X]
    return cols, X


def kth_distances(X, k):
    out = []
    for i, p in enumerate(X):
        ds = sorted(sum((a - b) ** 2 for a, b in zip(p, q)) for j, q in enumerate(X) if j != i)
        out.append(math.sqrt(ds[k - 1]))
    return sorted(out)


def knee(ys):
    """Kneedle for an increasing convex curve: max distance above... below the chord after normalisation."""
    n = len(ys)
    y0, y1 = ys[0], ys[-1]
    if y1 == y0:
        return n - 1
    best, idx = -1.0, n - 1
    for i, y in enumerate(ys):
        xn = i / (n - 1)
        yn = (y - y0) / (y1 - y0)
        d = xn - yn                      # convex increasing: curve lies below the chord
        if d > best:
            best, idx = d, i
    return idx


def q(ys, p):
    return ys[min(len(ys) - 1, max(0, int(round(p * (len(ys) - 1)))))]


def main():
    ap = argparse.ArgumentParser(description="DBSCAN eps from the k-distance curve.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--min-samples", type=int, help="DBSCAN min_samples (default 2 x dims, at least 4)")
    ap.add_argument("--no-scale", action="store_true")
    ap.add_argument("--max-rows", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        cols, X = load(a.csv, a.columns, set(a.drop), not a.no_scale, a.max_rows, a.seed)
    except (OSError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not cols or len(X) < 20:
        print("error: need >= 20 complete numeric rows", file=sys.stderr)
        return 2
    m = a.min_samples or max(4, 2 * len(cols))
    if m >= len(X):
        print("error: min_samples must be smaller than the number of rows", file=sys.stderr)
        return 2
    kd = kth_distances(X, m - 1)
    ki = knee(kd)
    eps = kd[ki]
    bracket = (q(kd, 0.85), q(kd, 0.98))
    noise_at_knee = sum(1 for d in kd if d > eps) / len(kd)
    out = {"rows": len(X), "columns": cols, "min_samples": m, "k": m - 1,
           "quantiles": {p: round(q(kd, p), 4) for p in (0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)},
           "knee_index": ki, "eps_knee": round(eps, 4), "noise_share_at_knee": round(noise_at_knee, 4),
           "eps_bracket_2_to_15pct_noise": [round(bracket[0], 4), round(bracket[1], 4)]}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{len(X)} rows x {len(cols)} columns ({'raw' if a.no_scale else 'standardised'}); min_samples={m} "
          f"-> distance to the {m - 1}-th nearest neighbour")
    print("quantiles: " + "  ".join(f"p{int(p * 100)}={v:g}" for p, v in out["quantiles"].items()))
    print(f"knee at rank {ki}/{len(kd)}: eps ~ {eps:.4g} (points beyond it: {noise_at_knee:.1%} -> likely noise)")
    print(f"eps for ~15% .. ~2% noise: {bracket[0]:.4g} .. {bracket[1]:.4g}")
    width, height = 60, 10
    cols_ = [kd[int(i * (len(kd) - 1) / (width - 1))] for i in range(width)]
    top = max(cols_) or 1
    for h in range(height, 0, -1):
        level = top * h / height
        print(("|" if h != height else "^") + "".join("*" if v >= level else " " for v in cols_))
    print("+" + "-" * width + "> points sorted by k-distance")
    print("Next: python dbscan_grid.py with eps around the knee and min_samples around "
          f"{max(4, m // 2)}..{m * 2}, then check noise share and cluster stability.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
