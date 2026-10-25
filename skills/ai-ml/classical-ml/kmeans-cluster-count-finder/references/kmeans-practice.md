# k-Means in Practice

## Fitting

```python
from sklearn.cluster import KMeans, MiniBatchKMeans, BisectingKMeans
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

seg = make_pipeline(StandardScaler(), KMeans(n_clusters=4, n_init="auto", random_state=0))
labels = seg.fit_predict(X)
centres_original_units = seg[0].inverse_transform(seg[-1].cluster_centers_)
```
- `n_init="auto"`: 1 run with k-means++ (scikit-learn >= 1.4 default); use 10+ for small data if results vary.
- `algorithm="lloyd"` (default) or `"elkan"` (faster on dense, well-separated data).
- Save the whole pipeline: new rows must be scaled with the training statistics.

## Large data

`MiniBatchKMeans(batch_size=4096, n_init="auto", random_state=0)`: choose k on a sample, fit on all data.
`partial_fit` for streaming.

## Outliers and empty clusters

- Outliers either take a centroid (singleton cluster) or pull one away. Cap features at percentiles, or remove
  rows flagged by an anomaly detector before clustering, and assign them afterwards.
- scikit-learn reassigns empty clusters automatically; frequent empties mean k is too large.

## Variants

| Variant | Use |
|---------|-----|
| k-medoids (PAM, `kmedoids` / `sklearn_extra.cluster.KMedoids`) | centres are real rows; any distance; robust to outliers |
| Bisecting k-means (`BisectingKMeans`) | hierarchical splits; faster for large k |
| Spherical k-means (normalise rows, cosine) | text / embedding vectors |
| k-prototypes / k-modes | mixed / categorical data |
| Constrained k-means (min/max sizes) | business size constraints (`k-means-constrained` package) |

## Assigning new rows

`seg.predict(X_new)` assigns to the nearest centroid. Track the distance to the centroid: rows far from every
centroid are novelties that may need a new segment.

## Refreshing segments

- Refit periodically (monthly/quarterly) on recent data.
- Label switching: cluster ids change between fits; match new clusters to old ones by centroid distance
  (Hungarian algorithm, `scipy.optimize.linear_sum_assignment`) before comparing.
- Monitor segment shares and centroid drift; large changes trigger a review of names and actions.
