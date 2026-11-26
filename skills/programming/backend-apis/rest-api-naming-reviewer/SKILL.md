---
name: rest-api-naming-reviewer
description: "Review and standardise naming across REST APIs so they read as one product: plural noun collections, kebab-case path segments, no verbs in paths (methods and action sub-resources instead), consistent path parameter names per resource, shallow nesting, no trailing slashes or file extensions, a single version prefix style, one casing for query parameters and JSON properties, naming of IDs, timestamps, booleans, money and enums, and an API style guide teams can follow. Ships path_naming_lint.py, which reads an OpenAPI spec or a plain route list and reports verbs in paths, casing that differs from the API's dominant style, uppercase segments, singular collections, trailing slashes and extensions, deep nesting, inconsistent parameter names, mixed version prefixes and mixed casing in query parameters and schema properties. Use when reviewing an API's naming, merging APIs from several teams or writing an API style guide."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# REST API Naming Reviewer

Naming is the part of an API every client sees on every call, and it's the hardest to change later. Inconsistent names
(`/user/{id}` next to `/orders/{orderId}`, `createdAt` next to `updated_at`, `/getInvoices` next to `/invoices`) make an
API feel like several APIs glued together, and they leak into every SDK. This skill reviews naming across the whole
surface with `scripts/path_naming_lint.py` and turns the decisions into a short style guide.

## Trigger Conditions

Activate this skill when the user:
- Reviews an API or OpenAPI spec for naming consistency
- Merges or aligns APIs built by different teams
- Writes or enforces an API style guide
- Asks how to name a path, parameter, field or action

Endpoint design: `rest-api-endpoint-designer`. Renaming safely: `rest-api-versioning-strategist`.

## Workflow

```
1. SCAN      -> python scripts/path_naming_lint.py openapi.yaml   (or a routes.txt from your router)
2. DECIDE    -> settle each convention once (table below); record it in the style guide
3. MAP       -> old name -> new name list; only rename what's worth a migration
4. MIGRATE   -> add new names alongside old (aliases), deprecate the old (versioning strategist)
5. ENFORCE   -> lint in CI (this script + Spectral rules); review new endpoints against the guide
```

## Conventions (sensible defaults)

| Item | Convention | Example |
|------|-----------|---------|
| Collections | Plural nouns, kebab-case | `/shipping-addresses` |
| Items | Collection + ID | `/orders/{orderId}` |
| Path parameters | `{resourceId}` in camelCase, same name everywhere | `{orderId}`, never `{id}` in one place and `{order_id}` in another |
| Actions | Action sub-resource or custom method | `POST /orders/{orderId}:cancel` or `POST /orders/{orderId}/cancellation` |
| Nesting | At most 2 levels; beyond that, top-level resource + filter | `/items?orderId=...` |
| Query parameters | Same casing as JSON properties | `createdAfter`, `pageSize` |
| JSON properties | One casing API-wide | camelCase (or snake_case; never both) |
| Booleans | Adjective or is/has | `active`, `isDefault`, `hasMore` |
| Timestamps | `...At` with RFC 3339 UTC | `createdAt`, `paidAt` |
| Dates | `...Date` / `...On` | `dueDate` |
| Money | Integer minor units + currency | `amount: 1299, currency: "GBP"` |
| Enums | lowercase snake strings | `"partially_refunded"` |
| IDs | Prefixed opaque strings | `"ord_01JD..."` |
| Versions | One prefix style | `/v1/...` |

## Lint Codes (path_naming_lint.py)

| Code | Severity | Problem |
|------|----------|---------|
| NM001 | warn | Verb in a path segment |
| NM002 | warn | Segment casing differs from the API's dominant style |
| NM003 | warn | Uppercase in a path segment |
| NM004 | warn | Singular collection before an ID while the API uses plurals |
| NM005 | warn | Trailing slash or file extension |
| NM006 | warn | Nesting deeper than `--max-depth` |
| NM007 | warn | Same resource's path parameter named differently |
| NM008 | warn | Mixed casing in query parameters or schema properties |
| NM009 | warn | Mixed version prefixes |
| NM010 | info | Collection name that isn't a noun |

## Scripts

```bash
python scripts/path_naming_lint.py openapi.yaml [--max-depth 2] [--json]
python scripts/path_naming_lint.py routes.txt          # one "METHOD /path" per line
```
Action suffixes (`{orderId}:cancel`) are understood. JSON with the standard library; YAML specs need PyYAML.
Exit codes: 0 no warnings, 1 warnings, 2 unreadable input.

## Output

Findings with the proposed name per item, the decisions table for the style guide, and a rename plan that keeps clients
working.

## Additional Resources

| File | Content |
|------|---------|
| [naming-style-guide.md](references/naming-style-guide.md) | A ready-to-adopt API naming style guide with rationale and examples |
