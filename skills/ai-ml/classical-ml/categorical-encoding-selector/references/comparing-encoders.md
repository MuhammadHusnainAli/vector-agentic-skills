# Comparing Encoders

## Experiment design

```python
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, TargetEncoder


class FrequencyEncoder(BaseEstimator, TransformerMixin):
    """Level share learned in fit (training fold only); unseen levels -> 0."""

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.maps_ = {c: X[c].value_counts(normalize=True) for c in X.columns}
        return self

    def transform(self, X):
        X = pd.DataFrame(X)
        return np.column_stack([X[c].map(self.maps_[c]).fillna(0.0).to_numpy(dtype=float) for c in X.columns])


high_card = ["merchant"]
low_card = ["channel", "country"]
num_cols = ["amount", "hour"]
encoders = {
    "onehot_rare": OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20),
    "target": TargetEncoder(smooth="auto"),
    "frequency": FrequencyEncoder(),
    "ordinal": OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
}
cv = StratifiedKFold(5, shuffle=True, random_state=0)       # or TimeSeriesSplit for temporal data
for name, enc in encoders.items():
    prep = ColumnTransformer([
        ("hc", enc, high_card),
        ("lc", OneHotEncoder(handle_unknown="ignore"), low_card),
        ("num", "passthrough", num_cols),
    ])
    scores = cross_val_score(make_pipeline(prep, make_model()), X, y, cv=cv, scoring="average_precision")
    print(f"{name:<12} {scores.mean():.4f} ± {scores.std():.4f}")
```

Rules:
- Same folds, same model, same hyperparameters for each variant.
- For temporal data, compare on a time-ordered holdout too: encoders that memorise levels look better on
  random folds than on the future.
- Measure width (number of output columns) and fit/predict time alongside the metric.

## Typical outcomes

| Model | Low cardinality | High cardinality |
|-------|-----------------|------------------|
| Logistic regression | one-hot best | target (cross-fitted) + frequency usually beat one-hot with rare grouping |
| Random forest | ordinal ≈ one-hot | target / frequency; one-hot dilutes splits |
| LightGBM / XGBoost | native ≈ ordinal ≈ one-hot | native competitive up to a few hundred levels; target/frequency more robust beyond |
| CatBoost | cat_features | cat_features (usually the strongest without extra work) |
| k-NN / SVM | one-hot (scaled) | target encoding or embeddings; one-hot distances get dominated by mismatches |

These are tendencies, not guarantees; run the comparison.

## Cost table

| Encoder | Output width | Unseen levels | Needs target | Interpretable |
|---------|--------------|---------------|--------------|---------------|
| One-hot | k (or fewer with grouping) | ignore/infrequent | no | yes |
| Ordinal | 1 | unknown_value | no | partly |
| Target | 1 (classes for multiclass) | prior | yes | yes (mean outcome) |
| Frequency | 1 | 0 | no | yes |
| Hashing | N | yes | no | no |
| Native GBM | 1 | model-specific | no | partly |

## Reporting

Report the chosen encoder per column with the comparison scores (mean ± std on identical folds), the
holdout check for target encoding, and the serving behaviour for unseen levels.
