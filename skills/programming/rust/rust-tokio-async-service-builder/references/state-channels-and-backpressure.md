# State, Channels and Backpressure

Locks, channels, actors, semaphores, timeouts, retries, and the two clients every service has: an HTTP client
(reqwest) and a database pool (sqlx).

## Contents

- [Choosing a lock](#choosing-a-lock)
- [std::sync::Mutex in async code](#stdsyncmutex-in-async-code)
- [When tokio::sync::Mutex is right](#when-tokiosyncmutex-is-right)
- [Read-mostly state: RwLock, watch, arc-swap](#read-mostly-state-rwlock-watch-arc-swap)
- [Channel semantics](#channel-semantics)
- [Backpressure and load shedding](#backpressure-and-load-shedding)
- [The actor pattern](#the-actor-pattern)
- [Semaphore: concurrency limits](#semaphore-concurrency-limits)
- [Timeouts](#timeouts)
- [Retries with backoff](#retries-with-backoff)
- [reqwest Client](#reqwest-client)
- [sqlx PgPool](#sqlx-pgpool)
- [Batching and coalescing](#batching-and-coalescing)

## Choosing a lock

| Situation | Choice |
|-----------|--------|
| Data never changes after startup | no lock: plain fields in `Arc<AppState>` |
| Counter, flag, gauge | `AtomicU64`, `AtomicBool` (`Ordering::Relaxed` for metrics, `Acquire/Release` for publication) |
| Small map/vec, lock held for microseconds, no `.await` inside | `std::sync::Mutex` (or `parking_lot::Mutex`) |
| Many readers, rare writers, no `.await` inside | `std::sync::RwLock` or `arc_swap::ArcSwap` |
| Guard must be held across `.await` (e.g. serialize writes to one connection) | `tokio::sync::Mutex` |
| Config that changes at runtime, readers want the latest | `tokio::sync::watch` |
| Mutable resource with I/O and invariants | actor (one owning task + channel) |
| Sharded hot map | `dashmap` (never hold a `Ref` across `.await`; it is a lock guard) |

The tokio docs say it directly: "contrary to popular belief, it is ok and often preferred to use the ordinary
Mutex from the standard library in asynchronous code"; the async mutex exists for holding a guard across
`.await` points.

## std::sync::Mutex in async code

```rust
use std::{collections::HashMap, sync::{Arc, Mutex}};

#[derive(Default)]
struct RateCounters {
    by_key: Mutex<HashMap<String, u64>>,
}

impl RateCounters {
    // Sync method: the guard cannot accidentally live across an .await.
    fn hit(&self, key: &str) -> u64 {
        let mut map = self.by_key.lock().unwrap_or_else(|poisoned| poisoned.into_inner());
        let n = map.entry(key.to_owned()).or_insert(0);
        *n += 1;
        *n
    }
}

async fn handle(counters: Arc<RateCounters>, key: String) -> u64 {
    let n = counters.hit(&key); // lock taken and released inside a sync fn
    tokio::task::yield_now().await;
    n
}
```

Wrapping lock access in small **sync** methods is the most reliable way to keep guards off `.await` points:
the compiler will not let a sync function hold a guard past its return.

Pitfalls:
- `let x = m.lock().unwrap().get(k).cloned();` is fine: the temporary guard drops at the end of the
  statement. `let g = m.lock().unwrap();` keeps it until the end of the block (lint TK006 if an `.await`
  follows).
- `match m.lock().unwrap().get(k) { .. }` keeps the temporary guard alive for the whole `match`, including
  `.await`s in the arms. Bind the value first.
- `if let Some(v) = m.lock().unwrap().get(k).cloned() { work(v).await }` holds the guard through the body in
  edition 2021; edition 2024 drops `if let` scrutinee temporaries before the `else` but **not** before the
  body. Bind first, then `if let`.
- Contention: a hot std mutex blocks worker threads briefly. If profiling shows contention, shard the map
  (`[Mutex<HashMap>; 16]` by hash) or use `dashmap`.

## When tokio::sync::Mutex is right

```rust
use std::sync::Arc;
use tokio::{io::AsyncWriteExt, net::TcpStream, sync::Mutex};

#[derive(Clone)]
struct AuditSink {
    conn: Arc<Mutex<TcpStream>>,
}

impl AuditSink {
    async fn write_record(&self, line: &str) -> std::io::Result<()> {
        let mut conn = self.conn.lock().await;        // held across the two awaits below: correct
        conn.write_all(line.as_bytes()).await?;
        conn.write_all(b"\n").await?;
        Ok(())
    }
}
```

Even here an actor is often better: callers do not queue on a lock, the connection can be re-established in
one place, and a slow write does not hold N tasks parked on `lock()`. `tokio::sync::Mutex::lock` is fair
(FIFO). `blocking_lock()` exists for sync code outside the runtime and panics inside it.

## Read-mostly state: RwLock, watch, arc-swap

```rust
use std::time::Duration;
use tokio::sync::watch;

#[derive(Clone, Debug, PartialEq)]
struct Limits { max_batch: usize, upstream_timeout: Duration }

async fn reload_loop(tx: watch::Sender<Limits>) {
    let mut every = tokio::time::interval(Duration::from_secs(30));
    loop {
        every.tick().await;
        let new = Limits { max_batch: 64, upstream_timeout: Duration::from_secs(5) }; // load from source
        tx.send_if_modified(|cur| if *cur != new { *cur = new; true } else { false });
    }
}

async fn worker(mut rx: watch::Receiver<Limits>) {
    loop {
        let limits = rx.borrow_and_update().clone(); // clone out: the Ref is a read guard, !Send
        tracing::debug!(?limits, "using limits");
        if rx.changed().await.is_err() {
            break; // sender dropped
        }
    }
}
```

- `watch::Receiver::borrow()` returns a `Ref` that holds a read lock: clone what you need, drop it, then
  await. Holding it across `.await` is the same bug as a `MutexGuard`.
- `rx.changed()` is cancel safe; `rx.wait_for(|v| predicate(v))` waits for a condition.
- `arc_swap::ArcSwap<T>`: lock-free `load()` of an `Arc<T>`, `store()` to replace; good for config and
  routing tables read on every request.

## Channel semantics

| Channel | Shape | Capacity / full behaviour | Closed when | Receive errors |
|---------|-------|---------------------------|-------------|----------------|
| `mpsc::channel(n)` | many -> one | `send().await` waits; `try_send` -> `TrySendError::Full` | all `Sender`s dropped (`recv` -> `None`) or `rx.close()` | `None` |
| `mpsc::unbounded_channel()` | many -> one | never full (memory grows) | same | `None` |
| `oneshot::channel()` | one value, once | `send` never waits; returns `Err(value)` if receiver dropped | sender dropped | `RecvError` |
| `broadcast::channel(n)` | many -> many, every receiver sees every value | ring buffer; slow receivers lose oldest | all senders dropped | `RecvError::Lagged(k)`, `Closed` |
| `watch::channel(v)` | one value, latest wins | never full | sender dropped | `changed()` -> `Err` |
| `async_channel` / `flume` (crates) | many -> many work queue (MPMC) | bounded | ... | ... |

Notes:
- `mpsc` is single-consumer. For a pool of N workers, either share the receiver behind
  `Arc<tokio::sync::Mutex<Receiver<T>>>` (simple, lock only around `recv`), spawn one channel per worker and
  round-robin, or use an MPMC crate.
- `recv_many(&mut buf, limit)` drains up to `limit` messages in one call: cheap batching.
- `Sender::reserve().await` gets a slot before you build the message (cancel safe, useful in `select!`).
- `broadcast` requires `T: Clone`; handle `Lagged` by logging and continuing:

```rust
use tokio::sync::broadcast::{self, error::RecvError};

async fn subscriber(mut rx: broadcast::Receiver<String>) {
    loop {
        match rx.recv().await {
            Ok(ev) => tracing::debug!(%ev, "event"),
            Err(RecvError::Lagged(skipped)) => tracing::warn!(skipped, "subscriber too slow, events dropped"),
            Err(RecvError::Closed) => break,
        }
    }
}
```

## Backpressure and load shedding

Backpressure = a full queue slows the producer. Load shedding = a full queue rejects new work. A service
needs one of them at every queue boundary, or memory absorbs the overload until the OOM killer arrives.

```rust,ignore
use axum::{extract::State, http::StatusCode};
use tokio::sync::mpsc::error::TrySendError;

async fn enqueue(State(state): State<AppStateRef>, body: String) -> StatusCode {
    match state.jobs.try_send(Job { body }) {
        Ok(()) => StatusCode::ACCEPTED,
        Err(TrySendError::Full(_)) => StatusCode::SERVICE_UNAVAILABLE, // shed: client retries later
        Err(TrySendError::Closed(_)) => StatusCode::SERVICE_UNAVAILABLE, // shutting down
    }
}
```

Inside a pipeline (reader -> parser -> writer) use `send().await` so the reader slows to the writer's pace.
Capacity: big enough to absorb bursts (roughly throughput x acceptable queueing delay), small enough that a
full queue is noticed quickly. Export `tx.capacity()` (free slots) as a gauge.

## The actor pattern

One task owns the state; everyone else holds a cheap `Handle` that sends messages. No locks, invariants in one
place, backpressure built in.

```rust
use std::collections::HashMap;
use tokio::sync::{mpsc, oneshot};
use tokio_util::sync::CancellationToken;

enum Msg {
    Get { key: String, reply: oneshot::Sender<Option<String>> },
    Put { key: String, value: String },
}

#[derive(Clone)]
pub struct CacheHandle {
    tx: mpsc::Sender<Msg>,
}

#[derive(Debug, thiserror::Error)]
#[error("cache actor is gone")]
pub struct ActorGone;

impl CacheHandle {
    pub fn spawn(tracker: &tokio_util::task::TaskTracker, token: CancellationToken) -> Self {
        let (tx, rx) = mpsc::channel(512);
        tracker.spawn(run(rx, token));
        Self { tx }
    }

    pub async fn get(&self, key: &str) -> Result<Option<String>, ActorGone> {
        let (reply, rx) = oneshot::channel();
        self.tx.send(Msg::Get { key: key.to_owned(), reply }).await.map_err(|_| ActorGone)?;
        rx.await.map_err(|_| ActorGone)
    }

    pub async fn put(&self, key: String, value: String) -> Result<(), ActorGone> {
        self.tx.send(Msg::Put { key, value }).await.map_err(|_| ActorGone)
    }
}

async fn run(mut rx: mpsc::Receiver<Msg>, token: CancellationToken) {
    let mut map: HashMap<String, String> = HashMap::new();
    loop {
        tokio::select! {
            biased;
            _ = token.cancelled() => break,
            msg = rx.recv() => match msg {
                Some(Msg::Get { key, reply }) => { let _ = reply.send(map.get(&key).cloned()); }
                Some(Msg::Put { key, value }) => { map.insert(key, value); }
                None => break, // every handle dropped
            },
        }
    }
}
```

Rules for actors:
- The actor loop must not `.await` slow I/O per message unless that is the point (it serializes everything).
  Spawn per-message work into a `JoinSet` owned by the actor if it can run concurrently.
- Ignore the `oneshot` send error (`let _ =`): the caller may have been cancelled.
- Never let the actor `send().await` to a channel that feeds back into itself: with both queues full it
  deadlocks.

## Semaphore: concurrency limits

```rust
use std::{sync::Arc, time::Duration};
use tokio::sync::Semaphore;

pub struct Upstream {
    http: reqwest::Client,
    permits: Arc<Semaphore>,
}

impl Upstream {
    pub fn new(http: reqwest::Client, max_in_flight: usize) -> Self {
        Self { http, permits: Arc::new(Semaphore::new(max_in_flight)) }
    }

    pub async fn price(&self, sku: &str) -> anyhow::Result<f64> {
        // wait at most 200 ms for a permit, then fail fast instead of queueing forever
        let _permit = tokio::time::timeout(Duration::from_millis(200), self.permits.acquire())
            .await
            .map_err(|_| anyhow::anyhow!("pricing saturated"))??;
        let price = self
            .http
            .get(format!("https://pricing.internal/v1/{sku}"))
            .timeout(Duration::from_secs(2))
            .send()
            .await?
            .error_for_status()?
            .json::<f64>()
            .await?;
        Ok(price)
    }
}
```

- `acquire()` borrows the semaphore; `Arc<Semaphore>::acquire_owned()` returns an `OwnedSemaphorePermit` you
  can move into a spawned task.
- The permit is released on drop, including on error and cancellation; no `release()` bookkeeping.
- `try_acquire()` for immediate shedding. `semaphore.close()` makes waiters fail with `AcquireError`
  (useful at shutdown).
- `acquire_many(n)` for weighted limits (e.g. tokens, bytes).

## Timeouts

| What | How |
|------|-----|
| Any future | `tokio::time::timeout(dur, fut).await` -> `Err(Elapsed)` |
| Absolute deadline across several steps | `tokio::time::timeout_at(deadline, fut)` with one `Instant` |
| Whole HTTP request (server side) | `tower_http::timeout::TimeoutLayer` |
| reqwest, all calls | `Client::builder().timeout(..)` (total) + `.connect_timeout(..)` |
| reqwest, one call | `RequestBuilder::timeout(..)` overrides the client's |
| sqlx pool checkout | `PgPoolOptions::acquire_timeout(..)` |
| sqlx statement | Postgres `statement_timeout` (`SET statement_timeout = '5s'` in `after_connect`, or in the URL `options`) |
| Raw TCP connect | `timeout(d, TcpStream::connect(addr))` |

A deadline budget propagates better than per-step timeouts: compute `deadline = Instant::now() + 2s` at the
start of the request and use `timeout_at(deadline, ..)` for every step, so three sequential 2 s steps cannot
take 6 s.

## Retries with backoff

Retry only idempotent operations and only on transient failures (timeouts, connect errors, 429, 502, 503,
504). Cap attempts and total time; add jitter to avoid synchronized retry storms.

```rust
use std::{future::Future, time::Duration};

pub async fn with_retry<T, E, F, Fut>(mut op: F) -> Result<T, E>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = Result<T, E>>,
    E: std::fmt::Display,
{
    let mut delay = Duration::from_millis(100);
    let max_attempts = 5;
    for attempt in 1.. {
        match op().await {
            Ok(v) => return Ok(v),
            Err(err) if attempt < max_attempts => {
                tracing::warn!(attempt, %err, ?delay, "retrying");
                tokio::time::sleep(delay).await;
                delay = (delay * 2).min(Duration::from_secs(5)); // add random jitter in production
            }
            Err(err) => return Err(err),
        }
    }
    unreachable!("loop returns on the last attempt")
}

pub fn is_transient(err: &reqwest::Error) -> bool {
    err.is_timeout()
        || err.is_connect()
        || err.status().is_some_and(|s| s.as_u16() == 429 || s.is_server_error())
}
```

With 5 attempts the sleeps are 100 + 200 + 400 + 800 ms. Test it with `#[tokio::test(start_paused = true)]`
so it runs instantly (see [testing-tokio-services.md](testing-tokio-services.md)). Respect `Retry-After` on
429/503. Crates like `backon` or `tokio-retry` package the same idea.

## reqwest Client

```rust
use std::time::Duration;

pub fn http_client() -> reqwest::Result<reqwest::Client> {
    reqwest::Client::builder()
        .user_agent(concat!(env!("CARGO_PKG_NAME"), "/", env!("CARGO_PKG_VERSION")))
        .timeout(Duration::from_secs(10))          // total per request, including body
        .connect_timeout(Duration::from_secs(3))
        .pool_idle_timeout(Duration::from_secs(90))
        .pool_max_idle_per_host(32)
        .tcp_keepalive(Duration::from_secs(60))
        .build()
}
```

- Build once, store in state, `clone()` per use (it is an `Arc` internally). One client per distinct config
  (e.g. different TLS roots), not per request (lint TK011).
- `error_for_status()` turns 4xx/5xx into `Err`; without it a 500 is an `Ok(Response)`.
- Stream large bodies with `resp.bytes_stream()` (feature `stream`) instead of `bytes().await`.
- TLS: `default-features = false, features = ["rustls-tls", "json"]` avoids OpenSSL (simpler distroless
  images). Feature names differ between reqwest major versions; check the docs of the version you pin.

## sqlx PgPool

```rust
use std::time::Duration;
use sqlx::postgres::PgPoolOptions;

pub async fn db_pool(url: &str) -> Result<sqlx::PgPool, sqlx::Error> {
    PgPoolOptions::new()
        .max_connections(20)                      // <= Postgres max_connections / replicas
        .min_connections(2)
        .acquire_timeout(Duration::from_secs(3))  // PoolTimedOut instead of waiting forever
        .idle_timeout(Duration::from_secs(300))
        .max_lifetime(Duration::from_secs(1800))
        .connect(url)
        .await
}

#[derive(Debug, sqlx::FromRow, serde::Serialize)]
pub struct Order {
    pub id: i64,          // Postgres has no unsigned types: use i64/i32
    pub sku: String,
    pub qty: i32,
}

pub async fn find_order(pool: &sqlx::PgPool, id: i64) -> Result<Option<Order>, sqlx::Error> {
    sqlx::query_as::<_, Order>("SELECT id, sku, qty FROM orders WHERE id = $1")
        .bind(id)
        .fetch_optional(pool)
        .await
}

pub async fn transfer(pool: &sqlx::PgPool, from: i64, to: i64, qty: i32) -> Result<(), sqlx::Error> {
    let mut tx = pool.begin().await?;
    sqlx::query("UPDATE stock SET qty = qty - $1 WHERE id = $2").bind(qty).bind(from).execute(&mut *tx).await?;
    sqlx::query("UPDATE stock SET qty = qty + $1 WHERE id = $2").bind(qty).bind(to).execute(&mut *tx).await?;
    tx.commit().await // dropping tx without commit rolls back
}
```

- Cargo: `sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "tls-rustls"] }` (+ `macros`,
  `migrate`, `chrono`/`time`, `uuid` as needed). The compile-time checked `query!`/`query_as!` macros need
  `DATABASE_URL` at build time or `cargo sqlx prepare` offline data (`.sqlx/` directory).
- A connection or transaction held across slow `.await`s (an HTTP call inside a transaction) pins a pool
  slot; under load that becomes `PoolTimedOut`. Do remote calls before or after the transaction.
- Pool size: start around `2 x cores` of the DB divided by replicas; measure.
- `sqlx::migrate!().run(&pool).await?` at startup (or as a separate job for multi-replica deploys).
- Close on shutdown: `pool.close().await`.

## Batching and coalescing

- **Batch writes:** collect messages with `rx.recv_many(&mut buf, 500).await` and write them in one
  statement or one request; flush on size or on a timer (`select!` on `interval.tick()`).
- **Coalesce identical reads (single flight):** keep `HashMap<Key, Shared<..>>` of in-flight lookups, or
  run the cache in an actor that parks waiters on a pending entry and replies to all when the fetch
  completes.
- **Cache with TTL:** `moka::future::Cache` (async-aware, `get_with` coalesces concurrent loads of the same
  key).
