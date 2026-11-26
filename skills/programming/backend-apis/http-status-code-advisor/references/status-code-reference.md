# Status Code Reference (RFC 9110 and related)

| Code | Meaning | Required/useful headers | Body | Client may retry? | Cacheable by default |
|------|---------|------------------------|------|-------------------|----------------------|
| 200 OK | Success with representation | ETag, Cache-Control | Yes | n/a | Yes (GET) |
| 201 Created | Resource created | Location | Created resource (recommended) | n/a | No |
| 202 Accepted | Accepted for async processing | Location (status resource) | Operation status | n/a | No |
| 204 No Content | Success, nothing to return | ETag (optional) | No body | n/a | Yes |
| 206 Partial Content | Range request | Content-Range | Partial | n/a | Yes |
| 301 / 308 | Moved permanently (308 keeps method) | Location | Optional | n/a | Yes |
| 302 / 307 | Temporary redirect (307 keeps method) | Location | Optional | n/a | No |
| 303 See Other | Go GET another resource (after POST) | Location | Optional | n/a | No |
| 304 Not Modified | Conditional GET matched | ETag, Cache-Control | No body | n/a | n/a |
| 400 Bad Request | Malformed or invalid request | | Problem details | No (fix the request) | No |
| 401 Unauthorized | Missing/invalid authentication | WWW-Authenticate | Problem details | After re-authenticating | No |
| 403 Forbidden | Authenticated, not permitted | | Problem details | No | No |
| 404 Not Found | No such resource (or hidden) | | Problem details | No | Yes (negative caching, short) |
| 405 Method Not Allowed | Method not supported | Allow | Problem details | No | Yes |
| 406 Not Acceptable | Can't produce requested media type | | Problem details | No | No |
| 409 Conflict | Conflicts with current state (duplicate, invalid transition, idempotency key reuse with different body) | | Problem details | After resolving | No |
| 410 Gone | Permanently removed (sunset) | | Problem details with migration link | No | Yes |
| 412 Precondition Failed | If-Match / If-Unmodified-Since failed | | Problem details | After re-fetching | No |
| 413 Content Too Large | Body exceeds limit | | Problem details with the limit | No | No |
| 415 Unsupported Media Type | Wrong Content-Type | Accept-Post / Accept-Patch | Problem details | No | No |
| 422 Unprocessable Content | Semantically invalid (validation) | | Problem details with field errors | No | No |
| 428 Precondition Required | Server requires If-Match | | Problem details | With precondition | No |
| 429 Too Many Requests | Rate limited | Retry-After, RateLimit headers | Problem details | Yes, after Retry-After | No |
| 500 Internal Server Error | Unexpected server error | | Problem details with request ID (no internals) | Idempotent requests, with backoff | No |
| 501 Not Implemented | Method not supported by server at all | | Problem details | No | Yes |
| 502 Bad Gateway | Invalid response from upstream | | Problem details | Yes, with backoff | No |
| 503 Service Unavailable | Overloaded, maintenance, shedding | Retry-After | Problem details | Yes, after Retry-After | No |
| 504 Gateway Timeout | Upstream timed out | | Problem details | Idempotent requests, with backoff (the first may have succeeded) | No |

Notes:
- Only retry non-idempotent requests (POST) on 5xx/timeouts if they carry an Idempotency-Key.
- 418, 420, 444, 499 and other non-standard codes: don't use in APIs (499 is an nginx log code for client closed request).
- `Retry-After` is seconds or an HTTP date; prefer seconds.
