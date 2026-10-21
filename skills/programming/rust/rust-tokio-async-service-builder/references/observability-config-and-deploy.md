# Observability, Configuration and Deployment

tracing setup, request spans, OpenTelemetry, tokio-console, configuration loading, container images and
performance habits for Tokio services.

## Contents

- [tracing basics](#tracing-basics)
- [Subscriber setup](#subscriber-setup)
- [#[instrument] and spans across await](#instrument-and-spans-across-await)
- [HTTP request spans with TraceLayer](#http-request-spans-with-tracelayer)
- [Metrics](#metrics)
- [OpenTelemetry](#opentelemetry)
- [tokio-console](#tokio-console)
- [Configuration](#configuration)
- [Dockerfile: cargo-chef + distroless](#dockerfile-cargo-chef--distroless)
- [Kubernetes probes and shutdown](#kubernetes-probes-and-shutdown)
- [Performance checklist](#performance-checklist)

## tracing basics

- `tracing` is the instrumentation API (spans, events, fields); `tracing-subscriber` decides what is
  recorded and where it goes. Libraries (tokio, hyper, tower-http, sqlx, reqwest) emit `tracing` events.
- Events: `tracing::info!(order_id = id, sku = %sku, "order created")`. `%` uses `Display`, `?` uses `Debug`.
  Use fields, not formatted strings, so logs stay queryable.
- Spans give context to every event inside them (request id, user, order). In async code, attach spans to
  futures (`.instrument(span)` / `#[instrument]`), never hold `span.enter()` across `.await`.

## Subscriber setup

```toml
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }
```

```rust
use tracing_subscriber::{EnvFilter, fmt, layer::SubscriberExt, util::SubscriberInitExt};

pub fn init_tracing() {
    let filter = EnvFilter::try_from_default_env() // RUST_LOG=info,my_service=debug,tower_http=debug,sqlx=warn
        .unwrap_or_else(|_| EnvFilter::new("info,tower_http=info,sqlx=warn"));
    let json = std::env::var("LOG_FORMAT").is_ok_and(|v| v == "json");
    let registry = tracing_subscriber::registry().with(filter);
    if json {
        registry
            .with(fmt::layer().json().with_current_span(true).with_span_list(false))
            .init();
    } else {
        registry.with(fmt::layer().with_target(false)).init();
    }
}
```

- `EnvFilter` directive syntax: `level`, `target=level`, `target[span{field=value}]=level`. Targets are module
  paths with `::` (crate names use `_`, not `-`).
- JSON in production (one object per line for the log pipeline), pretty/compact locally.
- `tracing-log` bridging is enabled by default in `tracing-subscriber`, so crates using `log` show up too.
- Non-blocking file/stdout writer: `tracing-appender::non_blocking(std::io::stdout())` returns a writer and a
  guard; keep the guard alive in `main` or buffered logs are lost at exit.

## #[instrument] and spans across await

```rust,ignore
use tracing::instrument;

#[instrument(skip(state, body), fields(tenant = %tenant, order_id))]
async fn create_order(state: &AppState, tenant: String, body: NewOrder) -> Result<Order, AppError> {
    let order = state.repo.insert(&tenant, &body).await?;
    tracing::Span::current().record("order_id", order.id); // fill a declared-empty field later
    Ok(order)
}

#[instrument(level = "debug", skip_all, err)] // err: record Err(e) as an error event (needs Display)
async fn charge(gateway: &Gateway, amount_cents: i64) -> Result<(), PaymentError> {
    gateway.charge(amount_cents).await
}
```

- `skip(..)`/`skip_all` for large or secret arguments; every non-skipped argument must implement `Debug`.
- `ret` records the return value, `err` records errors; `fields(..)` adds computed fields.
- Spawned tasks do **not** inherit the current span automatically: `tokio::spawn(fut.in_current_span())`
  (`tracing::Instrument`) or create a span explicitly.

## HTTP request spans with TraceLayer

```rust
use std::time::Duration;
use axum::{extract::{MatchedPath, Request}, response::Response};
use tower_http::trace::TraceLayer;
use tracing::Span;

pub fn trace_layer() -> TraceLayer<
    tower_http::classify::SharedClassifier<tower_http::classify::ServerErrorsAsFailures>,
    impl Fn(&Request) -> Span + Clone,
    tower_http::trace::DefaultOnRequest,
    impl Fn(&Response, Duration, &Span) + Clone,
> {
    TraceLayer::new_for_http()
        .make_span_with(|req: &Request| {
            let route = req.extensions().get::<MatchedPath>().map(|p| p.as_str().to_owned());
            let request_id = req.headers().get("x-request-id").and_then(|v| v.to_str().ok()).unwrap_or("-");
            tracing::info_span!(
                "http",
                method = %req.method(),
                route = route.as_deref().unwrap_or("unmatched"), // low-cardinality: "/orders/{id}"
                request_id,
                status = tracing::field::Empty,
            )
        })
        .on_response(|res: &Response, latency: Duration, span: &Span| {
            span.record("status", res.status().as_u16());
            tracing::info!(latency_ms = latency.as_millis() as u64, "response");
        })
}
```

The explicit return type is verbose; in practice build the layer inline in your router function. Use the
`MatchedPath` route template (not the raw URI) as the span/metric label to avoid unbounded cardinality.
`MatchedPath` is only available when the layer is applied with `Router::layer` (inside routing), not around
the whole service.

## Metrics

- `metrics` + `metrics-exporter-prometheus` (a `/metrics` endpoint) or OpenTelemetry metrics.
- RED per route: request count, error count (5xx), latency histogram, labelled by matched route and method.
- Saturation gauges: in-flight requests, `Semaphore::available_permits()`, channel `capacity()`, sqlx
  `pool.size()` and `pool.num_idle()`, blocking-pool queue (tokio runtime metrics).
- Tokio runtime metrics: `tokio::runtime::Handle::current().metrics()` exposes worker count, alive tasks,
  global queue depth on stable; more detailed per-worker metrics (busy duration, steal counts, poll counts)
  need `--cfg tokio_unstable`. `tokio-metrics` crate adds task-level instrumentation (`TaskMonitor`).

## OpenTelemetry

Export spans to an OTLP collector (Jaeger, Tempo, Honeycomb, Datadog agent) through `tracing-opentelemetry`.
The crates are `opentelemetry`, `opentelemetry_sdk`, `opentelemetry-otlp` and `tracing-opentelemetry`; they
release in lockstep and their builder APIs change between minor versions, so pin a matching set (the
`tracing-opentelemetry` README lists compatible versions) and copy the init code from that version's docs.
The shape is always:

```text
1. Build an OTLP span exporter (tonic/gRPC to :4317 or HTTP to :4318).
2. Build an SdkTracerProvider with a batch processor and a Resource { service.name, service.version, env }.
3. tracer = provider.tracer("my-service")
4. registry().with(EnvFilter).with(fmt::layer()).with(tracing_opentelemetry::layer().with_tracer(tracer)).init()
5. Propagate context: extract W3C `traceparent` from incoming headers into the request span; inject it into
   outgoing reqwest calls (a reqwest middleware or manual header injection).
6. On shutdown: provider.shutdown() so buffered spans are flushed.
```

Configure with the standard env vars where supported (`OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`,
`OTEL_TRACES_SAMPLER`). Sample in production (parent-based ratio) and keep high-cardinality data in span
attributes, not span names.

## tokio-console

A `top`-like view of every task: busy time, idle time, wakeups, polls, and warnings for tasks that are never
woken or poll for too long (blocking).

```toml
[dependencies]
console-subscriber = "0.4"
tokio = { version = "1", features = ["full", "tracing"] }
```

```rust,ignore
fn main() {
    console_subscriber::init(); // instead of your normal subscriber, or add console_subscriber::spawn() as a layer
    // build the runtime / #[tokio::main] as usual
}
```

```bash
RUSTFLAGS="--cfg tokio_unstable" cargo run      # instrumentation requires tokio_unstable
cargo install --locked tokio-console
tokio-console                                    # connects to 127.0.0.1:6669
```

Reading it:
- A task with high **busy** time and few polls is blocking the worker (a sync call or CPU loop): move it to
  `spawn_blocking`.
- Many tasks **idle** forever, count growing: leaked/detached tasks waiting on something that never happens.
- "lost waker" warnings: a hand-written future returned `Pending` without arranging a wakeup.

Check the `console-subscriber` version against your tokio version; build the instrumented binary only for
debugging or staging (it has overhead).

## Configuration

Order of precedence: defaults < config file < environment < CLI flags. Parse once at startup into a typed
struct, validate, fail fast with a clear message, and put it in `AppState`.

Plain environment variables (no extra crate):

```rust
use std::{net::SocketAddr, time::Duration};

#[derive(Clone, Debug)]
pub struct Config {
    pub addr: SocketAddr,
    pub database_url: String,
    pub request_timeout: Duration,
    pub max_db_connections: u32,
}

impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        use anyhow::Context;
        let var = |k: &str| std::env::var(k).with_context(|| format!("missing env var {k}"));
        Ok(Self {
            addr: std::env::var("ADDR").unwrap_or_else(|_| "0.0.0.0:3000".into()).parse()?,
            database_url: var("DATABASE_URL")?,
            request_timeout: Duration::from_secs(
                std::env::var("REQUEST_TIMEOUT_SECS").ok().and_then(|v| v.parse().ok()).unwrap_or(10),
            ),
            max_db_connections: std::env::var("MAX_DB_CONNECTIONS").ok().and_then(|v| v.parse().ok()).unwrap_or(20),
        })
    }
}
```

figment (`figment = { version = "0.10", features = ["toml", "env"] }`):

```rust,ignore
use figment::{Figment, providers::{Env, Format, Serialized, Toml}};

#[derive(Debug, serde::Deserialize, serde::Serialize)]
pub struct Settings {
    pub port: u16,
    pub database_url: String,
    pub log_format: String,
}

impl Default for Settings {
    fn default() -> Self {
        Self { port: 3000, database_url: String::new(), log_format: "text".into() }
    }
}

pub fn load() -> Result<Settings, figment::Error> {
    Figment::from(Serialized::defaults(Settings::default()))
        .merge(Toml::file("App.toml"))   // optional: missing file is ignored
        .merge(Env::prefixed("APP_"))    // APP_PORT=8080, APP_DATABASE_URL=...
        .extract()
}
```

config crate (`config = "0.15"`):

```rust,ignore
#[derive(Debug, serde::Deserialize)]
pub struct Settings {
    pub port: u16,
    pub database: Database,
}

#[derive(Debug, serde::Deserialize)]
pub struct Database {
    pub url: String,
    pub max_connections: u32,
}

pub fn load() -> Result<Settings, config::ConfigError> {
    config::Config::builder()
        .set_default("port", 3000)?
        .add_source(config::File::with_name("config/default").required(false))
        .add_source(config::Environment::with_prefix("APP").separator("__")) // APP_DATABASE__URL
        .build()?
        .try_deserialize()
}
```

- Secrets come from the environment or a mounted file, never from the image; wrap them (`secrecy::SecretString`)
  so `Debug` does not print them.
- Hot reload: publish new values through `tokio::sync::watch`; most settings (pool sizes, bind address)
  need a restart anyway, keep reload for flags and limits.

## Dockerfile: cargo-chef + distroless

```dockerfile
# syntax=docker/dockerfile:1
FROM lukemathwalker/cargo-chef:latest-rust-1 AS chef
WORKDIR /app

FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
# Dependencies only: this layer is cached until Cargo.toml/Cargo.lock change
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
ENV SQLX_OFFLINE=true
RUN cargo build --release --locked --bin orders-api

FROM gcr.io/distroless/cc-debian12:nonroot AS runtime
COPY --from=builder /app/target/release/orders-api /usr/local/bin/orders-api
EXPOSE 3000
ENTRYPOINT ["/usr/local/bin/orders-api"]
```

- `cc-debian12` contains glibc and libgcc (needed by a normal Rust binary) but no shell and no OpenSSL; use
  rustls in reqwest/sqlx, or switch to a debian-slim runtime with `libssl3` and `ca-certificates`.
- rustls with `webpki-roots` embeds CA roots; with native roots the image needs `/etc/ssl/certs` (distroless
  cc includes ca-certificates).
- Fully static alternative: build for `x86_64-unknown-linux-musl` and use `gcr.io/distroless/static` or
  `scratch`; if you do, consider a different global allocator (musl's malloc is slow under contention).
- `SQLX_OFFLINE=true` + committed `.sqlx/` lets `query!` macros compile without a database.
- The process is PID 1: it receives SIGTERM directly, which is what the shutdown handler expects. No shell
  wrapper (`sh -c`) that would swallow signals.

## Kubernetes probes and shutdown

```yaml
readinessProbe:
  httpGet: { path: /readyz, port: 3000 }
  periodSeconds: 5
  failureThreshold: 2
livenessProbe:
  httpGet: { path: /healthz, port: 3000 }
  periodSeconds: 10
  failureThreshold: 3
lifecycle:
  preStop:
    exec: { command: ["/usr/local/bin/orders-api", "--sleep", "5"] }  # distroless has no `sleep`; or use the in-app delay
terminationGracePeriodSeconds: 30
```

Either implement the readiness delay inside the app (flip readiness, sleep 5 s, then start draining, as in
[runtime-tasks-and-shutdown.md](runtime-tasks-and-shutdown.md)) or give the binary a tiny `--sleep N` mode
for `preStop`; recent Kubernetes versions also support a native `sleep` preStop action.

## Performance checklist

- [ ] One `reqwest::Client`, one `PgPool`, built at startup; no per-request TLS handshakes
- [ ] No blocking calls on workers (tokio-console busy times, `blocking_in_async`); CPU work on rayon/`spawn_blocking`
- [ ] Bodies as `Bytes` / streams, not `Vec<u8>` copies; `Bytes::clone` is a refcount bump
- [ ] Serialize with `serde_json::to_writer` into a pre-sized `Vec`, or return `Json(value)` directly; avoid
      `to_string` + copy
- [ ] Buffered I/O: `BufReader`/`BufWriter` with 8-64 KiB buffers on raw sockets and files; flush `BufWriter`
- [ ] `TCP_NODELAY` for request/response protocols with small writes
- [ ] Release profile: `lto = "thin"`, `codegen-units = 1`; consider `mimalloc`/`jemalloc` for allocation-heavy loads
- [ ] Bounded everything: channels, semaphores, body limits, timeouts; load shed instead of queueing forever
- [ ] Avoid `Arc<Mutex<..>>` hot spots: shard, use atomics, or an actor; measure contention before changing
- [ ] Logging: no `info!` per item in hot loops; use `debug!`/`trace!` and the filter; JSON formatting costs CPU
- [ ] Benchmark with realistic concurrency (`oha`, `wrk`, `k6`) and watch p99, not just throughput
