# Pagination at Scale

## Why OFFSET collapses

`OFFSET n LIMIT k` reads n + k rows and discards n. Page 1 reads 50 rows; page 4,000 reads 200,050. Under high traffic,
the deep pages from crawlers and sync jobs dominate database time. Results also shift when rows are inserted or deleted
between requests, causing skipped and repeated items.

If offset must exist (admin UI with page numbers):
- cap it (e.g. `offset <= 10000`), return 400 beyond;
- use the "deferred join" trick to make it cheaper: select IDs with offset on a covering index, then join for columns;
- move bulk consumers to an export or sync endpoint.

## Counts

| Need | Approach |
|------|----------|
| "Is there more?" | Fetch limit + 1 rows |
| Approximate size ("about 12,000 results") | Planner estimate (`pg_class.reltuples`, EXPLAIN rows), search engine `track_total_hits` cap, cached counters |
| Exact count rarely | Separate endpoint, cached, or computed asynchronously |
| Per-tenant counts | Maintained counters (incremented on write; sharded counters for hot tenants) |

## Sync endpoints (`changes since`)

```
GET /orders/changes?updatedAfter=2026-11-20T10:00:00Z&cursor=...
```
- Order by `(updated_at, id)`; cursor holds both.
- Watermark safety lag: don't return rows newer than `now() - lag` (e.g. 5 s) so in-flight transactions that commit with
  older timestamps aren't skipped. Or use a monotonic change sequence (logical replication LSN, outbox sequence).
- Include deletions as tombstones (soft delete with `deleted_at`, or a changes table).
- Clients store the last cursor and resume.

## Sharded data

- If the list is per tenant and tenants live on one shard: route and paginate normally.
- Cross-shard lists: query each shard for limit + 1 with the same keyset condition, merge by the sort key (k-way merge),
  return the top `limit`; the cursor holds the last sort values (which apply to every shard). Cost grows with shard count:
  prefer precomputed cross-shard read models (search index, materialised view) for hot cross-shard lists.

## Search engines

- Elasticsearch/OpenSearch: `search_after` with the last hit's sort values + a point-in-time (PIT) ID for consistency;
  `from + size` is limited (default max 10,000).
- Include a unique tiebreaker in the sort (`_shard_doc` with PIT, or an ID field).

## Caching pages

- First pages of public lists are good CDN/app-cache candidates (short TTL); deep pages rarely are.
- Cursor URLs are cacheable if the cursor is deterministic for the same position.

## Exports

For "give me everything": an asynchronous export job producing files (NDJSON/CSV/Parquet) to object storage, returned via
a long-running operation; don't make clients page through millions of rows on the hot API path.
