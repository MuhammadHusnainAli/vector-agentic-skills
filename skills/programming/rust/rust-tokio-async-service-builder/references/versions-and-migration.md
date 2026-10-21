# Versions and Migration

Crate versions this skill targets, what changed between the releases people still run, and how to migrate.
Check `Cargo.lock` before advising: many "it does not compile" questions are version mismatches.

## Contents

- [Version matrix](#version-matrix)
- [axum 0.6 -> 0.7](#axum-06---07)
- [axum 0.7 -> 0.8](#axum-07---08)
- [tower and tower-http](#tower-and-tower-http)
- [tokio 1.x](#tokio-1x)
- [tokio-util](#tokio-util)
- [Rust editions and language features](#rust-editions-and-language-features)
- [Mismatch symptoms](#mismatch-symptoms)

## Version matrix

| Crate | Version used here | Pairs with |
|-------|-------------------|------------|
| tokio | 1.x | everything below |
| axum | 0.8 | hyper 1, tower 0.5, tower-http 0.6 |
| tower | 0.5 | axum 0.8 (`ServiceExt` needs the `util` feature) |
| tower-http | 0.6 | axum 0.8 (each layer is a cargo feature: `trace`, `timeout`, `cors`, `limit`, ...) |
| tokio-util | 0.7 | `CancellationToken` (default), `TaskTracker` (feature `rt`) |
| hyper | 1.x | axum 0.7+, reqwest 0.12 |
| reqwest | 0.12 | hyper 1 |
| tracing-subscriber | 0.3 | features `env-filter`, `json` |
| sqlx | 0.8 | runtime feature `runtime-tokio` (+ a TLS feature for remote DBs) |

Mixing majors (tower-http 0.5 with axum 0.8, or two hyper majors) produces trait errors that look unrelated
to versions: "the trait `Service<Request<Body>>` is not implemented", "expected `axum::body::Body`, found
`hyper::Body`".

## axum 0.6 -> 0.7

axum 0.7 moved to hyper 1.0:

- `axum::Server::bind(..).serve(app.into_make_service())` is gone: use
  `axum::serve(tokio::net::TcpListener::bind(addr).await?, app).await?`.
- Request/response bodies are `axum::body::Body` (no generic body type parameter on handlers and middleware).
- Middleware written against `hyper::Body` must be ported; `tower-http` 0.5 pairs with axum 0.7.
- Graceful shutdown: `axum::serve(..).with_graceful_shutdown(signal)`.

## axum 0.7 -> 0.8

axum 0.8 (released January 2025) changes, in the order you will hit them:

| Change | Before (0.7) | After (0.8) |
|--------|--------------|-------------|
| Path parameter syntax | `"/users/:id"`, `"/files/*path"` | `"/users/{id}"`, `"/files/{*path}"`; old syntax panics at startup ("Path segments must not start with `:`") |
| Custom extractors | `#[async_trait] impl FromRequestParts<S> for X` | plain `impl FromRequestParts<S> for X` with `async fn` (native async fn in traits) |
| `Option<T>` extractor | any rejection became `None` | requires `OptionalFromRequestParts`/`OptionalFromRequest`; rejections now propagate |
| `Host` extractor | `axum::extract::Host` | moved to `axum-extra` |
| WebSocket messages | `String` / `Vec<u8>` payloads | `Utf8Bytes` / `Bytes` |
| MSRV | 1.66 | 1.75 |

Migration steps: bump `axum = "0.8"`, `tower-http = "0.6"`, `tower = "0.5"`; run the `service_hygiene` scanner
(TK017 finds old paths); delete `#[async_trait]` on extractor impls; fix `Option<..>` extractors; run tests.

## tower and tower-http

- tower 0.5 removed some re-exports and reorganised `ServiceExt`; enable `features = ["util"]` for
  `oneshot`/`ready`.
- tower-http 0.6: every middleware is behind a feature. Newer 0.6 releases deprecate `TimeoutLayer::new(d)` in
  favour of `TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, d)`.
- Layer order in `ServiceBuilder` is outermost first. `TimeoutLayer` requires a `Default` response body, so
  put `RequestBodyLimitLayer` before it (outside), not after.
- tower's own `tower::timeout::TimeoutLayer` returns an error instead of a response; with axum it needs
  `HandleErrorLayer`. Prefer tower-http's.

## tokio 1.x

- tokio 1.x is stable: minor releases add APIs without breaking. It publishes long-term-support minor
  versions (listed in its README); pin with `tokio = "~1.NN"` only if your policy needs an LTS line.
- Feature flags: `full` for applications; libraries should enable only what they use (`rt`, `macros`, `net`,
  `time`, `sync`, `signal`, `fs`, `process`, `io-util`). Tests that pause time need `test-util`.
- `JoinSet` (tokio::task) manages a dynamic group of tasks and aborts them on drop; `JoinHandle::abort` and
  `AbortHandle` cancel single tasks.
- `tokio::task::spawn_blocking` has its own large thread pool (default up to 512 threads); CPU-heavy work
  belongs on rayon or a bounded pool instead.
- `tokio-console` needs `RUSTFLAGS="--cfg tokio_unstable"` and the `console-subscriber` crate.

## tokio-util

- `sync::CancellationToken`: hierarchical cancellation (`child_token`, `cancelled().await`,
  `cancelled_owned()` for `'static` futures), always available.
- `task::TaskTracker` (feature `rt`): track spawned tasks, `close()` then `wait()` for graceful shutdown; unlike
  `JoinSet` it does not abort on drop and does not keep results.
- `codec` (feature `codec`): `Framed`, `LinesCodec`, `LengthDelimitedCodec`, the cancel-safe way to read framed
  protocols inside `select!` loops.

## Rust editions and language features

| Rust | Feature | Effect on async services |
|------|---------|--------------------------|
| 1.75 | `async fn` and `-> impl Trait` in traits | async repository/service traits without `async-trait` (add a `Send` story) |
| 1.80 | `LazyLock` | static config/regex without `once_cell` |
| 1.82 | precise capturing `use<..>` | control what `-> impl Future` borrows |
| 1.85 | edition 2024; async closures (`async \|x\| ..`, `AsyncFn*`) | RPIT captures all lifetimes; `if let` temporaries (lock guards) drop before `else` |

Edition 2024 `if let` rescoping helps services: `if let Some(v) = map.lock().unwrap().get(k) { .. } else { .. }`
no longer holds the guard in the `else` branch.

## Mismatch symptoms

| Error | Likely mismatch | Fix |
|-------|-----------------|-----|
| `Path segments must not start with ':'` (panic at startup) | axum 0.8 with 0.7 paths | `{id}` syntax (TK017) |
| `the trait bound ..: Handler<_, _>` is not satisfied | handler signature (extractor order, non-`Send` future, wrong body type) | `#[axum::debug_handler]` on the handler (feature `macros`) |
| `no method named oneshot` | tower `util` feature off | `tower = { version = "0.5", features = ["util"] }` |
| `start_paused` / `time::pause` not found | tokio `test-util` feature off | add it to dev-dependencies |
| `could not find TaskTracker in task` | tokio-util `rt` feature off | `tokio-util = { version = "0.7", features = ["rt"] }` |
| Two versions of `http`/`hyper` in `cargo tree -d` | crates on different majors | align axum/tower-http/reqwest majors |
