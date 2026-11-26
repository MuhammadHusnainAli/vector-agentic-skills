# Schema Design Rules

## Modelling

- Start from client use cases (screens, integrations), not tables. A `User` type may combine data from three services.
- Expose relationships as fields: `order.customer`, `customer.orders(first:)`.
- Avoid generic types (`Item`, `Data`, `Info`) and leaking storage (`createdTs`, `fk_user`).
- Computed fields are fine (`order.isRefundable`), they move logic to the server where it's consistent.

## Nullability

| Field | Choice | Reason |
|-------|--------|--------|
| `id`, required domain facts (`order.status`) | Non-null | Always present |
| Fields from other services that may fail | Nullable | A failure nulls the field, not the parent |
| Optional data (`user.phone`) | Nullable | |
| Lists | `[T!]!` | Empty list rather than null; no null items |
| Root query fields by ID (`user(id:)`) | Nullable | Not found -> null |

Changing nullable -> non-null in an output is safe; non-null -> nullable in an output breaks clients. For inputs, the
reverse.

## Global object identification

```graphql
interface Node { id: ID! }
type Query { node(id: ID!): Node, nodes(ids: [ID!]!): [Node]! }
type User implements Node { id: ID! ... }
```
IDs opaque (e.g. base64 of `User:123` or prefixed `usr_...`) so clients can refetch any object and caches normalise.

## Connections

```graphql
type Query { orders(first: Int = 20, after: String, filter: OrderFilter, orderBy: OrderOrder): OrderConnection! }
type OrderConnection { edges: [OrderEdge!]! pageInfo: PageInfo! totalCount: Int }
type OrderEdge { cursor: String! node: Order! }
```
Enforce a max `first` (e.g. 100) in resolvers; `totalCount` only if it's cheap.

## Mutations

```graphql
type Mutation { cancelOrder(input: CancelOrderInput!): CancelOrderPayload! }
input CancelOrderInput { orderId: ID! reason: CancelReason clientMutationId: String }
type CancelOrderPayload { order: Order userErrors: [UserError!]! }
type UserError { field: [String!] message: String! code: CancelOrderErrorCode! }
```
- Expected business errors as `userErrors` (data), unexpected failures as GraphQL `errors`.
- Name mutations verbNoun for the domain action (`cancelOrder`, not `updateOrderStatus`).
- Idempotency for retries: accept an idempotency key in the input for payments and creates.

## Interfaces, unions, enums, scalars

- Interface for shared fields and behaviour (`Node`, `Timestamped`); union for "one of" results (`SearchResult = User | Order`).
- Enums in UPPER_SNAKE_CASE; clients must handle unknown values.
- Custom scalars for validated formats: `DateTime` (RFC 3339), `URL`, `EmailAddress`, `Money` as an object (amount + currency) rather than a scalar.

## Evolution

- Add freely: types, fields, optional arguments, enum values (with client tolerance).
- `@deprecated(reason: "Use totalPrice. Removal after 2027-06-30.")`, then monitor field usage (Apollo GraphOS, schema
  usage reporting, logs of resolved fields) and remove when usage is zero.
- Breaking: removing fields/types, changing types, making arguments required, output non-null -> nullable.
- Check changes in CI with a schema diff (graphql-inspector, Apollo `rover graph check`).
