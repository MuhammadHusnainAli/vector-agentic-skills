---
name: feature-scaling-advisor
description: "Decide whether and how to scale or transform numeric features for a given model: no scaling for trees and gradient boosting, StandardScaler, RobustScaler for outliers, MinMaxScaler and MaxAbsScaler (sparse data), log1p, Box-Cox and Yeo-Johnson PowerTransformer for skew, QuantileTransformer for heavy tails, clipping/winsorising, and target transforms (TransformedTargetRegressor) for skewed regression targets. Measures skew, robust outliers, zeros, negatives and bounds per column, shows how one wide column dominates raw distances, emits a leak-free ColumnTransformer, and measures the effect of each scaling on a k-NN model with cross-validation. Use when someone asks whether to normalise or standardise, which scaler to use, why k-NN / k-means / SVM / PCA / logistic regression behave oddly, how to handle skewed or outlier-heavy features, or whether scaling leaks information."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Feature Scaling Advisor

Scaling matters for any model that uses **distances** (k-NN, k-means, SVM with RBF, DBSCAN), **penalties**
(ridge, lasso, elastic net, regularised logistic regression), **gradients** (neural nets, SGD) or
**variance** (PCA). It does nothing for trees and gradient boosting, which split on thresholds and are
invariant to monotone transforms. The choice of scaler follows the column's shape: symmetric -> standard;
outliers -> robust; right-skewed -> log/Box-Cox/Yeo-Johnson; heavy tails -> quantile; sparse -> max-abs.
`scripts/scaling_plan.py` recommends a transform per column and emits the ColumnTransformer;
`scripts/scale_impact.py` shows the effect on a k-NN model with cross-validation.

## Trigger Conditions

Activate this skill when the user:
- Asks "should I normalise / standardise?", "which scaler?", "MinMax or Standard?"
- Uses k-NN, k-means, SVM, PCA, regularised linear models or neural nets and gets odd results
- Has skewed, heavy-tailed or outlier-heavy numeric features, or a skewed regression target
- Wonders whether to scale for XGBoost / LightGBM / random forest (no)
- Suspects scaling leakage (scaler fitted on the full dataset before CV)

## Workflow

```
1. MODEL     -> tree-based? stop: no scaling (keep the raw units for interpretation)
2. MEASURE   -> python scripts/scaling_plan.py data.csv --model linear --target y --drop id
3. CHOOSE    -> per column: standard / robust / log1p+standard / power / quantile / passthrough
4. BUILD     -> python scripts/scaling_plan.py ... --code   (ColumnTransformer inside a Pipeline)
5. EVIDENCE  -> python scripts/scale_impact.py data.csv --target y   (raw vs scaled k-NN, CV)
6. TARGET    -> skewed regression target? TransformedTargetRegressor(log1p) or a Tweedie/Gamma loss
7. VERIFY    -> scaler fitted on training folds only; same transform at serving time
```

## Which Models Need Scaling

| Model | Needs scaling? | Why |
|-------|----------------|-----|
| Decision tree, random forest, extra trees | no | threshold splits are invariant to monotone transforms |
| Gradient boosting (XGBoost, LightGBM, CatBoost, HistGBM) | no | same; binning is rank-based |
| Linear / logistic regression, unregularised | for interpretation and solver speed only | coefficients rescale; predictions do not change |
| Ridge / lasso / elastic net / regularised logistic | **yes** | the penalty treats all coefficients equally, so units decide which features get shrunk |
| SVM (RBF or linear) | **yes** | distances and margins |
| k-NN, k-means, DBSCAN, hierarchical clustering | **yes** | Euclidean distance is dominated by the widest column |
| PCA, factor analysis | **yes** (or use correlation-based PCA) | components chase the largest variance |
| Neural networks, SGD-based models | **yes** | gradient conditioning and activation ranges |
| Naive Bayes (Gaussian) | no (per-feature distributions) | - |
| UMAP, t-SNE | usually yes | distance-based neighbourhoods |

`scale_impact.py` on the churn fixture: raw 15-NN ROC-AUC 0.58 (`total_charges` holds 99.9% of raw distance
variance) vs 0.76-0.78 scaled.

## Scaler Selection by Column Shape

| Column shape | Transform | scikit-learn |
|--------------|-----------|--------------|
| Roughly symmetric, few outliers | standardise | `StandardScaler()` |
| Outliers you want to keep but not let dominate | robust scaling (median / IQR) | `RobustScaler()` |
| Right-skewed, non-negative, has zeros | log1p then standardise | `FunctionTransformer(np.log1p)` + `StandardScaler()` |
| Right-skewed, strictly positive | Box-Cox | `PowerTransformer(method="box-cox")` |
| Skewed with negative values | Yeo-Johnson | `PowerTransformer(method="yeo-johnson")` |
| Heavy tails, outliers, any shape (NN inputs) | rank -> normal or uniform | `QuantileTransformer(output_distribution="normal")` |
| Already in [0, 1] (proportions) | none or standardise | - |
| Bounded inputs required (some NN activations, images) | min-max | `MinMaxScaler()` |
| Sparse matrix (TF-IDF, many one-hot) | max-abs (keeps zeros) | `MaxAbsScaler()` |
| Binary 0/1 indicators | leave as is | `"passthrough"` |
| Extreme errors / sentinel values (999999) | fix the data, then clip | `np.clip` at train quantiles |

`PowerTransformer` standardises its output by default (`standardize=True`). `QuantileTransformer` is
non-linear and distorts distances between far-apart values; prefer it for heavy-tailed inputs to neural nets
or linear models, not when relative magnitudes matter.

Transforms, formulas and their failure modes: [transforms-and-outliers.md](references/transforms-and-outliers.md).

## Scaling Without Leakage

```python
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, PowerTransformer
from sklearn.linear_model import LogisticRegression

prep = ColumnTransformer([
    ("std", StandardScaler(), ["tenure_months", "support_calls"]),
    ("pow", PowerTransformer(method="yeo-johnson"), ["total_charges"]),
], remainder="passthrough")
model = Pipeline([("prep", prep), ("clf", LogisticRegression(C=1.0, max_iter=2000))])
# cross_val_score(model, X, y, cv=cv) refits the scalers on every training fold.
```
- **Never** `scaler.fit(X_all)` before splitting or before cross-validation: test-fold means and variances
  leak into training. The effect is usually small for standard scaling and larger for quantile transforms,
  target-dependent steps and small datasets, but it is always avoidable.
- Fit once on training data, persist the fitted pipeline, apply the same object at serving time.
- Time series: fit on the past window only; refit at each retrain.

More leakage cases and serving issues: [scaling-pitfalls.md](references/scaling-pitfalls.md).

## Regression Targets

| Target shape | Option |
|--------------|--------|
| Right-skewed positive (prices, durations) | `TransformedTargetRegressor(regressor=..., func=np.log1p, inverse_func=np.expm1)` |
| Counts / zero-heavy | Poisson or Tweedie loss instead of transforming |
| Symmetric | no transform needed (scaling the target only matters for neural nets) |

Log-target models predict something closer to the median; when sums matter (total revenue), correct the
retransformation bias (smearing) or use a Gamma/Tweedie loss. Details:
[transforms-and-outliers.md](references/transforms-and-outliers.md).

## Output Format

When advising on scaling, answer with:
1. **Does this model need scaling?** - yes/no with the reason (distance, penalty, gradient, variance, or tree
   invariance).
2. **Per-column plan** - the `scaling_plan.py` table: shape statistics and the chosen transform.
3. **Code** - the ColumnTransformer inside a Pipeline.
4. **Evidence** - `scale_impact.py` result (raw vs scaled), or CV comparison of two scalers.
5. **Target handling** - for regression with a skewed target.
6. **Serving notes** - persisted fitted transformer, behaviour on out-of-range values.

## Scripts

```bash
python scripts/scaling_plan.py data.csv --model linear --target price --drop house_id
python scripts/scaling_plan.py data.csv --model tree
python scripts/scaling_plan.py data.csv --model nn --target y --json
python scripts/scaling_plan.py data.csv --model linear --target y --code > prep.py
```
Models: tree, linear (also SVM, k-NN, k-means, PCA), nn, sparse. Per numeric column: min, max, mean, std,
median, IQR, skew, robust outlier share (|x - median| / (1.4826 MAD) > 3.5), zero share, negatives,
distinct count; the transform with the reason; and the largest/smallest standard-deviation ratio across
columns. `--code` prints a ColumnTransformer of median imputation + scaler per group with unique step names.
Exit codes: 0 printed, 2 usage error or no numeric columns.

```bash
python scripts/scale_impact.py data.csv --target churned --drop customer_id
python scripts/scale_impact.py data.csv --target price --k 10 --folds 5 --max-rows 1500 --json
```
Pure-Python k-NN with K-fold CV on the numeric columns under raw, standard, robust, log1p+standard and min-max
scaling (fitted on each training fold): ROC-AUC for binary targets, MAE for numeric ones; plus each column's
share of raw squared-distance variance. Exit codes: 0 measured, 2 usage error or not enough numeric rows.

## Additional Resources

| File | Content |
|------|---------|
| [scaler-catalog.md](references/scaler-catalog.md) | Every scaler: formula, parameters, output range, sensitivity to outliers, sparse support, inverse transform |
| [transforms-and-outliers.md](references/transforms-and-outliers.md) | log, Box-Cox, Yeo-Johnson, quantile, winsorising, binning; outlier detection; target transforms and retransformation bias |
| [model-sensitivity.md](references/model-sensitivity.md) | Why each model family is or is not scale-sensitive, with small demonstrations (penalties, distances, PCA, gradients) |
| [scaling-pitfalls.md](references/scaling-pitfalls.md) | Leakage, fitting on all data, time series, serving drift, clipping at serving time, scaling one-hot columns, interpretation of scaled coefficients |
