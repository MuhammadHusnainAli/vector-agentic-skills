# Label Design and Windows

## The three windows

```
 history start                 cutoff = prediction time
      |--------- observation window ---------|-- gap --|------ outcome window ------|
      features use only this                  optional   the label is computed here
```

- **Observation window:** data the features may use. Often several sub-windows (last 7, 30, 90 days).
- **Gap (blackout):** time between prediction and the start of the outcome window. Use it when the action
  takes time (call scheduling, shipping) or when data arrives late (yesterday's events land today).
- **Outcome window:** where the label is measured. Its length is the horizon.

## Choosing the horizon

| Consideration | Pushes the horizon |
|---------------|-------------------|
| Time needed to act (schedule a call, ship stock) | longer: horizon > time to act + gap |
| Label delay you can tolerate before evaluating | shorter |
| Event frequency (enough positives per window) | longer for rare events |
| Business cycle (monthly billing, seasonal demand) | align to the cycle |
| Signal decay (features predict the near future better) | shorter |

Try two or three horizons and compare positives per window, offline metric and business usefulness. A 7-day
churn label may have 1% positives and high precision; a 90-day label 12% positives and weaker signal.

## Censoring

A row is right-censored when its outcome window has not fully elapsed. Treating it as negative biases the label
toward 0 for the most recent rows.

Options:
1. Drop scoring dates whose window has not ended (`score_date <= today - horizon`). Simple, loses fresh data.
2. Use survival analysis with `(duration, event)` labels.
3. For monitoring, compute a partial-window metric and compare like with like.

## Label delay and training freshness

Training data ends at `today - horizon - label_delay`. With a 90-day chargeback delay and a 30-day horizon, the
newest trainable row is four months old. Mitigations: a faster proxy label for monitoring (analyst labels in 2
days), weighting recent rows, or nowcasting the label.

## Multi-snapshot datasets

Scoring weekly means the training table should also be weekly snapshots: one row per entity per scoring date.

- Pros: matches deployment, multiplies positives, captures changing features.
- Cons: rows of one entity are correlated (group by entity in CV), long-lived entities dominate (weight by
  1 / snapshots per entity if needed), and churners appear as negatives in early snapshots, which is correct.

```python
import pandas as pd

def build_snapshots(customers, events, cancels, score_dates, horizon_days=30):
    """One row per (customer, score_date); features from events strictly before score_date."""
    rows = []
    for d in score_dates:
        active = customers[(customers.start_date <= d) & ((customers.end_date.isna()) | (customers.end_date > d))]
        past = events[events.ts < d]
        feats = (past[past.ts >= d - pd.Timedelta(days=90)]
                 .groupby("customer_id").agg(events_90d=("ts", "size"), last_event=("ts", "max")))
        snap = active[["customer_id"]].merge(feats, on="customer_id", how="left")
        snap["days_since_event"] = (d - snap.pop("last_event")).dt.days
        snap["score_date"] = d
        end = d + pd.Timedelta(days=horizon_days)
        churned = cancels[(cancels.cancel_date > d) & (cancels.cancel_date <= end)].customer_id
        snap["label"] = snap.customer_id.isin(churned).astype(int)
        rows.append(snap)
    return pd.concat(rows, ignore_index=True)
```

## Proxy labels

The thing you care about is often not observable (or too slow), so you train on a proxy:

| Goal | Proxy | Where they disagree |
|------|-------|---------------------|
| Customer value | clicks | clickbait gets clicks, not value |
| Fraud | chargebacks | friendly fraud; fraud on declined transactions never charges back |
| Good hire | interview score | interviewer bias |
| Patient health | billing codes | coding practice varies by hospital |
| Satisfaction | survey response | non-response bias |
| Defect | customer complaint | silent failures |

For each proxy write down: when it diverges from the goal, how big the gap is, and which guardrail metric
catches the divergence.

## Label noise

Human labels, delayed labels and heuristics are noisy. Estimate noise with a double-labelled sample (agreement
rate, Cohen's kappa). Noise above ~10% caps achievable accuracy; prefer models and losses robust to it, and
clean the most-confident disagreements first.

## Label SQL patterns

**Event within a window after a snapshot**
```sql
CASE WHEN EXISTS (
  SELECT 1 FROM events e
  WHERE e.entity_id = s.entity_id AND e.type = 'cancel'
    AND e.ts > s.score_ts AND e.ts <= s.score_ts + INTERVAL '30 days'
) THEN 1 ELSE 0 END AS label
```

**Quantity over a forward window**
```sql
COALESCE((SELECT SUM(o.amount) FROM orders o
          WHERE o.customer_id = s.customer_id
            AND o.ts > s.score_ts AND o.ts <= s.score_ts + INTERVAL '90 days'), 0) AS spend_next_90d
```

**Survival label**
```sql
LEAST(COALESCE(c.cancel_date, CURRENT_DATE), CURRENT_DATE) - s.start_date AS duration_days,
CASE WHEN c.cancel_date IS NOT NULL THEN 1 ELSE 0 END                      AS event
```

**Eligibility filter** (always): active at the snapshot, not already labelled positive, in the population you
will score in production.
