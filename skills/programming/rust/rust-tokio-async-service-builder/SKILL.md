---
name: rust-tokio-async-service-builder
description: "Build and review production async Rust services on Tokio 1.x and axum 0.8: runtime choice (#[tokio::main] multi_thread vs current_thread, Builder), axum routing with /{id} paths, State, extractors, IntoResponse error types, axum::serve with_graceful_shutdown, tower/tower-http middleware (TraceLayer, TimeoutLayer, CorsLayer, ConcurrencyLimitLayer, RequestBodyLimitLayer), Arc<AppState>, std vs tokio Mutex, JoinSet, TaskTracker, CancellationToken, select! cancel safety, bounded mpsc, oneshot, broadcast, watch, actors, Semaphore, timeouts, retries, spawn_blocking, sqlx PgPool, reqwest Client reuse, tracing, tests with start_paused and oneshot, Dockerfile. Fixes 'future cannot be sent between threads safely', E0373, Rc or MutexGuard held across await, 'Cannot start a runtime from within a runtime', 'Path segments must not start with :'. Ships std-only Rust scanners and a compiling axum 0.8 scaffold. Use when writing, reviewing or debugging a Tokio, axum, tower, hyper or reqwest service, worker or async Rust code."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Tokio Async Service Builder

Build async Rust services that survive production: one runtime chosen on purpose, shared state that never
holds a sync lock across `.await`, every task owned and cancellable, every queue bounded, every outbound call
timed out, errors mapped to HTTP status codes, structured traces, and a shutdown that drains instead of
dropping requests. Targets Tokio 1.x, axum 0.8, tower 0.5, tower-http 0.6, tokio-util 0.7, tracing-subscriber
0.3, reqwest 0.12 and sqlx 0.8. Four small std-only Rust scanners in `scripts/` flag the classic mistakes in
source text, and `scaffold_service` generates an axum 0.8 service that compiles, passes its tests and passes
the scanners.

## Trigger Conditions

Activate this skill when the user:
- Starts or reviews an HTTP/gRPC service, worker, consumer or proxy on Tokio, axum, tower, hyper or reqwest
- Hits `future cannot be sent between threads safely`, `` `Rc<..>` cannot be sent between threads safely ``,
  `` `MutexGuard<..>` cannot be sent ``, E0373 `async block may outlive the current function`, E0597 inside
  `tokio::spawn`, `the trait bound ... Handler<_, _> is not satisfied`
- Sees runtime panics: `Cannot start a runtime from within a runtime`, `Cannot block the current thread from
  within a runtime`, `can call blocking only when running on the multi-threaded runtime`, `Path segments must
  not start with ':'`
- Asks about graceful shutdown, SIGTERM in Kubernetes, `JoinSet`/`TaskTracker`/`CancellationToken`, `select!`,
  backpressure, channels, actors, rate/concurrency limits, timeouts, retries, connection pools
- Has latency spikes, stalled workers, memory growth from queues, or needs tracing/metrics/tokio-console
- Migrates axum 0.6/0.7 to 0.8, or wants tests that do not hit the network or real time

## Workflow

```
0. BUILD    -> once: for t in blocking_in_async await_holding task_hygiene service_hygiene scaffold_service; do
                 rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
1. SCAFFOLD -> new service: /tmp/scaffold_service --name orders-api --out ./orders-api
2. LINT     -> for t in blocking_in_async await_holding task_hygiene service_hygiene; do /tmp/$t src/; done
3. SHAPE    -> runtime (table below), AppState (Arc, std Mutex, pools, clients built once), router + layers
4. OWN      -> every spawn goes into a TaskTracker/JoinSet; every loop selects on a CancellationToken
5. BOUND    -> bounded channels, Semaphore around upstreams, timeouts on every outbound call and request
6. FAIL     -> AppError: IntoResponse; no unwrap in handlers; readiness reflects dependencies
7. OBSERVE  -> tracing + EnvFilter (+ JSON in prod), TraceLayer, #[instrument], tokio-console when stuck
8. VERIFY   -> cargo test with tower::ServiceExt::oneshot and start_paused; cargo clippy -- -D warnings;
               every scanner with --strict in CI
```

## Runtime Choice

| Need | Use | Notes |
|------|-----|-------|
| HTTP/gRPC service, mixed I/O | `#[tokio::main]` (multi_thread, one worker per core) | default; work-stealing; futures must be `Send` |
| Cap CPU in a container | `#[tokio::main(worker_threads = 4)]` or `Builder::new_multi_thread().worker_threads(n)` | match the CPU limit, not the host core count |
| CLI, single-connection client, `!Send` state | `#[tokio::main(flavor = "current_thread")]` | no `block_in_place`; one blocked call freezes everything |
| `!Send` futures on a multi-thread app | `tokio::task::LocalSet` + `spawn_local` | or move the `!Send` value into one dedicated task/thread |
| Tests | `#[tokio::test]` (current_thread by default) | `flavor = "multi_thread"` to test `Send`/parallelism; `start_paused = true` for time |
| CPU-heavy work (hash, compress, parse) | `spawn_blocking` (short), rayon pool + oneshot (parallel), own thread (long-lived) | never on the async workers |

```rust
fn main() -> anyhow::Result<()> {
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .max_blocking_threads(64) // spawn_blocking pool, default 512
        .thread_name("api-worker")
        .enable_all() // I/O + time drivers
        .build()?;
    rt.block_on(run())
}

async fn run() -> anyhow::Result<()> {
    Ok(())
}
```

## Core Rules

1. **Never block a worker.** No `std::thread::sleep`, `std::fs` on hot paths, `reqwest::blocking`, std sockets,
   `std::sync::mpsc::recv`, `thread.join()` or CPU loops over ~100 µs inside async code. Use the tokio
   equivalent, `spawn_blocking`, or rayon.
2. **`std::sync::Mutex` by default, `tokio::sync::Mutex` only if the guard must live across `.await`.** A std
   guard alive at an `.await` makes the future `!Send` and holds the lock while suspended. Scope it in a block
   or `drop(guard)` first.
3. **Every task has an owner.** `TaskTracker` or `JoinSet`, never a dropped `JoinHandle`. Owners cancel
   (`CancellationToken`) and wait (`tracker.wait()`, `join_next()`) on shutdown.
4. **Every queue is bounded** (`mpsc::channel(n)`); full means backpressure (`send().await`) or load shedding
   (`try_send` -> 503). `unbounded_channel` only when the producer is provably bounded.
5. **Every wait is bounded:** reqwest `timeout` + `connect_timeout`, sqlx `acquire_timeout`,
   `tokio::time::timeout` around anything else, `TimeoutLayer` on the router.
6. **Build clients and pools once** (`reqwest::Client`, `PgPool`) in `main`, store them in `AppState`, clone
   them freely (both are `Arc` inside).
7. **Handlers return `Result<T, AppError>`**; `AppError: IntoResponse` maps causes to status codes and logs
   internals. No `.unwrap()`/`.expect()` on fallible I/O in handlers.
8. **`select!` branches must be cancel safe** when the select runs in a loop; create timers and long reads
   outside the loop.
9. **Graceful shutdown:** Ctrl+C + SIGTERM -> readiness 503 -> stop accepting -> drain in-flight requests ->
   cancel background tasks -> wait with a deadline -> close pools.

## Service Skeleton (axum 0.8)

`/tmp/scaffold_service` prints the full version (Cargo.toml, error type, readiness, background task, tests).
The core:

```rust
use std::{sync::Arc, time::Duration};

use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
};
use tokio::net::TcpListener;
use tower::ServiceBuilder;
use tower_http::{timeout::TimeoutLayer, trace::TraceLayer};

struct AppState {
    db: sqlx::PgPool,
    http: reqwest::Client,
}

#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("not found")]
    NotFound,
    #[error(transparent)]
    Db(#[from] sqlx::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = match &self {
            AppError::NotFound => StatusCode::NOT_FOUND,
            AppError::Db(err) => {
                tracing::error!(error = %err, "database error");
                StatusCode::INTERNAL_SERVER_ERROR
            }
        };
        (status, self.to_string()).into_response()
    }
}

#[derive(serde::Serialize, sqlx::FromRow)]
struct Order {
    id: i64,
    sku: String,
}

async fn get_order(
    State(state): State<Arc<AppState>>,
    Path(id): Path<i64>,
) -> Result<Json<Order>, AppError> {
    let order = sqlx::query_as::<_, Order>("SELECT id, sku FROM orders WHERE id = $1")
        .bind(id)
        .fetch_optional(&state.db)
        .await?
        .ok_or(AppError::NotFound)?;
    Ok(Json(order))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter(tracing_subscriber::EnvFilter::from_default_env()).init();
    let db = sqlx::postgres::PgPoolOptions::new()
        .max_connections(20)
        .acquire_timeout(Duration::from_secs(3))
        .connect(&std::env::var("DATABASE_URL")?)
        .await?;
    let http = reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .connect_timeout(Duration::from_secs(3))
        .build()?;
    let state = Arc::new(AppState { db, http });

    let app = Router::new()
        .route("/orders/{id}", get(get_order)) // axum 0.8 syntax; "/:id" panics
        .layer(
            ServiceBuilder::new()
                .layer(TraceLayer::new_for_http())
                .layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, Duration::from_secs(10))),
        )
        .with_state(state); // Router<Arc<AppState>> -> Router<()>, which axum::serve needs

    let listener = TcpListener::bind("0.0.0.0:3000").await?;
    axum::serve(listener, app).with_graceful_shutdown(shutdown_signal()).await?;
    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c().await.expect("install Ctrl+C handler");
    };
    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("install SIGTERM handler")
            .recv()
            .await;
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}
```

Cargo features this needs: `tokio` `macros, rt-multi-thread, net, signal, time`; `tower-http` `trace, timeout`;
`sqlx` `runtime-tokio, postgres` (+ a TLS feature); `tracing-subscriber` `env-filter`. Routing, extractors,
middleware order and body limits: [axum-and-tower.md](references/axum-and-tower.md).

## Shared State and Locks

| State | Type | Why |
|-------|------|-----|
| Read-only config, clients, pools | `Arc<AppState>` fields, no lock | `PgPool`, `reqwest::Client` are already `Arc` + internally synchronized |
| Small map/counter, short critical section | `std::sync::Mutex` / `RwLock`, atomics | fastest; guard never crosses `.await` |
| Must hold the lock while awaiting (serialize an I/O sequence) | `tokio::sync::Mutex` | guard is `Send`; FIFO fair; slower |
| Hot read, rare write config | `tokio::sync::watch` or `arc-swap` | readers never block writers |
| Complex mutable resource (connection, cache with I/O) | actor: one task owns it, `mpsc` + `oneshot` | no locks at all |

```rust,ignore
// Wrong: guard alive across .await -> "future cannot be sent between threads safely"
// let mut cache = state.cache.lock().unwrap();
// let v = fetch(&state.http, &key).await?;
// cache.insert(key, v);

// Right: lock, copy out, unlock, await, lock again
let cached = state.cache.lock().unwrap().get(&key).cloned();
let value = match cached {
    Some(v) => v,
    None => {
        let v = fetch(&state.http, &key).await?;
        state.cache.lock().unwrap().insert(key.clone(), v.clone());
        v
    }
};
```

## Tasks, Cancellation and select!

```rust
use std::time::Duration;
use tokio_util::{sync::CancellationToken, task::TaskTracker};

async fn run_workers(token: CancellationToken) {
    let tracker = TaskTracker::new();
    for id in 0..4 {
        let token = token.child_token();
        tracker.spawn(async move {
            let mut tick = tokio::time::interval(Duration::from_secs(5));
            loop {
                tokio::select! {
                    biased; // check cancellation first, deterministically
                    _ = token.cancelled() => break,
                    _ = tick.tick() => tracing::debug!(worker = id, "tick"),
                }
            }
        });
    }
    tracker.close(); // no more spawns; wait() can now complete
    token.cancelled().await;
    if tokio::time::timeout(Duration::from_secs(10), tracker.wait()).await.is_err() {
        tracing::warn!("workers did not stop in 10s");
    }
}
```

- `JoinSet` when you need results/errors back (`join_next()`), and to abort everything on drop.
- `TaskTracker` for fire-and-track background work you only need to wait for at shutdown.
- `select!` drops the losing futures. Cancel safe: `mpsc::Receiver::recv`, `broadcast::Receiver::recv`,
  `watch::Receiver::changed`, `TcpListener::accept`, `AsyncReadExt::read`, `Interval::tick`,
  `CancellationToken::cancelled`, `Lines::next_line`, `StreamExt::next`. Not cancel safe: `read_exact`,
  `read_line`, `read_to_end`, `write_all`, `Mutex::lock`/`Semaphore::acquire` (lose their queue place),
  `Sender::send` (the message is dropped).

Full patterns (JoinSet vs TaskTracker, abort, panics, shutdown sequencing, blocking work):
[runtime-tasks-and-shutdown.md](references/runtime-tasks-and-shutdown.md).

## Channels, Backpressure and Limits

| Need | Primitive | Watch out |
|------|-----------|-----------|
| Work queue, many producers -> one consumer | `mpsc::channel(n)` | `send().await` waits when full; `try_send` to shed |
| Request/response to an actor | `oneshot` inside the mpsc message | receiver gets `RecvError` if the actor dropped the sender |
| Fan-out events to every subscriber | `broadcast::channel(n)` | slow receiver gets `RecvError::Lagged(skipped)`; handle it, do not exit |
| Latest value only (config, health) | `watch::channel(v)` | `borrow()` holds a read lock: never across `.await` |
| Limit concurrent upstream calls | `Semaphore` (`acquire_owned` to move into tasks) | permits release on drop; close() to fail waiters |
| Limit concurrent requests | `tower::limit::GlobalConcurrencyLimitLayer` / `ConcurrencyLimitLayer` | `Router::layer` wraps each route separately |

Actors, retries with backoff, reqwest and sqlx tuning: [state-channels-and-backpressure.md](references/state-channels-and-backpressure.md).

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| `future cannot be sent between threads safely` ... `MutexGuard` | std guard alive at an `.await` (TK006) | scope the guard in `{}` / `drop()` before `.await`, or tokio Mutex |
| `` `Rc<...>` cannot be sent between threads safely `` | `Rc`/`RefCell` in a spawned future (TK008) | `Arc` + `Mutex`; or `LocalSet::spawn_local` |
| E0373 `async block may outlive the current function` | `tokio::spawn(async { uses_local })` (TK019) | clone what it needs, `async move` |
| E0597 / `argument requires that x is borrowed for 'static` | passing `&local` into `spawn` | own the data (`Arc`, clone); `spawn` needs `'static` |
| `Handler<_, _> is not satisfied` | non-`Send` future, body extractor not last, return type not `IntoResponse`, wrong `State` type | add `#[axum::debug_handler]` (feature `macros`) to get the real error |
| Panic `Cannot start a runtime from within a runtime` | `block_on`/`Runtime::new` in async code, `reqwest::blocking` dropped in async (TK015/TK003) | `.await` it; `spawn_blocking` for sync code that needs a runtime |
| Panic `can call blocking only when running on the multi-threaded runtime` | `block_in_place` on current_thread / `#[tokio::test]` (TK018) | `spawn_blocking`, or `flavor = "multi_thread"` |
| Panic `Path segments must not start with ':'` at startup | axum 0.7 route syntax on 0.8 (TK017) | `/{id}`, `/{*rest}` |
| p99 spikes, all endpoints slow together | blocking call or CPU on a worker (TK001-TK005) | tokio-console "busy" tasks; move to `spawn_blocking`/rayon |
| Memory grows steadily under load | unbounded channel / detached tasks pile up (TK010/TK009) | bounded channel, Semaphore, TaskTracker |
| Requests hang forever when upstream stalls | no timeout (TK013) | client `timeout`, `tokio::time::timeout`, `TimeoutLayer` |
| `ResponseBody<Body>: Default` is not satisfied on `.layer(..)` | `RequestBodyLimitLayer` placed inside `TimeoutLayer`, which needs a `Default` body | add the body limit before (outside) the timeout in `ServiceBuilder` |
| `Too many open files`, TLS handshake per request | `reqwest::Client::new()` per request (TK011) | one Client in state |
| `PoolTimedOut` from sqlx under load | pool too small, long transactions, connection held across slow awaits | right-size pool, keep transactions short, `acquire_timeout` |
| 502s on every deploy | no graceful shutdown (TK014), readiness still 200 | `with_graceful_shutdown`, readiness 503 first, drain deadline |
| Data lost on a TCP stream that uses `select!` | `read_exact`/`read_line` cancelled (TK016) | `FramedRead`/`Lines::next_line`, or a dedicated reader task |
| Broadcast subscriber dies under load | treats `RecvError::Lagged` as fatal | log + continue; bigger buffer |

Every compile error with a minimal reproduction and fix: [send-static-and-compile-errors.md](references/send-static-and-compile-errors.md).

## Blocking and CPU Work

```rust,ignore
// Short blocking call (file, sync library, bcrypt): the blocking pool
let hash = tokio::task::spawn_blocking(move || bcrypt::hash(password, 12)).await??;

// Parallel CPU: rayon pool, result back through a oneshot
let (tx, rx) = tokio::sync::oneshot::channel();
rayon::spawn(move || {
    let sum: u64 = items.par_iter().map(|x| expensive(x)).sum(); // use rayon::prelude::*
    let _ = tx.send(sum);
});
let sum = rx.await?;
```

`spawn_blocking` tasks cannot be aborted once running and the runtime waits for them on shutdown; long-lived
blocking loops belong on `std::thread::spawn` with a channel.

## Observability

```rust,ignore
use tracing_subscriber::{EnvFilter, layer::SubscriberExt, util::SubscriberInitExt};

fn init_tracing(json: bool) {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info,tower_http=info"));
    let registry = tracing_subscriber::registry().with(filter);
    if json {
        registry.with(tracing_subscriber::fmt::layer().json()).init(); // feature "json"
    } else {
        registry.with(tracing_subscriber::fmt::layer()).init();
    }
}

#[tracing::instrument(skip(state), err)] // records `id`; logs the error on Err
async fn load_order(state: &AppState, id: i64) -> Result<Order, AppError> { /* ... */ }
```

OpenTelemetry export, tokio-console (`RUSTFLAGS="--cfg tokio_unstable"` + `console-subscriber`), configuration
with env/figment/config, Dockerfile with cargo-chef + distroless, and performance notes:
[observability-config-and-deploy.md](references/observability-config-and-deploy.md).

## Testing

```rust,ignore
#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request};
    use tower::ServiceExt; // oneshot

    #[tokio::test]
    async fn unknown_order_is_404() {
        let app = router(test_state());
        let res = app.oneshot(Request::get("/orders/999").body(Body::empty()).unwrap()).await.unwrap();
        assert_eq!(res.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test(start_paused = true)] // tokio feature "test-util"; time auto-advances when idle
    async fn retry_gives_up_after_deadline() {
        let started = tokio::time::Instant::now();
        let res = with_retry(|| async { Err::<(), _>("down") }).await;
        assert!(res.is_err());
        // 4 backoff sleeps: 100 + 200 + 400 + 800 ms of virtual time, the test runs instantly
        assert!(started.elapsed() >= Duration::from_millis(1500));
    }
}
```

`.unwrap()` is fine in tests (the linter skips `mod tests` and `#[tokio::test]`). More: fakes behind traits,
sqlx test databases, wiremock, testing shutdown and cancellation, `Send` assertions:
[testing-tokio-services.md](references/testing-tokio-services.md).

## Version Notes

| Crate | Version | What matters |
|-------|---------|--------------|
| axum | 0.8 | `/{id}` and `/{*rest}` paths; no `#[async_trait]` on custom extractors; `Option<T>` extractor needs `OptionalFromRequestParts`; tower 0.5, tower-http 0.6 |
| axum | 0.7 | hyper 1.0; `axum::Server` removed -> `axum::serve(TcpListener, app)`; own `Body` type |
| tokio | 1.x | stable API since 1.0; LTS lines; `JoinSet` (1.21), `JoinSet::join_all` (1.40) |
| tokio-util | 0.7 | `CancellationToken`, `TaskTracker` (feature `rt`), codecs |
| Rust | 1.75+ | `async fn` in traits (not `dyn`-compatible; `Send` bound needs `-> impl Future + Send`) |

Migration steps and breaking changes: [versions-and-migration.md](references/versions-and-migration.md).

## Output Format

When building or reviewing a service, answer with:
1. **Findings** - `file:line`, rule id (TKxxx when the linter flags it, or the compiler error code), why it
   breaks in production (stall, panic, leak, data loss, dropped requests).
2. **Fix** - complete, compiling before/after code using the crate versions above; name the Cargo features
   required.
3. **Design notes** - runtime flavor, state/lock choice, task ownership, bounds (channel capacity, permits,
   timeouts, pool size) with the reasoning.
4. **Verification** - the test (`oneshot`, `start_paused`) that proves the fix, and
   scanner (`--strict`) / `cargo clippy` / `cargo test` commands to run.

For a new service, start from `scaffold_service`, then list what was added beyond it.

## Scripts

Small, standard-library-only Rust programs (no Cargo project). The scanners read source text and never
compile or run your code. Build each once with `rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>`.

| Script | Rules | Job |
|--------|-------|-----|
| `scripts/blocking_in_async.rs` | TK001-TK005, TK015, TK018 | blocking calls on runtime workers: std sleep/fs/net/stdin, blocking HTTP, sync waits, nested runtimes, block_in_place on current_thread |
| `scripts/await_holding.rs` | TK006-TK008 | std guards / RefCell borrows alive at `.await`, tokio Mutex never held across `.await`, `Rc` in async code |
| `scripts/task_hygiene.rs` | TK009, TK010, TK016, TK019 | detached `tokio::spawn`, unbounded channels, cancel-unsafe `select!` loops, spawn without `move` |
| `scripts/service_hygiene.rs` | TK011-TK014, TK017 | reqwest client per call, `.await.unwrap()` in handlers, no outbound timeout, no graceful shutdown, axum 0.7 paths |
| `scripts/scaffold_service.rs` | - | axum 0.8 service: Cargo.toml + src/main.rs (compiles, 4 tests pass, scanners clean) |
| `scripts/async_ctx.rs`, `scripts/rsparse.rs`, `scripts/cli.rs` | - | shared modules: async-context and handler detection, source scanner, options and report |

```bash
/tmp/blocking_in_async src/                        # files and/or directories (*.rs, skips target/)
/tmp/await_holding src/main.rs --json              # machine-readable findings with fix
cat handler.rs | /tmp/service_hygiene -            # stdin
/tmp/task_hygiene src/ --strict                    # exit 1 on any finding (CI gate)
/tmp/blocking_in_async src/ --select TK001,TK002 --ignore TK018
/tmp/service_hygiene --list-rules                  # each scanner lists its rules with why and fix

/tmp/scaffold_service --name orders-api            # print both files
/tmp/scaffold_service --name orders-api --file main   # only src/main.rs (or --file cargo)
/tmp/scaffold_service --name orders-api --out ./orders-api [--force]
```

| Rule | Name | Flags |
|------|------|-------|
| TK001 | blocking-sleep | `std::thread::sleep` in async code |
| TK002 | blocking-fs | `std::fs::*` / `File::open` without `.await` in async code |
| TK003 | blocking-http | `reqwest::blocking` / `ureq` in async code |
| TK004 | blocking-net-or-stdin | std `TcpStream::connect`/`TcpListener::bind`/`UdpSocket::bind`, `std::io::stdin()` |
| TK005 | blocking-wait | `.recv()`, `.recv_timeout()`, `.join()`, `.wait()` without `.await` (not in `select!` or passed as an argument) |
| TK006 | sync-guard-across-await | std `MutexGuard`/`RwLock` guard/`RefCell` borrow alive at a later `.await` |
| TK007 | async-mutex-not-needed (low) | `tokio::sync::Mutex` guard never held across `.await` |
| TK008 | rc-in-async | `Rc` inside async code |
| TK009 | detached-spawn | `tokio::spawn(..);` with the `JoinHandle` dropped |
| TK010 | unbounded-channel | `unbounded_channel()` |
| TK011 | client-per-request | `reqwest::Client::new()/builder()` in an async fn (other than `main`) or a loop |
| TK012 | unwrap-on-await-in-handler | `.await.unwrap()` / `.await.expect()` in an axum handler |
| TK013 | outbound-without-timeout (low) | reqwest `.send().await` and no `timeout(` anywhere in the file |
| TK014 | no-graceful-shutdown | `axum::serve` without `.with_graceful_shutdown` |
| TK015 | runtime-in-runtime | `block_on`, `Runtime::new`, `blocking_recv/send/lock/read/write` in async code |
| TK016 | select-loop-not-cancel-safe | `select!` in a loop racing `read_exact`/`read_line`/`read_to_end`/`write_all`/`sleep(..)` |
| TK017 | axum07-path-syntax | `"/:id"` or `"/*rest"` in `.route`/`.nest` |
| TK018 | block-in-place-current-thread | `block_in_place` with `current_thread` / plain `#[tokio::test]` |
| TK019 | spawn-without-move (low) | `tokio::spawn(async { .. })` / `.spawn(async { .. })` without `move` |

Async context = `async fn` bodies, `async {}`/`async move {}` blocks and async closures, minus the arguments of
`spawn_blocking`, `block_in_place`, `thread::spawn` and `rayon::spawn`. Handlers = functions routed with
`get(..)`/`post(..)`/... or taking axum extractors. Silence a line with `// noqa` or `// noqa: TK009`.
Exit codes: 0 clean (or not strict), 1 findings with `--strict`, 2 usage error or unreadable file;
`scaffold_service` exits 2 if `--out` would overwrite files without `--force`.

## Additional Resources

| File | Content |
|------|---------|
| [runtime-tasks-and-shutdown.md](references/runtime-tasks-and-shutdown.md) | Runtime flavors and Builder, spawn/JoinHandle/JoinSet/TaskTracker, abort and panics, CancellationToken, select! and cancel safety, graceful shutdown sequence, blocking and CPU work |
| [axum-and-tower.md](references/axum-and-tower.md) | axum 0.8 routing, extractors and their order, State and FromRef, custom extractors, AppError mapping, tower/tower-http middleware and ordering, body limits, CORS, health/readiness, serve variants |
| [state-channels-and-backpressure.md](references/state-channels-and-backpressure.md) | std vs tokio Mutex, RwLock, atomics, watch/arc-swap, mpsc/oneshot/broadcast/watch semantics, actor pattern, Semaphore, timeouts, retries with backoff, reqwest Client and sqlx PgPool configuration |
| [send-static-and-compile-errors.md](references/send-static-and-compile-errors.md) | Send + 'static errors on spawn, MutexGuard/Rc/RefCell across await, E0373/E0597, Handler trait errors and debug_handler, async fn in traits, dyn and Send bounds |
| [observability-config-and-deploy.md](references/observability-config-and-deploy.md) | tracing-subscriber setup, EnvFilter, JSON, #[instrument], TraceLayer spans, request ids, OpenTelemetry, tokio-console, config with env/figment/config, Dockerfile (cargo-chef, distroless), performance |
| [testing-tokio-services.md](references/testing-tokio-services.md) | #[tokio::test] flavors, start_paused time control, oneshot router tests, fakes via traits, sqlx test databases, HTTP mocks, testing cancellation and shutdown, Send assertions |
| [versions-and-migration.md](references/versions-and-migration.md) | axum 0.6 -> 0.7 -> 0.8, tower 0.5 / tower-http 0.6, tokio 1.x additions and LTS, tokio-util, hyper 1.0, Rust edition 2024 notes |
