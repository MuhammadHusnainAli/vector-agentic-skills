# Transforms and Outliers

## Variance-stabilising transforms

| Transform | Formula | Domain | Use |
|-----------|---------|--------|-----|
| log | log(x) | x > 0 | multiplicative effects, right skew |
| log1p | log(1 + x) | x >= 0 | counts and amounts with zeros |
| sqrt | √x | x >= 0 | counts (Poisson-like), milder than log |
| Box-Cox | (x^λ − 1)/λ, log x at λ = 0 | x > 0 | fitted λ per column |
| Yeo-Johnson | Box-Cox-like with a branch for negatives | all reals | skew with negative values |
| asinh | log(x + √(x² + 1)) | all reals | log-like for signed amounts (profit/loss) |
| logit | log(p / (1 − p)) | 0 < p < 1 | proportions |
| rank / quantile | empirical CDF | any | heavy tails, monotone relations only |

Rule of thumb: if the domain relationship is multiplicative ("10% more spend") use log; if you just need to tame
a tail for a linear model, Yeo-Johnson or quantile.

## Detecting outliers before choosing a scaler

| Method | Rule | Notes |
|--------|------|-------|
| Robust z-score | |x − median| / (1.4826 · MAD) > 3.5 | used by `scaling_plan.py` |
| IQR fences | x < Q1 − 1.5·IQR or x > Q3 + 1.5·IQR | flags many points in skewed data |
| Domain limits | age > 120, negative prices | data errors: fix, don't scale |
| Sentinels | 999999, −1 meaning "unknown" | replace with NaN + missing indicator |

Distinguish **errors** (fix or drop), **sentinels** (convert to missing) and **genuine extremes** (keep,
then choose a robust scaler or transform).

## Winsorising (clipping)

```python
lo, hi = X_train["amount"].quantile([0.01, 0.99])
X_train["amount"] = X_train["amount"].clip(lo, hi)
X_test["amount"] = X_test["amount"].clip(lo, hi)        # same bounds, learned on train
```
Implement as a transformer so bounds are learned per fold:
```python
from sklearn.base import BaseEstimator, TransformerMixin
import numpy as np

class QuantileClipper(BaseEstimator, TransformerMixin):
    def __init__(self, lower=0.01, upper=0.99):
        self.lower, self.upper = lower, upper

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.lo_ = np.nanquantile(X, self.lower, axis=0)
        self.hi_ = np.nanquantile(X, self.upper, axis=0)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lo_, self.hi_)
```

## Binning

`KBinsDiscretizer(n_bins=10, strategy="quantile", encode="onehot")` turns a skewed column into robust
indicators. Useful for linear scorecards (credit) and when the effect is step-like; costs information.

## Target transforms for regression

```python
from sklearn.compose import TransformedTargetRegressor
from sklearn.linear_model import Ridge
import numpy as np

model = TransformedTargetRegressor(regressor=make_pipeline(prep, Ridge()), func=np.log1p, inverse_func=np.expm1)
```
- Predictions are back-transformed automatically.
- **Retransformation bias:** exp(E[log y]) <= E[y]. For totals multiply predictions by the smearing factor
  `mean(exp(residuals_on_log_scale))` (Duan 1983), or fit a Gamma/Tweedie GLM/GBM on the raw target instead.
- Metrics must be computed on the original scale for business reporting.

## Choosing between options empirically

Compare two or three transforms on the same CV folds with the final model; pick the simplest that is not
worse. For tree models do not bother: they are invariant to monotone transforms of features (but not of the
target).
