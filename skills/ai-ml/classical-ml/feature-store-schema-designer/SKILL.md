---
name: feature-store-schema-designer
description: "Design feature store schemas that serve the same features to training and production: entities and join keys, sources with event and created timestamps, feature views grouped by entity and refresh cadence, dtypes, TTLs matched to source cadence, online vs offline stores, freshness SLAs, point-in-time correct historical retrieval, materialisation, feature services per model version, naming conventions with window suffixes, ownership, PII tagging and governance. Lints a JSON/YAML feature spec for 12 design errors and generates a working Feast repository (Entity, FileSource/BigQuerySource/SnowflakeSource/RedshiftSource, FeatureView, FeatureService, feature_store.yaml) verified with feast apply and get_historical_features; maps the design to Tecton, Databricks, SageMaker, Vertex AI and Hopsworks. Use when someone designs or reviews a feature store, asks how to structure feature views, set TTLs, avoid train/serve skew, or turn feature tables into Feast definitions."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Feature Store Schema Designer

A feature store exists to make two things true: training rows get feature values **as they were at each
row's timestamp** (point-in-time correctness), and production gets **the same definitions** with bounded
staleness (no train/serve skew). The schema decides whether that works: entities and join keys, sources
with reliable timestamps, feature views split by entity and refresh cadence, TTLs that match the cadence,
and feature services that pin what each model version reads. `scripts/lint_feature_spec.py` checks a design
spec for 12 common errors; `scripts/gen_feast_repo.py` turns the spec into a Feast repository (verified with
`feast apply` and a historical retrieval on Feast 0.67).

## Trigger Conditions

Activate this skill when the user:
- Designs a feature store or migrates feature tables into Feast, Tecton, Databricks, SageMaker, Vertex AI or
  Hopsworks
- Asks how to structure entities, feature views, TTLs, online/offline stores or feature services
- Has train/serve skew, stale online features, or missing values from historical retrieval
- Needs naming conventions, ownership, documentation or PII governance for shared features
- Wants a spec reviewed before features are built

Window logic for the features themselves: [time-based-feature-builder](../time-based-feature-builder/SKILL.md);
point-in-time pitfalls: [target-leakage-detector](../target-leakage-detector/SKILL.md).

## Workflow

```
1. ENTITIES   -> business keys (customer_id, card_id, store_id+sku_id); one entity per key set
2. SOURCES    -> tables with event timestamp (+ created timestamp for corrections) and refresh cadence
3. VIEWS      -> group features by entity x source x cadence; dtypes; descriptions; owners
4. TTL/SLA    -> ttl >= source cadence (+ slack); freshness_sla for online views
5. SERVICES   -> one feature service per model version (pins the feature list)
6. LINT       -> python scripts/lint_feature_spec.py spec.json
7. GENERATE   -> python scripts/gen_feast_repo.py spec.json --out feature_repo/ ; feast apply
8. VERIFY     -> historical retrieval row count == spine rows; online vs offline parity check
```

## Core Concepts

| Concept | Meaning | Design rule |
|---------|---------|-------------|
| Entity | the thing features describe, with join keys | stable business keys; composite keys for pairs (store, sku) |
| Source | table/stream with an event timestamp | timestamp = when the value became true; created timestamp = when written (dedupes corrections) |
| Feature view | features from one source for one entity set | split by cadence: real-time, hourly, daily, static |
| TTL | how far back a value may be used for a lookup | >= source cadence plus delays; too short -> empty lookups; too long -> stale values |
| Offline store | full history for training (warehouse, files) | point-in-time join: latest value with timestamp <= row time and >= row time - ttl |
| Online store | latest value per entity for serving (Redis, DynamoDB, SQLite) | filled by materialisation or streaming push |
| Materialisation | copying latest offline values to the online store | schedule at least as often as the source cadence |
| Feature service | named, versioned list of features a model uses | one per model version; never edit, create v2 |
| On-demand features | computed at request time from request data + stored features | for values only known at request time (amount vs card mean) |

## Feature View Design

| Group by | Because |
|----------|---------|
| Entity (join keys) | a lookup joins on one key set |
| Source | one view reads one table/stream |
| Refresh cadence | a daily view and a streaming view need different TTLs and pipelines |
| Ownership | one owning team per view |

Good split for churn:

| View | Entity | Source | Cadence | TTL | Online |
|------|--------|--------|---------|-----|--------|
| `customer_activity` | customer | nightly aggregates | daily | 2d | yes |
| `customer_profile` | customer | CDC of the accounts table | daily | 400d | yes |
| `customer_realtime` | customer | event stream (push) | streaming | 1h | yes |
| `plan_catalog` | plan | price list | weekly | 30d | yes |

## TTL and Freshness

- **TTL >= cadence + delay.** A daily view with `ttl=12h` returns empty online lookups for half the day
  (FS006).
- **TTL bounds staleness:** with `ttl=2d`, a training row never receives a value older than 2 days, the same
  rule as serving. Static attributes get long TTLs (hundreds of days).
- **Freshness SLA** (FS007) is the operational promise ("updated by 06:00 daily"); monitor it and alert.
- Historical retrieval returns NaN (or, in some offline stores, drops the row) when no value falls inside the
  TTL: **assert `len(result) == len(spine)`** after every `get_historical_features`. On Feast 0.67's file
  offline store, combining views where one view's TTL had expired for a spine row dropped that row entirely.

## Point-in-Time Retrieval

```python
from feast import FeatureStore
fs = FeatureStore(repo_path="feature_repo")
spine = labels[["customer_id", "score_ts"]].rename(columns={"score_ts": "event_timestamp"})
train = fs.get_historical_features(entity_df=spine, features=fs.get_feature_service("churn_model_v1")).to_df()
assert len(train) == len(spine), "rows dropped by the point-in-time join (check TTLs and entity coverage)"
```
For each spine row the store picks, per view, the latest value with `timestamp <= event_timestamp` and within
the TTL. That is only correct if the source's timestamp is the time the value became available; a nightly job
stamping yesterday's aggregates with yesterday's date while they land at 06:00 today needs the timestamp set
to the load time (or a latency-aware spine).

## Naming and Governance

| Rule | Example |
|------|---------|
| snake_case, entity implied by the view | `logins_30d`, not `CustomerLogins30` |
| window suffix on every aggregate | `spend_7d`, `n_txn_1h`, `orders_lifetime` |
| units in the name when ambiguous | `amount_usd`, `duration_s` |
| description says the as-of rule | "Spend in the 30 days before event_ts" |
| owner per view; PII flagged | `pii: true` for email, phone, address, IP (FS010) |
| no labels in feature views | `churned`, `is_fraud` belong to the training spine (FS012) |

Full conventions and the review checklist: [naming-and-governance.md](references/naming-and-governance.md).

## Output Format

When designing a feature store schema, deliver:
1. **Entity and source table** - keys, timestamps, cadence, owners.
2. **Feature views** - grouping rationale, TTL, online flag, freshness SLA, features with dtypes and
   descriptions.
3. **Feature services** - one per model version.
4. **Spec + lint** - the JSON/YAML spec and `lint_feature_spec.py` output with errors fixed.
5. **Code** - generated `features.py` and `feature_store.yaml` (or the platform equivalent).
6. **Verification plan** - retrieval row-count assertion, online/offline parity check, freshness monitoring.

## Scripts

```bash
python scripts/lint_feature_spec.py spec.json
python scripts/lint_feature_spec.py spec.yaml --json          # YAML needs PyYAML
```
FS001-FS005 errors (entity without join keys or unknown entity/source references, source without
timestamp_field, duplicate names, missing or unsupported dtype, feature service referencing unknown
views/features); FS006-FS010 and FS012 warnings (TTL missing or shorter than source cadence, online view
without a freshness SLA or with an SLA looser than its TTL, non-snake_case names or aggregates without a window
suffix, missing descriptions/owners, likely PII without `pii: true`, label-like features); FS011 info (views with
more than 50 features). Exit codes: 0 no errors, 1 errors, 2 read error.

```bash
python scripts/gen_feast_repo.py --template > spec.json      # churn example: 1 entity, 2 sources, 2 views, 1 service
python scripts/gen_feast_repo.py spec.json --out feature_repo/
python scripts/gen_feast_repo.py spec.json --stdout
```
Writes `features.py` (Entity, FileSource / BigQuerySource / SnowflakeSource / RedshiftSource, FeatureView with
typed `Field`s, ttl, online flag, tags for owner and SLA, FeatureService with `view[[...]]` projections) and a
local `feature_store.yaml` (SQLite online store, file offline store). Imports `lint_feature_spec.py` from the
same folder and refuses specs with lint errors unless `--force`. Exit codes: 0 generated, 1 lint errors, 2 usage
or read error.

## Additional Resources

| File | Content |
|------|---------|
| [spec-format.md](references/spec-format.md) | Every field of the JSON/YAML spec, supported dtypes and source types, a YAML example |
| [feature-store-concepts.md](references/feature-store-concepts.md) | Online/offline stores, materialisation, streaming push, on-demand features, point-in-time joins, TTL semantics, skew |
| [naming-and-governance.md](references/naming-and-governance.md) | Naming conventions, documentation, ownership, PII and access control, versioning, deprecation, review checklist |
| [platform-mapping.md](references/platform-mapping.md) | The same design in Feast, Tecton, Databricks Feature Engineering, SageMaker Feature Store, Vertex AI Feature Store, Hopsworks |
