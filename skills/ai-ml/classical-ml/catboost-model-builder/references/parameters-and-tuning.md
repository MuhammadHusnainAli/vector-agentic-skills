# CatBoost Parameters and Tuning

## Tuning order

1. Overfitting detector on a validation set (`od_type="Iter"`, `od_wait=200`, `use_best_model=True`).
2. `learning_rate` 0.03-0.1 with enough `iterations` (early stopping decides).
3. `depth` 4-10.
4. `l2_leaf_reg` 1-10 (log).
5. `random_strength` 0.5-10, `bagging_temperature` 0-1 (Bayesian) or `bootstrap_type="Bernoulli"` +
   `subsample` 0.6-0.9.
6. Categorical knobs if categoricals dominate: `one_hot_max_size`, `max_ctr_complexity`.
7. Refit with a lower learning rate and the scaled iteration count.

CatBoost defaults are strong; a modest search (30-60 trials) is usually enough.

## Optuna space

```python
def objective(trial):
    params = {
        "loss_function": "Logloss", "eval_metric": "AUC", "iterations": 3000, "od_type": "Iter", "od_wait": 150,
        "random_seed": 0, "verbose": 0, "allow_writing_files": False,
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
        "depth": trial.suggest_int("depth", 4, 9),
        "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 20.0, log=True),
        "random_strength": trial.suggest_float("random_strength", 0.1, 10.0, log=True),
        "bootstrap_type": trial.suggest_categorical("bootstrap_type", ["Bayesian", "Bernoulli"]),
    }
    if params["bootstrap_type"] == "Bayesian":
        params["bagging_temperature"] = trial.suggest_float("bagging_temperature", 0.0, 1.0)
    else:
        params["subsample"] = trial.suggest_float("subsample", 0.6, 1.0)
    model = CatBoostClassifier(**params)
    model.fit(train_pool, eval_set=valid_pool, use_best_model=True)
    return model.get_best_score()["validation"]["AUC"]
```
Conditional parameters (bagging_temperature vs subsample) avoid the CB004 conflict.

## Imbalance

| Option | Effect |
|--------|--------|
| none | calibrated probabilities; evaluate with PRAUC |
| `auto_class_weights="Balanced"` / `"SqrtBalanced"` | reweights classes; probabilities shift (recalibrate) |
| `scale_pos_weight` | binary only |
| `class_weights=[w0, w1, ...]` | explicit |
Only one of the three may be set.

## Monotone constraints

```python
CatBoostRegressor(monotone_constraints=["sqft:1", "age:-1"])      # or a list aligned with columns
```
Supported for numeric features with symmetric/depthwise trees on CPU.

## Losses for other tasks

| Task | loss_function | eval_metric |
|------|---------------|-------------|
| Regression | RMSE, MAE, Huber:delta=1, Quantile:alpha=0.9, Expectile, LogCosh | RMSE, MAE, R2 |
| Counts / insurance | Poisson, Tweedie:variance_power=1.5 | Poisson, Tweedie:variance_power=1.5 |
| Uncertainty | RMSEWithUncertainty (predicts mean and variance) | RMSE |
| Multiclass | MultiClass, MultiClassOneVsAll | TotalF1:average=Macro, Accuracy, MultiClass |
| Ranking | YetiRank, PairLogit, QueryRMSE, LambdaMart | NDCG:top=10, MAP, PFound |
| Survival | Cox, SurvivalAft | - |

## GPU

`task_type="GPU", devices="0"`. Faster for large data and many iterations; some options differ
(`border_count` default 128, `rsm` only for pairwise losses, `max_ctr_complexity` limits). Results can differ
slightly from CPU.

## Speed tips

- Lower `max_ctr_complexity` (1-2) with many categoricals.
- `boosting_type="Plain"` (default for large data).
- `border_count` 32-128 for faster numeric binning.
- `thread_count=-1`; quantise once with `Pool.quantize()` when training several models on the same data.
