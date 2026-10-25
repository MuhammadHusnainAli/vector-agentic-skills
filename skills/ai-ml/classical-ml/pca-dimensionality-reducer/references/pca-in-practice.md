# PCA in Practice

## scikit-learn PCA

```python
from sklearn.decomposition import PCA
pca = PCA(n_components=0.95, svd_solver="full", whiten=False, random_state=0).fit(Z_train)
scores = pca.transform(Z_test)
loadings = pca.components_                         # (k, n_features): rows are components
recon = pca.inverse_transform(scores)              # back to the standardised feature space
```
- `n_components`: int, float in (0, 1) (variance share, needs `svd_solver="full"` or `"auto"`), or `"mle"`.
- `svd_solver="randomized"` for large dense data and small k.
- `whiten=True` scales components to unit variance (useful before some models / ICA; loses relative scale).

## Loadings vs correlations

`components_` are unit vectors in the standardised space. Correlation between feature j and component i is
`components_[i, j] * sqrt(explained_variance_[i])` (for standardised data), which is easier to read on a common
scale.

## Variants

| Tool | When |
|------|------|
| `IncrementalPCA(n_components, batch_size)` | data does not fit in memory; `partial_fit` per chunk |
| `TruncatedSVD(n_components)` | sparse matrices (TF-IDF: latent semantic analysis); no centring |
| `KernelPCA(kernel="rbf", gamma=...)` | non-linear structure; no straightforward inverse; O(n²) |
| `SparsePCA` / `MiniBatchSparsePCA` | components with few non-zero loadings (interpretability) |
| `FactorAnalysis` (+ `rotation="varimax"`) | latent factors with feature-specific noise; interpretation |
| `FastICA` | independent (non-Gaussian) sources, e.g. signal separation |

## PCA before other methods

| Downstream | Effect |
|------------|--------|
| Linear / logistic regression | removes collinearity; principal components regression; loses direct interpretability |
| k-NN, k-means, DBSCAN | reduces distance concentration and noise; speeds up |
| Gradient boosting / random forest | usually no gain; may hurt (trees use individual features) |
| UMAP / t-SNE | common to reduce to ~50 components first for speed and noise |

## Pitfalls

| Pitfall | Fix |
|---------|-----|
| No scaling with mixed units | standardise |
| PCA fitted on all data before CV | put it in the Pipeline |
| Interpreting late components | usually noise; check parallel analysis |
| Comparing components across refits | signs (and order for close eigenvalues) can flip; align by correlation |
| Categorical one-hot columns in PCA | use MCA / FAMD (prince package) for categorical / mixed data |
| Outliers driving components | robust scaling, or robust PCA; check leverage |
| Expecting PCA to keep predictive signal | variance ≠ relevance; supervised alternatives: PLS, feature selection |
