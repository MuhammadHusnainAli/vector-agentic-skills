# Spec Workflow

## Design-first

1. Draft the spec from the endpoint design (resources, operations, schemas, examples).
2. Review it like code: API review checklist, naming, consistency with other APIs.
3. Publish a mock (Prism) so client teams start immediately.
4. Implement the server against the spec; validate requests and responses at runtime in non-production (and requests in
   production).
5. Contract tests in CI: the running server conforms to the spec (Schemathesis for property-based testing, Dredd, or
   framework validators).

Code-first frameworks (FastAPI, NestJS, springdoc, ASP.NET) generate specs; treat the generated spec as the artefact to
review, lint and diff, and annotate code until it's complete (operationIds, examples, error responses).

## CI pipeline

| Step | Tool examples |
|------|---------------|
| Lint | `openapi_lint.py`, Spectral (with a custom ruleset), Redocly lint |
| Bundle | Redocly `bundle` |
| Breaking changes | oasdiff, openapi-diff (see rest-api-versioning-strategist) |
| Mock | Prism (`prism mock openapi.yaml`) |
| Contract tests | Schemathesis, Dredd |
| Docs | Redoc, Stoplight Elements, Scalar |
| SDKs | OpenAPI Generator, Speakeasy, Fern, Kiota |

## Spectral ruleset starter

```yaml
extends: ["spectral:oas"]
rules:
  operation-operationId: error
  operation-tags: error
  operation-description: warn
  oas3-valid-media-example: error
  path-keys-no-trailing-slash: error
  no-$ref-siblings: off            # allowed in 3.1
  paths-kebab-case:
    given: $.paths[*]~
    then: { function: pattern, functionOptions: { match: "^(/[a-z0-9-{}]+)+$" } }
```

## Review checklist

- [ ] Lint clean; Spectral clean
- [ ] Every operation: operationId, tag, summary, examples, error responses, security
- [ ] Lists paginated; inputs bounded
- [ ] Shared components used (Problem, pagination, rate-limit headers)
- [ ] No breaking changes vs the published version (or a version bump with migration notes)
- [ ] Mock server and docs regenerated
