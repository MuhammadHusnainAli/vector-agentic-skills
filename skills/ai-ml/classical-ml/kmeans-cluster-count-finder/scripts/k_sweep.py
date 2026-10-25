#!/usr/bin/env python3
"""Sweep k for k-means and recommend a cluster count from several criteria that disagree for good reasons.

Pure-Python k-means++ (Lloyd iterations, best of --n-init) on standardised numeric columns, for each k
in --k-min..--k-max:
  inertia             within-cluster sum of squares; the elbow is found with the kneedle method
  silhouette          mean silhouette on a sample of --sample points (higher is better)
  Calinski-Harabasz   between/within dispersion ratio (higher is better)
  Davies-Bouldin      average similarity of each cluster to its closest one (lower is better)
  gap statistic       log(W_k) of --b uniform reference sets minus log(W_k) of the data (Tibshirani 2001);
                      chosen k = smallest k with gap(k) >= gap(k+1) - s(k+1)
  stability           adjusted Rand index between two fits on overlapping 80% subsamples (agreement on
                      shared rows); < 0.6 means that k is not reproducible
Each criterion votes; the report shows the votes, the table and a recommendation, and says when the data
has no clear k: criteria spread over many values, best silhouette < 0.25, an unstable winner, or a gap
statistic below 0.25 for every k (uniform-like data, which k-means still splits into stable pieces).

Usage:
    python k_sweep.py data.csv --drop id label --k-max 10
    python k_sweep.py data.csv --columns x1 x2 x3 --k-min 2 --k-max 8 --b 10 --json
    python k_sweep.py data.csv --no-scale --n-init 10

Exit codes: 0 clear recommendation, 1 no clear k (criteria disagree widely or weak structure), 2 usage error.
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


def d2(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def kmeans(X, k, rng, n_init=5, iters=100):
    best = None
    for _ in range(n_init):
        cents = [X[rng.randrange(len(X))]]
        dist = [d2(x, cents[0]) for x in X]
        while len(cents) < k:                       # k-means++ seeding
            tot = sum(dist)
            r = rng.random() * tot
            acc = 0.0
            for i, w in enumerate(dist):
                acc += w
                if acc >= r:
                    break
            cents.append(X[i])
            dist = [min(dw, d2(x, X[i])) for dw, x in zip(dist, X)]
        labels = [0] * len(X)
        for _ in range(iters):
            changed = False
            for i, x in enumerate(X):
                j = min(range(k), key=lambda c: d2(x, cents[c]))
                if j != labels[i]:
                    labels[i], changed = j, True
            dim = len(X[0])
            sums = [[0.0] * dim for _ in range(k)]
            cnt = [0] * k
            for x, l in zip(X, labels):
                cnt[l] += 1
                for t in range(dim):
                    sums[l][t] += x[t]
            cents = [[s / cnt[c] for s in sums[c]] if cnt[c] else X[rng.randrange(len(X))] for c in range(k)]
            if not changed:
                break
        inertia = sum(d2(x, cents[l]) for x, l in zip(X, labels))
        if best is None or inertia < best[0]:
            best = (inertia, labels, cents)
    return best


def silhouette(X, labels, k, idx):
    s = []
    for i in idx:
        own = labels[i]
        dsum = [0.0] * k
        cnt = [0] * k
        for j, x in enumerate(X):
            if j != i:
                dsum[labels[j]] += math.sqrt(d2(X[i], x))
                cnt[labels[j]] += 1
        if cnt[own] == 0:
            s.append(0.0)
            continue
        a = dsum[own] / cnt[own]
        b = min(dsum[c] / cnt[c] for c in range(k) if c != own and cnt[c])
        s.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return sum(s) / len(s)


def ch_db(X, labels, cents, k):
    n, dim = len(X), len(X[0])
    mean = [sum(x[t] for x in X) / n for t in range(dim)]
    cnt = Counter(labels)
    W = sum(d2(x, cents[l]) for x, l in zip(X, labels))
    B = sum(cnt[c] * d2(cents[c], mean) for c in range(k))
    ch = (B / (k - 1)) / (W / (n - k)) if W > 0 and k > 1 else 0.0
    scat = [0.0] * k
    for x, l in zip(X, labels):
        scat[l] += math.sqrt(d2(x, cents[l]))
    scat = [scat[c] / cnt[c] if cnt[c] else 0.0 for c in range(k)]
    db = 0.0
    for i in range(k):
        db += max((scat[i] + scat[j]) / (math.sqrt(d2(cents[i], cents[j])) or 1e-12) for j in range(k) if j != i)
    return ch, db / k


def ari(a, b):
    n = len(a)
    cont = Counter(zip(a, b))
    comb = lambda x: x * (x - 1) / 2
    sum_ij = sum(comb(v) for v in cont.values())
    sa = sum(comb(v) for v in Counter(a).values())
    sb = sum(comb(v) for v in Counter(b).values())
    exp = sa * sb / comb(n) if n > 1 else 0
    mx = (sa + sb) / 2
    return 1.0 if mx == exp else (sum_ij - exp) / (mx - exp)


def kneedle(ks, ys):
    """Elbow of a decreasing convex curve: max distance below the chord."""
    x0, x1, y0, y1 = ks[0], ks[-1], ys[0], ys[-1]
    if y0 == y1:
        return ks[0]
    best, kbest = -1, ks[0]
    for k, y in zip(ks, ys):
        xn, yn = (k - x0) / (x1 - x0), (y - y1) / (y0 - y1)
        d = (1 - xn) - yn                   # chord from (0,1) to (1,0) minus normalised curve
        if d > best:
            best, kbest = d, k
    return kbest


def main():
    ap = argparse.ArgumentParser(description="Recommend k for k-means from several criteria.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--k-min", type=int, default=2)
    ap.add_argument("--k-max", type=int, default=10)
    ap.add_argument("--n-init", type=int, default=5)
    ap.add_argument("--b", type=int, default=5, help="reference datasets for the gap statistic (0 = skip)")
    ap.add_argument("--sample", type=int, default=400, help="points for silhouette")
    ap.add_argument("--max-rows", type=int, default=2000)
    ap.add_argument("--no-scale", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            header = rd.fieldnames or []
            rows = list(rd)
        cols = a.columns or [c for c in header if c not in a.drop and
                             all(num(r[c]) is not None for r in rows if (r[c] or "").strip())]
        X = [[num(r[c]) for c in cols] for r in rows]
        X = [x for x in X if all(v is not None for v in x)]
    except (OSError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not cols or len(X) < max(20, 3 * a.k_max) or a.k_min < 2 or a.k_max <= a.k_min:
        print("error: need numeric columns, >= 3*k_max rows and 2 <= k_min < k_max", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    if len(X) > a.max_rows:
        X = rng.sample(X, a.max_rows)
    if not a.no_scale:
        dim = len(cols)
        mu = [sum(x[t] for x in X) / len(X) for t in range(dim)]
        sd = [math.sqrt(sum((x[t] - mu[t]) ** 2 for x in X) / len(X)) or 1.0 for t in range(dim)]
        X = [[(x[t] - mu[t]) / sd[t] for t in range(dim)] for x in X]
    sidx = rng.sample(range(len(X)), min(a.sample, len(X)))
    ks = list(range(a.k_min, a.k_max + 1))
    res = {}
    lo = [min(x[t] for x in X) for t in range(len(cols))]
    hi = [max(x[t] for x in X) for t in range(len(cols))]
    gap_k = list(range(a.k_min - 1 if a.k_min > 1 else 1, a.k_max + 2))
    gaps = {}
    for k in sorted(set(ks + (gap_k if a.b else []))):
        inertia, labels, cents = kmeans(X, k, rng, a.n_init) if k > 1 else (
            sum(d2(x, [sum(c) / len(X) for c in zip(*X)]) for x in X), [0] * len(X), None)
        if a.b:
            ref = []
            for _ in range(a.b):
                R = [[rng.uniform(lo[t], hi[t]) for t in range(len(cols))] for _ in range(len(X))]
                ref.append(math.log(kmeans(R, k, rng, 2)[0] if k > 1 else sum(d2(r, [sum(c) / len(R) for c in zip(*R)]) for r in R)))
            m = sum(ref) / len(ref)
            sk = math.sqrt(sum((v - m) ** 2 for v in ref) / len(ref)) * math.sqrt(1 + 1 / a.b)
            gaps[k] = (m - math.log(inertia), sk)
        if k in ks:
            sil = silhouette(X, labels, k, sidx)
            ch, db = ch_db(X, labels, cents, k)
            # stability: two 80% subsamples, compare labels on their overlap
            n = len(X)
            i1 = set(rng.sample(range(n), int(0.8 * n)))
            i2 = set(rng.sample(range(n), int(0.8 * n)))
            l1 = dict(zip(sorted(i1), kmeans([X[i] for i in sorted(i1)], k, rng, 2)[1]))
            l2 = dict(zip(sorted(i2), kmeans([X[i] for i in sorted(i2)], k, rng, 2)[1]))
            shared = sorted(i1 & i2)
            stab = ari([l1[i] for i in shared], [l2[i] for i in shared])
            res[k] = {"inertia": inertia, "silhouette": sil, "calinski_harabasz": ch, "davies_bouldin": db,
                      "stability_ari": stab, "sizes": sorted(Counter(labels).values(), reverse=True)}
    votes = {"elbow": kneedle(ks, [res[k]["inertia"] for k in ks]),
             "silhouette": max(ks, key=lambda k: res[k]["silhouette"]),
             "calinski_harabasz": max(ks, key=lambda k: res[k]["calinski_harabasz"]),
             "davies_bouldin": min(ks, key=lambda k: res[k]["davies_bouldin"])}
    if a.b:
        cand = [k for k in ks if k + 1 in gaps and gaps[k][0] >= gaps[k + 1][0] - gaps[k + 1][1]]
        votes["gap"] = cand[0] if cand else ks[-1]
        for k in ks:
            res[k]["gap"], res[k]["gap_sk"] = gaps[k]
    tally = Counter(votes.values())
    top, n_top = tally.most_common(1)[0]
    stable_top = res[top]["stability_ari"] >= 0.6
    weak = res[votes["silhouette"]]["silhouette"] < 0.25
    spread = len(tally) >= 4
    # gap ~ 0 for every k: the data is no more clustered than uniform noise in its bounding box
    no_gap = bool(a.b) and max(res[k]["gap"] for k in ks) < 0.25
    clear = n_top >= 2 and stable_top and not weak and not spread and not no_gap
    out = {"rows": len(X), "columns": cols, "table": res, "votes": votes, "recommended_k": top, "clear": clear}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0 if clear else 1
    print(f"{len(X)} rows x {len(cols)} columns ({'raw' if a.no_scale else 'standardised'}), k-means++ best of {a.n_init}")
    hdr = f"{'k':>3} {'inertia':>11} {'silhouette':>10} {'CH':>9} {'DB':>6} {'stability':>9}"
    if a.b:
        hdr += f" {'gap':>7} {'sk':>6}"
    print(hdr + "  sizes")
    for k in ks:
        r = res[k]
        line = (f"{k:>3} {r['inertia']:>11.1f} {r['silhouette']:>10.3f} {r['calinski_harabasz']:>9.1f} "
                f"{r['davies_bouldin']:>6.3f} {r['stability_ari']:>9.2f}")
        if a.b:
            line += f" {r['gap']:>7.3f} {r['gap_sk']:>6.3f}"
        print(line + f"  {r['sizes'][:8]}")
    print("\nvotes: " + ", ".join(f"{m}={k}" for m, k in votes.items()))
    if clear:
        print(f"RECOMMENDED k = {top} ({n_top} of {len(votes)} criteria; stability ARI {res[top]['stability_ari']:.2f})")
    else:
        why = []
        if weak:
            why.append(f"best silhouette {res[votes['silhouette']]['silhouette']:.2f} < 0.25 (weak structure)")
        if spread:
            why.append("criteria spread over many k")
        if not stable_top:
            why.append(f"k={top} is unstable (ARI {res[top]['stability_ari']:.2f})")
        if n_top < 2:
            why.append("no two criteria agree")
        if no_gap:
            why.append(f"gap statistic <= {max(res[k]['gap'] for k in ks):.2f} for every k: no more structure than uniform "
                       "noise (k-means will still split it into stable but arbitrary pieces)")
        print(f"NO CLEAR k: {'; '.join(why)}. Choose k from the business need (segments you can act on) and check "
              "stability, or reconsider features / algorithm.")
    return 0 if clear else 1


if __name__ == "__main__":
    sys.exit(main())
