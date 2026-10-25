# Fraud Features

## Families

| Family | Examples |
|--------|----------|
| Velocity (entity x window) | count, amount sum and max per card / account / device / IP / email over 5m, 1h, 24h, 7d, 30d |
| Deviation from the entity's own history | amount / mean, z-score, hour-of-day vs the usual hours, new merchant category, new country |
| Ratios of short to long windows | cnt_1h / cnt_30d: sudden bursts relative to normal activity |
| Account / customer | account age, days since a password or email change, KYC level, number of linked cards |
| Device / session | new device, emulator / VPN flags, typing speed, time from login to payment |
| Merchant | MCC, merchant fraud rate (smoothed, lagged), card-not-present, high-risk category |
| Geography | distance from the last transaction / velocity of travel, country mismatch (card vs IP vs shipping) |
| Network / graph | number of cards per device, shared emails / addresses / phones, connected-component size, fraud labels in the neighbourhood (lagged) |
| Unsupervised scores | Isolation Forest, autoencoder reconstruction error, as features |

## Point-in-time rules

- Every aggregate uses events **strictly before** the current event. Include the current event only if the
  online system will also have it at decision time (for example, a counter incremented before scoring).
- Label-derived features ("merchant fraud rate") must use labels known at the event time. Lag them by the
  label delay.
- Simultaneous events (same timestamp) do not see each other: `fraud_velocity_features.py` processes
  timestamp batches.
- Offline features must equal online features. Test this by recomputing a sample of production-scored events
  offline and comparing.

## Computation

```python
# pandas, leak-free (identical to fraud_velocity_features.py)
df = df.sort_values("timestamp")
roll = (df.set_index("timestamp").groupby("card_id")["amount"]
          .rolling("24h", closed="left").agg(["count", "sum"]))
```
Online counters:
- per entity, sliding windows in Redis (sorted sets by timestamp) or a streaming engine (Flink, Kafka
  Streams), with an exactly-once update after scoring
- approximate counters (HyperLogLog for distinct counts, Count-Min sketches) for high-cardinality keys
- time-decayed counters (exponentially weighted) as a cheaper alternative to exact windows

## Encoding high-cardinality IDs

Merchant, device and IP ids: use target encoding with time-respecting out-of-fold estimates and smoothing,
or frequency / risk-tier encodings, or graph features instead of raw ids. Never one-hot millions of ids.

## Feature hygiene

- Monitor feature distributions weekly (PSI). Fraudsters move to where the model is blind.
- Remove features that only work through label leakage (e.g. "account closed" flags set after fraud is
  confirmed).
- Cap extreme values, and keep a missing-value indicator: missing device information is itself a signal.
