# Preprocessing for Clustering

Clusters are defined by distances, so preprocessing *is* the model.

## Feature choice

- Use features that describe the behaviour the segments should differ on (for customer segments: recency,
  frequency, monetary, product mix, channel), not IDs, dates or outcome labels.
- Drop near-duplicates: two copies of the same signal double its weight.
- Fewer, meaningful features beat many weak ones (distances concentrate in high dimensions).

## Scaling

| Situation | Transform |
|-----------|-----------|
| Mixed units | StandardScaler (or RobustScaler with outliers) |
| Skewed amounts / counts | log1p, then standardise |
| Proportions | keep in [0, 1] or logit |
| Features of different importance | multiply scaled columns by weights deliberately |

Unscaled, the widest column decides the clusters (feature-scaling-advisor's `scale_impact.py` shows the
dominance).

## Categorical features

| Option | Notes |
|--------|-------|
| k-prototypes / k-modes | native mixed / categorical objective |
| Gower distance | proper mixed dissimilarity; O(n²) |
| One-hot + scaling | a binary column's variance depends on its frequency; down-weight one-hot blocks (e.g. divide by sqrt(levels)) or the categorical features dominate |
| Target-free embeddings | e.g. from an autoencoder or entity embeddings |

## Dimensionality

- PCA to retain ~80-90% variance removes noise and speeds k-means/GMM.
- UMAP (n_components 5-20, `min_dist=0.0`) before HDBSCAN works well for complex manifolds; do not cluster on a
  2-D t-SNE plot (it distorts densities and distances).
- Check that clusters found in the reduced space are visible in the original feature profiles.

## Distance metrics

| Data | Metric |
|------|--------|
| Continuous, scaled | Euclidean |
| High-dimensional embeddings / text | cosine (or L2-normalise then Euclidean) |
| Counts / profiles | cosine, Bray-Curtis |
| Lat/lon | haversine (radians) |
| Mixed | Gower |
| Binary | Jaccard, Hamming |

## Outliers

Extreme rows pull centroids (k-means) and steal mixture components (GMM). Either cap features (winsorise),
remove obvious errors, or use a density method that labels noise.

## Checklist

- [ ] IDs, dates, labels removed
- [ ] Skewed features transformed
- [ ] Features scaled; weights deliberate
- [ ] Categoricals handled with a suitable dissimilarity
- [ ] Redundant features removed
- [ ] Dimensionality reduced if > ~20-50 features
