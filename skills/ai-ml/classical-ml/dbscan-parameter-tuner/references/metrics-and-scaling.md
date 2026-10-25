# Metrics and Scaling for Density Clustering

## Scaling

eps is a distance in the transformed space, so scaling decides what "close" means:
- Standardise numeric features (or RobustScaler with outliers).
- log1p skewed amounts before scaling.
- Weight features deliberately: multiplying a scaled column by 2 makes it count twice as much.
- Keep the fitted scaler: new points must use the same transform before applying eps.

## Coordinates (lat/lon)

Use the haversine metric on radians; eps is an angle:
```python
EARTH_KM = 6371.0
eps_km = 0.3                                    # 300 m neighbourhood
db = DBSCAN(eps=eps_km / EARTH_KM, min_samples=8, metric="haversine", algorithm="ball_tree")
db.fit(np.radians(df[["lat", "lon"]].to_numpy()))
```
Choose eps_km from the domain (walking distance, store catchment) and check with the k-distance curve computed
in km.

## Embeddings and text

- L2-normalise vectors; Euclidean distance on unit vectors is monotone in cosine distance.
- High-dimensional embeddings (384-1536 dims) make distances concentrate: reduce with UMAP
  (`n_components=10-20, min_dist=0.0, metric="cosine"`) and run HDBSCAN on the reduced space.

## High dimensions

As dimensionality grows, nearest and farthest neighbour distances converge, the k-distance curve loses its
knee and DBSCAN labels everything noise or merges everything. Remedies: feature selection, PCA (keep ~90%
variance), UMAP for density methods.

## Mixed or custom distances

Precompute a distance matrix (Gower for mixed types, edit distance for strings, DTW for series):
```python
db = DBSCAN(eps=0.15, min_samples=10, metric="precomputed").fit(D)     # D: n x n distances
```
O(n²) memory: practical up to ~20-30k points.

## Duplicates

Many identical rows (e.g. repeated GPS pings) inflate density. Deduplicate and pass counts as
`sample_weight` to `fit`: a point is core when the summed weight in its neighbourhood reaches min_samples.
