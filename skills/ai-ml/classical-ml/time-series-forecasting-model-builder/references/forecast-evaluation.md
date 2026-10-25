# Forecast Evaluation

## Rolling-origin (time series cross-validation)

```
history ----------------------------|origin 1|--h-->
history --------------------------------------|origin 2|--h-->
history ----------------------------------------------------|origin 3|--h-->
```
- Expanding window (all data before the origin) is the default. A sliding window suits regime changes.
- Space origins by the horizon (non-overlapping test windows) or by one season.
- Refit at every origin, or at least re-estimate state. Never use information after the origin.
- Include the periods that matter: if December decides the business, backtest Decembers.

## Metrics

| Metric | Formula | Use | Watch out |
|--------|---------|-----|-----------|
| MAE | mean \|y - f\| | units, robust | favours the median: forecasts of 0 for intermittent series |
| RMSE | sqrt(mean e^2) | penalises large misses | scale-dependent |
| MASE | MAE / in-sample MAE of the seasonal naive | compare across series; < 1 beats the one-step seasonal naive | multi-step MASE > 1 is common |
| RMSSE | sqrt(mean e^2 / in-sample MSE of the seasonal naive) | intermittent demand (M5) | |
| WAPE | sum \|e\| / sum \|y\| | business reporting, aggregates | dominated by large series |
| Bias | sum e / sum y | systematic over- or under-forecasting | report it always |
| MAPE | mean \|e / y\| | avoid | undefined with zeros, asymmetric |
| sMAPE | mean 2\|e\| / (\|y\| + \|f\|) | M3/M4 comparisons only | asymmetric, unstable near zero |
| Pinball loss | quantile loss at level q | quantile forecasts | |
| Coverage / interval width | share of actuals inside the intervals | prediction intervals | compare with the nominal level |
| CRPS | integrated pinball | full predictive distributions | |

Skill score: `1 - metric(model) / metric(baseline)`. The baseline is the seasonal naive unless a stronger
simple method exists (it often does: Holt-Winters beat snaive by 30% on the fixture).

## Error by horizon

Errors grow with the horizon. Report at least h=1, h/2 and h. A model that wins at h=1 but loses at h=28 is
the wrong model for a 28-day planning process. `ts_backtest.py` prints the MAE by horizon step for the best
model.

## Pitfalls

| Pitfall | Effect | Fix |
|---------|--------|-----|
| single train/test split | lucky or unlucky period decides | rolling origin |
| tuning on the test origins | optimistic results | nested: tune on earlier origins, evaluate on later ones |
| comparing on different origins or horizons | apples vs oranges | one protocol for every model (`--forecasts`) |
| filling gaps with future values | leakage | forward-fill or interpolate within the training window only |
| evaluating on aggregates only | hides SKU-level failure | report both levels |
| ignoring bias | systematic stock-outs or overstock | bias column and a bias alert in monitoring |
| MAPE on intermittent demand | infinite or meaningless | RMSSE, MASE, or inventory-based metrics (fill rate) |

## Reporting template

| Model | MASE | RMSSE | Skill vs snaive | WAPE | Bias | MAE h1 / h14 / h28 | 80% coverage |
|-------|------|-------|-----------------|------|------|--------------------|--------------|
