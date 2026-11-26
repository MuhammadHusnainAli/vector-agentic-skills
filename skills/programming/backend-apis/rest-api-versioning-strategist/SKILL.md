---
name: rest-api-versioning-strategist
description: "Choose and run an API versioning strategy that lets the API evolve without breaking clients: what counts as a breaking change, evolving compatibly first (additive changes, tolerant readers, expand-and-contract), when a new version is justified, and the strategies with their trade-offs (URI major versions, header or media-type versions, date-based versions with per-account pinning and version transformers as Stripe does), plus deprecation and sunset policy (Deprecation and Sunset headers, timelines, usage telemetry, migration guides, brownouts). Ships openapi_diff.py, which compares two OpenAPI 3.x specs and classifies changes as breaking (removed operations or fields, type changes, new required inputs, tightened constraints, renamed operationIds), potentially breaking (new response enum values, properties becoming optional) or safe. Use when changing a public or partner API, choosing a versioning scheme, deprecating endpoints or adding a breaking-change gate to CI."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# REST API Versioning Strategist

The best versioning strategy is the one you rarely use. Most API changes can be made compatibly; a new version is a cost
every client pays, and old versions run for years. This skill keeps changes compatible by default, catches the ones that
aren't with `scripts/openapi_diff.py` in CI, and when a break is worth it, picks a versioning scheme and runs the
deprecation like a project.

## Trigger Conditions

Activate this skill when the user:
- Plans a change to an API with external or other-team clients
- Chooses between URI, header, media-type or date-based versioning
- Needs to deprecate or sunset endpoints or a version
- Wants to block breaking changes in CI

Spec authoring: `openapi-spec-writer`. Protobuf/gRPC evolution: `protobuf-schema-evolution-checker`. GraphQL evolution:
`graphql-schema-designer`.

## Workflow

```
1. CLASSIFY  -> python scripts/openapi_diff.py published.yaml proposed.yaml (references/breaking-changes.md)
2. AVOID     -> rework breaking changes into compatible ones: add, don't change; expand then contract
3. DECIDE    -> if still breaking: is the value worth every client migrating? Who are the clients?
4. SCHEME    -> pick the versioning strategy for the API's audience (references/versioning-strategies.md)
5. RUN BOTH  -> new version beside the old; shared core, thin version adapters
6. DEPRECATE -> headers, docs, notices, telemetry of who still calls it (references/deprecation-and-sunset.md)
7. SUNSET    -> brownouts, final notices, removal; keep the 410 Gone response for a while
```

## Compatible-by-Default Rules

| Instead of | Do |
|-----------|----|
| Renaming a field | Add the new field, keep the old one, deprecate it |
| Changing a field's type | Add a new field with the new type |
| Making an input required | Default it server-side, or require it only in a new version |
| Removing an endpoint | Deprecate, measure usage, sunset with notice |
| Changing semantics silently | New field or endpoint; semantic changes are breaking even if the schema isn't |
| Tightening validation | Apply to new resources only, or version it |

Clients must follow the tolerant reader principle: ignore unknown fields and handle unknown enum values. Write that into
your API guidelines and SDKs, or adding a field or enum value becomes breaking in practice.

## Diff Codes (openapi_diff.py)

| Code | Severity | Change |
|------|----------|--------|
| BC001-BC010 | error (breaking) | Operation removed, success status removed, response property removed, type changed, new required body property, required parameter added, request enum value removed, constraint tightened, operationId changed, new scope required |
| PB001-PB002 | warn | Response enum value added; response property became optional or nullable |
| NB001-NB003 | info | Operation added; optional input added; response property added |

## Scripts

```bash
python scripts/openapi_diff.py published.yaml proposed.yaml [--json]
```
Resolves local `$ref`s and compares operations, parameters, request bodies and response schemas recursively.
Semantic changes (same schema, different meaning) can't be detected: review them by hand.
JSON with the standard library; YAML needs PyYAML. Exit codes: 0 no breaking changes, 1 breaking, 2 unreadable files.

## Output

1. Change classification with fixes that keep each change compatible
2. Versioning scheme recommendation with reasons
3. Deprecation plan: headers, dates, communications, telemetry, brownouts
4. CI gate configuration

## Additional Resources

| File | Content |
|------|---------|
| [breaking-changes.md](references/breaking-changes.md) | Full breaking-change catalogue, behavioural breaks, expand-and-contract, tolerant reader |
| [versioning-strategies.md](references/versioning-strategies.md) | URI, header, media type, date-based with pinning and transformers; comparison and implementation |
| [deprecation-and-sunset.md](references/deprecation-and-sunset.md) | Deprecation and Sunset headers, timelines, communications, telemetry, brownouts, removal |
