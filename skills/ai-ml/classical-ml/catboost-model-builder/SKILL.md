---
name: catboost-model-builder
description: "Build CatBoost models that use its strengths correctly: raw categorical columns as cat_features (ordered target statistics, no manual encoding), text_features, Pool construction with NaN-safe categories, ordered boosting and has_time for temporal data, symmetric (oblivious) trees, overfitting detector with eval_set and use_best_model, losses for classification, regression (Quantile, Poisson, Tweedie) and ranking (YetiRank), class weights, monotone constraints, feature importance (PredictionValuesChange, LossFunctionChange) and SHAP values, GPU training and model export. Plans cat/text/numeric columns from a CSV and generates a runnable training script, and checks parameter sets for the conflicts CatBoost rejects (iterations vs n_estimators, Bayesian bootstrap with subsample, multiple class-weight options, depth > 16, use_best_model without eval_set). Use when someone builds or tunes a CatBoost model, has many categorical or high-cardinality features, or hits CatBoostError messages."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# CatBoost Model Builder

CatBoost's advantage is categorical data: give it **raw** categorical columns and it computes target
statistics in an ordered, leakage-free way (each row is encoded using only rows before it in a random
permutation), builds combinations of categoricals, and trains symmetric trees that are fast at inference.
Most CatBoost mistakes come from fighting that: one-hot or target encoding beforehand, NaN in categorical
columns, float-typed category codes, or a random split on temporal data. `scripts/catboost_plan.py` sorts
a CSV's columns into cat / text / numeric / dropped and generates a training script (verified with
CatBoost 1.2 for binary, multiclass-with-text and Tweedie regression); `scripts/catboost_params_check.py`
catches parameter conflicts before a long run.

## Trigger Conditions

Activate this skill when the user:
- Builds a CatBoost classifier/regressor/ranker, or asks how to pass categorical or text features
- Has many categorical or high-cardinality columns and is unsure whether to encode them first (do not)
- Gets `CatBoostError` (invalid cat feature values, NaN in categoricals, conflicting parameters, depth limit)
- Needs CatBoost tuning, class weights, monotone constraints, SHAP values or model export
- Compares CatBoost with LightGBM/XGBoost (name map in xgboost-lightgbm-tuner)

## Workflow

```
1. PLAN      -> python scripts/catboost_plan.py data.csv --target y --drop id [--time-col ts]
2. PREPARE   -> cat columns as str (NaN -> "__nan__"), text columns as str, dates -> derived parts
3. SPLIT     -> train / validation (for the overfitting detector) / test; time order if temporal
4. CHECK     -> python scripts/catboost_params_check.py params.json --task binary --has-eval-set
5. TRAIN     -> Pool(..., cat_features, text_features); fit(eval_set=valid_pool, use_best_model=True)
6. TUNE      -> learning_rate x iterations, depth, l2_leaf_reg, random_strength, bagging_temperature
7. EXPLAIN   -> get_feature_importance (PredictionValuesChange / LossFunctionChange / ShapValues)
8. EXPORT    -> save_model("m.cbm") (or ONNX/CoreML/JSON); store the column order and cat list
```

## Minimal Correct Model

```python
from catboost import CatBoostClassifier, Pool

for c in CAT:                                         # strings or ints, never NaN or floats
    X[c] = X[c].astype("string").fillna("__nan__").astype(str)

train_pool = Pool(X_tr, y_tr, cat_features=CAT, text_features=TEXT or None)
valid_pool = Pool(X_va, y_va, cat_features=CAT, text_features=TEXT or None)

model = CatBoostClassifier(loss_function="Logloss", eval_metric="AUC", custom_metric=["PRAUC"],
                           iterations=5000, learning_rate=0.05, depth=6, l2_leaf_reg=3,
                           od_type="Iter", od_wait=200, random_seed=0, allow_writing_files=False, verbose=500)
model.fit(train_pool, eval_set=valid_pool, use_best_model=True)
proba = model.predict_proba(Pool(X_te, cat_features=CAT, text_features=TEXT or None))[:, 1]
```
Generated in full (split, metrics, importances, SHAP, save) by `catboost_plan.py --code`.

## Features: What Goes Where

| Column type | CatBoost handling | Prepare |
|-------------|-------------------|---------|
| Nominal categorical (any cardinality) | `cat_features`: ordered CTRs (target statistics) + combinations | `astype(str)`, NaN -> `"__nan__"`; no encoding |
| Numeric code with meaning only as a label (zip, store id) | `cat_features` | cast to str; near-unique codes -> a prefix (zip3) |
| Low-cardinality categorical (<= `one_hot_max_size`, default 2; up to 255 on GPU) | one-hot internally | nothing |
| Free text | `text_features`: tokenised, bag-of-words + naive Bayes / BM25 estimates | `astype(str)`, NaN -> `""` |
| Dense embeddings | `embedding_features` (LDA / KNN estimators) | list/array column per row |
| Numeric | as is; NaN allowed (`nan_mode="Min"` by default) | nothing |
| Dates | not native | derive year, month, day of week, days since |
| IDs | drop | - |

Mechanics of ordered target statistics, CTR types, feature combinations and text/embedding processing:
[catboost-essentials.md](references/catboost-essentials.md).

## Temporal Data

- Split by time (train on the past, validate and test on later periods).
- `has_time=True` makes CatBoost use the given row order instead of random permutations for ordered
  boosting and target statistics: sort rows by time first.
- The overfitting detector's `eval_set` should be the most recent training period, not a random sample.

## Key Parameters

| Parameter | Default | Tune | Notes |
|-----------|---------|------|-------|
| `iterations` + `learning_rate` | 1000, auto | lr 0.03-0.1 with early stopping | CatBoost picks lr automatically if unset |
| `depth` | 6 | 4-10 | symmetric trees: 2^depth leaves; > 16 is rejected |
| `l2_leaf_reg` | 3 | 1-10 (log) | main regulariser |
| `random_strength` | 1 | 0.5-10 | noise on split scores |
| `bagging_temperature` | 1 | 0-1+ | Bayesian bootstrap only |
| `bootstrap_type` | MVS / Bayesian | Bernoulli + `subsample` 0.6-0.9 | `subsample` is invalid with Bayesian |
| `border_count` | 254 (CPU) | 32-254 | numeric binning |
| `one_hot_max_size` | 2 | 2-10 | one-hot threshold for categoricals |
| `max_ctr_complexity` | 4 | 1-4 | categorical combinations (lower = faster) |
| `grow_policy` | SymmetricTree | Depthwise / Lossguide (+ `max_leaves`) | non-symmetric trees: slower inference |
| `auto_class_weights` | None | Balanced / SqrtBalanced | only one of this, `class_weights`, `scale_pos_weight` |
| `od_type`, `od_wait` | - | Iter, 100-300 | overfitting detector |

Tuning order, Optuna space and GPU notes: [parameters-and-tuning.md](references/parameters-and-tuning.md).

## Conflicts CatBoost Rejects

`catboost_params_check.py` mirrors the errors CatBoost 1.2 raises (checked against the library):

| Code | Conflict |
|------|----------|
| CB001 | `iterations` and `n_estimators` / `num_boost_round` / `num_trees` together |
| CB002 | `learning_rate` and `eta` together |
| CB003 | more than one of `scale_pos_weight`, `class_weights`, `auto_class_weights` |
| CB004 | `bootstrap_type="Bayesian"` with `subsample`; `bagging_temperature` without Bayesian |
| CB005 | `depth` > 16 |
| CB006 | `use_best_model=True` without `eval_set` |

Plus warnings for silently ignored settings (`max_leaves` without `grow_policy="Lossguide"`), no overfitting
detector, task/loss mismatches, extreme learning rates, deep trees and zero L2.

## Explaining and Exporting

```python
imp = model.get_feature_importance(train_pool, prettified=True)              # PredictionValuesChange
loss_imp = model.get_feature_importance(valid_pool, type="LossFunctionChange")  # needs labels, honest
shap = model.get_feature_importance(test_pool, type="ShapValues")          # (n, features + 1); last col = expected value
inter = model.get_feature_importance(train_pool, type="Interaction")       # strongest feature pairs
model.save_model("model.cbm")              # also "json", "cpp", "python"; ONNX only without cat_features
```
For multiclass, ShapValues has shape (n, classes, features + 1). Pitfalls (category order at inference,
`predict` vs `predict_proba`, `prediction_type`, thread settings, determinism):
[catboost-pitfalls.md](references/catboost-pitfalls.md).

## Output Format

When building a CatBoost model, deliver:
1. **Column plan** - cat / text / numeric / dropped with reasons (`catboost_plan.py`).
2. **Split** - train / validation (detector) / test, time order and `has_time` if temporal.
3. **Parameters** - with the `catboost_params_check.py` result.
4. **Training code** - Pool construction and fit with `eval_set` and `use_best_model`.
5. **Results** - best iteration, validation and test metrics, importances (LossFunctionChange preferred).
6. **Export** - saved model format, column order, cat feature list, version pin.

## Scripts

```bash
python scripts/catboost_plan.py data.csv --target churned --drop customer_id
python scripts/catboost_plan.py data.csv --target churned --time-col signup_date --code -o train_catboost.py
python scripts/catboost_plan.py tickets.csv --target queue --drop ticket_id --code
python scripts/catboost_plan.py claims.csv --target claim_amount --loss "Tweedie:variance_power=1.5" --code
```
Classifies columns into cat_features (non-numeric, plus code-like numerics), text_features (mean length >= 30 and
>= 4 words), numeric, and dropped (constant, near-unique IDs, dates, the time column); picks CatBoostClassifier
(Logloss / AUC + PRAUC, or MultiClass / TotalF1) or CatBoostRegressor (RMSE, or the `--loss` you give); `--code`
emits a script with NaN-safe category casting, time or stratified train/valid/test split, overfitting detector,
`has_time` for temporal data, test metric, importances, SHAP and `save_model`. Exit codes: 0 printed/written,
2 usage or read error.

```bash
python scripts/catboost_params_check.py params.json --task binary --has-eval-set
echo '{"iterations": 5000, "n_estimators": 100}' | python scripts/catboost_params_check.py -
```
Rules CB001-CB014 (errors CB001-CB006 confirmed against CatBoost 1.2). Exit codes: 0 no errors, 1 errors, 2 read
error.

## Additional Resources

| File | Content |
|------|---------|
| [catboost-essentials.md](references/catboost-essentials.md) | Ordered boosting, ordered target statistics and CTR types, feature combinations, symmetric trees, text and embedding features, Pool API |
| [parameters-and-tuning.md](references/parameters-and-tuning.md) | Parameter reference, tuning order and Optuna space, imbalance, monotone constraints, GPU training, speed tips |
| [catboost-pitfalls.md](references/catboost-pitfalls.md) | NaN and float categories, category consistency at inference, importance types, SHAP shapes, prediction types, determinism, common CatBoostError messages |
| [deployment.md](references/deployment.md) | save/load formats (cbm, ONNX, CoreML, JSON, C++), fast inference, versioning, applying models in other languages |
