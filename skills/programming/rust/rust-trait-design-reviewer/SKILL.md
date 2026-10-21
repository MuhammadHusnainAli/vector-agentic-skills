---
name: rust-trait-design-reviewer
description: "Review and design Rust traits and generic APIs: generics vs impl Trait vs dyn Trait (static vs dynamic dispatch), dyn compatibility / object safety (generic methods, Self returns, where Self: Sized, error[E0038] not dyn compatible / cannot be made into an object), associated types vs generic parameters, blanket impls, coherence and orphan rule (E0117, E0119, E0210), newtype, extension, sealed and marker traits, supertraits and trait upcasting (1.86), async fn in traits (1.75) and the Send bound problem (trait_variant, async-trait), RPITIT, GATs, From/Into/TryFrom/AsRef/Borrow, std trait checklist (Debug, Clone, PartialEq, Hash, Default, Display, Error, Send/Sync, serde feature), #[must_use], #[non_exhaustive], semver hazards, Deref abuse, builders, typestate, PhantomData, Box<dyn Error + Send + Sync>, Fn traits, mockall. Use when designing a public Rust trait or API, reviewing a PR adding traits/impls, or fixing E0038, E0117, E0119, E0210, E0277, E0599 or 'future cannot be sent between threads safely'."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Trait Design Reviewer

Design traits that are easy to implement, hard to misuse and safe to evolve, and review existing trait-heavy
code against the Rust API Guidelines. Every decision is a trade-off between three axes: dispatch (generics
vs `impl Trait` vs `dyn Trait`), extensibility (who may implement the trait: anyone, nobody outside the crate,
or only via a blanket impl) and evolution (which later changes are semver-major). Small std-only Rust programs
in `scripts/` scan source text for the mistakes that are cheap to catch mechanically (dyn-incompatible traits
used as `dyn`, `impl Into`, missing Debug/Error impls, Deref inheritance, non-Send `Box<dyn Error>`, `&Vec<T>`
parameters, unsendable public `async fn` traits), and `scaffold_trait` prints compiling templates for sealed,
extension, typestate, newtype, dyn-compatible and async-Send traits.

## Trigger Conditions

Activate this skill when the user:
- Designs a public trait, a plugin/strategy/backend abstraction or a generic library API in Rust
- Asks "generics or `dyn`?", "`impl Trait` or `T: Trait`?", "associated type or generic parameter?"
- Hits `error[E0038]: the trait X is not dyn compatible` / `cannot be made into an object`, E0117 / E0210
  (orphan rule), E0119 (conflicting implementations), E0277 (trait bound not satisfied), E0599 (method exists
  but trait bounds not satisfied / trait not in scope), E0191 (associated type must be specified), E0225
- Uses `async fn` in a trait and sees `future cannot be sent between threads safely` or the
  `async_fn_in_trait` warning, or needs `dyn` with async methods
- Reviews a PR adding traits, blanket impls, `Deref`, `From`/`Into`, error types or builder APIs
- Wants to seal a trait, add an extension trait, a newtype, a typestate builder or a mockable trait
- Asks which std traits a public type should implement, or whether a change is semver-breaking

## Workflow

```
0. BUILD     -> once: for t in dyn_compat trait_shape api_traits api_signatures scaffold_trait; do
                  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
1. SCAN      -> for t in dyn_compat trait_shape api_traits api_signatures; do /tmp/$t src/; done
                (whole crate: impls and `dyn` uses in other files count)
2. CLASSIFY  -> For each trait: who calls it (generic code, dyn, both)? who implements it (us, users, tests)?
                Use the dispatch and extensibility tables below.
3. CHECK     -> dyn compatibility, coherence (could a user or upstream crate write a conflicting impl?),
                Send/Sync story, std trait checklist for every public type, semver surface
4. FIX       -> Smallest change that keeps call sites compiling: `where Self: Sized`, From instead of Into,
                derive Debug, thiserror, &[T] instead of &Vec<T>, seal before 1.0
                Templates: /tmp/scaffold_trait sealed --name Backend
5. VERIFY    -> cargo check && cargo clippy -- -W clippy::pedantic; cargo test (incl. compile_fail doctests);
                cargo semver-checks for published crates; each scanner with --strict exits 1 on findings
```

## Dispatch: Generics vs `impl Trait` vs `dyn Trait`

| Need | Use | Cost / limit |
|------|-----|--------------|
| Fastest call, inlining, caller picks the type | `fn f<T: Trait>(x: T)` | one copy per type (code size, compile time); callers can turbofish `f::<u8>` |
| Same, simpler signature | `fn f(x: impl Trait)` | identical codegen; no turbofish for that parameter |
| Return one concrete unnamed type (closures, iterators) | `fn f() -> impl Iterator<Item = u32>` | one hidden type per function; auto traits (Send) leak from the body |
| Heterogeneous collection, plugin registry, runtime choice | `Vec<Box<dyn Trait>>`, `&dyn Trait`, `Arc<dyn Trait + Send + Sync>` | vtable call, no inlining, trait must be dyn compatible |
| Reduce monomorphization bloat of a big generic fn | generic shell + non-generic inner fn taking `&dyn`/`&Path` | one extra call |
| Heterogeneous but closed set of types | `enum` with one variant per type | no vtable, exhaustive `match`; adding a type = editing the enum |

```rust
use std::fmt::Display;
use std::path::Path;

pub fn join_all<T: Display>(items: &[T]) -> String {
    items.iter().map(ToString::to_string).collect::<Vec<_>>().join(", ")
}

pub fn bracket(item: impl Display) -> String {
    format!("[{item}]")
}

pub fn join_mixed(items: &[&dyn Display]) -> String {
    items.iter().map(|i| i.to_string()).collect::<Vec<_>>().join(", ")
}

// Generic shell, non-generic body: only the tiny shell is monomorphized (std::fs::read does this).
pub fn line_count<P: AsRef<Path>>(path: P) -> std::io::Result<usize> {
    fn inner(path: &Path) -> std::io::Result<usize> {
        Ok(std::fs::read_to_string(path)?.lines().count())
    }
    inner(path.as_ref())
}

fn main() {
    let mixed: [&dyn Display; 3] = [&1, &"two", &3.5];
    println!("{} | {} | {}", join_all(&[1, 2, 3]), bracket("x"), join_mixed(&mixed));
}
```

## Dyn Compatibility (Object Safety)

A trait can be used as `dyn Trait` only if every method can be called through a vtable. Methods that cannot
must opt out with `where Self: Sized` (they are then callable on concrete types only).

| Breaks `dyn` (E0038) | Fix |
|----------------------|-----|
| `trait T: Sized`, or supertrait `Clone`, `Default`, `Copy`, `FromStr` (all require Sized) | drop the supertrait; for Clone add `fn box_clone(&self) -> Box<dyn T>` (or the `dyn-clone` crate) |
| supertrait `PartialEq`/`Eq`/`PartialOrd`/`Ord` (they use `Self` as a type parameter) | compare via a method returning a key, or downcast with `Any` |
| generic method `fn put<V: Serialize>(&mut self, v: &V)` or `impl Trait` argument | `where Self: Sized`, or a dyn-friendly variant taking `&dyn Erased`/bytes |
| `Self` in argument or return type: `fn merge(&self, other: Self)`, `fn dup(&self) -> Self` | `where Self: Sized`, or return `Box<dyn T>` |
| associated function without receiver: `fn new() -> Self` | `where Self: Sized` |
| `async fn` / `-> impl Trait` method (RPITIT) | `#[async_trait]`, or return `Pin<Box<dyn Future<Output = T> + Send + '_>>` / `Box<dyn Iterator>` |
| associated `const`, or generic associated type `type Item<'a>` | move the const to a method; split the GAT into a separate trait |

Allowed: lifetime parameters on methods, trait-level generic parameters (`dyn Codec<u32>`), associated types
(must be named: `dyn Iterator<Item = u8>`, else E0191), receivers `&self`, `&mut self`, `self: Box<Self>`,
`Rc<Self>`, `Arc<Self>`, `Pin<&mut Self>`. Only auto traits may be added: `dyn Read + Send` works,
`dyn Read + Write` is E0225 (make `trait ReadWrite: Read + Write {}` with a blanket impl).

```rust
use std::fmt::Debug;

pub trait Storage: Debug + Send + Sync {
    fn get(&self, key: &str) -> Option<Vec<u8>>;
    fn put_bytes(&mut self, key: &str, value: &[u8]);

    fn open(path: &str) -> std::io::Result<Self>
    where
        Self: Sized;

    fn put_all<I: IntoIterator<Item = (String, Vec<u8>)>>(&mut self, items: I)
    where
        Self: Sized,
    {
        for (k, v) in items {
            self.put_bytes(&k, &v);
        }
    }
}

#[derive(Debug, Default)]
pub struct Memory(std::collections::HashMap<String, Vec<u8>>);

impl Storage for Memory {
    fn get(&self, key: &str) -> Option<Vec<u8>> {
        self.0.get(key).cloned()
    }
    fn put_bytes(&mut self, key: &str, value: &[u8]) {
        self.0.insert(key.to_owned(), value.to_vec());
    }
    fn open(_path: &str) -> std::io::Result<Self> {
        Ok(Self::default())
    }
}

fn main() {
    let mut store: Box<dyn Storage> = Box::new(Memory::open("mem").unwrap());
    store.put_bytes("k", b"v");
    assert_eq!(store.get("k").as_deref(), Some(&b"v"[..]));
}
```

**Trait upcasting (Rust 1.86):** `&dyn Sub` coerces to `&dyn Super` (also `Box`, `Arc`) when
`trait Sub: Super`. With `trait Plugin: Any`, `let any: &dyn Any = plugin;` then `any.downcast_ref::<T>()`
works without an `as_any()` helper. Before 1.86 add `fn as_any(&self) -> &dyn Any`.

## Associated Types vs Generic Parameters

| Question | Associated type `type Output;` | Generic parameter `Trait<T>` |
|----------|-------------------------------|------------------------------|
| How many impls per implementing type? | exactly one (`Iterator::Item`, `Deref::Target`) | many (`From<T>`, `Add<Rhs>`, `AsRef<T>`) |
| Who chooses? | the implementor | the caller / the impl list |
| Inference | always determined by `Self` | may need annotations (E0283 type annotations needed) |
| In `dyn` | must be specified: `dyn Iterator<Item = u8>` | part of the type: `dyn Codec<u8>` |

Rule: use an associated type when the type is an output determined by `Self`; use a generic parameter (with
a default, `trait Add<Rhs = Self>`) when the same type sensibly implements the trait several times.
Associated type bounds `T: Iterator<Item: Display>` are stable since 1.79.

## Who May Implement It: Extensibility Patterns

| Pattern | Shape | Use when |
|---------|-------|----------|
| Open trait | `pub trait Codec { .. }` | users must plug in their own types (serde, tower `Service`) |
| Sealed trait | `pub trait Codec: private::Sealed` | users call it, only you implement it: free to add methods in minor releases (C-SEALED) |
| Extension trait | `pub trait StrExt { .. } impl StrExt for str` | add methods to a foreign type (`itertools::Itertools`, `futures::StreamExt`) |
| Blanket-impl'd alias | `trait ReadWrite: Read + Write {} impl<T: Read + Write> ReadWrite for T {}` | name a bound combination; users can never impl it manually (E0119) |
| Marker trait | `pub trait Pod: Copy + 'static {}` (often `unsafe trait`) | encode a property; `unsafe trait` when wrong impls cause UB |
| Newtype | `pub struct Meters(f64);` | implement foreign traits for foreign types (orphan rule), add invariants, hide representation (C-NEWTYPE) |

```rust
mod private {
    pub trait Sealed {}
}

/// Implemented for `Json` and `Toml` only; new methods are not breaking changes.
pub trait Format: private::Sealed {
    fn extension(&self) -> &'static str;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
pub struct Json;

impl private::Sealed for Json {}
impl Format for Json {
    fn extension(&self) -> &'static str {
        "json"
    }
}
```

Coherence in one paragraph: `impl ForeignTrait for ForeignType` is E0117; `impl<T> ForeignTrait for T` is
E0210 (uncovered type parameter); a local type must appear before any uncovered type parameter, so
`impl<T> From<Local> for Vec<T>` and `impl Mul<Vec2> for f64` are fine (Rust 1.41+). `&T`, `&mut T`, `Box<T>`
and `Pin<T>` are fundamental: `impl Display for Box<Local>` is allowed. Two impls that could overlap for some
type are E0119, including "upstream crates may add a new impl" cases. Details and fixes:
[coherence-and-trait-patterns.md](references/coherence-and-trait-patterns.md).

## `async fn` in Traits (Rust 1.75+)

| Situation | Choose |
|-----------|--------|
| Private/internal trait, single-threaded or concrete types | plain `async fn` |
| Public trait, generic callers spawn on a multi-threaded runtime | `#[trait_variant::make(Name: Send)]`, or write `fn f(&self) -> impl Future<Output = T> + Send` |
| Need `dyn Trait` with async methods | `#[async_trait::async_trait]` (boxes every call; `Send` by default, `?Send` to opt out) or hand-written `Pin<Box<dyn Future + Send + '_>>` |
| Caller wants to require `Send` on one method's future | return-type notation `T: Trait<method(..): Send>` is not stable as of this writing; use a Send variant |

```rust,ignore
// Cargo.toml: trait-variant = "0.1"
#[trait_variant::make(Fetcher: Send)]
pub trait LocalFetcher {
    async fn fetch(&self, url: &str) -> Result<String, std::io::Error>;
}
// `Fetcher` is generated: same method, future is `+ Send`; impl Fetcher for your type and use
// `F: Fetcher + Clone + 'static` in code that tokio::spawn()s.
```

## Core Rules

- Implement `From`, never `Into` (Into comes from a blanket impl and `?` uses From); `TryFrom` for fallible
  conversions; `AsRef<T>` for cheap reference views; `Borrow<T>` only when Eq/Hash/Ord agree (map keys).
- Every public type: `Debug` (C-DEBUG). Then eagerly: `Clone`, `Copy` (small plain data only, removing it later
  is breaking), `PartialEq`/`Eq`, `Hash`, `PartialOrd`/`Ord` (when meaningful), `Default`, `Display` (user
  facing text), `Send + Sync` (check, do not assume), `serde` behind a `serde` cargo feature (C-SERDE).
- Error types: an enum or struct with `Display + Error + Send + Sync + 'static`, `#[non_exhaustive]`, `source()`
  wired (thiserror does all of it). Dynamic errors are `Box<dyn Error + Send + Sync + 'static>`.
- Accept borrowed, general inputs (`&[T]`, `&str`, `&Path`, `impl AsRef<Path>`, `impl IntoIterator`); return
  owned, concrete outputs. Take `R: Read`/`W: Write` by value (C-RW-VALUE; `&mut R` also implements them).
- Bounds go on impls and functions, not on struct definitions (C-STRUCT-BOUNDS), except where the type's
  Drop or layout needs them.
- `Deref` only for smart pointers and transparent wrappers (C-DEREF); never to fake inheritance.
- Operators only with their mathematical meaning (C-OVERLOAD); implement the `&a + &b` forms for non-Copy types.
- `#[must_use]` on builders and on functions whose only effect is their return value; `#[non_exhaustive]`
  on public enums/structs you expect to grow.
- Callbacks: accept the weakest Fn trait you can (`FnOnce` > `FnMut` > `Fn` for caller freedom); store
  `Box<dyn Fn(..) + Send + Sync>`; async callbacks: `AsyncFn` traits (1.85+) or `Fn() -> Fut`.
- A trait with one implementor and no dyn/test use is indirection: start concrete, extract a trait later.
- Seal or `#[doc(hidden)]` anything you are not ready to promise; adding a required method to an open trait
  is a major release.

More: [std-traits-and-api-guidelines.md](references/std-traits-and-api-guidelines.md),
[semver-and-evolution.md](references/semver-and-evolution.md).

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| `E0038 the trait X is not dyn compatible` | generic method, `Self` in signature, no receiver, async fn, Sized/Clone supertrait (TR001) | `where Self: Sized` on those methods, `box_clone`, `#[async_trait]` |
| `E0117 only traits defined in the current crate can be implemented for types defined outside` | foreign trait for foreign type | newtype wrapper, or implement a local trait |
| `E0210 type parameter T must be used as the type parameter for some local type` | `impl<T> Display for T` / `impl<T> From<Local> for T` | blanket impl a local trait, or impl for the concrete local types |
| `E0119 conflicting implementations` | overlapping blanket impls, or `impl<T> From<T> for Wrapper<T>` vs core's `impl<T> From<T> for T` | narrow the blanket impl, use a newtype or a named constructor |
| `E0599 no method named x found` / `method exists but trait bounds were not satisfied` | trait not in scope, or a bound on the impl block is unmet | `use crate::Ext;`, add the bound to the caller, check derives (Clone/Debug on T) |
| `E0277 the trait bound T: Send is not satisfied` / `future cannot be sent between threads safely` | `Rc`/`RefCell`/`MutexGuard` held across `.await`, or AFIT future not Send (TR008) | Send variant (`trait_variant`), `Arc`/`Mutex`, drop guards before `.await` |
| `E0191 the value of the associated type Item must be specified` | `dyn Iterator` without `Item = ..` | `dyn Iterator<Item = T>` |
| `E0225 only auto traits can be used as additional traits in a trait object` | `dyn Read + Write` | supertrait alias with blanket impl |
| `E0283 type annotations needed` | generic param inferred from nothing (`.into()` with many From impls) | turbofish / annotate, or associated type instead of parameter |
| `E0392 parameter T is never used` | typestate / marker parameter | `PhantomData<T>` (or `PhantomData<fn() -> T>` to stay Send/Sync and avoid drop-check) |
| `E0204 the trait Copy cannot be implemented for this type` | a field is not Copy | derive Clone only, or make the field Copy |
| `E0782 trait objects must include the dyn keyword` (edition 2021+) | bare `Box<Trait>` | `Box<dyn Trait>` |
| `?` does not convert into your error | only `impl Into<MyError> for E` written (TR002) | `impl From<E> for MyError` or `#[from]` |
| `{:?}` fails on a user's struct holding your type | your public type lacks Debug (TR003) | derive or hand-write a redacting Debug |
| `Box<dyn Error>` result cannot go into `tokio::spawn` / anyhow | missing `Send + Sync` (TR009) | `Box<dyn Error + Send + Sync + 'static>` |
| method on wrapper silently calls the inner type's method | `Deref` used as inheritance (TR005) | explicit delegation or a shared trait |

## Output Format

When reviewing, answer with:
1. **Summary** - one paragraph: what the abstraction is for, who implements it, who calls it, and the verdict.
2. **Findings** - ordered by severity; each with file:line, rule id (TRxxx when the script flags it, or the
   API guideline id such as C-DEBUG), why it matters for users or semver, and the concrete fix.
3. **Design decisions** - dispatch choice, extensibility (open/sealed/extension), Send/Sync story, error type,
   each with the alternative considered and why it lost.
4. **Code** - complete corrected trait + one impl + one call site (generic and/or dyn) that compiles on the
   stated MSRV; mark features needing a newer compiler (AFIT 1.75, upcasting 1.86, AsyncFn 1.85).
5. **Verification** - `cargo check`, `cargo clippy`, the test that pins the property (e.g. a `dyn` usage or
   `assert_send` test, a compile_fail doctest), `cargo semver-checks` for published crates.

When designing from scratch, lead with the trait definition and a table of decisions, then the code.

## Scripts

Small, standard-library-only Rust programs that read source text (no Cargo project, never compile your code).
Build each once with `rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>`.

| Script | Rules | Job |
|--------|-------|-----|
| `scripts/dyn_compat.rs` | TR001, TR008 | traits used as `dyn` that break dyn compatibility (with every reason); public `async fn` traits without a Send story |
| `scripts/trait_shape.rs` | TR002, TR005, TR006, TR007 | `impl Into`, Deref-as-inheritance, fat traits (`--max-methods`, default 8), private single-impl traits |
| `scripts/api_traits.rs` | TR003, TR004, TR011, TR012, TR014 | std traits public types should have: Debug, Display + Error, Hash/PartialEq consistency, Default, `#[non_exhaustive]` errors |
| `scripts/api_signatures.rs` | TR009, TR010, TR013 | `Box<dyn Error>` without Send + Sync, `&Vec<T>`/`&String`/`&PathBuf` params, builders without `#[must_use]` |
| `scripts/scaffold_trait.rs` | - | templates: sealed, extension, typestate, newtype, dyn-compatible, async-send (each compiles and passes the scanners) |
| `scripts/rsparse.rs`, `scripts/cli.rs` | - | shared modules: source scanner (traits, impls, attributes, test modules) and options/report |

```bash
/tmp/dyn_compat src/                                   # files and/or directories (skips target/, .git/)
/tmp/api_traits src/lib.rs --json                      # machine-readable findings with fix
cat src/lib.rs | /tmp/api_signatures -                 # stdin
/tmp/trait_shape src/ --strict --max-methods 6         # exit 1 on any finding (CI gate)
/tmp/api_traits src/ --select TR003,TR004 --ignore TR012
/tmp/dyn_compat --list-rules                           # each scanner lists its rules with why and fix
/tmp/scaffold_trait typestate --name Request           # also: sealed extension newtype dyn-compatible async-send
```

| Rule | Name | Severity | Flags |
|------|------|----------|-------|
| TR001 | dyn-incompatible-trait | high | trait used as `dyn` with receiver-less, generic, `impl Trait`-taking, Self-using or async methods, consts, GATs or a Sized supertrait |
| TR002 | impl-into-not-from | medium | `impl Into<X> for Y`, `impl TryInto` |
| TR003 | missing-debug | medium | `pub` struct/enum with no Debug derive or impl in the scanned files |
| TR004 | error-without-error-impl | high | `pub` `*Error` type lacking Display and/or `std::error::Error` (thiserror/snafu derives count) |
| TR005 | deref-inheritance | medium | `Deref<Target = LocalStruct>` on a multi-field struct |
| TR006 | fat-trait | low | public trait with more than `--max-methods` (default 8) required methods |
| TR007 | single-impl-trait | low | private trait, one impl for a local type, never `dyn` or a bound |
| TR008 | async-fn-public-trait | medium | `async fn` in a `pub` trait without `trait_variant`/`async_trait` |
| TR009 | box-dyn-error-not-send | medium | `Box<dyn Error>` without `Send` in fns and type aliases (not `fn main`, not trait impls) |
| TR010 | borrowed-owned-param | low | `&Vec<T>`, `&String`, `&Box<T>`, `&PathBuf`, `&OsString` parameters (not in trait impls) |
| TR011 | hash-with-manual-eq | medium | `#[derive(Hash)]` plus hand-written `PartialEq` |
| TR012 | new-without-default | low | `pub fn new() -> Self` with no args and no Default |
| TR013 | builder-missing-must-use | low | `pub fn x(self, ..) -> Self` methods without `#[must_use]` (method or type) |
| TR014 | error-enum-exhaustive | low | `pub enum *Error` without `#[non_exhaustive]` |

Scan the whole crate: impls in other files satisfy TR003/TR004 and `dyn` uses anywhere trigger TR001.
`#[cfg(test)]` modules are skipped by the hygiene rules; silence a line with `// noqa` or `// noqa: TR010`.
These are heuristic scanners, not rustc: macros, `cfg` variants and re-exports are invisible. Exit codes: 0
clean (or findings without `--strict`), 1 findings with `--strict`, 2 usage error or unreadable file.

## Additional Resources

| File | Content |
|------|---------|
| [dispatch-and-dyn-compatibility.md](references/dispatch-and-dyn-compatibility.md) | Generics vs impl Trait vs dyn, vtables, code size, every dyn-compatibility rule with E0038 fixes, upcasting, Any, dyn lifetimes |
| [coherence-and-trait-patterns.md](references/coherence-and-trait-patterns.md) | Orphan rule (E0117/E0210), overlap (E0119), blanket impls, newtype, extension, sealed, marker and auto traits, supertraits, default methods, ?Sized, PhantomData |
| [async-and-advanced-generics.md](references/async-and-advanced-generics.md) | async fn in traits, the Send problem, trait_variant, async-trait, RPITIT, GATs, HRTB, Fn/AsyncFn traits, associated types vs params |
| [std-traits-and-api-guidelines.md](references/std-traits-and-api-guidelines.md) | Std trait checklist, From/Into/TryFrom/AsRef/Borrow, Display and Error, serde feature, Iterator/IntoIterator, operators, Deref, builders, typestate, must_use |
| [semver-and-evolution.md](references/semver-and-evolution.md) | Which trait/impl changes are major, minor or possibly-breaking; sealing, non_exhaustive, auto-trait leakage, cargo-semver-checks |
| [testing-trait-designs.md](references/testing-trait-designs.md) | Hand-written fakes, mockall, compile_fail doctests, trybuild, Send/Sync and dyn assertions, property tests for trait laws |
| [version-history.md](references/version-history.md) | Trait-related stabilisations by Rust version and edition, with MSRV guidance |
