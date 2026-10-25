# Nested CV and the Variance of CV Estimates

## Nested CV

```python
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate
inner = StratifiedKFold(5, shuffle=True, random_state=1)
outer = StratifiedKFold(5, shuffle=True, random_state=2)
search = GridSearchCV(pipe, param_grid, cv=inner, scoring="average_precision", n_jobs=-1)
res = cross_validate(search, X, y, cv=outer, scoring="average_precision", return_estimator=True)
print(res["test_score"].mean(), res["test_score"].std())
print([est.best_params_ for est in res["estimator"]])        # stability of the chosen hyperparameters
```
Rules:
- The inner splitter follows the same constraints as the outer (groups, time order). With groups, the inner
  search also needs the groups, and `cross_validate(..., groups=g)` gives them only to the outer splitter
  (the inner `GroupKFold` then fails with "The 'groups' parameter should not be None"). Use metadata routing
  (scikit-learn >= 1.4), verified on 1.9:
  ```python
  import sklearn
  sklearn.set_config(enable_metadata_routing=True)
  search = GridSearchCV(pipe, param_grid, cv=GroupKFold(5), scoring="roc_auc")
  res = cross_validate(search, X, y, cv=StratifiedGroupKFold(5, shuffle=True, random_state=0),
                       scoring="roc_auc", params={"groups": groups})      # routed to outer split and inner search
  ```
- Report the outer score; the inner `best_score_` is optimistically biased.
- Final model: run the search on all data (non-nested) and deploy that; the nested score estimates how good
  "this procedure" is.

## Bias and variance of CV estimates

| Choice | Bias | Variance | Cost |
|--------|------|----------|------|
| Fewer folds (3) | pessimistic (smaller training sets) | lower per split, fewer splits | low |
| More folds (10) | less pessimistic | fold scores correlated | higher |
| Leave-one-out | nearly unbiased | high | n fits |
| Repeats | same | lower (averaged partitions) | x repeats |

The standard error of a CV mean is **not** sd/sqrt(k): folds share training data. Use the corrected variance
(Nadeau-Bengio, see ml-model-comparison-reporter) when testing differences, or repeated CV with the spread across
repeats as a rough indicator.

## Confidence interval for a single model's CV score

Practical options:
- Repeated CV: mean ± 2 x sd of the repeat-level means.
- Bootstrap the pooled out-of-fold predictions (`cross_val_predict`) for metric CIs.
- A final holdout with a bootstrap CI as the headline number.

## Out-of-fold predictions

```python
from sklearn.model_selection import cross_val_predict
oof = cross_val_predict(pipe, X, y, cv=outer, method="predict_proba")[:, 1]
```
Useful for error analysis, calibration plots, stacking and threshold choice; note each prediction comes from a
slightly different model.
