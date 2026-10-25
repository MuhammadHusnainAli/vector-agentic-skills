# Feature Store Concepts

## Offline vs online store

| | Offline store | Online store |
|-|---------------|--------------|
| Holds | full history (every timestamped value) | latest value per entity key |
| Backed by | warehouse / lake (BigQuery, Snowflake, Redshift, Parquet, Delta) | key-value store (Redis, DynamoDB, Bigtable, Cassandra, SQLite for dev) |
| Used for | training sets, batch scoring | real-time serving (< 10 ms lookups) |
| Read API | `get_historical_features(entity_df, features)` | `get_online_features(features, entity_rows)` |

## Point-in-time join

For a spine row (entity key k, timestamp t) and a feature view with TTL T, the offline store returns the
value v with the greatest source timestamp ts such that `ts <= t` and `ts >= t − T` (ties broken by the
created timestamp). The same rule, applied at "now", defines what the online store should hold.

Correctness depends on the source timestamp meaning "became available". If a nightly job writes aggregates
for day D at 06:00 on D+1 but stamps them `D 00:00`, training rows at D 12:00 see values production had not yet
computed. Stamp with the availability time, or shift the spine by the latency.

## Materialisation

`feast materialize-incremental $(date -u +%Y-%m-%dT%H:%M:%S)` copies the latest values in the window since the
last run into the online store. Schedule it at least as often as the source cadence; monitor lag (now − last
materialised timestamp) against the freshness SLA.

## Streaming and push sources

For features updated by streams (velocity counts), a stream processor computes aggregates and pushes them:
```python
from feast import PushSource
card_push = PushSource(name="card_velocity_push", batch_source=card_txn_batch_source)
# producer: fs.push("card_velocity_push", df_with_keys_and_ts, to=PushMode.ONLINE_AND_OFFLINE)
```
Pushing to both stores keeps history for training consistent with what was served.

## On-demand features

Values that depend on request data (the transaction being scored) cannot be precomputed:
```python
from feast import RequestSource, Field
from feast.on_demand_feature_view import on_demand_feature_view
from feast.types import Float64

txn_request = RequestSource(name="txn_request", schema=[Field(name="amount", dtype=Float64)])

@on_demand_feature_view(sources=[card_velocity_fv, txn_request],
                        schema=[Field(name="amount_vs_mean_24h", dtype=Float64)])
def amount_ratio(inputs):
    import pandas as pd
    out = pd.DataFrame()
    out["amount_vs_mean_24h"] = inputs["amount"] / (inputs["amount_sum_24h"] / inputs["n_txn_24h"].clip(lower=1))
    return out
```
The same Python runs at training (on historical requests) and serving time.

## Train/serve skew sources and fixes

| Source of skew | Fix |
|----------------|-----|
| Different code computes features offline and online | one definition (feature view / on-demand view) |
| Online values staler than training assumed | TTL and freshness SLA; train with latency-aware timestamps |
| Missing online values replaced differently | same defaults in both paths; log served features |
| Type differences (int vs float, string categories) | declared dtypes; validation at materialisation |
| Late corrections in the offline store | created timestamps; snapshot what was served |

## Parity check

Sample entities, read online features now and the offline point-in-time value at the same timestamp; the
differences should be zero up to the materialisation lag. Run it after every pipeline change.

## TTL semantics in practice

| TTL too short | TTL too long |
|---------------|--------------|
| online lookups return null between refreshes | stale values served silently after a pipeline outage |
| training rows get NaN although data existed | training uses values production would have considered expired |

Rule of thumb: `ttl = cadence + max expected delay`, e.g. daily job that can be 12 h late -> `ttl = 36h`; static
attributes -> long TTL; streaming -> minutes to hours.
