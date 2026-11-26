---
name: rest-api-endpoint-designer
description: "Design REST endpoints that are correct for clients and hold up at extreme scale (hundreds of thousands to a million requests per second): resource modelling, URIs, methods and their safety and idempotency, request and response shapes, filtering, sorting, sparse fieldsets and expansion, bulk and batch endpoints, long-running operations (202 + status resource), conditional requests (ETag, If-None-Match, If-Match), caching headers for CDNs, compression, idempotency keys, rate-limit headers, and the scale architecture behind them: edge caching, regions and cells, stateless services, sharding by a key, hot keys, load shedding and retry budgets. Ships capacity_plan.py, which turns a peak request rate, latency, cache hit rates and payload sizes into CDN offload, per-region and per-cell traffic, instance counts with headroom, requests in flight (Little's law), database read/write load and bandwidth,. Use when designing or reviewing API endpoints, or planning an API for high traffic."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# REST API Endpoint Designer

An endpoint is a contract with every client that will ever call it, and at a million requests per second every design
choice is multiplied a million times a second. An unbounded list endpoint, a write with no idempotency key, a response
that can't be cached, or a handler that fans out to five services decides your hardware bill and your outage pattern long
before anyone tunes code. This skill designs endpoints that are simple for clients, and sizes the system behind them with
real arithmetic instead of hope.

## Trigger Conditions

Activate this skill when the user:
- Designs new REST endpoints or a resource model, or reviews existing ones
- Plans an API for high traffic, or asks how to reach 100k-1M+ requests per second
- Needs caching, conditional requests, bulk operations or long-running operation patterns
- Asks how many servers, regions or database shards an API needs

Spec writing: `openapi-spec-writer`. Pagination: `api-pagination-designer`. Errors:
`api-error-response-designer`. Status codes: `http-status-code-advisor`. Versioning:
`rest-api-versioning-strategist`.

## Workflow

```
1. RESOURCES -> nouns, relationships, ownership; which are read-heavy, write-heavy, hot (references/endpoint-design-rules.md)
2. OPERATIONS-> method per operation; safe/idempotent; bulk, async, conditional variants
3. SHAPES    -> request/response schemas, filtering, sorting, fields, expansion, limits on every list and string
4. CACHING   -> Cache-Control, ETag, Vary per endpoint; what the CDN can serve (references/scale-playbook-1m-rps.md)
5. CAPACITY  -> python scripts/capacity_plan.py --rps <peak> --instance-rps <measured> ... (fix every PLAN warning)
6. RESILIENCE-> timeouts, retries with budgets, idempotency keys, rate limits, load shedding, cells
7. VERIFY    -> load test to the plan with production-like data; SLOs and dashboards (references/load-testing-and-slos.md)
```

## Rules for Endpoints That Scale

| Rule | Why at scale |
|------|--------------|
| Every list endpoint is paginated (cursor) with a max page size | One unbounded query at 1M rps takes down the database |
| Every request field has a size limit; every response has a size budget | Bandwidth and serialisation cost scale with bytes |
| Reads are cacheable by default (Cache-Control + ETag); per-user data marked private | The CDN is the cheapest capacity you'll ever buy |
| Writes accept an Idempotency-Key | Retries at scale are constant; duplicates become money and support load |
| Handlers do O(1) dependency calls; no per-item fan-out | Fan-out multiplies load and latency tail |
| Long work returns 202 + an operation resource | Holding connections for seconds exhausts concurrency |
| Stateless services; state in stores sharded by a key | Horizontal scale and cell isolation need it |
| Rate limits per client with standard headers | Protects capacity and tells clients how to behave |
| Timeouts everywhere, shorter than the caller's | Prevents request pile-ups during slowdowns |

## Plan Warnings (capacity_plan.py)

| Code | Meaning |
|------|---------|
| PLAN001 | Target utilisation above 75%: no headroom for spikes and failover |
| PLAN002 | Database writes beyond one primary: shard, batch or queue |
| PLAN003 | Database reads beyond a replica set: raise cache hit rate, replicas, shards |
| PLAN004 | Service p99 exceeds the end-to-end budget |
| PLAN005 | Too many instances per cell: smaller cells or faster instances |
| PLAN006 | Large responses: bandwidth explodes at scale |
| PLAN007 | CDN hit rate with nothing cacheable |
| PLAN008 | Unrealistically low CPU cost per request |

## Scripts

```bash
python scripts/capacity_plan.py --rps 1000000 --instance-rps 4000 --p50-ms 8 --p99-ms 45 --regions 3 --survive-region-loss
```
Per-instance throughput from a load test (`--instance-rps`) or CPU cost (`--cpu-ms`, `--cores`). Tunables: write ratio,
cacheable share and CDN hit rate, app-cache hit rate, DB queries per miss, DB limits, cell size, target utilisation, request
and response sizes. `--json` for machine output. Standard library only.
Exit codes: 0 plan, 1 plan with warnings, 2 bad arguments.

## Output

1. Resource model and endpoint table: method, path, purpose, idempotency, cacheability, limits, auth
2. Request/response schemas with examples
3. Capacity plan with the numbers and the fixes for each warning
4. Resilience settings: timeouts, retries, rate limits, load shedding
5. Load-test plan and SLOs

## Additional Resources

| File | Content |
|------|---------|
| [endpoint-design-rules.md](references/endpoint-design-rules.md) | Resources, URIs, methods, idempotency, filtering, fields, bulk, async operations, conditional requests, headers |
| [scale-playbook-1m-rps.md](references/scale-playbook-1m-rps.md) | Architecture for 1M rps: edge, regions, cells, connections, sharding, hot keys, caching, backpressure, cost |
| [load-testing-and-slos.md](references/load-testing-and-slos.md) | Latency budgets, SLOs, load test design, finding per-instance capacity, capacity reviews |
