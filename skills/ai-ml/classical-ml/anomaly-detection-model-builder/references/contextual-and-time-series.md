# Contextual and Time-Series Anomalies

## Context-relative features

A value is anomalous relative to a context. Encode the context in the features:

| Context | Feature |
|---------|---------|
| Entity history | amount / entity's mean over 30 days; z-score vs own history |
| Peer group | value / median of the peer group (same merchant category, same machine type) |
| Time of day / week | value vs the mean for that hour-of-week (seasonal baseline) |
| Recent trend | value vs rolling mean of the last N observations |
| Combination | ratios between related measures (temperature per unit load) |

```python
g = df.sort_values("ts").groupby("card_id")["amount"]
df["amt_vs_own_mean"] = df["amount"] / g.transform(lambda s: s.shift().rolling(30, min_periods=5).mean())
base = df.groupby(df.ts.dt.dayofweek * 24 + df.ts.dt.hour)["requests"].median()
df["vs_hour_of_week"] = df["requests"] / (df.ts.dt.dayofweek * 24 + df.ts.dt.hour).map(base)
```

## Time-series anomalies via residuals

1. Model the expected value (seasonal naive, STL, ETS, a GBM on lags) on history.
2. Residual = actual − expected; scale by a robust spread of past residuals.
3. Flag |residual| / scale > threshold; require persistence (2-3 consecutive points) for level shifts.

```python
from statsmodels.tsa.seasonal import STL
res = STL(series, period=7, robust=True).fit()
resid = res.resid
score = (resid - resid.median()).abs() / (1.4826 * (resid - resid.median()).abs().median())
```

## Change points

Level shifts and variance changes: CUSUM, Bayesian online change-point detection, `ruptures` (PELT, binary
segmentation). Useful for drift in sensors and KPIs.

## Collective anomalies

Unusual sequences (bursts, repeated small transactions, scanning patterns):
- window aggregates (counts, distinct counts, sums in 1 min / 1 h) as features, then point detectors;
- sequence models (n-gram frequencies, HMM likelihood, sequence autoencoders) when order matters.

## Seasonality traps

- Weekends, holidays and month-end look anomalous to a model without calendar features.
- Daylight-saving shifts create fake hourly anomalies; use UTC or local time consistently.
- Growth trends make old baselines stale: use rolling or recent-window baselines.
