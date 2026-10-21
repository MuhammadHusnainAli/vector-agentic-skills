---
name: rust-error-handling-thiserror-anyhow-designer
description: "Design and review Rust error handling with thiserror 2 and anyhow 1: library vs application split, typed error enums with #[from], #[source], #[error(transparent)] and #[non_exhaustive], ErrorKind patterns, context via .context()/.with_context(), bail!/ensure!, source() chains, {:#} and {:?} reports, RUST_BACKTRACE/RUST_LIB_BACKTRACE, Box<dyn Error + Send + Sync>, main -> anyhow::Result or ExitCode, unwrap/expect/panic policy, Option to Result, collecting iterators of Results, axum IntoResponse mapping, retryable errors, tracing, async Send bounds, testing with matches! and downcast_ref, no_std core::error::Error, and snafu, eyre/color-eyre, miette, error-stack. Use when the user writes an error.rs, asks thiserror vs anyhow or how to add context, wants to stop unwrap/panic, or hits \"`?` couldn't convert the error\", \"conflicting implementations of trait `From`\", \"`dyn std::error::Error` cannot be sent between threads safely\" or a message printed twice in .rs code."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Error Handling Designer (thiserror + anyhow)

Design error handling that callers can act on and operators can debug: libraries expose small typed
`thiserror` enums with context fields, a `source()` chain and `#[non_exhaustive]`; binaries use `anyhow` to
add context at every hop and report the whole chain once at the edge (main, HTTP handler, job runner).
Panics are reserved for broken invariants. Every review produces before/after Rust; three small std-only
Rust audits catch the mechanical mistakes (unwrap in libraries, stringly errors, discarded sources,
double-printed chains, non-Send boxed errors, anyhow in public library APIs), and `scaffold_errors` generates
an `error.rs` that compiles against thiserror 2 (and axum 0.8 for HTTP apps).

## Trigger Conditions

Activate this skill when the user:
- Writes or reviews an `error.rs`, a `thiserror` enum, `impl std::error::Error`, or `anyhow`/`eyre` code
- Asks "thiserror or anyhow?", "how do I add context?", "how do I get a backtrace?", "why is my error
  printed twice?", "how do I return errors from axum handlers?"
- Has `.unwrap()`/`.expect()`/`panic!` scattered through library code, or `Result<T, String>`
- Hits compiler errors such as "`?` couldn't convert the error to `X`", "the trait `From<io::Error>` is not
  implemented", "conflicting implementations of trait `From`", "`dyn std::error::Error` cannot be sent
  between threads safely", "the `?` operator can only be used in a function that returns `Result`"
- Upgrades thiserror 1 to 2, targets `no_std`, or needs errors that cross FFI, threads or async tasks

## Workflow

```
1. CLASSIFY   -> Is this crate a library (others match on errors) or an application (humans read them)?
                 lib: thiserror enum(s); app: anyhow::Result + context; both in a workspace
2. INVENTORY  -> List failure sources per operation: I/O, parsing, validation, not-found, conflicts,
                 upstream/network, timeouts, bugs (invariants)
3. DESIGN     -> One enum per module or operation family; variants by how callers react; context fields
                 (ids, paths, offsets) not formatted strings; #[non_exhaustive]; retryable classification
                 /tmp/scaffold_errors --spec errors.json -o src/error.rs   (or --preset storage-lib|web-app)
4. PROPAGATE  -> `?` + #[from] for 1:1 wraps; map_err(|source| Variant { ctx, source }) when context is
                 needed; .with_context(|| ..) in anyhow code; never discard or stringify the source
5. REPORT     -> One place logs/prints: main returns anyhow::Result (Debug report) or ExitCode; HTTP edge
                 maps to status codes without leaking internals; tracing logs the chain once
6. AUDIT      -> build once: for t in unwrap_audit error_types error_flow scaffold_errors; do
                   rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
                 for t in unwrap_audit error_types error_flow; do /tmp/$t src/ --strict; done
7. TEST       -> assert!(matches!(err, E::NotFound { .. })), Display snapshots, downcast_ref in app tests,
                 Send + Sync + 'static compile check
```

## Library vs Application

| Situation | Use | Why |
|-----------|-----|-----|
| Library crate (published or internal) | `thiserror` enum per module/operation | Callers `match` on variants; std-only public API |
| Binary, CLI, service `main`, scripts, tests | `anyhow::Result<T>` + `.context()` | Any error type, cheap context, great `{:?}` report |
| Service with an HTTP/RPC edge | thiserror `AppError` with `Internal(#[from] anyhow::Error)` | Typed 4xx variants, everything else becomes 500 |
| Library that must hide dependency types | opaque `struct Error { kind: ErrorKind, source }` | Like `std::io::Error`; freedom to swap deps |
| User-facing diagnostics with source spans (compilers, config linters) | `miette` (`Diagnostic` derive) | Labels, help text, snippets |
| Colorful CLI reports with span traces | `eyre` + `color-eyre` | anyhow-like API, pluggable report handler |
| Context-selector style, many contexts per source type | `snafu` | `.context(ReadConfigSnafu { path })` |
| Large systems wanting typed contexts + attachments | `error-stack` (`Report<C>`) | Change context at boundaries, attach data |

Both crates together is normal: library modules return `StoreError`, the binary calls them with
`.context("loading users")?` and gets an `anyhow::Error` whose chain still contains the `StoreError`
(recoverable with `downcast_ref`). thiserror never appears in your public API (it only derives std
traits), so switching away from it, or from 1.x to 2.x, is not a breaking change. Details:
[library-vs-application.md](references/library-vs-application.md).

## Core Rules

1. **Libraries return typed errors; applications may use anyhow.** A `pub fn` in a library returning
   `anyhow::Result` gives callers nothing to match on (ERR005).
2. **Describe this layer only.** `#[error("failed to read config {path:?}")]`, not `"...: {source}"`. The
   cause is returned by `source()`; printing it in Display too makes every report show it twice (ERR009).
   Exception: `#[error(transparent)]` forwards both Display and source on purpose.
3. **Never drop or stringify the source.** `map_err(|_| ..)` (ERR006) and `map_err(|e| e.to_string())`
   (ERR007) erase the type, kind, chain and backtrace. Wrap it: `map_err(|source| E::Parse { line, source })`.
4. **Context is data.** Variants carry fields (`id: u64`, `path: PathBuf`, `offset: u64`) so callers and
   logs can use them; messages are lowercase, no trailing punctuation (std convention).
5. **`#[non_exhaustive]` on public error enums** so adding a variant is not a breaking change (ERR010).
6. **Don't leak dependency types you may swap.** A `#[from] sqlx::Error` in a public enum makes sqlx's
   major version part of your API; wrap in your own variant or box as `Box<dyn Error + Send + Sync>`.
7. **Errors must be `Send + Sync + 'static`.** Required by `tokio::spawn`, anyhow conversion and most
   frameworks. Never `Box<dyn Error>` alone (ERR004). Keep `Err` small: box large payloads
   (`clippy::result_large_err` fires above 128 bytes).
8. **Panics are for bugs, not for input.** No `unwrap`/`panic!`/`todo!` in library paths (ERR001-ERR003);
   `expect("<why this cannot fail>")` only for real invariants, documented under `# Panics`.
9. **Handle or propagate; log once.** Inner layers add context and return; the boundary logs (with the
   whole chain) and converts to a response or exit code. `let _ = fallible()` hides failures (ERR011).
10. **Return errors from `main`.** `fn main() -> anyhow::Result<()>` or `-> ExitCode`; `eprintln!` +
    `process::exit` skips destructors and flushing (ERR013).
11. **Classify retryability in the type** (`is_retryable()`), not by matching message strings at call sites.
12. **Don't use unstable `try` blocks**, `Error::provide` or `std::error::Report` in stable code; use a
    closure or helper fn returning `Result` instead.

## Designing a Library Error (thiserror 2)

```rust,ignore
use std::path::PathBuf;

/// Errors returned by [`Store`].
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum StoreError {
    #[error("record {id} not found")]
    NotFound { id: u64 },

    #[error("record {id} was modified concurrently (expected v{expected}, found v{actual})")]
    Conflict { id: u64, expected: u64, actual: u64 },

    #[error("failed to open store at {path:?}")]
    Open { path: PathBuf, #[source] source: std::io::Error },

    #[error("store i/o failed")]
    Io(#[from] std::io::Error),

    #[error("cannot decode record at byte {offset}")]
    Decode { offset: u64, #[source] source: serde_json::Error },
}

pub type Result<T, E = StoreError> = std::result::Result<T, E>;

impl StoreError {
    pub fn is_retryable(&self) -> bool {
        match self {
            Self::Io(e) | Self::Open { source: e, .. } => matches!(
                e.kind(),
                std::io::ErrorKind::Interrupted | std::io::ErrorKind::TimedOut | std::io::ErrorKind::WouldBlock
            ),
            Self::Conflict { .. } => true,
            Self::NotFound { .. } | Self::Decode { .. } => false,
        }
    }
}

pub fn open(path: impl Into<PathBuf>) -> Result<Store> {
    let path = path.into();
    let file = std::fs::File::open(&path)
        .map_err(|source| StoreError::Open { path: path.clone(), source })?; // context + source
    Store::from_file(file)                                                   // `?` inside uses #[from] Io
}
```

| Attribute / form | Effect |
|------------------|--------|
| `#[error("record {id} not found")]` | Display; `{id}` = field, `{0}` = tuple field, `{id:?}` Debug |
| `#[error("bad {}", .path.display())]` | extra format args; `.field` / `.0` refer to fields |
| `#[source] source: E` (or a field named `source`) | `Error::source()` returns it |
| `#[from] E` | `#[source]` + `impl From<E>`; the variant may hold only that field (plus a backtrace) |
| `#[error(transparent)] Other(#[from] anyhow::Error)` | Display and `source()` forward to the inner error |
| `#[non_exhaustive]` on the enum | downstream `match` needs `_ =>`; adding variants is non-breaking |

thiserror 2 specifics: write `{type}` (not `{r#type}`) for a field named `r#type`; the crate using
`#[derive(Error)]` must depend on `thiserror` directly; `default-features = false` gives `no_std`
(`core::error::Error`, Rust 1.81+). See [thiserror-design.md](references/thiserror-design.md) and
[version-history.md](references/version-history.md).

## Context and Propagation in Applications (anyhow 1)

```rust,ignore
use anyhow::{bail, ensure, Context, Result};
use std::path::Path;

fn load_config(path: &Path) -> Result<Config> {
    let text = std::fs::read_to_string(path)
        .with_context(|| format!("reading config {}", path.display()))?; // lazy: formats only on error
    let cfg: Config = toml::from_str(&text).context("parsing config TOML")?;
    ensure!(cfg.workers > 0, "workers must be > 0, got {}", cfg.workers);
    if cfg.listen.is_empty() {
        bail!("`listen` is empty in {}", path.display());
    }
    Ok(cfg)
}

fn main() -> Result<()> {
    let cfg = load_config(Path::new("app.toml")).context("startup failed")?;
    run(cfg)
}
```

```
Error: startup failed

Caused by:
    0: reading config app.toml
    1: No such file or directory (os error 2)
```

| Tool | Use |
|------|-----|
| `.context("static msg")` | cheap constant context; works on `Result<T, E: Error + Send + Sync + 'static>` and `Option<T>` |
| `.with_context(\|\| format!(..))` | context that allocates; closure runs only on error |
| `bail!(..)` / `ensure!(cond, ..)` | early return with an ad-hoc error |
| `anyhow!(..)` / `anyhow::Error::msg(s)` | build an error from a message or a `String` error |
| `err.downcast_ref::<StoreError>()` | recover a typed error anywhere in the chain (context layers too) |
| `err.chain()` / `err.root_cause()` | iterate `source()` links / get the innermost error |

## Reporting, Chains and Backtraces

| Format | anyhow::Error prints | Use for |
|--------|----------------------|---------|
| `{}` | outermost message only | short UI text |
| `{:#}` | `outer: middle: root` on one line | log lines, CLI one-liners |
| `{:?}` | message, `Caused by:` list, backtrace if captured | `main` return, crash reports |

Backtraces: anyhow captures one (via `std::backtrace`, Rust 1.65+) when `RUST_LIB_BACKTRACE=1`, or when it
is unset and `RUST_BACKTRACE=1`/`full`. `RUST_LIB_BACKTRACE=0` keeps panic backtraces but disables error
captures (capturing is slow; avoid in hot paths). For a typed error, prefer letting the binary capture via
anyhow; a `Backtrace` field in a `#[derive(thiserror::Error)]` type needs nightly (thiserror generates
`provide()`), so on stable write Display/Error by hand for that type (see thiserror-design.md section 11).

Logging with tracing, once, at the boundary:
```rust,ignore
if let Err(err) = handle(job).await {
    tracing::error!(error = %format!("{err:#}"), job_id = %job.id, "job failed"); // whole chain, one line
}
```
`%err` records Display (outer message only for anyhow; use `{:#}` for the chain), `?err` records Debug
(multi-line for anyhow). `#[tracing::instrument(err)]` logs a returned `Err` with Display; do not also log
it in the caller.

## Panics vs Errors

| Use | When | Example |
|-----|------|---------|
| `Result` | anything the caller or environment can cause | missing file, bad input, timeout |
| `expect("...")` | invariant the code itself guarantees | `"regex literal is valid"`, `"index came from the same Vec"` |
| `unwrap()` | tests, examples, prototypes | `#[cfg(test)]` |
| `unreachable!()` | provably impossible branch | exhaustive state machine fallback |
| `panic!`/`todo!` | never in shipped library paths | |

```toml
# Cargo.toml (Rust 1.74+): enforce in CI with `cargo clippy -- -D warnings`
[lints.clippy]
unwrap_used = "deny"
expect_used = "warn"
panic = "warn"
todo = "deny"
unimplemented = "deny"
map_err_ignore = "warn"
result_large_err = "warn"
```
Add `allow-unwrap-in-tests = true` and `allow-expect-in-tests = true` to `clippy.toml` so tests stay terse.
Write `expect` messages as the reason it should succeed ("config should be validated at startup"), per the
std docs; the panic message then reads as a broken assumption.

## Conversions Cheat Sheet

```rust,ignore
let user = users.get(&id).ok_or_else(|| StoreError::NotFound { id })?;   // Option -> Result, lazy
let port: u16 = env::var("PORT").ok().and_then(|s| s.parse().ok()).unwrap_or(8080); // fallible default
let nums: Vec<u32> = lines.iter().map(|l| l.parse()).collect::<Result<_, _>>()?;   // first Err wins
let total: u64 = sizes.iter().map(|p| file_len(p)).sum::<Result<u64, _>>()?;      // Sum for Result
let (oks, errs): (Vec<_>, Vec<_>) = results.into_iter().partition(|r| r.is_ok()); // keep going, then
let errs: Vec<StoreError> = errs.into_iter().filter_map(Result::err).collect();   // split out errors
let maybe: Option<Config> = parse(text).ok();                             // Result -> Option, drops error
let res: Result<Option<T>, E> = opt_res.transpose();                     // Option<Result> <-> Result<Option>
fetch().inspect_err(|e| tracing::warn!(error = %e, "fetch failed"))?;   // Rust 1.76+
```
No `try { }` blocks on stable: use a closure `(|| -> Result<_> { a()?; b() })()` or a small helper fn.

## HTTP Boundary (axum 0.8)

```rust,ignore
use anyhow::Context;
use axum::{extract::Path, http::StatusCode, response::{IntoResponse, Response}, Json};

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("{resource} {id} not found")]
    NotFound { resource: &'static str, id: String },
    #[error("invalid {field}: {reason}")]
    Validation { field: &'static str, reason: String },
    #[error(transparent)]
    Internal(#[from] anyhow::Error),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            Self::NotFound { .. } => (StatusCode::NOT_FOUND, self.to_string()),
            Self::Validation { .. } => (StatusCode::UNPROCESSABLE_ENTITY, self.to_string()),
            Self::Internal(err) => {
                tracing::error!(error = %format!("{err:#}"), "internal error"); // log chain once
                (StatusCode::INTERNAL_SERVER_ERROR, "internal server error".to_owned()) // no leak
            }
        };
        (status, Json(serde_json::json!({ "error": message }))).into_response()
    }
}

async fn get_user(Path(id): Path<u64>) -> Result<Json<User>, ApiError> {
    let user = db::find_user(id).await.context("querying users")?  // anyhow -> ApiError::Internal
        .ok_or_else(|| ApiError::NotFound { resource: "user", id: id.to_string() })?;
    Ok(Json(user))
}
```
Rust does not chain `From`: an `sqlx::Error` will not `?` into `ApiError` through anyhow automatically;
add `.context(..)` (which yields `anyhow::Error`) or a dedicated `#[from]` variant. Status mapping, retry
headers and gRPC are covered in [boundaries-async-http.md](references/boundaries-async-http.md).

## Async, Threads and FFI

- Futures that hold an error across `.await` must be `Send` for `tokio::spawn`; `Box<dyn Error>` is not.
  Use `Box<dyn Error + Send + Sync>` (tower/hyper call this `BoxError`) or concrete types.
- `JoinHandle::await` returns `Err(JoinError)` when the task panicked or was cancelled
  (`is_panic()`, `is_cancelled()`); convert it with `.context("worker task failed")?`.
- Panics must not unwind across `extern "C"`: since Rust 1.81 they abort. Catch with
  `std::panic::catch_unwind` at the FFI edge and return an error code; use `extern "C-unwind"` only when
  the foreign side expects unwinding.
- `no_std`: implement `core::error::Error` (Rust 1.81+); thiserror 2 with `default-features = false`,
  anyhow with `default-features = false` (needs `alloc`).

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| "`?` couldn't convert the error to `MyError`" / "the trait `From<io::Error>` is not implemented for `MyError`" | no conversion for that source type | `#[from]` variant, or `.map_err(\|source\| MyError::Read { path, source })?` |
| "the `?` operator can only be used in a function that returns `Result` or `Option`" | `?` in `main`/closure returning `()` | `fn main() -> anyhow::Result<()>`; give the closure a `Result` return type |
| "conflicting implementations of trait `From<std::io::Error>`" (E0119) | two `#[from]` of the same type, or a blanket `From<E>` plus a derive | one `#[from]`; others use `#[source]` + `map_err` with context |
| "`dyn std::error::Error` cannot be sent between threads safely" | `Box<dyn Error>` held across `.await` / sent to a thread | `Box<dyn Error + Send + Sync>`, typed enum, or anyhow |
| "`?` couldn't convert the error to `anyhow::Error`" on `Result<_, String>` | `String` is not `std::error::Error` | `.map_err(anyhow::Error::msg)?`; better, give the function a real error type |
| Report shows `failed to read: No such file...: No such file...` | Display prints `{source}` and `source()` returns it | describe this layer only (ERR009) or `#[error(transparent)]` |
| `main` prints `Error: Os { code: 2, kind: NotFound, .. }` | `main` returns `Result<(), io::Error>` (Debug of io::Error) | return `anyhow::Result<()>`, or `ExitCode` and print `{err:#}` |
| anyhow `{:?}` has no backtrace | capture disabled | `RUST_BACKTRACE=1` or `RUST_LIB_BACKTRACE=1` |
| "non-exhaustive patterns: `_` not covered" matching a dependency's error | upstream enum is `#[non_exhaustive]` | add `_ =>` arm; prefer `is_*()`/`kind()` helpers |
| `clippy::result_large_err` | big variant inflates every `Result` | `Box` the large payload or the whole error |
| Compile errors on `{r#type}` / missing `thiserror` after upgrading to 2.0 | thiserror 2 rules | `{type}`; add `thiserror = "2"` to the crate that derives |
| HTTP 500 body contains SQL / file paths | `err.to_string()` sent to clients | generic message for 5xx, log the chain server-side |
| Error silently vanished | `let _ =`, `.ok();`, `unwrap_or_default()` on a Result | propagate, or log with reason (ERR011) |

## Output Format

When reviewing or designing, answer with:
1. **Classification** - library or application (per crate in a workspace) and the chosen crates.
2. **Findings** - numbered, each with file:line, rule id (ERR0xx when the script flagged it), the failure
   that becomes invisible or unmatchable, and severity.
3. **Error type(s)** - full `error.rs` with variants, messages, context fields, `#[non_exhaustive]`,
   `is_retryable()`, `Result` alias; a table variant -> caller reaction -> retryable -> HTTP status.
4. **Fixed call sites** - before/after for each `unwrap`, `map_err`, `?` that changes.
5. **Reporting** - where errors are logged/printed (exactly once) and the expected report text.
6. **Tests** - `matches!` per variant, Display assertions, downcast in app tests, Send/Sync check.

## Scripts

Small, standard-library-only Rust programs (no Cargo project; they read source text and never build your
crate). Build each once with `rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>`.

| Script | Rules | Job |
|--------|-------|-----|
| `scripts/unwrap_audit.rs` | ERR001-ERR003 | `.unwrap()`, `.expect()`, `panic!`/`todo!`/`unimplemented!` in library code |
| `scripts/error_types.rs` | ERR004, ERR005, ERR008-ERR010 | how errors are declared: non-Send `Box<dyn Error>`, anyhow in pub lib APIs, `Result<_, String>`, source printed twice, exhaustive pub error enums |
| `scripts/error_flow.rs` | ERR006, ERR007, ERR011-ERR013 | how errors travel: `map_err(\|_\| ..)`, stringly `map_err`, ignored Results, bare `?` without context, `eprintln!` + `exit` |
| `scripts/scaffold_errors.rs` | - | generates `error.rs` from a JSON spec or preset |
| `scripts/errgen.rs`, `scripts/json.rs` | - | modules of the generator: spec validation and code rendering; a minimal std-only JSON reader |
| `scripts/scope.rs`, `scripts/rsparse.rs`, `scripts/cli.rs` | - | shared modules: lib/app and test-code decisions, source scanner, options and report |

```bash
/tmp/unwrap_audit src/                                  # auto-detects lib/app per file
/tmp/error_types src/store.rs --lib --strict            # exit 1 on any finding (CI gate)
cat src/lib.rs | /tmp/error_flow - --lib                # stdin
/tmp/error_types crates/ --json --ignore ERR010
/tmp/error_flow src/ --select ERR006,stringly-map-err
/tmp/unwrap_audit --list-rules                          # each audit lists its rules with why and fix
```

| Rule | Name | Severity | Flags |
|------|------|----------|-------|
| ERR001 | unwrap-in-lib | medium | `.unwrap()` in non-test, non-binary code |
| ERR002 | expect-in-lib | low | `.expect(..)` in non-test, non-binary code |
| ERR003 | panic-in-lib | high | `todo!`/`unimplemented!` (unfinished), `panic!` (input error or invariant?) |
| ERR004 | box-dyn-error-not-send | medium | `Box<dyn Error>` without `Send + Sync` (`fn main` exempt) |
| ERR005 | anyhow-in-lib-api | high | `pub fn` returning anyhow in library code |
| ERR006 | map-err-discards-source | medium | `.map_err(\|_\| ..)` |
| ERR007 | stringly-map-err | medium | `.map_err(\|e\| e.to_string())`, `format!` with `e` |
| ERR008 | string-error-type | medium | `Result<_, String>`, `&str`, `()` |
| ERR009 | source-printed-twice | medium | `{0}`/`{source}` on a `#[from]`/`#[source]`/`source` field |
| ERR010 | missing-non-exhaustive | info | public error enum without `#[non_exhaustive]` (library code) |
| ERR011 | discarded-result | low | `let _ = call()`, `call().ok();` |
| ERR012 | missing-context | info | bare `?` on fs/parse/serde calls in fns returning anyhow |
| ERR013 | exit-instead-of-return | medium | `eprintln!` + `process::exit` |

A file is binary code when it is `main.rs`, under `src/bin/`, or defines `fn main`; `--lib`/`--app` override.
`#[cfg(test)]` modules, `#[test]` fns and a crate's `tests/`, `benches/`, `examples/` are skipped unless
`--include-tests`. Silence one line with `// noqa: ERR001`. Exit codes: 0 clean (or findings without
`--strict`), 1 findings with `--strict`, 2 usage or read error.

```bash
# Generate src/error.rs: thiserror enum, code(), is_retryable(), http_status(), Result alias, tests
/tmp/scaffold_errors --spec errors.json -o src/error.rs
/tmp/scaffold_errors --preset storage-lib                # library: #[non_exhaustive], io-kind retries
/tmp/scaffold_errors --preset web-app --json             # app: axum IntoResponse, anyhow Internal
cat errors.json | /tmp/scaffold_errors --spec -
/tmp/scaffold_errors --preset web-app --print-spec       # start your own spec from a preset
```

Spec: `{"crate_kind": "lib"|"app", "name": "StoreError", "http": true, "variants": [{"name": "NotFound",
"fields": {"id": "u64"}, "message": "item {id} not found"}, {"name": "Io", "from": "std::io::Error",
"message": "storage i/o failed"}]}`; variant keys `source`, `transparent`, `retryable`, `http`, `code`,
`doc`. Rejected with exit 2 and a precise message: duplicate `#[from]` types, `#[from]` beside other fields,
unknown or positional placeholders, placeholders printing the source, `{r#name}` (write `{name}`; keyword
fields such as `type` become `r#type` automatically). Generated code needs `thiserror = "2"`, plus `axum =
"0.8"`, `serde_json = "1"` and `tracing = "0.1"` for HTTP apps; the presets compile and their tests pass.

## Additional Resources

| File | Content |
|------|---------|
| [library-vs-application.md](references/library-vs-application.md) | thiserror vs anyhow vs snafu, eyre/color-eyre, miette, error-stack; workspace layouts; migration paths |
| [thiserror-design.md](references/thiserror-design.md) | Every attribute, format rules, enum granularity, ErrorKind/opaque pattern, dependency leakage, sizes |
| [anyhow-context-reporting.md](references/anyhow-context-reporting.md) | Context, macros, downcasting, chains, report formats, backtraces, main/ExitCode/Termination, tracing |
| [boundaries-async-http.md](references/boundaries-async-http.md) | axum/HTTP mapping, retryable classification, async Send, JoinError, threads, FFI, no_std, panics |
| [anti-patterns.md](references/anti-patterns.md) | Every ERR rule with before/after fixes, plus smells the script cannot see |
| [testing-errors.md](references/testing-errors.md) | matches!, Display snapshots, downcast, source chains, should_panic, HTTP and CLI error tests |
| [version-history.md](references/version-history.md) | std error stabilisations by Rust version, thiserror 1 -> 2 migration, anyhow notes, unstable features |
