# Survival Models

## Kaplan-Meier

`S(t) = prod over event times t_i <= t of (1 - d_i / n_i)`, with the Greenwood variance
`Var = S^2 sum d_i / (n_i (n_i - d_i))`. Confidence intervals use the log(-log) transform (lifelines' and R's
default), which keeps them inside [0, 1].

```python
from lifelines import KaplanMeierFitter
km = KaplanMeierFitter().fit(df.duration_days, df.event, label="all")
km.survival_function_at_times([90, 180, 365]); km.median_survival_time_
km.plot_survival_function(at_risk_counts=True)
```

## Cox proportional hazards

`h(t | x) = h0(t) exp(x' beta)`. A hazard ratio `exp(beta)` multiplies the hazard at every time point.

```python
from lifelines import CoxPHFitter
cph = CoxPHFitter(penalizer=0.1).fit(train, "duration_days", "event")      # Efron ties
cph.print_summary(); cph.check_assumptions(train, p_value_threshold=0.05)
cph.predict_survival_function(test, times=[90, 180, 365])
```
- Ties: Efron (default in lifelines and R) is better than Breslow when many events share times.
- Stratification (`strata=["region"]`) gives each stratum its own baseline hazard, for covariates that
  violate PH but are not of interest.
- Non-linear effects: splines or binning. Interactions: explicit product columns.

## Parametric AFT models

`log T = x' beta + sigma * epsilon`. The coefficients are **time ratios**: exp(beta) = 1.5 means 50% longer
expected time.

| Distribution | Hazard shape |
|--------------|--------------|
| Exponential | constant |
| Weibull | monotone increasing or decreasing |
| Log-normal, log-logistic | rises then falls |
| Generalised gamma | flexible, nests the others |

AFT models extrapolate beyond the follow-up (e.g. lifetime value), but only as well as the distribution fits.
Compare by AIC and with KM curves. Lifelines: `WeibullAFTFitter`, `LogNormalAFTFitter`, `LogLogisticAFTFitter`.

## Machine learning

| Model | Library | Notes |
|-------|---------|-------|
| Random survival forest | `sksurv.ensemble.RandomSurvivalForest` | non-PH, interactions; min_samples_leaf 5-20 |
| Gradient-boosted Cox | `sksurv.ensemble.GradientBoostingSurvivalAnalysis` | strong on tabular data |
| XGBoost survival | `objective="survival:cox"` or `"survival:aft"` | scale; AFT needs interval labels |
| Penalised Cox (elastic net) | `sksurv.linear_model.CoxnetSurvivalAnalysis` | many covariates |
| Deep models | DeepSurv, DeepHit (pycox) | large data, unstructured inputs |

## Competing risks

When other events prevent the event of interest (a customer who downgrades can no longer churn from premium;
death from other causes), 1 - KM overestimates the cumulative incidence.

| Question | Method |
|----------|--------|
| Cumulative incidence of each event | Aalen-Johansen (`lifelines.AalenJohansenFitter`) |
| Effect on the cause-specific hazard (aetiology) | cause-specific Cox: treat other events as censored |
| Effect on the cumulative incidence (prediction) | Fine-Gray subdistribution hazard (R `cmprsk`, `scikit-survival` in recent versions) |

## Discrete time

With monthly data and many rows, expand to person-period rows (one row per subject per month at risk) and
fit a logistic regression or gradient boosting on "event this month". This handles time-varying covariates
naturally and scales well. Survival is the product of (1 - hazard) over months.

## Churn and lifetime value

- Expected lifetime from survival: `E[T] = integral of S(t) dt` (restricted to the horizon: RMST).
- Customer lifetime value = sum over periods of S(t) x margin(t) x discount(t).
- Parametric or discrete-time models are needed to extrapolate beyond the observed follow-up. State the
  assumption.
