---
name: dbscan-parameter-tuner
description: "Tune DBSCAN (and know when to switch to HDBSCAN or OPTICS): choose min_samples from dimensionality and the smallest meaningful group, find eps from the knee of the k-distance curve with a noise-share bracket, grid-search eps x min_samples for stable regions (cluster count that persists across neighbouring settings, noise share, largest-cluster share, silhouette on non-noise points, ARI against reference labels), and handle scaling, distance metrics (Euclidean, cosine, haversine for coordinates), high dimensions, varying densities, border points, noise interpretation, and assigning new points. Pure-Python k-distance and DBSCAN grid scripts validated against scikit-learn. Use when someone asks how to set eps or min_samples, gets one giant cluster or all-noise results from DBSCAN, clusters geographic points, or needs density-based clustering with outliers."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# DBSCAN Parameter Tuner

DBSCAN has two parameters with physical meaning: **min_samples** (how many points make a dense
neighbourhood, i.e. the smallest group you care about, and how strict noise labelling is) and **eps** (the
neighbourhood radius in the scaled feature space). Choose min_samples first, read eps off the k-distance curve,
then confirm on a small grid that the result is **stable**: the same cluster count over neighbouring settings.
If no single eps works because clusters have different densities, DBSCAN is the wrong tool: use HDBSCAN.
`scripts/kdist.py` finds the knee and a noise-share bracket; `scripts/dbscan_grid.py` runs the grid and
recommends a stable setting (results identical to scikit-learn's DBSCAN on the fixture).

## Trigger Conditions

Activate this skill when the user:
- Asks how to choose eps / min_samples for DBSCAN
- Gets one giant cluster, everything labelled noise, or wildly different results from small eps changes
- Clusters GPS / lat-lon points, embeddings, or sensor readings with outliers
- Needs density-based clusters with noise and wonders about HDBSCAN or OPTICS
- Must assign new points to DBSCAN clusters

Choosing between algorithms: [clustering-algorithm-selector](../clustering-algorithm-selector/SKILL.md);
scaling: [feature-scaling-advisor](../feature-scaling-advisor/SKILL.md); anomaly scoring instead of clustering:
[anomaly-detection-model-builder](../anomaly-detection-model-builder/SKILL.md).

## Workflow

```
1. SCALE      -> standardise (or a meaningful metric: haversine in radians, cosine for embeddings)
2. DIMENSIONS -> > ~10-20 features: reduce first (PCA / UMAP); distances concentrate in high dimensions
3. MIN_SAMPLES-> start at 2 x dims (>= 4); raise for noisy data or to ignore small groups
4. EPS        -> python scripts/kdist.py data.csv --drop id --min-samples M   (knee + bracket)
5. GRID       -> python scripts/dbscan_grid.py data.csv --drop id --eps ... --min-samples ...
6. CHECK      -> stable cluster count, noise 2-15% (domain-dependent), no cluster > 90%, profiles make sense
7. FALLBACK   -> no stable setting or varying densities -> HDBSCAN(min_cluster_size=...)
```

## min_samples

| Consideration | Guidance |
|---------------|----------|
| Default | 2 x number of dimensions (Sander et al. 1998), at least 4 |
| Noisy data | larger (fewer spurious core points, more noise labels) |
| Smallest meaningful group | min_samples <= that group size |
| Large datasets | larger values (10-50) stabilise results |
| Duplicates / many identical points | larger, or deduplicate with sample weights |

min_samples counts the point itself in scikit-learn. A point is **core** if at least min_samples points
(including itself) lie within eps; **border** if within eps of a core point; otherwise **noise**.

## eps from the k-distance curve

```
300 rows x 3 columns (standardised); min_samples=6 -> distance to the 5-th nearest neighbour
quantiles: p10=0.1848  p25=0.2167  p50=0.2594  p75=0.3509  p90=0.4516  p95=0.7473  p99=3.0747
knee at rank 277/300: eps ~ 0.5133 (points beyond it: 7.3% -> likely noise)
eps for ~15% .. ~2% noise: 0.4046 .. 2.178
```
Sort every point's distance to its (min_samples − 1)-th nearest neighbour; cluster points sit on the flat part,
noise on the steep tail. The knee is the starting eps (the fixture has 5% planted noise; the knee flags 7%).

## Reading the grid

```
min_s      eps clusters   noise  largest   silh stable    ARI
    6      0.4        3    5.7%    31.7%  0.733      4  0.989  <- recommended
    6      1          2    4.7%    63.7%  0.535      2  0.590      (two clusters merged)
   10      0.3        3   28.0%    25.7%  0.786      2  0.581      (too strict: real points become noise)
```
- **Stable region**: the cluster count repeats across neighbouring eps/min_samples cells (`stable` column);
  a count that appears in one cell only is an accident. The script requires >= 2 agreeing neighbours.
- **Merging**: `largest` jumping toward 100% means eps bridged two clusters.
- **Fragmentation**: very small eps makes many tiny clusters and lots of noise.
- On the uniform fixture no setting is stable: the script says so instead of recommending 10 "clusters".

Parameter interplay, metrics and HDBSCAN translation: [dbscan-in-depth.md](references/dbscan-in-depth.md).

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| One giant cluster | eps too large, or chains of border points bridge clusters | lower eps; raise min_samples |
| Almost everything is noise | eps too small for the scaled space; high dimensions | raise eps (k-distance), reduce dimensions |
| Results jump with tiny eps changes | no density gap / varying densities | HDBSCAN or OPTICS |
| Dense core found, sparse groups lost | single global density | HDBSCAN |
| Clusters dominated by one feature | unscaled features | standardise; weight features deliberately |
| Geographic clusters wrong size | Euclidean on degrees | haversine on radians, eps = km / 6371 |
| Slow on large data | O(n²) neighbourhoods without an index | `algorithm="ball_tree"`, sample, or HDBSCAN |

## Geographic and Other Metrics

```python
import numpy as np
from sklearn.cluster import DBSCAN
coords = np.radians(df[["lat", "lon"]].to_numpy())
db = DBSCAN(eps=0.5 / 6371.0, min_samples=10, metric="haversine", algorithm="ball_tree").fit(coords)   # 500 m
```
Embeddings: L2-normalise and use Euclidean (equivalent ordering to cosine), or `metric="cosine"` with
`algorithm="brute"`. Details: [metrics-and-scaling.md](references/metrics-and-scaling.md).

## When to Use HDBSCAN Instead

HDBSCAN removes eps: it builds the density hierarchy and keeps the most persistent clusters, so it handles
varying densities and gives membership strengths. Translate: `min_cluster_size` ≈ the smallest meaningful
group; `min_samples` as in DBSCAN (noise strictness). `cluster_selection_epsilon` merges clusters closer than
a distance (DBSCAN-like behaviour at the bottom).

## Output Format

When tuning DBSCAN, deliver:
1. **Preprocessing** - scaling/metric, dimensionality reduction if any.
2. **min_samples rationale** and the k-distance summary (`kdist.py`): knee eps and bracket.
3. **Grid** - clusters, noise, largest share, silhouette, stability (and ARI if labels exist) (`dbscan_grid.py`).
4. **Choice** - eps and min_samples from the stable region, with cluster sizes and noise share.
5. **Sanity checks** - cluster profiles; noise points inspected; HDBSCAN comparison if unstable.
6. **Operational note** - how new points are assigned (nearest core point / classifier).

## Scripts

```bash
python scripts/kdist.py data.csv --drop id label
python scripts/kdist.py data.csv --min-samples 10 --columns x y --no-scale --json
```
Distance from every point to its (min_samples − 1)-th nearest neighbour (standardised features, default
min_samples = 2 x dims, at least 4), quantiles, kneedle knee as the eps suggestion with the share of points beyond
it, an eps bracket for ~15% to ~2% noise, and an ASCII plot. Exit codes: 0 printed, 2 usage or read error.

```bash
python scripts/dbscan_grid.py data.csv --drop id --eps 0.3 0.4 0.5 0.6 0.8 --min-samples 4 6 10
python scripts/dbscan_grid.py data.csv --labels true_cluster
python scripts/dbscan_grid.py data.csv --noise-max 0.1 --json
```
Pure-Python DBSCAN over the grid (eps defaults to multiples of the k-distance 90th percentile): cluster count,
noise share, largest-cluster share, sampled silhouette of non-noise points, stable neighbour count and optional
ARI vs `--labels`; recommends the most stable setting meeting the noise window and merge limit. Exit codes: 0
recommendation, 1 no stable setting, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [dbscan-in-depth.md](references/dbscan-in-depth.md) | Core/border/noise mechanics, parameter interplay, determinism, complexity, HDBSCAN/OPTICS parameters, assigning new points |
| [metrics-and-scaling.md](references/metrics-and-scaling.md) | Scaling, feature weighting, haversine for coordinates, cosine for embeddings, high dimensions and UMAP, precomputed distances |
| [evaluating-density-clusters.md](references/evaluating-density-clusters.md) | Noise interpretation, DBCV, silhouette on non-noise points, stability across settings, profiling noise vs clusters |
