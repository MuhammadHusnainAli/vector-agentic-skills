# GraphQL at Scale

One GraphQL request can ask for millions of objects. Protection must be built into the schema and the server, not bolted
on after an incident.

## Limits

| Control | Typical setting | Notes |
|---------|-----------------|-------|
| Max depth | 8-12 | Stops deeply nested cycles (`user.friends.friends.friends...`) |
| Max page size | 100 per connection | Enforced in resolvers |
| Query cost | Static analysis before execution: cost = sum over fields of (multiplier from `first`) x field cost; reject above a budget (e.g. 1,000-10,000 points) | Shopify and GitHub publish cost models |
| Node limit | Max total nodes returned (e.g. 50,000) | GitHub-style |
| Execution timeout | 1-10 s | Cancel resolvers with the request context |
| Aliases / batched operations | Cap aliases (e.g. 30) and operations per request | Prevents alias amplification |
| Introspection | Disabled or restricted in production for private graphs | Public graphs often keep it |

## Persisted / trusted documents

- Clients register queries at build time; requests send a hash (`extensions.persistedQuery.sha256Hash`) or an ID.
- First-party apps: allow only registered documents (trusted documents); third parties: cost limits apply.
- Benefits: smaller requests, no parse/validate cost per request, queries known in advance (cost precomputed), and
  **CDN caching**: persisted queries over `GET` with cache headers.

## Caching

- HTTP/CDN: GET persisted queries for public data with `Cache-Control` derived from the lowest max-age of fields
  (`@cacheControl` hints in Apollo).
- Server-side: per-request DataLoader cache; entity caches in Redis keyed by type + ID; response caching for anonymous
  queries.
- Client: normalised caches rely on `id` + `__typename`.

## Rate limiting by cost

Rate limit points per client per minute (cost of each query), not request counts. Return remaining budget in
`extensions` and headers. Over-budget -> HTTP 429 with `Retry-After`.

## Resolver performance

- Batch with DataLoader per request (see graphql-dataloader-n-plus-one-fixer).
- Look-ahead: inspect the selection set to fetch only requested columns or join when a child field is requested.
- Avoid per-field remote calls for lists; push work to batch endpoints.

## Federation and boundaries

- Split by domain ownership (subgraphs per team) with entity keys (`@key(fields: "id")`).
- The router plans queries across subgraphs; keep cross-subgraph hops shallow on hot paths.
- Schema checks against client usage before deploys; composition in CI.

## Observability

- Metrics per operation name (require operation names), per field resolver latency (sampled), errors by code.
- Trace each request with resolver spans; watch p99 per operation.
- Log query hashes, not full queries with variables (privacy).
