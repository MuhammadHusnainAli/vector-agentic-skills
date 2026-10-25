# Scaler Catalog

| Scaler | Formula | Output | Outlier-sensitive | Sparse-safe | Notes |
|--------|---------|--------|-------------------|-------------|-------|
| `StandardScaler` | (x − mean) / std | unbounded, mean 0, std 1 | yes (mean, std) | `with_mean=False` only | default for symmetric features |
| `RobustScaler` | (x − median) / IQR | unbounded | no | `with_centering=False` | `quantile_range=(25, 75)`; outliers stay outliers but do not set the scale |
| `MinMaxScaler` | (x − min) / (max − min) | [0, 1] (or `feature_range`) | very (min, max) | no | `clip=True` bounds unseen values at serving time |
| `MaxAbsScaler` | x / max|x| | [−1, 1] | yes | **yes** | for sparse data; keeps zeros |
| `Normalizer` | x / ‖x‖ per **row** | unit norm rows | - | yes | not a feature scaler: normalises samples (text vectors, cosine similarity) |
| `PowerTransformer` | Box-Cox / Yeo-Johnson, then standardise | ~Gaussian | moderately | no | λ fitted by maximum likelihood per column |
| `QuantileTransformer` | empirical CDF -> uniform or normal | [0, 1] or ~N(0, 1) | no | partially | non-linear; `n_quantiles` <= n rows; ties collapse |
| `FunctionTransformer(np.log1p)` | log(1 + x) | - | reduces right tail | yes (log1p(0) = 0) | x >= 0 only; add `inverse_func=np.expm1` |
| `SplineTransformer` | B-spline basis | several columns | - | no | non-linear effects for linear models, not scaling |
| `KBinsDiscretizer` | quantile / uniform / k-means bins | one-hot or ordinal | no | - | coarse, robust; loses within-bin information |

## Parameters worth knowing

```python
StandardScaler(with_mean=True, with_std=True)
RobustScaler(with_centering=True, with_scaling=True, quantile_range=(25.0, 75.0), unit_variance=False)
MinMaxScaler(feature_range=(0, 1), clip=False)
PowerTransformer(method="yeo-johnson", standardize=True)        # "box-cox" requires x > 0
QuantileTransformer(n_quantiles=1000, output_distribution="uniform", subsample=10_000, random_state=0)
```

`RobustScaler(unit_variance=True)` rescales so a normal feature ends with unit variance, making it comparable
with standard-scaled columns.

## Inverse transforms

All of the above have `inverse_transform` (FunctionTransformer only if `inverse_func` is given). Use it to
report predictions or cluster centres in original units.

## Mixed pipelines

```python
from sklearn.compose import ColumnTransformer, make_column_selector
prep = ColumnTransformer([
    ("num", StandardScaler(), make_column_selector(dtype_include="number")),
    ("cat", OneHotEncoder(handle_unknown="ignore"), make_column_selector(dtype_include="object")),
])
```
Do not standard-scale one-hot columns for tree models; for linear models with penalties, scaling one-hot
columns is optional (it changes how strongly rare levels are shrunk); many practitioners leave them as 0/1.
