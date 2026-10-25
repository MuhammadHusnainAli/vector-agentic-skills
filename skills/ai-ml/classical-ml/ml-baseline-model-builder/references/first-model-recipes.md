# First-Model Recipes (scikit-learn)

The goal of a first model is an honest number, not the best number. Defaults below are deliberately boring.

## Preprocessing defaults

```python
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

numeric = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler())
categorical = make_pipeline(
    SimpleImputer(strategy="most_frequent"),
    OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=10, sparse_output=False),
)
prep = ColumnTransformer([
    ("num", numeric, make_column_selector(dtype_include="number")),
    ("cat", categorical, make_column_selector(dtype_include=["object", "category", "string"])),
])
```

- `add_indicator=True` keeps "was missing" as information (often predictive).
- `min_frequency` groups rare levels so unseen/rare categories do not explode the feature count.
- Scaling matters for linear models, k-NN and SVMs; tree models ignore it.
- Everything inside the Pipeline so `fit` only sees training rows.

## Linear model

```python
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline

clf = Pipeline([("prep", prep), ("model", LogisticRegression(max_iter=2000))])
reg = Pipeline([("prep", prep), ("model", Ridge(alpha=1.0))])
```

For skewed positive targets:
```python
from sklearn.compose import TransformedTargetRegressor
import numpy as np
reg_log = TransformedTargetRegressor(regressor=reg, func=np.log1p, inverse_func=np.expm1)
```
Predictions from a log-target model estimate the median, not the mean; for totals (revenue sums) multiply
by a smearing factor `mean(exp(residuals))` or use a Gamma/Tweedie loss.

## Gradient boosting

```python
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OrdinalEncoder

cat_cols = X_train.select_dtypes(exclude="number").columns.tolist()
num_cols = X_train.select_dtypes(include="number").columns.tolist()
gbm = Pipeline([
    ("prep", ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                               encoded_missing_value=-1), cat_cols),
        ("num", "passthrough", num_cols),        # NaN is fine: HGB handles missing values natively
    ])),
    ("model", HistGradientBoostingClassifier(
        categorical_features=list(range(len(cat_cols))),   # the first len(cat_cols) output columns
        random_state=0)),
])
```
Negative category codes (unknown or missing, -1 above) are treated as missing by HistGradientBoosting. Native
categorical support beats one-hot for trees with many levels; it requires fewer than 256 levels per column
(`max_bins`), so group the tail first.

## Splits

```python
# Time-ordered
df = df.sort_values("event_date")
cut = int(len(df) * 0.8)
train, test = df.iloc[:cut], df.iloc[cut:]

# Grouped (no customer in both)
from sklearn.model_selection import GroupShuffleSplit
tr_idx, te_idx = next(GroupShuffleSplit(test_size=0.2, random_state=0).split(df, groups=df.customer_id))

# Stratified random
from sklearn.model_selection import train_test_split
train, test = train_test_split(df, test_size=0.2, stratify=df.y, random_state=0)
```

## Class imbalance in a first model

- Keep the natural class balance in the test set.
- Do not resample yet; score with PR-AUC and recall@capacity.
- `class_weight="balanced"` is acceptable for ranking, but distorts probabilities (log loss, calibration).

## What not to do yet

- Do not tune hyperparameters before the baseline table exists.
- Do not add feature selection, SMOTE, stacking or deep models.
- Do not drop rows with missing values (bias); impute in the pipeline.
- Do not look at the test set more than once per decision; iterate on validation folds.

## Sanity checks after the first fit

| Check | Expectation |
|-------|-------------|
| Train vs test metric | small gap; huge gap = overfitting or leakage |
| Metric by month in the test window | flat; declining = drift |
| Top coefficients / importances | plausible; an ID or post-event field on top = leak |
| Predictions on obviously different rows | sensible ordering |
| Score distribution | not all identical; not all 0/1 |
