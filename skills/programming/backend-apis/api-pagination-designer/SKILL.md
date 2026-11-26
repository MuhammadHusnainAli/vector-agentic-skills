---
name: api-pagination-designer
description: "Design list endpoints that stay fast and correct at any depth and traffic: cursor (keyset) pagination as the default with opaque, versioned, tamper-proof cursors, stable ordering with a unique tiebreaker, matching composite indexes and row-value SQL, page size defaults and caps, total counts (avoid, approximate or separate), bidirectional paging, consistency under inserts and deletes, filters bound to cursors, sync endpoints with updated_after watermarks, Link headers (RFC 8288) and GraphQL Relay connections, plus pagination over shards, search engines (search_after with point-in-time) and caches. Explains why OFFSET pagination collapses at depth and scale and when it is still acceptable. Use when designing or reviewing any list, search, feed or export endpoint."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# API Pagination Designer

Pagination decides whether a list endpoint costs the same on page 1 and page 10,000. `OFFSET 200000 LIMIT 50` makes the
database read and throw away 200,000 rows, and at high traffic a few deep-paging clients (often scrapers and sync jobs)
can saturate a primary. Offset paging also skips or repeats items when data changes between requests. Keyset (cursor)
pagination reads exactly one page through an index, every time. This skill designs pagination that stays correct and
constant-cost.

## Trigger Conditions

Activate this skill when the user:
- Designs any list, search, feed, timeline, audit log or export endpoint
- Has slow deep pages, duplicate or missing items while paging, or expensive total counts
- Builds sync APIs ("give me everything that changed since X")
- Paginates across shards, a search engine or a GraphQL schema

Endpoint and capacity design: `rest-api-endpoint-designer`. Spec snippets: `openapi-spec-writer`. GraphQL connections:
`graphql-schema-designer`.

## Choosing a Method

| Method | Cost per page | Consistency under writes | Jump to page N | Use for |
|--------|---------------|--------------------------|----------------|---------|
| Keyset / cursor | Constant (index seek) | Stable: no skips or duplicates | No | Default for APIs, feeds, sync, exports |
| Offset / page number | Grows with offset | Skips and duplicates | Yes | Small, bounded admin tables (cap offset, e.g. 10k rows) |
| Time/ID watermark (`updated_after`) | Constant | Stable with a tiebreaker | No | Incremental sync |
| Search-engine cursor (`search_after` + point-in-time) | Constant | Snapshot-consistent | No | Search results beyond the first pages |

## Rules

| Rule | Detail |
|------|--------|
| Deterministic order | Sort key + unique tiebreaker (`created_at DESC, id DESC`) |
| Index matches the order and filters | `(tenant_id, created_at DESC, id DESC)` for `WHERE tenant_id = ? ORDER BY created_at DESC, id DESC` |
| Opaque cursor | Base64url of a small JSON/binary payload: version, sort values, direction, filter hash; signed (HMAC) if tampering matters |
| Cursor bound to the query | Changing filters or sort with an old cursor returns 400 |
| Default and max page size | e.g. default 20, max 100; reject or clamp larger |
| No total count by default | `COUNT(*)` on big tables is a full scan; offer `has_more`, an approximate count, or a separate count endpoint |
| `nextCursor: null` ends the list | Don't make clients compare counts |

## Review Checklist

- [ ] Every list endpoint paginated; max page size enforced
- [ ] Order deterministic with a unique tiebreaker; index exists for each allowed sort
- [ ] Cursors opaque, versioned, tied to filters; expired/invalid cursor -> 400 with a clear code
- [ ] No unbounded `COUNT(*)`; offset (if offered) capped
- [ ] Sync endpoints use watermarks with a tiebreaker and a safety lag for in-flight transactions
- [ ] Sharded or search-backed lists use merge or engine cursors

## Output

Pagination design per endpoint: method, sort options, cursor format, SQL/query with the index, page size limits, response
shape (body and Link headers), error cases, and tests (inserts and deletes during paging).

## Additional Resources

| File | Content |
|------|---------|
| [keyset-implementation.md](references/keyset-implementation.md) | Cursor encoding, SQL for each direction, indexes, response shapes, Link headers, GraphQL connections, tests |
| [pagination-at-scale.md](references/pagination-at-scale.md) | Why offset fails, counts, sync watermarks, sharded merge, search engines, caching pages, exports |
