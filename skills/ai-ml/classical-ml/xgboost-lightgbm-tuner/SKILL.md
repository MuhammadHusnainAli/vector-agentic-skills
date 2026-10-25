---
name: xgboost-lightgbm-tuner
description: "Tune XGBoost and LightGBM models efficiently and read their training curves: validation design and early stopping inside CV, fixed learning rate for search then lower rate with more trees for the final fit, capacity knobs (num_leaves, max_depth, min_child_samples, min_child_weight) sized to the data, subsampling, L1/L2 and split-gain regularisation, categorical handling, imbalance (scale_pos_weight vs is_unbalance vs no weighting), monotone and interaction constraints, Optuna/TPE search with fold-level pruning and parameter importances, and the LightGBM <-> XGBoost <-> CatBoost parameter map. Parses LightGBM, XGBoost and CatBoost logs or CSV histories to find the best iteration, overfitting onset, train/validation gap and whether more rounds or a lower learning rate are needed. Use when someone tunes a gradient-boosted model, asks which hyperparameters matter, sees overfitting or underfitting in boosting curves, hits XGBoost 2 / LightGBM 4 API changes, or wants a search space for a GBM."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# XGBoost / LightGBM Tuner

Gradient boosting rewards a disciplined order: **honest validation -> early stopping -> capacity -> sampling
-> regularisation -> lower learning rate for the final fit**. Most of the gain comes from the first three;
the last few percent rarely justify a huge search. `scripts/gbm_param_advisor.py` produces starting
parameters, a search space scaled to the data (rows, features, positives) and an early-stopping plan for
LightGBM or XGBoost, plus the cross-library parameter map; `scripts/parse_gbm_log.py` reads training logs
from LightGBM, XGBoost or CatBoost (or a CSV history) and says whether you are overfitting, under-trained or
using too high a learning rate.

## Trigger Conditions

Activate this skill when the user:
- Tunes XGBoost or LightGBM, or asks which hyperparameters matter and what ranges to search
- Shows a training log or learning curve and asks whether the model is overfitting
- Has a GBM that peaks after a handful of rounds, never stops improving, or has a big train/valid gap
- Needs imbalance handling, monotone constraints or categorical settings for a GBM
- Migrates between LightGBM, XGBoost and CatBoost and needs equivalent parameters
- Hits errors from API changes (XGBoost 2+ `early_stopping_rounds` in the constructor; LightGBM callbacks)

CatBoost-specific work: [catboost-model-builder](../catboost-model-builder/SKILL.md); general search planning:
[hyperparameter-search-planner](../hyperparameter-search-planner/SKILL.md); full Optuna study scripts:
[optuna-study-writer](../optuna-study-writer/SKILL.md); diagnosing curves beyond boosting:
[overfitting-underfitting-diagnoser](../overfitting-underfitting-diagnoser/SKILL.md).

## Workflow

```
1. VALIDATE  -> folds that mirror deployment; fix them for every trial
2. ADVISE    -> python scripts/gbm_param_advisor.py --library lightgbm --rows N --features P --positives K
3. BASELINE  -> defaults + early stopping; log train and valid metrics
4. READ      -> python scripts/parse_gbm_log.py train.log   (best round, gap, still improving?)
5. SEARCH    -> 30-200 TPE/random trials on capacity, sampling, regularisation at a fixed learning rate
6. NARROW    -> parameter importances; widen ranges whose best sits at a bound; fix unimportant ones
7. FINAL     -> lower learning rate, more trees (early stopping again or scaled best_iteration), all training data
8. CONFIRM   -> holdout vs the untuned baseline; keep the gain only if it is beyond noise
```

## What Matters Most

| Rank | Knob | LightGBM | XGBoost | Rule |
|------|------|----------|---------|------|
| 1 | trees x learning rate | `n_estimators` + early stopping, `learning_rate` | same | search at 0.05-0.1; final at half |
| 2 | tree capacity | `num_leaves` (7-255, log) | `max_depth` (3-10) | larger for big data / many interactions |
| 3 | minimum leaf size | `min_child_samples` (~0.1-1% of rows) | `min_child_weight` | the regulariser that matters on small or noisy data |
| 4 | row sampling | `subsample` + `subsample_freq=1` | `subsample` | 0.6-0.9 |
| 5 | column sampling | `colsample_bytree` | `colsample_bytree` | 0.3-0.9; lower with many correlated features |
| 6 | L2 / L1 | `reg_lambda`, `reg_alpha` | `reg_lambda`, `reg_alpha` | log ranges; second-order |
| 7 | split gain | `min_split_gain` | `gamma` | loss-scale dependent |

LightGBM grows leaf-wise: `num_leaves` controls capacity, `max_depth=-1` by default. XGBoost grows
depth-wise: `max_depth` controls capacity (`grow_policy="lossguide"` + `max_leaves` mimics LightGBM).
`gbm_param_advisor.py --map` prints the full LightGBM / XGBoost / CatBoost name map.

## Reading Training Curves

```
valid_1 binary_logloss (lower is better), 30 logged rounds
best 0.13503 at iteration 10; last 0.27694 at 300; train/valid gap at best 0.1227
- best at iteration 10: the learning rate is high for this data; lower it (x0.3-0.5)
- validation got 100% of its range worse after the best round: early stopping is essential
- large train/valid gap at the best round: increase min_child_samples, lower num_leaves, raise reg_lambda
```

| Curve | Meaning | Action |
|-------|---------|--------|
| Valid best in the first ~10-50 rounds, then rises | learning rate too high and/or capacity too high | lower LR, raise min leaf size, lower leaves/depth |
| Valid still improving at the last round | under-trained | more rounds or higher LR; early stopping with patience |
| Large train/valid gap, valid flat | overfitting capacity | stronger leaf-size limits, subsampling, L2 |
| Train ≈ valid and both mediocre | under-fitting / weak features | more capacity, features, interactions |
| Valid noisy round to round | small validation set | larger fold, repeated CV, patience ≥ 100 |

## Early Stopping Done Right

- Early stopping chooses the number of trees on the **validation fold**; reporting that fold's score is mildly
  optimistic. For a strict number use an inner validation split or confirm on a holdout.
- XGBoost >= 2: `early_stopping_rounds` and `eval_metric` go in the **constructor**.
- LightGBM >= 4: `callbacks=[lgb.early_stopping(200), lgb.log_evaluation(100)]`; `early_stopping_rounds` in
  `fit` was removed; LightGBM >= 4.7 prefers `eval_X`/`eval_y` to `eval_set` in the scikit-learn API.
- Never early-stop on the test set (target-leakage-detector flags it as LK009).

```python
import lightgbm as lgb
m = lgb.LGBMClassifier(learning_rate=0.05, n_estimators=10000, num_leaves=31, min_child_samples=50,
                       subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, random_state=0)
m.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr), (X_va, y_va)], eval_metric="auc",
      callbacks=[lgb.early_stopping(200, verbose=False), lgb.log_evaluation(50)])
```

Playbook with ranges for small and large data: [tuning-playbook.md](references/tuning-playbook.md).

## Imbalance in GBMs

| Option | Effect | Use when |
|--------|--------|----------|
| No weighting (default) | calibrated probabilities; ranking unaffected | you evaluate with PR-AUC / top-K and use probabilities |
| `scale_pos_weight = neg/pos` (or `is_unbalance=True` in LightGBM) | more weight on positives; probabilities inflated | recall at a fixed default threshold matters; recalibrate if probabilities are used |
| Larger `min_child_samples` + `max_delta_step` (XGBoost) | stabilises leaf values with very rare positives | < 1% positives |

Ranking metrics (ROC-AUC, PR-AUC) usually change little with weighting. See imbalanced-class-handler.

## Library Notes

- LightGBM parameters, native API, categoricals, DART/linear trees, common warnings:
  [lightgbm-reference.md](references/lightgbm-reference.md).
- XGBoost 2/3 API, DMatrix, categoricals, constraints, multi-quantile, GPU:
  [xgboost-reference.md](references/xgboost-reference.md).
- Optuna objective with fixed folds, fold-level pruning, parameter importances and the final refit
  (verified with Optuna 5.0 and LightGBM 4.7): [optuna-for-gbms.md](references/optuna-for-gbms.md).

## Output Format

When tuning or reviewing a GBM, deliver:
1. **Validation design** - folds, metric, early-stopping placement.
2. **Starting point** - parameters and search space (`gbm_param_advisor.py`), with the reason for each range.
3. **Curve reading** - `parse_gbm_log.py` output for the baseline and the tuned model.
4. **Search results** - best parameters, parameter importances, trials used, best iteration.
5. **Final model** - learning rate and tree count for the refit, holdout score vs untuned baseline (with CI).
6. **Next lever** - if tuning gained little: features, labels or validation, not more trials.

## Scripts

```bash
python scripts/gbm_param_advisor.py --library lightgbm --rows 200000 --features 80 --task binary --positives 4000
python scripts/gbm_param_advisor.py --library xgboost --rows 3000 --features 25 --task regression --budget low --json
python scripts/gbm_param_advisor.py --map
```
Starting parameters (learning rate by data size, leaf size ~0.2% of rows clamped and capped by the positive
count, leaves/depth by size, feature sampling by width, early-stopping patience), a search space with types
and log scales, imbalance advice with the `scale_pos_weight` value, a trial budget and a 5-step plan; `--map`
prints the LightGBM / XGBoost / CatBoost parameter equivalences. Exit codes: 0 printed, 2 usage error.

```bash
python scripts/parse_gbm_log.py train.log                 # LightGBM / XGBoost / CatBoost text logs
python scripts/parse_gbm_log.py history.csv --json        # iteration + train/valid metric columns
python scripts/parse_gbm_log.py xgb.log --train-name validation_0
python train.py 2>&1 | python scripts/parse_gbm_log.py -
```
Detects the format, infers metric direction (AUC/NDCG/MAP/accuracy higher; loss/error/RMSE lower;
`--higher-better` overrides), treats `validation_0`/`valid_0` as the training curve when it scores better than
`_1`, and reports the best iteration and value, rounds after best, the train/valid gap and degradation, with
advice (more rounds, lower learning rate, early-stopping patience, regularisation, more capacity). Exit codes:
0 parsed, 2 nothing parseable.

## Additional Resources

| File | Content |
|------|---------|
| [tuning-playbook.md](references/tuning-playbook.md) | Tuning order, ranges, learning-rate/trees trade-off, early stopping inside CV, small- and large-data settings, when tuning cannot help |
| [lightgbm-reference.md](references/lightgbm-reference.md) | scikit-learn and native APIs, key parameters, categoricals, objectives and metrics, common problems |
| [xgboost-reference.md](references/xgboost-reference.md) | XGBoost 2/3 API, DMatrix, parameters, categoricals, objectives, GPU, common errors |
| [optuna-for-gbms.md](references/optuna-for-gbms.md) | CV objective with fixed folds and pruning, importances, final refit with a lower learning rate |
