# Cargo Workspace Features by Rust Version

Which Rust/Cargo release stabilised each manifest and workspace feature this skill relies on. Cargo ships with
Rust, so "1.64" means "Cargo shipped with Rust 1.64". Use this to choose an MSRV, or to explain why an old
toolchain cannot parse a manifest. The `manifest_lint` script's rule CW020 checks the most common mismatches.

## Contents

- [Quick matrix](#quick-matrix)
- [Timeline](#timeline)
- [Edition 2021 Cargo changes](#edition-2021-cargo-changes)
- [Edition 2024 Cargo changes](#edition-2024-cargo-changes)
- [Lock file versions](#lock-file-versions)
- [Choosing an MSRV for manifest features](#choosing-an-msrv-for-manifest-features)
- [Migrating an older workspace](#migrating-an-older-workspace)

## Quick matrix

| Feature | Stable in | Manifest/command | Notes |
|---------|-----------|------------------|-------|
| Workspaces | 1.12 | `[workspace] members = [...]` | glob members, `exclude` |
| Renamed dependencies | 1.31 | `http1 = { package = "http", version = "1" }` | |
| Alternate registries | 1.34 | `registry = "acme"`, `publish = ["acme"]` | |
| `cargo vendor` | 1.37 | built in | |
| Profile overrides | 1.41 | `[profile.dev.package."*"]`, `build-override` | |
| `cargo tree` | 1.44 | built in | `-d`, `-i`, `-e features` |
| Feature resolver 2 | 1.51 | `resolver = "2"` | default for edition 2021 packages |
| `split-debuginfo` profile key | 1.51 | `split-debuginfo = "unpacked"` | |
| Edition 2021 | 1.56 | `edition = "2021"` | implies resolver 2 |
| `rust-version` (MSRV) | 1.56 | `rust-version = "1.70"` | older Cargo ignores the key with a warning |
| `[env]` in config | 1.56 | `.cargo/config.toml` | |
| Custom named profiles | 1.57 | `[profile.dist] inherits = "release"` | `--profile dist` |
| `strip` profile key | 1.59 | `strip = "symbols"` | |
| Namespaced features | 1.60 | `"dep:serde"` | no implicit feature for that dep |
| Weak dependency features | 1.60 | `"serde?/std"` | |
| `cargo build --timings` | 1.60 | HTML report in `target/cargo-timings/` | |
| `cargo add` | 1.62 | built in | uses `workspace = true` when the root defines the dep |
| Workspace inheritance | 1.64 | `[workspace.package]`, `[workspace.dependencies]`, `x.workspace = true` | |
| `cargo remove` | 1.66 | built in | |
| Sparse registry protocol | 1.68 | `sparse+https://` | default for crates.io since 1.70 |
| `debug = "line-tables-only"` | 1.71 | profile key | |
| `[lints]` / `[workspace.lints]` | 1.74 | `[lints] workspace = true` | |
| `--keep-going` | 1.74 | `cargo build --keep-going` | |
| Credential providers | 1.74 | `[registry] global-credential-providers` | |
| `package.version` optional | 1.75 | omit `version` | defaults to 0.0.0, cannot be published |
| `cargo::` build-script directives | 1.77 | `cargo::rerun-if-changed=...` | `cargo:` single colon still works |
| Release `strip = "debuginfo"` by default | 1.77 | when the profile has no debuginfo | smaller release binaries |
| Lock file v4 readable | 1.78 | `Cargo.lock` `version = 4` | |
| `unexpected_cfgs` checking on by default | 1.80 | `[lints.rust] unexpected_cfgs = { level = "warn", check-cfg = [...] }` | catches `#[cfg(feature = "typo")]` |
| `cargo info` | 1.82 | built in | |
| Lock file v4 by default | 1.83 | new lock files | older Cargo cannot read them |
| MSRV-aware resolver | 1.84 | `resolver = "3"`, `[resolver] incompatible-rust-versions` | |
| Edition 2024 | 1.85 | `edition = "2024"` | implies resolver 3 |
| Multi-package publishing | 1.90 | `cargo publish --workspace` / several `-p` | ordered by dependencies |
| `rust-lld` default linker on x86_64 Linux | 1.90 | `x86_64-unknown-linux-gnu` | faster links |

## Timeline

### 1.12 - 1.44: the foundations

- **1.12**: `[workspace]` with a shared `Cargo.lock` and `target/` directory; members by path.
- **1.31**: Rust 2018 edition; dependency renaming via `package = "..."`.
- **1.34**: alternate registries.
- **1.37**: `cargo vendor` for offline/vendored builds.
- **1.41**: profile overrides: `[profile.dev.package.<name>]`, `[profile.dev.package."*"]` for all
  dependencies, and `[profile.dev.build-override]` for build scripts and proc-macros.
- **1.44**: `cargo tree` built in (previously the cargo-tree plugin).

### 1.51 - 1.60: features grow up

- **1.51**: feature resolver 2 (`resolver = "2"`): build-dependency, dev-dependency and target-specific
  features stop leaking into normal builds. Opt-in until edition 2021.
- **1.56**: edition 2021 (resolver 2 by default for packages, but *not* for virtual manifests, which have no
  edition); `rust-version` key; `[env]` in config.
- **1.57**: custom profiles with `inherits`.
- **1.59**: `strip` in profiles.
- **1.60**: `dep:` namespaced features and `?/` weak dependency features; `--timings` stable.

### 1.62 - 1.75: workspace ergonomics

- **1.62 / 1.66**: `cargo add` / `cargo remove`.
- **1.64**: workspace inheritance: `[workspace.package]` and `[workspace.dependencies]`; members use
  `key.workspace = true`. Manifests using it fail to parse on older Cargo.
- **1.68 / 1.70**: sparse registry protocol; default for crates.io in 1.70 (much faster index updates in CI).
- **1.71**: `debug = "line-tables-only"`.
- **1.74**: `[lints]` and `[workspace.lints]`; `--keep-going`; credential providers for registries.
- **1.75**: `package.version` may be omitted (defaults to `0.0.0`, not publishable).

### 1.77 - 1.90: MSRV awareness and edition 2024

- **1.77**: `cargo::KEY=VALUE` build-script directive syntax; release profiles strip debuginfo by default when
  they have no debuginfo of their own.
- **1.78**: Cargo can read lock file version 4.
- **1.80**: `--check-cfg` is on by default; unknown `cfg` names/values (including feature names) warn via
  `unexpected_cfgs`; expected custom cfgs are declared in `[lints.rust] unexpected_cfgs`.
- **1.82**: `cargo info <crate>` shows crate metadata from the registry.
- **1.83**: new lock files use version 4.
- **1.84**: MSRV-aware resolver: `resolver = "3"` in the manifest, or `incompatible-rust-versions = "fallback"`
  under `[resolver]` in `.cargo/config.toml`. Version selection prefers dependencies whose `rust-version` is
  compatible with your packages' `rust-version`.
- **1.85**: Rust 2024 edition (see below).
- **1.90**: `cargo publish` can publish multiple packages in one invocation (`--workspace`), handling the order;
  `rust-lld` becomes the default linker on `x86_64-unknown-linux-gnu`.

## Edition 2021 Cargo changes

- Default `resolver = "2"` for packages on edition 2021.
- Virtual manifests are unaffected: they still need `resolver = "2"` explicitly; Cargo warns when members are on
  2021 but the virtual workspace defaults to resolver 1.

## Edition 2024 Cargo changes

Edition 2024 (Rust 1.85) changes three Cargo behaviours for packages that opt in:

1. **Rust-version aware resolver**: edition 2024 implies `resolver = "3"`. Virtual manifests still need the key
   (`resolver = "3"`).
2. **Table and key name consistency**: the underscore aliases are rejected: `dev_dependencies`,
   `build_dependencies`, `default_features`, `crate_type`, `proc_macro` and friends, as is `[project]`
   instead of `[package]` (CW017). Use the hyphenated forms.
3. **Unused inherited `default-features` rejected**: `{ workspace = true, default-features = false }` is an error
   when the workspace entry does not itself disable default features (CW016). Before 2024 it was a warning and
   was ignored.

Migration: `cargo fix --edition` per crate (it handles code; review manifests by hand), then set
`edition = "2024"` in `[workspace.package]`. Edition is per crate, so a workspace can migrate crate by crate,
but CW005 flags the mixed state so it does not become permanent.

## Lock file versions

| Lock version | Written by default | Readable by |
|--------------|--------------------|-------------|
| 3 | Cargo before 1.83 | every Cargo an MSRV job is likely to use |
| 4 | Cargo 1.83+ | Cargo 1.78+ |

Cargo keeps the version of an existing lock file unless it has to change it. An MSRV CI job on a toolchain older
than 1.78 cannot read a v4 lock file; either keep the file at version 3 or regenerate it with the MSRV
toolchain.

## Choosing an MSRV for manifest features

The manifest itself sets a floor below which your declared MSRV is meaningless:

| You use | Minimum `rust-version` |
|---------|------------------------|
| `edition = "2024"` | 1.85 |
| `resolver = "3"` | 1.84 |
| `[lints]` / `[workspace.lints]` | 1.74 |
| `x.workspace = true` (any inheritance) | 1.64 |
| `dep:` or `?/` in `[features]` | 1.60 |
| `edition = "2021"` | 1.56 |
| `resolver = "2"` | 1.51 |

Dependencies set their own floors: if `tokio` requires 1.70, your MSRV is at least 1.70 regardless of your
manifest. With resolver 3, `cargo update` picks dependency versions that respect your `rust-version` where
possible; `cargo msrv find` or `cargo hack check --rust-version` confirms the real value.

## Pinning the toolchain

A `rust-toolchain.toml` at the workspace root makes rustup use the same toolchain for every developer and CI
job that runs cargo in the repository:

```toml
[toolchain]
channel = "1.85.0"              # or "stable", or a dated nightly such as "nightly-2025-06-01"
components = ["clippy", "rustfmt"]
profile = "minimal"
```

- Pinning the *development* toolchain (for reproducible clippy and rustfmt output) is independent of the
  *MSRV*: develop on a recent stable, test the MSRV in a separate CI job with `cargo +1.xx` or
  `cargo hack check --rust-version`.
- Bump the pinned toolchain in its own PR; new clippy lints appear with new toolchains.
- `rustc --version` and `cargo --version` print what is actually used; `rustup show` explains why (override,
  toolchain file, default).

## Migrating an older workspace

1. Add `resolver = "2"` (or `"3"` if MSRV >= 1.84) to a virtual manifest; check that nothing relied on resolver
   1 feature leaking (build with `--workspace` and with each `-p`).
2. Introduce `[workspace.package]` and `[workspace.dependencies]` (needs 1.64); move versions there one dependency
   at a time; members switch to `.workspace = true`.
3. Add `[workspace.lints]` (1.74) and `[lints] workspace = true` in every member; move `#![deny(...)]` crate
   attributes and `RUSTFLAGS` lint flags into it.
4. Declare `rust-version` and add an MSRV CI job.
5. Move to edition 2024 when MSRV allows 1.85: `cargo fix --edition`, fix manifests (underscore keys,
   inherited `default-features`), set the edition at the root.
6. Run `/tmp/manifest_lint . --strict` and `/tmp/dep_audit . --strict` after each step.
