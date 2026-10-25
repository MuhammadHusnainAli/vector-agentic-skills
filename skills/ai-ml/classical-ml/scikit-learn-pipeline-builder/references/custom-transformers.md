# Custom Transformers

## The estimator contract

1. `__init__` stores each parameter **as an attribute with the same name**, unchanged; no validation, no
   computation. `clone()`, `get_params()` and `set_params()` depend on this.
2. `fit(X, y=None)` learns state into attributes ending in `_` and returns `self`.
3. `transform(X)` uses only fitted state; never refits.
4. Set `n_features_in_` (and `feature_names_in_` for DataFrames) in `fit`.
5. Provide `get_feature_names_out` (or inherit `OneToOneFeatureMixin` / `ClassNamePrefixFeaturesOutMixin`).

Mixin order: mixins first, `BaseEstimator` last: `class T(OneToOneFeatureMixin, TransformerMixin, BaseEstimator)`.

## Stateful example: clipping + log

```python
import numpy as np
from sklearn.base import BaseEstimator, OneToOneFeatureMixin, TransformerMixin
from sklearn.utils.validation import check_is_fitted, validate_data   # validate_data: sklearn >= 1.6

class Log1pClip(OneToOneFeatureMixin, TransformerMixin, BaseEstimator):
    def __init__(self, upper_quantile=0.99):
        self.upper_quantile = upper_quantile

    def fit(self, X, y=None):
        X = validate_data(self, X, ensure_all_finite="allow-nan")
        self.upper_ = np.nanquantile(X, self.upper_quantile, axis=0)
        return self

    def transform(self, X):
        check_is_fitted(self)
        X = validate_data(self, X, ensure_all_finite="allow-nan", reset=False)
        return np.log1p(np.clip(X, 0, self.upper_))

    def __sklearn_tags__(self):                 # declare NaN support so check_estimator and pipelines know
        tags = super().__sklearn_tags__()
        tags.input_tags.allow_nan = True
        return tags
```
On scikit-learn < 1.6 use `self._validate_data(...)` (method), `force_all_finite=` and `_more_tags()` returning
`{"allow_nan": True}` instead. This class passes `check_estimator` on scikit-learn 1.9.

## Column-aware example: ratio features from a DataFrame

```python
class RatioFeatures(TransformerMixin, BaseEstimator):
    def __init__(self, pairs=(("total_charges", "tenure_months"),)):
        self.pairs = pairs

    def fit(self, X, y=None):
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        out = {f"{a}_per_{b}": X[a] / X[b].replace(0, np.nan) for a, b in self.pairs}
        return pd.DataFrame(out, index=X.index)

    def get_feature_names_out(self, input_features=None):
        return np.array([f"{a}_per_{b}" for a, b in self.pairs], dtype=object)
```
Use with a ColumnTransformer column list that contains every referenced column.

## Stateless vs stateful

| Kind | Example | Placement |
|------|---------|-----------|
| Stateless | date parts, ratios, log1p | anywhere; `FunctionTransformer` is enough |
| Stateful (learns from X) | clipping bounds, frequency maps, vocabularies | must be a fitted transformer in the Pipeline |
| Supervised (learns from y) | target encoding, supervised binning, selection | in the Pipeline; cross-fitted if it encodes rows used for training |

## Testing

```python
from sklearn.utils.estimator_checks import check_estimator
check_estimator(Log1pClip())          # runs the full API compliance suite (strict; aim for library code)
```
Unit-test behaviour too: fit on one frame, transform another with unseen values, NaN, and different column
order; assert shapes and names.

## Common bugs

| Bug | Symptom |
|-----|---------|
| Modifying parameters in `__init__` (`self.cols = list(cols)`) | `clone` warnings, searches ignore settings |
| Learning state in `transform` | CV leakage, different results per call |
| Returning a new object from `fit` | pipelines break |
| Mutating the input DataFrame | caller's data changes; use `X = X.copy()` |
| No `get_feature_names_out` | downstream `get_feature_names_out` fails |
| Lambdas stored as parameters | pickling fails |
