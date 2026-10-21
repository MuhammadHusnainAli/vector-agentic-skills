---
name: rust-cargo-workspace-designer
description: "Design, review and fix Cargo workspaces: when to split a crate (compile time, boundaries, publishing, proc-macros), crates/* vs apps/ + crates/ layouts, virtual manifest vs root package, members/exclude/default-members, resolver 2 vs 3 (MSRV-aware, edition 2024), [workspace.package] and [workspace.dependencies] inheritance, [workspace.lints], root-only profiles (lto, codegen-units), additive features with dep: and weak ?/ syntax, feature unification pitfalls, internal path + version deps, publish = false, Cargo.lock and MSRV policy, xtask, CI with --locked, nextest, rust-cache, sccache, cargo-hack/deny/machete/udeps/semver-checks, and cargo build --timings. Ships a workspace auditor and crate-graph tool. Use when the user creates or restructures a Rust monorepo, asks how to organise crates, sees 'profiles for the non root package will be ignored', 'cyclic package dependency', 'believes it's in a workspace when it's not', resolver warnings, duplicate dependency versions, slow builds or failed publishes."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Cargo Workspace Designer

Design a Cargo workspace that builds fast, layers cleanly and publishes without surprises: decide where crate
boundaries pay for themselves, pick a layout, put every shared setting in the root manifest exactly once
(package metadata, dependency versions, lints, profiles), keep features additive, and make CI prove it with
`--locked`. Review existing workspaces the same way: three small std-only Rust programs in `scripts/` read
every manifest (they never run cargo), flag 20 mechanical mistakes and print the internal dependency graph by
layer.

## Trigger Conditions

Activate this skill when the user:
- Starts a multi-crate Rust project, converts a single crate into a workspace, or asks "how should I split
  this into crates?", "monorepo layout", "virtual manifest or root package?"
- Edits a root `Cargo.toml` with `[workspace]`, `[workspace.package]`, `[workspace.dependencies]`,
  `[workspace.lints]`, `resolver`, `members`, `exclude`, `default-members`, or `[profile.*]`
- Sees `warning: profiles for the non root package will be ignored`, `virtual workspace defaulting to
  resolver = "1"`, `cyclic package dependency`, `current package believes it's in a workspace when it's not`,
  `default-features is ignored for ...`, or `cargo publish` failing on a path dependency without a version
- Has the same dependency at different versions across crates, two copies of a crate in `cargo tree -d`,
  features that work with `cargo build --workspace` but not with `cargo build -p one-crate`
- Wants faster builds (`cargo build --timings`), CI for a workspace, an MSRV policy, a Cargo.lock policy,
  an `xtask` crate, proc-macro crate placement, or a release/publishing flow for several crates

## Workflow

```
0. BUILD     -> once: for t in crate_graph manifest_lint dep_audit; do
                  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
1. INVENTORY -> /tmp/crate_graph .                  (crates, layers, internal edges, cycles, membership)
                cargo tree --workspace -e normal -d (duplicates), cargo build --timings (if a toolchain exists)
2. AUDIT     -> /tmp/manifest_lint . --strict; /tmp/dep_audit . --strict   (file:line + fix)
3. BOUNDARIES-> decide split/merge with the table below; target layering domain <- app <- infra <- bin
4. ROOT      -> one virtual manifest: resolver, [workspace.package], [workspace.dependencies],
                [workspace.lints], profiles; members inherit with `x.workspace = true`
5. FEATURES  -> additive only, defaults off at the root, dep:/?/ syntax; test each crate alone (cargo hack)
6. CI        -> fmt, clippy, nextest + doctests with --workspace --all-targets --locked; MSRV job;
                cargo deny; semver-checks for published crates
7. VERIFY    -> all three scripts with --strict exit 0; the graph has no cycles
```

## When to Split a Crate

| Reason to split | Why it pays | Reason NOT to split |
|-----------------|-------------|---------------------|
| Compile time: a big crate where every edit recompiles everything | crates compile in parallel; an edit only rebuilds the crate and its dependents | the "split" crates all depend on each other (no parallelism, more link/metadata work) |
| Isolate heavy dependencies (DB drivers, gRPC, GUI, ML) | crates that do not need them stop rebuilding when they change | the dependency is needed everywhere anyway |
| Proc-macros | **mandatory**: `proc-macro = true` crates can only export macros | - |
| Enforce an architectural boundary (domain must not see HTTP/SQL) | the compiler enforces it; `pub(crate)` stays private | a single module with `pub(crate)` enforces it well enough |
| Publish part of the code (SDK, client, macros) | independent semver, smaller download | internal-only code with no second consumer |
| Several binaries share code | `apps/*` binaries over shared `crates/*` | one binary: modules are enough |
| Isolate a `build.rs` / `links` / FFI `-sys` crate | build script reruns only rebuild that crate | - |
| Different platforms or `no_std` core | the core builds for embedded/wasm without std deps | - |

Costs of splitting: more manifests, orphan-rule friction (`impl ForeignTrait for ForeignType` is forbidden, so
trait impls must live next to the type or the trait), non-generic functions are not inlined across crates
without `#[inline]` or LTO, and every boundary is a public API you have to maintain. Start with modules; promote
a module to a crate when one of the reasons above is real. Detail: [crate-boundaries-and-layouts.md](references/crate-boundaries-and-layouts.md).

## Layouts

| Layout | Use when | Shape |
|--------|----------|-------|
| Flat `crates/*` virtual manifest | libraries + a few bins, the default for most projects | `Cargo.toml` (no `[package]`), `crates/<name>/` |
| `apps/` + `crates/` (or `libs/`) | several deployables share libraries | `apps/server`, `apps/cli`, `crates/domain`, `crates/infra` |
| Root package + members | one main crate with helpers (`foo`, `foo-macros`, `foo-derive`) | `[package]` and `[workspace]` in root `Cargo.toml` |
| Separate workspaces / `exclude` | fuzz targets, examples with conflicting deps, embedded firmware | `exclude = ["fuzz"]`, own `Cargo.toml` + lockfile |

```
shop/
├── Cargo.toml            # virtual manifest: [workspace] only, resolver, shared tables, profiles
├── Cargo.lock            # committed, one for the whole workspace
├── .cargo/config.toml    # aliases (xtask), no global rustflags
├── apps/shop-server/     # bin, publish = false
├── crates/shop-domain/   # pure types + rules, no IO          (layer 0-1)
├── crates/shop-macros/   # proc-macro = true                 (layer 0)
├── crates/shop-app/      # use cases, port traits            (layer 2)
├── crates/shop-infra/    # adapters: sqlx, reqwest, tokio     (layer 3)
└── xtask/                # cargo xtask codegen|dist|ci, publish = false
```

Name folders exactly like the crates (`crates/shop-domain` holds `name = "shop-domain"`) and prefix every
crate with the project name: crates.io has one global namespace and `use shop_domain::Order` reads clearly.

## Root Manifest

```toml
[workspace]
members = ["crates/*", "apps/*", "xtask"]
default-members = ["apps/shop-server"]      # what plain `cargo build` / `cargo run` at the root builds
exclude = ["fuzz"]
resolver = "3"                              # required in a virtual manifest; "2" if MSRV < 1.84

[workspace.package]
version = "0.3.0"
edition = "2024"
rust-version = "1.85"
license = "MIT OR Apache-2.0"
repository = "https://github.com/acme/shop"

[workspace.dependencies]
shop-domain = { path = "crates/shop-domain", version = "0.3.0" }   # path + version: publishable
serde = { version = "1.0.200", default-features = false }           # defaults off; members opt in
tokio = { version = "1.38", default-features = false }
thiserror = "2"

[workspace.lints.rust]
unsafe_code = "forbid"
[workspace.lints.clippy]
all = { level = "warn", priority = -1 }     # groups need a lower priority than single lints
unwrap_used = "warn"

[profile.release]
lto = "thin"
codegen-units = 1
[profile.dev.package."*"]
opt-level = 2                               # fast dependencies, debuggable own code
```

## Member Manifest

```toml
[package]
name = "shop-infra"
description = "Database and HTTP adapters for shop-app"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true
repository.workspace = true

[dependencies]
shop-domain = { workspace = true, features = ["serde"] }   # features are ADDED to the workspace entry
tokio = { workspace = true, features = ["rt-multi-thread", "fs"] }

[lints]
workspace = true
```

A member may add `features`, `optional = true` (and `default-features = false` only if the workspace entry
also disables defaults); it can never change the version, path or source. Full key reference:
[manifest-and-inheritance.md](references/manifest-and-inheritance.md).

## Core Rules

1. **Virtual manifest with an explicit `resolver`.** A virtual manifest has no edition, so without
   `resolver` it silently uses resolver 1. Use `"3"` for edition 2024 / MSRV >= 1.84, else `"2"`.
2. **Root-only sections live in the root.** `[profile.*]`, `[patch]`, `[replace]` in a member are ignored.
3. **One version per dependency.** Every external dependency used by two or more crates goes into
   `[workspace.dependencies]`; members write `dep.workspace = true`.
4. **Inherit metadata and lints.** `edition`, `rust-version`, `license`, `repository`, `version` via
   `.workspace = true`; every member has `[lints] workspace = true`.
5. **Layers point one way.** domain <- app <- infra <- bin; no cycles; shared types sink to the lowest crate;
   upper layers depend on traits defined below (ports), not the other way round.
6. **Internal deps carry path AND version** if anything that depends on them is published; everything else is
   `publish = false` (apps, xtask, test-support, benchmarks).
7. **Features are additive.** Defaults off at the root, `std` as an opt-out-able default, `dep:` for optional
   deps, `pkg?/feat` for weak features, no mutually exclusive features. Test each crate alone.
8. **Commit Cargo.lock** (binaries and libraries alike, per the 2023 Cargo guidance) and build CI with
   `--locked`; declare `rust-version` and test it in CI.
9. **No global `rustflags` in `.cargo/config.toml`** for things that change codegen of every crate unless you
   mean it: they invalidate caches, do not reach users of published crates, and are overridden by `RUSTFLAGS`.
10. **Measure before restructuring for speed.** `cargo build --timings` shows the critical path; split the crate
    on it, not the crates that are already parallel.

## Features and Unification

Cargo builds **one** copy of each dependency per build with the **union** of features requested by every
package selected for that build. `cargo build --workspace` and `cargo build -p shop-app` can therefore compile
`tokio` with different features: one passes, the other fails ("works in CI, fails when built alone"), and
switching between them rebuilds. Resolver 2+ keeps build-dependency/proc-macro features, dev-dependency
features (unless tests/examples are built) and other-platform dependencies out of the union.

```toml
[features]
default = ["std"]
std = ["serde?/std"]          # weak: enables serde/std only if serde is already on
serde = ["dep:serde"]         # namespaced: no implicit "serde" feature is created
[dependencies]
serde = { workspace = true, optional = true, features = ["derive"] }
```

Check every crate with its own features: `cargo hack check --workspace --each-feature --no-dev-deps`.
Pitfalls, `cargo tree -e features -i`, workspace-hack crates: [features-and-unification.md](references/features-and-unification.md).

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| `profiles for the non root package will be ignored` | `[profile]` in a member (CW002) | move to root Cargo.toml |
| `virtual workspace defaulting to resolver = "1"` | no `resolver` in virtual manifest (CW001) | `resolver = "2"` / `"3"` |
| `cyclic package dependency` | two crates depend on each other (CW011) | move shared items down a layer; invert with a trait |
| `current package believes it's in a workspace when it's not` | crate under the root not in `members` (CW010) | add to `members` or `exclude` |
| `failed to load manifest for workspace member` | stale member path / glob (CW009) | fix `members`, delete the empty dir |
| `cargo publish`: dependency does not specify a version | path dep without `version` (CW007) | `{ path = "...", version = "x.y" }` or `publish = false` |
| `default-features is ignored for serde` | member disables defaults the workspace enables (CW016) | `default-features = false` at the root |
| Same crate twice in `cargo tree -d` | members pin incompatible majors (CW003) | `[workspace.dependencies]`; `cargo update -p` |
| Builds alone fail, `--workspace` passes | feature unification hides a missing feature | declare the feature in that crate; `cargo hack --each-feature` |
| Everything rebuilds when switching `-p` / IDE vs CLI | different feature sets or `RUSTFLAGS` per invocation | unify features (workspace-hack), same flags, separate `target-dir` for the IDE |
| One edit rebuilds the whole tree | edited crate is at the bottom of the graph or one giant crate | split the hot crate, move volatile code up the graph |
| `lto`, `opt-level` in member have no effect | profile in member (CW002) | root profile, `[profile.release.package.foo]` for per-crate overrides |
| Old toolchain: `feature edition2024 is required` | MSRV lower than manifest needs (CW020) | raise `rust-version` or drop the feature |
| CI passes locally, fails with `--locked` | Cargo.lock not committed / out of date | commit it; `cargo update` deliberately in a PR |

## Version Notes

| Rust | Cargo change that matters for workspaces |
|------|------------------------------------------|
| 1.51 | `resolver = "2"` |
| 1.56 | edition 2021 (implies resolver 2), `rust-version` |
| 1.60 | `dep:` namespaced and `?/` weak features; `cargo build --timings` |
| 1.64 | workspace inheritance: `[workspace.package]`, `[workspace.dependencies]` |
| 1.74 | `[lints]` / `[workspace.lints]` |
| 1.84 | `resolver = "3"`: MSRV-aware dependency resolution (`incompatible-rust-versions = "fallback"`) |
| 1.85 | edition 2024 (implies resolver 3; underscore keys and `[project]` rejected) |

Full history: [version-history.md](references/version-history.md).

## Output Format

When designing or reviewing a workspace, answer with:
1. **Graph** - crates by layer (from `crate_graph`), proposed moves/splits/merges and why.
2. **Findings** - rule id, file:line, what breaks and when (now, on publish, on a fresh lockfile).
3. **Manifests** - complete root `Cargo.toml` and one representative member, not fragments.
4. **Features** - per crate: defaults, optional deps, what each feature enables; unification risks.
5. **CI and policy** - the commands (`--workspace --all-targets --locked`), MSRV, Cargo.lock, release flow.
6. **Verification** - the three scripts exit 0 with `--strict`, plus the cargo commands to run.

## Scripts

Small, standard-library-only Rust programs: they read TOML and never run cargo. Build each once with
`rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>`. Input is a workspace directory, any Cargo.toml in
it (the whole workspace is checked), or `-` for one manifest on stdin (no file-system checks).

| Script | Rules | Job |
|--------|-------|-----|
| `scripts/crate_graph.rs` | CW009-CW011, CW018 | crates by layer, internal edges (`--dot`, `--json`), cycles, missing/stray/invalid default members |
| `scripts/manifest_lint.rs` | CW001, CW002, CW004-CW006, CW008, CW012, CW017, CW019, CW020 | manifest contents: resolver, root-only sections, inheritance, edition, MSRV, publishability, lints, deprecated keys |
| `scripts/dep_audit.rs` | CW003, CW007, CW013-CW016 | dependency declarations: duplicates, unversioned path/git deps, `*`, unpinned git, undefined inheritance, ignored default-features |
| `scripts/toml.rs`, `scripts/workspace.rs`, `scripts/cli.rs` | - | shared modules: TOML reader with line numbers, Cargo-style member discovery, options and report |

```bash
/tmp/crate_graph .                                  # layered graph + membership findings
/tmp/crate_graph . --dot | dot -Tsvg > crates.svg   # cycle edges drawn in red
/tmp/crate_graph . --json
/tmp/manifest_lint crates/core/Cargo.toml           # a member: checks its whole workspace
/tmp/dep_audit . --json                             # machine-readable findings
/tmp/manifest_lint . --strict                       # exit 1 on any finding (CI gate)
/tmp/dep_audit . --select CW003,CW007 --ignore CW014
cat Cargo.toml | /tmp/manifest_lint -               # one manifest from stdin
/tmp/dep_audit --list-rules                         # each script lists its rules with why and fix
```

| Rule | Name | Severity |
|------|------|----------|
| CW001 | resolver-missing (virtual manifest, or root package on edition < 2021) | high |
| CW002 | root-only-section-in-member (`[profile]`, `[patch]`, `[replace]`) | high |
| CW003 | duplicated-dependency (not using `[workspace.dependencies]`) | medium |
| CW004 | package-field-not-inherited (`[workspace.package]` key neither inherited nor set) | low |
| CW005 | inconsistent-edition | medium |
| CW006 | missing-rust-version | low |
| CW007 | unversioned-path-dependency (path/git dep without version in a publishable crate) | high |
| CW008 | publish-not-set (no description/license yet no `publish = false`) | low |
| CW009 | member-missing (path without Cargo.toml, glob matching nothing) | high |
| CW010 | crate-not-in-workspace | medium |
| CW011 | dependency-cycle (normal/build edges) | high |
| CW012 | lints-not-inherited | medium |
| CW013 | wildcard-version (`"*"`) | high |
| CW014 | git-dependency-unpinned (no `rev`/`tag`) | medium |
| CW015 | inherit-undefined (`x.workspace = true` with nothing to inherit) | high |
| CW016 | default-features-ignored | medium |
| CW017 | deprecated-underscore-key (`dev_dependencies`, `default_features`, `[project]`) | medium |
| CW018 | default-member-invalid | high |
| CW019 | virtual-manifest-section (`[dependencies]`, `[features]` in a virtual manifest) | high |
| CW020 | msrv-below-manifest-feature (edition 2024 < 1.85, resolver 3 < 1.84, `[lints]` < 1.74...) | medium |

Members are found like Cargo does: `members` globs minus `exclude`, plus path dependencies of a root package
(implicit members); nested workspaces, hidden directories and `target/` are skipped. Exit codes: 0 clean (or
findings without `--strict`), 1 findings with `--strict`, 2 usage error or missing/invalid root manifest;
`crate_graph` also exits 1 whenever there is a dependency cycle. Unparsable member manifests are warned about
and skipped.

## Additional Resources

| File | Content |
|------|---------|
| [crate-boundaries-and-layouts.md](references/crate-boundaries-and-layouts.md) | When to split/merge, layouts, naming, layering, proc-macro and -sys crates, xtask, build.rs, tests/benches/examples |
| [manifest-and-inheritance.md](references/manifest-and-inheritance.md) | Every `[workspace]` key, inheritance rules, workspace deps, lints, profiles, `.cargo/config.toml` |
| [features-and-unification.md](references/features-and-unification.md) | Additive feature design, `dep:`/`?/`, resolver 2/3 rules, unification pitfalls, cargo-hack, workspace-hack |
| [publishing-msrv-and-lockfiles.md](references/publishing-msrv-and-lockfiles.md) | Internal path + version deps, publish order, release tools, semver-checks, Cargo.lock and MSRV policy |
| [ci-and-tooling.md](references/ci-and-tooling.md) | GitHub Actions workflows, --locked, nextest, rust-cache, sccache, cargo-deny/machete/udeps/hack |
| [build-performance.md](references/build-performance.md) | `cargo build --timings`, splitting hot crates, profiles, linkers, codegen bloat, CI cache strategy |
| [version-history.md](references/version-history.md) | Cargo workspace/manifest features by Rust version, edition 2021/2024 changes |
