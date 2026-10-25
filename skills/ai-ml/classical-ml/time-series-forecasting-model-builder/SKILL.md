---
name: time-series-forecasting-model-builder
description: "Build forecasting models that beat honest baselines: profile the series (frequency, gaps, duplicate timestamps, seasonality by autocorrelation, trend and seasonal strength, weekday and month effects, outliers, smooth/erratic/intermittent/lumpy demand by ADI and CV^2), backtest seasonal naive, drift, SES, Holt-Winters, Croston, SBA and TSB on rolling origins with MASE, RMSSE, WAPE and bias, score your own models' forecasts on the same origins, and generate a LightGBM forecaster with leak-free direct-strategy lags (every lag at least the horizon), rolling and calendar features, optional linear detrending (trees cannot extrapolate trend), multi-series support and split-conformal prediction intervals. Covers statsforecast/statsmodels ETS and ARIMA, global models, hierarchies and intermittent demand. Use when someone needs a demand, sales, traffic or load forecast, asks which forecasting model to use, how to backtest one, or why a model fails to beat naive."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Time Series Forecasting Model Builder

Most forecasting failures are evaluation failures. Common ones:
- comparing with no baseline, or a weak one
- one train/test split instead of rolling origins
- features that peek past the forecast origin
- MAPE on series with zeros
- tree models asked to extrapolate a trend

This skill makes the baseline and the protocol explicit first, then builds the model:
- `scripts/ts_profile.py` describes the series and recommends the model families
- `scripts/ts_backtest.py` scores the baselines (and your models) on identical rolling origins
- `scripts/gen_forecast_script.py` writes a leak-free LightGBM forecaster whose backtest output plugs
  straight back into `ts_backtest.py`

## Trigger Conditions

Activate this skill when the user:
- Needs a forecast (demand, sales, traffic, calls, energy load, inventory, KPIs)
- Asks which model to use (ETS, ARIMA, Prophet, LightGBM, Croston) or how to backtest
- Has a model that does not beat naive, or degrades in production
- Forecasts intermittent demand (spare parts, slow movers) or many related series

Time-based features for non-forecasting models: [time-based-feature-builder](../time-based-feature-builder/SKILL.md).
Splitting time data: [cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md).

## Workflow

```
1. PROFILE   -> python scripts/ts_profile.py sales.csv           (frequency, gaps, season, strength, demand class)
2. BASELINE  -> python scripts/ts_backtest.py sales.csv --horizon 28 --folds 6
3. BUILD     -> python scripts/gen_forecast_script.py --data sales.csv --value-col units --freq D --horizon 28 --detrend -o forecast.py
4. COMPARE   -> python forecast.py; python scripts/ts_backtest.py sales.csv --horizon 28 --folds 6 --forecasts backtest_forecasts.csv
5. DECIDE    -> deploy only what beats the best baseline on the same origins (MASE/RMSSE skill, bias)
6. DELIVER   -> forecast with intervals, the backtest table, and a monitoring plan
```

## Choosing a Model From the Profile

| Profile | Start with | Then try |
|---------|-----------|----------|
| Strong single seasonality, short history | seasonal naive, ETS / Holt-Winters | Theta, ARIMA |
| Multiple seasonalities (hourly: daily + weekly) | MSTL, TBATS | LightGBM with calendar features |
| Strong trend + seasonality, enough history | Holt-Winters / ETS | LightGBM on detrended target (`--detrend`) |
| Many related series (stores x products) | per-series ETS | **one global LightGBM** across series |
| Intermittent / lumpy (ADI >= 1.32) | Croston / SBA / TSB | probabilistic models (negative binomial), aggregated forecasts |
| Strong external drivers (price, promotions, weather) | regression with ARIMA errors | LightGBM with known-future covariates |
| Very short series (< 2 seasons) | naive / drift / mean | pool with similar series |

Sales fixture (daily, 2 years, weekly cycle, trend, December peak):

| Model | MASE | Skill vs snaive | WAPE |
|-------|------|-----------------|------|
| LightGBM, detrended (generated) | 0.889 | +46.5% | 4.0% |
| LightGBM, not detrended | 1.088 | +34.5% | 4.9% |
| Holt-Winters (stdlib) | 1.155 | +30.5% | 5.2% |
| statsforecast AutoETS | 1.367 | +17.8% | 6.2% |
| seasonal naive | 1.662 | 0 | 7.5% |

Model families and libraries: [statistical-models.md](references/statistical-models.md) and
[ml-forecasting.md](references/ml-forecasting.md).

## Evaluation Protocol

- **Rolling origin**: several forecast origins (5-10), each refit on data before it. One split is an anecdote.
- **Horizon = the business horizon**: forecasting 28 days ahead is a different problem from 1 day ahead.
  Report error by horizon step.
- **Scale-free metrics**: MASE (MAE / in-sample seasonal-naive MAE) to compare across series. Use RMSSE
  for intermittent demand, where MAE rewards forecasting zero. WAPE for business reporting. Always report
  bias.
- **Never MAPE with zeros or tiny values**: it is undefined or explodes. sMAPE is asymmetric.
- **Same origins for every model**: `ts_backtest.py --forecasts` scores external models on the baselines'
  origins (`--write-origins` exports them).
- **Multi-step MASE above 1 is normal**: the denominator is a one-step error. Compare models through the
  skill column.

Metric definitions, pitfalls and reporting: [forecast-evaluation.md](references/forecast-evaluation.md).

## Leakage Rules for ML Forecasters

| Leak | Prevention |
|------|------------|
| lag 1..h-1 used to forecast h steps ahead | direct strategy with minimum lag = horizon (the generated script) or recursive forecasting |
| rolling windows that include the target period | windows end H periods back (`shift(H).rolling(w)`) |
| scaling / target encoding fitted on all data | fit inside each training window |
| future covariates not known at forecast time (actual weather, actual price) | use forecasts, or values known in advance (planned prices, calendars) |
| random K-fold | rolling origin only |

## Prediction Intervals

The generated script builds split-conformal intervals from backtest residuals. Each step pools residuals
over ±3 neighbouring steps and scales them by the series' recent level. In checks on the fixture, holdout
coverage of the nominal 80% intervals was 0.71-0.86 in normal months but 0.46 in the December peak, which
the backtest folds did not contain. **Intervals are calibrated only for conditions the backtest covers.**
For seasonal peaks, include last year's peak in the folds (more folds, or origins chosen in that season).

## Output Format

When delivering a forecast, provide:
1. **Profile** - frequency, history, gaps, seasonality, trend, demand class, outliers.
2. **Backtest table** - all baselines and candidates on the same origins: MASE/RMSSE, skill, WAPE, bias,
   error by horizon.
3. **Chosen model** - why it wins, its features, and what it cannot capture.
4. **Forecast** - point forecast with intervals and coverage evidence.
5. **Monitoring** - the error metric tracked, the retraining cadence, and drift and bias alerts.

## Scripts

```bash
python scripts/ts_profile.py sales.csv
python scripts/ts_profile.py demand.csv --time-col week --value-col qty --horizon 8 --json
```
Strength measures come from a moving-average decomposition (0.89/0.94 on the fixture against
statsmodels STL 0.94/0.97; ACF identical). Exit codes: 0 profiled, 2 usage or read error.

```bash
python scripts/ts_backtest.py sales.csv --horizon 28 --folds 6
python scripts/ts_backtest.py demand.csv --horizon 8 --season 52 --forecasts my_forecasts.csv
python scripts/ts_backtest.py sales.csv --horizon 28 --folds 4 --write-origins origins.csv
```
Baselines are refit at each origin and clipped at zero for non-negative series. They are ranked by MASE,
or by RMSSE when more than 30% of values are zero, with a warning for near-zero forecasts. The
seasonal-naive MAE/MASE matches an independent pandas computation. Exit codes: 0 backtested, 2 usage or
read error.

```bash
python scripts/gen_forecast_script.py --data sales.csv --time-col date --value-col units --freq D --horizon 28 -o forecast.py
python scripts/gen_forecast_script.py --data stores.csv --id-col store --value-col sales --freq W --horizon 8 --fill zero --detrend
```
Writes `backtest_forecasts.csv` (for `ts_backtest.py --forecasts`) and `forecast.csv` (date, forecast, lo,
hi). Exit codes: 0 written, 2 usage error. `scripts/_ts_io.py` holds the shared loading, frequency
inference and gap filling.

## Additional Resources

| File | Content |
|------|---------|
| [forecast-evaluation.md](references/forecast-evaluation.md) | rolling origins, metrics (MASE, RMSSE, WAPE, bias, pinball, coverage), horizon analysis, pitfalls |
| [statistical-models.md](references/statistical-models.md) | ETS, ARIMA, Theta, MSTL/TBATS, intermittent methods, statsforecast and statsmodels code |
| [ml-forecasting.md](references/ml-forecasting.md) | features, direct vs recursive, global models, covariates, hierarchies, intervals, production |
