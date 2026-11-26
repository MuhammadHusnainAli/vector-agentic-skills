# Spec Patterns

## Cursor pagination

```yaml
components:
  parameters:
    Cursor: { name: cursor, in: query, schema: { type: string, maxLength: 500 }, description: Opaque cursor from nextCursor }
    Limit:  { name: limit, in: query, schema: { type: integer, minimum: 1, maximum: 100, default: 20 } }
  schemas:
    OrderPage:
      type: object
      required: [data]
      properties:
        data: { type: array, items: { $ref: '#/components/schemas/Order' }, maxItems: 100 }
        nextCursor: { type: [string, "null"] }
```

## Problem details (RFC 9457)

```yaml
components:
  schemas:
    Problem:
      type: object
      properties:
        type: { type: string, format: uri }
        title: { type: string }
        status: { type: integer }
        detail: { type: string }
        instance: { type: string }
        code: { type: string, description: Stable machine-readable error code }
        errors:
          type: array
          items: { type: object, properties: { pointer: { type: string }, detail: { type: string } } }
  responses:
    Problem:
      description: Error
      content: { application/problem+json: { schema: { $ref: '#/components/schemas/Problem' } } }
```

## Idempotency and rate limits

```yaml
components:
  parameters:
    IdempotencyKey:
      name: Idempotency-Key
      in: header
      required: true
      schema: { type: string, maxLength: 64 }
      description: Unique key per logical operation; repeats within 24 h return the original result.
  headers:
    RetryAfter: { schema: { type: integer }, description: Seconds to wait }
    RateLimitLimit: { schema: { type: integer } }
    RateLimitRemaining: { schema: { type: integer } }
    RateLimitReset: { schema: { type: integer }, description: Seconds until the window resets }
  responses:
    TooManyRequests:
      description: Rate limited
      headers:
        Retry-After: { $ref: '#/components/headers/RetryAfter' }
      content: { application/problem+json: { schema: { $ref: '#/components/schemas/Problem' } } }
```

## Conditional requests

```yaml
parameters:
  - { name: If-None-Match, in: header, schema: { type: string } }
responses:
  '200':
    headers: { ETag: { schema: { type: string } }, Cache-Control: { schema: { type: string } } }
  '304': { description: Not modified }
# updates
  - { name: If-Match, in: header, required: true, schema: { type: string } }
  '412': { $ref: '#/components/responses/Problem' }
```

## Long-running operations

```yaml
/exports:
  post:
    operationId: createExport
    responses:
      '202':
        description: Accepted
        headers: { Location: { schema: { type: string, format: uri } } }
        content: { application/json: { schema: { $ref: '#/components/schemas/Operation' } } }
```

## Webhooks (3.1)

```yaml
webhooks:
  orderPaid:
    post:
      operationId: onOrderPaid
      parameters:
        - { name: Webhook-Signature, in: header, required: true, schema: { type: string } }
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/OrderPaidEvent' } } } }
      responses: { '2XX': { description: Received } }
```

## Security schemes

```yaml
securitySchemes:
  oauth2:
    type: oauth2
    flows:
      authorizationCode:
        authorizationUrl: https://auth.example.com/authorize
        tokenUrl: https://auth.example.com/token
        scopes: { orders:read: Read orders, orders:write: Create and change orders }
      clientCredentials:
        tokenUrl: https://auth.example.com/token
        scopes: { orders:read: Read orders }
  apiKey: { type: apiKey, in: header, name: X-API-Key }
```
