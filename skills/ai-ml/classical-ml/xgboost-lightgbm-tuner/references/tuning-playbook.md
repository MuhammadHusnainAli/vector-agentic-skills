# GBM Tuning Playbook

## Order of work

1. **Validation design first.** Folds that mirror deployment (time / group / stratified). Tuning on a leaky or
   unrepresentative split optimises the wrong thing.
2. **Baseline:** library defaults + early stopping. Record the score and the best iteration.
3. **Fix the learning rate** for search (0.05-0.1) and let early stopping choose the number of trees inside
   each fold.
4. **Capacity:** `num_leaves` (LightGBM) or `max_depth` (XGBoost), and the minimum leaf size
   (`min_child_samples` / `min_child_weight`). These matter most.
5. **Randomisation:** `subsample` (+ `subsample_freq=1` in LightGBM), `colsample_bytree`.
6. **Regularisation:** `reg_lambda`, `reg_alpha`, `min_split_gain` / `gamma`. Usually second-order.
7. **Final fit:** lower learning rate (e.g. half), more trees (early stopping on a validation split, or
   best_iteration x ratio x 1.1), train on all training data.
8. **Confirm** on the untouched holdout; compare with the untuned baseline.

## Typical ranges

| Parameter | LightGBM | XGBoost | Notes |
|-----------|----------|---------|-------|
| learning rate | 0.01-0.1 | 0.01-0.1 | fixed during search; lower for the final model |
| capacity | num_leaves 7-255 (log) | max_depth 3-10 | LightGBM: keep num_leaves < 2^max_depth if max_depth is set |
| min leaf size | min_child_samples 5-1000 (log, ~0.1-1% of rows) | min_child_weight 1-100 (log) | raise for small/noisy data and rare positives |
| row sampling | subsample 0.5-1.0, subsample_freq 1 | subsample 0.5-1.0 | |
| column sampling | colsample_bytree 0.3-1.0 | colsample_bytree 0.3-1.0 | lower for many correlated features |
| L2 | reg_lambda 1e-3-30 (log) | reg_lambda 1e-3-30 (log) | |
| L1 | reg_alpha 1e-3-10 (log) | reg_alpha 1e-3-10 (log) | helps with many useless features |
| split gain | min_split_gain 0-1 | gamma 0-5 | scale depends on the loss |
| bins | max_bin 63-511 | max_bin 64-512 | more bins: finer splits, slower |

`gbm_param_advisor.py` scales the leaf-size range to the row count and the positive count.

## Learning rate vs trees

The product (learning_rate x n_trees) is roughly constant for a given fit quality. Halving the learning rate
needs about twice the trees and usually gains a little accuracy. Searching at 0.05-0.1 and refitting at a
lower rate is the standard compromise.

## Early stopping inside CV

```python
import lightgbm as lgb
from sklearn.model_selection import StratifiedKFold
scores, iters = [], []
for tr, va in StratifiedKFold(5, shuffle=True, random_state=0).split(X, y):
    m = lgb.LGBMClassifier(**params, n_estimators=10000)
    m.fit(X.iloc[tr], y.iloc[tr], eval_set=[(X.iloc[va], y.iloc[va])], eval_metric="auc",
          callbacks=[lgb.early_stopping(200, verbose=False)])
    scores.append(m.best_score_["valid_0"]["auc"]); iters.append(m.best_iteration_)
```
Early stopping on the same fold you score on is slightly optimistic (the stopping round is chosen on it).
For a strict estimate carve an inner validation split from the training fold, or accept the small bias and
confirm on a holdout.

## Search method

| Budget | Method |
|--------|--------|
| < 30 trials | random search over the space above |
| 30-200 trials | TPE (Optuna) with pruning on intermediate CV scores |
| very expensive fits | successive halving / Hyperband on rows or trees |

See optuna-study-writer and hyperparameter-search-planner.

## Small data (< ~5k rows)

- Raise `min_child_samples` (20-100), lower `num_leaves` (7-31) or `max_depth` (3-5).
- Strong subsampling and regularisation; repeated CV to reduce noise.
- Compare against logistic regression and CatBoost: small data is where GBM defaults lose.

## Large data (> ~5M rows)

- Tune on a sample (10-20%), then refit on all data with more trees.
- `max_bin` 255 default is fine; GPU (`device="cuda"` in XGBoost, `device_type="gpu"` in LightGBM) for big jobs.
- Watch memory: `free_raw_data`, Dataset construction once, `colsample_bytree < 1`.

## When tuning does not help

Typical gains over good defaults are 1-3% relative. If tuning moves nothing, the bottleneck is features,
labels or the validation design, not hyperparameters.
