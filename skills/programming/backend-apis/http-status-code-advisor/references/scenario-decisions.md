# Scenario Decisions

| Scenario | Code | Notes |
|----------|------|-------|
| POST creates a resource | 201 + Location | Body: the resource |
| POST with an Idempotency-Key that was already processed | Same code and body as the original | Add a header like `Idempotent-Replayed: true` |
| Same Idempotency-Key, different body | 422 or 409 | Code `idempotency_key_mismatch` |
| Same Idempotency-Key while the first is still processing | 409 | Retry-After optional |
| POST starts a long job | 202 + Location to the operation | Operation returns 200 with status; 303 to the result when done (optional) |
| PUT creates at a client-chosen URI | 201 | 200/204 when replacing |
| DELETE succeeded | 204 | Repeated DELETE: 204 or 404, pick one and document |
| GET collection with no items | 200 with empty `data` | Never 404 for an empty list |
| GET item that doesn't exist | 404 | |
| GET item in another tenant | 404 | Don't reveal existence |
| Field fails validation (format, range) | 400 or 422 | Pick one convention; include field pointers |
| Business rule violation (insufficient funds, invalid state transition) | 409 or 422 | 409 when about current resource state; 422 when about the request content |
| Optimistic concurrency failure (ETag mismatch) | 412 | Client re-fetches and retries |
| Update without If-Match on a resource that requires it | 428 | |
| Expired or invalid token | 401 + `WWW-Authenticate: Bearer error="invalid_token"` | |
| Token valid, scope missing | 403 + `WWW-Authenticate: Bearer error="insufficient_scope", scope="orders:write"` | |
| Account suspended | 403 | Code `account_suspended` |
| Per-client rate limit hit | 429 + Retry-After + RateLimit headers | |
| Global overload, load shedding | 503 + Retry-After | Not 429: the client did nothing wrong |
| Payload too large | 413 | Body says the limit |
| Dependency timed out | 504 | Or 503 if you short-circuit via circuit breaker |
| Dependency returned an error you can't handle | 502 | Don't forward the upstream's 4xx as yours unless meaningful |
| Batch where some items fail | 200 (or 207) with per-item status | Overall 4xx only if the whole batch is invalid |
| Endpoint retired | 410 | Link to the migration guide |
| Feature disabled for this plan | 403 | Code `plan_upgrade_required` |
| Maintenance window | 503 + Retry-After | |

## SLOs and alerting

- Availability SLI usually counts 5xx (and timeouts) as bad, 4xx as good (the service behaved correctly).
- Watch 4xx rates separately: a spike in 401/400 after a deploy often means you broke clients.
- 429 rates by client show who needs a higher limit or a better integration.
