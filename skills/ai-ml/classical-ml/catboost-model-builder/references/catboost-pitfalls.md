# CatBoost Pitfalls

## Categorical values

| Problem | Error / symptom | Fix |
|---------|-----------------|-----|
| NaN in a categorical column | `CatBoostError: Invalid type for cat_feature ... =nan` | `astype(str)` after filling NaN with a token |
| Float-typed category codes (3.0) | `cat_features must be integer or string, real number values and NaN values should be converted to string` | cast to int or str |
| Encoding categoricals before CatBoost (one-hot, target) | lower accuracy, wasted CatBoost advantage | pass raw categories |
| Different string forms at inference ("3" vs "3.0") | silent mismatch, worse predictions | same casting code in training and serving |
| cat_features given as names that are not in the frame | `CatBoostError: ... is not in columns` | check spelling / column order |

## Validation and early stopping

- `use_best_model=True` requires `eval_set`.
- The overfitting detector uses `eval_metric`; with several eval sets, the **last** one drives stopping.
- Early stopping on the test set biases the reported test score: keep a separate validation split.
- `get_best_iteration()` is 0-based; `model.tree_count_` after `use_best_model` equals best iteration + 1.

## Feature importance types

| Type | Meaning | Use |
|------|---------|-----|
| `PredictionValuesChange` (default) | how much predictions change when the feature changes; no labels | fast overview |
| `LossFunctionChange` | loss increase when the feature is removed; needs a labelled pool | honest importance on validation data |
| `ShapValues` | per-row additive contributions; last column = expected value | local explanations, SHAP plots |
| `Interaction` | strength of feature pairs | interaction discovery |
| `PredictionDiff` | pairwise row differences | explain why two rows differ |

## SHAP shapes

- Binary/regression: `(n_rows, n_features + 1)`; the last column is the expected value (in raw/log-odds space
  for Logloss).
- Multiclass: `(n_rows, n_classes, n_features + 1)`.
- Sum of a row's SHAP values = raw prediction (`prediction_type="RawFormulaVal"`).

## Prediction types

`model.predict(X)` returns classes for classifiers; use `predict_proba` for probabilities, or
`predict(X, prediction_type="Probability" | "RawFormulaVal" | "Exponent")`. For Poisson/Tweedie regressors
`predict` returns the mean (exponent of the raw value).

## Determinism

Fix `random_seed`; results can still vary across thread counts, CPU vs GPU and versions. For reproducible
experiments fix `thread_count` and pin the CatBoost version.

## Common CatBoostError messages (1.2)

| Message | Cause |
|---------|-------|
| `only one of the parameters iterations, n_estimators, num_boost_round, num_trees should be initialized` | CB001 |
| `only one of the parameters learning_rate, eta should be initialized` | CB002 |
| `only one of the parameters scale_pos_weight, class_weights, auto_class_weights should be initialized` | CB003 |
| `bayesian bootstrap doesn't support 'subsample'` | CB004 |
| `bagging temperature available for bayesian bootstrap only` | CB004 |
| `Maximum tree depth is 16` | CB005 |
| `To employ param {'use_best_model': True} provide non-empty 'eval_set'` | CB006 |
