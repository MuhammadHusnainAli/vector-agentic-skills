# Clustering Recipes

`X` is the preprocessed numeric matrix (scaled; see preprocessing-for-clustering.md).

## k-means

```python
from sklearn.cluster import KMeans, MiniBatchKMeans
km = KMeans(n_clusters=4, n_init="auto", random_state=0).fit(X)
labels, centres = km.labels_, km.cluster_centers_
mbk = MiniBatchKMeans(n_clusters=4, batch_size=4096, n_init="auto", random_state=0).fit(X)   # large data
```

## Gaussian mixture (soft assignments, BIC for k)

```python
from sklearn.mixture import GaussianMixture
bics = {k: GaussianMixture(n_components=k, covariance_type="full", n_init=3, random_state=0).fit(X).bic(X)
        for k in range(1, 9)}
best_k = min(bics, key=bics.get)
gm = GaussianMixture(n_components=best_k, covariance_type="full", n_init=5, random_state=0).fit(X)
proba = gm.predict_proba(X)            # membership probabilities
```
BIC spends components on outliers: on the blobs fixture (3 Gaussian blobs + 5% uniform noise) BIC keeps
falling up to k = 8, while the same data without the noise points has its minimum at k = 3. Remove or flag
noise first (HDBSCAN, robust z-scores), or read the BIC curve for its elbow (here the drop flattens after
k = 3-4) rather than its minimum.

## HDBSCAN (scikit-learn >= 1.3)

```python
from sklearn.cluster import HDBSCAN
hdb = HDBSCAN(min_cluster_size=15, min_samples=None, cluster_selection_method="eom").fit(X)
labels = hdb.labels_                   # -1 = noise
strength = hdb.probabilities_          # membership strength
```
`min_cluster_size` is the main knob (smallest group you care about); `min_samples` (defaults to it) controls
how conservative the noise labelling is. The standalone `hdbscan` package adds soft clustering and
`approximate_predict` for new points.

## DBSCAN

```python
from sklearn.cluster import DBSCAN
db = DBSCAN(eps=0.5, min_samples=2 * X.shape[1]).fit(X)     # eps from the k-distance knee (dbscan-parameter-tuner)
```

## Agglomerative and dendrograms

```python
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
agg = AgglomerativeClustering(n_clusters=4, linkage="ward").fit(X)
Z = linkage(X, method="ward")                  # scipy for the dendrogram
labels_at_cut = fcluster(Z, t=4, criterion="maxclust")
```
Linkages: `ward` (Euclidean, compact clusters), `average` / `complete` (any metric, `metric="cosine"` etc.),
`single` (chains; finds elongated shapes but is noise-sensitive).

## Spectral

```python
from sklearn.cluster import SpectralClustering
sc = SpectralClustering(n_clusters=3, affinity="nearest_neighbors", n_neighbors=15,
                        assign_labels="cluster_qr", random_state=0).fit(X)
```

## Mixed numeric + categorical: k-prototypes

```python
from kmodes.kprototypes import KPrototypes
Xm = df[num_cols + cat_cols].to_numpy(dtype=object)
Xm[:, :len(num_cols)] = StandardScaler().fit_transform(df[num_cols])      # scale the numeric part
kp = KPrototypes(n_clusters=4, init="Cao", n_init=5, random_state=0)
labels = kp.fit_predict(Xm, categorical=list(range(len(num_cols), len(num_cols) + len(cat_cols))))
```
`gamma` (default: half the numeric std) balances categorical mismatches against numeric distance.

## Mixed types: Gower distance

```python
import gower
from sklearn.cluster import HDBSCAN, AgglomerativeClustering
D = gower.gower_matrix(df[num_cols + cat_cols])                   # n x n, values in [0, 1]
labels = AgglomerativeClustering(n_clusters=4, metric="precomputed", linkage="average").fit_predict(D)
labels_hdb = HDBSCAN(metric="precomputed", min_cluster_size=15).fit_predict(D.astype("float64"))
```
O(n²) memory: sample or use k-prototypes beyond ~20k rows.

## Categorical only: k-modes

```python
from kmodes.kmodes import KModes
km = KModes(n_clusters=4, init="Huang", n_init=5, random_state=0).fit(df[cat_cols])
```

## Assigning new points

| Algorithm | New points |
|-----------|------------|
| k-means, GMM, BIRCH | `predict` |
| DBSCAN / HDBSCAN (sklearn) | no `predict`: train a classifier on the labels, or nearest core point; `hdbscan.approximate_predict` in the hdbscan package |
| Agglomerative, spectral | no `predict`: nearest centroid of the found clusters, or a classifier |
| k-prototypes / k-modes | `predict` |
