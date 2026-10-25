# Cross-Validation and Search with Pipelines

## cross_validate

```python
from sklearn.model_selection import cross_validate, StratifiedKFold
res = cross_validate(pipe, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0),
                     scoring={"auc": "roc_auc", "ap": "average_precision", "ll": "neg_log_loss"},
                     return_train_score=True, return_estimator=False, n_jobs=-1)
for k in ("auc", "ap", "ll"):
    print(k, res[f"test_{k}"].mean().round(4), "+/-", res[f"test_{k}"].std().round(4),
          "train", res[f"train_{k}"].mean().round(4))
```
`cross_val_predict` gives out-of-fold predictions for every row (for error analysis and calibration plots);
do not compute a single "CV score" from them for non-additive metrics without care.

## Parameter names

`<step>__<param>` recursively: `prep__num__simpleimputer__strategy`, `clf__C`,
`prep__cat__onehotencoder__min_frequency`. Inspect with `pipe.get_params().keys()`.

Search over whole steps:
```python
param_grid = [
    {"clf": [LogisticRegression(max_iter=5000)], "clf__C": [0.01, 0.1, 1, 10]},
    {"clf": [HistGradientBoostingClassifier(random_state=0)], "clf__learning_rate": [0.05, 0.1]},
]
```

## Searches

| Search | Use |
|--------|-----|
| `GridSearchCV` | <= ~50 combinations, discrete choices |
| `RandomizedSearchCV` | continuous ranges (`scipy.stats.loguniform`), 20-100 iterations |
| `HalvingRandomSearchCV` / `HalvingGridSearchCV` | many candidates; successive halving on samples (`from sklearn.experimental import enable_halving_search_cv` first) |
| Optuna / other Bayesian | expensive models, conditional spaces (see optuna-study-writer) |

`refit=` chooses the metric for the final model when `scoring` is a dict; `refit=callable` implements a
one-standard-error rule.

## Nested CV

```python
inner = StratifiedKFold(5, shuffle=True, random_state=1)
outer = StratifiedKFold(5, shuffle=True, random_state=2)
search = RandomizedSearchCV(pipe, dist, n_iter=30, cv=inner, scoring="average_precision", random_state=0)
outer_scores = cross_validate(search, X, y, cv=outer, scoring="average_precision")["test_score"]
```
The outer score estimates the performance of "run this search, take the best"; `search.best_score_` alone
is biased upward.

## Groups and metadata routing

```python
from sklearn.model_selection import StratifiedGroupKFold
cv = StratifiedGroupKFold(5, shuffle=True, random_state=0)
cross_validate(pipe, X, y, cv=cv, groups=customer_ids)
search.fit(X, y, groups=customer_ids)          # routed to the search's cv
```
Sample weights and other per-row metadata use metadata routing (scikit-learn >= 1.4,
`sklearn.set_config(enable_metadata_routing=True)` and `.set_fit_request(sample_weight=True)` on consumers).

## Time series

```python
from sklearn.model_selection import TimeSeriesSplit
cv = TimeSeriesSplit(n_splits=5, gap=30, test_size=None)    # rows must be sorted by time
```
`gap` drops rows between train and test (use the label window length when labels look ahead).

## Threshold tuning

```python
from sklearn.model_selection import TunedThresholdClassifierCV   # sklearn >= 1.5
tuned = TunedThresholdClassifierCV(pipe, scoring="f1", cv=5).fit(X, y)
print(tuned.best_threshold_)
```
For cost-based thresholds pass a scorer built with `make_scorer` on a cost function.

## Performance tips

- `n_jobs=-1` on the search or CV, not on both it and the estimator.
- `memory=` caching when only model parameters vary.
- `HistGradientBoosting*` instead of `GradientBoosting*` for > 10k rows.
- `error_score="raise"` while developing, so failures surface instead of NaN scores.
