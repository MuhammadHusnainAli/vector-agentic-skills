# Methods for Choosing k

## Elbow (inertia) and kneedle

Inertia W_k = Σ ||x − μ_c(x)||² always decreases with k. The elbow is where adding clusters stops paying.
Kneedle (Satopää et al. 2011): normalise k and W_k to [0, 1], take the point with the largest distance below the
chord from the first to the last point. `kneed.KneeLocator(ks, W, curve="convex", direction="decreasing")` and
yellowbrick's `KElbowVisualizer` implement it.

## Silhouette

For point i: a = mean distance to its own cluster, b = mean distance to the nearest other cluster,
s = (b − a) / max(a, b). Mean silhouette ∈ [−1, 1].
```python
from sklearn.metrics import silhouette_score, silhouette_samples
silhouette_score(X, labels, sample_size=5000, random_state=0)      # sample for large n (O(n²))
```
Rules of thumb: > 0.5 reasonable structure, 0.25-0.5 weak, < 0.25 no substantial structure. Look at the
per-cluster silhouette plot: a cluster with many negative values is poorly separated.

## Calinski-Harabasz and Davies-Bouldin

- CH = [B / (k − 1)] / [W / (n − k)] (between vs within dispersion), higher is better.
- DB = mean over clusters of max_j (s_i + s_j) / d(c_i, c_j), lower is better.
`calinski_harabasz_score`, `davies_bouldin_score`. Both are cheap and favour convex clusters.

## Gap statistic (Tibshirani, Walther & Hastie 2001)

```
Gap(k) = E*[log W_k] − log W_k        (E* over B reference datasets drawn uniformly in the bounding box)
s_k    = sd(log W_k*) · sqrt(1 + 1/B)
choose the smallest k with Gap(k) >= Gap(k+1) − s_{k+1}
```
Gap(k) ≈ 0 for all k means the data is not more clustered than uniform noise, the main thing other indices
cannot tell you. Variants draw references in the principal-component box (better for correlated data).

## Stability

Fit on two (overlapping) subsamples or with different seeds; compare labels on shared rows with the adjusted
Rand index (`adjusted_rand_score`). Plot mean ARI vs k: the supported k values are stable (ARI > 0.8). Stability
alone is not enough: k-means splits uniform data stably.

## BIC / AIC for Gaussian mixtures

```python
from sklearn.mixture import GaussianMixture
bic = [GaussianMixture(k, covariance_type="full", n_init=3, random_state=0).fit(X).bic(X) for k in range(1, 11)]
```
Lower is better; outliers inflate the chosen k (see clustering-algorithm-selector's recipes note).

## Cost

| Method | Cost per k |
|--------|------------|
| Inertia, CH, DB | one fit |
| Silhouette | O(n²) distances (sample) |
| Gap | (B + 1) fits |
| Stability | 2+ fits per repeat |

## Putting it together

1. Run all cheap indices and the gap statistic over k = 2..10.
2. Discard k values that produce clusters below the size floor.
3. Among the rest, prefer k values where several criteria agree and stability is high.
4. Decide with profiles and the business: the clearer, actionable segmentation wins ties.
