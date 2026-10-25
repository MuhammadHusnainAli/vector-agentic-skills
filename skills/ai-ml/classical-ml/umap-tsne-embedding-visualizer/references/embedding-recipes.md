# Embedding Recipes

## Standard 2-D maps

```python
import numpy as np
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
import umap

Z = StandardScaler().fit_transform(X)
if Z.shape[1] > 50:
    Z = PCA(n_components=50, random_state=0).fit_transform(Z)
Y_pca = PCA(n_components=2).fit_transform(Z)
Y_tsne = TSNE(perplexity=30, init="pca", learning_rate="auto", max_iter=1000, random_state=0).fit_transform(Z)
Y_umap = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=0).fit_transform(Z)
```

## Text / image embeddings (cosine)

```python
from sklearn.preprocessing import normalize
E = normalize(embeddings)                               # unit vectors
Y = umap.UMAP(n_neighbors=30, min_dist=0.05, metric="cosine", random_state=0).fit_transform(E)
```

## UMAP as input to clustering

```python
from sklearn.cluster import HDBSCAN
U = umap.UMAP(n_components=10, n_neighbors=30, min_dist=0.0, metric="cosine", random_state=0).fit_transform(E)
labels = HDBSCAN(min_cluster_size=25).fit_predict(U)
Y2 = umap.UMAP(n_components=2, n_neighbors=30, min_dist=0.1, metric="cosine", random_state=0).fit_transform(E)
# plot Y2 coloured by labels; the clustering itself happened in 10-D
```

## Placing new points on an existing map

```python
reducer = umap.UMAP(n_neighbors=15, random_state=0).fit(Z_train)
Y_new = reducer.transform(Z_new)                       # same scaler / PCA applied to Z_new first
```
t-SNE: use openTSNE (`TSNEEmbedding.transform`), or retrain.

## Supervised / semi-supervised UMAP

```python
Y_sup = umap.UMAP(random_state=0).fit_transform(Z, y=labels)          # -1 for unlabelled points
```
Use for presentation of known groups, never as evidence that the groups are separable.

## Plot helpers

```python
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(6, 6))
for lv in np.unique(labels):
    m = labels == lv
    ax.scatter(Y[m, 0], Y[m, 1], s=4, alpha=0.7, label=str(lv))
ax.set_xticks([]); ax.set_yticks([]); ax.legend(markerscale=4)
ax.set_title("UMAP (n_neighbors=15, min_dist=0.1, seed 0) - sizes/distances not to scale")
```
For large data use `alpha=0.2-0.5`, `s=1`, or datashader. Interactive: plotly `scatter` with hover text (IDs,
key features) helps inspection.

## Faithfulness

```python
from sklearn.manifold import trustworthiness
trustworthiness(Z, Y, n_neighbors=10)            # same as embedding_trust.py
```
