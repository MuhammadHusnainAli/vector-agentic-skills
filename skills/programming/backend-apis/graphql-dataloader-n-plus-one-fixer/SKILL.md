---
name: graphql-dataloader-n-plus-one-fixer
description: "Find and fix N+1 query problems in GraphQL (and ORM-backed REST) APIs with DataLoader-style batching: how N+1 arises from per-field resolvers, detecting it (query counts per operation, tracing spans, SQL logs, tests that assert query counts), writing batch functions that return results in key order with nulls for misses, one-to-many and many-to-many loaders, loaders with arguments (pagination per parent, filters) via composite keys, per-request caching versus shared caches, priming loaders, max batch size, batching across services (batch endpoints, gRPC batch RPCs, federation entity resolution), and language-specific implementations (dataloader for JavaScript, strawberry and aiodataloader for Python, dataloadgen for Go, java-dataloader, GreenDonut for .NET). Reviews code for per-item queries in resolvers, loaders created globally, batch functions returning misaligned results and unbounded batches. Use when GraphQL queries are slow, database query counts explode on lists, or when adding relationship fields."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# GraphQL DataLoader N+1 Fixer

`{ orders(first: 100) { customer { name } } }` looks like one query. Without batching it's 101 database queries: one for
orders, one per customer. Nest another level and it's thousands. At high traffic that's the difference between 2 queries
and 2,000 per request. DataLoader fixes it by collecting every key requested during one tick of execution and loading
them in a single batch. This skill finds the N+1s, writes correct loaders, and proves the fix with query-count tests.

## Trigger Conditions

Activate this skill when the user:
- Has slow GraphQL queries, especially on lists with nested objects
- Sees database query counts growing with page size
- Adds relationship fields to a schema
- Reviews loader code or sees wrong data returned from a loader

Resolver structure: `graphql-resolver-writer`. Schema design: `graphql-schema-designer`. Database pools:
`database-connection-pool-tuner`.

## Workflow

```
1. DETECT    -> count queries per operation (SQL log, tracing, test helper) (references/detecting-n-plus-one.md)
2. LOCATE    -> which field resolver issues per-item calls
3. LOADER    -> batch function: keys -> one query -> results in key order (references/loader-recipes.md)
4. WIRE      -> loaders created per request in context; field resolvers call loader.load(parent.fkId)
5. SPECIAL   -> one-to-many, many-to-many, loaders with arguments (composite keys), cross-service batching
6. PROVE     -> test asserting query count stays constant as page size grows
7. GUARD     -> query-count budget in CI for key operations; tracing alerts
```

## Correctness Rules for Batch Functions

| Rule | Why |
|------|-----|
| Return an array the same length and order as the input keys | DataLoader maps results by position |
| Return `null` (or an Error) for missing keys, never skip them | Skipping shifts every later result to the wrong parent |
| One-to-many: return an array (possibly empty) per key | `lineItemsByOrderId` |
| Keys must be comparable (primitives or a `cacheKeyFn`) | Object keys break caching |
| Apply authorisation inside the batch (filter by viewer) | Loaders bypass root-level checks otherwise |
| Create loaders per request | Shared loaders cache across users (data leak) and grow forever |
| Cap batch size (`maxBatchSize`) | `WHERE id IN (50,000 ids)` hurts too |

## Review Codes

| Code | Severity | Check |
|------|----------|-------|
| NP001 | high | Per-item database/HTTP call in a list field resolver |
| NP002 | high | Batch function returns results not aligned to keys (skips misses, reorders) |
| NP003 | high | Loader instance shared across requests (cache leaks between users) |
| NP004 | medium | Loader with arguments keyed only by ID (wrong results for different args) |
| NP005 | medium | No max batch size for loaders that can receive thousands of keys |
| NP006 | medium | Loader bypasses authorisation filters |
| NP007 | low | No test asserting query counts for list operations |

## Output

Loader implementations, resolver changes, the query-count test, and the before/after query counts.

## Additional Resources

| File | Content |
|------|---------|
| [detecting-n-plus-one.md](references/detecting-n-plus-one.md) | How N+1 forms, detection with logs, tracing and tests, ORM-level N+1 in REST too |
| [loader-recipes.md](references/loader-recipes.md) | Batch functions in JS, Python, Go, Java; one-to-many, many-to-many, composite keys, priming, cross-service batching |
