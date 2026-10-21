# Boundaries: HTTP, Retries, Async, Threads, FFI and no_std

Where errors leave your code they must change shape: into an HTTP response, a gRPC status, a retry
decision, an exit code, an FFI return code. This file covers each boundary and the Send/Sync/'static
requirements that async and threads impose.

## Contents

- [1. HTTP: an ApiError for axum](#1-http-an-apierror-for-axum)
- [2. Status code mapping](#2-status-code-mapping)
- [3. Not leaking internals](#3-not-leaking-internals)
- [4. Extractor rejections and validation](#4-extractor-rejections-and-validation)
- [5. gRPC with tonic](#5-grpc-with-tonic)
- [6. Retryable classification](#6-retryable-classification)
- [7. A retry loop](#7-a-retry-loop)
- [8. Async: Send, Sync and 'static](#8-async-send-sync-and-static)
- [9. Tasks and threads: JoinError and panics](#9-tasks-and-threads-joinerror-and-panics)
- [10. Panic policy](#10-panic-policy)
- [11. FFI](#11-ffi)
- [12. no_std](#12-no_std)

## 1. HTTP: an ApiError for axum

axum handlers return anything that implements `IntoResponse`; `Result<T, E>` does when both `T` and `E`
do. So the whole HTTP error story is one enum and one impl. (Examples use axum 0.8; route paths use
`/{id}` in 0.8 and `/:id` in 0.7. `IntoResponse` is the same in both.)

```rust,ignore
use anyhow::Context;
use axum::{
    extract::{Path, State},
    http::{header, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("{resource} {id} not found")]
    NotFound { resource: &'static str, id: String },

    #[error("invalid {field}: {reason}")]
    Validation { field: &'static str, reason: String },

    #[error("{0}")]
    Conflict(String),

    #[error("rate limited")]
    RateLimited { retry_after_secs: u64 },

    #[error("upstream {service} unavailable")]
    Unavailable { service: &'static str, #[source] source: anyhow::Error },

    #[error(transparent)]
    Internal(#[from] anyhow::Error),
}

impl ApiError {
    fn status(&self) -> StatusCode {
        match self {
            Self::NotFound { .. } => StatusCode::NOT_FOUND,
            Self::Validation { .. } => StatusCode::UNPROCESSABLE_ENTITY,
            Self::Conflict(_) => StatusCode::CONFLICT,
            Self::RateLimited { .. } => StatusCode::TOO_MANY_REQUESTS,
            Self::Unavailable { .. } => StatusCode::SERVICE_UNAVAILABLE,
            Self::Internal(_) => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    fn code(&self) -> &'static str {
        match self {
            Self::NotFound { .. } => "not_found",
            Self::Validation { .. } => "validation_failed",
            Self::Conflict(_) => "conflict",
            Self::RateLimited { .. } => "rate_limited",
            Self::Unavailable { .. } => "unavailable",
            Self::Internal(_) => "internal",
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = self.status();
        let message = if status.is_server_error() {
            // The only place this error is logged. {:#} on the anyhow source prints the whole chain.
            match &self {
                Self::Internal(err) | Self::Unavailable { source: err, .. } => {
                    tracing::error!(code = self.code(), error = %format!("{err:#}"), "request failed")
                }
                _ => tracing::error!(code = self.code(), error = %self, "request failed"),
            }
            "internal server error".to_owned()
        } else {
            self.to_string()
        };
        let body = Json(json!({ "error": { "code": self.code(), "message": message } }));
        match self {
            Self::RateLimited { retry_after_secs } => {
                (status, [(header::RETRY_AFTER, retry_after_secs.to_string())], body).into_response()
            }
            _ => (status, body).into_response(),
        }
    }
}

async fn get_order(State(db): State<Db>, Path(id): Path<u64>) -> Result<Json<Order>, ApiError> {
    let order = db
        .find_order(id)
        .await
        .context("querying orders")?                       // sqlx::Error -> anyhow -> ApiError::Internal
        .ok_or_else(|| ApiError::NotFound { resource: "order", id: id.to_string() })?;
    Ok(Json(order))
}

pub fn router(db: Db) -> Router {
    Router::new().route("/orders/{id}", get(get_order)).with_state(db)
}
```

Notes:

- `From` does not chain. `?` on `sqlx::Error` in a handler returning `ApiError` needs either a `#[from]
  sqlx::Error` variant or a hop through anyhow (`.context(..)?`). The second keeps the enum free of
  database types.
- Do **not** add a blanket `impl<E: Into<anyhow::Error>> From<E> for ApiError` (the pattern from axum's
  `anyhow-error-response` example) when `ApiError` derives `thiserror::Error`: `ApiError` itself is then
  `Into<anyhow::Error>`, which conflicts with the reflexive `From<T> for T` (E0119). That example works only
  because its error type does not implement `std::error::Error`.
- Library error enums can map themselves too: `scaffold_errors` generates `http_status()` for any spec with
  `"http": true`, and the axum `IntoResponse` impl for application specs. In a library, put that impl behind a
  cargo feature (`#[cfg(feature = "axum")]`) so the library does not force axum on its users.

## 2. Status code mapping

| Error meaning | Status | Retry-After | Body message |
|---------------|--------|-------------|--------------|
| malformed request, bad syntax | 400 Bad Request | | specific |
| semantically invalid input | 422 Unprocessable Entity (or 400) | | specific, per field |
| missing/invalid credentials | 401 Unauthorized (+ `WWW-Authenticate`) | | generic |
| authenticated but not allowed | 403 Forbidden (or 404 to hide existence) | | generic |
| resource does not exist | 404 Not Found | | specific |
| version/uniqueness conflict | 409 Conflict | | specific |
| precondition (If-Match) failed | 412 Precondition Failed | | specific |
| payload too large | 413 Content Too Large | | limit |
| rate limited / quota | 429 Too Many Requests | yes | generic |
| bug, unexpected failure | 500 Internal Server Error | | generic only |
| dependency returned garbage | 502 Bad Gateway | | generic |
| dependency down, overloaded, shutting down | 503 Service Unavailable | optional | generic |
| dependency timed out | 504 Gateway Timeout | | generic |

Rules: 4xx means "the client can fix this" and the message should help them; 5xx means "we failed" and the
message must not reveal internals.

## 3. Not leaking internals

Things that must never reach a client: SQL text and constraint names, file system paths, hostnames and
ports of internal services, stack traces, `Debug` output of errors, secrets in URLs.

- Build the body from `code()` and, for 4xx only, `to_string()` of variants whose messages you wrote for
  clients. For 5xx always send a fixed message.
- Include a request id (from a `tower-http` request-id layer or your tracing span) in the body and the log
  line, so support can correlate.
- Keep the `Debug` derive for logs, but never `format!("{err:?}")` into a response.
- Validation messages are data you produce, not echoes of parser internals:
  `"invalid email: missing @"` rather than serde's full error text with byte offsets of the internal
  struct.

## 4. Extractor rejections and validation

Extractors (`Json`, `Path`, `Query`) reject bad input before your handler runs, with axum's own plain-text
responses. To return your JSON error shape, take the `Result` of the extractor:

```rust,ignore
use axum::{extract::{rejection::JsonRejection, State}, http::StatusCode, Json};
use anyhow::Context;

impl From<JsonRejection> for ApiError {
    fn from(rejection: JsonRejection) -> Self {
        ApiError::Validation { field: "body", reason: rejection.body_text() }
    }
}

async fn create_order(
    State(db): State<Db>,
    payload: Result<Json<NewOrder>, JsonRejection>,
) -> Result<(StatusCode, Json<Order>), ApiError> {
    let Json(new) = payload?;                                   // rejection -> ApiError::Validation
    if new.quantity == 0 {
        return Err(ApiError::Validation { field: "quantity", reason: "must be at least 1".into() });
    }
    let order = db.insert_order(&new).await.context("inserting order")?;
    Ok((StatusCode::CREATED, Json(order)))
}
```

(`let-else` and `let Json(new) = payload?` destructuring are stable; `let-else` since Rust 1.65.)

## 5. gRPC with tonic

```rust,ignore
impl From<ApiError> for tonic::Status {
    fn from(err: ApiError) -> Self {
        match err {
            ApiError::NotFound { .. } => tonic::Status::not_found(err.to_string()),
            ApiError::Validation { .. } => tonic::Status::invalid_argument(err.to_string()),
            ApiError::Conflict(_) => tonic::Status::aborted(err.to_string()),
            ApiError::RateLimited { .. } => tonic::Status::resource_exhausted("rate limited"),
            ApiError::Unavailable { .. } => tonic::Status::unavailable("dependency unavailable"),
            ApiError::Internal(e) => {
                tracing::error!(error = %format!("{e:#}"), "rpc failed");
                tonic::Status::internal("internal error")
            }
        }
    }
}
```

## 6. Retryable classification

Decide retryability where the error is created or translated, expose it as `is_retryable()`, and let
generic retry code ask the error.

| Source | Retryable | Not retryable |
|--------|-----------|---------------|
| `std::io::Error` kinds | `Interrupted`, `WouldBlock`, `TimedOut`, `ConnectionReset`, `ConnectionAborted`, `ConnectionRefused` (service restarting) | `NotFound`, `PermissionDenied`, `InvalidInput`, `InvalidData`, `AlreadyExists`, `UnexpectedEof` (usually corrupt data) |
| `reqwest::Error` | `is_timeout()`, `is_connect()`, status 429, 502, 503, 504 | status 400-428, 430-499, `is_decode()`, `is_builder()` |
| `sqlx::Error` | `PoolTimedOut`, `Io(_)`, database codes for serialization failure / deadlock (Postgres `40001`, `40P01`) | `RowNotFound`, unique violation (`23505`) -> Conflict, `ColumnDecode` |
| HTTP you serve | 429, 503 | other 4xx |
| your domain | `Busy`, `Conflict` in optimistic concurrency (after re-read), `Timeout` | `NotFound`, `Validation`, `Corrupted` |

```rust,ignore
impl From<reqwest::Error> for FetchError {
    fn from(err: reqwest::Error) -> Self {
        let retryable = err.is_timeout()
            || err.is_connect()
            || err.status().is_some_and(|s| s.as_u16() == 429 || s.is_server_error());
        FetchError::Http { retryable, source: err }
    }
}

fn classify_db(err: sqlx::Error) -> StoreError {
    match &err {
        sqlx::Error::RowNotFound => StoreError::NotFound,
        sqlx::Error::Database(db) if db.code().as_deref() == Some("23505") => StoreError::Duplicate,
        sqlx::Error::Database(db) if matches!(db.code().as_deref(), Some("40001" | "40P01")) => {
            StoreError::Transient { source: err }
        }
        sqlx::Error::PoolTimedOut | sqlx::Error::Io(_) => StoreError::Transient { source: err },
        _ => StoreError::Backend { source: err },
    }
}
```

Only retry **idempotent** operations (GET, PUT with the same body, inserts with an idempotency key). A
timeout on a non-idempotent POST may have succeeded on the server.

## 7. A retry loop

```rust,ignore
use std::{future::Future, time::Duration};

pub async fn retry<T, F, Fut>(mut op: F, max_attempts: u32) -> Result<T, StoreError>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = Result<T, StoreError>>,
{
    let mut delay = Duration::from_millis(100);
    let mut attempt = 1;
    loop {
        match op().await {
            Err(err) if err.is_retryable() && attempt < max_attempts => {
                tracing::warn!(attempt, error = %err, "transient failure, retrying");
                // add jitter in production (e.g. delay * random 0.5..1.5) to avoid synchronized retries
                tokio::time::sleep(delay).await;
                delay = (delay * 2).min(Duration::from_secs(10));
                attempt += 1;
            }
            result => return result,
        }
    }
}

// usage
let user = retry(|| store.get_user(id), 5).await?;
```

Crates such as `backon` or `tokio-retry` provide jittered backoff policies; the important part is that the
predicate is `err.is_retryable()`, not a string match on the message.

## 8. Async: Send, Sync and 'static

`tokio::spawn` requires the future to be `Send + 'static`. Every value held across an `.await` becomes part
of the future's state, including errors:

```rust,ignore
// does not compile when spawned:
async fn sync_once() -> Result<(), Box<dyn std::error::Error>> {
    let data = fetch().await?;
    store(data).await?;
    Ok(())
}
// error: future cannot be sent between threads safely
//        ... `dyn std::error::Error` cannot be sent between threads safely
```

Fix: `Box<dyn std::error::Error + Send + Sync>` (alias `BoxError`), a thiserror enum whose fields are all
`Send + Sync`, or `anyhow::Error` (always `Send + Sync`).

Checklist for error types used in async code:

- No `Rc`, `RefCell`, raw pointers, or `MutexGuard` inside the error.
- No borrowed data (`&'a str`): errors must be `'static` to be boxed as `dyn Error + 'static` and to leave
  spawned tasks.
- Compile-time check (the scaffold generates it):

```rust,ignore
#[test]
fn error_is_send_sync_static() {
    fn assert_bounds<T: std::error::Error + Send + Sync + 'static>() {}
    assert_bounds::<StoreError>();
}
```

Cancellation is not an error in Rust async: a dropped future simply stops at its last `.await`. Do not
model "cancelled" as an error variant unless your API explicitly exposes cancellation (e.g. a
`CancellationToken` check that returns `Err(Cancelled)`).

## 9. Tasks and threads: JoinError and panics

```rust,ignore
let handle = tokio::spawn(async move { index_batch(batch).await });
match handle.await {
    Ok(Ok(count)) => tracing::info!(count, "batch indexed"),
    Ok(Err(err)) => return Err(err).context("indexing batch"),          // task returned an error
    Err(join_err) if join_err.is_panic() => {
        return Err(anyhow::anyhow!("indexer task panicked"));            // bug: report loudly
    }
    Err(join_err) => return Err(join_err).context("indexer task cancelled"),
}
```

`tokio::task::JoinError` implements `std::error::Error`, so `.context()`/`?` work on it. With
`JoinSet`, `join_next().await` yields `Option<Result<T, JoinError>>`.

Threads:

```rust,ignore
let handle = std::thread::spawn(move || compress(&input));
let output = match handle.join() {
    Ok(result) => result?,                       // thread's own Result
    Err(payload) => {
        let msg = payload
            .downcast_ref::<&str>()
            .map(|s| s.to_string())
            .or_else(|| payload.downcast_ref::<String>().cloned())
            .unwrap_or_else(|| "non-string panic payload".into());
        anyhow::bail!("compression thread panicked: {msg}");
    }
};
```

`JoinHandle::join` returns `Err(Box<dyn Any + Send>)` when the thread panicked; the payload is usually a
`&'static str` or `String`.

## 10. Panic policy

| Situation | Policy |
|-----------|--------|
| Invalid input, I/O, network, missing data | `Result` |
| Violated internal invariant (index out of sync, impossible state) | panic with `expect("<invariant>")` and fix the bug |
| Library API misuse that cannot be expressed in types (e.g. zero chunk size) | either `Result` or documented panic (`# Panics` section), like `slice::chunks(0)` |
| `Mutex` poisoning | usually `lock().expect("<name> mutex poisoned")`; or recover with `unwrap_or_else(PoisonError::into_inner)` |
| Tests, examples, build scripts | `unwrap`/`expect` freely |
| Server request handling | never let a panic be the error path; tower-http's `CatchPanicLayer` turns panics into 500s as a safety net, not a strategy |

`[profile.release] panic = "abort"` makes every panic terminate the process immediately: `catch_unwind`,
`JoinError::is_panic` recovery and `CatchPanicLayer` stop working. Choose it only for binaries that would
rather crash than continue.

## 11. FFI

Panics must not unwind into C. Since Rust 1.81, a panic escaping an `extern "C"` function aborts the
process. Catch at the boundary and translate to an error code:

```rust,ignore
use std::ffi::{c_char, c_int, CStr};
use std::panic::{catch_unwind, AssertUnwindSafe};

pub const KV_OK: c_int = 0;
pub const KV_NOT_FOUND: c_int = 1;
pub const KV_INVALID_ARG: c_int = 2;
pub const KV_INTERNAL: c_int = -1;

/// # Safety
/// `key` must be a valid NUL-terminated string; `out` must be valid for writes.
#[unsafe(no_mangle)] // edition 2024 syntax; plain #[no_mangle] on edition 2021
pub unsafe extern "C" fn kv_get(key: *const c_char, out: *mut u64) -> c_int {
    let result = catch_unwind(AssertUnwindSafe(|| {
        if key.is_null() || out.is_null() {
            return KV_INVALID_ARG;
        }
        // SAFETY: checked non-null above; caller guarantees NUL termination and validity.
        let key = match unsafe { CStr::from_ptr(key) }.to_str() {
            Ok(k) => k,
            Err(_) => return KV_INVALID_ARG,
        };
        match store().get(key) {
            Ok(v) => {
                // SAFETY: checked non-null; caller guarantees `out` is writable.
                unsafe { *out = v };
                KV_OK
            }
            Err(StoreError::NotFound { .. }) => KV_NOT_FOUND,
            Err(err) => {
                set_last_error(format!("{err}"));   // thread-local message for kv_last_error()
                KV_INTERNAL
            }
        }
    }));
    result.unwrap_or(KV_INTERNAL)
}
```

- Use `extern "C-unwind"` (Rust 1.71+) only when the foreign caller is prepared for unwinding (e.g. C++
  with matching exceptions); otherwise `extern "C"` + `catch_unwind`.
- Provide a thread-local "last error" string accessor for detail, like `errno` + `strerror`.

## 12. no_std

`core::error::Error` is stable since Rust 1.81; `std::error::Error` is a re-export of it.

```rust
#![no_std]

use core::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum FrameError {
    TooShort { len: usize },
    BadChecksum { expected: u16, actual: u16 },
}

impl fmt::Display for FrameError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TooShort { len } => write!(f, "frame too short ({len} bytes)"),
            Self::BadChecksum { expected, actual } => {
                write!(f, "checksum mismatch: expected {expected:#06x}, got {actual:#06x}")
            }
        }
    }
}

impl core::error::Error for FrameError {}
```

With thiserror 2 the same is a derive:

```toml
[dependencies]
thiserror = { version = "2", default-features = false }   # no_std; needs Rust 1.81+
```

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, thiserror::Error)]
#[non_exhaustive]
pub enum FrameError {
    #[error("frame too short ({len} bytes)")]
    TooShort { len: usize },
    #[error("checksum mismatch: expected {expected:#06x}, got {actual:#06x}")]
    BadChecksum { expected: u16, actual: u16 },
}
```

anyhow supports `no_std` with `default-features = false` but needs a global allocator (`alloc`). Small,
`Copy` error enums without allocation are the norm in embedded code; they also make `PartialEq`-based
tests possible.
