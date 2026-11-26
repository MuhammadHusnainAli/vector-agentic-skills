# Error Middleware

## Mapping layer

```
Domain/infra exception            -> Public error (code, status)
ValidationError(field errors)     -> validation_failed (422) with errors[]
NotFound(resource)                -> not_found (404)
PermissionDenied                  -> forbidden (403)  (or not_found 404 to hide existence)
VersionConflict                   -> precondition_failed (412)
StateTransitionError              -> invalid_state_transition (409)
RateLimitExceeded(retry_after)    -> rate_limited (429) + Retry-After
DependencyTimeout                 -> upstream_timeout (504)
CircuitOpen                       -> service_unavailable (503) + Retry-After
anything else                     -> internal_error (500), full details only in logs
```
Domain code raises domain exceptions; only the boundary knows HTTP.

## Examples

**FastAPI**
```python
@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    body = {"type": f"https://docs.example.com/errors/{exc.code}", "title": exc.title, "status": exc.status,
            "code": exc.code, "detail": exc.detail, "requestId": request.state.request_id, "errors": exc.field_errors or None}
    return JSONResponse({k: v for k, v in body.items() if v is not None}, status_code=exc.status,
                        media_type="application/problem+json", headers=exc.headers)

@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    log.exception("unhandled", extra={"request_id": request.state.request_id})
    return JSONResponse({"type": "https://docs.example.com/errors/internal_error", "title": "Something went wrong on our side",
                         "status": 500, "code": "internal_error", "requestId": request.state.request_id},
                        status_code=500, media_type="application/problem+json")
```

**Express**
```js
app.use((err, req, res, next) => {
  const e = err instanceof AppError ? err : AppError.internal();
  if (!(err instanceof AppError)) req.log.error({ err, requestId: req.id }, "unhandled");
  res.status(e.status).type("application/problem+json").set(e.headers ?? {})
     .json({ type: `https://docs.example.com/errors/${e.code}`, title: e.title, status: e.status,
             code: e.code, detail: e.detail, requestId: req.id, errors: e.fieldErrors });
});
```

**Spring Boot 3**: return `ProblemDetail` from `@ExceptionHandler` methods in a `@RestControllerAdvice`, set
`spring.mvc.problemdetails.enabled=true`, add `code` and `requestId` as properties.

**Go**: a single `writeProblem(w, r, err)` helper using `errors.As` against typed errors; middleware recovers panics into
`internal_error`.

## Logging and metrics

- Log every 5xx with stack trace and request ID; log 4xx at info/debug with the code (not the full body, which may hold
  personal data).
- Metrics: `http_errors_total{code="card_declined", route="/payments", status="402"}`. Alert on 5xx rate and unusual
  spikes of specific 4xx codes after deploys.

## Localisation

Keep `code` stable and English `title`/`detail` by default; localise `detail` with `Accept-Language` only if end users see
messages directly. Better: clients map codes to their own localised UI strings.

## At scale

- Error responses are small and constant-cost: no DB lookups to build them, no per-request template rendering.
- Don't log full request bodies on 4xx storms; sample.
- A misbehaving client sending 100k invalid requests/s should hit the edge rate limiter, not your validation code.
