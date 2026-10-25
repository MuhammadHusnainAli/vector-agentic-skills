# Evaluating Density Clusters

## Noise is an output, not an error

The noise share is a product decision: in fraud or anomaly work noise points may be the interesting ones; in
segmentation, 30% noise means many customers get no segment. Decide the acceptable range before tuning
(`dbscan_grid.py --noise-min/--noise-max`).

Inspect noise: profile noise vs clustered points (cluster_profile.py with label −1). Noise that looks like a
coherent group means eps is too small or the group is sparser than the rest (HDBSCAN).

## Indices for density clusters

| Index | Notes |
|-------|-------|
| Silhouette on non-noise points | favours convex clusters; can understate good non-convex results |
| DBCV (density-based clustering validation) | designed for arbitrary shapes and noise; `hdbscan.validity.validity_index` |
| HDBSCAN `relative_validity_` | fast approximation of DBCV (hdbscan package) |
| Cluster persistence / probabilities | HDBSCAN `probabilities_`, condensed tree stability |

## Stability across settings

A trustworthy result keeps its cluster count and membership as eps and min_samples move slightly. Compute ARI
between labelings of neighbouring grid cells; values > 0.9 indicate a stable region.

## Against reference labels

When some ground truth exists (known store regions, manual tags), report ARI / NMI with noise treated as its own
label (as `dbscan_grid.py --labels` does) and separately the share of labelled points placed in noise.

## Checklist

- [ ] Noise share within the agreed range; noise profiled
- [ ] Cluster count stable across neighbouring parameter settings
- [ ] No cluster absorbing > 80-90% of the data (unless expected)
- [ ] Clusters profiled and nameable
- [ ] HDBSCAN compared when DBSCAN is unstable
