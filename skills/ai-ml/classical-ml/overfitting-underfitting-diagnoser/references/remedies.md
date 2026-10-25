# Remedies

## Overfitting

| Model | Strongest levers first |
|-------|------------------------|
| LightGBM | early stopping; `min_child_samples` up; `num_leaves` down; `feature_fraction`/`bagging_fraction` < 1 (+ `bagging_freq`); `lambda_l2`; `min_gain_to_split`; `max_bin` down; lower learning rate + more rounds |
| XGBoost | early stopping; `max_depth` down; `min_child_weight` up; `subsample`, `colsample_bytree` < 1; `reg_lambda`, `gamma` (min split loss) up |
| CatBoost | early stopping (`od_type="Iter"`, `od_wait`); `depth` down; `l2_leaf_reg` up; `random_strength` up; ordered boosting on small data |
| HistGradientBoosting | `early_stopping=True`; `max_leaf_nodes` down; `min_samples_leaf` up; `l2_regularization` |
| Random forest / extra trees | `min_samples_leaf` up; `max_features` down; `max_depth`; more trees only reduce variance from randomness |
| Decision tree | `ccp_alpha` (cost-complexity pruning) via the 1-SE rule; `max_depth`; `min_samples_leaf` |
| Linear / logistic | lower `C` / higher `alpha`; L1 or elastic net to drop features; fewer one-hot levels (`min_frequency`) |
| SVM | lower `C`; lower RBF `gamma` |
| k-NN | larger `n_neighbors`; feature selection (distance concentration in high dimensions) |
| MLP | early stopping; weight decay; dropout; smaller layers; more data/augmentation |

Feature-side remedies for any model: drop ID-like and high-cardinality columns, target-encode with
cross-fitting, remove features that only work on training rows (leakage), aggregate sparse categories.

## Underfitting

| Model | Levers |
|-------|--------|
| Boosting | more rounds (or higher learning rate); `num_leaves`/`max_depth` up; smaller `min_child_samples`; less L2 |
| Random forest | `min_samples_leaf=1`; higher `max_features` |
| Linear / logistic | splines (`SplineTransformer`), interactions, log/ratio transforms, weaker penalty, or a tree model |
| SVM | higher `C`, higher `gamma` |
| k-NN | smaller `n_neighbors`, scaled features |
| Any | new informative features; check label noise (inter-annotator agreement); check the target definition |

## Early-stopping set-ups

```python
# LightGBM
m = lgb.LGBMClassifier(n_estimators=10000, learning_rate=0.03)
m.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], callbacks=[lgb.early_stopping(100), lgb.log_evaluation(0)])
# XGBoost (>= 2.0: constructor argument)
m = xgb.XGBClassifier(n_estimators=10000, learning_rate=0.03, early_stopping_rounds=100)
m.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
# CatBoost
m = CatBoostClassifier(iterations=10000, learning_rate=0.03, od_type="Iter", od_wait=100)
m.fit(X_tr, y_tr, eval_set=(X_va, y_va), use_best_model=True)
# scikit-learn
HistGradientBoostingClassifier(early_stopping=True, validation_fraction=0.1, n_iter_no_change=20)
```
- The early-stopping set must not be the test set; inside CV use each fold's validation split, then refit on
  all data with about the mean best iteration x (1 + 1/k) for k folds.
- Patience: about 5-10% of the expected rounds, never below 10 for noisy metrics.
- Stop on the metric you care about (`first_metric_only=True` in LightGBM when several are logged).

## Confirming a fix

| Fix | Curve that confirms it |
|-----|------------------------|
| Regularisation | gap at the best iteration shrinks, best validation unchanged or better |
| Early stopping | final validation = best validation; fewer rounds |
| More capacity | training score up, validation up; the gap may widen a little |
| New features | validation up at the same complexity; the validation curve's peak moves up |
| Simpler setting via 1-SE | holdout score within noise of the best, model smaller/faster |
