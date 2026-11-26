---
name: api-error-response-designer
description: "Design one consistent error format for an API that clients can program against and humans can debug: RFC 9457 Problem Details (type, title, status, detail, instance) extended with a stable machine-readable code, field-level validation errors with JSON Pointers, request and trace IDs, retry hints and documentation links; an error code catalogue with naming rules and owners; mapping internal exceptions to public errors without leaking stack traces, SQL or internal hostnames; localisation; and behaviour at scale (cheap error paths, no error amplification, logging and metrics by error code). Reviews APIs for inconsistent shapes, free-text-only errors, leaked internals, missing request IDs and errors that clients can't branch on. Use when defining or reviewing an API's errors, writing an error catalogue or building error middleware."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# API Error Response Designer

Errors are the part of an API that clients code against the most and that teams design the least. Free-text messages
force clients to parse English. Every service inventing its own shape forces SDKs to special-case. Stack traces in
responses leak internals to attackers. This skill designs one error contract: RFC 9457 Problem Details plus stable codes
and field errors. It also designs the catalogue and the middleware that enforces it.

## Trigger Conditions

Activate this skill when the user:
- Defines how an API reports errors, or unifies errors across services
- Writes an error code catalogue or error-handling middleware
- Reviews an API with inconsistent, vague or leaky errors
- Needs validation errors that point at the exact field

Status codes: `http-status-code-advisor`. Spec components: `openapi-spec-writer`.

## The Format

```json
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://docs.example.com/errors/validation_failed",
  "title": "The request has invalid fields",
  "status": 422,
  "code": "validation_failed",
  "detail": "2 fields are invalid.",
  "instance": "/orders",
  "requestId": "req_01JD9W7H8X3K",
  "errors": [
    { "pointer": "/items/0/quantity", "code": "too_small", "detail": "Must be at least 1.", "meta": { "minimum": 1 } },
    { "pointer": "/shipping/postalCode", "code": "invalid_format", "detail": "Not a valid postal code for GB." }
  ]
}
```

| Field | Rule |
|-------|------|
| `type` | Stable URI per error type, resolving to documentation |
| `title` | Short human summary, same for every occurrence of the type |
| `status` | Mirrors the HTTP status |
| `code` | Stable snake_case identifier clients branch on; never changes once published |
| `detail` | Human explanation for this occurrence; safe to show developers, not parsed by code |
| `errors[]` | Field-level problems with JSON Pointer (RFC 6901) to the request field |
| `requestId` | Same ID as in logs and traces (and a response header) |
| `retryable` / `Retry-After` | Optional hint for clients |

## Rules

| Rule | Why |
|------|-----|
| One shape for every error from every service (gateway included) | SDKs and clients handle errors once |
| Codes are API; messages are not | Clients branch on `code`; wording can change |
| Never return stack traces, SQL, internal hostnames, exception class names | Security and stability |
| Map every internal exception to a public error at the boundary; unknown -> 500 `internal_error` | No leaks, predictable shape |
| Every error has a request ID that support can look up | Debugging at scale |
| Report all validation errors at once | One round trip, not one per field |
| Error paths are cheap | At scale, error storms (bad deploy of a client) must not cost more than successes |

## Review Codes

| Code | Severity | Check |
|------|----------|-------|
| ER001 | high | Stack traces, SQL, internal hosts or exception names in responses |
| ER002 | high | Different error shapes across endpoints or services |
| ER003 | high | No machine-readable code (clients must parse messages) |
| ER004 | medium | Validation errors without field pointers, or only the first error returned |
| ER005 | medium | No request ID in error responses |
| ER006 | medium | Error codes reused for different meanings, or renamed |
| ER007 | medium | Errors returned with 2xx status |
| ER008 | low | No documentation page per error type |

## Output

The error schema (JSON Schema/OpenAPI component), the error catalogue, the exception-to-error mapping, middleware
outline for the stack in use, and review findings.

## Additional Resources

| File | Content |
|------|---------|
| [error-catalogue.md](references/error-catalogue.md) | Naming rules, starter catalogue with codes, statuses and messages, documentation pages, governance |
| [error-middleware.md](references/error-middleware.md) | Exception mapping, middleware examples (Express, FastAPI, Spring, Go), logging, metrics, localisation, scale |
