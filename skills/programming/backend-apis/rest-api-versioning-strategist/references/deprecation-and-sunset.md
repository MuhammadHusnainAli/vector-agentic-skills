# Deprecation and Sunset

## Headers

```
Deprecation: @1767225600                 (RFC 9745: date it was deprecated, as a Unix timestamp)
Sunset: Wed, 30 Jun 2027 00:00:00 GMT    (RFC 8594: when it stops working)
Link: <https://developer.example.com/migrate/v2>; rel="deprecation"; type="text/html"
```
Send them on every response from deprecated endpoints or versions. SDKs can log warnings when they see them.

## Timelines (typical)

| Audience | Minimum notice |
|----------|----------------|
| Public API, many developers | 12 months (longer for mobile apps and enterprise customers) |
| Partner API with contracts | Per contract, often 6-12 months |
| Internal API | 1-3 months, with usage data |

## Process

1. **Announce**: changelog, docs banner, email to registered developers, dashboard notice; migration guide with
   before/after examples.
2. **Measure**: usage of deprecated endpoints per client/API key; reach out to the top users directly.
3. **Remind**: at 6, 3 and 1 month(s); in API responses (headers) and in the developer dashboard.
4. **Brownouts**: scheduled short outages of the deprecated feature (minutes, then hours) announced in advance, so
   forgotten integrations surface before the final date.
5. **Sunset**: return `410 Gone` with a problem body linking the migration guide; keep that response for months.
6. **Clean up**: remove code paths, docs, SDK methods (major SDK version).

## Telemetry

- Log API version and deprecated-feature usage per request with the client ID.
- Dashboard: calls per day per client to each deprecated item; trend to zero.
- Don't sunset while a large customer still depends on it without a direct conversation.

## CI gate

```bash
python scripts/openapi_diff.py published/openapi.yaml openapi.yaml || {
  echo "Breaking change: bump the major version or make it compatible"; exit 1; }
```
Allow an explicit override label for intentional breaking changes in a new version.
