//! Generate an `error.rs` module from a small JSON spec or a built-in preset: a thiserror 2
//! enum (non_exhaustive for libraries), code(), is_retryable(), http_status(), a Result alias,
//! an axum IntoResponse impl for HTTP apps, and tests.
//!
//! Build: rustc -O --edition 2021 scripts/scaffold_errors.rs -o /tmp/scaffold_errors
//! Usage: scaffold_errors --spec errors.json|- [-o src/error.rs] [--json]
//!        scaffold_errors --preset storage-lib|web-app [--print-spec]

mod errgen;
mod json;

use std::io::Read;
use std::process::exit;

const USAGE: &str = r#"usage: scaffold_errors (--spec FILE|- | --preset NAME) [-o FILE] [--json] [--print-spec]

Generate a Rust error module from a JSON spec:
  {"crate_kind": "lib"|"app", "name": "StoreError", "http": true, "variants": [
     {"name": "NotFound", "fields": {"id": "u64"}, "message": "item {id} not found"},
     {"name": "Io", "from": "std::io::Error", "message": "storage i/o failed"},
     {"name": "Decode", "fields": {"offset": "u64"}, "source": "serde_json::Error",
      "message": "cannot decode record at byte {offset}", "http": 500},
     {"name": "Internal", "transparent": "anyhow::Error"}]}
Variant keys: name, fields, message, from, source, transparent, retryable, http, code, doc.

options:
  --spec FILE|-      read the spec (- for stdin)
  --preset NAME      storage-lib (library: non_exhaustive, io kinds) or web-app (axum IntoResponse)
  --print-spec       print the preset's spec (start your own from it)
  -o FILE            write the module to FILE instead of stdout
  --json             print {"name", "variants", "rust"} instead of plain Rust
Exit: 0 generated, 2 invalid spec (the message names the problem) or usage error."#;

const STORAGE_LIB: &str = r#"{
  "crate_kind": "lib",
  "name": "StoreError",
  "http": false,
  "variants": [
    {"name": "NotFound", "fields": {"key": "String"}, "message": "key {key:?} not found", "doc": "The key does not exist."},
    {"name": "EmptyKey", "message": "key must not be empty"},
    {"name": "Busy", "message": "storage engine is busy", "retryable": true},
    {"name": "Open", "fields": {"path": "std::path::PathBuf"}, "source": "std::io::Error", "message": "failed to open {path:?}"},
    {"name": "Io", "from": "std::io::Error", "message": "i/o error on the store log"},
    {"name": "Corrupt", "fields": {"line": "usize"}, "message": "corrupt record at line {line}"}
  ]
}"#;

const WEB_APP: &str = r#"{
  "crate_kind": "app",
  "name": "ApiError",
  "http": true,
  "variants": [
    {"name": "NotFound", "fields": {"resource": "&'static str", "id": "String"}, "message": "{resource} {id} not found"},
    {"name": "Validation", "fields": {"field": "&'static str", "reason": "String"}, "message": "invalid {field}: {reason}", "http": 422},
    {"name": "Unauthorized", "message": "authentication required"},
    {"name": "Conflict", "fields": {"id": "String"}, "message": "{id} was modified concurrently"},
    {"name": "RateLimited", "fields": {"retry_after_secs": "u64"}, "message": "rate limited, retry in {retry_after_secs}s", "retryable": true},
    {"name": "Upstream", "fields": {"service": "&'static str"}, "source": "std::io::Error", "message": "upstream {service} failed", "http": 502},
    {"name": "Internal", "transparent": "anyhow::Error"}
  ]
}"#;

fn die(msg: &str) -> ! {
    eprintln!("error: {msg}");
    exit(2);
}

fn json_str(s: &str) -> String {
    let mut out = String::from("\"");
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c => out.push(c),
        }
    }
    out + "\""
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() || args.iter().any(|a| a == "-h" || a == "--help") {
        println!("{USAGE}");
        exit(if args.is_empty() { 2 } else { 0 });
    }
    let (mut spec_path, mut preset, mut out_path) = (None, None, None);
    let (mut as_json, mut print_spec) = (false, false);
    let mut it = args.iter();
    while let Some(a) = it.next() {
        let mut val = || it.next().cloned().unwrap_or_else(|| die(&format!("{a} needs a value")));
        match a.as_str() {
            "--spec" => spec_path = Some(val()),
            "--preset" => preset = Some(val()),
            "-o" | "--out" => out_path = Some(val()),
            "--json" => as_json = true,
            "--print-spec" => print_spec = true,
            other => die(&format!("unknown argument {other}")),
        }
    }
    let text = match (&spec_path, &preset) {
        (Some(_), Some(_)) => die("use either --spec or --preset"),
        (None, Some(p)) => match p.as_str() {
            "storage-lib" => STORAGE_LIB.to_string(),
            "web-app" => WEB_APP.to_string(),
            other => die(&format!("unknown preset '{other}' (storage-lib, web-app)")),
        },
        (Some(p), None) if p == "-" => {
            let mut s = String::new();
            std::io::stdin().read_to_string(&mut s).unwrap_or_else(|e| die(&format!("cannot read stdin: {e}")));
            s
        }
        (Some(p), None) => std::fs::read_to_string(p).unwrap_or_else(|e| die(&format!("cannot read {p}: {e}"))),
        (None, None) => die("pass --spec FILE or --preset NAME"),
    };
    if print_spec {
        println!("{}", text.trim());
        return;
    }
    let doc = json::parse(&text).unwrap_or_else(|e| die(&format!("cannot parse spec JSON: {e}")));
    let spec = errgen::from_json(&doc).unwrap_or_else(|e| die(&format!("invalid spec: {e}")));
    let rust = errgen::render(&spec);
    let variants: Vec<String> = spec.variants.iter().map(|v| json_str(&v.name)).collect();
    let output = if as_json {
        format!("{{\"name\":{},\"variants\":[{}],\"rust\":{}}}\n", json_str(&spec.name), variants.join(","), json_str(&rust))
    } else {
        rust
    };
    match out_path {
        Some(p) => {
            std::fs::write(&p, &output).unwrap_or_else(|e| die(&format!("cannot write {p}: {e}")));
            eprintln!("wrote {p} ({} with {} variants)", spec.name, spec.variants.len());
        }
        None => print!("{output}"),
    }
}
