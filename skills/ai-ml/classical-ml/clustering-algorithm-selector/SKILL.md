---
name: clustering-algorithm-selector
description: "Choose the right clustering algorithm and check that clustering makes sense at all: cluster tendency (Hopkins statistic with a correlated-features caveat, nearest-neighbour isolation), then k-means / MiniBatchKMeans, Gaussian mixtures with BIC, agglomerative (Ward, average, complete, single) with dendrograms, DBSCAN, HDBSCAN, OPTICS, spectral clustering, BIRCH, mean shift, k-prototypes and k-modes for mixed or categorical data, and Gower distance, matched to data size, expected shapes, noise, varying density, known k, soft memberships, hierarchy and streaming. Covers preprocessing (scaling, encoding, dimensionality, distance metrics), validation (internal indices, bootstrap stability, external labels, business profiling) and assigning new points. Use when someone wants to segment customers, group products or documents, find natural groups, asks which clustering algorithm to use, k-means vs DBSCAN vs HDBSCAN, or whether their clusters are real."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Clustering Algorithm Selector

Clustering always returns clusters, so the first question is whether the data has structure worth
finding, and the second is what kind: convex segments a business can act on (k-means, GMM, Ward), or
arbitrary dense groups with noise left out (HDBSCAN, DBSCAN). The features and their scaling decide more than
the algorithm. `scripts/cluster_tendency.py` measures cluster tendency (Hopkins statistic, isolation of
points, correlated-feature caveat); `scripts/select_clustering.py` ranks algorithms for the data and the goal,
with starting parameters and cautions.

## Trigger Conditions

Activate this skill when the user:
- Wants to segment customers, users, products, stores, documents or embeddings
- Asks which clustering algorithm to use, or k-means vs DBSCAN vs HDBSCAN vs hierarchical vs GMM
- Has mixed numeric and categorical data to cluster
- Got clusters and wants to know whether they are real, stable or useful
- Needs to assign new records to existing segments

Choosing k for k-means: [kmeans-cluster-count-finder](../kmeans-cluster-count-finder/SKILL.md); DBSCAN
parameters: [dbscan-parameter-tuner](../dbscan-parameter-tuner/SKILL.md); reducing dimensions first:
[pca-dimensionality-reducer](../pca-dimensionality-reducer/SKILL.md) and
[umap-tsne-embedding-visualizer](../umap-tsne-embedding-visualizer/SKILL.md); scaling:
[feature-scaling-advisor](../feature-scaling-advisor/SKILL.md).

## Workflow

```
1. GOAL       -> what decision do the segments drive? fixed k? must every row be assigned?
2. FEATURES   -> behaviour features, no IDs/labels; transform skew; scale; handle categoricals
3. TENDENCY   -> python scripts/cluster_tendency.py data.csv --drop id   (H > 0.75 clustered, ~0.5 random)
4. SELECT     -> python scripts/select_clustering.py --csv data.csv --drop id [--k-known 5 --noise ...]
5. FIT 2-3    -> top candidates; choose k / density parameters with the dedicated skills
6. VALIDATE   -> internal index matching the algorithm, bootstrap stability (ARI), profiles, outcome differences
7. OPERATE    -> naming, assignment of new rows (predict or a classifier), refresh cadence, drift of segment sizes
```

## Is There Anything to Cluster?

```
Hopkins H = 0.856 (blobs fixture: 3 groups + noise)   -> clustered
Hopkins H = 0.535 (uniform fixture)                   -> no clear structure (close to random)
Hopkins H = 0.728 + 13 pairs with |r| > 0.7 (wide)    -> correlated features, not necessarily clusters
```
- H measures departure from uniform randomness. Strongly correlated features (points on a low-dimensional
  manifold) raise H without forming groups; the script warns when many column pairs have |r| > 0.7.
  Re-check on a few principal components.
- A high share of isolated points (> 3x the median nearest-neighbour distance) favours density methods that
  can label noise.

## Selection Table

| Situation | First choice | Alternatives |
|-----------|--------------|--------------|
| k fixed by the business, numeric, convex segments | k-means (MiniBatchKMeans if large) | GMM, Ward |
| Overlapping groups, need probabilities | Gaussian mixture (BIC for k) | HDBSCAN soft clustering |
| Arbitrary shapes, noise, unknown k | HDBSCAN | DBSCAN (single density), OPTICS |
| Varying densities | HDBSCAN | OPTICS |
| Need a hierarchy / drill-down | Agglomerative + dendrogram | HDBSCAN condensed tree |
| Non-convex, small data, k known | Spectral clustering | HDBSCAN |
| Streaming / huge data | MiniBatchKMeans, BIRCH | HDBSCAN on a sample + classifier |
| Mixed numeric + categorical | k-prototypes | Gower + agglomerative / HDBSCAN |
| Categorical only | k-modes | Gower / Jaccard + agglomerative |
| Embeddings / text | UMAP -> HDBSCAN | k-means on normalised embeddings |
| Geographic points | HDBSCAN / DBSCAN with haversine | grid aggregation |

Assumptions, scaling limits and typical pipelines: [algorithm-guide.md](references/algorithm-guide.md).

## Preprocessing Decides the Result

1. Choose features that describe the differences you want segments to capture.
2. log1p skewed amounts and counts; standardise (or robust-scale) everything.
3. Categoricals: a dedicated method (k-prototypes, Gower) or carefully down-weighted one-hot.
4. Remove redundant copies of the same signal (they double its weight).
5. Reduce dimensions above ~20-50 features (PCA for centroid methods, UMAP for density methods); never
   cluster on a 2-D t-SNE map.

Details and metric choice per data type: [preprocessing-for-clustering.md](references/preprocessing-for-clustering.md).

## Validating Clusters

| Check | How | Good sign |
|-------|-----|-----------|
| Internal index | silhouette / CH / DB for centroid methods; DBCV for density methods | clear optimum, not just "higher with k" |
| Stability | refit on 80% subsamples / new seeds; adjusted Rand index | ARI > 0.8 |
| Profiles | feature means per cluster relative to the population | nameable, distinct segments |
| Outcomes | churn / spend / response by cluster | real differences |
| Actionability | one action per segment | yes |
| Size | share per cluster | no trivial (< 1-2%) segments unless they are the point |

Code: [validating-clusters.md](references/validating-clusters.md). Verified recipes for every algorithm (k-means,
GMM/BIC, HDBSCAN, DBSCAN, agglomerative + dendrogram, spectral, k-prototypes, Gower, k-modes) and how to
assign new points: [clustering-recipes.md](references/clustering-recipes.md). Note from the fixture: with 5%
uniform noise, GMM's BIC keeps adding components (minimum at k = 8 vs k = 3 without noise); handle noise first.

## Output Format

When recommending a clustering approach, deliver:
1. **Goal and constraints** - decision, k fixed or free, noise allowed, soft or hard, hierarchy.
2. **Tendency** - Hopkins H, isolated share, correlation caveat (`cluster_tendency.py`).
3. **Preprocessing** - features, transforms, scaling, categorical handling, dimensionality reduction.
4. **Ranked algorithms** - top 2-3 with starting parameters (`select_clustering.py`).
5. **Validation plan** - index, stability, profiling, outcome comparison.
6. **Operational plan** - assigning new rows, refresh cadence, monitoring segment sizes.

## Scripts

```bash
python scripts/cluster_tendency.py data.csv --drop customer_id
python scripts/cluster_tendency.py data.csv --columns x1 x2 x3 --sample 300 --repeats 10 --json
python scripts/cluster_tendency.py data.csv --power d          # dimension-adjusted Hopkins variant
```
Standardises numeric columns, averages the Hopkins statistic over repeats (uniform points in the bounding box vs
sampled data points), reports the nearest-neighbour distance CV and isolated-point share, and lists column pairs
with |r| > 0.7. Exit codes: 0 clustered (H > 0.7), 1 no clear structure, 2 usage or read error.

```bash
python scripts/select_clustering.py --csv customers.csv --drop customer_id
python scripts/select_clustering.py --rows 2000000 --dims 12 --k-known 5 --streaming
python scripts/select_clustering.py --rows 5000 --dims 3 --shapes arbitrary --noise --varying-density --json
```
Scores 11-13 algorithms (k-means, GMM, HDBSCAN, DBSCAN, Ward, spectral, BIRCH, OPTICS, mean shift, plus
k-prototypes / Gower for mixed data and k-modes for categorical data) from rows, dimensions, categorical count
and the goal flags, and prints why, a starting configuration and cautions for each. Exit codes: 0 printed, 2
usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [algorithm-guide.md](references/algorithm-guide.md) | Assumptions, k, noise, shapes, scale and soft assignment per algorithm; decision questions; typical pipelines; limits of clustering |
| [preprocessing-for-clustering.md](references/preprocessing-for-clustering.md) | Feature choice, scaling, categorical handling, dimensionality reduction, distance metrics, outliers |
| [validating-clusters.md](references/validating-clusters.md) | Internal indices and their biases, bootstrap stability, external labels, profiling, business validation |
| [clustering-recipes.md](references/clustering-recipes.md) | Verified code for each algorithm, mixed-type options, assigning new points |
