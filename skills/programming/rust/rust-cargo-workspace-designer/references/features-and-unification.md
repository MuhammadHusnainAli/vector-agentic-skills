# Features and Feature Unification in Workspaces

Cargo features are compile-time switches. In a workspace they interact: Cargo compiles each dependency once
per build with the union of every feature any selected package asked for. This file covers how to design
features that survive that, and how to find the bugs unification hides.

## Contents

- [How features resolve](#how-features-resolve)
- [What resolver 2 and 3 change](#what-resolver-2-and-3-change)
- [Design rules](#design-rules)
- [Optional dependencies, dep: and weak features](#optional-dependencies-dep-and-weak-features)
- [default-features across a workspace](#default-features-across-a-workspace)
- [Unification pitfalls](#unification-pitfalls)
- [Inspecting features](#inspecting-features)
- [Testing feature combinations](#testing-feature-combinations)
- [Workspace-hack crates](#workspace-hack-crates)
- [Mutually exclusive choices](#mutually-exclusive-choices)
- [Checklist](#checklist)

## How features resolve

```toml
[features]
default = ["std"]
std = []
json = ["dep:serde_json", "serde"]
serde = ["dep:serde", "shop-domain/serde"]
```

- A feature is a name mapped to a list of other features, `dep:name` (enable an optional dependency) or
  `pkg/feature` (enable a feature of a dependency).
- `default` is enabled unless the dependent writes `default-features = false` (or passes
  `--no-default-features` for the package being built).
- For one build, Cargo computes the set of packages to compile (the selected members and their dependency
  graph), then for each dependency the **union** of features requested anywhere in that graph. One `tokio`
  is compiled with `rt-multi-thread` because one crate asked for it, and every other crate in that build sees
  `rt-multi-thread` too.
- Which members are selected matters: `cargo build --workspace`, `cargo build -p shop-app`, and building
  inside `crates/shop-app/` (which selects only that package) can produce three different feature sets for
  the same dependency.

## What resolver 2 and 3 change

With resolver 1, features are unified across every use of a dependency. Resolver 2 (default for edition
2021, explicit `resolver = "2"` in virtual manifests) splits the union in three places:

| Situation | Resolver 1 | Resolver 2 / 3 |
|-----------|------------|----------------|
| Same dep used as build-dependency (or by a proc-macro) and as a normal dependency | one feature set | host (build scripts, proc-macros) and target resolved separately; may compile twice |
| Dev-dependency enables extra features | always unified into the normal build | only when building targets that need dev-deps (tests, examples, benches) |
| `[target.'cfg(windows)'.dependencies]` features | unified even on Linux | only for the platform being built |
| `--features` / `--no-default-features` in a workspace | applied in odd ways to the root package | applied to the selected packages; `-F crate/feat` syntax for others |

Resolver 3 keeps resolver 2's feature behaviour and adds MSRV-aware *version* selection; it does not change
feature unification.

Consequence of the dev-dependency rule: `cargo build` and `cargo test` can compile a dependency with different
features (e.g. `tokio` gets `test-util` only for tests), so switching between them may rebuild that dependency.
That is the price of not leaking test-only features into release builds.

## Design rules

1. **Features are additive.** Enabling a feature may add items or capabilities; it must never remove an API,
   change a type's layout used by other crates, or change behaviour another crate relies on. Because of
   unification, *some other crate* can always turn your feature on.
2. **No negative features.** `no_std`, `disable-tls`, `without-x` break when two crates disagree. Invert them:
   `std` (default), `tls`, `x`.
3. **Small defaults for libraries.** Defaults are hard to turn off downstream (every dependent must write
   `default-features = false`, and inheritance cannot turn them off later). Put the common, cheap path in
   `default`; make heavy integrations opt-in.
4. **Name features after capabilities, not dependencies,** when the dependency is an implementation detail:
   `compression` rather than `flate2`. Use `dep:` so the dependency name does not become a public feature.
5. **Every feature combination compiles.** At least: no features, default, each feature alone, all features.
   `cargo hack` automates it.
6. **Forward features explicitly through layers.** If `shop-infra` has `serde`, it enables
   `shop-domain/serde`; it does not rely on someone else having enabled it.
7. **Document features** in the crate docs and gate docs with `#[cfg_attr(docsrs, doc(cfg(feature = "x")))]`
   (nightly docs.rs feature) or simply list them in the README.
8. **Test-only behaviour does not go in a feature that ships.** Use dev-dependencies, `#[cfg(test)]`, or a
   `test-support` crate.

## Optional dependencies, dep: and weak features

Since 1.60:

```toml
[dependencies]
serde = { workspace = true, optional = true, features = ["derive"] }
serde_json = { workspace = true, optional = true }
tokio = { workspace = true, optional = true }

[features]
default = ["std"]
std = ["serde?/std"]              # weak: only if serde is already enabled; does not enable serde
serde = ["dep:serde"]             # explicit feature name for the optional dep
json = ["serde", "dep:serde_json"]
runtime = ["dep:tokio", "tokio?/rt-multi-thread"]
```

- Without `dep:`, every optional dependency `foo` implicitly creates a feature `foo`. As soon as any feature
  uses `dep:foo`, that implicit feature is **not** created, so the dependency name stops being part of your
  public feature API.
- `pkg?/feat` (weak dependency feature) enables `feat` on `pkg` only if `pkg` is enabled by something else.
  Without the `?`, `std = ["serde/std"]` would turn serde on whenever `std` is on.
- Manifests using `dep:` or `?/` need Cargo 1.60+; declare `rust-version` accordingly (CW020 checks it).
- `#[cfg(feature = "serde")]` in code refers to *feature names*, not dependency names. Since 1.80 rustc checks
  cfg names and values (`unexpected_cfgs`), so a misspelled `#[cfg(feature = "serd")]` warns instead of
  silently compiling the item out.

```rust
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OrderId(pub u64);
```

## default-features across a workspace

Workspace inheritance is additive, so the root decides the floor:

```toml
# root Cargo.toml
[workspace.dependencies]
tokio = { version = "1.38", default-features = false }
serde = { version = "1", default-features = false }
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls"] }
```

```toml
# crates/shop-infra/Cargo.toml
[dependencies]
tokio = { workspace = true, features = ["rt-multi-thread", "net", "fs"] }
serde = { workspace = true, features = ["derive", "std"] }
reqwest = { workspace = true, features = ["json"] }
```

Pitfalls:

- `{ workspace = true, default-features = false }` with a root entry that keeps defaults on does nothing; Cargo
  warns, edition 2024 rejects it (CW016).
- Turning defaults off at the root but forgetting `std` on a crate that needs it: `serde` without `std`
  compiles in `--workspace` builds (some other crate enabled `std`) but fails with `-p` alone. Test with
  `cargo hack`.
- One crate anywhere in the build that depends on `reqwest` with defaults re-enables `native-tls` for
  everyone; `cargo tree -e features -i native-tls` finds who.

## Unification pitfalls

| Symptom | Cause | Fix |
|---------|-------|-----|
| `cargo build --workspace` passes, `cargo build -p shop-app` fails with "unresolved import" / "no method" | shop-app uses a dependency feature it never requested; another member enabled it | add the feature in shop-app's manifest; `cargo hack check --each-feature` per package |
| `cargo test` passes, `cargo build --release` fails | feature only enabled by a dev-dependency | add it to the normal dependency |
| Dependency rebuilds every time you alternate between two commands | different feature sets (or RUSTFLAGS) per command | build with consistent selections, workspace-hack crate, separate IDE target dir |
| Binary larger / slower to compile than expected | some crate enabled heavy defaults (e.g. `full`) | `cargo tree -e features -i <dep>`; disable defaults at root |
| Two copies of a crate in `cargo tree -d` | different major versions requested | align versions via `[workspace.dependencies]`; `cargo update -p dep@old` |
| `links` conflict ("only one package in the dependency graph may specify the same links value") | two versions of a `-sys` crate | unify the version of the wrapper crates that pull them in |
| Proc-macro dependency compiled twice | host vs target feature split (resolver 2) | expected; keep proc-macro deps' features minimal |
| Feature-gated code in a library is never compiled in CI | CI only builds `--workspace` with default features | `--all-features` job and `cargo hack --each-feature` job |

## Inspecting features

```bash
cargo tree -e features -i tokio                  # who enables which tokio features (inverted)
cargo tree -p shop-app -e features               # features active when building shop-app alone
cargo tree --workspace -d                        # duplicate versions
cargo tree -e normal --target all -i openssl-sys # who pulls a -sys crate on any platform
cargo metadata --format-version 1 | jq '.resolve.nodes[] | select(.id | contains("tokio")) | .features'
cargo build -p shop-app -v 2>&1 | grep -- '--cfg .feature'   # the cfgs rustc actually got
```

## Testing feature combinations

cargo-hack (taiki-e) runs a cargo command over feature combinations, **one package at a time**, which is
exactly what catches unification bugs:

```bash
cargo install cargo-hack --locked
cargo hack check --workspace --each-feature --no-dev-deps        # every feature alone (+ none, + all)
cargo hack check --workspace --feature-powerset --depth 2 --no-dev-deps   # pairs of features
cargo hack check --workspace --feature-powerset --exclude-features nightly --group-features a,b
cargo hack test --workspace --each-feature                       # run tests per feature (slower)
cargo hack check --rust-version --workspace                      # each crate on its declared rust-version
```

- `--no-dev-deps` drops dev-dependencies so their features cannot mask a missing one (and is faster); it edits
  manifests temporarily and restores them.
- `--feature-powerset` grows exponentially; bound it with `--depth`, `--group-features` and
  `--exclude-features`.
- Feature combinations that are intentionally unsupported can be skipped with `--exclude-features` or
  documented with `compile_error!`.

## Workspace-hack crates

Large workspaces sometimes add a crate (conventionally `workspace-hack`) that depends on every third-party
crate with the union of features any member uses, and make every member depend on it. Then every build
selection sees the same feature set: no rebuilds when switching `-p`, and better cache hits. `cargo-hakari`
generates and maintains such a crate (`cargo hakari generate`, `cargo hakari manage-deps`, `cargo hakari
verify` in CI).

Trade-offs: members compile features they do not need, the crate must be `publish = false` and is stripped or
replaced when publishing, and it is one more moving part. Worth it at tens of crates and heavy dependencies;
overkill for five crates.

## Mutually exclusive choices

Sometimes a choice really is exclusive (TLS backend, async runtime, allocator). Options in order of
preference:

1. **Avoid it at the library level.** Take the choice as a type parameter, a trait object or a runtime
   value; let the binary pick.
2. **Make both work at once.** Enable `rustls` and `native-tls` simultaneously and pick at runtime.
3. **Decide in the binary only.** Libraries expose features; only `apps/*` enable exactly one.
4. **Fail loudly** if both are enabled:

```rust
#[cfg(all(feature = "runtime-tokio", feature = "runtime-async-std"))]
compile_error!("features `runtime-tokio` and `runtime-async-std` are mutually exclusive");
```

Remember that unification can enable both behind your back; `compile_error!` turns a silent wrong choice into
a clear build error.

## Checklist

- [ ] Root `[workspace.dependencies]` disables default features of heavy crates; members add what they use
- [ ] No negative features; `std` is a default, not `no_std` a feature
- [ ] Optional deps use `dep:`; cross-crate feature forwarding uses `?/` where appropriate
- [ ] Every member builds alone: `cargo hack check --workspace --each-feature --no-dev-deps`
- [ ] CI has a `--all-features` job and a no-default-features job for libraries
- [ ] `cargo tree -d` reviewed; duplicates are intentional or tracked
- [ ] Exclusive choices live in binaries, or are guarded with `compile_error!`
