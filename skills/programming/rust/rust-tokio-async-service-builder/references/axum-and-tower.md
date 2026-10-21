# axum 0.8 and tower Middleware

Routing, extractors, state, error mapping and middleware for axum 0.8 on tower 0.5 and tower-http 0.6.

## Contents

- [Cargo setup](#cargo-setup)
- [Routing](#routing)
- [Extractors and their order](#extractors-and-their-order)
- [State](#state)
- [Custom extractors (0.8 style)](#custom-extractors-08-style)
- [Error type and IntoResponse](#error-type-and-intoresponse)
- [Rejections: making extractor errors JSON](#rejections-making-extractor-errors-json)
- [Middleware with tower-http](#middleware-with-tower-http)
- [Layer ordering](#layer-ordering)
- [Concurrency limits and load shedding](#concurrency-limits-and-load-shedding)
- [Body size limits](#body-size-limits)
- [Writing middleware with from_fn](#writing-middleware-with-from_fn)
- [Health and readiness](#health-and-readiness)
- [Serving: listeners, ConnectInfo, nesting](#serving-listeners-connectinfo-nesting)
- [Streaming and WebSockets](#streaming-and-websockets)

## Cargo setup

```toml
[dependencies]
axum = { version = "0.8", features = ["macros"] }   # "macros" for #[debug_handler]; default features include json, query, tokio, http1
tokio = { version = "1", features = ["macros", "rt-multi-thread", "net", "signal", "time"] }
tower = { version = "0.5", features = ["util", "limit", "load-shed", "timeout"] }
tower-http = { version = "0.6", features = ["trace", "timeout", "cors", "compression-gzip", "limit",
                                            "request-id", "catch-panic", "sensitive-headers"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "2"
tracing = "0.1"
```

Only enable the tower-http features you use; each is a separate module (`tower_http::cors`, `::timeout`, ...).

## Routing

```rust,ignore
use axum::{Router, routing::{get, post}};

fn api_router() -> Router<AppStateRef> {
    Router::new()
        .route("/orders", get(list_orders).post(create_order))       // several methods, one path
        .route("/orders/{id}", get(get_order).delete(delete_order))   // capture
        .route("/files/{*path}", get(serve_file))                     // wildcard (rest of path)
        .route("/users/{user_id}/orders/{order_id}", get(user_order)) // several captures
}

fn app(state: AppStateRef) -> Router {
    Router::new()
        .nest("/api/v1", api_router())   // prefix
        .route("/healthz", get(|| async { "ok" }))
        .fallback(not_found)             // 404 for everything else
        .with_state(state)
}
```

- axum 0.8 path syntax: `{name}` captures one segment, `{*name}` the rest. `"/:id"` and `"/*rest"` panic
  when the router is built: run the app (or a router test) once after upgrading. Literal braces: `{{` / `}}`.
- Overlapping routes (same path registered twice) panic at startup; that is a feature: build the router in
  a unit test so CI catches it.
- `Router<S>` means "needs state S"; `.with_state(s)` turns it into `Router<()>`, the only type
  `axum::serve` accepts. Error "expected `Router`, found `Router<Arc<AppState>>`" = missing `with_state`.
- Handlers are `async fn`s whose arguments implement `FromRequestParts`/`FromRequest` and whose return type
  implements `IntoResponse`. Closures work too: `get(|| async { "ok" })`.

## Extractors and their order

| Extractor | Gets | Rejection status |
|-----------|------|------------------|
| `Path<T>` (`Path<u64>`, `Path<(u64, String)>`, `Path<Params>`) | captures | 400 (bad parse) |
| `Query<T>` | query string | 400 |
| `State<S>` | app state | compile-time checked |
| `HeaderMap`, `TypedHeader<T>` (axum-extra) | headers | - / 400 |
| `Extension<T>` | value inserted by a layer | 500 if missing |
| `ConnectInfo<SocketAddr>` | peer address | needs `into_make_service_with_connect_info` |
| `Json<T>` | JSON body | 400 syntax, 415 content-type, 422 data |
| `Form<T>`, `Bytes`, `String`, `Multipart` | body | 400/415/413 |
| `Request` | the whole request | consumes everything |

**Body extractors (`FromRequest`) consume the request and must be the last argument.** Putting `Json<T>`
before `State` is the most common cause of `the trait bound ... Handler<_, _> is not satisfied`. Add
`#[axum::debug_handler]` to the handler to get a precise error.

```rust,ignore
use axum::{Json, extract::{Path, Query, State}, http::StatusCode};

#[derive(serde::Deserialize)]
struct Paging { limit: Option<u32>, cursor: Option<String> }

#[axum::debug_handler]
async fn create_order(
    State(state): State<AppStateRef>,
    Path(tenant): Path<String>,
    Query(paging): Query<Paging>,
    Json(input): Json<NewOrder>,      // last
) -> Result<(StatusCode, Json<Order>), AppError> {
    let order = state.repo.create(&tenant, input).await?;
    let _ = paging;
    Ok((StatusCode::CREATED, Json(order)))
}
```

`Option<Query<T>>`-style optional extractors changed in 0.8: `Option<T>` now requires `T:
OptionalFromRequestParts` and a malformed value is a rejection instead of `None`. For optional query fields,
prefer `Query<T>` with `Option<_>` fields as above.

## State

```rust,ignore
use std::sync::Arc;

pub struct AppState {
    pub db: sqlx::PgPool,
    pub http: reqwest::Client,
    pub config: Config,
}
pub type AppStateRef = Arc<AppState>;
```

- One `Arc<AppState>`: cloning the state per request is one atomic increment.
- `State` vs `Extension`: `State` is type-checked at compile time; `Extension` fails at runtime with 500 if
  the layer was not added. Prefer `State`.
- Substates: derive `FromRef` (feature `macros`) to let handlers extract a part of the state.

```rust
use axum::extract::FromRef;

#[derive(Clone, FromRef)]
struct AppState2 {
    db: sqlx::PgPool,
    http: reqwest::Client,
}

async fn ping_db(axum::extract::State(db): axum::extract::State<sqlx::PgPool>) -> &'static str {
    let _ = db;
    "ok"
}
```

With `FromRef` the state struct itself must be `Clone` (each field is cheap to clone here).

## Custom extractors (0.8 style)

axum 0.8 uses native `async fn` in traits: no `#[async_trait]` on the impl.

```rust
use axum::{
    extract::FromRequestParts,
    http::{StatusCode, request::Parts},
};

pub struct ApiKey(pub String);

impl<S: Send + Sync> FromRequestParts<S> for ApiKey {
    type Rejection = (StatusCode, &'static str);

    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        parts
            .headers
            .get("x-api-key")
            .and_then(|v| v.to_str().ok())
            .map(|v| ApiKey(v.to_owned()))
            .ok_or((StatusCode::UNAUTHORIZED, "missing x-api-key"))
    }
}
```

To read app state inside an extractor, bound `S` with `AppStateRef: FromRef<S>` and call
`AppStateRef::from_ref(state)`.

## Error type and IntoResponse

One error enum per service (or per bounded context), mapped once:

```rust
use axum::{Json, http::StatusCode, response::{IntoResponse, Response}};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("{0} not found")]
    NotFound(&'static str),
    #[error("validation failed: {0}")]
    Validation(String),
    #[error("conflict: {0}")]
    Conflict(String),
    #[error("upstream timed out")]
    UpstreamTimeout,
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error(transparent)]
    Upstream(#[from] reqwest::Error),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code) = match &self {
            AppError::NotFound(_) => (StatusCode::NOT_FOUND, "not_found"),
            AppError::Validation(_) => (StatusCode::UNPROCESSABLE_ENTITY, "validation"),
            AppError::Conflict(_) => (StatusCode::CONFLICT, "conflict"),
            AppError::UpstreamTimeout => (StatusCode::GATEWAY_TIMEOUT, "upstream_timeout"),
            AppError::Upstream(e) if e.is_timeout() => (StatusCode::GATEWAY_TIMEOUT, "upstream_timeout"),
            AppError::Upstream(_) => (StatusCode::BAD_GATEWAY, "upstream"),
            AppError::Database(sqlx::Error::RowNotFound) => (StatusCode::NOT_FOUND, "not_found"),
            AppError::Database(sqlx::Error::PoolTimedOut) => (StatusCode::SERVICE_UNAVAILABLE, "busy"),
            AppError::Database(_) | AppError::Other(_) => (StatusCode::INTERNAL_SERVER_ERROR, "internal"),
        };
        let message = if status.is_server_error() {
            tracing::error!(error = ?self, "request failed"); // full detail in logs only
            "internal error".to_owned()
        } else {
            self.to_string()
        };
        (status, Json(json!({ "error": { "code": code, "message": message } }))).into_response()
    }
}
```

- Handlers return `Result<impl IntoResponse, AppError>` and use `?` everywhere.
- Log 5xx in one place (here) with the full chain; never return internal messages to clients.
- `anyhow` is fine as a catch-all variant; keep variants that need specific status codes explicit.

## Rejections: making extractor errors JSON

Built-in rejections return plain text. Wrap the extractor to keep one error format:

```rust
use axum::{extract::{FromRequest, rejection::JsonRejection}, response::{IntoResponse, Response}};

#[derive(FromRequest)]
#[from_request(via(axum::Json), rejection(ApiError))]
pub struct ApiJson<T>(pub T);

pub struct ApiError(JsonRejection);

impl From<JsonRejection> for ApiError {
    fn from(r: JsonRejection) -> Self { ApiError(r) }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let status = self.0.status();
        (status, axum::Json(serde_json::json!({ "error": { "code": "bad_request", "message": self.0.body_text() } })))
            .into_response()
    }
}
```

The `FromRequest` derive needs the `macros` feature. Implementing `IntoResponse` for `ApiJson<T>` as well
lets handlers return it.

## Middleware with tower-http

```rust
use std::time::Duration;
use axum::http::{HeaderName, HeaderValue, Method, StatusCode, header};
use tower::ServiceBuilder;
use tower_http::{
    catch_panic::CatchPanicLayer,
    compression::CompressionLayer,
    cors::CorsLayer,
    request_id::{MakeRequestUuid, PropagateRequestIdLayer, SetRequestIdLayer},
    sensitive_headers::SetSensitiveRequestHeadersLayer,
    timeout::TimeoutLayer,
    trace::TraceLayer,
};

fn with_middleware(router: axum::Router) -> axum::Router {
    let x_request_id = HeaderName::from_static("x-request-id");
    let cors = CorsLayer::new()
        .allow_origin("https://app.example.com".parse::<HeaderValue>().expect("valid origin"))
        .allow_methods([Method::GET, Method::POST, Method::DELETE])
        .allow_headers([header::CONTENT_TYPE, header::AUTHORIZATION])
        .max_age(Duration::from_secs(600));

    router.layer(
        ServiceBuilder::new()
            .layer(SetSensitiveRequestHeadersLayer::new([header::AUTHORIZATION, header::COOKIE]))
            .layer(SetRequestIdLayer::new(x_request_id.clone(), MakeRequestUuid))
            .layer(TraceLayer::new_for_http())
            .layer(PropagateRequestIdLayer::new(x_request_id))
            .layer(CatchPanicLayer::new())
            .layer(TimeoutLayer::with_status_code(StatusCode::REQUEST_TIMEOUT, Duration::from_secs(10)))
            .layer(cors)
            .layer(CompressionLayer::new()),
    )
}
```

| Layer | Purpose | Notes |
|-------|---------|-------|
| `TraceLayer::new_for_http()` | span + events per request | customize with `make_span_with`, `on_response`, `on_failure` |
| `TimeoutLayer::new(d)` | 408 after `d` | newer 0.6 releases add `TimeoutLayer::with_status_code(status, d)` and deprecate `new`; tower's own `TimeoutLayer` returns an error that needs `HandleErrorLayer` |
| `CorsLayer` | CORS preflight + headers | `CorsLayer::permissive()` only for local dev; `allow_credentials(true)` cannot be combined with `Any` origins |
| `CompressionLayer` | gzip/br/zstd/deflate response bodies | enable `compression-gzip`, `compression-br`, ... or `compression-full` |
| `RequestBodyLimitLayer::new(n)` | 413 for bodies over `n` | put it *outside* `TimeoutLayer` (earlier in `ServiceBuilder`): `TimeoutLayer` needs a `Default` response body and the limit's body type is not, so the other order fails with ``ResponseBody<Body>: Default` is not satisfied`` |
| `CatchPanicLayer` | panic -> 500 | log the panic; still fix it |
| `SetRequestIdLayer` / `PropagateRequestIdLayer` | `x-request-id` in and out | put `SetRequestId` before `TraceLayer` so the span can record it |
| `SetSensitiveRequestHeadersLayer` | redact secrets in traces | add before `TraceLayer` |

`Router::layer` only wraps routes added **before** the call; routes added after are not wrapped.
`Router::route_layer` wraps only matched routes (no effect on 404s), useful for auth.

## Layer ordering

With `ServiceBuilder`, layers run **top to bottom** on the request (the first `.layer` is the outermost).
With chained `Router::layer` calls, the **last** call is the outermost. Prefer `ServiceBuilder` to keep the
order readable.

```
request -> SetSensitiveHeaders -> SetRequestId -> Trace -> PropagateRequestId -> CatchPanic -> Timeout
        -> Cors -> Compression -> handler
```

Put tracing outside timeout so timed-out requests are traced with their 408; put request-id outside tracing;
put auth (`route_layer`) inside so 401s are traced.

## Concurrency limits and load shedding

- `tower::limit::ConcurrencyLimitLayer::new(n)`: each `layer()` call creates its own semaphore. `Router::layer`
  applies the layer to each route separately, so this becomes a per-route limit.
- `tower::limit::GlobalConcurrencyLimitLayer::new(n)`: one shared semaphore for everything it wraps: a true
  global cap through `Router::layer`.
- These limits make excess requests **wait**. To reject instead (fail fast under overload), add load shedding;
  its error must be converted with `HandleErrorLayer` because axum routes require infallible services:

```rust,ignore
use axum::{BoxError, error_handling::HandleErrorLayer, http::StatusCode};
use tower::{ServiceBuilder, limit::GlobalConcurrencyLimitLayer, load_shed::LoadShedLayer};

fn with_overload_protection(router: axum::Router) -> axum::Router {
    router.layer(
        ServiceBuilder::new()
            .layer(HandleErrorLayer::new(|_err: BoxError| async { StatusCode::SERVICE_UNAVAILABLE }))
            .layer(LoadShedLayer::new())                    // reject when the inner service is not ready
            .layer(GlobalConcurrencyLimitLayer::new(512)),  // at most 512 requests in handlers
    )
}
```

Bound upstream calls separately with a `Semaphore` in state; the router-level limit protects the process,
the per-upstream semaphore protects the dependency.

## Body size limits

- axum's body extractors (`Json`, `Form`, `Bytes`, `String`) apply a **default 2 MB limit**. Change it with
  `.layer(axum::extract::DefaultBodyLimit::max(10 * 1024 * 1024))` or turn it off with
  `DefaultBodyLimit::disable()`.
- `tower_http::limit::RequestBodyLimitLayer::new(n)` limits the body for everything including streaming
  handlers that read `Body` directly; it answers 413 when `Content-Length` is too large up front.
- Upload routes: disable the default for that route only and set a larger explicit limit.

```rust,ignore
use axum::{Router, extract::DefaultBodyLimit, routing::post};
use tower_http::limit::RequestBodyLimitLayer;

fn upload_routes() -> Router<AppStateRef> {
    Router::new()
        .route("/uploads", post(upload))
        .layer(DefaultBodyLimit::disable())
        .layer(RequestBodyLimitLayer::new(250 * 1024 * 1024))
}
```

## Writing middleware with from_fn

```rust,ignore
use axum::{extract::{Request, State}, http::StatusCode, middleware::{self, Next}, response::Response};

async fn require_api_key(
    State(state): State<AppStateRef>,
    req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let ok = req
        .headers()
        .get("x-api-key")
        .and_then(|v| v.to_str().ok())
        .is_some_and(|k| state.config.api_keys.iter().any(|known| known == k));
    if !ok {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(req).await)
}

fn protected(state: AppStateRef) -> axum::Router<AppStateRef> {
    axum::Router::new()
        .route("/admin/stats", axum::routing::get(stats))
        .route_layer(middleware::from_fn_with_state(state, require_api_key))
}
```

`from_fn` middleware: extractors first, `Request` second to last, `Next` last. Values for handlers go into
`req.extensions_mut().insert(..)` and come out with `Extension<T>`. Compare secrets in constant time
(`subtle` crate) in real code.

## Health and readiness

| Endpoint | Answers | Checks | Used by |
|----------|---------|--------|---------|
| `/healthz` (liveness) | "the process is not wedged" | nothing external; returns 200 | restart policy |
| `/readyz` (readiness) | "send me traffic" | shutdown flag, DB ping with short timeout, critical caches warmed | load balancer / k8s endpoints |
| `/startupz` (optional) | "initialization done" | migrations ran, config loaded | k8s startupProbe |

```rust,ignore
use std::{sync::atomic::Ordering, time::Duration};
use axum::{extract::State, http::StatusCode};

async fn readyz(State(state): State<AppStateRef>) -> StatusCode {
    if state.shutting_down.load(Ordering::Relaxed) {
        return StatusCode::SERVICE_UNAVAILABLE;
    }
    let ping = sqlx::query("SELECT 1").execute(&state.db);
    match tokio::time::timeout(Duration::from_millis(500), ping).await {
        Ok(Ok(_)) => StatusCode::OK,
        _ => StatusCode::SERVICE_UNAVAILABLE,
    }
}
```

Never make liveness depend on the database: a DB outage would restart every pod and turn a partial outage
into a full one.

## Serving: listeners, ConnectInfo, nesting

```rust
use std::net::SocketAddr;
use axum::extract::ConnectInfo;

async fn whoami(ConnectInfo(addr): ConnectInfo<SocketAddr>) -> String {
    addr.to_string()
}

async fn run(app: axum::Router) -> anyhow::Result<()> {
    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
    axum::serve(listener, app.into_make_service_with_connect_info::<SocketAddr>())
        .with_graceful_shutdown(async { let _ = tokio::signal::ctrl_c().await; })
        .await?;
    Ok(())
}
```

- `axum::serve` is a simple HTTP/1 + HTTP/2 server on hyper 1 (`http1`/`http2` features). For TLS
  termination use a proxy/ingress, `axum-server` with rustls, or a hyper-util connection loop.
- axum 0.8 `serve` accepts any type implementing `axum::serve::Listener` (e.g. `tokio::net::UnixListener`).
- Behind a proxy the peer address is the proxy: read `X-Forwarded-For` only from trusted proxies.

## Streaming and WebSockets

- Server-sent events: `axum::response::sse::{Sse, Event, KeepAlive}` with a `Stream` of
  `Result<Event, Infallible>`; end the stream on shutdown (`futures::StreamExt::take_until(stream,
  token.cancelled_owned())`) or graceful shutdown waits for every open SSE connection.
- WebSockets: feature `ws`, `WebSocketUpgrade` extractor, `ws.on_upgrade(|socket| handle(socket, state))`.
  In 0.8 `Message::Text` carries `Utf8Bytes` and `Message::Binary` carries `Bytes`: use `.as_str()` / `.into()`
  conversions instead of `String`/`Vec<u8>`.
- Split a socket into sender/receiver (`socket.split()` via `futures::StreamExt`) and run them as two tasks
  in a `JoinSet` so either side ending aborts the other.
