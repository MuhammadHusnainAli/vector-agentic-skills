# Build Performance in Workspaces

Workspace structure is the biggest lever on Rust build times after "do less work". This file covers how to
measure, which structural changes help, and the profile, linker and CI settings that matter. Measure before and
after every change; intuition about Rust build times is wrong surprisingly often.

## Contents

- [Measure first](#measure-first)
- [Reading cargo build --timings](#reading-cargo-build---timings)
- [Structural fixes](#structural-fixes)
- [Dependency diet](#dependency-diet)
- [Profile settings for fast iteration](#profile-settings-for-fast-iteration)
- [Linking](#linking)
- [Codegen bloat: generics and macros](#codegen-bloat-generics-and-macros)
- [Avoiding needless rebuilds](#avoiding-needless-rebuilds)
- [CI build speed](#ci-build-speed)
- [Nightly-only options](#nightly-only-options)
- [Playbook](#playbook)

## Measure first

```bash
cargo clean && cargo build --workspace --timings          # writes target/cargo-timings/cargo-timing.html
touch crates/shop-domain/src/lib.rs && cargo build --timings   # incremental: what rebuilds after an edit?
cargo build --release --timings
cargo check --workspace                                   # front-end only (no codegen): your editor's loop
```

Measure the scenario that hurts: clean CI build, incremental build after editing a low-level crate, or
`cargo test` link time. They have different fixes.

Additional tools:
- `cargo llvm-lines -p crate` (cargo-llvm-lines): which functions generate the most LLVM IR (monomorphisation
  bloat).
- `cargo bloat --release --crates` (cargo-bloat): binary size per crate.
- `RUSTFLAGS="-Zself-profile"` (nightly) + `measureme` / `summarize` for compiler-pass detail.
- `cargo tree --workspace -e normal | wc -l` and `cargo tree -d`: how big the graph is, and duplicates.

## Reading cargo build --timings

The HTML report shows each crate as a bar on a timeline, coloured by phase (front-end/metadata vs codegen),
plus a concurrency graph of how many units ran in parallel.

| Pattern in the report | Meaning | Fix |
|----------------------|---------|-----|
| One long bar with nothing else running | a crate on the critical path that everything waits for | split it, move dependents off it, or shrink it |
| Long tail where one leaf crate (often the binary) builds alone at the end | the top crate is huge | move code into libraries below it that build in parallel |
| Many short bars but low concurrency early | a deep chain of dependencies (A -> B -> C -> D) | flatten: make crates depend on the bottom directly, not through each other |
| Proc-macro crates (`syn`, `serde_derive`) early and long | macro infrastructure blocks everything | fewer macro crates, smaller `syn` feature sets, `[profile.dev.build-override] opt-level` |
| Build script (`build-script-build`) runs long | native compilation (cc, cmake), bindgen | prebuilt/system library, cache, move codegen to xtask |
| Codegen phase dominates | lots of monomorphised generic code or `opt-level` high in dev | see codegen bloat; lower dev opt-level of own crates |

Pipelining: a crate can start compiling as soon as its dependencies' *metadata* is ready, before their codegen
finishes. A dependent therefore waits on the dependency's front-end time, not its full time; this is why
splitting a crate whose front-end (type checking) is slow pays off most.

## Structural fixes

1. **Split the crate on the critical path** into pieces that do not depend on each other. Two halves that
   depend on each other in a chain do not help.
2. **Make the graph wide, not deep.** `app -> service -> repo -> model` serialises four crates; if `app`,
   `service` and `repo` each depend only on `model`, three of them build in parallel.
3. **Keep volatile code high in the graph.** An edit rebuilds the edited crate and everything that depends on
   it. Code that changes daily (business logic, handlers) belongs in crates near the top; stable code
   (types, protocols, utilities) at the bottom.
4. **Isolate heavy dependencies** behind a crate boundary so most edits never touch the crates that link them.
   `shop-infra` pays for sqlx; `shop-domain` and its tests do not.
5. **Thin binaries.** `apps/server/src/main.rs` wires things together; logic lives in libraries. Large binary
   crates rebuild entirely on every edit and are slow to link.
6. **Consolidate integration tests** into one binary per crate (`tests/it/main.rs`): N test files = N link
   steps.
7. **Do not over-split.** Each crate adds metadata generation, rmeta loading in every dependent, and a manifest
   to maintain. Merging tiny crates that always change together can speed builds up.

## Dependency diet

- `default-features = false` at the root for heavy crates; enable only what is used (see
  [features-and-unification.md](features-and-unification.md)).
- Look for duplicates (`cargo tree -d`): two versions of `syn`, `hyper` or `windows-sys` double their compile
  time. Align versions, or wait for upstream.
- Replace heavy dependencies for trivial uses (a regex for one fixed string, a full HTTP client for one GET in a
  build script).
- Check `cargo build --timings` for the top 10 slowest dependencies; for each, ask who needs it
  (`cargo tree -i heavy-crate`).
- Prefer `serde` derives over handwritten macros that each pull their own `syn`; prefer one well-known macro
  ecosystem over several.

## Profile settings for fast iteration

```toml
# root Cargo.toml
[profile.dev]
debug = "line-tables-only"      # 1.71+: much less debuginfo to generate and link; backtraces keep line numbers

[profile.dev.package."*"]
opt-level = 2                   # dependencies are compiled once and cached: make them fast at runtime

[profile.dev.build-override]
opt-level = 3                   # build scripts and proc-macros (incl. their deps) execute faster

[profile.release]
lto = "thin"
codegen-units = 1               # release speed; costs build time, so not for dev

[profile.ci]                    # cargo build --profile ci: optimised enough for tests, faster than release
inherits = "dev"
debug = false
incremental = false
```

- `debug = false` or `"line-tables-only"` in dev is often the single biggest win for link times on large
  projects; switch to full debuginfo temporarily when you need a debugger.
- `opt-level = 1` for your own crates in dev can make tests that do real work much faster at a small build-time
  cost; measure.
- `codegen-units = 1` and `lto = "fat"` belong in a dedicated `dist` profile, not in the everyday `release`, if
  release builds are part of the development loop.
- `incremental = true` (dev default) is good locally and useless in CI.

## Linking

Linking is serial per binary and dominates incremental builds of large binaries and test suites.

| Platform | Option |
|----------|--------|
| x86_64 Linux | Rust 1.90+ uses `rust-lld` by default on `x86_64-unknown-linux-gnu`; before that, or for even faster links, use mold |
| Linux (any) | mold: `linker = "clang"`, `rustflags = ["-C", "link-arg=-fuse-ld=mold"]` under `[target.<triple>]` |
| macOS | the default Apple linker (ld-prime, Xcode 15+) is already fast; `split-debuginfo = "unpacked"` is the macOS dev default |
| Windows MSVC | `rust-lld`: `linker = "rust-lld.exe"` under `[target.x86_64-pc-windows-msvc]` |

Put linker choices in `.cargo/config.toml` only if every developer and CI image has the linker installed;
otherwise in `$CARGO_HOME/config.toml` per machine. Fewer, larger test binaries also mean fewer link steps.

## Codegen bloat: generics and macros

- Generic functions are monomorphised in each crate that instantiates them, per type. A generic function used
  with 30 types in 10 crates is compiled up to 300 times.
- **Non-generic inner function** trick: keep the generic shim thin and forward to a concrete function.

```rust
pub fn read_config<P: AsRef<std::path::Path>>(path: P) -> std::io::Result<String> {
    fn inner(path: &std::path::Path) -> std::io::Result<String> {
        std::fs::read_to_string(path)     // compiled once
    }
    inner(path.as_ref())                  // only this line is monomorphised per P
}
```

- Prefer `&dyn Trait` / `Box<dyn Trait>` at boundaries that are not hot.
- Large `#[derive]` on hundreds of types (serde, clap) generate a lot of code; consider whether all of it is
  needed (e.g. only `Serialize`).
- Use `cargo llvm-lines` to find the top offenders before refactoring.

## Avoiding needless rebuilds

| Cause | Symptom | Fix |
|-------|---------|-----|
| Different feature sets between commands (`-p` vs `--workspace`, build vs test) | dependencies recompile when switching | consistent selections, workspace-hack crate |
| `RUSTFLAGS` differ between terminal, IDE and scripts | everything rebuilds | same flags everywhere; separate `target-dir` for the IDE |
| rust-analyzer and terminal share `target/` with different settings | they invalidate each other, lock contention | rust-analyzer `cargo.targetDir = true` (uses a subdirectory) |
| Build script without `rerun-if-changed` | crate rebuilds whenever any file in the package changes | emit precise `cargo::rerun-if-changed=` / `rerun-if-env-changed=` |
| Build script that touches files or embeds timestamps | rebuilds every time | deterministic outputs, write only when content changes |
| `env!("GIT_HASH")` via build.rs in a low crate | every commit rebuilds the world | put version info in the top binary crate only |
| Editing a crate at the bottom of the graph | everything above rebuilds | expected; move volatile code up |

## CI build speed

- `CARGO_INCREMENTAL=0`; cache dependencies (rust-cache) or compilations (sccache); see
  [ci-and-tooling.md](ci-and-tooling.md#caching-rust-cache-and-sccache).
- Use `cargo check` / `clippy` for the lint job (no codegen), `cargo nextest` with `--partition` for tests.
- Build tests once and reuse: `cargo nextest archive` then run the archive on several machines.
- Build only what changed on PRs, but keep a full workspace build on `main`.
- Avoid `--release` in CI unless tests need speed; a custom `ci` profile is a middle ground.
- Large runners help less than expected when the critical path is one serial crate; fix the structure first.

## Nightly-only options

These are not stable; useful for local experiments, risky as a team default:

- Parallel front-end: `RUSTFLAGS="-Z threads=8"`.
- Cranelift codegen backend for dev builds (`rustup component add rustc-codegen-cranelift-preview` on nightly,
  then `-Zcodegen-backend=cranelift`): much faster debug codegen, slower generated code.
- `-Zshare-generics` to reuse monomorphisations from dependencies, and `-Zself-profile` for profiling the compiler.

## Worked example: splitting the critical path

Before: `shop` is one 60k-line library crate plus a binary. `--timings` shows `shop` taking 95 s with one core
busy for most of it, then the binary linking for 12 s. Editing any handler rebuilds all 95 s.

```
before:  serde, tokio, sqlx ... -> shop (95 s, serial) -> shop-server (12 s link)
after:   serde ...  -> shop-domain (14 s)
         tokio ...  -> shop-app (22 s)        -> shop-api (18 s)  -> shop-server (thin, 6 s link)
         sqlx  ...  -> shop-infra (25 s)    /
```

- `shop-domain` and the dependency builds overlap; `shop-app` and `shop-infra` build in parallel once
  `shop-domain`'s metadata is ready.
- A handler edit now rebuilds only `shop-api` and the thin binary: about 25 s instead of 107 s.
- Clean build wall time drops less than incremental time (more crates, same total work); that is expected.
- `debug = "line-tables-only"` in dev cut the link from 12 s to 6 s independently of the split.

Numbers are illustrative; the shape (incremental time falling far more than clean time) is typical.

## Playbook

1. `cargo build --workspace --timings` from clean and after a typical edit; save both reports.
2. Identify the critical path and the slowest 10 units.
3. Cheap wins first: `debug = "line-tables-only"`, `[profile.dev.package."*"] opt-level`, faster linker, test
   binary consolidation, disabling unused default features.
4. Structural changes next: split the crate on the critical path, widen deep chains, isolate heavy deps.
5. `/tmp/crate_graph .` to confirm the new layering and no cycles.
6. Re-measure; keep the change only if the numbers moved.
