# Library vs Application Error Handling

Choosing the error strategy per crate: who consumes the error decides its shape. Code reacts to errors
(match, retry, map to status codes); humans read errors (logs, terminal, bug reports). Libraries serve
code, applications serve humans, and services usually need both at once.

## Contents

- [1. The decision](#1-the-decision)
- [2. thiserror in one page](#2-thiserror-in-one-page)
- [3. anyhow in one page](#3-anyhow-in-one-page)
- [4. Using both in one workspace](#4-using-both-in-one-workspace)
- [5. Alternatives](#5-alternatives)
- [6. Hand-written errors without any crate](#6-hand-written-errors-without-any-crate)
- [7. Migration paths](#7-migration-paths)
- [8. Checklist](#8-checklist)

## 1. The decision

| Question | If yes | If no |
|----------|--------|-------|
| Will another crate (or another module you do not own) `match` on this error? | typed enum (thiserror) | anyhow is fine |
| Is this a `main.rs`, CLI, test, build script, migration tool, one-off job? | anyhow (or eyre) | typed |
| Is the error turned into an HTTP/gRPC status? | typed variants for every non-500 case, plus an `Internal(anyhow::Error)` catch-all | |
| Does the error need source-code snippets with labels? | miette | |
| Do you want colored reports + `tracing` span traces in a CLI? | eyre + color-eyre | anyhow |
| Must the public API hide which dependencies you use? | opaque struct with `kind()` | enum is fine |

Rules of thumb:

- A **library** never returns `anyhow::Error` from a public function. The caller cannot distinguish "not
  found" from "disk full" without downcasting to types you never promised.
- An **application** gains little from a giant crate-wide enum that only ever gets printed. Use anyhow and
  spend the effort on context messages.
- A **service** sits in between: the HTTP layer needs to know "this is a 404", but database and I/O failures
  are all "500, log it". Typed for what callers react to, anyhow for the rest.

## 2. thiserror in one page

```toml
[dependencies]
thiserror = "2"
```

```rust
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum FetchError {
    #[error("invalid url {url:?}")]
    InvalidUrl { url: String, #[source] source: url::ParseError },

    #[error("server returned {status} for {url}")]
    Status { url: String, status: u16 },

    #[error("request to {url} timed out after {timeout_ms} ms")]
    Timeout { url: String, timeout_ms: u64 },

    #[error("transport error")]
    Transport(#[from] std::io::Error),
}
```

What the derive generates:

- `impl std::fmt::Display` from the `#[error(...)]` attributes
- `impl std::error::Error` with `source()` returning the `#[source]`/`#[from]` field (or a field named
  `source`)
- `impl From<std::io::Error> for FetchError` for each `#[from]`

Nothing else. No runtime, no trait objects, no allocation. The generated code only references `std`/`core`
traits, so thiserror is not part of your public API: callers never need to depend on it, and you can remove
it later by writing the impls by hand without a breaking change.

## 3. anyhow in one page

```toml
[dependencies]
anyhow = "1"
```

```rust,ignore
use anyhow::{Context, Result};

fn main() -> Result<()> {
    let url = std::env::var("FEED_URL").context("FEED_URL is not set")?;
    let body = fetch(&url).with_context(|| format!("fetching feed {url}"))?;
    let items = parse_feed(&body).context("parsing feed XML")?;
    println!("{} items", items.len());
    Ok(())
}
```

- `anyhow::Error` holds any `E: std::error::Error + Send + Sync + 'static`, plus a context chain and an
  optional backtrace. It is a single pointer wide, so `Result<T, anyhow::Error>` stays small.
- `anyhow::Result<T>` is `Result<T, anyhow::Error>`; the second parameter defaults, so
  `anyhow::Result<T, MyError>` also works.
- `Context` adds a message layer without losing the original: `err.downcast_ref::<std::io::Error>()` still
  finds it.
- `anyhow::Error` itself does **not** implement `std::error::Error` (that would conflict with its blanket
  `From<E: Error>` impl). It derefs to `dyn Error + Send + Sync + 'static`, implements
  `AsRef<dyn Error + Send + Sync>`, and converts into `Box<dyn Error + Send + Sync + 'static>`.

## 4. Using both in one workspace

```
workspace/
  crates/store/      library: thiserror StoreError, pub type Result<T, E = StoreError>
  crates/indexer/    library: thiserror IndexError { Store(#[from] StoreError), ... }
  crates/api/        service: thiserror ApiError (typed 4xx) + Internal(#[from] anyhow::Error)
  crates/cli/        binary: anyhow everywhere, main() -> anyhow::Result<()>
```

The binary keeps the typed information available:

```rust,ignore
use anyhow::Context;
use store::StoreError;

fn show(id: u64) -> anyhow::Result<()> {
    match store::get(id) {
        Ok(item) => println!("{item}"),
        Err(StoreError::NotFound { .. }) => println!("no item {id}"), // expected case: handled, not an error
        Err(other) => return Err(other).with_context(|| format!("loading item {id}")),
    }
    Ok(())
}

fn exit_code(err: &anyhow::Error) -> u8 {
    // Any layer of the chain can be inspected after context was added.
    if let Some(StoreError::Io(_)) = err.downcast_ref::<StoreError>() { 74 } else { 1 } // 74 = EX_IOERR
}
```

Library-to-library: wrap the lower error as a variant of the higher one when callers of the higher crate
need to react to it; otherwise wrap it as an opaque source with a description of what the higher crate was
doing:

```rust,ignore
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum IndexError {
    #[error("document {doc_id} not found in store")]
    MissingDocument { doc_id: u64 },               // callers react: skip or re-fetch

    #[error("failed to load segment {segment}")]
    Load { segment: u32, #[source] source: store::StoreError }, // callers just report it
}
```

## 5. Alternatives

### snafu (context selectors)

```rust
use snafu::{ResultExt, Snafu};
use std::path::PathBuf;

#[derive(Debug, Snafu)]
pub enum ConfigError {
    #[snafu(display("could not read config {}", path.display()))]
    Read { path: PathBuf, source: std::io::Error },

    #[snafu(display("invalid TOML in {}", path.display()))]
    Parse { path: PathBuf, source: toml::de::Error },
}

pub fn load(path: PathBuf) -> Result<String, ConfigError> {
    let text = std::fs::read_to_string(&path).context(ReadSnafu { path: path.clone() })?;
    Ok(text)
}
```

- Each variant gets a generated "context selector" (`ReadSnafu` since snafu 0.7) that you pass to
  `.context(..)`, so the same source type (`io::Error`) can map to several variants with different context,
  which is exactly where thiserror's `#[from]` stops working.
- Also offers `ensure!`, `whatever!` and a `Whatever` type for application-style stringly errors.
- Choose it when nearly every conversion needs context fields; choose thiserror when most are 1:1.

### eyre and color-eyre

```rust,ignore
use color_eyre::eyre::{Result, WrapErr};

fn main() -> Result<()> {
    color_eyre::install()?;                          // installs panic + error report hooks
    let cfg = std::fs::read_to_string("app.toml").wrap_err("reading app.toml")?;
    run(&cfg)
}
```

- `eyre::Report` is an anyhow fork with a pluggable report handler. `wrap_err`/`wrap_err_with` are the
  equivalents of `context`/`with_context`; `eyre::ContextCompat` provides `.context()` on `Option` for anyhow-style code.
- color-eyre renders colored reports, optional span traces via `tracing-error`, and custom sections
  (`.suggestion(..)`, `.note(..)` from `color_eyre::Section`).
- Choose it for developer-facing CLIs. Do not mix anyhow and eyre in the same binary without reason; pick one.

### miette (diagnostics)

```rust,ignore
use miette::{Diagnostic, NamedSource, SourceSpan};

#[derive(Debug, thiserror::Error, Diagnostic)]
#[error("unknown key `{key}`")]
#[diagnostic(code(config::unknown_key), help("valid keys are: listen, workers, log_level"))]
pub struct UnknownKey {
    key: String,
    #[source_code]
    src: NamedSource<String>,
    #[label("not a recognised key")]
    span: SourceSpan,
}

fn main() -> miette::Result<()> {
    check("app.toml")?;      // fancy report needs miette's "fancy" feature in the binary
    Ok(())
}
```

- miette builds on thiserror: the error is still a std error; `Diagnostic` adds code, help, URL, labels and
  source snippets.
- `miette::IntoDiagnostic::into_diagnostic()` converts ordinary errors into `miette::Report`.
- Choose it for compilers, linters, config validators: anything where the user must see *where* in an
  input the problem is.

### error-stack

- `Report<C>` carries a current context type `C` plus a stack of attachments; at layer boundaries you call
  `.change_context(MyLayerError)` and add data with attachment methods. Good for large codebases that want
  typed contexts and rich attachments; heavier API than thiserror + anyhow. Check the docs of the version
  you use: attachment method names have changed between releases.

### Comparison

| Crate | Error type | Typed matching | Context | Reports | Best for |
|-------|------------|----------------|---------|---------|----------|
| thiserror 2 | your enum/struct | yes | fields in variants, `map_err` | your Display | libraries, service error enums |
| anyhow 1 | `anyhow::Error` | via `downcast_ref` | `.context()` | `{:#}`, `{:?}` with chain + backtrace | binaries, tests |
| snafu | your enum | yes | selectors with fields | your Display | libraries with many contextual wraps |
| eyre + color-eyre | `eyre::Report` | via downcast | `.wrap_err()` | colored, sections, span traces | CLIs |
| miette | your type + `Diagnostic` | yes | labels, help | snippets with labels | compilers, linters, config tools |
| error-stack | `Report<C>` | context type | change_context + attachments | tree of frames | large systems |

## 6. Hand-written errors without any crate

Zero dependencies is a fine choice for small libraries, `no_std` crates or when compile time matters:

```rust
use std::{error::Error, fmt};

#[derive(Debug)]
#[non_exhaustive]
pub enum ParseError {
    Empty,
    BadNumber { line: usize, source: std::num::ParseIntError },
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Empty => f.write_str("input is empty"),
            Self::BadNumber { line, .. } => write!(f, "invalid number on line {line}"),
        }
    }
}

impl Error for ParseError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Empty => None,
            Self::BadNumber { source, .. } => Some(source),
        }
    }
}
```

That is exactly what thiserror would generate for:

```rust
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum ParseError {
    #[error("input is empty")]
    Empty,
    #[error("invalid number on line {line}")]
    BadNumber { line: usize, #[source] source: std::num::ParseIntError },
}
```

## 7. Migration paths

### `Box<dyn Error>` everywhere -> structured

1. Make it at least `Box<dyn Error + Send + Sync + 'static>` (type alias `BoxError`). Nothing else changes,
   and async/threads start working.
2. Binaries: replace the alias with `anyhow::Result`; `?` keeps working for every std error. Add context.
3. Libraries: introduce `pub enum Error` per module, starting with the variants callers already
   distinguish (search for `downcast_ref` and `to_string().contains(` at call sites).

### `Result<T, String>` -> typed

```rust,ignore
// before
pub fn parse_port(s: &str) -> Result<u16, String> {
    s.parse().map_err(|e| format!("bad port {s}: {e}"))
}

// after
#[derive(Debug, thiserror::Error)]
#[error("invalid port {input:?}")]
pub struct PortError {
    input: String,
    #[source]
    source: std::num::ParseIntError,
}

pub fn parse_port(s: &str) -> Result<u16, PortError> {
    s.parse().map_err(|source| PortError { input: s.to_owned(), source })
}
```

### Library returning anyhow -> typed

Keep anyhow internally while you migrate: add a temporary catch-all variant and shrink it over time.

```rust
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum Error {
    #[error("record {0} not found")]
    NotFound(u64),
    /// Temporary: everything not yet classified. Remove before 1.0.
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}
```

`#[non_exhaustive]` lets you split `Other` into real variants later without a breaking release (callers
already have a `_ =>` arm).

### anyhow -> eyre (or back)

Mostly mechanical: `anyhow::Result` -> `eyre::Result`, `Context::context` -> `WrapErr::wrap_err`,
`anyhow!` -> `eyre!`, `bail!`/`ensure!` exist in both. Install the report hook first thing in `main`.

## 8. Checklist

- [ ] Every library crate exposes typed errors; no `anyhow` in `pub fn` signatures
- [ ] Every binary returns `anyhow::Result<()>` (or `ExitCode`) from `main`
- [ ] Error enums are `#[non_exhaustive]` and `Send + Sync + 'static`
- [ ] No dependency error type you intend to swap is a public field or `#[from]`
- [ ] Services: one `ApiError` with typed 4xx variants and an `Internal` catch-all
- [ ] Context added on every `?` that crosses an I/O or parse boundary in application code
