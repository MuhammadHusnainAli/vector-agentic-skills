---
name: grpc-service-scaffolder
description: "Scaffold production-ready gRPC services in Go, Java/Kotlin, Python, Node.js/TypeScript, .NET and Rust: project layout with generated code from Buf, server bootstrap, interceptors (authentication, logging, metrics, tracing with OpenTelemetry, panic recovery, validation with protovalidate), deadlines and cancellation, the standard health checking protocol and reflection, graceful shutdown with draining, keepalive and max message settings, error mapping to canonical status codes with rich details, client channels with retries and hedging via service config, load balancing for long-lived HTTP/2 connections (L7 proxies, xDS, client-side), browser access with gRPC-Web or Connect, REST transcoding, and testing with in-process servers. Reviews services for missing deadlines, no health checks, L4 load balancing that pins traffic, unbounded streams, per-call channel creation and leaked internal errors. Use when creating, hardening or reviewing a gRPC service or client."
metadata:
  category: programming
  subcategory: backend-apis
  version: "1.0.0"
---

# gRPC Service Scaffolder

The `.proto` file gives you generated stubs. Production needs everything around them: interceptors for auth and
observability, deadlines that propagate, health checks the platform understands, shutdown that drains streams, and load
balancing that works with long-lived HTTP/2 connections. The last one is the classic surprise: behind a plain L4 load
balancer, every client pins to one backend. This skill scaffolds the service and client with those pieces in place, in
the team's language.

## Trigger Conditions

Activate this skill when the user:
- Creates a new gRPC service or client in any major language
- Hardens an existing service for production (interceptors, health, shutdown, observability)
- Sees uneven load across gRPC backends, deadline errors or stream leaks
- Needs browser or REST access to gRPC services

Proto design: `grpc-protobuf-definition-writer`. Breaking changes: `protobuf-schema-evolution-checker`. Retries:
`retry-backoff-policy-designer`.

## Workflow

```
1. GENERATE  -> buf generate into the language package (references/server-skeletons.md)
2. SERVER    -> service implementation delegating to domain code; validation at the edge
3. CHAIN     -> interceptors: recovery -> tracing -> metrics -> logging -> auth -> validation
4. LIFECYCLE -> health service, reflection (non-prod or authenticated), graceful shutdown with drain timeout
5. LIMITS    -> deadlines required, max message sizes, keepalive, max concurrent streams
6. CLIENT    -> one long-lived channel per target, service config with retry policy, deadlines per call
7. LB        -> L7 (Envoy, service mesh) or client-side LB with DNS/xDS (references/production-grpc.md)
8. TEST      -> in-process server tests; contract tests against the proto
```

## Rules

| Rule | Why |
|------|-----|
| Every call has a deadline; servers check `ctx` and propagate it | Without deadlines, slow dependencies pile up requests forever |
| Reuse channels; never create one per call | Channel creation is a TCP + TLS + HTTP/2 handshake |
| L7 or client-side load balancing | HTTP/2 multiplexes many calls over one connection; L4 balancers pin all of them to one backend |
| Implement `grpc.health.v1.Health` | Kubernetes probes, load balancers and meshes use it |
| Graceful shutdown: stop accepting, finish in-flight, then force | Deploys without errors |
| Map errors to canonical codes; never return internal messages | Clients and retries depend on codes |
| Retry only idempotent methods, with budgets | Retry storms multiply load |

## Review Codes

| Code | Severity | Check |
|------|----------|-------|
| GS001 | high | No deadlines on client calls, or server ignores cancellation |
| GS002 | high | Channel created per request |
| GS003 | high | Behind an L4 load balancer without client-side balancing (traffic pinned) |
| GS004 | medium | No health service; no graceful shutdown |
| GS005 | medium | Panics/exceptions not recovered into INTERNAL with logging |
| GS006 | medium | Internal error text returned in status messages |
| GS007 | medium | Unbounded streams (no flow control, no max duration, no per-connection limit) |
| GS008 | low | Reflection enabled publicly in production |

## Output

Project skeleton for the chosen language: server main, service implementation, interceptor chain, health and shutdown,
client factory with service config, Dockerfile/Kubernetes probes, and tests.

## Additional Resources

| File | Content |
|------|---------|
| [server-skeletons.md](references/server-skeletons.md) | Go, Python, Node/Connect, Java, .NET and Rust skeletons with interceptors, health and shutdown |
| [production-grpc.md](references/production-grpc.md) | Load balancing, keepalive, service config retries and hedging, errors, gRPC-Web/Connect, transcoding, scale settings |
