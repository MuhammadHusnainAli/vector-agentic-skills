# Residual Diagnostics

Compute on out-of-fold or holdout predictions, never on training predictions.

## 1. Decile calibration

Sort by prediction, cut into 10 groups, compare mean prediction with mean actual:
```python
import pandas as pd
d = pd.DataFrame({"y": y, "p": p})
d["decile"] = pd.qcut(d.p.rank(method="first"), 10, labels=False) + 1
cal = d.groupby("decile").agg(mean_pred=("p", "mean"), mean_true=("y", "mean"))
cal["ratio"] = cal.mean_pred / cal.mean_true
```
Ratios should be ~1 everywhere. A rising curve below 1 at the top and above 1 at the bottom is
"regression to the mean" (shrinkage); common with strong regularisation and squared error on skewed targets.

## 2. Heteroscedasticity

Correlation between |residual| and prediction (or a binned plot of residual SD by prediction decile). Growing
spread means relative errors are roughly constant: log targets or deviance losses fit better, and constant-width
intervals are wrong.

## 3. Residuals vs features

For each important feature, plot mean residual by quantile bin:
```python
d["feature_bin"] = pd.qcut(X_valid["sqft"], 10, duplicates="drop")
d.groupby("feature_bin").apply(lambda g: (g.p - g.y).mean())
```
A systematic pattern means the model misses a non-linearity or interaction in that feature (add splines,
interactions, or let the GBM split more).

## 4. Segment bias

MAE and bias per business segment (region, product line, size band). A small overall bias can hide a large
under-prediction for the most valuable segment (the fixture's `large` segment: −14.8%).

## 5. Residuals over time

Mean residual by month of the prediction date: drift or a structural break shows up as a trend or step.

## 6. Worst errors

Read the 20 largest absolute errors row by row: unit errors, duplicated records, outliers that are data
issues, or a missing feature that explains them.

## 7. Influence (linear models)

Cook's distance (`statsmodels` `get_influence().cooks_distance`) flags rows that move the fit; inspect them,
do not delete them automatically.

## Patterns and actions

| Pattern | Action |
|---------|--------|
| Under-prediction at the top, over at the bottom | less regularisation, log/deviance loss, features for extremes |
| Spread grows with level | log target / Gamma; relative metrics; adaptive intervals |
| Residual trend vs a feature | non-linear term or interaction |
| One segment biased | segment feature or interaction; separate model |
| Trend over time | retrain cadence, time features, drift investigation |
| A few huge errors | data quality; robust loss |
