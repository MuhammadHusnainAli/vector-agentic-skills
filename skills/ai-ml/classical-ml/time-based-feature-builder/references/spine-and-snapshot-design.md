# Spines and Snapshots

The **spine** is the table of rows to score: entity + cutoff (+ label). Every feature is joined onto it.
Getting the spine right is most of the leakage battle.

## Snapshot spine (batch scoring)

```sql
-- one row per customer active on each Monday, with a 30-day label window
WITH dates AS (
  SELECT d::date AS score_date
  FROM generate_series('2024-01-01'::date, CURRENT_DATE - 30, INTERVAL '7 day') AS d
)
SELECT c.customer_id, d.score_date,
       (EXISTS (SELECT 1 FROM cancellations x
                WHERE x.customer_id = c.customer_id
                  AND x.cancel_date >  d.score_date
                  AND x.cancel_date <= d.score_date + 30))::int AS churned_30d
FROM dates d
JOIN customers c
  ON c.signup_date < d.score_date
 AND (c.end_date IS NULL OR c.end_date > d.score_date);
```

Rules:
- Eligibility at the cutoff: only entities you would actually score that day.
- Label windows must be fully observed (`score_date <= today − horizon`).
- Snapshot frequency equals scoring frequency (weekly scoring -> weekly snapshots).

## Event-level spine (real-time scoring)

Each event is a row; its cutoff is its own timestamp. Features come from the entity's earlier events only;
the event itself is excluded (`pit_features.py --event-level`, `gen_window_sql.py --event-level --id`).
Labels are attached per event (fraud flag for the transaction).

## Warm-up

A 90-day window is meaningless for a snapshot taken 10 days after the entity's first event, or 10 days after
your event log starts. Options:
- Start snapshots after the log start + longest window.
- Keep young entities but add `tenure_days`; counts will be naturally small.
- Separate models for new vs established entities when behaviour differs strongly.

## Snapshot frequency vs correlation

Weekly snapshots of the same customer are highly correlated:
- Cross-validate with `GroupKFold` / `StratifiedGroupKFold` on the entity, or by time.
- Long-lived entities contribute many rows; consider weighting by 1 / snapshots_per_entity if the population of
  interest is entities rather than entity-weeks.
- Sample snapshots (one random date per entity per month) to cut size without losing diversity.

## Negative sampling

For rare events (fraud, failures), keep all positive rows and sample negatives (e.g. 10%); record the
sampling rate and correct predicted probabilities: `p = p_s / (p_s + (1 − p_s) / rate)` where `rate` is the
negative sampling fraction. Evaluate on unsampled data.

## Label alignment checklist

- [ ] Outcome window starts strictly after the cutoff (plus any gap for action time).
- [ ] Outcome window fully observed for every training row.
- [ ] Features end at the anchor (cutoff − latency).
- [ ] Entities that already had the outcome before the cutoff are excluded.
- [ ] Same spine logic is used to build the scoring table in production.
