# Latency, Backfills and Serving Parity

## Event time vs arrival time

| Data | Event time | Arrives | Usable at a 02:00 batch score |
|------|-----------|---------|------------------------------|
| App events (streamed) | t | t + seconds | up to 01:59 |
| Daily warehouse load | t | next day 06:00 | up to the day before yesterday |
| Support tickets (CRM export) | t | t + 24 h | up to yesterday 02:00 |
| Chargebacks | t | t + 30-120 days | only old transactions |

Model training must use the same availability as production. If the table has an `ingested_at` column,
filter on it (`ingested_at < anchor`); otherwise set `--latency` to the typical delay (or a conservative
upper bound).

## Late-arriving and corrected data

- Events can arrive late (offline devices, batch partners). Production at time a did not see them; training
  that includes them is optimistic. Prefer arrival-time filtering.
- Records can be corrected later (refunds amend amounts, status changes). Use an append-only event log, or
  snapshot feature values as computed at the time.

## Backfills

When adding a new feature, historical values must be computed as they would have been at each past anchor:
1. Use the event log with arrival times.
2. Recompute per anchor with the same code that runs in production (or the feature store's point-in-time
   join).
3. Validate: for recent dates where production already logged the feature, compare backfilled vs logged
   values. Differences reveal latency or logic mismatches.

## Online/offline parity

| Concern | Practice |
|---------|----------|
| Same definitions | one feature definition (SQL / feature store) for batch training and online serving |
| Same windows | online stream aggregations with the same window lengths and closedness |
| Same anchor | online: events up to "now" minus processing delay; offline: same latency |
| Missing history | online new entities get the same defaults (0 counts, NaN means) as offline |
| Logging | log the features actually served; train future models on logged values when possible |

## Streaming windows

Real-time velocity features are maintained by a stream processor (Flink, Kafka Streams, Spark Structured
Streaming) or an online feature store with sliding/hopping windows. Notes:
- Sliding windows of exact length are expensive; hopping windows (e.g. 24h window, 5-minute hop) approximate
  them. Train on the same approximation.
- Watermarks control late data: events later than the watermark are dropped online; drop them offline too.
- Exclude the current event explicitly when the feature is computed after it is ingested.
