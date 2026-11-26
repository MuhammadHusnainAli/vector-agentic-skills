# Resolver Testing

## Execute real operations against the real schema

```ts
const result = await executeOperation(server, {
  query: `query($id: ID!) { order(id: $id) { id customer { name } lineItems(first: 2) { edges { node { sku } } } } }`,
  variables: { id: "ord_1" },
}, { contextValue: testContext({ viewer: alice }) });
expect(result.errors).toBeUndefined();
expect(result.data.order.customer.name).toBe("Alice");
```
Test through the schema (not resolver functions in isolation) so argument parsing, nullability and error formatting are
covered.

## Fakes over mocks

Inject fake services or an in-memory database through the context. Mocking every resolver hides integration bugs.

## Query-count assertions (catch N+1)

```ts
const db = countingDb();
await run(`{ orders(first: 50) { edges { node { customer { name } } } } }`, { db });
expect(db.queryCount).toBeLessThanOrEqual(3);   // orders + customers batch + maybe count
```

## Authorization tests

For each sensitive type, test every path that reaches it:
- `order(id:)` as owner, as another user, anonymous.
- `customer.orders` as the same three viewers.
- Field-level rules (`user.email`) as self, other, admin.

## Error tests

- Expected failure returns `userErrors` with the right code and `null` object.
- Unexpected exception returns a masked error with a request ID, and the log contains the stack trace.

## Performance smoke tests

- Largest allowed page sizes with nested connections, under the cost limit, stay within the latency budget.
- Over-limit queries are rejected before execution.
