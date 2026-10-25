# DBSCAN in Depth

## Mechanics

- **Neighbourhood** N_eps(p): points within eps of p (p included).
- **Core point**: |N_eps(p)| >= min_samples.
- **Directly density-reachable**: q in N_eps(p) and p is core.
- **Cluster**: maximal set of points density-connected through core points.
- **Border point**: not core, but in the neighbourhood of a core point; assigned to the first cluster that
  reaches it (order-dependent when it neighbours two clusters).
- **Noise**: neither core nor border (label −1).

## Parameter interplay

| Change | Effect |
|--------|--------|
| eps up | more core points, clusters grow and merge, less noise |
| eps down | clusters shrink and split, more noise |
| min_samples up | fewer core points, more noise, small groups disappear, more robust to chaining |
| min_samples down | more core points, chaining between clusters, tiny clusters appear |

Rule of thumb: decide min_samples from the domain (noise tolerance, smallest group), then tune eps.

## Determinism

Core points and noise are deterministic; border points between two clusters depend on processing order.
scikit-learn's implementation is deterministic for a given input order.

## Complexity and scale

- Neighbourhood queries dominate: O(n log n) average with a tree index in low dimensions, O(n²) worst case or in
  high dimensions.
- `algorithm="ball_tree"` / `"kd_tree"` / `"brute"`; `n_jobs=-1` parallelises queries.
- Memory: scikit-learn materialises neighbourhoods; large eps on big data can exhaust memory. Sample, reduce
  eps, or use HDBSCAN.

## OPTICS

Orders points by reachability distance; clusters are valleys in the reachability plot.
```python
from sklearn.cluster import OPTICS
op = OPTICS(min_samples=10, xi=0.05, min_cluster_size=0.02).fit(X)
reach = op.reachability_[op.ordering_]           # plot: valleys = clusters
```
`cluster_optics_dbscan(reachability=..., core_distances=..., ordering=..., eps=e)` extracts the DBSCAN result
for any eps from one OPTICS run, which is cheap for exploring eps.

## HDBSCAN

```python
from sklearn.cluster import HDBSCAN
hdb = HDBSCAN(min_cluster_size=20, min_samples=10, cluster_selection_epsilon=0.0,
              cluster_selection_method="eom").fit(X)
```
| Parameter | Meaning |
|-----------|---------|
| min_cluster_size | smallest group to report as a cluster |
| min_samples | noise strictness (defaults to min_cluster_size) |
| cluster_selection_epsilon | merge clusters below this distance (DBSCAN-like floor) |
| cluster_selection_method | "eom" (excess of mass, fewer larger clusters) or "leaf" (finer clusters) |

## Assigning new points

DBSCAN has no `predict`. Options:
1. Nearest core point within eps -> its cluster; otherwise noise:
   ```python
   from sklearn.neighbors import NearestNeighbors
   core = db.components_; core_labels = db.labels_[db.core_sample_indices_]
   nn = NearestNeighbors(n_neighbors=1).fit(core)
   dist, idx = nn.kneighbors(X_new)
   new_labels = np.where(dist[:, 0] <= db.eps, core_labels[idx[:, 0]], -1)
   ```
2. Train a classifier on (X, labels) for non-noise points.
3. Re-run clustering periodically on fresh data.
