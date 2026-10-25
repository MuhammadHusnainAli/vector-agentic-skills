---
name: categorical-encoding-selector
description: "Choose and implement the right encoding for every categorical column given the model family and the data: one-hot (with infrequent-level grouping and handle_unknown), ordinal with an explicit order, cross-fitted target encoding (scikit-learn TargetEncoder, CatBoost ordered statistics, category_encoders inside CV), frequency/count encoding, feature hashing, native categorical support in LightGBM, HistGradientBoosting, XGBoost and CatBoost, prefix levels for codes (zip3, NAICS-2), and embeddings. Measures cardinality, rare-level share, unseen-level rate on a time-ordered holdout and target signal per column, emits the ColumnTransformer, and quantifies target-encoding leakage (in-sample vs out-of-fold vs holdout AUC). Use when someone asks how to encode categorical variables, one-hot vs target vs ordinal encoding, how to handle high-cardinality IDs, zip codes, unseen categories at inference, or why target encoding overfits."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Categorical Encoding Selector

The right encoder depends on three things: the **model family** (linear models need one column per level or
a numeric summary; trees can split integer codes; modern GBMs take categories natively), the
**cardinality and rare/unseen levels**, and whether the column carries **order**. Target encoding is
powerful for high cardinality and dangerous when computed in-sample. `scripts/encoding_plan.py` measures
each column and recommends an encoder with the scikit-learn code; `scripts/te_leakage_check.py` shows how
much naive target encoding inflates a column's apparent signal.

## Trigger Conditions

Activate this skill when the user:
- Asks how to encode categorical variables, or one-hot vs label/ordinal vs target vs frequency encoding
- Has high-cardinality columns (merchant, product, user, zip, city) and a model that overfits or explodes in
  width
- Gets errors or silent issues from unseen categories at inference ("Found unknown categories")
- Uses LightGBM / XGBoost / CatBoost / HistGradientBoosting and wants native categorical handling
- Sees great CV scores after target encoding that collapse on a holdout

## Workflow

```
1. INVENTORY -> python scripts/encoding_plan.py data.csv --target y --model <family> [--time-col ts]
2. ORDER     -> confirm ordinal columns and their order with a domain owner
3. CARDINAL  -> low: one-hot / native; high: target (cross-fitted), frequency, hashing; codes: prefixes
4. UNSEEN    -> handle_unknown / infrequent grouping / prior smoothing; measure unseen rate on recent data
5. LEAKAGE   -> python scripts/te_leakage_check.py data.csv --target y   (encoders inside CV only)
6. BUILD     -> python scripts/encoding_plan.py ... --code; place it in the Pipeline
7. COMPARE   -> 2-3 encodings on the same folds; keep the simplest that is not worse
```

## Decision Table

| Column | Linear / logistic, k-NN, SVM, NN | Random forest / single trees | LightGBM / HistGBM / XGBoost | CatBoost |
|--------|----------------------------------|------------------------------|------------------------------|----------|
| 2 levels | 0/1 | 0/1 | 0/1 | 0/1 or cat_features |
| Ordered (low < med < high) | ordinal integer (or one-hot if effect is non-monotone) | ordinal | ordinal | ordinal or cat_features |
| <= ~15 levels, nominal | one-hot | ordinal codes or one-hot | native categorical | cat_features |
| 15-100 levels | one-hot with `min_frequency` / `max_categories` | ordinal or target | native (< 256 levels) | cat_features |
| 100+ levels, enough rows per level | cross-fitted target encoding + frequency | target / frequency | native up to 255, else target / frequency | cat_features |
| 100+ levels, many unseen at serve time | hashing or frequency; target with strong smoothing | frequency | frequency / target | cat_features |
| Near-unique (IDs) | drop (or aggregate features per ID) | drop | drop | drop |
| Hierarchical codes (zip, NAICS, ICD) | prefix levels, then the rules above | same | same | same |
| Free text | not categorical: TF-IDF / embeddings | | | text_features |
| Dates | not categorical: date features | | | |

Encoder internals, parameters and edge cases: [encoder-catalog.md](references/encoder-catalog.md).

## One-Hot Done Right

```python
from sklearn.preprocessing import OneHotEncoder
ohe = OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20, sparse_output=True)
```
- `min_frequency` / `max_categories` group rare levels into one "infrequent" column, learned on train.
- `handle_unknown="infrequent_if_exist"` maps unseen levels to the infrequent column (or `"ignore"` -> all
  zeros).
- `drop="if_binary"` for linear models without regularisation (avoid the dummy trap); with L2 regularisation
  keep all columns.
- Sparse output for wide data; most linear solvers accept sparse matrices.

## Target Encoding Without Leakage

Replacing a level by the mean target of its rows is in-sample memorisation when the row's own label is
included. Rare levels then "predict" perfectly in CV and fail on new data.

```
encoded(level) = (sum_y(level) + m * prior) / (n(level) + m)       # smoothing toward the global mean
```

Safe implementations:
- **scikit-learn `TargetEncoder`** (>= 1.3): `fit_transform` cross-fits internally (each row encoded by a
  model fitted on other folds); `transform` uses the full-train mapping. Supports binary, multiclass (one
  column per class) and continuous targets; `smooth="auto"` uses empirical Bayes shrinkage.
- **CatBoost**: ordered target statistics (encode each row using only "earlier" rows in a random
  permutation), the default for `cat_features`.
- **category_encoders** (`TargetEncoder`, `MEstimateEncoder`, `JamesSteinEncoder`, `CatBoostEncoder`): only
  inside a Pipeline evaluated with CV, never fitted on all data before splitting.

`te_leakage_check.py` makes the danger concrete:

```
column                 levels rows/lvl in-sample     OOF  holdout     gap
merchant_id_name          471      6.4     0.858   0.723    0.755  +0.135  <- in-sample encoding leaks
zip_code                  397      1.0     1.000   0.499    0.500  +0.501  <- in-sample encoding leaks
```
A near-unique column gets AUC 1.000 in-sample and 0.5 honestly. Leakage detail and nested-CV patterns:
[target-encoding-and-leakage.md](references/target-encoding-and-leakage.md).

## Native Categorical Support in GBMs

| Library | How | Notes |
|---------|-----|-------|
| LightGBM | `categorical_feature=[...]` or pandas `category` dtype | optimal split over sorted level gradients; tune `cat_smooth`, `min_data_per_group`, `max_cat_threshold`; can overfit high cardinality |
| HistGradientBoosting | `categorical_features="from_dtype"` (>= 1.4) or a boolean mask | < 256 levels (`max_bins`); codes must be 0..k-1, negative = missing |
| XGBoost | `enable_categorical=True` with pandas `category` dtype, `tree_method="hist"` | `max_cat_to_onehot` switches to one-hot splits for small k |
| CatBoost | `cat_features=[...]` | ordered target statistics + feature combinations; strong default for many categoricals |

Category dtype must have identical categories (same order) in training and serving: store the category
list with the model. Code: [gbm-native-categoricals.md](references/gbm-native-categoricals.md).

## Unseen and Rare Levels

| Situation | Handling |
|-----------|----------|
| New levels appear in production (new merchants) | one-hot `handle_unknown`; target encoding falls back to the prior; frequency = 0; hashing handles it |
| Rare levels (< 20 rows) | group into "other" (min_frequency) or rely on smoothing |
| Levels change meaning over time | time-based validation; re-fit encoders on retrain |
| Missing values | explicit "missing" level for one-hot/target; native handling in GBMs |

`encoding_plan.py --time-col` measures the share of the latest 20% of rows whose level never appears in the
earlier 80%: that is roughly the unseen rate the model will face.

## Output Format

When recommending encodings, answer with:
1. **Per-column plan** - levels, rare share, unseen rate, order, target signal, chosen encoder and why (the
   `encoding_plan.py` table).
2. **Code** - the ColumnTransformer (or native-categorical setup) inside a Pipeline.
3. **Leakage note** - for target-encoded columns, the cross-fitting method and the `te_leakage_check.py` gap.
4. **Serving notes** - unseen-level behaviour, stored category lists, refit schedule.
5. **Comparison plan** - which alternative encoders to test on the same folds.

## Scripts

```bash
python scripts/encoding_plan.py data.csv --target churned --model linear
python scripts/encoding_plan.py data.csv --target is_fraud --model gbm --time-col timestamp --drop txn_id
python scripts/encoding_plan.py data.csv --target y --model catboost --json
python scripts/encoding_plan.py data.csv --target y --model linear --code > prep.py
```
Models: linear, knn, nn, tree, gbm, catboost. Per non-numeric column (plus numeric-looking codes): levels, rows
per level, missing share, rare share (`--min-count`, default 20), unseen rate on the latest (or hashed) 20%,
detected order (low/medium/high, S/M/L, basic/standard/premium, Likert...), out-of-fold target signal; then
one of onehot, onehot_infrequent, ordinal, target, hashing, native, catboost_native, prefix (near-unique codes),
skip (dates) or drop (IDs). `--code` prints a ColumnTransformer with OneHotEncoder / OrdinalEncoder (explicit
categories) / TargetEncoder / FeatureHasher steps (picklable) and the native-categorical list. Exit codes: 0
printed, 2 usage or read error.

```bash
python scripts/te_leakage_check.py data.csv --target is_fraud --time-col date
python scripts/te_leakage_check.py data.csv --target churned --columns zip_code plan --folds 5 --smooth 20 --json
```
For each categorical column: ROC-AUC of the target-encoded column alone, in-sample vs out-of-fold (smoothed,
K folds) vs time-ordered holdout, the gap, and a flag when the gap exceeds `--max-gap` for columns with fewer
than `--min-rows-per-level` rows per level. Exit codes: 0 no flagged column, 1 flagged column(s), 2 usage
error or non-binary target.

## Additional Resources

| File | Content |
|------|---------|
| [encoder-catalog.md](references/encoder-catalog.md) | Every encoder: one-hot, dummy, ordinal, target/M-estimate/James-Stein/WoE, frequency, hashing, binary, embeddings, prefixes; parameters and pitfalls |
| [target-encoding-and-leakage.md](references/target-encoding-and-leakage.md) | Why in-sample encoding leaks, smoothing math, cross-fitting, nested CV, multiclass and regression targets, time-aware encoding |
| [gbm-native-categoricals.md](references/gbm-native-categoricals.md) | LightGBM, XGBoost, HistGradientBoosting, CatBoost native categorical code and tuning, serving consistency |
| [comparing-encoders.md](references/comparing-encoders.md) | Experiment design for choosing encoders, typical results by model family, width and latency costs |
