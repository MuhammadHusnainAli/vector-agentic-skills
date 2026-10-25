# PDP, ICE and ALE

## Definitions

For a feature S and the other features C:

- **ICE** for row i: `f(x_S = v, x_C = x_C^(i))` as v varies over the grid: one curve per row.
- **PDP**: the average of the ICE curves, `PD(v) = mean_i f(v, x_C^(i))`. This is the marginal expectation:
  it pairs every grid value with every row's other features, including combinations that never occur.
- **Centred ICE (c-ICE)**: `ICE_i(v) - ICE_i(v_0)`, so curves start at zero and their shapes are comparable.
- **ALE**: accumulate the average *local* change in prediction across small intervals of x_S, using only the
  rows whose x_S falls in each interval:

```
for each quantile bin k = [z_{k-1}, z_k]:
    rows_k = rows with x_S in bin k
    effect_k = mean over rows_k of f(z_k, x_C) - f(z_{k-1}, x_C)
ALE(z_k) = sum_{j<=k} effect_j ; then subtract the data-weighted mean so the ALE is centred
```
Each row is only moved within its own neighbourhood, so ALE stays on realistic data when features are
correlated. For an additive model ALE recovers each component exactly (the generated script recovers a
linear coefficient to 1e-15).

## scikit-learn

```python
from sklearn.inspection import partial_dependence, PartialDependenceDisplay
X = X.astype({c: float for c in X.select_dtypes("integer").columns})       # required since 1.6
r = partial_dependence(model, X, ["tenure_months"], kind="both", grid_resolution=20,
                       percentiles=(0.05, 0.95), response_method="predict_proba")
r["average"], r["individual"], r["grid_values"]
PartialDependenceDisplay.from_estimator(model, X, ["tenure_months", ("tenure_months", "support_calls")],
                                        kind=["both", "average"], centered=True, subsample=300, random_state=0)
```
- `kind="both"` gives ICE + PDP. `centered=True` centres them. `subsample` limits the number of ICE lines.
- `categorical_features=[...]` gives a bar-style PDP per level.
- For a two-way PDP, the function takes `features=[a, b]` (a joint grid); `from_estimator` takes a tuple `(a, b)`.
- `method="recursion"` is a fast exact PDP for sklearn gradient boosting and trees (average only, not ICE).
- Multiclass: `r["average"]` has one row per class.

## Two-way PDP and the H-statistic

A two-way PDP over (a, b) shows the joint effect. Friedman's H-statistic measures how much of it is not
additive:

```
H^2_ab = sum (PD_ab(a,b) - PD_a(a) - PD_b(b))^2 / sum PD_ab(a,b)^2      (all centred)
```
H near 0 means no interaction and H near 1 means the effect is mostly interaction. It is expensive (a grid
squared x rows). Screen candidate pairs with ICE separators or SHAP interaction values first.

## ALE libraries

`alibi.explainers.ALE`, `PyALE`, `dalex` (`model_profile(type="accumulated")`), and R's `ALEPlot`/`iml`. The
generated script implements first-order ALE for numeric features without extra dependencies.

## Cost

| Method | Model evaluations |
|--------|-------------------|
| PDP / ICE | rows x grid points (per feature) |
| Two-way PDP | rows x grid^2 |
| ALE | 2 x rows (each row evaluated at its bin's two edges) |
| H-statistic | rows x grid^2 per pair |

Sample 300-1000 rows for ICE. More rows add lines, not insight.
