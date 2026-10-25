#!/usr/bin/env python3
"""Rank clustering algorithms for a dataset and a goal, with starting parameters and validation advice.

Traits from a CSV (--csv, numeric/categorical counts, rows) or flags; goals/needs from flags:
  --k-known N          number of clusters is fixed by the business (segments for N teams)
  --shapes convex|arbitrary|unknown   expected cluster geometry
  --noise              there are outliers / background points that should not be forced into clusters
  --varying-density    clusters of very different densities
  --soft               need membership probabilities (overlapping segments)
  --hierarchy          need a dendrogram / nested segments
  --mixed              numeric + categorical features (or detected from the CSV)
  --streaming          data arrives continuously / does not fit in memory

Candidates: k-means / MiniBatchKMeans, Gaussian mixture, agglomerative (Ward / average / complete),
HDBSCAN, DBSCAN, OPTICS, spectral clustering, BIRCH, mean shift, k-prototypes (mixed),
k-modes (categorical), affinity propagation.

Usage:
    python select_clustering.py --csv customers.csv --drop customer_id
    python select_clustering.py --rows 2000000 --dims 12 --k-known 5 --streaming
    python select_clustering.py --rows 5000 --dims 3 --shapes arbitrary --noise --varying-density --json

Exit codes: 0 ranking printed, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def traits_from_csv(path, drop):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    num = cat = 0
    for c in header:
        if c in drop:
            continue
        vals = [(r[c] or "").strip() for r in rows if (r[c] or "").strip().lower() not in MISSING]
        if not vals:
            continue
        try:
            [float(v) for v in vals]
            num += 1
        except ValueError:
            if len(set(vals)) < 0.5 * len(vals):
                cat += 1
    return len(rows), num, cat


def rank(t):
    n, d, cat = t["rows"], t["dims"], t["categorical"]
    big = n > 200_000
    huge = n > 2_000_000
    mixed = t["mixed"] or (cat > 0 and d > 0)
    only_cat = cat > 0 and d == 0
    arb = t["shapes"] == "arbitrary"
    out = []

    def add(name, score, why, start, caution):
        out.append({"algorithm": name, "score": round(score, 1), "why": why, "start": start, "caution": caution})

    kk = t["k_known"]
    add("k-means (KMeans / MiniBatchKMeans)",
        7 + (2 if kk else 0) + (1.5 if big else 0) + (1 if t["streaming"] else 0) - (3 if arb else 0)
        - (2 if t["noise"] else 0) - (1.5 if t["varying_density"] else 0) - (3 if mixed or only_cat else 0) - (2 if t["soft"] else 0),
        "fast, scalable, simple centroids that are easy to explain as segments",
        f"KMeans(n_clusters={kk or 'k from kmeans-cluster-count-finder'}, n_init='auto', random_state=0) on scaled features; "
        "MiniBatchKMeans(batch_size=4096) for large data",
        "assumes convex, similar-sized, similar-variance clusters; every point is assigned (outliers distort centroids)")
    add("Gaussian mixture (GaussianMixture)",
        6 + (2.5 if t["soft"] else 0) + (1 if kk else 0) - (2 if huge else 0) - (2 if arb else 0) - (3 if mixed or only_cat else 0)
        - (1 if d > 50 else 0),
        "soft assignments, elliptical clusters of different shapes/sizes, BIC to choose k",
        "GaussianMixture(n_components=k, covariance_type='full', n_init=5, random_state=0); choose k by BIC",
        "sensitive to initialisation and scaling; 'full' covariance needs many points per cluster in high dimensions")
    add("HDBSCAN",
        6 + (2.5 if arb else 0) + (2.5 if t["noise"] else 0) + (2 if t["varying_density"] else 0) - (2 if kk else 0)
        - (1 if huge else 0) - (1.5 if d > 50 else 0) - (3 if only_cat else 0),
        "finds arbitrary shapes and varying densities, labels noise, needs no k",
        "sklearn.cluster.HDBSCAN(min_cluster_size=max(15, n//200), min_samples=None) on scaled (or UMAP-reduced) data",
        "noise share can be large; cluster count follows the data, not the business; distance-based (scale first)")
    add("DBSCAN",
        4.5 + (2 if arb else 0) + (2 if t["noise"] else 0) - (2 if t["varying_density"] else 0) - (2 if kk else 0)
        - (1 if d > 20 else 0) - (3 if only_cat else 0),
        "arbitrary shapes and noise with two interpretable parameters",
        "DBSCAN(eps from the k-distance knee, min_samples=2*dims) - see dbscan-parameter-tuner",
        "one global density: fails with varying densities; eps is in scaled units")
    add("Agglomerative (Ward)",
        5.5 + (3 if t["hierarchy"] else 0) + (1 if kk else 0) - (4 if n > 30_000 else 0) - (1.5 if arb else 0) - (2 if mixed else 0)
        - (4 if only_cat else 0),
        "dendrogram for nested segments; deterministic",
        "AgglomerativeClustering(n_clusters=k, linkage='ward'); scipy.cluster.hierarchy for the dendrogram",
        "O(n^2) memory; Ward behaves like k-means (convex); use average/complete linkage for other metrics")
    add("Spectral clustering",
        4 + (2.5 if arb else 0) + (1 if kk else 0) - (5 if n > 20_000 else 0),
        "non-convex clusters via a similarity graph, k known",
        "SpectralClustering(n_clusters=k, affinity='nearest_neighbors', n_neighbors=15, assign_labels='cluster_qr')",
        "does not scale beyond ~10-20k points; sensitive to the affinity choice")
    add("BIRCH", 3.5 + (2 if big else 0) + (2 if t["streaming"] else 0) - (2 if arb else 0) - (3 if mixed or only_cat else 0),
        "single pass, memory-bounded, incremental (partial_fit)", "Birch(threshold=0.5, n_clusters=k)",
        "convex clusters; threshold depends on scaling")
    add("OPTICS", 3.5 + (2 if t["varying_density"] else 0) + (1 if arb else 0) - (2 if big else 0),
        "density ordering that handles varying density; reachability plot", "OPTICS(min_samples=2*dims, xi=0.05)",
        "slower than HDBSCAN, which usually supersedes it")
    add("Mean shift", 2.5 + (1 if arb else 0) - (4 if n > 10_000 else 0), "mode seeking; no k",
        "MeanShift(bandwidth=estimate_bandwidth(X, quantile=0.2))", "slow; bandwidth-sensitive")
    if mixed:
        add("k-prototypes (kmodes package)", 8 + (1 if kk else 0) - (1 if huge else 0),
            "numeric + categorical in one objective (Euclidean + matching dissimilarity)",
            "KPrototypes(n_clusters=k, init='Cao', gamma=None).fit(X, categorical=[indices])",
            "gamma weights categorical vs numeric parts; scale numerics first")
        add("Gower distance + agglomerative / HDBSCAN (precomputed)", 6.5 - (4 if n > 20_000 else 0),
            "any mix of types through a proper dissimilarity", "gower.gower_matrix(df) -> HDBSCAN(metric='precomputed')",
            "O(n^2) memory")
    if only_cat:
        add("k-modes (kmodes package)", 9, "categorical-only data: modes instead of means",
            "KModes(n_clusters=k, init='Huang', n_init=5)", "matching dissimilarity ignores level similarity")
    if t["soft"]:
        for o in out:
            if o["algorithm"].startswith("HDBSCAN"):
                o["caution"] += "; soft memberships via the hdbscan package's membership vectors"
    return sorted(out, key=lambda o: -o["score"])


def main():
    ap = argparse.ArgumentParser(description="Rank clustering algorithms for data and goals.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--rows", type=int)
    ap.add_argument("--dims", type=int, help="numeric feature count")
    ap.add_argument("--categorical", type=int, default=0)
    ap.add_argument("--k-known", type=int)
    ap.add_argument("--shapes", choices=["convex", "arbitrary", "unknown"], default="unknown")
    ap.add_argument("--noise", action="store_true")
    ap.add_argument("--varying-density", action="store_true")
    ap.add_argument("--soft", action="store_true")
    ap.add_argument("--hierarchy", action="store_true")
    ap.add_argument("--mixed", action="store_true")
    ap.add_argument("--streaming", action="store_true")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        if a.csv:
            rows, dims, cat = traits_from_csv(a.csv, set(a.drop))
        elif a.rows and a.dims is not None:
            rows, dims, cat = a.rows, a.dims, a.categorical
        else:
            raise ValueError("give --csv or --rows and --dims")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    t = {"rows": rows, "dims": dims, "categorical": cat, "k_known": a.k_known, "shapes": a.shapes, "noise": a.noise,
         "varying_density": a.varying_density, "soft": a.soft, "hierarchy": a.hierarchy, "mixed": a.mixed,
         "streaming": a.streaming}
    ranked = rank(t)[:a.top]
    if a.json:
        print(json.dumps({"traits": t, "ranking": ranked}, indent=2))
        return 0
    flags = [k for k in ("k_known", "noise", "varying_density", "soft", "hierarchy", "mixed", "streaming") if t[k]]
    print(f"Data: {rows:,} rows, {dims} numeric, {cat} categorical; shapes {a.shapes}; needs: {', '.join(flags) or 'none'}")
    for i, r in enumerate(ranked, 1):
        print(f"\n{i}. {r['algorithm']}  (score {r['score']})\n   why:     {r['why']}\n   start:   {r['start']}\n"
              f"   caution: {r['caution']}")
    print("\nBefore trusting any result: check cluster tendency (cluster_tendency.py), scale features, compare 2-3 "
          "algorithms, test stability (bootstrap ARI) and ask whether each cluster leads to a different action.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
