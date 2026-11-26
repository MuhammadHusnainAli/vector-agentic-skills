# Endpoint Design Rules

## Resources and URIs

- Nouns for resources, plural collections: `/orders`, `/orders/{orderId}`, `/orders/{orderId}/items`.
- Nest at most one level for ownership; beyond that use top-level resources with filters (`/items?orderId=...`).
- Opaque, stable IDs (UUIDv7, ULID, or prefixed IDs like `ord_...`); never expose auto-increment IDs (enumeration,
  shard hot spots on sequential keys).
- Actions that don't fit CRUD: model as a resource (`POST /orders/{id}/cancellations`) or a clear verb sub-resource
  (`POST /orders/{id}:cancel`); pick one convention.

## Methods

| Method | Safe | Idempotent | Use |
|--------|------|------------|-----|
| GET | yes | yes | Read; cacheable |
| HEAD | yes | yes | Metadata, existence, ETag checks |
| POST | no | no (make it so with Idempotency-Key) | Create, actions, searches with large bodies |
| PUT | no | yes | Full replace at a known URI |
| PATCH | no | not by default (JSON Merge Patch is; use If-Match) | Partial update |
| DELETE | no | yes | Delete (repeat returns 204 or 404 consistently) |

## Request and response shapes

- JSON with consistent casing (camelCase or snake_case, never both); RFC 3339 timestamps in UTC; money as integer minor
  units plus currency code; enums as strings.
- Envelope only where needed (list responses: `data` + `nextCursor`); single resources unwrapped.
- Limits in the schema: `maxLength` on strings, `maxItems` on arrays, max page size, max body size (reject with 413).
- Sparse fieldsets (`?fields=id,status,total`) and controlled expansion (`?expand=customer`, depth 1) to cut payloads.
- Filtering with explicit, indexed fields (`?status=paid&createdAfter=...`); reject unknown filters (400) instead of
  ignoring them.
- Sorting only on indexed fields; default sort stable (by ID as tiebreaker).

## Bulk and batch

- Bulk create/update: `POST /orders:batchCreate` with up to N items (e.g. 100), per-item results (207-style body with
  status per item) and an Idempotency-Key for the batch.
- Batching reduces request overhead at scale, but caps keep latency and memory bounded.

## Long-running operations

```
POST /exports            -> 202 Accepted, Location: /operations/op_123
GET  /operations/op_123  -> {"status":"running","progress":0.4}
GET  /operations/op_123  -> {"status":"succeeded","result":{"url":"..."}}
```
Optionally notify by webhook. Never hold an HTTP request open for minutes.

## Conditional requests and caching

| Header | Use |
|--------|-----|
| `ETag` (strong or weak) | Version of the representation |
| `If-None-Match` on GET | 304 Not Modified saves bandwidth and serialisation |
| `If-Match` on PUT/PATCH/DELETE | Optimistic concurrency; 412 Precondition Failed on conflict |
| `Cache-Control: public, max-age=60, stale-while-revalidate=30` | Shared caches (CDN) for public data |
| `Cache-Control: private, max-age=0, must-revalidate` | Per-user data |
| `Vary` | Only on headers that change the representation (Accept-Encoding, Accept-Language); `Vary: Authorization` kills CDN hit rates |
| `Surrogate-Key` / cache tags | Targeted CDN purges on writes |

## Other headers

- `Idempotency-Key` on unsafe requests (see idempotency-key-designer).
- Rate-limit headers: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset` (IETF draft) or the common `X-RateLimit-*`; `Retry-After` on 429 and 503.
- `Content-Encoding: br` or `gzip` for responses over about 1 kB (CPU vs bandwidth trade-off; precompress static).
- Request IDs: accept and propagate `traceparent` (W3C Trace Context); return a request ID in errors.

## Review checklist

- [ ] Every list paginated with max page size; every string and array bounded
- [ ] Methods match semantics; unsafe operations accept Idempotency-Key
- [ ] Cache headers and ETags on reads; no `Vary: Authorization` on public data
- [ ] No per-item fan-out in handlers; bulk endpoints for clients that need them
- [ ] Long-running work is asynchronous
- [ ] Errors follow the error format; status codes correct
- [ ] Auth scopes per endpoint; rate limits defined
