# Designing Typed Errors with thiserror 2

Everything needed to write a library error type that callers can match on, that reports cleanly through
any `source()`-walking reporter, and that can evolve without breaking releases.

## Contents

- [1. Attribute reference](#1-attribute-reference)
- [2. Format strings](#2-format-strings)
- [3. Sources, from and transparent](#3-sources-from-and-transparent)
- [4. Granularity: one enum per what?](#4-granularity-one-enum-per-what)
- [5. Variants by caller reaction](#5-variants-by-caller-reaction)
- [6. Context fields instead of strings](#6-context-fields-instead-of-strings)
- [7. Evolving errors: non_exhaustive and helpers](#7-evolving-errors-non_exhaustive-and-helpers)
- [8. Not leaking dependency types](#8-not-leaking-dependency-types)
- [9. The ErrorKind / opaque struct pattern](#9-the-errorkind--opaque-struct-pattern)
- [10. Size, Clone, PartialEq and generics](#10-size-clone-partialeq-and-generics)
- [11. Backtraces in typed errors](#11-backtraces-in-typed-errors)
- [12. Message style](#12-message-style)

## 1. Attribute reference

| Attribute | Where | Meaning |
|-----------|-------|---------|
| `#[derive(Debug, thiserror::Error)]` | enum or struct | implements `Display` (from `#[error]`) and `std::error::Error` |
| `#[error("...")]` | each enum variant, or the struct | Display message with format args |
| `#[error(transparent)]` | variant or struct with exactly one field | forward `Display` and `source()` to that field |
| `#[source]` | one field | returned by `Error::source()` |
| field named `source` | one field | treated as `#[source]` automatically |
| `#[from]` | the (only) field of a variant | implies `#[source]` and generates `impl From<FieldType>` |
| `#[backtrace]` / `Backtrace` field | field | provides a backtrace through the unstable `Error::provide` API (nightly only) |

Constraints the derive enforces at compile time:

- A `#[from]` variant may contain only the source field (and optionally a backtrace field). Context fields
  next to it are rejected: `From` would not know what to put in them.
- Two variants with `#[from]` of the same type produce two `From` impls: error E0119 "conflicting
  implementations". Use `#[from]` on one, `#[source]` + `map_err` on the other.
- `#[error(transparent)]` requires exactly one field.
- Every variant of an enum needs its own `#[error("...")]` or `#[error(transparent)]`.

## 2. Format strings

```rust
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("missing key `{0}`")]                               // tuple field by index
    Missing(String),

    #[error("{key} must be between {min} and {max}, got {value}")] // named fields
    OutOfRange { key: &'static str, min: i64, max: i64, value: i64 },

    #[error("unexpected value {value:?} for {key}")]            // Debug formatting quotes strings
    Unexpected { key: String, value: String },

    #[error("cannot read {}", .path.display())]                 // extra args; `.field` refers to a field
    Read { path: std::path::PathBuf, #[source] source: std::io::Error },

    #[error("invalid {type} literal")]                          // thiserror 2: field r#type, written {type}
    Literal { r#type: &'static str },

    #[error("limit is {limit}", limit = usize::MAX)]            // named extra argument
    TooBig,
}
```

Rules:

- Placeholders are standard `format!` syntax: `{field}`, `{field:?}`, `{0}`, `{0:>8}`, `{{` for a literal brace.
- Additional arguments after the string can reference fields with a leading dot: `.0`, `.path`,
  `.items.len()`.
- `{field}` requires the field to implement `Display`. `PathBuf` does not: use `{path:?}` or
  `.path.display()`.
- thiserror 2: raw identifiers are written unraw inside the string (`{type}` for `r#type`); `{r#type}` is
  rejected. Tuple variants can no longer mix numeric `{0}` access with extra positional arguments in the
  same message (it was ambiguous).

## 3. Sources, from and transparent

```rust,ignore
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum SyncError {
    // 1:1 wrap, no context needed: `?` converts automatically.
    #[error("sync transport failed")]
    Transport(#[from] std::io::Error),

    // Same source type, different meaning: no #[from], build it with map_err.
    #[error("failed to write checkpoint {path:?}")]
    Checkpoint { path: std::path::PathBuf, #[source] source: std::io::Error },

    // Forward everything: this layer adds no information.
    #[error(transparent)]
    Remote(#[from] RemoteError),
}

fn save_checkpoint(path: &std::path::Path, bytes: &[u8]) -> Result<(), SyncError> {
    std::fs::write(path, bytes).map_err(|source| SyncError::Checkpoint { path: path.to_owned(), source })
}
```

### The double-print rule

A reporter walks the chain: `outer.to_string()`, then `outer.source().to_string()`, and so on. If the outer
Display already contains the inner message, the reader sees it twice:

```rust,ignore
// bad: Display includes the source AND source() returns it
#[error("failed to read config: {0}")]
Read(#[from] std::io::Error),
```
```
Error: failed to read config: No such file or directory (os error 2)

Caused by:
    No such file or directory (os error 2)
```

```rust,ignore
// good: describe this layer only
#[error("failed to read config")]
Read(#[from] std::io::Error),
```
```
Error: failed to read config

Caused by:
    No such file or directory (os error 2)
```

Pick one: either print the inner error in Display and return `None` from `source()` (a leaf error that
flattens its cause, rarely right), or return it from `source()` and leave it out of Display (almost always
right). `#[error(transparent)]` is the explicit "this layer is invisible" choice: Display and `source()`
both delegate, so nothing is duplicated.

When you only ever display `{}` (no reporter walks the chain), the source is invisible. That is the
reporter's job: use anyhow's `{:#}`/`{:?}`, or a loop over `source()` (see
[anyhow-context-reporting.md](anyhow-context-reporting.md)).

## 4. Granularity: one enum per what?

| Shape | Pros | Cons | Use when |
|-------|------|------|----------|
| One crate-wide `Error` | simple imports, one `Result` alias | every function "can return" every variant; docs lie | small crates (< ~10 variants) |
| One enum per module (`store::Error`, `index::Error`) | variants match the module's operations | some duplication | most libraries |
| One enum per operation (`OpenError`, `QueryError`) | precise: callers match only possible cases | many types, conversion boilerplate | public APIs where precision matters (std does this: `ParseIntError`, `TryFromIntError`) |
| Struct + kind (`io::Error` style) | stable API, hide internals | less pattern matching ergonomics | large public crates with changing internals |

A good default: one enum per module, plus dedicated small error structs for leaf operations that can fail
in exactly one way (`ParsePortError`).

## 5. Variants by caller reaction

Group failures by what the caller will do, not by which dependency produced them.

| Variant | Caller reaction | Retryable | HTTP |
|---------|-----------------|-----------|------|
| `NotFound { id }` | show 404 / create it | no | 404 |
| `AlreadyExists { id }` | treat as success or 409 | no | 409 |
| `Conflict { id, expected, actual }` | re-read and retry the read-modify-write | yes | 409 |
| `InvalidInput { field, reason }` | tell the user | no | 400/422 |
| `Unauthorized` / `Forbidden` | re-authenticate / deny | no | 401/403 |
| `Busy` / `RateLimited { retry_after }` | back off and retry | yes | 503/429 |
| `Timeout { op, after }` | retry if idempotent | yes | 504 |
| `Io(io::Error)` / `Backend { source }` | report; maybe retry by kind | depends | 500/503 |
| `Corrupted { path, offset }` | alert, never retry | no | 500 |

If two variants always get the same reaction, merge them. If one variant needs two reactions depending on
a detail, split it or add a `kind()`/`is_retryable()` helper.

## 6. Context fields instead of strings

```rust,ignore
// bad: the only way to learn the id is to parse the message
#[error("{0}")]
NotFound(String),               // built with format!("user {id} not found")

// good: data first, message derived from data
#[error("user {id} not found")]
NotFound { id: u64 },
```

Fields let callers act (`if let Err(StoreError::NotFound { id }) = ..`), let logs be structured, and keep
messages consistent. Include what an operator needs to reproduce: ids, paths, offsets, limits, the
operation name. Do not include secrets or whole payloads.

## 7. Evolving errors: non_exhaustive and helpers

```rust
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum StoreError {
    #[error("record {id} not found")]
    #[non_exhaustive]                 // fields can be added later, too
    NotFound { id: u64 },
    #[error("store i/o failed")]
    Io(#[from] std::io::Error),
}

impl StoreError {
    pub fn is_not_found(&self) -> bool {
        matches!(self, Self::NotFound { .. })
    }
}
```

- `#[non_exhaustive]` on the enum forces downstream `match` to include `_ =>`, so new variants are not
  breaking. Inside your own crate, matches stay exhaustive (you still get compiler help).
- `#[non_exhaustive]` on a variant prevents downstream code from constructing it and requires `..` in
  patterns, so adding a field is not breaking.
- Helper predicates (`is_not_found()`, `is_retryable()`) give callers a stable API even if variants are
  reorganised.

## 8. Not leaking dependency types

Every type appearing in a public variant is part of your API. `#[from] reqwest::Error` means a reqwest
major bump is your major bump, and callers may start matching on reqwest internals.

Options, from lightest to strongest:

```rust,ignore
// 1. Keep it as a source, but not a public field type: box it.
#[error("http request to {url} failed")]
Http { url: String, #[source] source: Box<dyn std::error::Error + Send + Sync> },

// 2. Wrap it in your own opaque newtype.
#[derive(Debug, thiserror::Error)]
#[error(transparent)]
pub struct TransportError(reqwest::Error);     // private field: callers can't touch reqwest::Error

#[error("http request to {url} failed")]
Http { url: String, #[source] source: TransportError },

// 3. Classify at the edge and keep only what callers need.
#[error("http {status} from {url}")]
Status { url: String, status: u16 },
```

Constructing option 1 from a concrete error: `map_err(|e| Error::Http { url, source: Box::new(e) })`
(or `e.into()`).

It is fine to expose `std` types (`std::io::Error`, `std::num::ParseIntError`) and types from crates you
already expose elsewhere in your API.

## 9. The ErrorKind / opaque struct pattern

`std::io::Error` exposes a stable `kind()` and keeps its representation private. Use it when the set of
causes is large, changes often, or comes from many dependencies.

```rust
use std::{error::Error as StdError, fmt};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum ErrorKind {
    NotFound,
    PermissionDenied,
    InvalidInput,
    Unavailable,
    Other,
}

#[derive(Debug)]
pub struct Error {
    kind: ErrorKind,
    message: String,
    source: Option<Box<dyn StdError + Send + Sync + 'static>>,
}

impl Error {
    pub fn kind(&self) -> ErrorKind {
        self.kind
    }

    pub fn is_retryable(&self) -> bool {
        self.kind == ErrorKind::Unavailable
    }

    pub(crate) fn new(kind: ErrorKind, message: impl Into<String>) -> Self {
        Self { kind, message: message.into(), source: None }
    }

    pub(crate) fn with_source(mut self, source: impl StdError + Send + Sync + 'static) -> Self {
        self.source = Some(Box::new(source));
        self
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl StdError for Error {
    fn source(&self) -> Option<&(dyn StdError + 'static)> {
        self.source.as_deref().map(|e| e as &(dyn StdError + 'static))
    }
}

// Internal conversions stay private to the crate's behaviour, not its types:
impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        let kind = match e.kind() {
            std::io::ErrorKind::NotFound => ErrorKind::NotFound,
            std::io::ErrorKind::PermissionDenied => ErrorKind::PermissionDenied,
            std::io::ErrorKind::TimedOut | std::io::ErrorKind::Interrupted => ErrorKind::Unavailable,
            _ => ErrorKind::Other,
        };
        Error::new(kind, "i/o error").with_source(e)
    }
}
```

Callers: `match err.kind() { ErrorKind::NotFound => .., _ => .. }`. You can add kinds, change sources
and swap dependencies freely.

## 10. Size, Clone, PartialEq and generics

- `Result<T, E>` is at least as large as `E`. A 200-byte error makes every `Ok` path move 200 bytes.
  `clippy::result_large_err` warns above 128 bytes. Fix by boxing the big variant's payload
  (`Box<LargeContext>`) or the whole error (`pub struct Error(Box<ErrorInner>)`).
- `std::io::Error` is not `Clone` and not `PartialEq`, so enums containing it cannot derive them. Test with
  `matches!` instead of `assert_eq!` (see [testing-errors.md](testing-errors.md)). If you must share an
  error between consumers, wrap it in `Arc`.
- Generic errors work: `#[derive(Debug, thiserror::Error)] pub enum SendError<T> { #[error("channel
  closed")] Closed(T) }`. thiserror infers the bounds its Display impl needs from the fields you
  format; `T` still needs `Debug` (Error requires it) and `'static` to be boxed or used as a source.
- Errors must be `'static` to be used as `source()` or boxed as `dyn Error + 'static`: avoid borrowed
  fields (`&'a str`); use `String`, `Box<str>`, `Arc<str>` or `&'static str`.

## 11. Backtraces in typed errors

Stable Rust has `std::backtrace::Backtrace` (1.65) but not the `provide` API that lets reporters find a
backtrace inside an arbitrary error. **thiserror treats any field whose type is named `Backtrace` specially:
it generates a `provide()` impl that only compiles on nightly** (`error_generic_member_access`). On stable,
derive nothing for such a type and write the two small impls by hand:

```rust
use std::backtrace::Backtrace;
use std::fmt;

#[derive(Debug)]
pub struct InvariantError {
    what: &'static str,
    backtrace: Backtrace,             // captured explicitly; respects RUST_BACKTRACE / RUST_LIB_BACKTRACE
}

impl InvariantError {
    pub fn new(what: &'static str) -> Self {
        Self { what, backtrace: Backtrace::capture() }
    }

    pub fn backtrace(&self) -> &Backtrace {
        &self.backtrace
    }
}

impl fmt::Display for InvariantError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "invariant violated: {}", self.what)
    }
}

impl std::error::Error for InvariantError {}
```

Most applications get backtraces from anyhow instead: the `anyhow::Error` created at the first `?` captures
one (when enabled), which points close enough to the failure.

## 12. Message style

Follow the std/API guidelines convention:

- lowercase, no trailing period: `"invalid digit found in string"`
- describe what failed at this layer: `"failed to open store log"`, not `"error"` or `"oops"`
- no `"error: "` prefix (the reporter adds it), no source text (the chain adds it)
- name the thing: `"user {id} not found"`, `"config key `{key}` is missing"`
- use `{:?}` for user-provided strings so whitespace and empty values are visible: `"invalid name {name:?}"`
