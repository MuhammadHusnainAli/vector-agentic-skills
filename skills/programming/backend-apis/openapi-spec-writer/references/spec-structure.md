# Spec Structure

```yaml
openapi: 3.1.0
info:
  title: Orders API
  version: 2025-11-01          # or semver; matches your versioning strategy
  description: Create and manage orders.
  contact: { name: API team, url: https://example.com/support }
servers:
  - url: https://api.example.com/v1
tags:
  - name: Orders
    description: Order lifecycle
security:
  - oauth2: [orders:read]
paths:
  /orders: { ... }
components:
  schemas: { ... }
  parameters: { Cursor: ..., Limit: ..., IdempotencyKey: ... }
  responses: { Problem: ..., TooManyRequests: ..., NotFound: ... }
  securitySchemes: { oauth2: ..., apiKey: ... }
  headers: { RateLimitLimit: ..., RateLimitRemaining: ..., RetryAfter: ... }
```

## Naming

| Item | Convention | Example |
|------|-----------|---------|
| operationId | verbNoun, camelCase | `listOrders`, `getOrder`, `createOrder`, `cancelOrder` |
| Schemas | PascalCase nouns; role suffixes | `Order`, `NewOrder`, `OrderPatch`, `OrderPage` |
| Properties | One casing everywhere | `createdAt` (camel) or `created_at` (snake) |
| Tags | Resource groups | `Orders`, `Customers` |
| Parameters (components) | PascalCase | `Cursor`, `Limit` |

## OpenAPI 3.0 vs 3.1

| Topic | 3.0 | 3.1 |
|-------|-----|-----|
| Schema dialect | Extended subset of JSON Schema draft 4/5 | Full JSON Schema 2020-12 |
| Nullable | `nullable: true` | `type: [string, "null"]` |
| Examples in schemas | `example` | `examples` (array) |
| Exclusive min/max | booleans | numbers |
| Webhooks | Not supported (callbacks only) | Top-level `webhooks` |
| `$ref` siblings | Ignored | Allowed (description, summary) |
| File uploads | `format: binary` | `contentMediaType` / `contentEncoding` |

Check your tooling (codegen, validators, docs) supports 3.1 before migrating.

## Large specs

- Split by resource into files (`paths/orders.yaml`, `schemas/order.yaml`) and bundle for publishing (Redocly CLI
  `bundle`, swagger-cli).
- One source of truth: generate server stubs or validate the server against the spec; don't maintain two copies.
- Keep shared components (Problem, pagination, headers) in a common file reused across APIs.

## Schemas

- `required` lists explicit; `additionalProperties: false` on inputs (reject unknown fields) but tolerant outputs.
- `readOnly` for server-set fields (id, createdAt), `writeOnly` for secrets (password).
- Discriminated unions with `oneOf` + `discriminator` (and the mapping) for polymorphic resources.
- Formats: `date-time`, `uuid`, `email`, `uri`; `pattern` for IDs (`^ord_[a-zA-Z0-9]{24}$`).
