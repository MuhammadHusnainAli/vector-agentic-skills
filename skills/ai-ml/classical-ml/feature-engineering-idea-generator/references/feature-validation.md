# Validating New Features

## Group ablation

Add features in meaningful groups and compare on identical folds:

```python
import numpy as np
from sklearn.model_selection import cross_val_score, StratifiedKFold   # or TimeSeriesSplit / GroupKFold

groups = {
    "base": base_cols,
    "+dates": base_cols + date_cols,
    "+rates": base_cols + date_cols + rate_cols,
    "+entity_aggs": base_cols + date_cols + rate_cols + agg_cols,
}
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
results = {}
for name, cols in groups.items():
    s = cross_val_score(make_model(cols), X[cols], y, cv=cv, scoring="average_precision")
    results[name] = s
    print(f"{name:<14} {s.mean():.4f} ± {s.std():.4f}")
```

Keep a group when the gain is larger than the noise: compare fold-by-fold (paired) differences, not two
means. A simple rule: the mean paired gain > 2 x its standard error, and positive in most folds. For a formal
test use the corrected resampled t-test (ml-model-comparison-reporter).

## Same folds, same budget

- Identical CV splits for every variant (pass the same `cv` object or precomputed indices).
- Same model and hyperparameters; re-tuning per variant confounds feature value with tuning effort.
- Same preprocessing; new features go through the same pipeline.

## Stability over time

```python
for period, part in valid.groupby(valid["score_date"].dt.to_period("Q")):
    print(period, metric(part.y, model.predict_proba(part[cols])[:, 1]))
```
And compare SHAP importance of each new feature by quarter. A feature whose importance or effect direction
changes sharply between periods will hurt after deployment.

## Leakage checks for new features

| Check | Red flag |
|-------|----------|
| Single-feature AUC | > 0.9 |
| Gain much larger than domain experts expect | investigate before keeping |
| Feature better on old periods than recent ones | built from overwritten / backfilled data |
| Train CV much better than the time holdout | leak through aggregates or encoding |
| Feature uses the current row in its own aggregate | missing `shift()` or `closed="left"` |

Run target-leakage-detector on the final feature table.

## Cost and serving

For each kept feature record: compute cost, freshness required, online availability, and the fallback when
missing. A feature that improves offline AUC by 0.002 but needs a real-time stream is rarely worth it.

## Feature documentation template

| Field | Example |
|-------|---------|
| Name | `card_amount_vs_mean_prior_30d` |
| Definition | amount / mean amount of the card's transactions in the 30 days before this one |
| Source | payments.transactions |
| As-of logic | events strictly before the transaction timestamp |
| Freshness | real-time (online store, < 1 s) |
| Missing when | card has no prior transactions -> NaN (model handles) |
| Added | 2026-10-24, validated +0.012 PR-AUC (paired CI 0.006-0.018) |
| Owner | fraud-ds |
