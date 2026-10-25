# Regression and Forecast Metrics

Notation: e = ŷ − y, n rows.

## Point-error metrics

| Metric | Formula | Minimised by | Use | Misleads when |
|--------|---------|--------------|-----|---------------|
| MAE | mean|e| | median | typical error in units | big misses are much worse |
| RMSE | sqrt(mean e²) | mean | large errors costly | outliers are noise |
| MedAE | median|e| | - | very robust summary | tail errors matter |
| Bias (ME) | mean e | - | guardrail for systematic over/under | used alone |
| R² | 1 − SSE/SST | mean | model comparison on one dataset | comparing datasets; reporting to business |
| MAPE | mean|e/y| | a value below the median (favours under-forecasts) | relative error, values far from 0 | y near 0; mixing small and large items |
| sMAPE | mean 2|e|/(|y|+|ŷ|) | - | bounded relative error | asymmetric; unstable near 0 |
| WAPE | Σ|e| / Σ|y| | median-weighted | business reporting across items | a few huge items dominate (weight explicitly) |
| RMSLE | sqrt(mean (log1p ŷ − log1p y)²) | geometric-mean-like | relative errors, positive skewed targets | under-prediction penalised less |

## Deviance metrics (for GLM-style targets)

| Target | Metric | sklearn |
|--------|--------|---------|
| Counts | mean Poisson deviance | `mean_poisson_deviance` |
| Positive, skewed (claim size) | mean Gamma deviance | `mean_gamma_deviance` |
| Zero-inflated positive (insurance loss) | mean Tweedie deviance, power 1 < p < 2 | `mean_tweedie_deviance(power=1.5)` |

Use the deviance that matches the training objective; report MAE alongside for interpretability.

## Forecast metrics

### MASE
```
MASE = mean|e_t| / ( (1/(T−m)) Σ_{t=m+1..T} |y_t − y_{t−m}| )      # denominator on the training data
```
Scale-free, defined with zeros, < 1 means better than in-sample seasonal naive (m = season length; m = 1 for
non-seasonal naive). Average MASE across series for global comparison.

### RMSSE
Squared version of MASE (used in the M5 competition), weighted by series revenue.

### Pinball (quantile) loss
```
L_q(y, ŷ) = q·(y − ŷ) if y ≥ ŷ else (1 − q)·(ŷ − y)
```
Average across quantiles approximates CRPS. Report with **coverage**: share of actuals inside the
[q_low, q_high] interval, which should match the nominal level (80% interval -> ~80%).

### Bias for forecasts
```
bias% = Σ(ŷ − y) / Σ y
```
Tracking signal = cumulative error / MAD; |TS| > 4 flags a biased forecast.

## Loss and metric alignment

| You report | Train with |
|------------|-----------|
| MAE | absolute error / L1, or quantile 0.5 |
| RMSE | squared error |
| Quantile q | pinball loss at q |
| MAPE | sample weights 1/|y| with L1 (roughly) |
| WAPE | L1 |
| Poisson deviance | Poisson objective |
| RMSLE | squared error on log1p(y) |

Training on log1p(y) with squared error then reporting MAE in original units estimates the median times a
bias factor; for sums (total revenue) correct with a smearing factor.

## Slicing

Report MAE/bias by segment (product size, region, horizon). A small overall error can hide a large systematic
under-prediction for the biggest customers (see `metric_report.py --segment`).

## scikit-learn calls

```python
from sklearn.metrics import (mean_absolute_error, mean_absolute_percentage_error, mean_pinball_loss,
                             mean_poisson_deviance, mean_squared_error, mean_squared_log_error,
                             mean_tweedie_deviance, median_absolute_error, r2_score, root_mean_squared_error)

root_mean_squared_error(y, p)                         # sklearn >= 1.4
mean_pinball_loss(y, p_q90, alpha=0.9)
mean_tweedie_deviance(y, p, power=1.5)
wape = abs(y - p).sum() / abs(y).sum()
```

`mean_absolute_percentage_error` returns a fraction (0.12 = 12%) and does not skip zeros: it divides by
`max(|y|, eps)`, so a single zero actual produces an enormous value.
