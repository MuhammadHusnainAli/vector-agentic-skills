# API Naming Style Guide (template)

Adopt, adjust, publish. Every rule has a reason so reviewers can apply it to new cases.

## 1. Resources

- **Plural nouns for collections**: `/invoices`. Reason: a collection holds many; consistent pluralisation means nobody
  guesses.
- **kebab-case segments**: `/payment-methods`. Reason: URLs are case-sensitive and kebab is the web norm; avoid camelCase
  and underscores in paths.
- **Name resources after the domain, not the implementation**: `/subscriptions`, not `/sub_tbl` or `/billing-service`.
- **Singleton sub-resources are singular**: `/users/{userId}/profile`, `/me`.

## 2. Identifiers

- Path parameter named after the resource: `{invoiceId}`; identical everywhere the resource appears.
- Opaque, prefixed IDs (`inv_...`) so humans and logs can tell types apart and nobody parses them.

## 3. Actions that aren't CRUD

- Prefer modelling state: `POST /orders/{orderId}/cancellation` (creates a cancellation) or a custom method
  `POST /orders/{orderId}:cancel` (Google AIP-136 style). Pick one style per API.
- Never `GET` for actions; never verbs as collections (`/createOrder`).

## 4. Query parameters

- Filters use field names: `?status=paid&customerId=cus_123`.
- Ranges with suffixes: `createdAfter`, `createdBefore`, `amountMin`, `amountMax`.
- Pagination: `cursor`, `limit` (or `pageToken`, `pageSize`), the same across all endpoints.
- Sorting: `sort=-createdAt,id` (minus for descending), only on indexed fields.
- Expansion and fields: `expand=customer`, `fields=id,status`.

## 5. JSON properties

- One casing across the API (camelCase recommended for JSON APIs consumed by JavaScript; snake_case is fine if already
  established; never mixed).
- No abbreviations unless universal (`id`, `url`); `quantity` not `qty`.
- Booleans as adjectives or `is`/`has`: `active`, `isPrimary`, `hasMore`. Avoid negatives (`notVisible`).
- Collections as plurals: `lineItems`.
- Timestamps `...At` (RFC 3339, UTC); dates `...Date` (`YYYY-MM-DD`); durations with units (`timeoutSeconds`).
- Money: `amount` in minor units + `currency` (ISO 4217); never floats.
- Enums: lowercase snake strings, documented as open (new values may appear).
- Units in names where ambiguous: `weightGrams`, `sizeBytes`.

## 6. Headers

- Standard headers first (`Idempotency-Key`, `RateLimit-*`, `Retry-After`, `ETag`).
- Custom headers without the deprecated `X-` prefix where possible, product-prefixed if needed (`Acme-Request-Id`).

## 7. Versions

- `/v1` prefix (or the chosen strategy), the same form everywhere.

## Review questions for new endpoints

1. Is the resource a plural noun in kebab-case, named after the domain?
2. Are path parameters named like elsewhere?
3. Do query parameters and fields use the API-wide casing and existing names for the same concepts?
4. Is any action modelled as a verb in the path?
5. Does `path_naming_lint.py` pass?
