// Fixture for the rust-tokio-async-service-builder scanners: the order service from tk_bad_service.rs, fixed.
// Expected: no findings with --strict.
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::Duration,
};

use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use tokio::{
    net::TcpListener,
    sync::{Semaphore, mpsc, oneshot, watch},
    task::JoinSet,
};
use tokio_util::{sync::CancellationToken, task::TaskTracker};
use tower::ServiceBuilder;
use tower_http::{timeout::TimeoutLayer, trace::TraceLayer};

#[derive(Clone, Debug, Serialize, Deserialize)]
struct Order {
    id: u64,
    sku: String,
    qty: u32,
}

#[derive(Clone, Debug)]
struct Config {
    pricing_url: String,
    max_upstream: usize,
}

// ---------------------------------------------------------------- actor

enum AuditCmd {
    Record(String),
    Count(oneshot::Sender<usize>),
}

#[derive(Clone)]
struct AuditHandle {
    tx: mpsc::Sender<AuditCmd>,
}

impl AuditHandle {
    fn spawn(tracker: &TaskTracker, token: CancellationToken) -> Self {
        let (tx, mut rx) = mpsc::channel::<AuditCmd>(1024);
        tracker.spawn(async move {
            let mut log: Vec<String> = Vec::new();
            loop {
                tokio::select! {
                    biased;
                    _ = token.cancelled() => break,
                    cmd = rx.recv() => match cmd {
                        Some(AuditCmd::Record(line)) => log.push(line),
                        Some(AuditCmd::Count(reply)) => { let _ = reply.send(log.len()); }
                        None => break,
                    },
                }
            }
            tracing::info!(entries = log.len(), "audit actor stopped");
        });
        Self { tx }
    }

    async fn record(&self, line: String) -> Result<(), AppError> {
        self.tx.send(AuditCmd::Record(line)).await.map_err(|_| AppError::Unavailable)
    }

    async fn count(&self) -> Result<usize, AppError> {
        let (reply, rx) = oneshot::channel();
        self.tx.send(AuditCmd::Count(reply)).await.map_err(|_| AppError::Unavailable)?;
        rx.await.map_err(|_| AppError::Unavailable)
    }
}

// ---------------------------------------------------------------- state + errors

struct AppState {
    orders: Mutex<HashMap<u64, Order>>,
    http: reqwest::Client,
    upstream: Semaphore,
    config: watch::Receiver<Config>,
    audit: AuditHandle,
    tracker: TaskTracker,
}

type Shared = Arc<AppState>;

fn build_http_client() -> reqwest::Result<reqwest::Client> {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .connect_timeout(Duration::from_secs(2))
        .pool_idle_timeout(Duration::from_secs(60))
        .build()
}

#[derive(Debug, thiserror::Error)]
enum AppError {
    #[error("order {0} not found")]
    NotFound(u64),
    #[error("dependency unavailable")]
    Unavailable,
    #[error("upstream error: {0}")]
    Upstream(#[from] reqwest::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = match &self {
            AppError::NotFound(_) => StatusCode::NOT_FOUND,
            AppError::Unavailable => StatusCode::SERVICE_UNAVAILABLE,
            AppError::Upstream(err) if err.is_timeout() => StatusCode::GATEWAY_TIMEOUT,
            AppError::Upstream(_) => StatusCode::BAD_GATEWAY,
        };
        (status, Json(serde_json::json!({ "error": self.to_string() }))).into_response()
    }
}

// ---------------------------------------------------------------- handlers

async fn get_order(State(state): State<Shared>, Path(id): Path<u64>) -> Result<Json<Order>, AppError> {
    let order = {
        let orders = state.orders.lock().expect("orders mutex poisoned");
        orders.get(&id).cloned()
    }; // guard dropped before any .await
    let order = order.ok_or(AppError::NotFound(id))?;
    let price = enrich(&state, &order.sku).await?;
    tracing::info!(price, "served order");
    Ok(Json(order))
}

async fn enrich(state: &AppState, sku: &str) -> Result<f64, AppError> {
    let _permit = state.upstream.acquire().await.map_err(|_| AppError::Unavailable)?;
    let base = state.config.borrow().pricing_url.clone();
    let price = state
        .http
        .get(format!("{base}/v1/{sku}"))
        .send()
        .await?
        .error_for_status()?
        .json::<f64>()
        .await?;
    Ok(price)
}

async fn create_order(State(state): State<Shared>, Json(order): Json<Order>) -> Result<StatusCode, AppError> {
    let rules = tokio::task::spawn_blocking(|| std::fs::read_to_string("/etc/orders/rules.toml"))
        .await
        .map_err(|_| AppError::Unavailable)?
        .unwrap_or_default();
    state.audit.record(format!("create {} ({} bytes of rules)", order.id, rules.len())).await?;
    state.orders.lock().expect("orders mutex poisoned").insert(order.id, order.clone());
    let http = state.http.clone();
    state.tracker.spawn(async move {
        if let Err(err) = notify_warehouse(&http, &order).await {
            tracing::warn!(error = %err, order = order.id, "warehouse notification failed");
        }
    });
    Ok(StatusCode::CREATED)
}

async fn notify_warehouse(http: &reqwest::Client, order: &Order) -> reqwest::Result<()> {
    http.post("https://warehouse.internal/v1/orders")
        .json(order)
        .send()
        .await?
        .error_for_status()?;
    Ok(())
}

async fn audit_count(State(state): State<Shared>) -> Result<Json<usize>, AppError> {
    Ok(Json(state.audit.count().await?))
}

async fn checksums(Json(blobs): Json<Vec<Vec<u8>>>) -> Result<Json<Vec<u64>>, AppError> {
    let mut set = JoinSet::new();
    for (i, blob) in blobs.into_iter().enumerate() {
        set.spawn_blocking(move || (i, blob.iter().map(|b| u64::from(*b)).sum::<u64>()));
    }
    let mut out = vec![0; set.len()];
    while let Some(res) = set.join_next().await {
        let (i, sum) = res.map_err(|_| AppError::Unavailable)?;
        out[i] = sum;
    }
    Ok(Json(out))
}

async fn healthz() -> &'static str {
    "ok"
}

// ---------------------------------------------------------------- server

fn router(state: Shared) -> Router {
    Router::new()
        .route("/orders/{id}", get(get_order))
        .route("/orders", post(create_order))
        .route("/audit/count", get(audit_count))
        .route("/checksums", post(checksums))
        .route("/healthz", get(healthz))
        .layer(
            ServiceBuilder::new()
                .layer(TraceLayer::new_for_http())
                .layer(TimeoutLayer::new(Duration::from_secs(10))),
        )
        .with_state(state)
}

async fn shutdown_signal(token: CancellationToken) {
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
    token.cancel();
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter(tracing_subscriber::EnvFilter::from_default_env()).init();

    let (config_tx, config_rx) = watch::channel(Config {
        pricing_url: std::env::var("PRICING_URL").unwrap_or_else(|_| "https://pricing.internal".into()),
        max_upstream: 32,
    });
    let token = CancellationToken::new();
    let tracker = TaskTracker::new();
    let max_upstream = config_rx.borrow().max_upstream;
    let state = Arc::new(AppState {
        orders: Mutex::new(HashMap::new()),
        http: build_http_client()?,
        upstream: Semaphore::new(max_upstream),
        config: config_rx,
        audit: AuditHandle::spawn(&tracker, token.child_token()),
        tracker: tracker.clone(),
    });

    let listener = TcpListener::bind("0.0.0.0:3000").await?;
    axum::serve(listener, router(state))
        .with_graceful_shutdown(shutdown_signal(token.clone()))
        .await?;

    drop(config_tx);
    token.cancel();
    tracker.close();
    tokio::time::timeout(Duration::from_secs(10), tracker.wait()).await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, http::Request};
    use tower::ServiceExt;

    #[tokio::test(start_paused = true)]
    async fn actor_counts_records() {
        let tracker = TaskTracker::new();
        let audit = AuditHandle::spawn(&tracker, CancellationToken::new());
        audit.record("a".into()).await.unwrap();
        assert_eq!(audit.count().await.unwrap(), 1);
    }

    #[tokio::test]
    async fn healthz_without_network() {
        let res = Router::new()
            .route("/healthz", get(healthz))
            .oneshot(Request::get("/healthz").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(res.status(), StatusCode::OK);
    }
}
