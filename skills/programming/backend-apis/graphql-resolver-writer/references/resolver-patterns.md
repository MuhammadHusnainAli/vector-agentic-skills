# Resolver Patterns

## Context per request (TypeScript, Apollo Server / Yoga)

```ts
export async function createContext({ req }): Promise<Ctx> {
  const viewer = await authenticate(req.headers.authorization);          // null for anonymous
  return {
    viewer,
    requestId: req.headers["x-request-id"] ?? crypto.randomUUID(),
    loaders: createLoaders({ viewer }),                                  // new DataLoaders every request
    services: { orders: new OrderService({ viewer }), customers: new CustomerService({ viewer }) },
    signal: req.signal,                                                  // cancellation
  };
}
```

## Thin resolvers

```ts
const resolvers = {
  Query: {
    order: (_p, { id }, ctx) => ctx.services.orders.get(id),            // service authorises and returns null if not visible
    orders: (_p, args, ctx) => ctx.services.orders.list(connectionArgs(args, { max: 100 })),
  },
  Order: {
    customer: (order, _a, ctx) => ctx.loaders.customerById.load(order.customerId),
    lineItems: (order, args, ctx) => ctx.loaders.lineItemsByOrder.load({ orderId: order.id, ...connectionArgs(args, { max: 100 }) }),
  },
  Mutation: {
    cancelOrder: async (_p, { input }, ctx) => {
      const result = await ctx.services.orders.cancel(input.orderId, input.reason);
      return result.ok ? { order: result.order, userErrors: [] }
                       : { order: null, userErrors: [{ field: ["orderId"], message: result.message, code: result.code }] };
    },
  },
};
```

## Authorization

- Authorise where data is fetched (service/loader), filtering by the viewer: `loadMany` returns `null` for objects the
  viewer can't see.
- For field-level rules (e.g. `User.email` only for self or admins): directive (`@auth(requires: ADMIN)`) or a check in
  the field resolver.
- Default deny: new types are private until rules are written.

## Errors

| Situation | Return |
|-----------|--------|
| Expected business failure in a mutation | `userErrors` in the payload |
| Not found by ID | `null` |
| Not authenticated | GraphQL error with `extensions.code: "UNAUTHENTICATED"` (HTTP 200 or 401 at transport per server config) |
| Forbidden | `extensions.code: "FORBIDDEN"` or `null` to hide existence |
| Unexpected | Masked: `"Internal server error"` with a request ID; full error logged |

Use the server's error masking (Yoga masks by default; Apollo `formatError`).

## Look-ahead

Inspect the selection set to avoid over-fetching or to join eagerly:
```ts
import { parseResolveInfo } from "graphql-parse-resolve-info";
const fields = parseResolveInfo(info); // only select columns the query asked for
```
Use sparingly; loaders handle most cases.

## Subscriptions

- Transport: graphql-ws over WebSocket (or SSE). Authenticate on connection init; re-check authorisation per event.
- Filter events per subscriber on the server; publish via Redis/Kafka for multiple instances.
- Bound fan-out: limit subscriptions per connection and payload size.

## Other languages

| Server | Notes |
|--------|-------|
| Strawberry (Python) | `@strawberry.field` methods; `info.context` per request; `strawberry.dataloader.DataLoader` |
| gqlgen (Go) | Generated resolver interfaces; context carries loaders (`dataloadgen`); use `ctx` deadlines |
| Netflix DGS / graphql-java | `@DgsData` fetchers; `DataLoader` registry per request; `DataFetchingEnvironment` |
| Hot Chocolate (.NET) | Resolvers on types; built-in DataLoader (`GreenDonut`), projections and filtering |
