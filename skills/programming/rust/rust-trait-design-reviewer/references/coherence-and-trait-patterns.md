# Coherence and Trait Patterns

Coherence guarantees that for any type and trait there is at most one impl, anywhere in the dependency graph.
The orphan rule and the overlap check enforce it, and they shape every extensibility pattern: newtypes,
extension traits, sealed traits, blanket impls and marker traits.

## Contents

- [The orphan rule](#the-orphan-rule)
- [Overlap: E0119](#overlap-e0119)
- [Blanket impls](#blanket-impls)
- [Newtype pattern](#newtype-pattern)
- [Extension traits](#extension-traits)
- [Sealed traits](#sealed-traits)
- [Marker traits and unsafe traits](#marker-traits-and-unsafe-traits)
- [Auto traits: Send, Sync, Unpin](#auto-traits-send-sync-unpin)
- [Supertraits](#supertraits)
- [Default methods and the required core](#default-methods-and-the-required-core)
- [?Sized and forwarding impls](#sized-and-forwarding-impls)
- [PhantomData](#phantomdata)
- [Review checklist](#review-checklist)

## The orphan rule

For `impl<P1..Pn> Trait<T1..Tn> for T0` where `Trait` is defined in another crate, the impl is allowed only if:

1. at least one of `T0..Tn` is a local type, and
2. no uncovered type parameter (`P` appearing bare, not inside another type) appears before the first local type.

`&T`, `&mut T`, `Box<T>` and `Pin<T>` are *fundamental*: `Box<Local>` counts as local.

| Impl | Result | Why |
|------|--------|-----|
| `impl Display for Local` | ok | local self type |
| `impl Display for Vec<u8>` | error[E0117] | foreign trait, foreign type |
| `impl Display for Vec<Local>` | error[E0117] | `Vec` is not fundamental; `Vec<Local>` is foreign |
| `impl Display for Box<Local>` / `&Local` | ok | fundamental wrapper of a local type |
| `impl<T> Display for T` | error[E0210] | uncovered `T` |
| `impl<T> From<Local> for T` | error[E0210] | uncovered `T` before the local `T1` |
| `impl<T> From<Local> for Vec<T>` | ok (1.41+) | `T` is covered by `Vec`, `Local` is `T1` |
| `impl From<Local> for String` | ok (1.41+) | `T1` is local |
| `impl Mul<Vec2> for f64` | ok | `T1` is local, `f64` has no type parameters |
| `impl Trait for Foreign` where `Trait` is local | ok | local trait |

Rust 1.41 relaxed these rules (RFC 2451). That is why the old advice "implement Into when you cannot implement
From" no longer applies: `impl From<Local> for ForeignType` is accepted.

The error messages:

```text
error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate
error[E0210]: type parameter `T` must be used as the type parameter for some local type (e.g., `MyStruct<T>`)
```

Fixes: wrap the foreign type in a newtype, implement a local trait instead, or put the impl in the crate that
owns the trait or the type (upstream PR, or a feature-gated impl in your own crate).

## Overlap: E0119

Two impls overlap if some type could satisfy both. The compiler also assumes upstream crates may add impls in
future versions, so negative reasoning about foreign types is not allowed:

```rust,compile_fail
use std::fmt::Display;

trait Describe {
    fn describe(&self) -> String;
}

impl<T: Display> Describe for T {
    fn describe(&self) -> String {
        format!("display: {self}")
    }
}

// error[E0119]: conflicting implementations of trait `Describe` for type `Vec<u8>`
// note: upstream crates may add a new impl of trait `std::fmt::Display` for type `std::vec::Vec<u8>`
impl Describe for Vec<u8> {
    fn describe(&self) -> String {
        format!("{} bytes", self.len())
    }
}
```

For a *local* type that does not implement `Display`, the second impl is accepted: only your crate could add
`impl Display for Local`, and doing so later would then fail to compile in your crate, not in a dependent.

Two blanket impls with different bounds always overlap, because one type can satisfy both bounds:

```rust,compile_fail
use std::fmt::{Debug, Display};

trait Render {
    fn render(&self) -> String;
}

impl<T: Display> Render for T {
    fn render(&self) -> String {
        format!("{self}")
    }
}

// error[E0119]: conflicting implementations of trait `Render`
impl<T: Debug> Render for T {
    fn render(&self) -> String {
        format!("{self:?}")
    }
}
```

Pick one blanket impl and implement the rest per type, or use two traits, or a wrapper type
(`struct ViaDebug<T>(T)`) that selects the behaviour. Be equally careful with generic `From` impls on your own
types (`impl<T: SomeBound> From<T> for MyType`): they easily collide with core's reflexive
`impl<T> From<T> for T` or with each other; concrete `From<&str>` / `From<String>` impls or a named
constructor (`MyType::new(impl Into<String>)`) avoid the problem.

Specialization (choosing the "more specific" impl) is unstable; do not design around it.

## Blanket impls

A blanket impl implements a trait for every type matching a bound: `impl<T: Display + ?Sized> ToString for T`.

```rust
use std::fmt::Display;

pub trait Shout {
    fn shout(&self) -> String;
}

impl<T: Display + ?Sized> Shout for T {
    fn shout(&self) -> String {
        self.to_string().to_uppercase()
    }
}

fn main() {
    assert_eq!("hi".shout(), "HI");
    assert_eq!(42_i32.shout(), "42");
}
```

Consequences to weigh:

- Nobody can write a more specific impl for a type covered by the bound (E0119), including you later.
- Adding a blanket impl to an existing public trait is a breaking change: downstream impls for covered types
  stop compiling.
- Blanket impls over `&T`, `&mut T`, `Box<T>` (forwarding impls, see below) are expected and cheap.
- A blanket impl of a *foreign* trait for all `T` is impossible (E0210).
- Combine with a supertrait to make a "trait alias": `pub trait Service: Handler + Send + Sync + 'static {}`
  plus `impl<T: Handler + Send + Sync + 'static> Service for T {}`.

## Newtype pattern

A tuple struct with one field: zero runtime cost, a new type for coherence and invariants.

```rust
use std::fmt;

/// Implement a foreign trait (Display) for a foreign type (Vec<String>) via a local wrapper.
pub struct CommaList(pub Vec<String>);

impl fmt::Display for CommaList {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0.join(", "))
    }
}

/// Encode an invariant: never empty, at most 32 bytes.
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Tag(String);

impl Tag {
    pub fn new(s: impl Into<String>) -> Option<Self> {
        let s = s.into();
        (!s.is_empty() && s.len() <= 32).then_some(Tag(s))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

fn main() {
    assert_eq!(CommaList(vec!["a".into(), "b".into()]).to_string(), "a, b");
    assert!(Tag::new("").is_none());
    assert_eq!(Tag::new("rust").unwrap().as_str(), "rust");
}
```

Guidelines:
- Keep the field private when there is an invariant (C-NEWTYPE-HIDE); expose `as_str`/`as_ref`, `into_inner`.
- Derive the traits the inner type has that still make sense; do not blindly `Deref` to the inner type
  (that leaks the whole inner API and bypasses invariants for `&mut` access via `DerefMut`).
- `#[repr(transparent)]` guarantees the same layout as the field (needed for FFI or sound pointer casts).
- Units and IDs as newtypes (`UserId(u64)`, `Meters(f64)`) prevent argument mix-ups (C-NEWTYPE).

## Extension traits

Add methods to a type you do not own. Convention: name it `<Type>Ext` and implement it for the foreign type
(often via a blanket impl):

```rust
pub trait ResultExt<T> {
    /// Log the error and turn the result into an Option.
    fn log_err(self, context: &str) -> Option<T>;
}

impl<T, E: std::fmt::Display> ResultExt<T> for Result<T, E> {
    fn log_err(self, context: &str) -> Option<T> {
        match self {
            Ok(v) => Some(v),
            Err(e) => {
                eprintln!("{context}: {e}");
                None
            }
        }
    }
}

fn main() {
    let r: Result<u8, String> = Err("boom".into());
    assert_eq!(r.log_err("parse"), None);
}
```

- Callers must import the trait (`use mycrate::ResultExt;`); a missing import is error[E0599] with the hint
  "trait `ResultExt` which provides `log_err` is implemented but not in scope". Re-export extension traits from
  a `prelude` module.
- Method names can collide with inherent methods added to the foreign type later: inherent methods win
  silently. Prefer distinctive names (`log_err`, not `ok`).
- Extension traits are the idiomatic way to add combinators to traits you also define:
  `futures::StreamExt` over `Stream`, `itertools::Itertools` over `Iterator`.

## Sealed traits

Public trait, private implementability. Downstream crates can name it, use it as a bound and call its
methods, but cannot implement it, so you can add methods (even required ones) without a major release
(C-SEALED).

```rust
mod sealed {
    pub trait Sealed {}
    impl Sealed for u32 {}
    impl Sealed for u64 {}
}

/// Integer types this crate can encode. Not implementable outside this crate.
pub trait Varint: sealed::Sealed + Copy {
    fn encoded_len(self) -> usize;
}

impl Varint for u32 {
    fn encoded_len(self) -> usize {
        ((32 - self.leading_zeros()).max(1) as usize).div_ceil(7)
    }
}

impl Varint for u64 {
    fn encoded_len(self) -> usize {
        ((64 - self.leading_zeros()).max(1) as usize).div_ceil(7)
    }
}

fn main() {
    assert_eq!(300_u32.encoded_len(), 2);
    assert_eq!(1_u64.encoded_len(), 1);
}
```

`usize::div_ceil` needs Rust 1.73.

Variations:
- **Sealed by a private method parameter** (partially sealed): a method taking a private token type
  (`fn __private(&self, _: private::Token)`) can be called and overridden only inside the crate.
- **Better error messages**: since Rust 1.78, `#[diagnostic::on_unimplemented(message = "...", note = "...")]`
  on the public trait explains why users cannot implement it or which types do.
- Document sealing in the trait docs ("This trait is sealed and cannot be implemented outside this crate").
- Sealing an existing open trait is a breaking change; seal from the start when in doubt.

## Marker traits and unsafe traits

A marker trait has no methods and encodes a property checked by bounds:

```rust
/// Types whose all-zero bit pattern is a valid value.
///
/// # Safety
/// Implementors must be valid for every byte being zero, contain no padding-dependent invariants,
/// no references and no niche-optimized fields.
pub unsafe trait Zeroable: Copy + 'static {}

unsafe impl Zeroable for u32 {}
unsafe impl Zeroable for [u8; 16] {}

pub fn zeroed<T: Zeroable>() -> T {
    // SAFETY: T: Zeroable guarantees the all-zero bit pattern is a valid T.
    unsafe { std::mem::zeroed() }
}

fn main() {
    assert_eq!(zeroed::<u32>(), 0);
}
```

- Make the trait `unsafe trait` when a wrong impl causes undefined behavior in safe code that trusts it
  (`Send`, `Sync`, `bytemuck::Pod`, `GlobalAlloc`). Document the contract in a `# Safety` section.
- If wrong impls only cause logic bugs, it is a normal trait.
- Prefer existing ecosystem markers (`bytemuck::Pod`, `zerocopy::FromBytes`) to inventing your own unsafe
  marker.

## Auto traits: Send, Sync, Unpin

Auto traits are implemented automatically when every field implements them: `Send`, `Sync`, `Unpin`,
`UnwindSafe`, `RefUnwindSafe`. Defining new auto traits is unstable.

| Field type | Effect on the containing type |
|------------|-------------------------------|
| `Rc<T>`, raw pointers `*const T` / `*mut T` | `!Send`, `!Sync` |
| `Cell<T>`, `RefCell<T>` | `!Sync` (still `Send` if `T: Send`) |
| `MutexGuard<'_, T>` | `!Send` |
| `PhantomPinned` | `!Unpin` |
| `PhantomData<*const ()>` | opt out of `Send`/`Sync` on purpose |

Rules:
- Auto traits leak through `impl Trait` return types and are part of your public API; check them with a test
  (see [testing-trait-designs.md](testing-trait-designs.md)).
- `unsafe impl Send for X {}` is a soundness claim: only for types wrapping raw pointers whose aliasing you
  control, with a `// SAFETY:` comment.
- Negative impls (`impl !Send for X`) are unstable; use a `PhantomData` marker field instead.

## Supertraits

`trait Sub: Super` means "every `Sub` implementor must also implement `Super`", and lets `Sub`'s methods and
users of `T: Sub` call `Super`'s methods.

```rust
use std::fmt::Debug;

pub trait Entity: Debug + Send + Sync + 'static {
    fn id(&self) -> u64;
}

pub trait Versioned: Entity {
    fn version(&self) -> u32;

    fn key(&self) -> String {
        format!("{}@{}", self.id(), self.version()) // supertrait method available
    }
}
```

- Supertraits are a promise to implementors: adding one later is breaking.
- `Debug` as a supertrait makes `{:?}` work on `dyn Trait` values; cheap and useful for diagnostics.
- `Send + Sync + 'static` supertraits make `Arc<dyn Trait>` usable across threads without repeating bounds,
  at the cost of forbidding single-threaded implementors.
- A supertrait that is not dyn compatible (Clone, Default, PartialEq) makes the subtrait not dyn compatible.
- Trait upcasting (`&dyn Versioned` to `&dyn Entity`) is stable since 1.86.
- Supertrait method name clashes require fully qualified syntax: `<T as Super>::name(&t)` (E0034 "multiple
  applicable items in scope" otherwise).

## Default methods and the required core

Keep the required surface tiny and build the rest as provided methods, like `Iterator` (one required method,
more than 70 provided):

```rust
pub trait KvRead {
    /// Required.
    fn get(&self, key: &str) -> Option<String>;

    /// Provided: implementors may override for efficiency.
    fn contains(&self, key: &str) -> bool {
        self.get(key).is_some()
    }

    fn get_or(&self, key: &str, default: &str) -> String {
        self.get(key).unwrap_or_else(|| default.to_owned())
    }

    fn get_many(&self, keys: &[&str]) -> Vec<Option<String>> {
        keys.iter().map(|k| self.get(k)).collect()
    }
}
```

- An overriding impl cannot call the default body ("super" call). If overriders need it, expose the default
  as a free function (`pub fn default_get_many<T: KvRead + ?Sized>(t: &T, ..)`).
- Provided methods must keep their documented contract consistent with the required ones
  (`contains(k) == get(k).is_some()`); test the laws (see testing reference).
- Adding a provided method is minor but *possibly breaking*: a user's type with an inherent or other-trait
  method of the same name may hit ambiguity (E0034) in generic code.

## ?Sized and forwarding impls

Generic parameters have an implicit `T: Sized` bound; `Self` in a trait does not. Relax it when the function
only handles `T` behind a pointer, so `str`, `[T]` and `dyn Trait` are accepted:

```rust
use std::fmt::Display;

pub fn log_ref<T: Display + ?Sized>(value: &T) {
    println!("{value}");
}

pub trait Render {
    fn render(&self) -> String;
}

// Forwarding impls: references and boxes of renderers are renderers.
impl<T: Render + ?Sized> Render for &T {
    fn render(&self) -> String {
        (**self).render()
    }
}

impl<T: Render + ?Sized> Render for Box<T> {
    fn render(&self) -> String {
        (**self).render()
    }
}

impl Render for str {
    fn render(&self) -> String {
        format!("\"{self}\"")
    }
}

pub fn render_all<R: Render>(items: &[R]) -> Vec<String> {
    items.iter().map(Render::render).collect()
}

fn main() {
    log_ref("unsized str is fine");
    let boxed: Vec<Box<dyn Render>> = vec![Box::new(1_u8), Box::new("x")];
    assert_eq!(render_all(&boxed), ["1", "\"x\""]);
}

impl Render for u8 {
    fn render(&self) -> String {
        self.to_string()
    }
}
```

Forwarding impls for `&T`, `&mut T`, `Box<T>`, `Rc<T>`/`Arc<T>` (as appropriate for the receiver) let users pass
references and trait objects to your generic functions. std does this for `Read`, `Write`, `Iterator`,
`Hasher` and others. Add them in the first release: adding them later is fine semver-wise but users will have
written wrappers.

## PhantomData

Mark a type parameter or lifetime the struct logically uses but does not store. Without it: error[E0392]
"parameter `T` is never used".

| Marker | Variance in `T` | Drop check (owns a `T`) | Auto traits follow |
|--------|-----------------|-------------------------|--------------------|
| `PhantomData<T>` | covariant | yes | `T` |
| `PhantomData<&'a T>` | covariant | no | `&T` |
| `PhantomData<fn() -> T>` | covariant | no | always `Send + Sync` |
| `PhantomData<fn(T)>` | contravariant | no | always `Send + Sync` |
| `PhantomData<fn(T) -> T>` / `PhantomData<Cell<T>>` | invariant | no / yes | varies |
| `PhantomData<*const T>` | covariant | no | `!Send`, `!Sync` |

```rust
use std::marker::PhantomData;

/// A typed ID: Id<User> and Id<Order> cannot be mixed up. fn() -> T keeps Id Send + Sync even for !Send T.
pub struct Id<T> {
    raw: u64,
    _marker: PhantomData<fn() -> T>,
}

impl<T> Id<T> {
    pub const fn new(raw: u64) -> Self {
        Id { raw, _marker: PhantomData }
    }
    pub const fn raw(self) -> u64 {
        self.raw
    }
}

// Manual impls: #[derive(Clone, Copy, PartialEq)] would add T: Clone / T: Copy / T: PartialEq bounds.
impl<T> Clone for Id<T> {
    fn clone(&self) -> Self {
        *self
    }
}
impl<T> Copy for Id<T> {}
impl<T> PartialEq for Id<T> {
    fn eq(&self, other: &Self) -> bool {
        self.raw == other.raw
    }
}
impl<T> Eq for Id<T> {}
impl<T> std::fmt::Debug for Id<T> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Id({})", self.raw)
    }
}

pub struct User;

fn main() {
    let a: Id<User> = Id::new(7);
    let b = a; // Copy even though User is not Copy
    assert_eq!(a, b);
    assert_eq!(b.raw(), 7);
}
```

Derive pitfall: `#[derive(Clone)]` on `struct Id<T>` generates `impl<T: Clone> Clone for Id<T>`, even when no
field needs it. For phantom-typed wrappers write the impls by hand (or use the `derive-where` crate).

## Review checklist

- [ ] No impl that needs the orphan rule relaxed; newtypes where a foreign trait meets a foreign type.
- [ ] Blanket impls on public traits are deliberate, documented, and present from the first release.
- [ ] Extension traits named `*Ext`, re-exported from a prelude, with distinctive method names.
- [ ] Traits users should not implement are sealed (and documented as such).
- [ ] `unsafe trait` only when wrong impls cause UB, with a `# Safety` contract.
- [ ] Forwarding impls for `&T`/`&mut T`/`Box<T>` where users will pass references or trait objects.
- [ ] `?Sized` on generic parameters only used behind references.
- [ ] `PhantomData` variant chosen on purpose; phantom-typed wrappers implement traits manually.
- [ ] Auto-trait properties (Send/Sync) of public types are tested.
