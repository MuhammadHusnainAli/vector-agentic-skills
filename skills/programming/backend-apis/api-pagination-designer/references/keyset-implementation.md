# Keyset Implementation

## Cursor format

```json
{"v": 1, "k": ["2026-11-20T10:15:02.123Z", "ord_01JD3..."], "d": "next", "f": "a1b2c3"}
```
- `v` version (change the format safely), `k` last row's sort values, `d` direction, `f` hash of filters + sort.
- Encode base64url; optionally HMAC-sign (`payload.signature`) so clients can't craft cursors that bypass filters.
- Treat cursors as opaque in docs; never promise their contents.

## SQL (PostgreSQL; row-value comparison)

```sql
-- index
CREATE INDEX orders_tenant_created_id ON orders (tenant_id, created_at DESC, id DESC);

-- first page
SELECT id, created_at, status, total FROM orders
WHERE tenant_id = $1
ORDER BY created_at DESC, id DESC
LIMIT $2 + 1;                          -- fetch one extra to know if there's a next page

-- next page (after cursor values $3, $4)
SELECT id, created_at, status, total FROM orders
WHERE tenant_id = $1 AND (created_at, id) < ($3, $4)
ORDER BY created_at DESC, id DESC
LIMIT $2 + 1;

-- previous page: flip comparison and order, then reverse the result in the application
SELECT ... WHERE tenant_id = $1 AND (created_at, id) > ($3, $4)
ORDER BY created_at ASC, id ASC LIMIT $2 + 1;
```
MySQL supports row constructors too, but may not use the index well for them; expand to
`created_at < ? OR (created_at = ? AND id < ?)`. Check the plan with EXPLAIN.

Nullable sort columns: use `COALESCE` with a sentinel or `NULLS LAST` consistently in the index, the ORDER BY and the
comparison.

## Response shape

```json
{
  "data": [ ... ],
  "nextCursor": "eyJ2IjoxLCJrIjpb...",
  "prevCursor": "eyJ2IjoxLCJrIjpb...",
  "hasMore": true
}
```
Optional Link header (RFC 8288):
```
Link: <https://api.example.com/v1/orders?cursor=eyJ2...&limit=50>; rel="next"
```

## Errors

| Case | Response |
|------|----------|
| Malformed or tampered cursor | 400 `invalid_cursor` |
| Cursor from different filters or sort | 400 `cursor_mismatch` |
| Cursor format version retired | 400 `cursor_expired` (restart from the first page) |
| `limit` above max | 400 or clamp (document which) |

## GraphQL (Relay connections)

```graphql
type OrderConnection { edges: [OrderEdge!]!, pageInfo: PageInfo! }
type OrderEdge { node: Order!, cursor: String! }
type PageInfo { hasNextPage: Boolean!, hasPreviousPage: Boolean!, startCursor: String, endCursor: String }
type Query { orders(first: Int, after: String, last: Int, before: String): OrderConnection! }
```
Cap `first`/`last` (e.g. 100) in the resolver or with query-cost limits.

## Tests

- Insert rows newer and older than the cursor while paging: no duplicates, no skips.
- Delete the row the cursor points to: next page still works (cursor holds values, not a row reference).
- Equal sort values across a page boundary: tiebreaker keeps order stable.
- Every allowed sort uses an index (EXPLAIN in CI for the query templates).
