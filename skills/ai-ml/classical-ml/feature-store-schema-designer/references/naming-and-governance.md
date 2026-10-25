# Naming and Governance

## Naming conventions

| Element | Convention | Examples |
|---------|------------|----------|
| Entity | singular noun | `customer`, `card`, `store_sku` |
| Feature view | `<entity>_<topic>` | `customer_activity`, `card_velocity`, `store_sku_sales` |
| Feature | `<measure>_<window>` or `<measure>_<qualifier>` | `logins_30d`, `amount_sum_24h`, `days_since_last_login`, `plan` |
| Window suffix | `_<n><unit>` with m/h/d/w, or `_lifetime` | `_15m`, `_24h`, `_7d`, `_4w` |
| Counts | `n_` prefix or `_count` suffix, consistently | `n_txn_1h` |
| Distinct counts | `nuniq_<thing>_<window>` | `nuniq_merchant_7d` |
| Ratios | `<a>_per_<b>` or `<a>_vs_<b>` | `spend_per_login_30d`, `amount_vs_mean_24h` |
| Flags | `is_` / `has_` | `has_failed_payment_30d` |
| Units | explicit when ambiguous | `amount_usd`, `latency_ms` |
| Feature service | `<model>_v<n>` | `churn_model_v1` |

## Documentation per feature

- What it measures and the as-of rule ("in the 30 days before event_ts").
- Source table and transformation (link to code).
- Null semantics (no events -> 0 for counts, null for means).
- Owner and creation date; known caveats (changed definition on 2026-03-01).

## Ownership

- One owning team per feature view, on call for its freshness SLA.
- Consumers register through feature services, so owners know who breaks when a feature changes.

## PII and access

- Tag PII (`pii: true`); restrict views containing it; prefer derived, non-identifying features (hashed or
  aggregated) over raw identifiers.
- Do not put direct identifiers (email, phone, name) into model features at all; keep them in the entity
  key mapping service.
- Record lawful basis/purpose for sensitive features (regulated domains).

## Versioning and change management

| Change | Process |
|--------|---------|
| New feature | add to a view; existing services unaffected |
| Definition change | new feature name (`spend_30d_v2`) or new view; never silently change meaning |
| Removal | deprecate (tag + date), notify service owners, remove after consumers migrate |
| Model update | new feature service `model_v2`; keep v1 until the old model is retired |

## Review checklist

- [ ] Entities use stable business keys; composite keys where needed.
- [ ] Every source has an availability-correct timestamp and a created timestamp if rows are corrected.
- [ ] Views split by entity, source and cadence; < ~50 features each.
- [ ] TTL >= cadence + delay; freshness SLA for online views; monitoring in place.
- [ ] Names follow the conventions; every aggregate has a window.
- [ ] Every feature and view has a description and an owner.
- [ ] PII tagged and access-controlled; no labels in feature views.
- [ ] Feature services per model version.
- [ ] Historical retrieval asserts row counts; online/offline parity check scheduled.
