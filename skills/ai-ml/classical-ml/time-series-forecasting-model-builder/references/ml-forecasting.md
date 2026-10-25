# Machine Learning Forecasting

## Features

| Group | Examples | Leak-safe rule |
|-------|----------|----------------|
| Lags | y(t-H), ..., y(t-H-season+1), y(t-364) | minimum lag >= horizon (direct), or recursive prediction |
| Rolling statistics | mean/std/min/max over 7, 14, 28 periods | window ends at t-H |
| Calendar | day of week, month, day of year (sin/cos), week, holidays, paydays, events | known in advance |
| Known-future covariates | planned price, promotions, opening hours | only values fixed at forecast time |
| Static | store size, product category, region | fine |
| Series id | categorical id in a global model | fine |
| Trend handling | target / rolling mean, differences, or linear detrend | fit within the training window |

Tree models cannot predict outside the target range seen in training, so an upward trend gets flattened.
Detrend (the generated script's `--detrend` fits a linear trend per training window), model ratios to a
rolling level, or difference the target. On the fixture, detrending cut MASE from 1.088 to 0.889.

## Strategies for multi-step forecasts

| Strategy | How | Pros / cons |
|----------|-----|-------------|
| Recursive | one-step model, feed predictions back as lags | one model; errors compound; needs lag 1 features |
| Direct (one model per step) | H models, model h uses lags >= h | no compounding; H models |
| Direct with minimum lag = H (generated script) | one model, all lags >= H | one model, leak-free for every step; loses the most recent information for short steps |
| Multi-output (MIMO) | predict the H-vector at once | captures step dependence; needs suitable learners |

## Global models

One model trained on many related series, with series id or static features, usually beats per-series models
when series are short or noisy. This was the case in M5, where LightGBM global models won.

```python
panel["series_id"] = panel["store"].astype("category")
# features computed per series with groupby(...).shift(H).rolling(...); then one LGBMRegressor on all rows
```
Normalise targets per series (divide by the series mean) so large series do not dominate, and add the
scale back after prediction. Use the Tweedie objective for zero-inflated sales.

## Hierarchies

Store x product x region totals must add up. Forecast at each level and reconcile with bottom-up, top-down
or MinT (`hierarchicalforecast` package). MinT usually improves accuracy at all levels.

## Intervals

| Method | Notes |
|--------|-------|
| Split-conformal on backtest residuals (generated script) | distribution-free; calibrated only for regimes seen in the folds |
| Quantile regression (LightGBM `objective="quantile"`, alpha=0.1 / 0.9) | one model per quantile; can cross |
| Model-based (ETS/ARIMA) | assume the model is right; often too narrow |
| Bootstrapped residual paths | for recursive models |

Check coverage on a later holdout. On the fixture: 0.71-0.86 in normal months for 80% intervals, but 0.46 in
the December peak that the folds did not include.

## Production

- Retrain on a schedule (weekly) and backtest every retrain against the previous model and seasonal naive.
- Monitor error by horizon and bias, with labels arriving over the horizon. Alert on sustained bias.
- Log forecasts with their origin, so they can be evaluated exactly as in the backtest.
- Plan for structural breaks (new stores, product launches, pandemics): override or exclude periods, and
  add cold-start rules for new series (use the category average or similar series).
