#!/usr/bin/env python3
"""PCA report for a numeric CSV: how many components to keep, what they mean, and whether scaling is wrong.

Pure Python (Jacobi eigendecomposition of the covariance or correlation matrix; fine up to ~60
columns). Reports:
  explained variance ratio and cumulative share per component
  components needed for --targets (default 80/90/95%)
  Kaiser rule (eigenvalue > 1 on the correlation matrix)
  parallel analysis (Horn 1965): keep components whose eigenvalue beats the --pa-quantile of
                     eigenvalues from --pa-runs column-shuffled copies of the data
  top loadings per component (which original features drive it), signed
  scaling check: with --no-scale, warns when one column holds most of the total variance (PCA then
                     mostly finds that column)
Import note: pca_outliers.py reuses load() and pca() from this file.

Usage:
    python pca_report.py data.csv --drop id label
    python pca_report.py data.csv --columns f1 f2 f3 f4 --top 4 --targets 0.9 0.99
    python pca_report.py data.csv --no-scale --json

Exit codes: 0 report printed, 2 usage or read error.
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


def load(path, columns=None, drop=()):
    with (sys.stdin if path == "-" else open(path, newline="", encoding="utf-8-sig")) as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    cols = columns or [c for c in header if c not in drop and all(num(r[c]) is not None for r in rows if (r[c] or "").strip())]
    missing = [c for c in cols if c not in header]
    if missing:
        raise ValueError(f"columns not found: {missing}")
    X = [[num(r[c]) for c in cols] for r in rows]
    return cols, [x for x in X if all(v is not None for v in x)]


def center_scale(X, scale):
    n, d = len(X), len(X[0])
    mu = [sum(x[j] for x in X) / n for j in range(d)]
    sd = [math.sqrt(sum((x[j] - mu[j]) ** 2 for x in X) / (n - 1)) or 1.0 for j in range(d)]
    Z = [[(x[j] - mu[j]) / (sd[j] if scale else 1.0) for j in range(d)] for x in X]
    return Z, mu, sd


def covariance(Z):
    n, d = len(Z), len(Z[0])
    return [[sum(z[i] * z[j] for z in Z) / (n - 1) for j in range(d)] for i in range(d)]


def jacobi(A, tol=1e-12, max_sweeps=100):
    """Eigenvalues and eigenvectors (columns of V) of a symmetric matrix."""
    d = len(A)
    A = [row[:] for row in A]
    V = [[1.0 if i == j else 0.0 for j in range(d)] for i in range(d)]
    for _ in range(max_sweeps):
        off = sum(A[i][j] ** 2 for i in range(d) for j in range(d) if i != j)
        if off < tol:
            break
        for p in range(d - 1):
            for q in range(p + 1, d):
                if abs(A[p][q]) < 1e-15:
                    continue
                theta = (A[q][q] - A[p][p]) / (2 * A[p][q])
                t = (1 if theta >= 0 else -1) / (abs(theta) + math.sqrt(theta * theta + 1))
                c = 1 / math.sqrt(t * t + 1)
                s = t * c
                for k in range(d):
                    akp, akq = A[k][p], A[k][q]
                    A[k][p], A[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(d):
                    apk, aqk = A[p][k], A[q][k]
                    A[p][k], A[q][k] = c * apk - s * aqk, s * apk + c * aqk
                for k in range(d):
                    vkp, vkq = V[k][p], V[k][q]
                    V[k][p], V[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    vals = [A[i][i] for i in range(d)]
    order = sorted(range(d), key=lambda i: -vals[i])
    comps = []
    for i in order:
        vec = [V[k][i] for k in range(d)]
        j = max(range(d), key=lambda k: abs(vec[k]))       # sign convention: largest loading positive
        if vec[j] < 0:
            vec = [-v for v in vec]
        comps.append(vec)
    return [max(0.0, vals[i]) for i in order], comps


def pca(X, scale=True):
    Z, mu, sd = center_scale(X, scale)
    vals, comps = jacobi(covariance(Z))
    return {"eigenvalues": vals, "components": comps, "mean": mu, "sd": sd, "scaled": scale}


def main():
    ap = argparse.ArgumentParser(description="PCA report with component-count rules and loadings.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--no-scale", action="store_true", help="PCA on the covariance of raw values")
    ap.add_argument("--targets", nargs="*", type=float, default=[0.8, 0.9, 0.95])
    ap.add_argument("--top", type=int, default=3, help="loadings to show per component")
    ap.add_argument("--show", type=int, default=6, help="components to describe")
    ap.add_argument("--pa-runs", type=int, default=20)
    ap.add_argument("--pa-quantile", type=float, default=0.95)
    ap.add_argument("--max-rows", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        cols, X = load(a.csv, a.columns, set(a.drop))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(cols) < 2 or len(X) <= len(cols):
        print("error: need >= 2 numeric columns and more rows than columns", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    if len(X) > a.max_rows:
        X = rng.sample(X, a.max_rows)
    res = pca(X, scale=not a.no_scale)
    ev = res["eigenvalues"]
    total = sum(ev) or 1.0
    ratio = [v / total for v in ev]
    cum, s = [], 0.0
    for r in ratio:
        s += r
        cum.append(s)
    need = {t: next(i + 1 for i, c in enumerate(cum) if c >= t - 1e-12) for t in a.targets}
    corr_vals = ev if not a.no_scale else jacobi(covariance(center_scale(X, True)[0]))[0]
    kaiser = sum(1 for v in corr_vals if v > 1)
    # parallel analysis: shuffle each column independently (keeps marginals, breaks correlations)
    pa = []
    for _ in range(a.pa_runs):
        cols_shuf = [[x[j] for x in X] for j in range(len(cols))]
        for c in cols_shuf:
            rng.shuffle(c)
        Xs = [[cols_shuf[j][i] for j in range(len(cols))] for i in range(len(X))]
        pa.append(pca(Xs, scale=not a.no_scale)["eigenvalues"])
    qs = []
    for k in range(len(cols)):
        vals = sorted(r[k] for r in pa)
        qs.append(vals[min(len(vals) - 1, int(a.pa_quantile * len(vals)))])
    pa_keep = 0
    for k in range(len(cols)):
        if ev[k] > qs[k]:
            pa_keep += 1
        else:
            break
    var_share = None
    if a.no_scale:
        vars_ = [res["sd"][j] ** 2 for j in range(len(cols))]
        tv = sum(vars_)
        j = max(range(len(cols)), key=lambda j: vars_[j])
        var_share = (cols[j], vars_[j] / tv)
    comps = []
    for k in range(min(a.show, len(cols))):
        load_ = sorted(zip(cols, res["components"][k]), key=lambda t: -abs(t[1]))[:a.top]
        comps.append({"component": k + 1, "explained": ratio[k], "cumulative": cum[k], "eigenvalue": ev[k],
                      "top_loadings": [{"feature": f, "loading": round(v, 4)} for f, v in load_]})
    out = {"rows": len(X), "columns": cols, "scaled": not a.no_scale, "explained_ratio": ratio, "cumulative": cum,
           "components_for_target": {str(k): v for k, v in need.items()}, "kaiser": kaiser,
           "parallel_analysis": pa_keep, "components": comps}
    if var_share:
        out["largest_variance_column"] = {"column": var_share[0], "share": var_share[1]}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"PCA on {len(X)} rows x {len(cols)} columns ({'correlation (standardised)' if not a.no_scale else 'covariance (raw)'})")
    print("explained: " + "  ".join(f"PC{i + 1} {r:.1%}" for i, r in enumerate(ratio[:10])))
    print("cumulative: " + "  ".join(f"{c:.1%}" for c in cum[:10]))
    print("components needed: " + ", ".join(f"{t:.0%} -> {k}" for t, k in need.items()))
    print(f"Kaiser (eigenvalue > 1): {kaiser}   parallel analysis ({a.pa_runs} shuffles, q{a.pa_quantile:g}): {pa_keep}")
    if var_share and var_share[1] > 0.5:
        print(f"WARNING: unscaled - {var_share[0]} holds {var_share[1]:.0%} of the total variance, so PC1 is mostly that "
              "column. Standardise unless all features share units and their variances are meaningful.")
    for c in comps:
        loads = ", ".join(f"{l['feature']} {l['loading']:+.2f}" for l in c["top_loadings"])
        print(f"  PC{c['component']} ({c['explained']:.1%}): {loads}")
    print(f"\nSuggested k: {pa_keep or 1} (parallel analysis) for structure; {need[max(need)]} to retain "
          f"{max(need):.0%} variance as model input.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
