# Feature Spec Format

Read by `lint_feature_spec.py` and `gen_feast_repo.py`. JSON always works; YAML needs PyYAML.

## Top level

| Key | Type | Notes |
|-----|------|-------|
| `project` | string | Feast project name (snake_case) |
| `entities` | list | see below |
| `sources` | list | see below |
| `feature_views` | list | see below |
| `feature_services` | list | optional |

## Entity

| Key | Required | Example |
|-----|----------|---------|
| `name` | yes | `customer` |
| `join_keys` | yes | `["customer_id"]`, or `["store_id", "sku_id"]` |
| `description` | recommended | `"A subscriber account"` |

## Source

| Key | Required | Example |
|-----|----------|---------|
| `name` | yes | `customer_daily_activity` |
| `type` | no (default `file`) | `file`, `bigquery`, `snowflake`, `redshift` |
| `path` | for file | `data/customer_daily_activity.parquet` |
| `table` | for warehouses | `proj.dataset.table` (BigQuery), `DB.SCHEMA.TABLE` (Snowflake), `schema.table` (Redshift) |
| `timestamp_field` | yes | `event_ts`: when the value became valid/available |
| `created_timestamp_field` | no | `created_ts`: when the row was written; used to pick the latest correction |
| `cadence` | recommended | `streaming`, `minutely`, `hourly`, `daily`, `weekly`, `monthly` (drives the TTL check) |

## Feature view

| Key | Required | Example |
|-----|----------|---------|
| `name` | yes | `customer_activity` |
| `entities` | yes | `["customer"]` |
| `source` | yes | a source name |
| `ttl` | recommended | `"2d"`, `"6h"`, `"400d"` (s, m, h, d, w) |
| `online` | no (default true) | `true` |
| `freshness_sla` | for online views | `"1d"` |
| `owner` | recommended | team email |
| `description` | recommended | |
| `features` | yes | list of features |

## Feature

| Key | Required | Example |
|-----|----------|---------|
| `name` | yes | `logins_30d` |
| `dtype` | yes | `int32`, `int64`, `float32`, `float64`, `string`, `bool`, `bytes`, `unix_timestamp`, `array<int64>`, `array<float32>`, `array<float64>`, `array<string>` |
| `description` | recommended | "Logins in the 30 days before event_ts" |
| `window` | optional | `"30d"` (alternative to a window suffix) |
| `pii` | when applicable | `true` |

## Feature service

| Key | Required | Example |
|-----|----------|---------|
| `name` | yes | `churn_model_v1` |
| `features` | yes | `["customer_activity:*", "customer_profile:plan"]` (`view:*` = whole view) |
| `description` | recommended | |

## YAML example

```yaml
project: fraud_features
entities:
  - name: card
    join_keys: [card_id]
    description: A payment card
sources:
  - name: card_txn_aggregates
    type: bigquery
    table: payments.features.card_txn_aggregates
    timestamp_field: window_end_ts
    created_timestamp_field: computed_ts
    cadence: hourly
feature_views:
  - name: card_velocity
    entities: [card]
    source: card_txn_aggregates
    ttl: 3h
    online: true
    freshness_sla: 1h
    owner: fraud-ds@example.com
    description: Hourly velocity aggregates per card
    features:
      - {name: n_txn_24h, dtype: int64, description: Transactions in the 24 h before window_end_ts}
      - {name: amount_sum_24h, dtype: float64, description: Amount in the 24 h before window_end_ts}
      - {name: nuniq_merchant_7d, dtype: int64, description: Distinct merchants in 7 days}
feature_services:
  - name: fraud_model_v3
    features: ["card_velocity:*"]
```
