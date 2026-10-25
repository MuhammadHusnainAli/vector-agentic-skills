# Validating Clusters

There is no accuracy for clustering. Validate on four fronts.

## 1. Internal indices (diagnostics, not truth)

| Index | Better | Bias |
|-------|--------|------|
| Silhouette | higher (−1..1) | favours convex, well-separated clusters |
| Calinski-Harabasz | higher | favours convex clusters, grows with k on large data |
| Davies-Bouldin | lower | favours convex clusters |
| DBCV (density-based validation) | higher | for density clusters (HDBSCAN `relative_validity_` in the hdbscan package) |

```python
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
mask = labels != -1                                   # exclude noise for density methods
print(silhouette_score(X[mask], labels[mask]), calinski_harabasz_score(X[mask], labels[mask]),
      davies_bouldin_score(X[mask], labels[mask]))
```
Compare algorithms with the index that matches their cluster model; never compare k-means and HDBSCAN by
silhouette alone.

## 2. Stability

Clusters that matter reappear on resampled data:
```python
import numpy as np
from sklearn.metrics import adjusted_rand_score
rng = np.random.default_rng(0)
scores = []
for _ in range(20):
    idx = rng.choice(len(X), int(0.8 * len(X)), replace=False)
    a = KMeans(4, n_init="auto", random_state=int(rng.integers(1e6))).fit(X[idx])
    b = KMeans(4, n_init="auto", random_state=int(rng.integers(1e6))).fit(X[idx])
    scores.append(adjusted_rand_score(a.labels_, b.labels_))     # seed stability; also compare across subsamples on shared rows
print(np.mean(scores))     # > 0.8 stable, < 0.5 arbitrary
```
For subsample stability, fit on two overlapping subsamples and compare labels on the shared rows.

## 3. External validation (when some labels exist)

Adjusted Rand Index, normalised mutual information, homogeneity/completeness against known groups. A
segmentation that is unrelated to every known variable is suspicious.

## 4. Business validation

- **Profile** each cluster: size, mean/median of each feature relative to the population (lift), top
  categories.
- **Name** them in plain language; if you cannot, the cluster may be an artefact.
- **Outcome differences**: do clusters differ in churn rate, spend, response? Segments that behave the same
  do not need different treatment.
- **Actionability**: each cluster maps to a different action or message.
- **Size floor**: tiny clusters (< 1-2% of rows) are rarely actionable.
- **Stability over time**: re-run next month; do segments persist and do customers move between them sensibly?

## Profiling snippet

```python
prof = df.assign(cluster=labels).groupby("cluster")[feature_cols].mean()
lift = prof / df[feature_cols].mean()
sizes = df.assign(cluster=labels).cluster.value_counts(normalize=True)
```
