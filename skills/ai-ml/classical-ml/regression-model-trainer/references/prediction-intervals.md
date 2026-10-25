# Prediction Intervals

## Quantile models

```python
from sklearn.ensemble import HistGradientBoostingRegressor
lo = HistGradientBoostingRegressor(loss="quantile", quantile=0.1, random_state=0).fit(X_tr, y_tr)
hi = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, random_state=0).fit(X_tr, y_tr)
p10, p90 = lo.predict(X_te), hi.predict(X_te)
p10, p90 = np.minimum(p10, p90), np.maximum(p10, p90)          # fix crossing quantiles
coverage = np.mean((y_te >= p10) & (y_te <= p90))              # target ~0.80
```
Quantile models are not guaranteed to reach nominal coverage, especially with small data or shift.

## Split conformal (distribution-free)

```python
# 1. split training data into fit / calibration
model.fit(X_fit, y_fit)
resid = np.abs(y_cal - model.predict(X_cal))
alpha = 0.2
n = len(resid)
qhat = np.quantile(resid, np.ceil((n + 1) * (1 - alpha)) / n, method="higher")
# 2. intervals for new rows
pred = model.predict(X_new)
lower, upper = pred - qhat, pred + qhat                       # >= 80% marginal coverage under exchangeability
```
Constant width; for adaptive widths normalise residuals by a predicted scale (e.g. a model of |residual|) or
use CQR.

## Conformalised quantile regression (CQR)

```python
q_lo, q_hi = lo.predict(X_cal), hi.predict(X_cal)
scores = np.maximum(q_lo - y_cal, y_cal - q_hi)
qhat = np.quantile(scores, np.ceil((len(scores) + 1) * (1 - alpha)) / len(scores), method="higher")
lower, upper = lo.predict(X_new) - qhat, hi.predict(X_new) + qhat
```
Adaptive width with valid marginal coverage.

## MAPIE

The `mapie` library implements split/cross conformal, jackknife+ and CQR for scikit-learn regressors with
a common API (its interface changed in v1; check the version you install).

## Evaluating intervals

| Metric | Meaning |
|--------|---------|
| Coverage | share of actuals inside the interval; compare with nominal |
| Mean width | sharpness; narrower is better at equal coverage |
| Coverage by segment / decile | conditional validity; marginal coverage can hide failures |
| Pinball loss per quantile | proper scoring rule for quantiles |
| Interval score (Winkler) | width + penalty for misses: `(u − l) + 2/α · (l − y)·1[y<l] + 2/α · (y − u)·1[y>u]` |

`residual_report.py --lower p10 --upper p90 --nominal 0.8` reports coverage and width.

## Time series and shift

Exchangeability fails under drift: recalibrate conformal quantiles on recent data (rolling calibration
window), or use adaptive conformal methods for sequences.
