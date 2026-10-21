# Testing Errors

Errors are API: test which variant is returned, what the message says, that the source chain is intact, that
the type stays `Send + Sync + 'static`, and how the edge (CLI, HTTP) presents it. Examples use thiserror 2 and
anyhow 1 unless marked std.

## Contents

- [Asserting the variant](#asserting-the-variant)
- [Display messages](#display-messages)
- [Source chains](#source-chains)
- [anyhow errors: downcasting and context](#anyhow-errors-downcasting-and-context)
- [Compile-time properties](#compile-time-properties)
- [Panics](#panics)
- [HTTP error responses](#http-error-responses)
- [CLI exit codes and stderr](#cli-exit-codes-and-stderr)
- [Checklist](#checklist)

## Asserting the variant

Prefer `matches!` over `assert_eq!`: it does not require `PartialEq` (which most source errors such as
`std::io::Error` do not implement) and can check selected fields.

```rust
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum StoreError {
    #[error("key {key:?} not found")]
    NotFound { key: String },
    #[error("i/o error on store log")]
    Io(#[from] std::io::Error),
}

pub fn get(map: &std::collections::HashMap<String, String>, key: &str) -> Result<String, StoreError> {
    map.get(key).cloned().ok_or_else(|| StoreError::NotFound { key: key.to_owned() })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_key_is_not_found() {
        let err = get(&Default::default(), "a").unwrap_err();
        assert!(matches!(err, StoreError::NotFound { ref key } if key == "a"), "got {err:?}");
    }

    #[test]
    fn io_errors_convert() {
        let io = std::io::Error::new(std::io::ErrorKind::PermissionDenied, "denied");
        let err: StoreError = io.into();
        assert!(matches!(&err, StoreError::Io(e) if e.kind() == std::io::ErrorKind::PermissionDenied));
    }
}
```

`assert!(matches!(..), "got {err:?}")` prints the actual error when the test fails, which a bare `matches!`
does not.

## Display messages

Messages are user-facing text; pin them so refactors do not change them by accident:

```rust,ignore
#[test]
fn messages() {
    assert_eq!(StoreError::NotFound { key: "a".into() }.to_string(), r#"key "a" not found"#);
}
```

For many variants use snapshot testing (`insta::assert_snapshot!(err.to_string())`). Keep messages lowercase,
without trailing punctuation, and without the source's text (see ERR009).

## Source chains

Check that wrapping preserved the cause, and that no layer repeats it:

```rust
use std::error::Error;

fn chain(e: &(dyn Error + 'static)) -> Vec<String> {
    let mut out = vec![e.to_string()];
    let mut cur = e.source();
    while let Some(s) = cur {
        out.push(s.to_string());
        cur = s.source();
    }
    out
}

#[derive(Debug, thiserror::Error)]
#[error("failed to load config")]
struct LoadError(#[source] std::io::Error);

#[test]
fn chain_has_each_layer_once() {
    let err = LoadError(std::io::Error::new(std::io::ErrorKind::NotFound, "no such file"));
    assert_eq!(chain(&err), ["failed to load config", "no such file"]);
}
```

## anyhow errors: downcasting and context

```rust
use anyhow::Context;

#[derive(Debug, thiserror::Error)]
#[error("rate limited")]
pub struct RateLimited;

fn call() -> anyhow::Result<()> {
    Err(RateLimited).context("calling the pricing service")
}

#[test]
fn context_and_root_cause() {
    let err = call().unwrap_err();
    assert_eq!(err.to_string(), "calling the pricing service");             // outermost context
    assert_eq!(format!("{err:#}"), "calling the pricing service: rate limited"); // whole chain
    assert!(err.downcast_ref::<RateLimited>().is_some());                     // typed root survives context
    assert!(err.root_cause().is::<RateLimited>());
}
```

`downcast_ref::<T>()` works through `.context(..)` layers for the original error type, which is how
application code can still branch on a specific failure.

## Compile-time properties

Lock in that errors can cross threads and convert into anyhow:

```rust,ignore
const _: () = {
    const fn assert_error<E: std::error::Error + Send + Sync + 'static>() {}
    assert_error::<StoreError>();
};
```

Adding a `Rc` or a non-`Send` source to the enum later then fails to compile in your crate instead of in a
downstream `tokio::spawn`.

## Panics

```rust
pub fn percent(part: u32, total: u32) -> u32 {
    assert!(total > 0, "total must be positive");
    part * 100 / total
}

#[test]
#[should_panic(expected = "total must be positive")]
fn zero_total_panics() {
    percent(1, 0);
}
```

`expected` matches a substring of the panic message. Use `std::panic::catch_unwind` only when testing
behaviour after a panic (for example mutex poisoning).

## HTTP error responses

With axum, drive the router with `tower::ServiceExt::oneshot` and assert on status and body:

```rust,ignore
use axum::{body::Body, http::{Request, StatusCode}};
use tower::ServiceExt; // oneshot

#[tokio::test]
async fn unknown_item_is_404_with_code() {
    let app = app(test_state());
    let res = app.oneshot(Request::get("/items/999").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(res.status(), StatusCode::NOT_FOUND);
    let body = axum::body::to_bytes(res.into_body(), 64 * 1024).await.unwrap();
    let json: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(json["code"], "NOT_FOUND");
}

#[tokio::test]
async fn internal_errors_do_not_leak() {
    let res = app(failing_state()).oneshot(Request::get("/items/1").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(res.status(), StatusCode::INTERNAL_SERVER_ERROR);
    let body = axum::body::to_bytes(res.into_body(), 64 * 1024).await.unwrap();
    assert!(!String::from_utf8_lossy(&body).contains("password")); // no internals in the body
}
```

## CLI exit codes and stderr

Test the binary as a process with `assert_cmd` (and `predicates`):

```rust,ignore
use assert_cmd::Command;
use predicates::str::contains;

#[test]
fn missing_config_exits_1_with_chain() {
    Command::cargo_bin("mytool").unwrap()
        .args(["--config", "/nope.toml"])
        .assert()
        .code(1)
        .stderr(contains("reading config /nope.toml"))
        .stderr(contains("No such file"));
}
```

`fn main() -> anyhow::Result<()>` exits with code 1 and prints `Error: ..` plus `Caused by:` lines (the Debug
report) on failure.

## Checklist

| Property | Test |
|----------|------|
| Right variant for each failure | `assert!(matches!(err, E::X { .. }), "got {err:?}")` |
| Stable messages | `assert_eq!(err.to_string(), "..")` or snapshots |
| Chain intact, no duplicates | walk `source()` and compare layers |
| Typed root survives anyhow context | `err.downcast_ref::<T>()`, `root_cause().is::<T>()` |
| `Send + Sync + 'static` | const-fn assertion |
| Panics only where documented | `#[should_panic(expected = "..")]` |
| HTTP mapping and no leaks | `oneshot` tests on status, `code`, body text |
| CLI behaviour | `assert_cmd`: exit code and stderr |
