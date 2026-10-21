# CI and Tooling for Cargo Workspaces

A CI setup that proves the workspace builds, tests, lints and stays publishable, plus the cargo plugins that
keep dependencies tidy. Commands assume a workspace root; every cargo invocation in CI uses `--locked`.

## Contents

- [What CI must prove](#what-ci-must-prove)
- [Core commands](#core-commands)
- [GitHub Actions workflow](#github-actions-workflow)
- [Caching: rust-cache and sccache](#caching-rust-cache-and-sccache)
- [cargo-nextest](#cargo-nextest)
- [Dependency hygiene: deny, machete, udeps, shear](#dependency-hygiene-deny-machete-udeps-shear)
- [Feature and MSRV matrix: cargo-hack](#feature-and-msrv-matrix-cargo-hack)
- [Semver and release checks](#semver-and-release-checks)
- [Only building what changed](#only-building-what-changed)
- [Workspace audit in CI](#workspace-audit-in-ci)
- [Tool summary](#tool-summary)

## What CI must prove

| Property | Command |
|----------|---------|
| Formatting | `cargo fmt --all --check` |
| Every crate, every target compiles | `cargo build --workspace --all-targets --locked` (or `check`) |
| Lints clean | `cargo clippy --workspace --all-targets --all-features --locked -- -D warnings` |
| Tests pass | `cargo nextest run --workspace --locked` + `cargo test --workspace --doc --locked` |
| Lock file is committed and current | `--locked` on every command |
| Each crate builds with its own features | `cargo hack check --workspace --each-feature --no-dev-deps` |
| MSRV holds | `cargo +1.85 check --workspace --all-targets --locked` or `cargo hack check --rust-version --workspace` |
| Docs build without broken links | `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps --locked` |
| Licenses / advisories / duplicate policy | `cargo deny check` |
| Published API not broken | `cargo semver-checks --workspace` |
| Workspace structure | `/tmp/manifest_lint . --strict`, `/tmp/dep_audit . --strict`, `/tmp/crate_graph .` (this skill's scripts) |

Key flags:
- `--workspace` (alias `--all`, deprecated) selects every member; without it a virtual manifest builds
  `default-members` or all members, and a root package builds only itself.
- `--all-targets` = lib, bins, tests, benches, examples. Without it, examples and benches rot.
- `--locked` fails if `Cargo.lock` would change. `--offline` forbids network. `--frozen` = both.
- `--all-features` checks feature-gated code; it is not a substitute for testing features one by one.
- `--keep-going` (1.74) reports all failing crates instead of stopping at the first.

## Core commands

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo build --workspace --all-targets --locked
cargo nextest run --workspace --all-features --locked
cargo test --workspace --doc --locked
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps --all-features --locked
```

Put the same list in `cargo xtask ci` (see [crate-boundaries-and-layouts.md](crate-boundaries-and-layouts.md#the-xtask-pattern))
so developers run exactly what CI runs.

## GitHub Actions workflow

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

env:
  CARGO_TERM_COLOR: always
  CARGO_INCREMENTAL: 0          # incremental artefacts are useless in CI and bloat the cache
  RUST_BACKTRACE: 1

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: clippy, rustfmt
      - uses: Swatinem/rust-cache@v2
        with:
          save-if: ${{ github.ref == 'refs/heads/main' }}
      - run: cargo fmt --all --check
      - run: cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
      - run: |                                                 # this skill's scripts, vendored under scripts/
          for t in manifest_lint dep_audit crate_graph; do rustc -O --edition 2021 scripts/$t.rs -o /tmp/$t; done
          /tmp/manifest_lint . --strict && /tmp/dep_audit . --strict && /tmp/crate_graph .

  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
      - uses: taiki-e/install-action@v2
        with:
          tool: cargo-nextest
      - run: cargo nextest run --workspace --all-features --locked --profile ci
      - run: cargo test --workspace --doc --locked

  msrv:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@master
        with:
          toolchain: "1.85"     # keep in sync with workspace.package.rust-version
      - uses: Swatinem/rust-cache@v2
      - run: cargo check --workspace --all-targets --locked

  features:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
      - uses: taiki-e/install-action@v2
        with:
          tool: cargo-hack
      - run: cargo hack check --workspace --each-feature --no-dev-deps

  deny:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: EmbarkStudios/cargo-deny-action@v2
```

Notes:
- `dtolnay/rust-toolchain@stable` installs the latest stable; `@master` with a `toolchain` input installs a
  specific version. A `rust-toolchain.toml` at the root pins the toolchain for everyone (CI and developers);
  then the action only needs to install components.
- `save-if` saves the cache only from `main`, so PR branches restore it without each writing gigabytes.
- `fail-fast: false` keeps the other OS jobs running when one fails.
- Cross-platform matrix: run full tests on Linux, a smoke `check` on others if minutes matter.

## Caching: rust-cache and sccache

**Swatinem/rust-cache** caches `~/.cargo` (registry, git) and `target/` keyed by the lock file, toolchain
and job. Useful inputs:

| Input | Use |
|-------|-----|
| `shared-key` | share one cache between jobs that build the same thing |
| `key` | extra key component (e.g. a feature set) |
| `workspaces` | `"path/to/ws -> target"` when the workspace is not at the repo root or there are several |
| `cache-on-failure` | save even if the job failed (warm cache for the retry) |
| `save-if` | restrict saving (e.g. main only) |
| `cache-targets` | `false` to cache only `~/.cargo` |

It removes workspace members' own artefacts before saving, keeping only dependency artefacts, which is the
part that is expensive and stable.

**sccache** caches individual `rustc` invocations in a backend (GitHub Actions cache, S3, GCS, Redis, local
disk). It helps when many jobs or branches compile the same dependencies with the same flags.

```yaml
      - uses: mozilla-actions/sccache-action@v0.0.9   # pin the current release
      - run: cargo build --workspace --all-targets --locked
        env:
          SCCACHE_GHA_ENABLED: "true"
          RUSTC_WRAPPER: sccache
```

- sccache cannot cache incremental compilation, linking, or crates with build scripts that are not
  deterministic; set `CARGO_INCREMENTAL=0`.
- Use either rust-cache's `target/` caching or sccache as the primary mechanism; both together mostly
  duplicate storage. Many teams use rust-cache for small workspaces and sccache for large ones.
- Locally, `RUSTC_WRAPPER=sccache` shares compiled dependencies between different checkouts and worktrees.

## cargo-nextest

A faster test runner: each test runs in its own process, in parallel across all test binaries, with retries,
timeouts, JUnit output and partitioning.

```bash
cargo nextest run --workspace --locked
cargo nextest run -p shop-app -E 'test(order::)'       # filter expression
cargo nextest run --workspace --partition count:1/4    # shard across CI machines
cargo nextest archive --workspace --archive-file tests.tar.zst   # build once, run elsewhere
```

```toml
# .config/nextest.toml
[profile.ci]
retries = 2
fail-fast = false
slow-timeout = { period = "60s", terminate-after = 3 }

[profile.ci.junit]
path = "junit.xml"
```

nextest does **not** run doctests; keep `cargo test --doc --workspace` as a separate step. Tests that rely on
shared in-process state across tests (a global set once per binary) behave differently under
process-per-test; that is usually a bug worth fixing.

## Dependency hygiene: deny, machete, udeps, shear

**cargo-deny** checks the full dependency graph against a policy in `deny.toml`:

```bash
cargo install cargo-deny --locked
cargo deny init               # writes a commented deny.toml
cargo deny check              # advisories, bans, licenses, sources
cargo deny check advisories   # one category
```

```toml
# deny.toml (excerpt)
[advisories]
ignore = []                   # RUSTSEC ids with a justification comment

[licenses]
allow = ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "Unicode-3.0"]

[bans]
multiple-versions = "warn"    # duplicate crates in the graph
wildcards = "deny"            # "*" requirements (path deps without version count unless allow-wildcard-paths)
deny = [{ name = "openssl-sys", reason = "use rustls" }]

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-git = []
```

**cargo-audit** (`cargo audit`) checks only RustSec advisories against `Cargo.lock`; cargo-deny's `advisories`
check covers the same database.

**Unused dependencies**:

| Tool | How it works | Toolchain | Trade-off |
|------|--------------|-----------|-----------|
| cargo-machete | text search of sources for each dependency name | stable, very fast | false positives for deps used only via macros or renamed; ignore with `[package.metadata.cargo-machete] ignored = ["..."]` |
| cargo-shear | parses sources to find unused deps (also misplaced dev-deps) | stable, fast | newer; similar caveats |
| cargo-udeps | uses compiler output to find deps never linked | **nightly** (`cargo +nightly udeps --workspace --all-targets`) | precise, but needs a full build per configuration |

Run machete or shear on every PR (seconds), udeps on a schedule.

## Feature and MSRV matrix: cargo-hack

```bash
cargo hack check --workspace --each-feature --no-dev-deps
cargo hack check --workspace --feature-powerset --depth 2 --no-dev-deps
cargo hack check --workspace --rust-version             # each crate with its own rust-version toolchain
cargo hack test --workspace --each-feature --exclude-features nightly
```

cargo-hack builds packages one at a time, so feature unification across members cannot hide missing features.
Details: [features-and-unification.md](features-and-unification.md#testing-feature-combinations).

## Semver and release checks

```yaml
  semver:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: obi1kenobi/cargo-semver-checks-action@v2
```

Also run `cargo publish --dry-run -p <crate>` for each publishable crate in release PRs (bottom layer first),
or let release-plz do both. See [publishing-msrv-and-lockfiles.md](publishing-msrv-and-lockfiles.md).

## Only building what changed

In large workspaces, building every member for every PR wastes time. Options:

- **Rely on caches first.** With rust-cache or sccache, unchanged crates are mostly free.
- **Path filters per app** in CI (`on.pull_request.paths`), coarse but simple.
- **Affected-crates computation**: map changed files to members, then add their reverse dependencies.
  `cargo metadata --format-version 1` gives the graph; tools such as `cargo-guppy`-based `determinator`, or
  `cargo hakari`'s companion tooling, compute affected packages. Then run
  `cargo nextest run -p crate-a -p crate-b`. Always keep a full `--workspace` run on `main`.
- **Remember feature unification**: building a subset can change features and miss errors that the full build
  would show, or vice versa. The full build on `main` is the backstop.

## Workspace audit in CI

The three scripts are single-file, std-only Rust programs: `rustc` compiles each in about a second, no Cargo
project or network needed, so they can run in the cheapest job (any runner with a Rust toolchain):

```bash
for t in manifest_lint dep_audit crate_graph; do rustc -O --edition 2021 scripts/$t.rs -o /tmp/$t; done
/tmp/manifest_lint . --strict                     # fail on any manifest finding
/tmp/dep_audit . --strict --ignore CW014          # tolerate unpinned git deps while migrating
/tmp/dep_audit . --json > dep-audit.json          # artefact for dashboards
/tmp/crate_graph . --dot > crates.dot             # document the architecture (exit 1 on a cycle)
```

## Tool summary

| Tool | Install | Purpose |
|------|---------|---------|
| cargo-nextest | `taiki-e/install-action` with `tool: cargo-nextest` | fast, parallel, sharded tests |
| cargo-hack | `cargo install cargo-hack --locked` | per-crate feature and MSRV matrices |
| cargo-deny | `EmbarkStudios/cargo-deny-action@v2` | advisories, licenses, bans, sources |
| cargo-audit | `cargo install cargo-audit --locked` | RustSec advisories only |
| cargo-machete / cargo-shear | `cargo install cargo-machete --locked` | unused dependencies, stable toolchain |
| cargo-udeps | `cargo install cargo-udeps --locked` | unused dependencies, nightly, precise |
| cargo-semver-checks | `obi1kenobi/cargo-semver-checks-action@v2` | breaking API changes |
| cargo-msrv | `cargo install cargo-msrv --locked` | find / verify the MSRV |
| cargo-hakari | `cargo install cargo-hakari --locked` | workspace-hack crate for unified features |
| release-plz / cargo-release | see publishing reference | version bumps and ordered publishing |
| sccache | `mozilla-actions/sccache-action` | shared compilation cache |
| Swatinem/rust-cache | GitHub Action | cache `~/.cargo` and dependency artefacts |
