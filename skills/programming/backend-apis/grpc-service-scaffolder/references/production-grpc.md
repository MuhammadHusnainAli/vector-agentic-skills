# Production gRPC

## Load balancing

gRPC multiplexes calls over long-lived HTTP/2 connections. An L4 (TCP) load balancer balances connections, not calls, so a
client with one connection sends everything to one backend.

| Option | How | Fits |
|--------|-----|------|
| L7 proxy | Envoy, NGINX (grpc_pass), cloud L7 LBs balance per request | Edge, mixed clients |
| Service mesh | Sidecars (Istio/Linkerd) or proxyless (gRPC xDS) balance per request | Many internal services |
| Client-side | `dns:///orders.internal` + `round_robin` policy, Kubernetes headless service | Simple internal setups |
| xDS | Control plane pushes endpoints and policies to gRPC clients | Large fleets, advanced routing |

Server-side `MaxConnectionAge` (with grace) forces periodic reconnects so traffic spreads to new instances.

## Keepalive

- Client: keepalive time 30-60 s for long-lived idle connections through NATs/firewalls; don't ping more often than the
  server's enforcement policy allows (servers send GOAWAY "too_many_pings").
- Server: `MaxConnectionIdle`, `MaxConnectionAge` + grace; enforcement `MinTime`.

## Service config: retries and hedging

```json
{
  "loadBalancingConfig": [{ "round_robin": {} }],
  "methodConfig": [{
    "name": [{ "service": "acme.orders.v1.OrderService", "method": "GetOrder" }],
    "timeout": "0.5s",
    "retryPolicy": {
      "maxAttempts": 3, "initialBackoff": "0.05s", "maxBackoff": "1s", "backoffMultiplier": 2,
      "retryableStatusCodes": ["UNAVAILABLE"]
    }
  }],
  "retryThrottling": { "maxTokens": 100, "tokenRatio": 0.1 }
}
```
- Retry only idempotent methods; `retryThrottling` caps retries when failures are widespread.
- Hedging (`hedgingPolicy`) sends a second attempt after a delay for latency-sensitive idempotent reads; use carefully
  (extra load).

## Status codes

| Situation | Code | Retry? |
|-----------|------|--------|
| Invalid input | INVALID_ARGUMENT | No |
| Not found | NOT_FOUND | No |
| Already exists | ALREADY_EXISTS | No |
| State precondition | FAILED_PRECONDITION | No (fix state) |
| Optimistic concurrency conflict | ABORTED | Yes (retry the read-modify-write) |
| Rate limit / quota | RESOURCE_EXHAUSTED | After delay |
| No auth / bad auth | UNAUTHENTICATED / PERMISSION_DENIED | No |
| Transient unavailability | UNAVAILABLE | Yes |
| Deadline passed | DEADLINE_EXCEEDED | Maybe (operation may have completed) |
| Bug | INTERNAL | No (unless idempotent and known transient) |

## Browsers and REST

- gRPC-Web via Envoy or Connect; Connect protocol supports plain HTTP/JSON from browsers with the same handlers.
- REST transcoding: `google.api.http` annotations + grpc-gateway or Envoy's gRPC-JSON transcoder for public REST APIs.

## Scale settings

- `MaxConcurrentStreams` per connection (HTTP/2 default often 100): clients need several connections (channel pool or
  subchannels) for very high per-client throughput.
- Message size limits (default 4 MB receive); large payloads via streaming chunks or object storage.
- Compression (gzip) for large messages only; it costs CPU at high RPS.
- Streams: per-connection stream limits, max stream duration, server-side idle timeouts, resumable streams.
- Observability: OpenTelemetry gRPC instrumentation; metrics per method and status code; latency histograms.
