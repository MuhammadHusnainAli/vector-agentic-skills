# Scale Playbook: 1 Million Requests per Second

1M rps is 86 billion requests a day. At that rate a 1 ms CPU saving is 1,000 cores, a 1 kB smaller response is 8 Gbit/s,
and a 0.1% error rate is 1,000 failures every second. Design in this order: don't serve it, serve it from the edge, serve
it from memory, then serve it from a shard.

## 1. Traffic shape first

- Measure or estimate: peak vs average (often 2-5x), read/write ratio, cacheable share, payload sizes, client mix,
  geographic split, burst behaviour (launches, retries, batch jobs at midnight UTC).
- Run `capacity_plan.py` for the peak, then again for failure scenarios (one region down, cache cold, CDN miss storm).

## 2. Edge: the cheapest capacity

| Technique | Effect |
|-----------|--------|
| CDN caching for public GETs with `max-age` + `stale-while-revalidate` | Often 50-95% of read traffic never reaches origin |
| Request collapsing / origin shield | One origin fetch per object per POP during misses |
| Cache keys normalised (sorted query params, no tracking params) | Higher hit rates |
| `stale-if-error` | Serve stale content when origin is degraded |
| Edge rate limiting and bot filtering | Abuse never consumes origin capacity |
| TLS termination and HTTP/2, HTTP/3 at the edge | Fewer connections and handshakes to origin |

## 3. Regions and cells

- Multiple active regions, routed by latency (anycast or DNS); each region sized to absorb a failed region's share
  (`--survive-region-loss`).
- **Cell-based architecture**: split each region into independent cells (full stack: load balancer, services, caches,
  database shards), each serving a slice of customers chosen by a cell-routing key (tenant/user ID). A bad deploy or a
  poison request takes out one cell, not the service. Typical cell size: 50k-100k rps.
- Thin, highly available cell router at the front; mapping stored in a replicated config, not a database query per
  request.

## 4. Connections and protocols

- Keep-alive everywhere; HTTP/2 multiplexing between edge and origin and between services (gRPC).
- Connection pools sized from Little's law: in-flight requests = rps x latency. 100k rps x 20 ms = 2,000 concurrent
  requests per dependency per region.
- Load balancers: least-outstanding-requests (or power-of-two-choices), not round robin, to avoid slow-instance pile-ups.
- Avoid connection storms on deploys: gradual rollout, connection draining, client-side jittered reconnects.

## 5. Services

- Stateless instances; horizontal autoscaling on CPU and concurrency, with scale-up lead time covered by headroom
  (target 50-70% utilisation at peak).
- Efficient runtimes and serialisation: pre-allocated buffers, avoid reflection-heavy JSON in hot paths, consider
  binary formats (protobuf) internally.
- No synchronous fan-out per item; batch dependency calls (DataLoader pattern), parallelise independent calls with a
  deadline.
- Deadlines propagated (gRPC deadlines, timeout headers); work stops when the caller gave up.

## 6. Data

| Concern | Approach |
|---------|----------|
| Read load | App cache (Redis/Memcached) with high hit rate; request coalescing on misses; read replicas for the rest |
| Write load | Shard by a high-cardinality key (tenant, user); batch writes; queue non-urgent writes (outbox/Kafka) |
| Hot keys | Detect (top-k sampling); replicate hot items to local in-process cache with short TTL; split counters (sharded counters) |
| Sequential IDs | Avoid as shard keys (hot tail); use hashed or random-prefix keys, UUIDv7 with hash routing |
| Cross-shard queries | Avoid in request paths; build read models asynchronously |
| Consistency | Choose per endpoint: strong for money and inventory, eventual for feeds and counts |

## 7. Protect the system

- **Rate limiting** per client at the edge (token bucket), distributed with local approximation plus periodic sync.
- **Load shedding**: reject early (429/503 with Retry-After) when queue depth or latency exceeds thresholds; prioritise
  by request class (checkout over recommendations).
- **Backpressure**: bounded queues everywhere; no unbounded thread pools.
- **Retries**: only idempotent operations, exponential backoff with jitter, retry budgets (e.g. at most 10% extra load),
  retries at one layer only. At 1M rps, a retry storm doubles traffic in seconds.
- **Circuit breakers** around dependencies; fallbacks (cached or degraded responses).
- **Graceful degradation**: feature flags to turn off expensive features under load.

## 8. Payload and CPU budget

| Lever | Example saving at 1M rps |
|-------|--------------------------|
| Response 4 kB -> 2 kB (fields, compression) | 16 Gbit/s egress |
| 1 ms less CPU per request | About 1,000 cores |
| Cache hit rate 90% -> 95% | Halves database reads |
| 304 Not Modified on repeat reads | Bandwidth and serialisation |

## 9. Deploys and operations

- Progressive delivery: one cell first, then a region, then all; automated rollback on SLO burn.
- Capacity tests before peaks; game days for region and cell failure.
- Observability per cell and per endpoint: rps, error rate, p50/p99/p99.9, saturation (CPU, connections, queue depth).

## Worked numbers

`capacity_plan.py --rps 1000000 --instance-rps 4000 --p50-ms 8 --p99-ms 45 --regions 3 --survive-region-loss`:
456k rps served by the CDN, 544k reach origin, 272k per surviving region, 3 cells of about 91k each, 39 instances per
cell (351 total), about 24k requests in flight at p99, 74k DB reads/s after caching and 50k DB writes/s, which is beyond
one primary: the plan says shard writes.
