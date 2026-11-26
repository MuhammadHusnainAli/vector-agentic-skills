# Load Testing and SLOs

## Latency budget

Allocate the end-to-end p99 budget across hops before writing code:

| Hop | Budget (example, 150 ms p99) |
|-----|------------------------------|
| Client to edge (network, TLS) | 40 ms |
| Edge to origin | 15 ms |
| Load balancer and service | 45 ms |
| Cache and database | 30 ms |
| Downstream services | 20 ms |

Tail latency compounds: a request touching 10 services each with 1% chance of a slow response hits at least one slow
response about 10% of the time. Hedge or parallelise carefully, and keep the call graph shallow.

## SLOs

| SLI | Example SLO |
|-----|-------------|
| Availability (non-5xx share of valid requests) | 99.95% over 30 days |
| Latency | 99% of requests under 150 ms at the edge |
| Freshness (for cached data) | 99% of reads at most 60 s stale |

Alert on error-budget burn rate (fast and slow windows), not on single spikes.

## Finding per-instance capacity

1. Production-like data volume and cache state; realistic request mix (not one endpoint).
2. Open-model load generator (constant arrival rate: k6 `constant-arrival-rate`, Gatling, wrk2, Vegeta) so latency isn't
   hidden by coordinated omission.
3. Increase rate in steps; record throughput, p50/p99/p99.9, CPU, memory, GC, connections, errors.
4. Capacity = highest rate where p99 stays within budget and errors under threshold. Plan at 50-70% of it
   (`--instance-rps` x `--target-util`).
5. Repeat after major changes; track capacity per release.

## Test scenarios

| Scenario | Purpose |
|----------|---------|
| Steady peak | Validate the plan |
| Spike (2-3x in a minute) | Autoscaling lead time, load shedding |
| Soak (hours) | Memory leaks, connection churn |
| Cache cold start | Origin and database survive a flushed cache |
| Dependency slow (inject latency) | Timeouts, circuit breakers, pool exhaustion |
| Region or cell failure | Survivors carry the load |

## Capacity review (before launches and quarterly)

- Traffic forecast vs plan; headroom per region and per cell.
- Top endpoints by CPU and by bytes; the cheapest wins.
- Database load vs limits; shard growth plan.
- Results of the last game day.
