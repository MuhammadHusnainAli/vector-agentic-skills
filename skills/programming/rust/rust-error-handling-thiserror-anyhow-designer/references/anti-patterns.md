# Error-Handling Anti-Patterns

Every ERR rule the audits report, with the reason, a before/after fix, and when the pattern is acceptable.
After that, smells the scripts cannot see. Examples use thiserror 2 and anyhow 1.

## Contents

- [ERR001-ERR003: panics in library code](#err001-err003-panics-in-library-code)
- [ERR004: `Box<dyn Error>` without `Send + Sync`](#err004-boxdyn-error-without-send--sync)
- [ERR005: anyhow in a library API](#err005-anyhow-in-a-library-api)
- [ERR006: `map_err(|_| ..)`](#err006-map_err_--)
- [ERR007: stringly `map_err`](#err007-stringly-map_err)
- [ERR008: `Result<T, String>`](#err008-resultt-string)
- [ERR009: source printed twice](#err009-source-printed-twice)
- [ERR010: exhaustive public error enums](#err010-exhaustive-public-error-enums)
- [ERR011: discarded results](#err011-discarded-results)
- [ERR012: `?` without context](#err012--without-context)
- [ERR013: `process::exit` instead of returning](#err013-processexit-instead-of-returning)
- [Smells the scripts cannot see](#smells-the-scripts-cannot-see)

## ERR001-ERR003: panics in library code

A library cannot know whether its caller can recover; panicking takes that decision away and loses the
error value.

```rust,ignore
// Before
pub fn port(cfg: &HashMap<String, String>) -> u16 {
    cfg.get("port").unwrap().parse().expect("port must be a number")
}

// After
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum ConfigError {
    #[error("missing key {0:?}")]
    Missing(&'static str),
    #[error("invalid value {value:?} for {key}")]
    Invalid { key: &'static str, value: String, #[source] source: std::num::ParseIntError },
}

pub fn port(cfg: &HashMap<String, String>) -> Result<u16, ConfigError> {
    let value = cfg.get("port").ok_or(ConfigError::Missing("port"))?;
    value.parse().map_err(|source| ConfigError::Invalid { key: "port", value: value.clone(), source })
}
```

Acceptable: `expect` for genuine invariants, phrased as the invariant (`.expect("regex literal is valid")`,
`.expect("index < len checked above")`); `unwrap` in tests, examples, build scripts and `main` of small tools.
Document deliberate panics under a `# Panics` heading. `todo!`/`unimplemented!` should not ship.

## ERR004: `Box<dyn Error>` without `Send + Sync`

`Box<dyn Error>` cannot be sent to another thread or task, cannot be returned from a `tokio::spawn`ed future,
and does not convert into `anyhow::Error` (which requires `Send + Sync + 'static`).

```rust
// Before: pub fn load(p: &str) -> Result<String, Box<dyn std::error::Error>>
pub type BoxError = Box<dyn std::error::Error + Send + Sync + 'static>;

pub fn load(p: &str) -> Result<String, BoxError> {
    Ok(std::fs::read_to_string(p)?)
}
```

Acceptable: `fn main() -> Result<(), Box<dyn Error>>` in a small binary (the audits exempt `main`).

## ERR005: anyhow in a library API

Callers of a library need to *react* to failures (retry on timeout, 404 on not-found). With `anyhow::Error`
they must downcast to guess what happened, and every new internal error becomes invisible API.

```rust,ignore
// Before
pub fn fetch(id: u64) -> anyhow::Result<Item> { .. }

// After: typed at the boundary, anyhow stays inside the binary
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum FetchError {
    #[error("item {0} not found")]
    NotFound(u64),
    #[error("request timed out")]
    Timeout,
    #[error("transport error")]
    Transport(#[source] std::io::Error),
}
pub fn fetch(id: u64) -> Result<Item, FetchError> { .. }
```

Acceptable: internal (`pub(crate)`) functions, workspace-internal crates owned by one binary, CLI-only crates.

## ERR006: `map_err(|_| ..)`

The original error is thrown away: no `source()`, no cause in logs.

```rust,ignore
// Before
let n: usize = raw.parse().map_err(|_| StoreError::BadCount(raw.to_owned()))?;

// After: keep the cause
#[error("invalid count {input:?}")]
BadCount { input: String, #[source] source: std::num::ParseIntError },

let n: usize = raw.parse().map_err(|source| StoreError::BadCount { input: raw.to_owned(), source })?;
```

Acceptable: when the source genuinely adds nothing and is huge or sensitive (rare); then say so in a comment.

## ERR007: stringly `map_err`

`e.to_string()` or `format!("..: {e}")` keeps the message but loses the type, the chain and any backtrace.

```rust,ignore
// Before
fs::write(dest, json).map_err(|e| format!("write failed: {e}"))?;

// After (application code)
fs::write(&dest, json).with_context(|| format!("writing snapshot to {}", dest.display()))?;

// After (library code)
fs::write(&dest, json).map_err(|source| StoreError::Write { path: dest.to_owned(), source })?;
```

## ERR008: `Result<T, String>`

`String` errors cannot be matched, do not implement `std::error::Error` (no `?` into anyhow, no `source`), and
push formatting into every call site.

- Library: a thiserror enum (generate one with `scaffold_errors`).
- Application: `anyhow::Result<T>` with `bail!("..")`/`.context("..")`.
- `Result<T, ()>`: use `Option<T>` if there is only one failure, or a unit-variant enum.

## ERR009: source printed twice

thiserror's `Display` comes from `#[error(..)]`; `source()` comes from the `#[from]`/`#[source]`/`source` field.
Reporters (`anyhow`'s `{:#}`, `{:?}`, tracing with `std::error::Error` chains, `eyre`) print each layer's
Display and then walk `source()`, so a message that interpolates its own source prints it twice:

```text
Error: i/o error: No such file or directory (os error 2)

Caused by:
    No such file or directory (os error 2)
```

```rust,ignore
// Before
#[error("i/o error: {0}")]
Io(#[from] std::io::Error),

// After: describe this layer only
#[error("i/o error on the store log")]
Io(#[from] std::io::Error),
```

Use `#[error(transparent)]` when the wrapper adds nothing and should forward both Display and `source()`.

## ERR010: exhaustive public error enums

Adding a variant to an exhaustive public enum breaks every downstream `match` (a major release).
`#[non_exhaustive]` lets you add variants in minor releases; callers write a `_ =>` arm. Inside the defining
crate, matches stay exhaustive.

## ERR011: discarded results

`let _ = f();` and `f().ok();` silence the `#[must_use]` warning without handling the failure.

```rust,ignore
// Before
let _ = self.compact();

// After: decide explicitly
if let Err(e) = self.compact() {
    tracing::warn!(error = %e, "compaction failed; continuing with an uncompacted log");
}
```

Acceptable: best-effort cleanup where failure is expected and harmless (`let _ = fs::remove_file(tmp);` in a
`Drop`), ideally with a comment. Note `let _ = x;` drops `x` immediately, whereas `let _guard = x;` keeps it.

## ERR012: `?` without context

`?` on `File::open` produces `No such file or directory (os error 2)` with no path. In application code, add
what was being attempted:

```rust,ignore
let text = fs::read_to_string(&path)
    .with_context(|| format!("reading config {}", path.display()))?;
let cfg: Config = serde_json::from_str(&text)
    .with_context(|| format!("parsing config {}", path.display()))?;
```

Use `.context("static message")` when nothing needs formatting; `with_context` avoids building the string on
success. In libraries, put the path in a variant field instead.

## ERR013: `process::exit` instead of returning

`std::process::exit` does not run destructors (buffered writers are not flushed, temp files stay), cannot be
tested, and makes the function unusable as a library.

```rust,ignore
// Before
fn load_or_exit(path: &str) -> Store {
    match Store::open(path) {
        Ok(s) => s,
        Err(e) => { eprintln!("cannot open store: {e}"); std::process::exit(1) }
    }
}

// After
fn main() -> anyhow::Result<()> {
    let store = Store::open(path).context("opening store")?; // main prints the chain, exits with 1
    run(store)
}
```

For custom exit codes return `std::process::ExitCode` from `main` (see anyhow-context-reporting.md).

## Smells the scripts cannot see

| Smell | Why it hurts | Fix |
|-------|--------------|-----|
| One giant crate-wide `Error` enum | every function "may return" every variant; callers cannot tell what to handle | one enum per module or operation family |
| Variants named after dependencies (`Reqwest(reqwest::Error)`) in a public API | your semver is tied to theirs; callers depend on a crate they never chose | variants by meaning (`Timeout`, `Transport`), dependency error as `#[source]` |
| Logging *and* returning the same error at every layer | the same failure appears 5 times in logs | log once at the edge (handler, main, job runner) |
| Messages with capital letters and trailing periods | chains read "Failed to read. Caused by: Permission denied." | lowercase, no trailing punctuation: `failed to read config` |
| `Display` that exposes secrets, SQL or user data | ends up in logs and HTTP bodies | keep sensitive data out of messages; map 5xx bodies to a generic text |
| `PartialEq` derived on errors only for tests | blocks wrapping non-`PartialEq` sources | `assert!(matches!(..))` in tests instead |
| Retrying every error | retries `NotFound` and validation failures forever | `is_retryable()` on the error type |
| `.unwrap_or_default()` on errors that matter | turns failures into silent wrong data | handle or propagate; default only where it is the specified behaviour |
