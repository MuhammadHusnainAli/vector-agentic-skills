# Version History: Error Handling in Rust

Standard-library error features by Rust version, the thiserror 1 to 2 migration, and anyhow notes, so advice
matches the project's MSRV and dependency versions.

## Contents

- [Standard library](#standard-library)
- [thiserror 1 -> 2](#thiserror-1---2)
- [anyhow](#anyhow)
- [Still unstable](#still-unstable)
- [MSRV guidance](#msrv-guidance)

## Standard library

| Rust | Feature | Before it |
|------|---------|-----------|
| 1.13 | the `?` operator (for `Result`) | the `try!` macro |
| 1.22 | `?` on `Option` | `.ok_or(..)?` / `match` |
| 1.26 | `main` may return `Result<(), E: Debug>` | `std::process::exit` after printing |
| 1.30 | `Error::source` (replaces `cause`) | `Error::cause` (deprecated) |
| 1.34 | `TryFrom`/`TryInto` | custom fallible constructors |
| 1.42 | `matches!` macro | `match .. { X => true, _ => false }` |
| 1.61 | `std::process::ExitCode` and `Termination` for custom exit codes | `process::exit(n)` |
| 1.65 | `std::backtrace::Backtrace`; `let ... else` | the `backtrace` crate; nested `match` |
| 1.81 | `core::error::Error` (the `Error` trait in `core`, usable in `no_std`) | std-only errors or crate-specific traits |

Notes:

- `Backtrace::capture()` respects `RUST_BACKTRACE` and `RUST_LIB_BACKTRACE`; `Backtrace::force_capture()`
  always captures. Capturing is expensive: do it at error creation in rare paths only.
- `fn main() -> Result<(), E>` prints `Error: {e:?}` (the Debug form) and exits with code 1.
- `Error::description` is deprecated (since 1.42); implement `Display` instead.

## thiserror 1 -> 2

thiserror 2.0 (November 2024) is a small migration for most code:

| Area | Change |
|------|--------|
| `no_std` | supported: disable default features (`default-features = false`) to use `core::error::Error` |
| MSRV | raised (thiserror 2 needs a newer Rust than 1.x did; check the crate's `rust-version`) |
| Raw identifiers in messages | a field `r#type` is referred to as `{type}` in `#[error("..")]`, not `{r#type}` |
| Generated code | refers to `::thiserror` paths, so the crate deriving `Error` needs `thiserror` as a direct dependency (not only a re-export) |

Migration steps: bump to `thiserror = "2"`, `cargo check`, fix any raw-identifier placeholders, run tests that
pin `Display` text. Both majors can coexist in one dependency graph (different crates).

## anyhow

- anyhow 1.x is stable and backwards compatible; `anyhow::Error` requires `Send + Sync + 'static` sources.
- Backtraces: on Rust 1.65+ anyhow uses `std::backtrace` and captures when `RUST_BACKTRACE=1` or
  `RUST_LIB_BACKTRACE=1` is set; printed by the `{:?}` report.
- `Result<T, anyhow::Error>` alias: `anyhow::Result<T>`; `anyhow::Ok(v)` helps type inference in closures.
- Formats: `{}` outermost message, `{:#}` whole chain on one line joined by `: `, `{:?}` multi-line report with
  `Caused by:` and the backtrace, `{:#?}` struct-style debug.
- Alternatives with similar APIs: `eyre`/`color-eyre` (customisable reports), `miette` (diagnostics with source
  spans), `error-stack` (typed contexts with attachments).

## Still unstable

| Feature | Stable alternative |
|---------|-------------------|
| `try` blocks (`try { .. }`) | an immediately-called closure `(|| -> Result<_, _> { .. })()` or a helper fn |
| `Error::provide` / generic member access | store data (backtraces, codes) in fields and expose accessors |
| `Try` trait for custom types (`?` on your own type) | return `Result`/`Option`, or convert with `.into()` |
| `never` type (`!`) in more positions | `std::convert::Infallible` |

## MSRV guidance

- Below 1.81: no `core::error::Error`; `no_std` libraries need their own error trait or a feature-gated std impl.
- Below 1.65: no `std::backtrace`; use the `backtrace` crate or skip backtraces.
- Below 1.61: no `ExitCode`; exit codes need `process::exit` (accept ERR013 there, or upgrade).
- Check thiserror 2's own `rust-version` before upgrading a crate with an old MSRV; staying on thiserror 1 is
  fine if the MSRV cannot move.
