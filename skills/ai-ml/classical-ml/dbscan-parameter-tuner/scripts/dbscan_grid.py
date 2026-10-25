#!/usr/bin/env python3
"""Grid-search DBSCAN's eps x min_samples and show where the clustering is stable and sensible.

Pure-Python DBSCAN (exact Euclidean neighbourhoods from one sorted distance table, reused for every
grid point) on standardised numeric columns. For each (eps, min_samples):
  clusters        number of clusters (noise excluded)
  noise           share of points labelled noise (-1)
  largest         share of points in the biggest cluster (near 1.0 = everything merged)
  silhouette      mean silhouette of non-noise points on a sample (needs >= 2 clusters)
  ari_vs_labels   agreement with a reference label column (--labels), if given (noise as its own label)
Then recommends the setting inside the most stable region: the cluster count must repeat in at least
two neighbouring grid cells, noise must lie between --noise-min and --noise-max and no cluster may
hold > 90% of points; ties go to the highest silhouette.

eps values default to multiples of the k-distance knee (see kdist.py) unless --eps is given.

Usage:
    python dbscan_grid.py data.csv --drop id --eps 0.3 0.4 0.5 0.6 0.8 --min-samples 4 6 10
    python dbscan_grid.py data.csv --drop true_cluster --labels true_cluster
    python dbscan_grid.py data.csv --json

Exit codes: 0 recommendation found, 1 no setting meets the noise/cluster constraints, 2 usage error.
"""

import argparse
import bisect
import csv
import json
import math
import random
import sys
from collections import Counter, deque


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def dbscan(order, dists, eps, m):
    """order[i]: neighbour indices sorted by distance; dists[i]: matching sorted distances (self included)."""
    n = len(order)
    nb = [order[i][:bisect.bisect_right(dists[i], eps)] for i in range(n)]
    core = [len(x) >= m for x in nb]
    labels = [-1] * n
    c = 0
    for i in range(n):
        if labels[i] != -1 or not core[i]:
            continue
        labels[i] = c
        dq = deque([i])
        while dq:
            p = dq.popleft()
            if not core[p]:
                continue
            for q in nb[p]:
                if labels[q] == -1:
                    labels[q] = c
                    if core[q]:
                        dq.append(q)
        c += 1
    return labels, c


def ari(a, b):
    n = len(a)
    comb = lambda x: x * (x - 1) / 2
    s = sum(comb(v) for v in Counter(zip(a, b)).values())
    sa = sum(comb(v) for v in Counter(a).values())
    sb = sum(comb(v) for v in Counter(b).values())
    e = sa * sb / comb(n)
    mx = (sa + sb) / 2
    return 1.0 if mx == e else (s - e) / (mx - e)


def silhouette(D, labels, idx):
    vals = []
    ks = sorted(set(l for l in labels if l != -1))
    if len(ks) < 2:
        return None
    for i in idx:
        if labels[i] == -1:
            continue
        tot = {k: [0.0, 0] for k in ks}
        for j, l in enumerate(labels):
            if l != -1 and j != i:
                tot[l][0] += D[i][j]
                tot[l][1] += 1
        own = tot[labels[i]]
        if own[1] == 0:
            continue
        a = own[0] / own[1]
        b = min(t[0] / t[1] for k, t in tot.items() if k != labels[i] and t[1])
        vals.append((b - a) / max(a, b) if max(a, b) else 0.0)
    return sum(vals) / len(vals) if vals else None


def main():
    ap = argparse.ArgumentParser(description="Grid-search DBSCAN parameters.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--labels", help="reference label column for ARI (excluded from features)")
    ap.add_argument("--eps", nargs="*", type=float)
    ap.add_argument("--min-samples", nargs="*", type=int)
    ap.add_argument("--noise-min", type=float, default=0.0)
    ap.add_argument("--noise-max", type=float, default=0.2)
    ap.add_argument("--no-scale", action="store_true")
    ap.add_argument("--max-rows", type=int, default=1500)
    ap.add_argument("--sample", type=int, default=300, help="points for silhouette")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            header = rd.fieldnames or []
            rows = list(rd)
        if a.labels and a.labels not in header:
            raise ValueError(f"label column {a.labels!r} not found")
        drop = set(a.drop) | ({a.labels} if a.labels else set())
        cols = a.columns or [c for c in header if c not in drop and all(num(r[c]) is not None for r in rows if (r[c] or "").strip())]
        data = [([num(r[c]) for c in cols], r.get(a.labels) if a.labels else None) for r in rows]
        data = [(x, l) for x, l in data if all(v is not None for v in x)]
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not cols or len(data) < 20:
        print("error: need >= 20 complete numeric rows", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    if len(data) > a.max_rows:
        data = rng.sample(data, a.max_rows)
    X = [x for x, _ in data]
    ref = [l for _, l in data]
    d = len(cols)
    if not a.no_scale:
        mu = [sum(x[j] for x in X) / len(X) for j in range(d)]
        sd = [math.sqrt(sum((x[j] - mu[j]) ** 2 for x in X) / len(X)) or 1.0 for j in range(d)]
        X = [[(x[j] - mu[j]) / sd[j] for j in range(d)] for x in X]
    n = len(X)
    D = [[math.sqrt(sum((p - q) ** 2 for p, q in zip(X[i], X[j]))) for j in range(n)] for i in range(n)]
    order = [sorted(range(n), key=D[i].__getitem__) for i in range(n)]
    dists = [[D[i][j] for j in order[i]] for i in range(n)]
    ms_list = a.min_samples or sorted({max(3, d), max(4, 2 * d), max(6, 4 * d)})
    if a.eps:
        eps_list = sorted(a.eps)
    else:
        kd = sorted(dists[i][min(n - 1, max(ms_list) - 1)] for i in range(n))
        base = kd[int(0.9 * (n - 1))]
        eps_list = [round(base * f, 4) for f in (0.4, 0.55, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0)]
    sidx = rng.sample(range(n), min(a.sample, n))
    grid = []
    for m in ms_list:
        for e in eps_list:
            labels, k = dbscan(order, dists, e, m)
            cnt = Counter(labels)
            noise = cnt.get(-1, 0) / n
            largest = max((v for l, v in cnt.items() if l != -1), default=0) / n
            cell = {"eps": e, "min_samples": m, "clusters": k, "noise": noise, "largest": largest,
                    "silhouette": silhouette(D, labels, sidx) if 2 <= k <= 50 else None}
            if a.labels:
                cell["ari_vs_labels"] = ari(labels, ref)
            grid.append(cell)
    # stability: how many neighbouring cells (same min_samples, adjacent eps; same eps, adjacent min_samples) share k
    key = {(c["min_samples"], c["eps"]): c for c in grid}
    for c in grid:
        i, j = ms_list.index(c["min_samples"]), eps_list.index(c["eps"])
        neigh = [(ms_list[i + di], eps_list[j + dj]) for di, dj in ((0, -1), (0, 1), (-1, 0), (1, 0))
                 if 0 <= i + di < len(ms_list) and 0 <= j + dj < len(eps_list)]
        c["stable_neighbours"] = sum(1 for nkey in neigh if key[nkey]["clusters"] == c["clusters"])
    ok = [c for c in grid if c["clusters"] >= 2 and a.noise_min <= c["noise"] <= a.noise_max and c["largest"] < 0.9
          and c["stable_neighbours"] >= 2]     # a cluster count no neighbouring setting reproduces is an accident
    best = max(ok, key=lambda c: (c["stable_neighbours"], c["silhouette"] or -1)) if ok else None
    out = {"rows": n, "columns": cols, "eps": eps_list, "min_samples": ms_list, "grid": grid, "recommended": best}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0 if best else 1
    print(f"{n} rows x {d} columns ({'raw' if a.no_scale else 'standardised'})")
    head = f"{'min_s':>5} {'eps':>8} {'clusters':>8} {'noise':>7} {'largest':>8} {'silh':>6} {'stable':>6}"
    if a.labels:
        head += f" {'ARI':>6}"
    print(head)
    for c in grid:
        s = "-" if c["silhouette"] is None else f"{c['silhouette']:.3f}"
        line = (f"{c['min_samples']:>5} {c['eps']:>8.4g} {c['clusters']:>8} {c['noise']:>7.1%} {c['largest']:>8.1%} "
                f"{s:>6} {c['stable_neighbours']:>6}")
        if a.labels:
            line += f" {c['ari_vs_labels']:>6.3f}"
        print(line + ("  <- recommended" if c is best else ""))
    if best:
        print(f"\nRECOMMENDED: DBSCAN(eps={best['eps']:g}, min_samples={best['min_samples']}) -> {best['clusters']} clusters, "
              f"{best['noise']:.1%} noise (cluster count stable in {best['stable_neighbours']} neighbouring settings)")
        return 0
    print(f"\nNo stable setting: none gives >= 2 clusters with noise in [{a.noise_min:.0%}, {a.noise_max:.0%}], no single "
          "cluster > 90% and the same cluster count in >= 2 neighbouring settings. The data may have no density "
          "clusters, or densities vary: try HDBSCAN, or reconsider features/scaling.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
