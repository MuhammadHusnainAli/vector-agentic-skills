# Semver and Evolution of Traits and Impls

Which changes to traits, impls and public types break downstream code, following the Cargo book's SemVer
compatibility chapter and RFC 1105 (API evolution). "Major" means a new major version (or a new minor
version below 1.0); "possibly breaking" means it can break some callers in practice, usually through name
collisions or type inference, and is conventionally allowed in a minor release.

## Contents

- [Trait changes](#trait-changes)
- [Impl changes](#impl-changes)
- [Generic bounds and parameters](#generic-bounds-and-parameters)
- [Public types](#public-types)
- [Auto traits leak](#auto-traits-leak)
- [Designing for evolution](#designing-for-evolution)
- [Checking before release](#checking-before-release)

## Trait changes

| Change | Impact | Why |
|--------|--------|-----|
| Add a method **without** a default | major | every downstream implementor fails to compile |
| Add a method **with** a default | possibly breaking | calls may become ambiguous with a same-named method from another trait in scope |
| Add a method that makes the trait dyn-incompatible | major | `dyn Trait` users fail (E0038); add `where Self: Sized` to keep it out of the vtable |
| Change a method signature (params, return, receiver, generics) | major | implementors and callers both break |
| Add an associated type | major | implementors must define it (associated type defaults are unstable) |
| Add an associated const without a default | major | implementors must define it |
| Add a defaulted type parameter to the trait (`trait T<X = ()>`) | minor | existing uses keep the default |
| Add a supertrait | major | implementors may not implement the new supertrait |
| Remove a supertrait | major | callers relying on supertrait methods through the bound break |
| Any change to a **sealed** trait's items | minor (for items callers do not call) | nobody outside the crate implements it |

Seal traits that users only consume, so you can add required methods later. Leave traits open only when
downstream implementations are the point (plugins, backends, codecs).

## Impl changes

| Change | Impact | Notes |
|--------|--------|-------|
| Remove a trait impl | major | callers using the impl break |
| Add an impl of an existing trait for an existing type | minor, possibly breaking | can break inference: adding `impl From<u16> for Id` makes `x.into()` ambiguous where it was not |
| Add a **blanket** impl (`impl<T: Bound> Trait for T`) of an existing trait | major | can overlap with downstream impls (E0119 in their code) |
| Add inherent methods | possibly breaking | an inherent method shadows a trait method of the same name callers were using |
| Implement a foreign trait for a local type | minor | coherence keeps it yours |

## Generic bounds and parameters

| Change | Impact |
|--------|--------|
| Tighten a bound (`T: Clone` -> `T: Clone + Send`) on a fn, type or impl | major |
| Loosen a bound | minor |
| Add a type parameter with a default to a type | minor |
| Add a type parameter to a fn | possibly breaking (callers using turbofish break) |
| Replace a concrete parameter type with a generic that still accepts it (`&str` -> `impl AsRef<str>`) | minor, possibly breaking (inference) |
| Change `impl Trait` in return position to another concrete type | minor (opaque), unless auto traits change (below) |

## Public types

| Change | Impact |
|--------|--------|
| Add a variant to an exhaustive `pub enum` | major (exhaustive matches break) |
| Add a variant to a `#[non_exhaustive]` enum | minor |
| Add `#[non_exhaustive]` to an existing enum/struct | major |
| Add a public field to a struct with only public fields | major (struct literals and patterns break) |
| Add a private field when one already exists | minor |
| Add a field to a `#[non_exhaustive]` struct | minor |
| Remove a derive (`Debug`, `Clone`, `Hash`...) | major |
| Add a derive | minor |
| Change `#[repr]` or layout of a `repr(C)` type | major |

`#[non_exhaustive]` on public error enums and config structs (built through constructors or builders) keeps
future additions minor. Callers must then write `_ =>` arms and cannot use struct literals.

## Auto traits leak

`Send`, `Sync`, `Unpin`, `UnwindSafe` and `RefUnwindSafe` are inferred from fields and from the concrete type
behind `impl Trait`. They are part of your public API even though you never wrote them:

- Adding an `Rc`, `RefCell`, raw pointer or `!Send` guard field to a public struct removes `Send`/`Sync`:
  **major**.
- Changing what an `-> impl Future` returns so it holds a `!Send` value across an `.await` removes `Send` from
  the opaque type: **major** for callers who spawned it.
- Guard against accidents with compile-time assertions (see testing-trait-designs.md):

```rust
pub struct Client { inner: std::sync::Arc<std::sync::Mutex<Vec<u8>>> }

const _: () = {
    const fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<Client>();
};
```

## Designing for evolution

1. **Seal** consumer-only traits (`pub trait Codec: private::Sealed`).
2. Give new trait methods **defaults**, and prefer names unlikely to collide.
3. Put constructors and generic helpers behind `where Self: Sized` so the trait stays dyn-compatible as it
   grows.
4. Mark error enums and option structs `#[non_exhaustive]` from the first release.
5. Return **opaque** types (`impl Iterator`, newtypes) instead of concrete std/foreign types, so the
   implementation can change.
6. Keep foreign types out of public signatures when they have their own semver (a `reqwest::Error` in your
   API ties your major version to theirs); wrap them.
7. Implement `From` (not `Into`) and keep the set of `From` impls deliberate: each one is a commitment and a
   possible inference hazard.

## Checking before release

- `cargo semver-checks` compares the public API against the last published version and reports many of the
  breaking changes above (removed items, new required trait items, enum variants, auto-trait changes).
- `cargo public-api diff` (nightly rustdoc JSON) shows the full public surface change.
- Run downstream crates' test suites (crater-style) for widely used libraries.
- Write the change into `CHANGELOG.md` with its classification.
