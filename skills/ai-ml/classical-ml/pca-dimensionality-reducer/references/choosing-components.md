# Choosing the Number of Components

## Explained variance

Eigenvalue λ_i of the covariance (or correlation) matrix = variance along component i. Explained ratio
λ_i / Σλ. Cumulative share: keep the smallest k reaching a target (80% exploratory, 90-95% compression).
```python
from sklearn.decomposition import PCA
p = PCA().fit(Z)                                   # Z standardised
cum = p.explained_variance_ratio_.cumsum()
k95 = int((cum >= 0.95).argmax()) + 1
```

## Scree plot / elbow

Plot λ_i against i; keep components before the curve levels off. Subjective; useful as a picture.

## Kaiser criterion

On the correlation matrix keep λ > 1 (a component explains more than one original standardised variable).
Tends to keep too many with many variables and too few with few.

## Parallel analysis (Horn 1965)

Compare each eigenvalue with the distribution of the same-rank eigenvalue from data with no correlation
structure: shuffle each column independently (keeps the marginals) or simulate normal data of the same shape.
Keep components while λ_i exceeds the 95th percentile of the random λ_i. The most reliable simple rule for
"how many real dimensions" (implemented in `pca_report.py`).

## Velicer's MAP

Minimum average partial correlation: partial out the first m components and find the m minimising the average
squared partial correlation. Available in R (`psych::vss`); conservative.

## Broken-stick

Keep component i if its share exceeds the expected share of the i-th longest piece of a randomly broken stick:
`b_i = (1/p) Σ_{k=i..p} 1/k`.

## Downstream cross-validation

When PCA is a preprocessing step, treat k as a hyperparameter:
```python
from sklearn.model_selection import GridSearchCV
search = GridSearchCV(make_pipeline(StandardScaler(), PCA(), Ridge()),
                      {"pca__n_components": [2, 4, 8, 16, 32]}, cv=5, scoring="neg_mean_absolute_error")
```

## Probabilistic PCA likelihood

`PCA(n_components="mle")` (Minka's MLE) or `PCA().score(X)` (average log-likelihood under probabilistic PCA) on
held-out data can choose k.

## Which rule for which purpose

| Purpose | Rule |
|---------|------|
| How many underlying factors? | parallel analysis (and MAP) |
| Compress with little information loss | cumulative variance 90-99% |
| Visualise | 2-3 components (check their cumulative share) |
| Model input | CV over k |
