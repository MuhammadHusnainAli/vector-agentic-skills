# Version History: Trait Features by Rust Version

Use this to match a suggestion to the project's MSRV (`rust-version` in `Cargo.toml`). If the MSRV is older
than the version listed, use the "before" column.

## Contents

- [Stabilisations](#stabilisations)
- [Edition changes that affect traits](#edition-changes-that-affect-traits)
- [Still unstable (do not suggest for stable code)](#still-unstable-do-not-suggest-for-stable-code)
- [Terminology changes](#terminology-changes)
- [MSRV guidance](#msrv-guidance)

## Stabilisations

| Rust | Feature | Before it |
|------|---------|-----------|
| 1.26 | `impl Trait` in argument and return position | named generic parameters; `Box<dyn Trait>` returns |
| 1.27 | `dyn Trait` syntax | bare `Trait` as a type (deprecated, an error in edition 2021) |
| 1.34 | `TryFrom` / `TryInto` | custom conversion traits or `from_str`-style constructors |
| 1.41 | relaxed orphan rule: `impl ForeignTrait<LocalType> for ForeignType` | newtype wrappers |
| 1.51 | const generics (integers, `bool`, `char`) | macro-generated impls for array sizes |
| 1.62 | `#[derive(Default)]` on enums with `#[default]` on a unit variant | manual `impl Default` |
| 1.65 | generic associated types (`type Item<'a> where Self: 'a`) | lending-iterator crates, boxing |
| 1.75 | `async fn` and return-position `impl Trait` in traits (RPITIT) | `async-trait` (boxes every call), associated future types |
| 1.78 | `#[diagnostic::on_unimplemented]` for custom "trait not implemented" messages | `#[rustc_on_unimplemented]` (std only) |
| 1.79 | associated type bounds: `T: Iterator<Item: Display>` | `where T::Item: Display` |
| 1.81 | `core::error::Error` (the `Error` trait usable in `no_std`) | std-only error types, or crate-specific traits |
| 1.82 | precise capturing `impl Trait + use<'a, T>` | the `Captures<'a>` trick |
| 1.85 | edition 2024; async closures and `AsyncFn`, `AsyncFnMut`, `AsyncFnOnce` | `Fn(..) -> Fut` with owned arguments |
| 1.86 | trait upcasting: `&dyn Sub` -> `&dyn Super` coercion | an `as_super(&self) -> &dyn Super` method on the trait |

## Edition changes that affect traits

| Edition | Change |
|---------|--------|
| 2018 | `dyn Trait` encouraged (bare trait objects warn); anonymous `'_` in impl headers |
| 2021 | bare trait objects are a hard error; `TryFrom`, `TryInto`, `FromIterator` added to the prelude; disjoint closure captures |
| 2024 | `-> impl Trait` (including in traits) captures all in-scope lifetimes by default; `impl_trait_overcaptures` migration lint; `unsafe extern` blocks; `IntoIterator` for `Box<[T]>`; the `gen` keyword is reserved |

Prelude additions matter for trait design: adding a method named `try_from` or `from_iter` to your own trait
can become ambiguous once the std trait is in scope everywhere.

## Still unstable (do not suggest for stable code)

| Feature | Stable workaround |
|---------|-------------------|
| Specialization (`default fn`) | separate traits, or a marker trait plus explicit impls |
| Negative impls (`impl !Send for T`) | a `PhantomData<*const ()>` field to remove `Send`/`Sync` |
| Associated type defaults (`type Out = ();` in the trait) | document the expected type; add it in a major release |
| Return type notation (`T::method(..): Send`) | `-> impl Future + Send` in the trait, or `trait_variant` |
| `impl Trait` in associated types / type aliases (TAIT/ATPIT) | name the concrete type, or box it |
| Trait aliases (`trait Svc = Fn() + Send;`) | a subtrait with a blanket impl: `trait Svc: Fn() + Send {} impl<T: Fn() + Send> Svc for T {}` |
| `dyn` async traits (dyn-compatible `async fn`) | `async-trait`, or methods returning `Pin<Box<dyn Future + Send + '_>>` |

Check the release notes for the project's toolchain before promising any of these; nightly-only features should
never appear in advice for a stable MSRV.

## Terminology changes

- "Object safety" was renamed **dyn compatibility** in the Rust reference and compiler messages (E0038 now reads
  "the trait `X` is not dyn compatible"; older compilers say "cannot be made into an object"). Both refer to the
  same rules.
- "RPITIT" = return-position `impl Trait` in traits; "AFIT" = `async fn` in traits.

## MSRV guidance

- Libraries: support at least the last few stable releases and state `rust-version`; CI should build on it
  (`cargo +<msrv> check` or `cargo msrv verify`).
- `async fn` in public traits (1.75) is fine for most libraries now; pair it with a `Send` story.
- Trait upcasting (1.86) and `get_disjoint_mut` (1.86) are recent: offer the pre-1.86 workaround if the MSRV is
  older.
- Edition 2024 requires Rust 1.85; migrating changes RPIT capture behaviour, so run `cargo fix --edition` and
  review `use<..>` suggestions on public functions.
