# Workspace Manifest and Inheritance Reference

Every workspace-level key in `Cargo.toml`, how members inherit from the root, what is root-only, and what
belongs in `.cargo/config.toml` instead. Versions are the Rust/Cargo release where a feature became stable;
see [version-history.md](version-history.md) for the full timeline.

## Contents

- [The [workspace] table](#the-workspace-table)
- [Member discovery](#member-discovery)
- [resolver](#resolver)
- [[workspace.package]](#workspacepackage)
- [[workspace.dependencies]](#workspacedependencies)
- [[workspace.lints]](#workspacelints)
- [Root-only sections: profiles, patch, replace](#root-only-sections-profiles-patch-replace)
- [Profiles in depth](#profiles-in-depth)
- [[workspace.metadata]](#workspacemetadata)
- [.cargo/config.toml](#cargoconfigtoml)
- [Complete example](#complete-example)
- [Common errors](#common-errors)

## The [workspace] table

| Key | Meaning |
|-----|---------|
| `members` | list of paths or globs (`"crates/*"`) of member packages, relative to the root |
| `exclude` | paths (not globs) that are never members, even if a `members` glob matches them |
| `default-members` | members built by commands run at the root without `-p`/`--workspace`; must be members |
| `resolver` | `"1"`, `"2"` or `"3"`; see below |
| `package` | `[workspace.package]` values members can inherit |
| `dependencies` | `[workspace.dependencies]` entries members can inherit |
| `lints` | `[workspace.lints]` members can opt into |
| `metadata` | free-form table for external tools; ignored by Cargo |

A member can point at its root explicitly with `package.workspace = "../.."`, which is only needed when the
root is not an ancestor directory. Normally Cargo finds the root by walking up from the package directory to
the first `Cargo.toml` with a `[workspace]` table that lists (or implicitly includes) the package.

## Member discovery

Cargo's rules, which this skill's `workspace.rs` loader mirrors:

1. Expand every `members` entry (globs allowed) relative to the root directory.
2. Drop anything under an `exclude` path.
3. Add **path dependencies that live inside the workspace directory**: they become members automatically
   (implicit members), even if `members` does not list them.
4. A root `[package]`, if present, is a member.
5. A `Cargo.toml` inside the root directory that is none of the above and has no `[workspace]` of its own makes
   cargo fail when run in that directory with `current package believes it's in a workspace when it's not`
   (CW010). Fix: add it to `members` or `exclude`, or give it its own `[workspace]` table.

`default-members` controls what runs when you type `cargo build`, `cargo test` or `cargo run` at the root
without package selection. Use it to keep `cargo run` pointing at the main app and to keep xtask or slow
benchmark crates out of the default build. `--workspace` always means "every member".

## resolver

| Value | Default for | Behaviour |
|-------|-------------|-----------|
| `"1"` | edition 2015/2018 packages and **every virtual manifest without the key** | features of a dependency are unified across normal, dev, build and all target-specific uses |
| `"2"` | edition 2021 | build-deps/proc-macros, dev-deps (when not building tests/examples/benches) and other-platform deps no longer contribute features to the normal build |
| `"3"` | edition 2024 (Cargo 1.84+ for the key) | resolver 2 plus MSRV-aware version selection: `incompatible-rust-versions = "fallback"` by default |

- The resolver is a **workspace-wide** setting. In a workspace with a root package it comes from the root
  package's edition (or the explicit key). In a virtual manifest there is no edition, so the key is required;
  Cargo warns "virtual workspace defaulting to `resolver = "1"` despite one or more workspace members being on
  edition 2021 which implies `resolver = "2"`" (CW001).
- MSRV-aware resolution (resolver 3) prefers dependency versions whose `rust-version` is compatible with the
  `rust-version` declared by your workspace members, and falls back to newer versions when nothing compatible
  exists. It changes what `cargo update` / `cargo generate-lockfile` pick, not what an existing lockfile says.
  The same behaviour can be enabled per user or per repo with
  `[resolver] incompatible-rust-versions = "fallback"` in `.cargo/config.toml` (1.84+), or turned off with
  `"allow"`.
- Using `resolver = "3"` with a declared `rust-version` below 1.84 is a contradiction: older Cargo cannot parse
  the manifest (CW020).

## [workspace.package]

Members inherit with `key.workspace = true` (dotted key) or `key = { workspace = true }`.

| Inheritable key | Notes |
|-----------------|-------|
| `version` | lockstep versioning; crates with independent versions just set their own |
| `edition` | one edition for everyone; migrate crate by crate with `cargo fix --edition` if needed |
| `rust-version` | the MSRV; drives resolver 3 and the "requires rustc X" error message |
| `authors`, `description`, `documentation`, `homepage`, `repository` | `description` is usually per crate |
| `license`, `license-file` | `license-file` and `readme` paths are relative to the workspace root |
| `readme` | same path rule as `license-file` |
| `keywords`, `categories` | usually per crate |
| `publish` | e.g. `publish = false` workspace-wide, then `publish.workspace = true` only where wanted |
| `include`, `exclude` | packaging file lists |
| `badges` | rarely used |

Not inheritable: `name`, `build`, `links`, `default-run`, `autobins`/`autoexamples`/..., `[lib]`, `[[bin]]`,
`[features]`.

Rules:
- A member must opt in key by key; there is no "inherit everything" switch.
- Inheriting a key the workspace does not define is an error (CW015).
- Inherited and explicit values cannot be mixed for one key: a member either inherits `edition` or sets it.

```toml
# crates/shop-domain/Cargo.toml
[package]
name = "shop-domain"
description = "Domain types and rules"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true
repository.workspace = true
readme = "README.md"            # crate-local readme is fine; inherit only what is truly shared
```

## [workspace.dependencies]

Declare each dependency once, at the root:

```toml
[workspace.dependencies]
# crates.io
anyhow = "1"
serde = { version = "1.0.200", default-features = false }
tokio = { version = "1.38", default-features = false }
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls", "json"] }
# renamed
http1 = { package = "http", version = "1" }
# internal crates: path + version so dependents can be published
shop-domain = { path = "crates/shop-domain", version = "0.3.0" }
# git, pinned
tiny-fork = { git = "https://github.com/acme/tiny", rev = "4f2c1e9" }
```

Members reference it:

```toml
[dependencies]
anyhow.workspace = true
serde = { workspace = true, features = ["derive", "std"] }
tokio = { workspace = true, features = ["rt-multi-thread", "macros"] }
shop-domain.workspace = true
reqwest = { workspace = true, optional = true }

[dev-dependencies]
tokio = { workspace = true, features = ["test-util"] }

[build-dependencies]
prost-build.workspace = true
```

| A member may set | A member may not set |
|------------------|----------------------|
| `features` (added to the workspace list) | `version`, `path`, `git`, `branch`, `tag`, `rev`, `registry`, `package` |
| `optional = true` | a different source of any kind |
| `default-features = false`, only if the workspace entry already disables defaults | `default-features = false` when the workspace entry leaves defaults on (ignored with a warning; an error in edition 2024; CW016) |

Consequences:

- **Disable defaults at the root, add features in members.** Features only add up. If the root says
  `tokio = "1"` (defaults on), no member can turn defaults off.
- **Use it for internal crates too**: one `path + version` line; bumping the internal version is one edit.
- **Paths in `[workspace.dependencies]` are relative to the root**, not to the member.
- **Not every dependency must be shared**. Something used by exactly one crate can stay local; the audit only
  flags a dependency versioned in two or more members (CW003) or one that bypasses an existing workspace entry.
- Inheritance works in `[dependencies]`, `[dev-dependencies]`, `[build-dependencies]` and
  `[target.'cfg(...)'.dependencies]`.
- `cargo add serde -p shop-app` adds `serde.workspace = true` automatically when the workspace already defines
  `serde`.

## [workspace.lints]

Stable since 1.74. Declares lint levels once; members opt in with `[lints] workspace = true`.

```toml
[workspace.lints.rust]
unsafe_code = "forbid"
missing_debug_implementations = "warn"
unreachable_pub = "warn"
unexpected_cfgs = { level = "warn", check-cfg = ["cfg(tokio_unstable)", "cfg(coverage_nightly)"] }

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }        # lint groups first (lower priority)...
pedantic = { level = "warn", priority = -1 }
module_name_repetitions = "allow"              # ...then individual overrides win
unwrap_used = "warn"
dbg_macro = "warn"

[workspace.lints.rustdoc]
broken_intra_doc_links = "deny"
```

- Tools: `rust`, `clippy`, `rustdoc`. Levels: `allow`, `warn`, `force-warn`, `deny`, `forbid`.
- `priority` orders entries: lower numbers are applied first, so groups get `-1` and individual lints override
  them. Clippy's `lint_groups_priority` lint warns when a group and a member lint have the same priority.
- A member with `[lints] workspace = true` cannot add its own entries in the same `[lints]` table (Cargo
  rejects the combination). Crate-specific exceptions go in code: `#![allow(clippy::...)]` at the crate root.
- Lints do not apply to dependencies (Cargo caps lints of non-local crates).
- Forgetting the opt-in is silent (CW012).
- Prefer this over `RUSTFLAGS="-D warnings"` in `.cargo/config.toml`: rustflags change the build fingerprint
  for every crate (cache misses), while lint levels from manifests do not affect dependencies.
- In CI, deny warnings at the clippy invocation (`cargo clippy ... -- -D warnings`) instead of setting `deny` in
  the manifest, so a new toolchain's new warnings do not break local builds of downstream users.

## Root-only sections: profiles, patch, replace

| Section | In the root | In a member |
|---------|-------------|-------------|
| `[profile.*]` | applies to the whole workspace build | ignored: `warning: profiles for the non root package will be ignored, specify profiles at the workspace root` |
| `[patch.crates-io]`, `[patch.'https://...']` | overrides a dependency for the whole graph | ignored with a warning |
| `[replace]` | deprecated predecessor of `[patch]` | ignored with a warning |

Per-crate profile settings are written in the root:

```toml
[profile.release.package.shop-codec]
opt-level = 3
[profile.dev.package.sqlx-macros]
opt-level = 3            # proc-macro that runs at compile time: fast macro = fast build
```

`[patch]` usage:

```toml
[patch.crates-io]
# temporary fork until https://github.com/foo/bar/pull/123 is released
bar = { git = "https://github.com/acme/bar", rev = "9c1d2e4" }
# local checkout while developing two repos together (do not commit)
# baz = { path = "../baz" }
```

A `[patch]` entry only takes effect if the patched version satisfies the requirement in the graph; Cargo warns
"Patch `bar v0.4.0` was not used in the crate graph" otherwise.

## Profiles in depth

Built-in profiles: `dev` (`cargo build`), `release` (`--release`), `test` (inherits `dev`), `bench` (inherits
`release`). Custom profiles (1.57) use `inherits`.

| Key | dev default | release default | Notes |
|-----|-------------|-----------------|-------|
| `opt-level` | `0` | `3` | `1`/`2` for dev deps; `"s"`/`"z"` for size |
| `debug` | `true` (full) | `false` | `"line-tables-only"` (1.71) keeps backtraces with far less debuginfo |
| `strip` | `"none"` | `"none"`, but `"debuginfo"` is applied when release has no debuginfo (1.77) | `"symbols"` for smallest binaries |
| `lto` | `false` | `false` (thin-local) | `"thin"` most of the benefit, `"fat"`/`true` max, `"off"` none |
| `codegen-units` | `256` | `16` | `1` = best code, slowest build |
| `incremental` | `true` | `false` | CI often sets `CARGO_INCREMENTAL=0` |
| `panic` | `"unwind"` | `"unwind"` | `"abort"`: smaller, but no `catch_unwind`; tests always unwind |
| `overflow-checks` | `true` | `false` | can be enabled in release for safety |
| `debug-assertions` | `true` | `false` | |
| `split-debuginfo` | platform default | | `"unpacked"` speeds macOS/Linux dev links |

Recommended baseline:

```toml
[profile.dev]
debug = "line-tables-only"       # faster builds and links; full debug only when stepping in a debugger

[profile.dev.package."*"]
opt-level = 2                    # dependencies optimised once and cached; own code stays debuggable

[profile.dev.build-override]
opt-level = 3                    # build scripts and proc-macros run faster

[profile.release]
lto = "thin"
codegen-units = 1
strip = "symbols"

[profile.dist]                   # cargo build --profile dist
inherits = "release"
lto = "fat"
panic = "abort"

[profile.profiling]              # for perf/samply/flamegraph
inherits = "release"
debug = "line-tables-only"
strip = "none"
```

`[profile.dev.package."*"]` matches all non-member packages (dependencies), so your own crates keep
`opt-level = 0`. Package overrides cannot set `lto`, `panic` or `rpath` (those apply to the final artefact).

## [workspace.metadata]

Ignored by Cargo, read by tools: `[workspace.metadata.release]` (cargo-release), `[workspace.metadata.dist]`
(cargo-dist), `[workspace.metadata.docs.rs]`-style settings at package level (`[package.metadata.docs.rs]`),
`[package.metadata.cargo-machete] ignored = ["..."]` for false positives. Keep tool configuration here or in
the tool's own file rather than in ad-hoc scripts.

## .cargo/config.toml

Configuration for *how cargo runs* on this machine/repository, not for *what a package is*. Cargo merges
`.cargo/config.toml` files from the current directory upward plus `$CARGO_HOME/config.toml`. Config is not
read for dependencies and never reaches users of published crates.

```toml
# .cargo/config.toml at the workspace root
[alias]
xtask = "run --package xtask --"
ck = "check --workspace --all-targets"
lint = "clippy --workspace --all-targets -- -D warnings"

[build]
# target-dir = "target"          # shared by all members already; set only to move it (e.g. a fast disk)

[env]
SQLX_OFFLINE = "true"            # environment for build scripts and rustc invocations

[resolver]
incompatible-rust-versions = "fallback"   # MSRV-aware resolution without resolver 3 (Cargo 1.84+)

[net]
git-fetch-with-cli = true        # use the system git (SSH agents, credential helpers)

# Faster linking on Linux (needs clang + mold installed on every machine that builds)
# [target.x86_64-unknown-linux-gnu]
# linker = "clang"
# rustflags = ["-C", "link-arg=-fuse-ld=mold"]
```

Cautions about `rustflags`:

- Precedence: `CARGO_ENCODED_RUSTFLAGS`, then `RUSTFLAGS`, then `target.<triple>.rustflags` /
  `target.<cfg>.rustflags`, then `build.rustflags`. They are **not merged**: a developer's `RUSTFLAGS` silently
  replaces the repository's `build.rustflags`.
- Changing rustflags changes every crate's fingerprint: a full rebuild, and separate cache entries in CI.
- `-C target-cpu=native` makes binaries that crash with illegal-instruction on older CPUs; never put it in a
  shared config for artefacts you ship.
- Lint levels belong in `[workspace.lints]`, not `-D warnings` in rustflags.
- Prefer committing only portable settings; machine-specific ones (linker choice, `target-dir` on a RAM disk)
  go in `$CARGO_HOME/config.toml` or an untracked file.

## Complete example

```toml
[workspace]
members = ["crates/*", "apps/*", "xtask"]
default-members = ["apps/shop-server"]
exclude = ["fuzz"]
resolver = "3"

[workspace.package]
version = "0.3.0"
edition = "2024"
rust-version = "1.85"
license = "MIT OR Apache-2.0"
repository = "https://github.com/acme/shop"

[workspace.dependencies]
shop-domain = { path = "crates/shop-domain", version = "0.3.0" }
shop-app = { path = "crates/shop-app", version = "0.3.0" }
shop-infra = { path = "crates/shop-infra", version = "0.3.0" }
anyhow = "1"
serde = { version = "1.0.200", default-features = false }
thiserror = "2"
tokio = { version = "1.38", default-features = false }
tracing = "0.1"

[workspace.lints.rust]
unsafe_code = "forbid"
[workspace.lints.clippy]
all = { level = "warn", priority = -1 }

[profile.dev.package."*"]
opt-level = 2
[profile.release]
lto = "thin"
codegen-units = 1
strip = "symbols"
```

## Common errors

| Message (abridged) | Cause | Fix |
|--------------------|-------|-----|
| `failed to load manifest for workspace member` | `members` points at a directory without `Cargo.toml` | fix the path/glob, remove empty dirs |
| `current package believes it's in a workspace when it's not` | crate under the root not in `members`/`exclude` | add to one of them |
| `package ... is a member of the wrong workspace` / `multiple workspace roots found` | nested `[workspace]` tables | remove the inner `[workspace]` or `exclude` it |
| `this virtual manifest specifies a [dependencies] section, which is not allowed` | package section in a virtual manifest | `[workspace.dependencies]` |
| `error inheriting X from workspace root manifest's workspace.dependencies.X` | inherited dep not declared at the root | add it to `[workspace.dependencies]` |
| `default-features is ignored for X, since default-features was not specified for workspace.dependencies.X` | member tries to disable defaults the workspace enables | `default-features = false` at the root |
| `profiles for the non root package will be ignored` | profile in a member | move it to the root |
| `feature X is required` / `feature edition2024 is required` | toolchain older than the manifest needs | update the toolchain or lower the manifest features; align `rust-version` |
