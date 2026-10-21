// Fixture for the rust-tokio-async-service-builder scanners: an order service with the usual async mistakes.
// Every block below is wrong on purpose; see tk_clean_service.rs for the fixed version.
use std::{
    cell::RefCell,
    collections::HashMap,
    rc::Rc,
    sync::{Arc, Mutex},
    time::Duration,
};

use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::mpsc;

#[derive(Clone, Serialize, Deserialize)]
struct Order {
    id: u64,
    sku: String,
    qty: u32,
}

struct AppState {
    orders: Mutex<HashMap<u64, Order>>,
    audit: tokio::sync::Mutex<Vec<String>>,
    events: mpsc::UnboundedSender<String>,
}

type Shared = Arc<AppState>;

async fn get_order(State(state): State<Shared>, Path(id): Path<u64>) -> Json<Order> {
    let orders = state.orders.lock().unwrap();
    let order = orders.get(&id).cloned().unwrap();
    // guard still alive: enrich() is awaited while the std MutexGuard is held
    let price = enrich(&order.sku).await;
    tracing::info!(price, "served order");
    Json(order)
}

async fn enrich(sku: &str) -> f64 {
    // new client (pool + TLS) per call, and no timeout anywhere in this file
    let client = reqwest::Client::new();
    let resp = client
        .get(format!("https://pricing.internal/v1/{sku}"))
        .send()
        .await
        .unwrap();
    resp.json::<f64>().await.unwrap()
}

async fn create_order(State(state): State<Shared>, Json(order): Json<Order>) -> StatusCode {
    // blocking file I/O and sleep on a runtime worker
    let rules = std::fs::read_to_string("/etc/orders/rules.toml").unwrap_or_default();
    std::thread::sleep(Duration::from_millis(50));
    let mut audit = state.audit.lock().await;
    audit.push(format!("create {} ({} bytes of rules)", order.id, rules.len()));
    drop(audit);
    state.orders.lock().unwrap().insert(order.id, order.clone());
    // fire and forget: errors and panics vanish, shutdown cannot wait for it
    tokio::spawn(async move {
        notify_warehouse(order).await;
    });
    let _ = state.events.send("created".to_owned());
    StatusCode::CREATED
}

async fn notify_warehouse(order: Order) {
    let body = serde_json::to_string(&order).unwrap();
    reqwest::Client::new()
        .post("https://warehouse.internal/v1/orders")
        .body(body)
        .send()
        .await
        .ok();
}

async fn legacy_report() -> String {
    // blocking client inside async code panics when dropped in the runtime
    let text = reqwest::blocking::get("https://legacy.internal/report")
        .and_then(|r| r.text())
        .unwrap_or_default();
    let cached = tokio::fs::read_to_string("/var/cache/orders/report.txt").await.unwrap();
    let _probe = std::net::TcpStream::connect("legacy.internal:80");
    let counter = Rc::new(RefCell::new(cached.len()));
    *counter.borrow_mut() += 1;
    tokio::time::sleep(Duration::from_millis(1)).await;
    text
}

async fn sync_bridge(rx: std::sync::mpsc::Receiver<String>) -> Option<String> {
    let handle = tokio::runtime::Handle::current();
    let first = rx.recv().ok();
    handle.block_on(async { tokio::time::sleep(Duration::from_millis(1)).await });
    first
}

async fn read_frames(stream: TcpStream, mut shutdown: mpsc::Receiver<()>) -> std::io::Result<()> {
    let mut reader = BufReader::new(stream);
    let mut header = [0u8; 4];
    let mut line = String::new();
    loop {
        tokio::select! {
            res = reader.read_exact(&mut header) => { res?; }
            res = reader.read_line(&mut line) => { if res? == 0 { break; } }
            _ = tokio::time::sleep(Duration::from_secs(30)) => break,
            _ = shutdown.recv() => break,
        }
    }
    Ok(())
}

fn compute_checksum(data: Vec<u8>) -> u64 {
    tokio::task::block_in_place(|| data.iter().map(|b| *b as u64).sum())
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let (tx, mut rx) = mpsc::unbounded_channel::<String>();
    let state = Arc::new(AppState {
        orders: Mutex::new(HashMap::new()),
        audit: tokio::sync::Mutex::new(Vec::new()),
        events: tx,
    });
    let local = vec![1u8, 2, 3];
    tokio::spawn(async {
        println!("checksum {}", compute_checksum(local.clone()));
    });
    tokio::spawn(async move { while let Some(ev) = rx.recv().await { println!("{ev}"); } });

    let app = Router::new()
        .route("/orders/:id", get(get_order))
        .route("/orders", post(create_order))
        .route("/report", get(legacy_report))
        .with_state(state);

    let listener = TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
