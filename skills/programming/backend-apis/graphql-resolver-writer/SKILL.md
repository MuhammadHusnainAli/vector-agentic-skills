---
name: graphql-resolver-writer
description: "Write GraphQL resolvers that are thin, fast, secure and testable in any major server (Apollo Server, GraphQL Yoga, Mercurius, Strawberry, Graphene, gqlgen, graphql-java/DGS, Hot Chocolate): resolver signatures (parent, args, context, info), per-request context with auth, loaders and request-scoped clients, delegation to services instead of business logic in resolvers, batching with DataLoader, field-level authorization, connection resolvers with cursors and page caps, mutation resolvers returning payloads with user errors, error mapping and masking, cancellation and timeouts, look-ahead with the selection set, subscriptions, and testing with real schemas. Reviews resolvers for business logic in resolvers, per-item database calls, auth checks missing on nested fields, unbounded lists, leaked internal errors, shared mutable state across requests and missing timeouts. Use when implementing or reviewing GraphQL resolvers."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# GraphQL Resolver Writer

Resolvers are where a clean schema meets reality. Most GraphQL production problems are resolver problems: business logic
copied into resolvers, a database call per list item, an auth check on `Query.order` but not on `Customer.orders`, an
internal exception leaked into `errors`, a context object shared between requests. This skill writes resolvers as thin
adapters over services, with batching, authorization and errors handled the same way everywhere.

## Trigger Conditions

Activate this skill when the user:
- Implements resolvers for a schema in any GraphQL server library
- Has slow GraphQL queries, auth gaps or inconsistent errors
- Writes mutation resolvers, connection resolvers or subscriptions
- Reviews or tests resolver code

Schema design: `graphql-schema-designer`. Batching in depth: `graphql-dataloader-n-plus-one-fixer`.

## Workflow

```
1. CONTEXT   -> build per request: viewer (auth), loaders, request ID, deadline (references/resolver-patterns.md)
2. ROOTS     -> Query/Mutation resolvers call services with validated args
3. FIELDS    -> object fields resolve via loaders (by parent IDs), never direct per-item queries
4. AUTH      -> authorize in the service layer or per type/field; deny by default
5. LISTS     -> connections with cursor, max first, deterministic order
6. MUTATIONS -> validate, call domain service, return payload with userErrors; idempotency key where needed
7. ERRORS    -> map domain errors to userErrors or coded GraphQL errors; mask unexpected ones
8. TEST      -> execute operations against the real schema with fakes for services (references/resolver-testing.md)
```

## Rules

| Rule | Why |
|------|-----|
| Resolvers adapt; services decide | Business rules stay reusable by REST, jobs and tests |
| Context created per request | Loaders and viewer must not leak across requests |
| Every relationship field uses a loader | Prevents N+1 |
| Authorize on the object, not only the root field | Nested paths reach the same data (`customer.orders`) |
| Respect cancellation and deadlines | Abandoned queries shouldn't keep running |
| Mask unexpected errors | No stack traces or SQL in `errors` |
| Default resolvers for plain properties | Less code; only write resolvers that compute or fetch |

## Review Codes

| Code | Severity | Check |
|------|----------|-------|
| RS001 | high | Authorization only on root fields; nested fields expose the same data unchecked |
| RS002 | high | Database or HTTP call per item in a list field (N+1) |
| RS003 | high | Loaders, caches or viewer stored in module-level state shared across requests |
| RS004 | medium | Business logic inside resolvers (validation rules, pricing, state transitions) |
| RS005 | medium | Internal errors returned raw to clients |
| RS006 | medium | Connection resolver without max page size or stable ordering |
| RS007 | medium | No timeout or cancellation propagated to downstream calls |
| RS008 | low | Resolvers written for plain fields the default resolver handles |

## Output

Resolver code for the target server, context factory, loader registry, error mapping, and tests.

## Additional Resources

| File | Content |
|------|---------|
| [resolver-patterns.md](references/resolver-patterns.md) | Context, delegation, authorization, connections, mutations, errors, look-ahead, subscriptions, per-language examples |
| [resolver-testing.md](references/resolver-testing.md) | Testing operations end to end, fakes, query-count assertions, auth tests |
