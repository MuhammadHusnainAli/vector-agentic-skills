---
name: openapi-spec-writer
description: "Write and review OpenAPI 3.0 and 3.1 specifications that serve as the single contract for docs, SDKs, mocks, validation and tests: design-first workflow, document structure, reusable components (schemas, parameters, responses, security schemes), JSON Schema 2020-12 in 3.1, stable operationIds, tags, examples, problem+json errors, cursor pagination, idempotency and rate-limit headers, ETags, security schemes (OAuth2, bearer, API key), webhooks and callbacks, and the CI pipeline around the spec (Spectral rulesets, Prism mocks, contract tests, breaking-change checks, generated SDKs). Ships openapi_lint.py (JSON, or YAML with PyYAML) that resolves local refs and reports missing or duplicate operationIds, unresolved refs, path parameter mismatches, missing error responses and schemas, unbounded list responses and request fields, missing security, POSTs without Idempotency-Key, no 429s and missing examples. Use when writing, generating or reviewing an OpenAPI spec."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# OpenAPI Spec Writer

A good OpenAPI spec is the API: docs, client SDKs, server validation, mock servers and contract tests all come from it.
A weak spec (no operationIds, inline schemas everywhere, no error responses, unbounded lists) produces ugly SDKs, docs
that lie, and runtime surprises at scale. This skill writes specs design-first, reviews existing ones with
`scripts/openapi_lint.py`, and wires the spec into CI so it stays true.

## Trigger Conditions

Activate this skill when the user:
- Writes an OpenAPI/Swagger spec, or converts endpoints into one
- Reviews or cleans up a generated or legacy spec
- Sets up design-first API development, mocks, SDK generation or contract testing
- Migrates from Swagger 2.0 or OpenAPI 3.0 to 3.1

Endpoint design and capacity: `rest-api-endpoint-designer`. Breaking-change policy: `rest-api-versioning-strategist`.
SDKs: `sdk-from-openapi-generator`.

## Workflow

```
1. SKELETON  -> openapi, info, servers, tags, security schemes (references/spec-structure.md)
2. RESOURCES -> schemas in components first: entities, inputs, pages, problem details
3. OPERATIONS-> each path + method: operationId, summary, parameters, requestBody, responses with examples
4. PATTERNS  -> pagination, errors, idempotency, rate limits, ETags, async ops (references/spec-patterns.md)
5. LINT      -> python scripts/openapi_lint.py openapi.yaml (no errors or warnings), plus Spectral in CI
6. MOCK      -> Prism mock server; client teams build against it
7. GUARD     -> breaking-change diff in CI, contract tests, SDK generation (references/spec-workflow.md)
```

## Rules

| Rule | Why |
|------|-----|
| operationId on every operation, verbNoun, unique and stable | Becomes SDK method names; renaming breaks clients |
| Schemas in `components`, referenced with `$ref` | Reuse, consistent SDK types, readable diffs |
| Separate input and output schemas (`NewOrder`, `Order`, `OrderPatch`) | Read-only fields don't leak into requests |
| Every response documented, including errors with a shared problem schema | Clients handle failures intentionally |
| Bounds everywhere: maxLength, maxItems, maximum, max page size | Validation and capacity at scale |
| Examples for every request and success response | Docs, mocks and tests become realistic |
| `security` defined globally; public endpoints say `security: []` | Nothing is accidentally unauthenticated |
| Enum values as strings; document unknown-value handling | Adding a value shouldn't break clients |

## Lint Codes (openapi_lint.py)

| Code | Severity | Problem |
|------|----------|---------|
| OA001 | error | Missing openapi version, info title/version or paths |
| OA002 | error | Operation without operationId |
| OA003 | error | Duplicate operationId |
| OA004 | error | Unresolved local $ref |
| OA005 | error | Path template and path parameters don't match |
| OA006 | warn | No error responses |
| OA007 | warn | Success response without a schema |
| OA008 | warn | Unbounded list response (no pagination, no maxItems) |
| OA009 | warn | Unbounded request strings or arrays |
| OA010 | warn | No security requirement |
| OA011 | warn | POST without Idempotency-Key header |
| OA012 | info | No 429 response |
| OA013 | info | No summary or description |
| OA014 | info | No examples |

## Scripts

```bash
python scripts/openapi_lint.py openapi.yaml [--json]
```
JSON is read with the standard library; YAML needs PyYAML (`pip install pyyaml`). Local `$ref`s are resolved, including
recursive schemas. Remote refs are not fetched. Exit codes: 0 clean, 1 errors or warnings, 2 unreadable file.

## Output

A complete spec (YAML) with components, examples and patterns applied, lint results, and the CI setup (lint, mock,
breaking-change check, SDK generation).

## Additional Resources

| File | Content |
|------|---------|
| [spec-structure.md](references/spec-structure.md) | Document layout, components, naming, 3.0 vs 3.1 differences, splitting large specs |
| [spec-patterns.md](references/spec-patterns.md) | YAML snippets: pagination, problem details, idempotency, rate limits, ETags, async ops, webhooks, security |
| [spec-workflow.md](references/spec-workflow.md) | Design-first process, Spectral, Prism, contract tests, breaking-change checks, codegen |
