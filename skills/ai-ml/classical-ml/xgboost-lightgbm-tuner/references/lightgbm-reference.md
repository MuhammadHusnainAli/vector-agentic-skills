# LightGBM Reference

## scikit-learn API

```python
import lightgbm as lgb
clf = lgb.LGBMClassifier(
    objective="binary", learning_rate=0.05, n_estimators=10000,
    num_leaves=31, max_depth=-1, min_child_samples=50,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
    reg_lambda=1.0, reg_alpha=0.0, min_split_gain=0.0,
    max_bin=255, random_state=0, n_jobs=-1, verbose=-1)
clf.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], eval_metric=["auc", "binary_logloss"],
        callbacks=[lgb.early_stopping(200, first_metric_only=True), lgb.log_evaluation(100)])
print(clf.best_iteration_, clf.best_score_)
proba = clf.predict_proba(X_te, num_iteration=clf.best_iteration_)[:, 1]
```
LightGBM >= 4.7 prefers `eval_X=` / `eval_y=` over `eval_set=` in the scikit-learn API (`eval_set` still works
with a deprecation warning). With early stopping, predictions use the best iteration automatically.

## Native API

```python
dtrain = lgb.Dataset(X_tr, y_tr, categorical_feature=cat_cols, free_raw_data=False)
dvalid = lgb.Dataset(X_va, y_va, reference=dtrain)
booster = lgb.train(params, dtrain, num_boost_round=10000, valid_sets=[dtrain, dvalid],
                    valid_names=["train", "valid"],
                    callbacks=[lgb.early_stopping(200), lgb.log_evaluation(100)])
cv = lgb.cv(params, dtrain, num_boost_round=10000, nfold=5, stratified=True, seed=0,
            callbacks=[lgb.early_stopping(200)])                # returns mean/stdv per round
```

## Key parameters

| Parameter | Effect |
|-----------|--------|
| `num_leaves` | main capacity knob (leaf-wise growth) |
| `max_depth` | cap depth (-1 = no limit); set when num_leaves is large to avoid very deep trees |
| `min_child_samples` (`min_data_in_leaf`) | minimum rows per leaf: the most important regulariser on small data |
| `min_sum_hessian_in_leaf` | minimum hessian; matters for skewed probabilities |
| `subsample` + `subsample_freq` | bagging; `subsample_freq=0` disables it even if subsample < 1 |
| `colsample_bytree` / `feature_fraction_bynode` | feature sampling per tree / per node |
| `reg_lambda`, `reg_alpha` | L2 / L1 on leaf values |
| `min_split_gain` | minimum loss reduction to split |
| `cat_smooth`, `min_data_per_group`, `max_cat_threshold`, `cat_l2` | categorical split regularisation |
| `is_unbalance` / `scale_pos_weight` | class weighting (one or the other) |
| `boosting_type` | `"gbdt"` default; `"dart"` (dropout; no early stopping), `"rf"` |
| `linear_tree` | linear models in leaves (smooth extrapolation) |
| `extra_trees` | random thresholds: extra regularisation |
| `path_smooth` | smooths leaf values toward the parent |
| `deterministic=True` + `force_row_wise=True` | reproducibility across runs |

## Categoricals

Pass pandas `category` columns (automatic) or `categorical_feature=[...]`. Category codes must be identical
between training and prediction: store the categories. High-cardinality categoricals overfit; raise
`cat_smooth` and `min_data_per_group` or switch to target/frequency encoding.

## Objectives and metrics

`binary`, `multiclass` (`num_class`), `regression`, `regression_l1`, `huber`, `quantile` (`alpha`),
`poisson`, `gamma`, `tweedie` (`tweedie_variance_power`), `lambdarank` / `rank_xendcg` (ranking),
`cross_entropy`. Metrics: `auc`, `average_precision`, `binary_logloss`, `multi_logloss`, `l1`, `l2`, `rmse`,
`ndcg` (`eval_at`), `map`.

## Common problems

| Problem | Fix |
|---------|-----|
| `[Warning] No further splits with positive gain` | trees cannot split: lower min_child_samples, check features |
| Overfits fast (best iteration < 50) | lower learning rate, raise min_child_samples, lower num_leaves |
| Results differ run to run | `random_state`, `deterministic=True`, fixed `n_jobs` |
| Validation metric worse than expected after reload | predict with the saved best iteration; same category mapping |
| Memory blow-up | lower `max_bin`, `colsample_bytree`, construct Dataset once |
