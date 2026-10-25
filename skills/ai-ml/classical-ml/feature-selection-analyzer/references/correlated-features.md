# Correlated Features

## Why they matter for selection

- **L1/lasso** picks one member of a correlated group, often arbitrarily, and the choice flips between folds.
- **Trees** split on whichever member is marginally better in each bootstrap/fold; importance is spread.
- **Permutation importance** under-states each member: shuffling one leaves its twin to carry the signal.
- **Prediction quality** is usually unaffected; interpretation and stability are.

## Finding groups

```python
import numpy as np
import pandas as pd
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

corr = X_train.select_dtypes("number").corr(method="spearman").abs()
dist = 1 - corr
link = hierarchy.ward(squareform(dist.values, checks=False))
cluster_ids = hierarchy.fcluster(link, t=0.3, criterion="distance")        # tune t; ~ |rho| > 0.7 groups
groups = pd.Series(cluster_ids, index=corr.columns).groupby(level=0).apply(list)
```
`filter_select.py --corr 0.9` does single-linkage grouping at a fixed |Spearman| threshold and keeps the member
with the strongest univariate signal.

## Choosing a representative

| Criterion | When |
|-----------|------|
| Strongest validated signal | prediction focus |
| Cheapest to compute / most available at serving | production focus |
| Most interpretable to stakeholders | explanation focus |
| A composite (sum, ratio, first principal component of the group) | keeps information from all members |

## Grouped permutation importance

```python
import numpy as np
from sklearn.metrics import average_precision_score

def grouped_permutation_importance(model, X, y, groups, n_repeats=10, seed=0):
    rng = np.random.default_rng(seed)
    base = average_precision_score(y, model.predict_proba(X)[:, 1])
    out = {}
    for name, cols in groups.items():
        drops = []
        for _ in range(n_repeats):
            Xp = X.copy()
            idx = rng.permutation(len(X))
            Xp[cols] = X[cols].values[idx]          # shuffle the whole group together, keeping its internal correlation
            drops.append(base - average_precision_score(y, model.predict_proba(Xp)[:, 1]))
        out[name] = (np.mean(drops), np.std(drops))
    return out
```

## Variance inflation factor (linear models)

VIF_j = 1 / (1 − R²_j), where R²_j regresses feature j on the others. VIF > 5-10 signals multicollinearity
that destabilises linear coefficients (not predictions). `statsmodels.stats.outliers_influence.variance_inflation_factor`.

## Practical policy

1. Remove exact and near-exact duplicates (|rho| > 0.98) always.
2. For interpretation-heavy models (scorecards, GLMs), keep one per group at |rho| > 0.8.
3. For GBMs used for prediction, keep groups unless serving cost matters; report group-level importance.
