# Error Catalogue

## Naming rules

- snake_case, specific, stable: `card_declined`, not `error_402` or `payment_error`.
- Generic codes for generic cases (`validation_failed`, `not_found`), specific codes where clients act differently
  (`insufficient_funds` vs `card_expired`).
- Field-level codes from a small shared set: `required`, `invalid_format`, `too_small`, `too_large`, `too_long`,
  `not_allowed`, `already_exists`, `not_found`.
- Never reuse a retired code for a new meaning.

## Starter catalogue

| Code | Status | Title | When |
|------|--------|-------|------|
| `validation_failed` | 400/422 | The request has invalid fields | Field errors in `errors[]` |
| `malformed_request` | 400 | The request body could not be parsed | Invalid JSON |
| `unsupported_media_type` | 415 | Unsupported content type | |
| `payload_too_large` | 413 | The request body is too large | Include the limit in `detail` |
| `authentication_required` | 401 | Authentication required | No credentials |
| `invalid_token` | 401 | The access token is invalid or expired | |
| `insufficient_scope` | 403 | The token lacks a required scope | Include required scope |
| `forbidden` | 403 | You don't have access to this resource | |
| `not_found` | 404 | Resource not found | |
| `method_not_allowed` | 405 | Method not allowed | |
| `conflict` | 409 | The request conflicts with the current state | Prefer specific codes |
| `already_exists` | 409 | A resource with this identifier already exists | |
| `invalid_state_transition` | 409 | The resource can't change to that state | e.g. cancel a shipped order |
| `idempotency_key_reused` | 422 | Idempotency key used with a different request | |
| `idempotency_key_in_progress` | 409 | A request with this key is still processing | |
| `precondition_failed` | 412 | The resource changed since you read it | ETag mismatch |
| `rate_limited` | 429 | Too many requests | Retry-After |
| `quota_exceeded` | 429/403 | Plan quota exhausted | Link to upgrade |
| `internal_error` | 500 | Something went wrong on our side | Request ID only |
| `upstream_error` | 502 | A dependency returned an invalid response | |
| `service_unavailable` | 503 | Temporarily unavailable | Retry-After |
| `upstream_timeout` | 504 | A dependency timed out | |

## Documentation page per type

Each `type` URI resolves to a page: what it means, common causes, how to fix it, example response, whether retrying
helps. Generate the pages from the catalogue file (YAML in the repo) so docs and code never drift.

## Governance

- Catalogue lives in one file (`errors.yaml`) shared by services and SDK generation.
- New codes reviewed like API changes; removing or renaming a code is breaking.
- SDKs expose codes as constants plus typed exceptions for common ones.
