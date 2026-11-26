# Versioning Strategies

| Strategy | Example | Pros | Cons | Fits |
|----------|---------|------|------|------|
| URI major version | `/v1/orders`, `/v2/orders` | Obvious, cache-friendly, easy routing and docs | Big-bang migrations; URLs change | Public APIs with rare breaks |
| Header version | `Api-Version: 2` | Clean URLs | Invisible in links and logs; caches need `Vary` | Internal/partner APIs |
| Media type version | `Accept: application/vnd.acme.order.v2+json` | Per-resource versions | Complex for clients and tooling | Hypermedia-heavy APIs |
| Date-based with account pinning | `Stripe-Version: 2024-06-20`; account pinned to its first version | Small frequent changes; clients upgrade when ready | Needs a transformation layer and discipline | Large public APIs with many small changes |
| No versioning (evolve compatibly only) | GraphQL-style | No version maintenance | Requires strict compatibility discipline | Internal APIs, GraphQL |

## Date-based versions with transformers (Stripe-style)

- Each breaking change ships as a small dated version change.
- The core API speaks the latest version; requests and responses pass through a chain of transformers that downgrade the
  response (and upgrade the request) to the client's pinned version.
- Accounts are pinned to the version current when they started; they can upgrade per request with a header to test, then
  move their default.
- Benefit: many small breaks without forking the codebase. Cost: transformer chain maintenance and tests per version.

## URI versions done well

- Major version only (`/v1`), never minor.
- New major version shares the domain model; v1 becomes a thin adapter over v2 logic where possible.
- Both versions documented, with a migration guide mapping every change.
- Load balancer or gateway routes by prefix; separate SLOs and metrics per version.

## Choosing

| Question | Lean towards |
|----------|-------------|
| Many external developers, infrequent large changes | URI major versions |
| Many external developers, frequent small improvements | Date-based with pinning |
| Few known clients (internal, partners) | Compatible evolution + header version when needed |
| Mobile apps that can't be force-updated | Long support windows; compatible evolution; feature flags |

Whatever you pick: write the versioning and deprecation policy down and publish it before v1 ships.
