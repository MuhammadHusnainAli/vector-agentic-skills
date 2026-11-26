---
name: graphql-schema-designer
description: "Design GraphQL schemas that model the domain, evolve without versions and survive production traffic: types named for the domain, nullability as a deliberate contract, IDs and global object identification, Relay connections for every list, mutations with a single input and a payload carrying user errors, interfaces and unions, enums, custom scalars, deprecation instead of breaking changes, schema-first review, and the protections a public graph needs at scale (query depth and cost limits, persisted and trusted documents, pagination caps, rate limiting by cost, CDN caching of persisted GET queries, federation boundaries). Ships graphql_schema_lint.py, which parses SDL and reports unbounded lists of objects, nullable list items, mutations without input/payload, identifiers typed String/Int, naming that breaks conventions, RPC-style query names, deprecations without reasons and foreign-key fields without relationships. Use when designing, reviewing or evolving a GraphQL schema."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# GraphQL Schema Designer

A GraphQL schema is a product: clients compose queries against it in ways you didn't plan, and you can't version it. Every
field you add is effectively forever, and every unbounded list is an open invitation to an expensive query. Good schemas
model the domain (not the database), make nullability a deliberate contract, paginate everything that grows, and come
with cost limits from day one. This skill designs and reviews schemas with `scripts/graphql_schema_lint.py`.

## Trigger Conditions

Activate this skill when the user:
- Designs a new GraphQL schema or adds types and fields
- Reviews SDL for conventions, evolvability or performance risks
- Exposes a public or partner GraphQL API and needs abuse protection
- Plans federation or splits a graph across teams

Resolvers: `graphql-resolver-writer`. N+1 problems: `graphql-dataloader-n-plus-one-fixer`. Pagination internals:
`api-pagination-designer`.

## Workflow

```
1. DOMAIN    -> entities and relationships from the client's perspective (not tables) (references/schema-design-rules.md)
2. TYPES     -> objects, interfaces, unions, enums, scalars; IDs; nullability decisions
3. LISTS     -> every growing list as a Connection with first/after and a max page size
4. MUTATIONS -> verbNoun, input: XInput!, XPayload with userErrors
5. LINT      -> python scripts/graphql_schema_lint.py schema.graphql
6. PROTECT   -> depth/cost limits, persisted documents, timeouts (references/graphql-at-scale.md)
7. EVOLVE    -> add fields, deprecate with reasons, track field usage before removal
```

## Rules

| Rule | Why |
|------|-----|
| Name types after the domain (`Order`, not `OrderRow`) | Schema outlives the database |
| Non-null where the server guarantees a value; nullable where it might fail or not exist | Over-using `!` makes one failing field null out the whole parent |
| Lists `[T!]!`; growing lists as Connections | No null items; bounded pages |
| `ID` for identifiers, opaque and globally unique | Caching (Apollo/Relay normalisation), refetching via `node(id:)` |
| Relationships as object fields (`author: User`), not `authorId` | Clients traverse the graph |
| Mutations: `input: XInput!` -> `XPayload` with `userErrors` | Add fields without breaking; errors as data |
| Enums for closed sets; document that new values may appear | Clients handle unknown values |
| Deprecate with a reason, measure usage, then remove | No versioning in GraphQL |

## Lint Codes (graphql_schema_lint.py)

| Code | Severity | Problem |
|------|----------|---------|
| GQ001 | warn | List of objects without pagination arguments |
| GQ002 | warn | Nullable list items |
| GQ003 | warn | Mutation without single input or without payload |
| GQ004 | warn | Identifier typed String/Int |
| GQ005 | warn | Naming convention broken |
| GQ006 | warn | RPC-style Query field name |
| GQ007 | warn | @deprecated without reason |
| GQ008 | info | Foreign-key field without relationship field |
| GQ009 | info | Type without description |

## Scripts

```bash
python scripts/graphql_schema_lint.py schema.graphql [more.graphql ...] [--json]
```
Parses SDL with the standard library (types, interfaces, inputs, enums, extend type). Exit codes: 0 no warnings,
1 warnings, 2 unreadable input or no types found.

## Output

Schema SDL with descriptions, lint results, the scale protections configuration, and an evolution/deprecation plan.

## Additional Resources

| File | Content |
|------|---------|
| [schema-design-rules.md](references/schema-design-rules.md) | Modelling, nullability, IDs and node interface, connections, mutations and user errors, unions/interfaces, scalars, evolution |
| [graphql-at-scale.md](references/graphql-at-scale.md) | Cost and depth limits, persisted documents, caching, rate limits by cost, timeouts, federation, observability |
