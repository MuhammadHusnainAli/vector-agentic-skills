//! Find HTTP-service mistakes in axum/reqwest code.
//!   TK011 client-per-request          reqwest::Client::new()/builder() inside an async fn or loop
//!   TK012 unwrap-on-await-in-handler  .await.unwrap() / .await.expect() in an axum handler
//!   TK013 outbound-without-timeout    reqwest .send().await and no `timeout(` anywhere in the file
//!   TK014 no-graceful-shutdown        axum::serve(..) without .with_graceful_shutdown(..)
//!   TK017 axum07-path-syntax          "/:id" or "/*rest" route paths (axum 0.8 uses "/{id}" and "/{*rest}")
//!
//! Build: rustc -O --edition 2021 scripts/service_hygiene.rs -o /tmp/service_hygiene
//! Usage: service_hygiene <FILES|DIRS|-> [--json] [--strict] [--select IDS] [--ignore IDS]

mod async_ctx;
mod cli;
mod rsparse;

use async_ctx::{fn_at, handlers, is_async_fn};
use cli::{Finding, Rule};
use rsparse::{close_of, items, word_positions, Src};

const RULES: &[Rule] = &[
    Rule { id: "TK011", name: "client-per-request", severity: "medium",
           why: "each reqwest::Client owns a connection pool and TLS config: building one per call throws both away",
           fix: "build one Client at startup (with timeouts), store it in AppState, clone the handle (it is an Arc)" },
    Rule { id: "TK012", name: "unwrap-on-await-in-handler", severity: "medium",
           why: "a panic in a handler kills the request with a dropped connection and no useful status or log",
           fix: "return Result<_, AppError> with IntoResponse and use `?`" },
    Rule { id: "TK013", name: "outbound-without-timeout", severity: "low",
           why: "reqwest has no request timeout by default: one hung upstream pins tasks and sockets forever",
           fix: "Client::builder().timeout(..).connect_timeout(..), RequestBuilder::timeout, or tokio::time::timeout" },
    Rule { id: "TK014", name: "no-graceful-shutdown", severity: "medium",
           why: "without graceful shutdown SIGTERM drops in-flight requests and background work mid-way",
           fix: "axum::serve(listener, app).with_graceful_shutdown(shutdown_signal()), then drain tasks (TaskTracker)" },
    Rule { id: "TK017", name: "axum07-path-syntax", severity: "high",
           why: "axum 0.8 changed path parameters to {id} / {*rest}; the old :id / *rest syntax panics at startup",
           fix: "\"/orders/{id}\", \"/files/{*path}\"" },
];

const USAGE: &str = "usage: service_hygiene <FILES|DIRS|-> [options]

Report reqwest clients built per request (TK011), panicking .await.unwrap() in axum
handlers (TK012), outbound HTTP with no timeout anywhere in the file (TK013), axum::serve
without graceful shutdown (TK014) and axum 0.7 path syntax (TK017).";

fn main() {
    let opts = cli::parse(USAGE, RULES, &[]);
    let inputs = opts.inputs();
    let mut findings = Vec::new();
    for input in &inputs {
        let src = Src::new(input.text.clone());
        let code = &src.code;
        let (fns, _, _) = items(&src);
        let routed = handlers(&src, &fns);
        let mut found = Vec::new();
        let mut push = |off: usize, id: &'static str, what: String| {
            found.push(Finding { file: input.name.clone(), line: src.line_of(off), id, msg: what, fix: String::new() });
        };
        let uses_reqwest = code.contains("reqwest");
        let loops: Vec<(usize, usize)> = ["loop", "while", "for"]
            .iter()
            .flat_map(|kw| word_positions(code, kw))
            .filter_map(|i| code[i..].find('{').map(|b| (i + b, close_of(code, i + b))))
            .collect();

        for pat in ["Client::new()", "Client::builder()"] {
            for (off, _) in code.match_indices(pat) {
                let reqwest_client = code[..off].ends_with("reqwest::") || uses_reqwest && !code[..off].ends_with("::");
                let f = fn_at(&src, &fns, off);
                let per_call = f.is_some_and(|f| is_async_fn(&src, f) && f.name != "main") || loops.iter().any(|&(a, b)| a < off && off < b);
                if reqwest_client && per_call {
                    push(off, "TK011", format!("`{pat}` in {} builds a new pool per call", f.map_or("a loop".into(), |f| format!("fn {}", f.name))));
                }
            }
        }
        for f in fns.iter().filter(|f| routed.contains(&f.name) && is_async_fn(&src, f)) {
            let squashed: String = f.body.split_whitespace().collect();
            if squashed.contains(".await.unwrap()") || squashed.contains(".await.expect(") {
                push(f.off, "TK012", format!("handler {} panics on a failed .await (unwrap/expect)", f.name));
            }
        }
        if !code.contains("timeout(") {
            let squashed: String = code.split_whitespace().collect();
            if uses_reqwest && squashed.contains(".send().await") {
                let off = code.find(".send()").unwrap_or(0);
                push(off, "TK013", "outbound reqwest calls and no timeout anywhere in this file".into());
            }
        }
        for (off, _) in code.match_indices("serve(") {
            let open = off + "serve".len();
            let after: String = code[close_of(code, open)..].split(';').next().unwrap_or("").split_whitespace().collect();
            if code[..off].ends_with("axum::") && !after.contains("with_graceful_shutdown") {
                push(off, "TK014", "axum::serve(..) has no .with_graceful_shutdown(..)".into());
            }
        }
        for pat in [".route(", ".nest(", ".route_service(", ".nest_service("] {
            for (off, _) in code.match_indices(pat) {
                let open = off + pat.len() - 1;
                let lit = src.orig[open + 1..close_of(code, open)].split(',').next().unwrap_or("").trim();
                if lit.starts_with('"') && (lit.contains("/:") || lit.contains("/*")) {
                    push(off, "TK017", format!("route path {lit} uses axum 0.7 syntax"));
                }
            }
        }
        let on = |id: &str| RULES.iter().any(|r| r.id == id && opts.enabled(r));
        findings.extend(found.into_iter().filter(|f| on(f.id) && !src.noqa(f.line, f.id)));
    }
    let findings: Vec<Finding> = findings
        .into_iter()
        .map(|mut f| {
            f.fix = RULES.iter().find(|r| r.id == f.id).map_or(String::new(), |r| r.fix.to_string());
            f
        })
        .collect();
    cli::finish(&opts, RULES, findings, inputs.len(), "service")
}
