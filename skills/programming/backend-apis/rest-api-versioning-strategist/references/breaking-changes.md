# Breaking Changes

## Schema-level breaks

| Change | Breaking? | Why |
|--------|-----------|-----|
| Remove endpoint, method or response field | Yes | Clients call or read it |
| Rename field, parameter or operationId | Yes | Same as remove + add; SDK methods rename |
| Change type (int -> string, object -> array) | Yes | Parsers fail |
| Add required input (field, parameter, header) | Yes | Existing requests become invalid |
| Make optional input required | Yes | Same |
| Tighten validation (shorter max, fewer enum values, new pattern) | Yes | Previously valid input rejected |
| Remove a success status code or change 200 -> 201 | Yes for strict clients | Clients branch on status |
| Change error codes or error shape | Yes | Clients branch on error codes |
| New required scope or auth method | Yes | Existing tokens fail |
| Add response field | No (with tolerant readers) | |
| Add optional input | No | |
| Add enum value in responses | Potentially | Strict deserialisers (generated enums) fail |
| Loosen validation | No | |
| Add endpoint | No | |

## Behavioural breaks (schema unchanged)

- Default page size, sort order or default filter changed.
- Rate limits lowered; timeouts shortened.
- Side effects changed (now sends an email; no longer creates an invoice).
- Eventual vs strong consistency changed for reads after writes.
- Different meaning of a field (amount now includes tax).
- Error now returned where success was (or the reverse).
These need versioning or opt-in just like schema breaks.

## Expand and contract

1. **Expand:** add the new field/endpoint alongside the old; write both; read either.
2. **Migrate:** clients move to the new shape; measure usage of the old.
3. **Contract:** remove the old after deprecation (new major version, or after sunset for internal APIs).

Example: `name` -> `givenName` + `familyName`. Add both new fields, keep returning `name`, accept either on input,
deprecate `name`, remove in v2.

## Tolerant reader (client rules to publish)

- Ignore unknown response fields.
- Treat unknown enum values as a known fallback ("unknown") instead of crashing.
- Don't depend on field order or undocumented fields.
- Follow redirects and `Location` headers; respect `Retry-After`.
- Generated SDKs: configure enums as open (string with known values) where the generator allows.
