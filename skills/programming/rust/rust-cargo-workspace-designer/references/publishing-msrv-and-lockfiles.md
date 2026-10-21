# Publishing, Versioning, MSRV and Cargo.lock Policy

How internal crates reference each other so they can be published, how to version and release several crates,
how to keep semver honest, and the policies for `Cargo.lock` and the minimum supported Rust version (MSRV).

## Contents

- [Publishable or internal](#publishable-or-internal)
- [Internal dependencies: path plus version](#internal-dependencies-path-plus-version)
- [What cargo publish requires](#what-cargo-publish-requires)
- [Versioning strategies](#versioning-strategies)
- [Release order and tooling](#release-order-and-tooling)
- [Semver checking](#semver-checking)
- [Cargo.lock policy](#cargolock-policy)
- [MSRV policy](#msrv-policy)
- [Git and patched dependencies](#git-and-patched-dependencies)
- [Private registries](#private-registries)

## Publishable or internal

Decide per crate and write it down in the manifest:

| Crate kind | `publish` | Why |
|------------|-----------|-----|
| Library meant for crates.io | omit (or a registry list) | needs `description`, `license`/`license-file`, versioned deps |
| Proc-macro crate of a published library | omit | published together with the runtime crate |
| Binary / service (`apps/*`) | `false` | deployed, not published (or published deliberately as a `cargo install` tool) |
| `xtask`, `test-support`, `e2e`, `benches`, `workspace-hack` | `false` | never meant for others |
| Company-internal library | `["company-registry"]` | can only go to the named registry |

`publish = false` makes `cargo publish` refuse, lets release tools skip the crate, and allows path-only
dependencies. A crate without `description` or `license` cannot be published to crates.io anyway; saying
`publish = false` explicitly is clearer (CW008). Since Cargo 1.75 `package.version` may be omitted; it then
defaults to `0.0.0` and the package cannot be published, which suits apps and xtask.

Workspace-wide default with opt-in:

```toml
# root
[workspace.package]
publish = false
# the few published crates
[package]
publish = true          # an explicit value in the member overrides; do not inherit here
```

## Internal dependencies: path plus version

During development Cargo uses `path`; when publishing it strips `path` and keeps `version`, so the published
manifest points at the crates.io release.

```toml
# root Cargo.toml
[workspace.dependencies]
shop-domain = { path = "crates/shop-domain", version = "0.3.0" }
shop-macros = { path = "crates/shop-macros", version = "=0.3.0" }   # exact pin for a tightly coupled macro crate
```

```toml
# crates/shop-app/Cargo.toml
[dependencies]
shop-domain.workspace = true
shop-macros.workspace = true
```

- A normal or build dependency with only `path` in a publishable crate fails `cargo publish` (CW007).
- **Dev-dependencies may be path-only**: Cargo removes dev-dependencies without a version from the published
  manifest. That is the standard way to use a `test-support` crate.
- Use `=x.y.z` for a proc-macro companion whose generated code relies on private items of the runtime crate
  (`serde` / `serde_derive` style), so mismatched versions cannot combine.
- The version requirement must be satisfiable by the path crate's actual version, or Cargo errors locally.
  When bumping, update both the crate's `version` and the requirement (lockstep versioning with
  `version.workspace = true` makes this one edit).

## What cargo publish requires

- `name`, `version`, `description`, `license` or `license-file` (crates.io policy); `repository`,
  `documentation`, `readme`, `keywords` (max 5), `categories` (from the crates.io list) are recommended.
- Every normal/build dependency resolvable from a registry: no path-only, git-only or `"*"` (wildcard
  requirements are rejected by crates.io; CW013).
- The packaged crate must build on its own: `cargo publish` runs `cargo package`, which builds the `.crate`
  in isolation with dependencies from the registry. Files outside the package directory are not included, so
  `include_str!("../../README.md")` breaks; `readme`/`license-file` inherited from the workspace are copied in
  by Cargo.
- Dry run: `cargo publish --dry-run -p shop-domain`; inspect contents with `cargo package --list -p shop-domain`.
- Publishing is permanent: versions can be yanked (`cargo yank --version 0.3.1`) but never deleted or reused.

## Versioning strategies

| Strategy | How | Good for | Cost |
|----------|-----|----------|------|
| Lockstep | `version.workspace = true` everywhere; one version for all | tightly coupled crates released together (a framework and its macros) | unchanged crates get new versions |
| Independent | each crate sets its own `version` | loosely coupled libraries with separate users | must track which dependents need bumps |
| Hybrid | lockstep for a core group, independent for satellites | most real projects | discipline |

Semver for Rust crates (Cargo's interpretation):
- `1.2.3 -> 1.2.4`: bug fixes; `1.2 -> 1.3`: additive changes; `1.x -> 2.0`: breaking changes.
- Below 1.0 the left-most non-zero component is the "major": `0.3.1 -> 0.4.0` is breaking, `0.3.1 -> 0.3.2` is
  not. A caret requirement `"0.3"` means `>=0.3.0, <0.4.0`.
- Raising MSRV is not considered breaking by Cargo, but say so in the changelog; many crates bump at least the
  minor version for it.
- Adding a public dependency's types to your API ties your major version to theirs. Re-exporting `tokio` types
  means a tokio 2.0 is a breaking change for you.

## Release order and tooling

Crates must be published bottom-up: a dependency has to exist on the registry before a dependent referencing its
version can be published. `/tmp/crate_graph .` lists crates by layer; publish layer 0
first.

| Tool | What it does |
|------|--------------|
| `cargo publish -p crate` | publishes one package; you handle order and version bumps |
| `cargo publish --workspace` | Cargo 1.90+: publishes several packages, ordering them by dependencies |
| release-plz | opens a release PR with version bumps and changelogs from conventional commits, publishes on merge; uses cargo-semver-checks |
| cargo-release (`cargo release`) | bumps versions, tags, publishes in order, pushes; configurable per workspace |
| cargo-workspaces (`cargo ws`) | lerna-style: list changed crates, version, publish |
| cargo-dist | builds and uploads release artefacts (binaries, installers) for `apps/*` |

Whatever the tool, the steps are: bump versions (including requirements of internal dependents), update the
changelog, `cargo publish --dry-run` in dependency order, tag, publish, push.

## Semver checking

`cargo-semver-checks` compares the public API of a crate against its last published version (or a git
revision) and reports breaking changes such as removed public items, new required trait items, changed function
signatures, or auto-trait changes.

```bash
cargo install cargo-semver-checks --locked
cargo semver-checks --workspace                       # all publishable members vs crates.io
cargo semver-checks -p shop-domain --baseline-rev origin/main
```

CI: `obi1kenobi/cargo-semver-checks-action@v2` on PRs to libraries. It cannot catch behavioural changes or
everything about generics; treat it as a safety net, not proof. Crates with `publish = false` are skipped.

## Cargo.lock policy

The Cargo team changed its guidance in August 2023 ("Change in Guidance on Committing Lockfiles"): **commit
`Cargo.lock` by default for every project, libraries included**, and decide consciously if you want otherwise.
`cargo new` no longer adds `Cargo.lock` to `.gitignore` for libraries.

Why it matters for workspaces:
- There is one `Cargo.lock` for the whole workspace at the root; members never have their own.
- CI with `--locked` fails when the lock file is missing or out of date, so dependency changes appear in
  reviewed diffs, not as surprise breakages on a Tuesday.
- `git bisect` and reproducing old builds need the old lock file.
- Published libraries' lock files are ignored by their users (except for `cargo install --locked`), so committing
  one costs users nothing.

What a committed lock does *not* do: test your library against the newest compatible versions your users will
get. Add a scheduled job for that:

```bash
cargo update                       # latest compatible versions
cargo test --workspace             # catches breakage before users do
# and the opposite end, nightly-only:
cargo +nightly update -Z direct-minimal-versions && cargo test --workspace   # lowest declared versions
```

Keep the lock fresh with Dependabot or Renovate (both understand Cargo workspaces) or a weekly `cargo update`
PR. `cargo update -p serde` and `cargo update -p serde --precise 1.0.210` update a single package.

Lock file format: Cargo 1.83+ writes lockfile version 4 by default, which Cargo older than 1.78 cannot read. If
your MSRV job uses an older toolchain, generate the lock file with that toolchain or keep the version line at 3
(`version = 3` at the top of `Cargo.lock`; newer Cargo preserves an existing version).

## MSRV policy

Declare it, test it, and decide how you raise it.

```toml
[workspace.package]
rust-version = "1.85"      # members: rust-version.workspace = true
```

- **Declare**: `rust-version` makes Cargo fail early with "package X cannot be built because it requires rustc
  1.85 or newer" instead of an obscure syntax error, and feeds MSRV-aware resolution.
- **Resolve for it**: `resolver = "3"` (or `incompatible-rust-versions = "fallback"` in `.cargo/config.toml`)
  makes `cargo update` prefer dependency versions compatible with the declared MSRV.
- **Test it**: a CI job on exactly that toolchain (`cargo +1.85 check --workspace --all-targets --locked`, or
  `cargo hack check --rust-version --workspace`). Use `cargo msrv find` to discover the real minimum and
  `cargo msrv verify` to check the declared one.
- **Keep the manifest compatible**: edition 2024 needs 1.85, `resolver = "3"` 1.84, `[lints]` 1.74, workspace
  inheritance 1.64, `dep:`/`?/` 1.60 (CW020).
- **Policies people use**: "latest stable only" (applications, internal services), "N-2 / last 6 months"
  (many ecosystem libraries), "whatever Debian stable / a given LTS distro ships" (system tools). Write it in
  the README and bump it in a minor release.
- Different members may have different MSRVs (a core library supports older compilers than the CLI), but then
  the workspace-level CI job must check each crate against its own (`cargo hack --rust-version` does that).

## Git and patched dependencies

- `git` dependencies are fine for applications and short-lived forks; pin them with `rev` or `tag` (CW014).
  `branch` moves on every `cargo update`.
- They cannot be published to crates.io unless they also have a `version` (then Cargo publishes the version
  requirement and drops the git source).
- Prefer `[patch.crates-io]` in the root manifest for "use my fork until upstream releases": dependents keep the
  normal crates.io requirement, so removing the patch later is one deletion, and published crates are unaffected.

```toml
[patch.crates-io]
hyper = { git = "https://github.com/acme/hyper", rev = "0c5f8e1" }   # upstream PR #3721; remove after 1.5.1
```

## Private registries

```toml
# .cargo/config.toml
[registries.acme]
index = "sparse+https://cargo.acme.example/index/"
```

```toml
# Cargo.toml
[package]
publish = ["acme"]
[dependencies]
acme-auth = { version = "2", registry = "acme" }
```

Authentication goes through credential providers (`[registry] global-credential-providers`, stable since
1.74) or `CARGO_REGISTRIES_ACME_TOKEN` in CI; never commit tokens. In `[workspace.dependencies]`, the
`registry` key is set at the root and inherited like every other source key.
