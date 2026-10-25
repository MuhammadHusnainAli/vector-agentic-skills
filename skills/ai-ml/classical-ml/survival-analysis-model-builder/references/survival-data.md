# Survival Data

## Building the table

```sql
-- one row per customer: duration from signup to churn or to the data cut-off
SELECT customer_id,
       signup_date,
       COALESCE(churn_date, DATE '2026-09-30') AS end_date,
       DATE_DIFF(COALESCE(churn_date, DATE '2026-09-30'), signup_date, DAY) AS duration_days,
       CASE WHEN churn_date IS NOT NULL AND churn_date <= DATE '2026-09-30' THEN 1 ELSE 0 END AS event,
       plan_at_signup, channel_at_signup
FROM customers
WHERE signup_date < DATE '2026-09-30';
```
- Covariates must be known at the origin (here: signup). "Number of support calls" is not, because it
  grows with time and depends on survival. It needs time-varying handling.
- Durations of 0 (event on day 0) break some models. Use a small positive value (0.5 days) or start at day 1.

## Censoring types

| Type | Example | Handling |
|------|---------|----------|
| Right censoring (administrative) | still a customer at the cut-off | standard |
| Right censoring (loss to follow-up) | moved away, account merged | standard if non-informative |
| Interval censoring | failure found at an inspection between two visits | interval-censored methods (lifelines `fit_interval_censoring`) |
| Left truncation (delayed entry) | customers acquired before the data history starts | pass entry times (`entry=` in lifelines) |

## Informative censoring

Censoring is informative when its reason is related to the event. Examples:
- customers "censored" when they downgrade, who were about to churn
- patients withdrawn from a study because of side effects
- machines removed for preventive maintenance because they looked worn

Consequences: KM and Cox estimates are biased. Options: treat the censoring reason as a competing event,
redefine the event (any downgrade or churn), or use inverse probability of censoring weights.

## Checks before modelling

| Check | Why |
|-------|-----|
| durations >= 0, events in {0, 1} | data errors (the scripts refuse others) |
| events per covariate >= 10 | stable Cox estimates |
| follow-up distribution by group | groups observed for very different lengths compare badly |
| censoring share by group and over calendar time | informative or administrative patterns |
| event times piled at specific values (e.g. day 30, 365) | contract terms; consider discrete-time models |
| covariates measured after the origin | immortal-time bias, leakage |

## Long (counting-process) format

For time-varying covariates, use one row per subject per interval:

| id | start | stop | event | plan |
|----|-------|------|-------|------|
| C1 | 0 | 120 | 0 | basic |
| C1 | 120 | 300 | 1 | premium |

```python
from lifelines import CoxTimeVaryingFitter
CoxTimeVaryingFitter().fit(long_df, id_col="id", start_col="start", stop_col="stop", event_col="event")
```

## Immortal-time bias

Classifying subjects by something that happens later ("customers who used feature X") gives them guaranteed
event-free time before X. Model X as time-varying, or use a landmark analysis: fix a landmark time, classify
by status at the landmark, and analyse survival after it.
