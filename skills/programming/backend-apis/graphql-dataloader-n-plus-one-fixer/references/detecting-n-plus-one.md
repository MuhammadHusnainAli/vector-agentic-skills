# Detecting N+1

## How it forms

GraphQL executes field resolvers per object. For a list of N parents, a child field resolver runs N times. If each run
queries the database, you get 1 + N queries; another nested level multiplies again (1 + N + N x M).

The same happens in REST with ORMs: iterating `orders` and touching `order.customer` lazily loads one customer per
order.

## Detection

| Method | How |
|--------|-----|
| SQL logging in development | Enable query logging; run the operation; count statements |
| Tracing | OpenTelemetry spans per resolver and per query; N+1 appears as many identical sibling spans |
| APM | "N+1 query" detectors in Sentry, New Relic, Datadog |
| ORM helpers | Django `assertNumQueries`, `nplusone` package, Rails `bullet`, Hibernate statistics, `sqlalchemy` event counters |
| Tests | Wrap the database client with a counter; assert per operation |
| Production | Queries per request metric; alert when a route's average jumps |

## Query-count test pattern

```python
def test_orders_query_is_batched(client, db_counter):
    for page_size in (5, 50):
        db_counter.reset()
        client.execute("query($n: Int!) { orders(first: $n) { edges { node { customer { name } items { sku } } } } }",
                       variables={"n": page_size})
        assert db_counter.count <= 3, f"{db_counter.count} queries for {page_size} orders"
```
The assertion must hold for both page sizes: constant, not proportional.

## ORM fixes in REST

| ORM | Eager loading |
|-----|---------------|
| Django | `select_related` (FK), `prefetch_related` (reverse/M2M) |
| SQLAlchemy | `selectinload`, `joinedload`; `lazy="raise"` to catch accidental lazy loads |
| Rails | `includes`, `preload`; `strict_loading` |
| Hibernate/JPA | fetch joins, `@EntityGraph`, `@BatchSize` |
| Prisma | `include` / `select` with relations; or `findMany({ where: { id: { in: ids } } })` |
| EF Core | `Include`, `AsSplitQuery` |

In GraphQL, eager loading at the root is fragile (you don't know what nested fields will be requested); loaders are the
general fix.
