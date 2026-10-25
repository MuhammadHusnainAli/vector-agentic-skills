# Clustering Algorithm Guide

## What each algorithm assumes

| Algorithm | Cluster model | Needs k | Handles noise | Shapes | Scales to | Soft |
|-----------|---------------|---------|---------------|--------|-----------|------|
| k-means | nearest centroid, equal-variance spheres | yes | no | convex | millions (MiniBatch) | no |
| Gaussian mixture | ellipsoidal Gaussians | yes (BIC) | partly | elliptical | ~10^5 | yes |
| Agglomerative Ward | merge minimising variance | yes (or cut height) | no | convex | ~2-3 x 10^4 | no |
| Agglomerative average/complete | merge by linkage on any metric | yes | weak | moderate | ~2-3 x 10^4 | no |
| Single linkage | chaining | yes | no | elongated | ~10^4 | no |
| DBSCAN | dense regions of fixed density | no | yes | arbitrary | ~10^6 (index-dependent) | no |
| HDBSCAN | density hierarchy, varying density | no | yes | arbitrary | ~10^6 | via hdbscan package |
| OPTICS | density ordering | no | yes | arbitrary | ~10^5 | no |
| Spectral | graph cuts on a similarity graph | yes | no | non-convex | ~10^4 | no |
| BIRCH | CF-tree micro-clusters | optional | weak | convex | streaming | no |
| Mean shift | density modes | no | weak | blobs | ~10^4 | no |
| Affinity propagation | exemplars via message passing | no | no | moderate | ~10^4 | no |
| k-prototypes / k-modes | centroids / modes with mixed dissimilarity | yes | no | convex-ish | ~10^6 | no |

## Decision questions

1. **Is there structure?** Run cluster_tendency.py. If H ~ 0.5, any partition is arbitrary.
2. **Is k given by the business?** (one segment per sales team) -> k-means / GMM / Ward with that k.
3. **Must every point belong to a cluster?** If no (outliers, background), density methods.
4. **Shapes?** Convex segments -> centroid methods; manifolds, rings, elongated groups -> HDBSCAN / spectral.
5. **Different densities?** HDBSCAN / OPTICS, not DBSCAN.
6. **Soft memberships?** GMM (or HDBSCAN soft clustering).
7. **Hierarchy / drill-down?** Agglomerative with a dendrogram.
8. **Mixed types?** k-prototypes, Gower + hierarchical/HDBSCAN, or encode + scale carefully.
9. **Size?** > 10^5 rows: MiniBatchKMeans, BIRCH, HDBSCAN on a sample or a UMAP embedding.

## Typical combinations

| Goal | Pipeline |
|------|----------|
| Customer segments for marketing | features (RFM, behaviour) -> scale -> k-means (k = 4-8) -> profile -> stability check |
| Discover unusual groups / noise | scale -> UMAP (10-20 dims) -> HDBSCAN |
| Geographic hotspots | lat/lon (haversine) -> DBSCAN / HDBSCAN with `metric="haversine"` on radians |
| Document / embedding topics | embeddings -> UMAP -> HDBSCAN (BERTopic-style) |
| Product taxonomy | agglomerative (average, cosine) -> dendrogram cut |
| Overlapping personas | GMM with probabilities |

## What clustering cannot do

- Find the "right" number of clusters without a goal; different k answer different questions.
- Be validated by accuracy: there is no ground truth. Use stability, internal indices as diagnostics, and
  business usefulness (do segments behave differently and lead to different actions?).
- Fix bad features: clusters reflect the features and their scaling more than the algorithm.
