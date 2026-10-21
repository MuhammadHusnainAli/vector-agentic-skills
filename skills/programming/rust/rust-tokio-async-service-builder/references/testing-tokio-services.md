# Testing Tokio Services

Fast, deterministic tests for async services: no real network, no real time, no sleeps. Examples target
tokio 1 (with the `test-util` feature for time control), axum 0.8 and tower 0.5 (`util` feature for
`ServiceExt::oneshot`).

## Contents

- [Test runtimes](#test-runtimes)
- [Controlling time](#controlling-time)
- [Router tests without a socket](#router-tests-without-a-socket)
- [Fakes through traits in state](#fakes-through-traits-in-state)
- [Cancellation and shutdown](#cancellation-and-shutdown)
- [Channels and backpressure](#channels-and-backpressure)
- [Send assertions](#send-assertions)
- [End-to-end over a real port](#end-to-end-over-a-real-port)
- [Databases and HTTP dependencies](#databases-and-http-dependencies)
- [Checklist](#checklist)

## Test runtimes

| Attribute | Runtime | Use for |
|-----------|---------|---------|
| `#[tokio::test]` | current_thread | most tests: deterministic, no `Send` requirement on locals |
| `#[tokio::test(flavor = "multi_thread", worker_threads = 2)]` | multi_thread | code using `block_in_place`, real parallelism, races |
| `#[tokio::test(start_paused = true)]` | current_thread, paused clock | timeouts, retries, intervals, backoff |

Dev-dependency for time control: `tokio = { version = "1", features = ["test-util", "macros", "rt"] }`.

## Controlling time

With a paused clock, `sleep`, `timeout` and `interval` complete as soon as every task is idle: the runtime
auto-advances to the next timer. A test of a 30-second timeout takes microseconds.

```rust
use std::time::Duration;
use tokio::time::{self, Instant};

async fn retry_with_backoff<F, Fut>(mut op: F, attempts: u32) -> Result<u32, &'static str>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<u32, &'static str>>,
{
    let mut delay = Duration::from_millis(100);
    for _ in 0..attempts {
        match op().await {
            Ok(v) => return Ok(v),
            Err(_) => {
                time::sleep(delay).await;
                delay *= 2;
            }
        }
    }
    Err("gave up")
}

#[tokio::test(start_paused = true)]
async fn backoff_waits_100_200_400ms() {
    let start = Instant::now();
    let mut calls = 0;
    let res = retry_with_backoff(|| { calls += 1; async { Err("down") } }, 3).await;
    assert_eq!(res, Err("gave up"));
    assert_eq!(start.elapsed(), Duration::from_millis(700)); // exact: virtual time
}

#[tokio::test(start_paused = true)]
async fn timeout_fires_without_waiting() {
    let slow = time::sleep(Duration::from_secs(30));
    assert!(time::timeout(Duration::from_secs(5), slow).await.is_err());
}
```

Use `time::advance(d).await` to move the clock by hand when a test must observe intermediate states.
Real I/O (sockets, files) is not virtual: keep it out of paused-clock tests.

## Router tests without a socket

An axum `Router` is a tower `Service`: call it directly with `oneshot`.

```rust
use axum::{body::{to_bytes, Body}, extract::Path, http::{Request, StatusCode}, routing::get, Json, Router};
use tower::ServiceExt; // oneshot

async fn get_item(Path(id): Path<u64>) -> Result<Json<serde_json::Value>, StatusCode> {
    if id == 0 { Err(StatusCode::NOT_FOUND) } else { Ok(Json(serde_json::json!({ "id": id }))) }
}

fn app() -> Router {
    Router::new().route("/items/{id}", get(get_item))
}

#[tokio::test]
async fn returns_item_json() {
    let res = app().oneshot(Request::get("/items/7").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(res.status(), StatusCode::OK);
    let body = to_bytes(res.into_body(), 64 * 1024).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["id"], 7);
}

#[tokio::test]
async fn zero_is_not_found() {
    let res = app().oneshot(Request::get("/items/0").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(res.status(), StatusCode::NOT_FOUND);
}
```

`oneshot` consumes the router; build a fresh one per request (cheap) or clone it. For several requests
against one router use `ServiceExt::ready` + `call`, or wrap state in `Arc` and rebuild.

## Fakes through traits in state

Put external dependencies behind a trait in `AppState` so tests swap in an in-memory fake:

```rust
use std::{collections::HashMap, sync::{Arc, Mutex}};
use axum::{extract::{Path, State}, http::StatusCode, routing::get, Router};

pub trait Prices: Send + Sync {
    fn price(&self, sku: &str) -> Option<u64>;
}

#[derive(Clone)]
pub struct AppState { prices: Arc<dyn Prices> }

async fn price(State(s): State<AppState>, Path(sku): Path<String>) -> Result<String, StatusCode> {
    s.prices.price(&sku).map(|p| p.to_string()).ok_or(StatusCode::NOT_FOUND)
}

pub fn router(state: AppState) -> Router {
    Router::new().route("/price/{sku}", get(price)).with_state(state)
}

#[derive(Default)]
struct FakePrices(Mutex<HashMap<String, u64>>);

impl Prices for FakePrices {
    fn price(&self, sku: &str) -> Option<u64> {
        self.0.lock().unwrap().get(sku).copied()
    }
}

#[tokio::test]
async fn uses_the_fake() {
    use axum::{body::Body, http::Request};
    use tower::ServiceExt;
    let fake = FakePrices::default();
    fake.0.lock().unwrap().insert("apple".into(), 42);
    let app = router(AppState { prices: Arc::new(fake) });
    let res = app.oneshot(Request::get("/price/apple").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(res.status(), StatusCode::OK);
}
```

For async dependencies use `async fn` in the trait with a `Send` bound on the returned future (see
send-static-and-compile-errors.md) or a boxed future, so `Arc<dyn Trait>` stays possible.

## Cancellation and shutdown

```rust
use std::time::Duration;
use tokio_util::{sync::CancellationToken, task::TaskTracker};

fn spawn_worker(tracker: &TaskTracker, token: CancellationToken) {
    tracker.spawn(async move {
        let mut tick = tokio::time::interval(Duration::from_secs(1));
        loop {
            tokio::select! {
                _ = token.cancelled() => break,
                _ = tick.tick() => {}
            }
        }
    });
}

#[tokio::test(start_paused = true)]
async fn workers_stop_on_cancel() {
    let (tracker, token) = (TaskTracker::new(), CancellationToken::new());
    for _ in 0..3 {
        spawn_worker(&tracker, token.child_token());
    }
    token.cancel();
    tracker.close();
    tokio::time::timeout(Duration::from_secs(1), tracker.wait()).await.expect("workers stopped");
    assert!(tracker.is_empty());
}
```

Test that a dropped future cleans up (cancellation by drop) with a guard type whose `Drop` records it, and
abort a `JoinHandle` to check `JoinError::is_cancelled()`.

## Channels and backpressure

```rust
use tokio::sync::mpsc::{self, error::TrySendError};

#[tokio::test]
async fn bounded_channel_pushes_back() {
    let (tx, mut rx) = mpsc::channel::<u32>(2);
    tx.try_send(1).unwrap();
    tx.try_send(2).unwrap();
    assert!(matches!(tx.try_send(3), Err(TrySendError::Full(3)))); // producer must wait or drop
    assert_eq!(rx.recv().await, Some(1));
    tx.try_send(3).unwrap(); // room again
}
```

## Send assertions

`tokio::spawn` needs `Send` futures; catch regressions in your crate rather than at the spawn site:

```rust
fn assert_send<T: Send>(_: &T) {}

async fn handler_logic(state: std::sync::Arc<std::sync::Mutex<Vec<u32>>>) {
    {
        let mut g = state.lock().unwrap();
        g.push(1);
    } // guard dropped before the await
    tokio::task::yield_now().await;
}

#[test]
fn handler_future_is_send() {
    let fut = handler_logic(Default::default());
    assert_send(&fut); // fails to compile if a !Send value lives across an .await
}
```

## End-to-end over a real port

Bind to port 0 so tests run in parallel, then talk HTTP. Useful for middleware that needs a real connection
(TLS, timeouts on the socket, graceful shutdown).

```rust,ignore
#[tokio::test]
async fn serves_over_tcp() {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let token = tokio_util::sync::CancellationToken::new();
    let server = tokio::spawn({
        let token = token.clone();
        async move {
            axum::serve(listener, app()).with_graceful_shutdown(token.cancelled_owned()).await.unwrap();
        }
    });
    let body = reqwest::get(format!("http://{addr}/healthz")).await.unwrap().text().await.unwrap();
    assert_eq!(body, "ok");
    token.cancel();
    server.await.unwrap(); // graceful shutdown completed
}
```

## Databases and HTTP dependencies

- **sqlx**: `#[sqlx::test]` creates a fresh test database per test (from `DATABASE_URL`) and runs migrations;
  the test receives a `PgPool`. Keep pure logic out of the database layer so most tests do not need it.
- **HTTP upstreams**: `wiremock` starts a local mock server per test (`Mock::given(method("GET")).respond_with(..)`);
  point the client's base URL at `mock_server.uri()`.
- Never call real third-party services from unit tests; use contract tests in a separate job.

## Checklist

| Behaviour | Test |
|-----------|------|
| Handler status codes and JSON | `oneshot` against the router |
| Timeouts, retries, intervals | `start_paused = true`, assert virtual elapsed time |
| Graceful shutdown | cancel the token, `tracker.wait()` under a timeout |
| Backpressure | bounded channel `try_send` returns `Full` |
| Futures stay `Send` | `assert_send(&fut)` compile-time check |
| Middleware on a real socket | bind `127.0.0.1:0`, request, cancel, await the server task |
| External services | fakes behind traits; wiremock for HTTP; `#[sqlx::test]` for SQL |
