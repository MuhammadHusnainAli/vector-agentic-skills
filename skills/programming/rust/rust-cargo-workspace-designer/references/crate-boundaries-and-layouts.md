# Crate Boundaries and Workspace Layouts

How to decide what becomes a crate, how to arrange crates on disk, how to name them, and how to keep the
dependency graph layered. Everything here is about *structure*; manifest keys are in
[manifest-and-inheritance.md](manifest-and-inheritance.md), build speed in [build-performance.md](build-performance.md).

## Contents

- [The unit of compilation](#the-unit-of-compilation)
- [Split or keep together](#split-or-keep-together)
- [Layout patterns](#layout-patterns)
- [Virtual manifest vs root package](#virtual-manifest-vs-root-package)
- [Naming](#naming)
- [Layering and the dependency graph](#layering-and-the-dependency-graph)
- [Proc-macro crates](#proc-macro-crates)
- [-sys crates, build.rs and links](#-sys-crates-buildrs-and-links)
- [The xtask pattern](#the-xtask-pattern)
- [Tests, benches and examples](#tests-benches-and-examples)
- [Refactoring a monolith into a workspace](#refactoring-a-monolith-into-a-workspace)
- [Anti-patterns](#anti-patterns)

## The unit of compilation

A crate is what `rustc` compiles in one invocation. That has consequences you cannot get around:

| Property | Inside one crate | Across crates |
|----------|------------------|---------------|
| Parallelism | codegen is split into codegen units, but type checking and borrow checking are mostly serial | independent crates compile in parallel; a dependent can start once its dependencies' metadata is ready (pipelining) |
| Incremental rebuild | incremental compilation reuses unchanged query results, but the crate is always re-analysed | an untouched crate is not recompiled at all, unless something it depends on changed |
| Privacy | `pub(crate)`, `pub(super)` | only `pub` items are visible; the boundary is enforced by the compiler |
| Inlining | anything can be inlined | non-generic functions are only inlined with `#[inline]` or LTO; generics are monomorphised in the caller crate |
| Coherence | impls anywhere in the crate | orphan rule: `impl ForeignTrait for ForeignType` is forbidden |
| Cycles | modules may reference each other freely | crates may not form a dependency cycle (normal/build edges) |

So a crate boundary is a performance tool *and* an API. Splitting along a line that the code crosses all the
time gives you neither speed nor clarity.

## Split or keep together

Split when at least one of these is true:

1. **Proc-macros.** A `proc-macro = true` crate can export only procedural macros. Derives, attribute macros
   and function-like proc macros always need their own crate.
2. **A crate is on the critical path of the build** and `cargo build --timings` shows it compiling alone
   while cores sit idle. Splitting it into two halves that do not depend on each other lets them build in
   parallel.
3. **A heavy dependency is only needed by part of the code** (sqlx, tonic, wgpu, polars, candle). Put that part
   in its own crate so editing the rest does not drag the heavy part along, and so binaries that do not need
   it do not compile it.
4. **An architectural rule must be enforced.** The domain must not depend on HTTP or SQL: make `domain` a
   crate without those dependencies and the compiler enforces the rule forever.
5. **Something is published separately** (a client SDK, a macro crate, a `-sys` crate) or has a different
   release cadence or semver promise than the rest.
6. **Several binaries share code.** `apps/server` and `apps/worker` both depend on `crates/core`.
7. **Different targets.** A `no_std` or wasm-compatible core, platform-specific backends.
8. **A build script or FFI.** `build.rs` reruns only rebuild the crate that owns it; native linking (`links`)
   belongs in a `-sys` crate.

Keep together when:

- the pieces call each other in both directions (you would need a cycle or a trait for every call);
- the "crate" would be 200 lines with one consumer: a module is cheaper;
- splitting forces you into orphan-rule workarounds everywhere (newtypes around every foreign type);
- hot inner loops would cross the boundary and you do not want to sprinkle `#[inline]` or require LTO;
- you only want to "organise" code: modules and `pub(crate)` do that without manifests.

A rough shape that works for most services: 3-10 crates. Workspaces with 50+ crates exist (rust-analyzer,
Bevy, Deno), but each crate there has a clear reason, and they invest in tooling to manage them.

## Layout patterns

### Flat `crates/*` (default)

```
myproj/
├── Cargo.toml          # [workspace] members = ["crates/*"]
├── Cargo.lock
└── crates/
    ├── myproj/         # facade / main library or binary
    ├── myproj-core/
    ├── myproj-macros/
    └── myproj-cli/
```

One glob covers every crate, the tree stays flat (no `crates/a/crates/b`), and finding a crate by name is
trivial. rust-analyzer popularised this layout and argues for it in "Large Rust Workspaces": a flat list scales
better than a hierarchy, because the hierarchy you choose today will be wrong tomorrow.

### `apps/` + `crates/` (or `libs/`)

```
platform/
├── Cargo.toml          # members = ["apps/*", "crates/*", "xtask"]
├── apps/
│   ├── api-server/     # bin, publish = false
│   ├── worker/         # bin, publish = false
│   └── admin-cli/      # bin, publish = false
├── crates/
│   ├── domain/
│   ├── storage/
│   ├── http-client/
│   └── test-support/   # publish = false, only in [dev-dependencies]
└── xtask/
```

Deployables are visible at a glance; libraries are reusable. Use `default-members = ["apps/api-server"]` if
`cargo run` at the root should run the main app.

### Root package + helper members

```
serde-like/
├── Cargo.toml          # [package] name = "serde-like" + [workspace] members = ["derive"]
├── src/lib.rs          # pub use serde_like_derive::*;  (behind a "derive" feature)
└── derive/
    ├── Cargo.toml      # name = "serde-like-derive", proc-macro = true
    └── src/lib.rs
```

Good for one library with a companion macro crate: the main crate is at the repository root, `cargo publish`
at the root publishes it, and the README sits next to its manifest.

### Separate workspaces under one repository

Use `exclude` (or simply a different directory outside `members`) plus a second `Cargo.toml` with its own
`[workspace]` when the part:

- needs a different toolchain (nightly-only `fuzz/` targets for cargo-fuzz, embedded firmware with `build-std`);
- needs incompatible dependency versions or features that would pollute unification;
- is an example meant to be copied by users as a standalone project.

```toml
[workspace]
members = ["crates/*"]
exclude = ["fuzz", "examples/standalone-app"]
```

`exclude` takes paths (prefixes), not globs.

## Virtual manifest vs root package

| | Virtual manifest (no `[package]`) | Root package |
|-|-----------------------------------|--------------|
| `cargo build` at root | builds `default-members`, else all members | builds the root package only (unless `default-members`) |
| Resolver | must be set explicitly (no edition to infer from) | inferred from the root package edition |
| Feels like | a monorepo of equals | one main crate with helpers |
| `src/` at root | none | the root crate's code |
| Typical | services, tool suites, large libraries split into many crates | a library with `-derive`/`-macros`/`-core` companions |

A virtual manifest cannot have `[dependencies]`, `[features]`, `[lib]`, `[[bin]]` or `[lints]` (use
`[workspace.lints]`): those belong to a package. `manifest_lint` flags them as CW019.

## Naming

- **Prefix every crate with the project** (`shop-domain`, `shop-infra`). crates.io is a single global
  namespace; a name like `core-utils` will clash or confuse. Internal-only crates benefit too: `use shop_domain::`
  reads unambiguously in code reviews.
- **Folder name = crate name.** `crates/shop-domain/Cargo.toml` contains `name = "shop-domain"`. It keeps the
  glob, `cargo -p shop-domain`, and the file tree in sync.
- **Hyphens in Cargo, underscores in Rust.** `shop-domain` is imported as `shop_domain`. Pick one style for
  crate names and stick to it (hyphens are the common convention).
- **Suffix conventions** readers recognise: `-macros` / `-derive` (proc-macro), `-sys` (raw FFI bindings and
  native linking), `-core` (no-IO core), `-cli` (binary), `-test-support` or `-testing` (fixtures),
  `xtask` (build automation).
- **Library and binary names** can be overridden (`[lib] name = "..."`, `[[bin]] name = "shop"`), which helps
  when the package name is long but the binary should be short.

## Layering and the dependency graph

A layered workspace has edges in one direction only. A common service shape (ports and adapters):

```
 layer 3  apps/shop-server  ── depends on ──► shop-infra, shop-app
 layer 2  shop-infra        ── depends on ──► shop-app, shop-domain    (sqlx, reqwest, tokio)
 layer 1  shop-app          ── depends on ──► shop-domain               (use cases, port traits)
 layer 0  shop-domain                                                   (types, rules; no IO)
```

Rules that keep it that way:

1. **Lower layers define traits, upper layers implement them.** `shop-app` defines `trait OrderRepo`;
   `shop-infra` implements it for Postgres; the binary wires them together. The domain never imports the
   database crate.
2. **Shared types sink.** When two crates both need `OrderId`, it moves down into the lowest crate that both
   depend on, not sideways into one of them.
3. **No cycles, not even through dev-dependencies if you can avoid it.** Cargo allows a dev-dependency cycle
   (`a` tests use `b`, `b` depends on `a`), but it compiles `a` twice (once as the library, once for the test)
   and types from the two copies do not match, which yields baffling "expected `a::Foo`, found `a::Foo`"
   errors. Put shared test fixtures in a `test-support` crate at the bottom instead.
4. **Binaries are leaves.** Nothing depends on an `apps/*` crate. If code in a binary is needed elsewhere, move
   it into a library crate.
5. **Fan-in at the bottom is fine; fan-out at the bottom is a smell.** A low-layer crate that depends on many
   crates will rebuild often and rebuild everything above it.

Print the graph with `/tmp/crate_graph .`; layer numbers are the longest path to a
crate with no internal dependencies. Crates in or above a cycle get no layer and the cycle is listed (CW011).
`cargo tree --workspace -e normal --depth 1` and `cargo depgraph` (third-party) show the same from Cargo's
point of view when a toolchain is available.

### Breaking a cycle

```rust
// Before: shop-core needs storage::save(), shop-storage needs core::Order -> cycle.

// After: core defines the port...
// crates/shop-core/src/lib.rs
pub struct Order { pub id: u64 }
pub trait OrderStore {
    fn save(&self, order: &Order) -> Result<(), StoreError>;
}
#[derive(Debug)]
pub struct StoreError;

// ...storage implements it (storage -> core, never core -> storage)
// crates/shop-storage/src/lib.rs
pub struct PgStore;
impl shop_core::OrderStore for PgStore {
    fn save(&self, _order: &shop_core::Order) -> Result<(), shop_core::StoreError> { Ok(()) }
}
```

## Proc-macro crates

- A proc-macro crate (`[lib] proc-macro = true`) runs inside the compiler and can only export procedural
  macros, so any runtime types, traits or helper functions the generated code refers to live in the "main"
  crate.
- Standard pairing: `foo` (runtime) re-exports `foo-macros`; generated code refers to `::foo::...` paths so
  users only depend on `foo`.

```toml
# crates/foo/Cargo.toml
[features]
derive = ["dep:foo-macros"]
[dependencies]
foo-macros = { workspace = true, optional = true }
```

```rust
// crates/foo/src/lib.rs
#[cfg(feature = "derive")]
pub use foo_macros::Builder;
```

- Proc-macros are compiled for the host. With resolver 2+, features enabled on their dependencies (syn,
  quote, proc-macro2) do not leak into the target build, and vice versa.
- `syn` with `features = ["full"]` is one of the slowest dependencies in many trees. Keep macro crates small,
  enable only the `syn` features needed (`derive`, `parsing`, `printing`, `clone-impls`, `proc-macro` are the defaults; `full`
  only if you parse arbitrary items or expressions), and avoid having many macro crates each pulling a
  different `syn` major.
- A proc-macro crate cannot be used by the crate that defines it; integration-test macros from a separate
  crate or from `tests/` of the macro crate (with `trybuild` for compile-fail tests).

## -sys crates, build.rs and links

- A `foo-sys` crate contains raw FFI declarations plus the `build.rs` that finds or builds the native library,
  and sets `links = "foo"` in `[package]`. Only one package in the whole dependency graph may declare a given
  `links` value, which is why two semver-incompatible versions of the same `-sys` crate cannot coexist.
- A safe wrapper `foo` depends on `foo-sys`. Users depend on `foo`.
- Keep build scripts in the smallest possible crate: any change that triggers a build script rerun rebuilds
  that crate and its dependents. Emit precise `cargo::rerun-if-changed=PATH` lines (the `cargo::` form needs
  Cargo 1.77; `cargo:rerun-if-changed` works everywhere). Without any `rerun-if` line the script reruns when
  any file in the package changes.
- Build-script dependencies go in `[build-dependencies]`. With resolver 2+ their features are resolved
  separately from normal dependencies.
- Code generation (protobuf, bindgen, sqlx offline data) can run either in `build.rs` (always fresh, slower
  builds, needs the generator on every machine) or in `cargo xtask codegen` with the generated files committed
  (fast builds, reviewable diffs, CI checks freshness). The second scales better in big workspaces.

## The xtask pattern

Build automation written in Rust, run with `cargo xtask <task>`, no make/just/npm required:

```
xtask/
├── Cargo.toml   # name = "xtask", publish = false
└── src/main.rs
```

```toml
# .cargo/config.toml
[alias]
xtask = "run --package xtask --"
```

```rust
// xtask/src/main.rs
use std::process::{Command, ExitCode};

fn main() -> ExitCode {
    let task = std::env::args().nth(1);
    let ok = match task.as_deref() {
        Some("ci") => run("cargo", &["clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"])
            && run("cargo", &["test", "--workspace", "--locked"]),
        Some("codegen") => run("cargo", &["run", "-p", "shop-codegen"]),
        _ => {
            eprintln!("usage: cargo xtask <ci|codegen>");
            false
        }
    };
    if ok { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

fn run(cmd: &str, args: &[&str]) -> bool {
    Command::new(cmd).args(args).status().is_ok_and(|s| s.success())
}
```

Guidelines: keep xtask dependencies light (it is compiled on first use), make it a member so it shares the lock
file and target directory, `publish = false`, and exclude it from `default-members` so `cargo build` does not
build it. Typical tasks: `codegen`, `dist` (build release artefacts), `ci` (the same steps CI runs), `bench`,
`install-hooks`, `release`.

## Tests, benches and examples

| Kind | Location | Notes |
|------|----------|-------|
| Unit tests | `#[cfg(test)] mod tests` inside `src/` | can test private items |
| Integration tests | `crates/foo/tests/*.rs` | each file is a separate crate and binary: compile + link time per file |
| Integration test suite (fast) | `crates/foo/tests/it/main.rs` + `mod` files | one binary for all tests; `[[test]] name = "it" path = "tests/it/main.rs"` (or rely on auto-discovery of `tests/it/main.rs`) |
| Cross-crate / end-to-end tests | dedicated `crates/e2e` or `tests` crate, `publish = false` | depends on several crates; keeps heavy test deps out of libraries |
| Shared fixtures | `crates/test-support`, used only in `[dev-dependencies]` | must not depend on crates that use it in their normal deps |
| Benchmarks | `crates/foo/benches/*.rs` with `[[bench]] name = "x" harness = false` for Criterion/Divan | `cargo bench -p foo` |
| Examples | `crates/foo/examples/*.rs` | built by `cargo test` and `--all-targets`; can use dev-dependencies |
| Doc tests | `///` code blocks | `cargo test --doc`; cargo-nextest does not run them |

Each `tests/*.rs` file links its own binary; 40 files in a crate that links tokio and sqlx can spend more time
linking than testing. Consolidating into one `tests/it/` binary is one of the cheapest build-time wins.

## Refactoring a monolith into a workspace

1. Turn the existing crate into a member: move it to `crates/<name>/` (or keep it as the root package first).
2. Add the virtual root manifest with `resolver`, `[workspace.package]`, `[workspace.dependencies]`; move
   profiles and `[patch]` to the root; keep the single `Cargo.lock` at the root.
3. Extract leaf modules first (types with no internal dependencies): they become `-core`/`domain`. Fix visibility
   (`pub(crate)` items used across the new boundary become `pub`, ideally behind a narrower API).
4. Re-export from the original crate (`pub use shop_domain::*;`) so downstream code keeps compiling while you
   migrate imports.
5. Move heavy-dependency modules into adapter crates; replace direct calls from lower layers with traits.
6. Run `/tmp/manifest_lint . --strict`, `/tmp/dep_audit . --strict` and `/tmp/crate_graph .` after each step; run
   `cargo build --timings` before and after to confirm the split helped.

## Anti-patterns

- **One crate per module ("crate soup").** 80 tiny crates that all depend on each other: no parallelism, more
  metadata, more manifests, endless version bumps.
- **`utils` / `common` dumping ground.** Everything depends on it and it depends on everything heavy, so every
  change rebuilds the world. Split by concern (`shop-ids`, `shop-time`) or push items to their users.
- **Binaries with logic.** `main.rs` of 3,000 lines that tests cannot reach. Keep `main` thin; move logic to a
  library crate.
- **Domain depends on infra** (`domain` uses `sqlx::FromRow` or `axum` types). The boundary exists on paper only.
- **Mixed editions and copy-pasted metadata** in every member instead of `[workspace.package]`.
- **Nested workspaces by accident** (a member with its own `[workspace]` table): Cargo errors about multiple
  workspace roots; remove the inner `[workspace]` or `exclude` the directory.
