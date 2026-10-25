# UMAP, t-SNE and PCA: How They Work and How to Set Them

## t-SNE

1. Converts high-dimensional distances into neighbour probabilities with a Gaussian per point whose width is
   set so its entropy matches log2(perplexity).
2. Places points in 2-D, with a heavy-tailed Student-t kernel, to match those probabilities (KL divergence).
3. The heavy tail pushes dissimilar points far apart: clusters look well separated regardless of their real gap.

Parameters:
- `perplexity` (5-50; < n/3): roughly the number of effective neighbours. Small values fragment data into
  many small groups; large values show more global structure and run slower.
- `early_exaggeration` (12): separates clusters early in optimisation; rarely changed.
- `learning_rate="auto"` (max(n/early_exaggeration/4, 50)), `max_iter` 1000+ (`n_iter` was renamed).
- `init="pca"`: deterministic-ish, better global layout than random.
- Barnes-Hut (`method="barnes_hut"`) is O(n log n); exact is O(n²).
- scikit-learn's TSNE has no `transform` for new points; openTSNE does.

## UMAP

1. Builds a fuzzy k-nearest-neighbour graph (n_neighbors) in the original space with local distance scaling.
2. Optimises a low-dimensional layout whose fuzzy graph matches it (cross-entropy), with negative sampling.

Parameters:
- `n_neighbors` (5-50, default 15): local vs global balance.
- `min_dist` (0.0-0.99, default 0.1): minimum spacing in the layout; 0.0 for clustering, larger to spread
  points for display.
- `metric`: any of euclidean, cosine, manhattan, correlation, haversine, custom numba functions.
- `n_components`: 2-3 for plots, 5-20 as input to clustering.
- `random_state` makes it reproducible but single-threaded; omit it (and set `n_jobs`) for speed.
- `densmap=True`: preserves local density (sizes become more meaningful).
- `transform(X_new)`: embeds new points into an existing map; inverse_transform for some metrics.

## PCA

Linear projection on maximum-variance directions; distances and global layout are preserved as far as two
dimensions allow. Always show it as the baseline and report its explained variance.

## Pre-reduction

For > 50 features (embeddings with 384-1536 dims, many tabular features), PCA to 50 components first: removes
noise dimensions, speeds up k-NN, and rarely changes UMAP/t-SNE results materially. For cosine-based embeddings
L2-normalise first.

## Other methods

| Method | Strength |
|--------|----------|
| PaCMAP | balances local and global structure; robust defaults |
| TriMap | triplet constraints; better global structure |
| openTSNE | fast FFT-accelerated t-SNE, `transform`, exaggeration control |
| densMAP | UMAP with density preservation |
| Parametric UMAP | neural-network mapping; embeds new points quickly |
| MDS / Isomap | distance / geodesic preservation; small data |

## Large data

- UMAP handles millions of points (approximate nearest neighbours via pynndescent).
- t-SNE: openTSNE or FIt-SNE for > 100k points; subsample for exploration.
- Plot with alpha / datashader to avoid overplotting.
