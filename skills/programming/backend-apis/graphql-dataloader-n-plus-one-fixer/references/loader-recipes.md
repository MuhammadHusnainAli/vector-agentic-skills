# Loader Recipes

## JavaScript / TypeScript (dataloader)

```ts
import DataLoader from "dataloader";

export function createLoaders(db, viewer) {
  return {
    customerById: new DataLoader<string, Customer | null>(async (ids) => {
      const rows = await db.customer.findMany({ where: { id: { in: [...ids] }, tenantId: viewer.tenantId } });
      const byId = new Map(rows.map((r) => [r.id, r]));
      return ids.map((id) => byId.get(id) ?? null);                // aligned, nulls for misses
    }, { maxBatchSize: 500 }),

    lineItemsByOrderId: new DataLoader<string, LineItem[]>(async (orderIds) => {
      const rows = await db.lineItem.findMany({ where: { orderId: { in: [...orderIds] } }, orderBy: { id: "asc" } });
      const groups = new Map<string, LineItem[]>(orderIds.map((id) => [id, []]));
      for (const r of rows) groups.get(r.orderId)!.push(r);
      return orderIds.map((id) => groups.get(id)!);                // one array per key, possibly empty
    }),
  };
}
```

## Loaders with arguments (composite keys)

```ts
// orders(first: 10, status: PAID) per customer
const ordersByCustomer = new DataLoader(
  async (keys: { customerId: string; status: string; first: number }[]) => {
    // group keys with identical args; one query per arg group using a window function
    // SELECT * FROM (SELECT o.*, row_number() OVER (PARTITION BY customer_id ORDER BY created_at DESC, id DESC) rn
    //                FROM orders o WHERE customer_id = ANY($1) AND status = $2) t WHERE rn <= $3
    ...
  },
  { cacheKeyFn: (k) => `${k.customerId}|${k.status}|${k.first}` },
);
```
Per-parent pagination in one query uses a window function (`row_number() OVER (PARTITION BY parent_id ...)`) or a
`LATERAL` join.

## Many-to-many

Batch the join table first (`tag_ids by post_id`), then load tags by ID through a second loader. Both loaders batch, so
the total is two queries regardless of list sizes.

## Priming

After loading a list of customers at the root, prime the by-ID loader: `customers.forEach(c => loaders.customerById.prime(c.id, c))`
so later lookups hit the cache.

## Python (Strawberry)

```python
from strawberry.dataloader import DataLoader

async def load_customers(ids: list[str]) -> list[Customer | None]:
    rows = await repo.customers_by_ids(ids)
    by_id = {r.id: r for r in rows}
    return [by_id.get(i) for i in ids]

def context_getter(request):          # per request
    return {"customer_loader": DataLoader(load_fn=load_customers, max_batch_size=500)}
```

## Go (dataloadgen)

```go
loader := dataloadgen.NewLoader(func(ctx context.Context, ids []string) ([]*Customer, []error) {
    rows, err := repo.CustomersByIDs(ctx, ids)
    byID := make(map[string]*Customer, len(rows))
    for _, r := range rows { byID[r.ID] = r }
    out := make([]*Customer, len(ids)); errs := make([]error, len(ids))
    for i, id := range ids { out[i] = byID[id]; if err != nil { errs[i] = err } }
    return out, errs
}, dataloadgen.WithBatchCapacity(500), dataloadgen.WithWait(time.Millisecond))
```
Create in middleware per request and put on the context.

## Java (java-dataloader, DGS)

`@DgsDataLoader(name = "customers")` implementing `MappedBatchLoader<String, Customer>`; DGS creates a registry per
request. Return a `Map` (mapped loader) to avoid alignment bugs.

## Across services

- Provide batch endpoints (`GET /customers?ids=a,b,c` or a `BatchGetCustomers` RPC) and call them from the loader.
- Federation: entity resolution (`__resolveReference`) is called per entity; implement it with a loader so the router's
  batch of representations becomes one call.
- Cache: per-request loader cache is for consistency within a request; use Redis for cross-request caching, with
  invalidation (see redis-cache-strategy-designer).
