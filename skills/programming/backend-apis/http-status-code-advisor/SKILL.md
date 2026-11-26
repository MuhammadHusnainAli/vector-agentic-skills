---
name: http-status-code-advisor
description: "Pick the correct HTTP status code for every API outcome according to RFC 9110 and related RFCs, and use status codes as the contract that clients, retries, caches, load balancers and SLOs depend on: 200/201/202/204 for success, 304 and conditional requests, redirects, 400 vs 422 for invalid input, 401 vs 403 vs 404 (and hiding existence), 405, 406, 409 vs 412 for conflicts, 410 for sunset resources, 413, 415, 428, 429 with Retry-After, 500 vs 502 vs 503 vs 504, which codes clients may retry, which are cacheable, and how codes feed error budgets and alerting. Reviews APIs for 200-with-error-body, 500 for client mistakes, 404 vs 403 leaks, wrong retry signals and codes that break caching. Use when designing responses, reviewing an API's error handling or debugging client retry behaviour."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# HTTP Status Code Advisor

Status codes aren't decoration. Retry libraries, CDNs, load balancers, monitoring and client SDKs all act on them without
reading the body. A `200 {"error": ...}` passes health checks and pollutes caches. A `500` for bad input burns the error
budget and triggers pages for a client bug. A `503` without `Retry-After` invites retry storms. This skill picks the
code by asking who must act (client or server) and what they should do next.

## Trigger Conditions

Activate this skill when the user:
- Asks which status code to return for a situation
- Designs an API's responses or error handling
- Debugs retries, caching or alerting that misbehave because of status codes
- Reviews an API that returns 200 for errors or 500 for client mistakes

Error body format: `api-error-response-designer`. Endpoint design: `rest-api-endpoint-designer`.

## Decision Path

```
1. Did the request succeed?            -> 2xx (which one depends on what happened: references/status-code-reference.md)
2. Can the client fix it by changing the request?   -> 4xx
   - malformed syntax / invalid parameters            -> 400
   - valid syntax, fails business/semantic validation -> 422 (or 400 if you use one code for all validation)
   - not authenticated / bad token                    -> 401 + WWW-Authenticate
   - authenticated but not allowed                    -> 403 (or 404 to hide existence)
   - resource state conflict                          -> 409 ; precondition (If-Match) failed -> 412
   - too many requests                                -> 429 + Retry-After
3. Is it the server's (or a dependency's) fault?      -> 5xx
   - bug / unexpected                                 -> 500
   - upstream returned garbage                        -> 502 ; upstream timed out -> 504
   - overloaded / maintenance / shedding load         -> 503 + Retry-After
```

## Rules

| Rule | Why |
|------|-----|
| Never 200 with an error body | Breaks retries, caches, monitoring and SDKs |
| 4xx = client must change something; 5xx = retrying the same request may work | Retry logic and SLOs depend on it |
| Validation failures are never 5xx | They'd page on-call for client bugs and burn the error budget |
| 429 and 503 carry Retry-After | Turns retry storms into orderly backoff |
| 401 includes `WWW-Authenticate` | Required by the spec; tells clients how to authenticate |
| Use 404 instead of 403 when existence is sensitive | Avoid confirming that a private resource exists |
| Same situation, same code, everywhere | Clients branch on codes |

## Review Codes

| Code | Severity | Check |
|------|----------|-------|
| SC001 | high | 200 (or any 2xx) returned with an error payload |
| SC002 | high | 5xx returned for invalid client input or auth failures |
| SC003 | high | 429/503 without Retry-After at high-traffic endpoints |
| SC004 | medium | 403 reveals existence of resources the caller may not know about |
| SC005 | medium | 409 vs 412 vs 422 used inconsistently |
| SC006 | medium | 201 without Location for creates; 202 without a status resource |
| SC007 | medium | 404 for unsupported method (should be 405 with Allow) |
| SC008 | low | 204 with a body; 304 with a body |
| SC009 | low | Redirects used for API versioning or POST requests (clients may change method on 301/302) |

## Output

A status table per endpoint (situation -> code -> body -> headers -> retryable?), plus findings with fixes when reviewing.

## Additional Resources

| File | Content |
|------|---------|
| [status-code-reference.md](references/status-code-reference.md) | Codes used in APIs: meaning, headers, body, retryable, cacheable |
| [scenario-decisions.md](references/scenario-decisions.md) | Worked scenarios: creation, async jobs, conflicts, auth, rate limits, partial failures, upstream errors |
