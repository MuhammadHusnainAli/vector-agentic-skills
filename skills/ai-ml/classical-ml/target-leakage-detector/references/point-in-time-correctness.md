# Point-in-Time Correctness

Every feature for a row with prediction time t must be computed from data **known** at t: event time <= t
and the data had arrived (processing time) by t.

## As-of joins in pandas

```python
import pandas as pd

snap = snapshots.sort_values("score_ts")          # one row per (customer_id, score_ts)
plan_hist = plan_changes.sort_values("valid_from")  # one row per change (customer_id, valid_from, plan)

out = pd.merge_asof(snap, plan_hist, left_on="score_ts", right_on="valid_from", by="customer_id",
                    direction="backward", allow_exact_matches=False)   # strictly before score_ts
```
`allow_exact_matches=False` excludes changes stamped exactly at the scoring time (often written by the same
process that produces the outcome).

## As-of joins in SQL (SCD type 2)

```sql
SELECT s.customer_id, s.score_date, p.plan
FROM snapshots s
JOIN plan_history p
  ON p.customer_id = s.customer_id
 AND p.valid_from <= s.score_date
 AND (p.valid_to IS NULL OR p.valid_to > s.score_date);
```

## Aggregates strictly before t

```sql
SELECT s.customer_id, s.score_date,
       COUNT(e.*)                                       AS events_30d,
       MAX(e.ts)                                        AS last_event_ts
FROM snapshots s
LEFT JOIN events e
  ON e.customer_id = s.customer_id
 AND e.ts <  s.score_date
 AND e.ts >= s.score_date - INTERVAL '30 days'
GROUP BY s.customer_id, s.score_date;
```

pandas for event-level rows:
```python
df = df.sort_values(["card_id", "ts"])
df["amount_mean_prior"] = df.groupby("card_id")["amount"].transform(lambda s: s.shift().expanding().mean())
```

## Event time vs processing time

| Term | Meaning |
|------|---------|
| Event time | when the thing happened (`txn_ts`) |
| Processing / ingestion time | when the record became available (`loaded_at`) |
| Prediction time | when the model scores |

A feature is available at prediction time only if `loaded_at <= prediction_time`. Batch pipelines that land
yesterday's data at 06:00 mean a 02:00 score sees data up to the day before yesterday. Train with the same
lag: filter on `loaded_at` when it exists, or shift windows by the typical latency.

## Label latency for target-derived features

Features built from past labels (customer's previous chargebacks, merchant fraud rate) may use only labels
**known** at t. A chargeback filed 60 days after a transaction is not known on day 10. Use the label's
`known_at` timestamp, not the event's timestamp.

## Snapshot tables

The most robust design: store daily/weekly snapshots of feature values as they were computed in production
(`feature_value, entity_id, as_of_ts`). Training then reads the same values the model would have seen.
Feature stores (Feast, Tecton, Databricks, SageMaker) implement point-in-time joins over such logs; see
feature-store-schema-designer.

## Checks

| Check | How |
|-------|-----|
| No future dates | for each datetime feature, share of rows where value > prediction time = 0 |
| Snapshot replay | recompute features for a past date from raw logs and compare with what production logged |
| Latency respected | `loaded_at <= prediction_time` for all joined rows |
| Label-derived features | built from labels with `known_at <= prediction_time` |
