# anyhow: Context, Downcasting and Reporting

How applications should propagate, enrich, inspect and finally report errors, with anyhow 1.x and std.
Covers `main`, `ExitCode`, custom `Termination`, backtraces and logging with `tracing`.

## Contents

- [1. The API surface](#1-the-api-surface)
- [2. Adding context well](#2-adding-context-well)
- [3. bail!, ensure!, anyhow!](#3-bail-ensure-anyhow)
- [4. Downcasting and inspecting the chain](#4-downcasting-and-inspecting-the-chain)
- [5. Report formats](#5-report-formats)
- [6. Backtraces](#6-backtraces)
- [7. main, ExitCode and Termination](#7-main-exitcode-and-termination)
- [8. Logging errors once with tracing](#8-logging-errors-once-with-tracing)
- [9. Interop: Box dyn Error, String errors, closures](#9-interop-box-dyn-error-string-errors-closures)
- [10. Pitfalls](#10-pitfalls)

## 1. The API surface

| Item | Signature / behaviour |
|------|-----------------------|
| `anyhow::Error` | boxed error + context chain + optional backtrace; one pointer wide |
| `anyhow::Result<T, E = anyhow::Error>` | alias for `core::result::Result<T, E>` |
| `Context::context(self, ctx)` | on `Result<T, E>` (E: std error or anyhow::Error) and `Option<T>`; wraps the error with `ctx` (Display + Send + Sync + 'static) |
| `Context::with_context(self, \|\| ctx)` | same, but the closure runs only on the error path |
| `anyhow!(..)` / `format_err!(..)` | build an `anyhow::Error` from a format string or from an error value |
| `bail!(..)` | `return Err(anyhow!(..))` |
| `ensure!(cond, ..)` | `if !cond { bail!(..) }` |
| `Error::msg(m)` | error from any `Display + Debug + Send + Sync + 'static` (e.g. a `String`) |
| `Error::new(e)` | from a std error (same as `e.into()`) |
| `err.context(ctx)` | add a layer to an existing `anyhow::Error` |
| `err.downcast_ref::<T>()`, `downcast_mut`, `downcast`, `is::<T>()` | typed access to the original error or any context value |
| `err.chain()` | iterator over `&(dyn Error + 'static)`: outermost first |
| `err.root_cause()` | the innermost error |
| `err.backtrace()` | `&std::backtrace::Backtrace` (Rust 1.65+) |
| `anyhow::Ok(v)` | `Ok::<_, anyhow::Error>(v)`; helps inference in closures/async blocks |

## 2. Adding context well

Context answers "what were we doing?" at each hop. The source answers "what went wrong?".

```rust,ignore
use anyhow::{Context, Result};
use std::path::Path;

fn import(dir: &Path) -> Result<usize> {
    let mut count = 0;
    for entry in std::fs::read_dir(dir).with_context(|| format!("listing {}", dir.display()))? {
        let path = entry.context("reading directory entry")?.path();
        let text = std::fs::read_to_string(&path)
            .with_context(|| format!("reading {}", path.display()))?;
        let rows: Vec<Row> = serde_json::from_str(&text)
            .with_context(|| format!("parsing {} as JSON rows", path.display()))?;
        count += store_rows(&rows).with_context(|| format!("storing rows from {}", path.display()))?;
    }
    Ok(count)
}
```

Guidelines:

- **Every I/O, parse, network or subprocess `?` in application code gets context.** A bare
  `No such file or directory (os error 2)` does not say which file. The audit flags these as ERR012.
- **Name the input** (path, URL, id, line number), not the function: `"reading users.csv"` beats
  `"read_users failed"`.
- **`context` for literals, `with_context` for anything that allocates** (`format!`), so the success path
  stays free.
- **Don't repeat the cause** in the context: `"reading config"`, not `"reading config: {err}"`.
- **Context on `Option`** turns "missing" into an error with a message:
  `let home = std::env::var_os("HOME").context("HOME is not set")?;`
- **Context on library errors** keeps them typed: after `store.get(id).context("loading user")?`,
  `err.downcast_ref::<StoreError>()` still works.

## 3. bail!, ensure!, anyhow!

```rust
use anyhow::{anyhow, bail, ensure, Result};

fn parse_range(s: &str) -> Result<(u32, u32)> {
    let (a, b) = s.split_once("..").ok_or_else(|| anyhow!("expected START..END, got {s:?}"))?;
    let (a, b): (u32, u32) = (a.parse()?, b.parse()?);
    ensure!(a <= b, "range start {a} is after end {b}");
    if b - a > 10_000 {
        bail!("range {s:?} is too large ({} items, max 10000)", b - a);
    }
    Ok((a, b))
}
```

- `anyhow!(err_value)` with a single expression that is an error keeps it as the source (it is not
  stringified); with a format string it creates a message-only error.
- `bail!(MyError::Locked { id })` returns a typed error that is still downcastable.
- Prefer a typed error over `bail!` when callers will want to react to this specific case.

## 4. Downcasting and inspecting the chain

```rust,ignore
fn exit_code_for(err: &anyhow::Error) -> u8 {
    if let Some(e) = err.downcast_ref::<StoreError>() {
        return match e {
            StoreError::NotFound { .. } => 66, // EX_NOINPUT
            _ => 74,                           // EX_IOERR
        };
    }
    if let Some(io) = err.root_cause().downcast_ref::<std::io::Error>() {
        if io.kind() == std::io::ErrorKind::PermissionDenied {
            return 77; // EX_NOPERM
        }
    }
    1
}
```

What `downcast_ref::<T>()` can see:

- the original error value passed into anyhow (`?` conversion, `Error::new`, `anyhow!(e)`)
- any context value added with `.context(C)` (downcast to `C`, e.g. a `&'static str` or your own
  context struct)
- **not** errors further down the `source()` chain of that original error. For those, iterate:

```rust,ignore
let is_timeout = err.chain().any(|cause| {
    cause.downcast_ref::<std::io::Error>().is_some_and(|e| e.kind() == std::io::ErrorKind::TimedOut)
});
```

(`Option::is_some_and` is stable since Rust 1.70.)

Downcasting is for the few places that decide policy (exit codes, retry, HTTP mapping). If many call sites
downcast the same type, that code wants a typed error instead of anyhow.

## 5. Report formats

Given `Err(io_err).context("reading app.toml").context("loading configuration")`:

| Format | Output |
|--------|--------|
| `{}` | `loading configuration` |
| `{:#}` | `loading configuration: reading app.toml: No such file or directory (os error 2)` |
| `{:?}` | multi-line report (below) |
| `{:#?}` | Rust struct-style Debug of the error and its parts; for debugging anyhow itself |

```
loading configuration

Caused by:
    0: reading app.toml
    1: No such file or directory (os error 2)

Stack backtrace:
   0: ...
```

The `Stack backtrace:` section appears only when a backtrace was captured. With a single cause the list is
not numbered.

For your own typed errors without anyhow, write the chain yourself:

```rust
pub fn report(err: &(dyn std::error::Error + 'static)) -> String {
    let mut out = err.to_string();
    let mut source = err.source();
    while let Some(cause) = source {
        out.push_str("\n  caused by: ");
        out.push_str(&cause.to_string());
        source = cause.source();
    }
    out
}
```

(`std::error::Report` does this in std but is unstable; do not depend on it.)

## 6. Backtraces

| Variable | Effect on anyhow / `Backtrace::capture()` | Effect on panics |
|----------|------------------------------------------|------------------|
| unset | no capture | no backtrace |
| `RUST_BACKTRACE=1` | capture | short backtrace |
| `RUST_BACKTRACE=full` | capture | full backtrace |
| `RUST_LIB_BACKTRACE=1` | capture (overrides RUST_BACKTRACE for errors) | unchanged |
| `RUST_LIB_BACKTRACE=0` with `RUST_BACKTRACE=1` | no capture | backtrace |

- The setting is read once and cached; set it before the first error is created (in the environment, not
  midway through the program).
- Capturing costs microseconds to milliseconds; for errors on hot paths (cache misses as errors, parse
  retries) keep it off in production or use `RUST_LIB_BACKTRACE=0`.
- Backtraces need debug info to be useful: `[profile.release] debug = "line-tables-only"`
  gives file:line without full debug info size.
- `Backtrace::force_capture()` ignores the variables; `Backtrace::status()` tells whether one was captured.
- Typed thiserror errors do not get backtraces automatically on stable; see
  [thiserror-design.md](thiserror-design.md#11-backtraces-in-typed-errors).

## 7. main, ExitCode and Termination

### Return anyhow::Result

```rust,ignore
fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    run(args)
}
```

On `Err`, std's `Termination` impl for `Result<(), E: Debug>` prints `Error: {err:?}` to stderr and exits
with code 1. With anyhow, `{:?}` is the full report (chain + backtrace). With a plain `io::Error` it is the
ugly `Os { code: 2, kind: NotFound, message: "..." }`, which is why `main` should return anyhow (or eyre)
rather than a raw std error.

### Return ExitCode for custom codes and formatting

```rust,ignore
use std::process::ExitCode;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("error: {err:#}");                 // one line for users
            if std::env::var_os("APP_DEBUG").is_some() {
                eprintln!("{err:?}");                    // full report for developers
            }
            ExitCode::from(exit_code_for(&err))
        }
    }
}
```

`ExitCode` and custom `Termination` impls are stable since Rust 1.61. Returning from `main` (unlike
`std::process::exit`) runs destructors: buffered writers flush, temp files are removed, tracing
subscribers flush.

### Custom Termination

```rust,ignore
use std::process::{ExitCode, Termination};

enum Outcome {
    Done,
    NothingToDo,
    Failed(anyhow::Error),
}

impl Termination for Outcome {
    fn report(self) -> ExitCode {
        match self {
            Outcome::Done => ExitCode::SUCCESS,
            Outcome::NothingToDo => ExitCode::from(3),
            Outcome::Failed(err) => {
                eprintln!("error: {err:?}");
                ExitCode::FAILURE
            }
        }
    }
}

fn main() -> Outcome {
    match sync_all() {
        Ok(0) => Outcome::NothingToDo,
        Ok(_) => Outcome::Done,
        Err(err) => Outcome::Failed(err),
    }
}
```

### Async main

```rust,ignore
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cfg = load_config().await.context("loading configuration")?;
    serve(cfg).await
}
```

## 8. Logging errors once with tracing

Policy: **handle, or add context and return. Never log and return.** Logging at every layer produces the
same failure N times with partial context each time. Log at the boundary that decides the outcome (request
handler, job loop, `main`).

```rust,ignore
// worker loop: the boundary
loop {
    let job = queue.next().await?;
    if let Err(err) = process(&job).await {
        tracing::error!(job_id = %job.id, error = %format!("{err:#}"), "job failed");
        queue.nack(job.id).await?;
    }
}
```

| Field syntax | Records | For anyhow::Error |
|--------------|---------|-------------------|
| `error = %err` | Display | outermost message only |
| `error = %format!("{err:#}")` | Display of the chain | `outer: inner: root` (recommended) |
| `error = ?err` | Debug | full multi-line report incl. backtrace |
| `error = &err as &(dyn std::error::Error + 'static)` | the error as a `tracing` error value | for typed errors that are `'static`; subscribers may render the chain |

`#[tracing::instrument(err)]` emits an ERROR event with the returned error's Display when the function
returns `Err`; `err(Debug)` uses Debug. If you use it, do not also log the same error in the caller.

```rust,ignore
#[tracing::instrument(skip(db), err)]
async fn create_user(db: &Db, email: &str) -> Result<UserId, ApiError> {
    db.insert_user(email).await.context("inserting user").map_err(ApiError::from)
}
```

Severity guidance: client mistakes (4xx) at `debug`/`info` (or not at all), dependency failures that were
retried successfully at `warn`, failures that reached the user at `error`.

## 9. Interop: Box dyn Error, String errors, closures

```rust,ignore
// anyhow -> Box<dyn Error + Send + Sync> (e.g. a framework that wants BoxError)
fn handler() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    inner().map_err(Into::into)          // From<anyhow::Error> for Box<dyn Error + Send + Sync + 'static>
}

// Box<dyn Error + Send + Sync> -> anyhow: the anyhow! macro accepts it and keeps the source chain
fn call_plugin() -> anyhow::Result<()> {
    plugin_run().map_err(|e| anyhow::anyhow!(e))
}

// String / &str errors -> anyhow
fn legacy() -> anyhow::Result<u32> {
    old_api().map_err(anyhow::Error::msg)  // old_api() -> Result<u32, String>
}

// anyhow::Error where &dyn Error is needed
fn log_it(err: &anyhow::Error) {
    let e: &(dyn std::error::Error + Send + Sync + 'static) = err.as_ref();
    eprintln!("{e}");
}
```

Closures and async blocks often cannot infer the error type for `?`:

```rust,ignore
let parsed = (|| {
    let a: u32 = x.parse()?;
    let b: u32 = y.parse()?;
    anyhow::Ok(a + b)                       // pins the error type to anyhow::Error
})()?;

let task = tokio::spawn(async move {
    let body = fetch(&url).await?;
    Ok::<_, anyhow::Error>(body.len())      // same idea with turbofish
});
let len = task.await.context("fetch task panicked or was cancelled")??;
```

## 10. Pitfalls

| Pitfall | Why it hurts | Fix |
|---------|--------------|-----|
| `.context(format!("reading {path}"))` | allocates on success too | `.with_context(\|\| format!(..))` |
| context that repeats the error: `.with_context(\|\| format!("failed: {e}"))` | doubled text in reports | describe the operation only |
| `err.to_string()` in logs | drops the chain | `format!("{err:#}")` or `?err` |
| `anyhow::Error` in library `pub fn` | callers cannot match | typed errors; see [library-vs-application.md](library-vs-application.md) |
| downcasting to a type wrapped deep inside another error's `source()` | `downcast_ref` only sees the top value and contexts | `err.chain().find_map(\|c\| c.downcast_ref::<T>())` |
| `main` printing with `eprintln!("{err}")` then `exit(1)` | loses chain, skips destructors | return the error or `ExitCode` |
| `unwrap()` on `serde_json::from_str` in a CLI | panic message + backtrace instead of a clear error | `.with_context(\|\| format!("parsing {path}"))?` |
| expecting backtraces in release without debug info | frames show addresses only | `debug = "line-tables-only"` in release profile |
