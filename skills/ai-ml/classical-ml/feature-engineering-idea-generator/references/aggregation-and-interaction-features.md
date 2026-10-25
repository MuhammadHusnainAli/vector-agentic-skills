# Aggregation and Interaction Features

## Two dataset shapes

1. **Event-level rows** (each transaction is scored): aggregates over the entity's *previous* events.
2. **Snapshot rows** (each customer scored at a date): aggregates over events before the snapshot date.

Both obey the same rule: no data from the prediction moment or later.

## Expanding (all prior history) per entity

```python
df = df.sort_values(["customer_id", "ts"])
g = df.groupby("customer_id")
df["n_prior"] = g.cumcount()
df["amount_mean_prior"] = g["amount"].transform(lambda s: s.shift().expanding().mean())
df["amount_max_prior"] = g["amount"].transform(lambda s: s.shift().expanding().max())
df["secs_since_prev"] = g["ts"].diff().dt.total_seconds()
```

## Time windows (last 1 h, 24 h, 7 d, 30 d)

```python
df = df.sort_values("ts").set_index("ts")
roll = df.groupby("card_id")["amount"].rolling("24h", closed="left")   # closed="left" excludes the current row
feat = pd.DataFrame({"n_24h": roll.count(), "sum_24h": roll.sum()}).reset_index()
df = df.reset_index().merge(feat, on=["card_id", "ts"], how="left")
df[["n_24h", "sum_24h"]] = df[["n_24h", "sum_24h"]].fillna(0)        # NaN = no prior events in the window
```
With duplicate timestamps per entity, aggregate on a unique key (transaction ID) instead of merging on time.
For large data, compute windows in SQL with `RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND CURRENT ROW`
minus the current row, or in polars `rolling` / `group_by_dynamic`.

## Snapshot aggregates (one row per entity per scoring date)

```python
def snapshot_features(events, entities, score_date, windows=(7, 30, 90)):
    past = events[events.ts < score_date]
    out = entities[["customer_id"]].copy()
    for w in windows:
        win = past[past.ts >= score_date - pd.Timedelta(days=w)]
        agg = win.groupby("customer_id").agg(**{f"n_{w}d": ("ts", "size"), f"spend_{w}d": ("amount", "sum")})
        out = out.merge(agg, on="customer_id", how="left")
    last = past.groupby("customer_id").ts.max()
    out["days_since_last"] = (score_date - out.customer_id.map(last)).dt.days
    return out.fillna({c: 0 for c in out.columns if c.startswith(("n_", "spend_"))})
```

## RFM and engagement

| Feature | Definition |
|---------|------------|
| Recency | days since last purchase / login |
| Frequency | events in the last 30 / 90 days |
| Monetary | spend in the last 30 / 90 days |
| Tenure | days since first event |
| Breadth | distinct products / categories / devices |
| Regularity | std of inter-event gaps; coefficient of variation |

## Trends and ratios to self

```python
df["spend_trend"] = df["spend_30d"] / (df["spend_prev_30d"] + 1)          # < 1 declining
df["logins_trend"] = df["logins_7d"] / (df["logins_30d"] / 4 + 1e-3)
df["amount_vs_own_mean"] = df["amount"] / (df["amount_mean_prior"] + 1e-3)
df["zscore_vs_own"] = (df["amount"] - df["amount_mean_prior"]) / (df["amount_std_prior"] + 1e-3)
```

## Group context

```python
med = train.groupby("neighborhood")["price_per_sqft"].median()
df["ppsf_vs_hood"] = df["price_per_sqft"] / df["neighborhood"].map(med)
```
Group statistics of the *target* are target encoding: fit out-of-fold.

## Velocity features (fraud, abuse)

| Feature | Example |
|---------|---------|
| Count in window | transactions per card in the last 10 min / 1 h / 24 h |
| Distinct in window | distinct merchants, countries, devices per card in 24 h |
| Sum in window | amount per card in 24 h vs its 30-day daily average |
| Shared entities | cards per device in 7 d; accounts per IP in 24 h |
| Impossible travel | distance between consecutive transactions / time between them |

## Interactions

| Model | Approach |
|-------|----------|
| Linear | explicit products (`plan_basic * support_calls`), `PolynomialFeatures(degree=2, interaction_only=True)` on a few features, splines (`SplineTransformer`) for non-linear effects |
| GBM | usually finds interactions; add explicit ratios/differences it cannot express easily |
| Any | concatenated categoricals (`plan + "_" + region`) when the combination has meaning |

Find candidate interactions with SHAP interaction values or by comparing a GBM with a linear model per
feature pair; keep only those that validate.

## Splines and binning

```python
from sklearn.preprocessing import SplineTransformer, KBinsDiscretizer
spline = SplineTransformer(n_knots=5, degree=3)              # smooth non-linear effect for linear models
bins = KBinsDiscretizer(n_bins=10, encode="onehot", strategy="quantile")
```
Fit both on training data only (inside the pipeline).

## Cost of aggregates in production

Real-time aggregates need a stream processor or an online feature store; batch aggregates are cheap. Decide
the freshness each feature needs (feature-store-schema-designer) before building it.
