#!/usr/bin/env python3
"""Score rows of a numeric CSV with four unsupervised anomaly detectors and a rank-averaged ensemble.

Detectors (standard library only):
  robust_z     max over features of |x - median| / (1.4826 * MAD): one feature far from normal
  mahalanobis  sqrt((x - mu)' S^-1 (x - mu)) with a covariance fitted on the central 90% of rows by robust z
               (resists masking by the outliers themselves): unusual combinations of features
  knn          distance to the k-th nearest neighbour (standardised features): isolated points
  iforest      isolation forest (Liu et al. 2008): average path length over random trees on subsamples
               of 256 rows, score = 2^(-E[h]/c(256)); short paths = easy to isolate = anomalous
  ensemble     mean of the four rank-normalised scores (robust to the detectors' different scales)
For the top rows it shows which features deviate most (robust z per feature).

Fit and score can differ: --train defines "normal" (e.g. last month), --score is scored against it.

Usage:
    python anomaly_scores.py --train sensors.csv --drop reading_id is_anomaly --top 10
    python anomaly_scores.py --train ref.csv --score new.csv --drop id --out scores.csv
    python anomaly_scores.py --train data.csv --columns temperature pressure --k 10 --trees 200 --json

Exit codes: 0 scored, 2 usage or read error.
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


def load(path, cols, drop):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    cols = cols or [c for c in header if c not in drop and all(num(r[c]) is not None for r in rows if (r[c] or "").strip())]
    keep = [r for r in rows if all(num(r.get(c)) is not None for c in cols)]
    return cols, keep, [[num(r[c]) for c in cols] for r in keep]


def median(xs):
    s = sorted(xs)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2


def invert(M):
    n = len(M)
    A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c]))
        if abs(A[p][c]) < 1e-12:
            A[p][c] += 1e-6                     # ridge for singular covariance
        A[c], A[p] = A[p], A[c]
        piv = A[c][c]
        A[c] = [v / piv for v in A[c]]
        for r in range(n):
            if r != c:
                f = A[r][c]
                A[r] = [v - f * w for v, w in zip(A[r], A[c])]
    return [row[n:] for row in A]


def c_factor(n):
    return 2 * (math.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n if n > 2 else (1.0 if n == 2 else 0.0)


def build_tree(X, depth, limit, rng):
    if depth >= limit or len(X) <= 1:
        return ("leaf", len(X))
    d = len(X[0])
    f = rng.randrange(d)
    lo, hi = min(x[f] for x in X), max(x[f] for x in X)
    if lo == hi:
        return ("leaf", len(X))
    t = rng.uniform(lo, hi)
    left = [x for x in X if x[f] < t]
    right = [x for x in X if x[f] >= t]
    return ("node", f, t, build_tree(left, depth + 1, limit, rng), build_tree(right, depth + 1, limit, rng))


def path_len(tree, x, depth=0):
    if tree[0] == "leaf":
        return depth + c_factor(tree[1])
    _, f, t, l, r = tree
    return path_len(l if x[f] < t else r, x, depth + 1)


def ranks01(v):
    order = sorted(range(len(v)), key=v.__getitem__)
    r = [0.0] * len(v)
    for pos, i in enumerate(order):
        r[i] = pos / max(1, len(v) - 1)
    return r


def main():
    ap = argparse.ArgumentParser(description="Unsupervised anomaly scores (robust z, Mahalanobis, kNN, iForest).",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True)
    ap.add_argument("--score")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--trees", type=int, default=100)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--out", help="write all scores to this CSV")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        cols, _, Xtr = load(a.train, a.columns, set(a.drop))
        if a.score:
            _, srows, Xsc = load(a.score, cols, set())
        else:
            with open(a.train, newline="", encoding="utf-8-sig") as fh:
                srows = [r for r in csv.DictReader(fh) if all(num(r.get(c)) is not None for c in cols)]
            Xsc = Xtr
    except (OSError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not cols or len(Xtr) < 20:
        print("error: need >= 20 complete numeric training rows", file=sys.stderr)
        return 2
    d = len(cols)
    rng = random.Random(a.seed)
    med = [median([x[j] for x in Xtr]) for j in range(d)]
    mad = [median([abs(x[j] - med[j]) for x in Xtr]) * 1.4826 or 1e-9 for j in range(d)]
    rz = lambda x: [(x[j] - med[j]) / mad[j] for j in range(d)]
    robust = [max(abs(v) for v in rz(x)) for x in Xsc]
    # covariance from the central 90% (by robust z) to reduce masking
    rz_tr = sorted(range(len(Xtr)), key=lambda i: max(abs(v) for v in rz(Xtr[i])))
    core = [Xtr[i] for i in rz_tr[:max(d + 2, int(0.9 * len(Xtr)))]]
    mu = [sum(x[j] for x in core) / len(core) for j in range(d)]
    S = [[sum((x[i] - mu[i]) * (x[j] - mu[j]) for x in core) / (len(core) - 1) for j in range(d)] for i in range(d)]
    Si = invert(S)
    maha = []
    for x in Xsc:
        dv = [x[j] - mu[j] for j in range(d)]
        maha.append(math.sqrt(max(0.0, sum(dv[i] * Si[i][j] * dv[j] for i in range(d) for j in range(d)))))
    sd = [math.sqrt(S[j][j]) or 1.0 for j in range(d)]
    Ztr = [[(x[j] - mu[j]) / sd[j] for j in range(d)] for x in Xtr]
    Zsc = [[(x[j] - mu[j]) / sd[j] for j in range(d)] for x in Xsc]
    same = a.score is None
    knn = []
    for i, z in enumerate(Zsc):
        ds = sorted(sum((p - q) ** 2 for p, q in zip(z, t)) for jj, t in enumerate(Ztr) if not (same and jj == i))
        knn.append(math.sqrt(ds[min(a.k, len(ds)) - 1]))
    psi = min(256, len(Xtr))
    limit = math.ceil(math.log2(psi))
    trees = [build_tree(rng.sample(Xtr, psi), 0, limit, rng) for _ in range(a.trees)]
    cn = c_factor(psi)
    iforest = [2 ** (-(sum(path_len(t, x) for t in trees) / len(trees)) / cn) for x in Xsc]
    ens = [sum(v) / 4 for v in zip(ranks01(robust), ranks01(maha), ranks01(knn), ranks01(iforest))]
    order = sorted(range(len(Xsc)), key=lambda i: -ens[i])
    top = []
    for i in order[:a.top]:
        dev = sorted(zip(cols, rz(Xsc[i])), key=lambda cv: -abs(cv[1]))[:3]
        top.append({"line": i + 2, "ensemble": round(ens[i], 4), "robust_z": round(robust[i], 2),
                    "mahalanobis": round(maha[i], 2), "knn": round(knn[i], 3), "iforest": round(iforest[i], 3),
                    "deviations": [{"feature": c, "robust_z": round(v, 2)} for c, v in dev]})
    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            keys = list(srows[0].keys()) if srows else []
            w = csv.writer(fh)
            w.writerow(keys + ["score_robust_z", "score_mahalanobis", "score_knn", "score_iforest", "score_ensemble"])
            for r, s1, s2, s3, s4, s5 in zip(srows, robust, maha, knn, iforest, ens):
                w.writerow([r[k] for k in keys] + [round(s1, 4), round(s2, 4), round(s3, 4), round(s4, 4), round(s5, 4)])
    out = {"train_rows": len(Xtr), "scored_rows": len(Xsc), "columns": cols, "top": top}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"Fitted on {len(Xtr)} rows x {d} features; scored {len(Xsc)} rows (k={a.k}, {a.trees} trees, psi={psi})")
    print(f"{'line':>6} {'ensemble':>8} {'robust_z':>8} {'mahal':>7} {'knn':>7} {'iforest':>7}  most deviating features")
    for t in top:
        devs = ", ".join(f"{d_['feature']} {d_['robust_z']:+.1f}" for d_ in t["deviations"])
        print(f"{t['line']:>6} {t['ensemble']:>8.3f} {t['robust_z']:>8.2f} {t['mahalanobis']:>7.2f} {t['knn']:>7.3f} "
              f"{t['iforest']:>7.3f}  {devs}")
    if a.out:
        print(f"\nwrote all scores to {a.out} (evaluate with anomaly_eval.py)")
    print("High Mahalanobis with modest robust z = unusual combination; high robust z = one extreme feature.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
