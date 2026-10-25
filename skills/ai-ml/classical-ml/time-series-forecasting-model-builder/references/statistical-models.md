# Statistical Forecasting Models

## Quick map

| Model | Captures | Library |
|-------|----------|---------|
| Naive, seasonal naive, drift, mean | benchmarks | any; `ts_backtest.py` |
| Simple exponential smoothing | level | statsforecast `SimpleExponentialSmoothingOptimized`, statsmodels |
| Holt / Holt-Winters / ETS | level, trend (damped), season (additive/multiplicative) | statsforecast `AutoETS`, statsmodels `ETSModel`, `ExponentialSmoothing` |
| ARIMA / SARIMA | autocorrelation, differencing, seasonal AR/MA | statsforecast `AutoARIMA`, pmdarima |
| Theta | trend-damped SES, strong on M3/M4 | statsforecast `AutoTheta` |
| MSTL, TBATS | multiple seasonalities | statsforecast `MSTL`, `AutoTBATS` |
| Regression + ARIMA errors | covariates with autocorrelated noise | statsmodels `SARIMAX(exog=)` |
| Croston, SBA, TSB, ADIDA, IMAPA | intermittent demand | statsforecast `CrostonClassic`, `CrostonSBA`, `TSB`, `ADIDA`, `IMAPA` |
| Prophet | trend changepoints, holidays, multiple seasons | `prophet`; benchmark it against ETS, it often loses |

## statsforecast (fast, many series)

```python
from statsforecast import StatsForecast
from statsforecast.models import AutoETS, AutoARIMA, AutoTheta, SeasonalNaive, MSTL
df = sales.rename(columns={"date": "ds", "units": "y"}).assign(unique_id="s1")   # long format
sf = StatsForecast(models=[SeasonalNaive(7), AutoETS(season_length=7), AutoARIMA(season_length=7),
                           AutoTheta(season_length=7)], freq="D", n_jobs=-1)
fc = sf.forecast(df=df, h=28, level=[80, 95])                   # intervals included
cv = sf.cross_validation(df=df, h=28, step_size=28, n_windows=6)  # rolling origin
```
For `ts_backtest.py --forecasts`, write `origin` (= cutoff), `date` (= ds), `model`, `forecast`. These
are verified on the fixture: AutoETS MASE 1.367, AutoARIMA 1.381.

## statsmodels

```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import STL
fit = ExponentialSmoothing(y, trend="add", seasonal="add", seasonal_periods=7, damped_trend=True).fit()
fit.forecast(28)
stl = STL(y, period=7, robust=True).fit()      # trend, seasonal, resid; strength = 1 - var(resid)/var(comp+resid)
```

## Choosing within ETS

- Multiplicative season when the seasonal swing grows with the level (retail, traffic). Additive when it
  is constant.
- A damped trend almost always forecasts better beyond a few steps than a linear trend.
- AutoETS selects by AICc. Still compare with seasonal naive on the backtest.

## Intermittent demand

| Class (Syntetos-Boylan) | ADI | CV^2 | Method |
|-------------------------|-----|------|--------|
| smooth | < 1.32 | < 0.49 | ETS / SES |
| erratic | < 1.32 | >= 0.49 | SES, ML with care |
| intermittent | >= 1.32 | < 0.49 | Croston / SBA |
| lumpy | >= 1.32 | >= 0.49 | SBA / TSB; consider aggregation |

- SBA corrects Croston's upward bias by (1 - alpha/2). TSB updates the demand probability every period and
  handles obsolescence.
- Evaluate with RMSSE, scaled squared errors or inventory outcomes (service level, holding cost), not
  MAE. A flat zero forecast wins on MAE and stocks nothing.
- Temporal aggregation (weekly instead of daily, ADIDA) often helps more than a better model.

## Multiple seasonalities

Hourly data has daily (24) and weekly (168) cycles. Daily data has weekly and yearly cycles. Use MSTL
(STL per season), TBATS, or calendar features in an ML model. Holt-Winters handles only one season.
