# Selection Bias and Nested Cross-Validation

## The bias, demonstrated on pure noise

```python
import numpy as np
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import make_pipeline

rng = np.random.default_rng(0)
X = rng.normal(size=(100, 5000))              # 5,000 noise features
y = rng.integers(0, 2, 100)                   # random labels: no signal exists

# WRONG: select on all data, then cross-validate the reduced model
top = SelectKBest(f_classif, k=20).fit(X, y).get_support()
print("wrong:", cross_val_score(LogisticRegression(max_iter=1000), X[:, top], y, cv=5, scoring="roc_auc").mean())

# RIGHT: selection inside the pipeline, refitted per fold
pipe = make_pipeline(SelectKBest(f_classif, k=20), LogisticRegression(max_iter=1000))
print("right:", cross_val_score(pipe, X, y, cv=5, scoring="roc_auc").mean())
```
Typical output: wrong ≈ 0.9+, right ≈ 0.5. The "wrong" model learned the labels of the test folds through
the selection step.

## Nested CV when selection is tuned

When `k`, the L1 strength or the RFE stopping point is chosen by CV, that choice must also be evaluated on
data it did not see:

```python
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score

inner = StratifiedKFold(5, shuffle=True, random_state=1)
outer = StratifiedKFold(5, shuffle=True, random_state=2)
search = GridSearchCV(pipe, {"selectkbest__k": [10, 20, 50, 100]}, cv=inner, scoring="roc_auc")
scores = cross_val_score(search, X, y, cv=outer, scoring="roc_auc")     # honest estimate of the whole procedure
```
Report the outer score; then refit `search` on all data to get the final model and selected features.

## Which steps count as "selection"

Anything that looks at the target to decide which columns to keep:
- univariate tests, mutual information, correlation with the target;
- L1 / tree / permutation importance thresholds;
- RFE, sequential selection, Boruta;
- "I looked at the SHAP plot on all data and dropped the bottom 50%".

Unsupervised steps (variance threshold, missingness, correlation between features) do not use the target,
so their leakage is limited to distribution statistics; still, fitting them inside the pipeline costs nothing.

## Time-based validation of a feature set

Random folds reward features that capture period-specific effects. Validate the final feature set on a
later time window: features that help on random folds but hurt on the future window should be dropped or
rebuilt.

```python
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5, gap=0)
```

## Reporting

State the procedure, not just the selected list: "Features selected by L1-logistic (C tuned in inner 5-fold
CV) within each of 5 outer folds; outer PR-AUC 0.41 ± 0.03; 18 features selected in >= 80% of outer folds."
