# Native Categorical Handling in Gradient Boosting

## LightGBM

```python
import lightgbm as lgb

cat_cols = ["merchant_category", "country", "device_type"]
for c in cat_cols:
    X_train[c] = X_train[c].astype("category")
    X_valid[c] = pd.Categorical(X_valid[c], categories=X_train[c].cat.categories)   # same categories, same order

model = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.05, cat_smooth=10, min_data_per_group=50,
                           max_cat_threshold=32)
model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], callbacks=[lgb.early_stopping(100)])
```
- Splits by sorting levels by gradient statistics: one split can separate any subset of levels.
- High-cardinality columns can overfit: raise `cat_smooth`, `min_data_per_group`, `cat_l2`, or switch to
  target/frequency encoding.
- Unseen categories at prediction time follow the "other" direction; NaN is treated as missing.

## XGBoost

```python
import xgboost as xgb
for c in cat_cols:
    X_train[c] = X_train[c].astype("category")
model = xgb.XGBClassifier(tree_method="hist", enable_categorical=True, max_cat_to_onehot=8,
                          n_estimators=2000, learning_rate=0.05, early_stopping_rounds=100)
model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)])
```
- `max_cat_to_onehot`: one-hot style splits for columns with fewer levels, partition splits otherwise.
- Requires pandas `category` dtype (or a DMatrix with feature types).

## scikit-learn HistGradientBoosting

```python
from sklearn.ensemble import HistGradientBoostingClassifier
for c in cat_cols:
    X_train[c] = X_train[c].astype("category")
model = HistGradientBoostingClassifier(categorical_features="from_dtype")   # sklearn >= 1.4
```
- At most 255 levels per categorical feature (`max_bins`); group the tail beforehand.
- Inside a Pipeline with an `OrdinalEncoder`, pass `categorical_features` as indices or a boolean mask of the
  encoded columns; negative codes are treated as missing.

## CatBoost

```python
from catboost import CatBoostClassifier, Pool
train_pool = Pool(X_train, y_train, cat_features=cat_cols)
valid_pool = Pool(X_valid, y_valid, cat_features=cat_cols)
model = CatBoostClassifier(iterations=3000, learning_rate=0.05, eval_metric="AUC", od_type="Iter", od_wait=200)
model.fit(train_pool, eval_set=valid_pool, use_best_model=True)
```
- Ordered target statistics computed over random permutations (no leakage by design).
- Builds combinations of categorical features automatically (`max_ctr_complexity`).
- Categorical columns must be strings or integers, not floats; fill NaN with a string like "nan".
- See catboost-model-builder for tuning.

## Serving consistency

| Risk | Fix |
|------|-----|
| Category order differs between train and serving | save `X_train[c].cat.categories` with the model; rebuild `pd.Categorical(..., categories=saved)` |
| New levels in production | they map to NaN/unknown: confirm the model's handling; monitor the unseen rate |
| Different dtypes (int vs str) | normalise to strings before encoding |
| Library version changes | pin versions; re-validate after upgrades |

## When native is not the best choice

- Very high cardinality with few rows per level: frequency or cross-fitted target encoding generalises better.
- Linear components or stacked models need numeric encodings anyway.
- Interpretability: one-hot with a linear model, or WoE scorecards, are easier to explain.
