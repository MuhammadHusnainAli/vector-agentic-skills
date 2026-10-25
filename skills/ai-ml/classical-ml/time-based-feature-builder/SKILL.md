---
name: time-based-feature-builder
description: "Build leakage-safe time-based features from event logs: point-in-time window aggregates (counts, sums, means, max, distinct counts over 1h/24h/7d/30d) strictly before each cutoff, recency (time since last event), frequency and monetary (RFM), velocity and burst ratios, trends (short vs long window), expanding per-entity statistics, lags and rolling statistics for forecasting, EWMA, time-since-milestone, calendar and holiday features, and data-latency offsets. Supports snapshot spines (one row per entity per scoring date) and event-level scoring (each event scored on its own history), and generates matching SQL for PostgreSQL, DuckDB, BigQuery and Snowflake. Use when someone needs rolling-window or as-of features, RFM or velocity features, features for churn, fraud or demand models from transaction/event tables, or asks how to avoid look-ahead bias in time features."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Time-Based Feature Builder

Time features answer "what did this entity do recently, compared with before?", the strongest signal in most
churn, fraud, credit and demand models. They are also the easiest place to leak the future. Every feature is
computed for a row's **anchor** (its prediction time minus data latency) from events **strictly before**
that anchor. `scripts/pit_features.py` computes window features from a CSV event log for a snapshot spine or
for every event; `scripts/gen_window_sql.py` emits the same features as SQL for PostgreSQL, DuckDB, BigQuery
or Snowflake. On the fixtures the two agree row for row (verified in DuckDB) and match pandas
`rolling(..., closed="left")`.

## Trigger Conditions

Activate this skill when the user:
- Needs rolling-window, as-of or "last N days" features from transactions, logins, clicks, sensor readings
  or orders
- Builds RFM (recency, frequency, monetary), velocity (fraud), engagement trend (churn) or lag features
  (forecasting)
- Asks how to compute features "as of" a scoring date, or per event without using that event or later ones
- Has a model that looks great offline and suspects look-ahead bias in time features
- Needs the SQL for windowed features in a warehouse

Choosing which features to build: [feature-engineering-idea-generator](../feature-engineering-idea-generator/SKILL.md);
checking the result for leakage: [target-leakage-detector](../target-leakage-detector/SKILL.md); serving the
same features online: [feature-store-schema-designer](../feature-store-schema-designer/SKILL.md); forecasting
models themselves: [time-series-forecasting-model-builder](../time-series-forecasting-model-builder/SKILL.md).

## Workflow

```
1. SPINE     -> rows to score: (entity, cutoff) snapshots, or each event (event-level)
2. LATENCY   -> how stale is the data at scoring time? anchor = cutoff - latency
3. WINDOWS   -> pick 3-4 windows on a log scale matching the decision cadence (1h/24h/7d, 7d/30d/90d)
4. COMPUTE   -> python scripts/pit_features.py --events ev.csv --entity id --time ts --value amount \
                  --spine spine.csv --cutoff-col score_date --windows 7d 30d 90d --latency 6h -o f.csv
5. SQL       -> python scripts/gen_window_sql.py --dialect bigquery ... (same semantics in the warehouse)
6. DERIVE    -> ratios (short/long), deltas, per-unit rates, days since milestones
7. VERIFY    -> no feature uses data at/after the anchor; replay one entity by hand; leakage scan
```

## Feature Families

| Family | Examples | Typical use |
|--------|----------|-------------|
| Recency | seconds/days since last event, since last purchase, since last support ticket | churn, reactivation |
| Frequency | events in 1h / 24h / 7d / 30d, active days in 30d | engagement, fraud velocity |
| Monetary | sum / mean / max amount per window | CLV, fraud, credit |
| Velocity / burst | count in 1h vs mean hourly count over 7d; ratio of short to long mean | fraud, bot detection |
| Trend | spend 30d / spend previous 30d; slope of weekly counts | churn (declining engagement) |
| Diversity | distinct merchants / devices / countries / products per window | fraud, cross-sell |
| Expanding | all-time count, mean and max before the anchor; tenure | normalisation for new vs old entities |
| Relative to self | amount / entity mean over 30d; z-score vs own history | anomaly, fraud |
| Lags (series) | y[t-7], y[t-14], y[t-28], y[t-364]; rolling means shifted by the horizon | forecasting |
| Smoothed | exponentially weighted mean (half-life 7d) | stable recency-weighted levels |
| Milestones | days since signup, since plan change, until contract end | churn, renewals |
| Calendar | day of week, hour, month, holiday, payday, days to holiday | demand, traffic |

Definitions, formulas and code (pandas, polars, SQL) for each: [window-feature-catalog.md](references/window-feature-catalog.md).

## The Point-in-Time Rule

```
            [ window 7d ............................. )
   ---------|-----------------------------------------|----------|------> time
         anchor - 7d                               anchor      cutoff
                                                     ^  latency  ^
   events counted: anchor - 7d <= t_event < anchor          prediction made here
```

- **Strictly before:** `t_event < anchor`, never `<=`. An event stamped at the cutoff is usually part of the
  outcome (the transaction being scored, the cancellation itself).
- **Event-level scoring excludes the current event** (`--event-level`): the transaction being scored cannot
  appear in its own velocity count.
- **Latency:** if events land in the warehouse with a delay, training must use the same delay
  (`--latency 6h`), or the model learns from data production will not have yet.
- **Windows anchored at the anchor**, recency measured to the anchor: both scripts use the same convention.

## Spine Design

| Scoring pattern | Spine | Notes |
|-----------------|-------|-------|
| Weekly batch churn | one row per active customer per Monday | eligibility filter at each date; group CV by customer |
| Real-time fraud | one row per transaction (`--event-level`) | features from the card's earlier transactions only |
| Monthly credit review | one row per account per month-end | label window starts after the snapshot |
| Daily demand | one row per store-SKU per day | lags must respect the forecast horizon |

Spine construction, sampling of negatives and snapshot frequency: [spine-and-snapshot-design.md](references/spine-and-snapshot-design.md).

## Choosing Windows

- Match the decision cadence: real-time fraud needs minutes/hours; monthly churn needs weeks/months.
- Use 3-4 windows spaced roughly x4-x8 apart (1h, 6h, 24h, 7d or 7d, 30d, 90d, 365d).
- Always pair a short and a long window so the model can see change (`ratio_<value>_<short>_<long>`).
- Longer windows need longer history before the first usable snapshot (warm-up period): drop or flag
  snapshots whose history is shorter than the longest window.
- Count-type features should be 0, not missing, when no events fall in the window; means/max are missing
  (the model or an indicator handles it).

## Forecasting Lags

For a forecast made at day t for day t + h, a lag k is only available if k >= h (direct strategy):
- Horizon 7 days: y[t-7], y[t-14], y[t-28] are valid; y[t-1] is not (unknown at forecast time for t+7).
- Rolling statistics must be shifted by h before rolling.
```python
h = 7
g = df.groupby("series_id")["y"]
df["lag_7"] = g.shift(h)
df["rmean_28"] = g.transform(lambda s: s.shift(h).rolling(28, min_periods=7).mean())
```

## Output Format

When building time features, deliver:
1. **Spine definition** - rows, cutoff semantics, eligibility, latency.
2. **Feature list** - name, definition (window, aggregation, filter), anchor convention, missing/zero
   behaviour.
3. **Code** - `pit_features.py` command or pandas/polars code, and the warehouse SQL from `gen_window_sql.py`.
4. **Verification** - a hand-checked entity, the leakage scan, and the warm-up rule.
5. **Serving note** - how the same features are computed online (stream, feature store) with the same windows.

## Scripts

```bash
python scripts/pit_features.py --events txns.csv --entity card_id --time timestamp --value amount \
    --event-level --windows 1h 24h 7d --distinct merchant_category country -o feats.csv
python scripts/pit_features.py --events events.csv --entity customer_id --time ts --value amount \
    --spine snapshots.csv --cutoff-col score_date --windows 7d 30d 90d --latency 6h
```
Pure Python (bisect per entity). Per window: n, sum, mean, max of `--value`, distinct counts of `--distinct`
columns; plus n_prior, secs_since_last and the short/long mean ratio. Event-level mode excludes the current
event; spine mode keeps the spine's columns. Times: ISO dates/datetimes (with Z or offsets) or unix seconds/ms.
Exit codes: 0 written, 2 usage or read error.

```bash
python scripts/gen_window_sql.py --dialect postgres --events payments.txns --entity card_id --time txn_ts \
    --value amount --windows 1h 24h 7d --distinct merchant_id --event-level --id txn_id
python scripts/gen_window_sql.py --dialect bigquery --events '`p.d.events`' --entity customer_id \
    --time event_ts --spine '`p.d.snapshots`' --cutoff score_ts --value revenue --windows 7d 30d 90d --latency 6h
```
Dialects: postgres, duckdb, bigquery, snowflake. One LEFT JOIN of spine to events bounded by the longest
window, conditional aggregates per window, strict `<` on the anchor, current event excluded by id in
event-level mode, days since the last event. Exit codes: 0 printed, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [window-feature-catalog.md](references/window-feature-catalog.md) | Every feature family with formulas and pandas / polars / SQL code: RFM, velocity, trend, diversity, EWMA, self-relative, lags, calendar |
| [spine-and-snapshot-design.md](references/spine-and-snapshot-design.md) | Building spines, eligibility, snapshot frequency, warm-up, negative sampling, group-aware CV |
| [latency-backfill-and-serving.md](references/latency-backfill-and-serving.md) | Event vs processing time, late-arriving data, backfills, online/offline parity, streaming windows |
| [performance-at-scale.md](references/performance-at-scale.md) | Making window features fast: polars, DuckDB, Spark, pre-aggregated daily tables, incremental computation |
