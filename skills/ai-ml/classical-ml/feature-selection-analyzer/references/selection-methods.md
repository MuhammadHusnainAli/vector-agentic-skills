# Feature Selection Methods in scikit-learn

All selectors below are transformers: put them in a Pipeline after preprocessing so they are fitted on
training folds only.

## Filter

```python
from sklearn.feature_selection import (VarianceThreshold, SelectKBest, SelectPercentile, f_classif,
                                       mutual_info_classif, mutual_info_regression, chi2)

VarianceThreshold(threshold=0.0)                       # constant columns (after scaling, pick a small threshold)
SelectKBest(score_func=mutual_info_classif, k=30)      # non-linear univariate dependence; set random_state via partial
SelectPercentile(score_func=f_classif, percentile=20)  # linear univariate (ANOVA F)
SelectKBest(chi2, k=50)                                # non-negative features (counts, TF-IDF)
```
```python
from functools import partial
mi = partial(mutual_info_classif, random_state=0, discrete_features="auto")
selector = SelectKBest(mi, k=30)
```

## Embedded: L1 and elastic net

```python
from sklearn.feature_selection import SelectFromModel
from sklearn.linear_model import LogisticRegression, LassoCV, ElasticNetCV

l1 = SelectFromModel(LogisticRegression(penalty="l1", solver="saga", C=0.1, max_iter=5000))
lasso = SelectFromModel(LassoCV(cv=5, random_state=0))                         # regression
enet = SelectFromModel(ElasticNetCV(l1_ratio=[0.2, 0.5, 0.8], cv=5, random_state=0))
```
- Scale features first (the penalty is unit-dependent).
- L1 keeps one arbitrary member of a correlated group; elastic net spreads weight over the group (more stable).
- Inspect the regularisation path (`lasso_path`, `l1_min_c`) to see the order in which features enter.

## Embedded: tree importance

```python
from sklearn.ensemble import RandomForestClassifier
SelectFromModel(RandomForestClassifier(n_estimators=500, random_state=0), threshold="median")
```
Impurity-based importance (`feature_importances_`) is computed on training data and biased toward
high-cardinality and continuous features; use permutation importance on held-out data for decisions.

## Wrapper: RFE / RFECV

```python
from sklearn.feature_selection import RFECV
from sklearn.model_selection import StratifiedKFold
rfecv = RFECV(estimator=LogisticRegression(max_iter=2000), step=0.1, cv=StratifiedKFold(5),
              scoring="average_precision", min_features_to_select=5, n_jobs=-1)
rfecv.fit(X_train_prepped, y_train)
print(rfecv.n_features_, rfecv.cv_results_["mean_test_score"])
```
`step` as a fraction removes that share of features per round (much faster on wide data).

## Wrapper: sequential selection

```python
from sklearn.feature_selection import SequentialFeatureSelector
sfs = SequentialFeatureSelector(model, n_features_to_select="auto", tol=0.001, direction="forward",
                                scoring="average_precision", cv=5, n_jobs=-1)
```
Costs O(features²) model fits; use on tens, not thousands, of features.

## Permutation importance (held-out)

```python
from sklearn.inspection import permutation_importance
r = permutation_importance(fitted_pipe, X_valid, y_valid, scoring="average_precision", n_repeats=20,
                           random_state=0, n_jobs=-1)
order = r.importances_mean.argsort()[::-1]
for i in order[:20]:
    print(f"{X_valid.columns[i]:<25} {r.importances_mean[i]:.4f} ± {r.importances_std[i]:.4f}")
```
Features whose mean minus 2 std is <= 0 are not distinguishable from zero on this validation set.

## Boruta-style shadow features

```python
import numpy as np
rng = np.random.default_rng(0)
shadow = X_train.apply(lambda c: rng.permutation(c.values)).add_prefix("shadow_")
X_aug = pd.concat([X_train, shadow], axis=1)
# fit a tree model on X_aug; a real feature must beat the best shadow importance (repeat many times)
```
The `boruta` package (BorutaPy) implements the full iterative test.

## Stability selection

```python
import numpy as np
from sklearn.utils import resample

def stability_selection(X, y, make_selector, n_runs=50, frac=0.5, seed=0):
    rng = np.random.default_rng(seed)
    counts = np.zeros(X.shape[1])
    for _ in range(n_runs):
        idx = rng.choice(len(X), int(frac * len(X)), replace=False)
        sel = make_selector().fit(X.iloc[idx], y.iloc[idx])
        counts += sel.get_support()
    return counts / n_runs          # keep features with frequency >= 0.6-0.8
```
Write each run's importances in long format (run, feature, importance) and feed them to
`importance_stability.py`.
