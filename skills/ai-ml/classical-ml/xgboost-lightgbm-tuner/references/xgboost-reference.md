# XGBoost Reference

## scikit-learn API (XGBoost >= 2)

```python
import xgboost as xgb
clf = xgb.XGBClassifier(
    objective="binary:logistic", eval_metric=["aucpr", "logloss"], tree_method="hist",
    learning_rate=0.05, n_estimators=10000, max_depth=6, min_child_weight=5,
    subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, reg_alpha=0.0, gamma=0.0,
    early_stopping_rounds=200, random_state=0, n_jobs=-1)
clf.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=200)
print(clf.best_iteration, clf.best_score)
proba = clf.predict_proba(X_te)[:, 1]          # uses best_iteration automatically when early stopping was on
```
In XGBoost 2+/3, `early_stopping_rounds`, `eval_metric` and `callbacks` belong in the **constructor**, not in
`fit()`. The last metric in `eval_metric` drives early stopping.

## Native API

```python
dtrain = xgb.DMatrix(X_tr, label=y_tr, enable_categorical=True)
dvalid = xgb.DMatrix(X_va, label=y_va, enable_categorical=True)
booster = xgb.train(params, dtrain, num_boost_round=10000, evals=[(dtrain, "train"), (dvalid, "valid")],
                    early_stopping_rounds=200, verbose_eval=200)
cv = xgb.cv(params, dtrain, num_boost_round=10000, nfold=5, stratified=True, early_stopping_rounds=200, seed=0)
```

## Key parameters

| Parameter | Effect |
|-----------|--------|
| `max_depth` | depth-wise growth capacity (default 6) |
| `grow_policy="lossguide"` + `max_leaves` | leaf-wise growth like LightGBM |
| `min_child_weight` | minimum hessian sum per child (≈ rows for squared error; p(1-p)·rows for logloss) |
| `gamma` (`min_split_loss`) | minimum loss reduction to split |
| `subsample`, `colsample_bytree` / `bylevel` / `bynode` | sampling |
| `reg_lambda` (default 1), `reg_alpha` | L2 / L1 on leaf weights |
| `max_delta_step` | caps leaf updates; helps extreme imbalance with logloss |
| `scale_pos_weight` | weight for positives (≈ negatives/positives) |
| `tree_method="hist"` | default fast histogram method; `device="cuda"` for GPU |
| `max_cat_to_onehot` | one-hot style splits for categoricals with few levels |
| `monotone_constraints`, `interaction_constraints` | domain constraints |
| `multi_strategy="multi_output_tree"` | one tree for all outputs (multi-target) |

## Categoricals

`enable_categorical=True` with pandas `category` dtype (or DMatrix feature types). Keep identical category
sets between train and inference.

## Objectives and metrics

`binary:logistic`, `multi:softprob` (`num_class`), `reg:squarederror`, `reg:absoluteerror`,
`reg:pseudohubererror`, `reg:quantileerror` (`quantile_alpha`, multi-quantile), `count:poisson`, `reg:gamma`,
`reg:tweedie`, `rank:ndcg` / `rank:pairwise`, `survival:cox`, `survival:aft`. Metrics: `auc`, `aucpr`,
`logloss`, `error`, `rmse`, `mae`, `ndcg@k`, `map@k`.

## Common problems

| Problem | Fix |
|---------|-----|
| `TypeError: fit() got an unexpected keyword argument 'early_stopping_rounds'` | move it to the constructor (XGBoost 2+) |
| Categorical error with object dtype | convert to `category` and set `enable_categorical=True` |
| Probabilities poorly calibrated after `scale_pos_weight` | expected: recalibrate or do not weight |
| Very slow on wide sparse data | `tree_method="hist"`, `colsample_bytree < 1`, sparse CSR input |
| Different results on GPU vs CPU | small numeric differences are normal; fix seeds and versions |
