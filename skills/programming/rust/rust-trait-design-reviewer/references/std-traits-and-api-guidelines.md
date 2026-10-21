# Std Traits and the Rust API Guidelines

Which standard traits a public type should implement, how conversions and errors should look, and the
patterns (iterators, operators, `Deref`, builders, typestate) that users expect to behave like std. Guideline
ids (C-XXX) refer to the Rust API Guidelines checklist (rust-lang.github.io/api-guidelines).

## Contents

- [Std trait checklist for public types](#std-trait-checklist-for-public-types)
- [Debug and Display](#debug-and-display)
- [Equality, ordering and hashing](#equality-ordering-and-hashing)
- [Clone, Copy and Default](#clone-copy-and-default)
- [Send and Sync](#send-and-sync)
- [serde behind a feature](#serde-behind-a-feature)
- [Conversions: From, TryFrom, AsRef, Borrow, FromStr](#conversions-from-tryfrom-asref-borrow-fromstr)
- [Error types](#error-types)
- [Iterators and collections](#iterators-and-collections)
- [Operator overloading](#operator-overloading)
- [Deref: only for smart pointers](#deref-only-for-smart-pointers)
- [Builders](#builders)
- [Typestate](#typestate)
- [must_use and non_exhaustive](#must_use-and-non_exhaustive)
- [Naming conventions that interact with traits](#naming-conventions-that-interact-with-traits)
- [Lints that enforce this](#lints-that-enforce-this)

## Std trait checklist for public types

| Trait | Implement when | How | Guideline |
|-------|----------------|-----|-----------|
| `Debug` | always | derive; manual to redact secrets | C-DEBUG, C-DEBUG-NONEMPTY |
| `Clone` | value can be duplicated meaningfully | derive | C-COMMON-TRAITS |
| `Copy` | small, plain data, no ownership, stable forever | derive with Clone | C-COMMON-TRAITS |
| `PartialEq` / `Eq` | equality is meaningful; Eq if reflexive (no NaN floats) | derive | C-COMMON-TRAITS |
| `PartialOrd` / `Ord` | a natural order exists | derive (field order matters) or manual | C-COMMON-TRAITS |
| `Hash` | `Eq` is implemented and the type may be a map/set key | derive, consistent with Eq | C-COMMON-TRAITS |
| `Default` | an obvious "empty"/neutral value exists | derive, `#[default]` variant for enums (1.62) | C-COMMON-TRAITS |
| `Display` | the value has a user-facing text form (errors always) | manual | C-COMMON-TRAITS |
| `From` / `TryFrom` / `AsRef` / `AsMut` | natural conversions exist | manual | C-CONV-TRAITS |
| `FromIterator` / `Extend` | collection types | manual | C-COLLECT |
| `Serialize` / `Deserialize` | data types users may persist or send | `cfg_attr` derive behind `serde` feature | C-SERDE |
| `Send` / `Sync` | automatically; verify they hold | test with assertions | C-SEND-SYNC |
| `std::error::Error` | error types | manual or thiserror | C-GOOD-ERR |
| `Binary`, `Octal`, `LowerHex`, `UpperHex`, `LowerExp` | numeric-like types | manual | C-NUM-FMT |

Why "eagerly": the orphan rule stops your users from adding std trait impls to your types. If you omit
`Hash`, nobody can put your type in a `HashSet` without a newtype.

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Default)]
pub struct Version {
    pub major: u16,
    pub minor: u16,
    pub patch: u16,
}

impl std::fmt::Display for Version {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)
    }
}

fn main() {
    let v = Version { major: 1, minor: 86, patch: 0 };
    assert!(v > Version { major: 1, minor: 75, patch: 9 }); // derived Ord compares fields in order
    assert_eq!(v.to_string(), "1.86.0");
}
```

## Debug and Display

- `Debug` is for programmers (`{:?}`, `dbg!`, `assert_eq!` failure messages, `unwrap` panics); derive it.
- `Display` is for users; implement it by hand; never derive-like (no struct syntax). `ToString` comes free:
  implement `Display`, never `ToString` directly (clippy `to_string_trait_impl`).
- Redact secrets in a manual `Debug`:

```rust
use std::fmt;

pub struct ApiKey(String);

impl fmt::Debug for ApiKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let tail = self.0.get(self.0.len().saturating_sub(4)..).unwrap_or("");
        write!(f, "ApiKey(****{tail})")
    }
}

pub struct Client {
    key: ApiKey,
    base_url: String,
    pool: Vec<u8>, // imagine a connection pool without Debug
}

impl fmt::Debug for Client {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Client")
            .field("key", &self.key)
            .field("base_url", &self.base_url)
            .finish_non_exhaustive() // prints `..` for omitted fields (1.53)
    }
}

fn main() {
    let c = Client { key: ApiKey("sk-123456".into()), base_url: "https://api".into(), pool: vec![] };
    assert_eq!(format!("{c:?}"), r#"Client { key: ApiKey(****3456), base_url: "https://api", .. }"#);
    let _ = &c.pool;
}
```

- Use `f.debug_struct`, `debug_tuple`, `debug_list`, `debug_map` so `{:#?}` pretty-printing works.
- Display should honor width/fill flags when it is value-like: `f.pad(&s)` instead of `write!(f, "{s}")`.

## Equality, ordering and hashing

Laws users and std collections rely on:

- `a == b` implies `hash(a) == hash(b)` (HashMap/HashSet correctness).
- `Eq`: reflexive, so no `f32`/`f64` fields (NaN != NaN). Wrap floats (`ordered_float::OrderedFloat`) or
  compare with `total_cmp` manually if you need `Eq`/`Ord`.
- `Ord` must agree with `PartialOrd` and `Eq` (`cmp == Equal` exactly when `==`).
- `Borrow<Q>` impls require `Q`'s Eq/Hash/Ord to agree with the owner's.

Derives compare fields in declaration order, so field order is part of the ordering semantics. If equality
should ignore a field (a cache, a timestamp), write `PartialEq` and `Hash` by hand, both over the same fields:

```rust
use std::hash::{Hash, Hasher};

#[derive(Debug, Clone)]
pub struct CacheKey {
    pub tenant: String,
    pub query: String,
    pub computed_at_ms: u64, // not part of identity
}

impl PartialEq for CacheKey {
    fn eq(&self, other: &Self) -> bool {
        self.tenant == other.tenant && self.query == other.query
    }
}
impl Eq for CacheKey {}

impl Hash for CacheKey {
    fn hash<H: Hasher>(&self, state: &mut H) {
        self.tenant.hash(state);
        self.query.hash(state);
    }
}
```

`#[derive(Hash)]` plus a hand-written `PartialEq` is exactly the bug `api_traits` flags as TR011
(clippy `derived_hash_with_manual_eq`).

## Clone, Copy and Default

- `Copy` is a promise: removing it later breaks every user that relied on implicit copies. Implement it for
  small value types (IDs, coordinates, flags), not for types that may grow a `String` or `Vec` field.
- `Clone` should be "obviously correct" duplication. Expensive clones are fine (`Vec`), but shared-handle
  clones (`Arc`-based clients) should be documented as cheap and sharing state.
- `Default` complements `new()`: if `new()` takes no arguments, `impl Default` and have one call the other
  (clippy `new_without_default`, TR012). For enums use `#[derive(Default)]` with `#[default]` on a unit variant.
- Derives on generic types add bounds on the parameters (`#[derive(Clone)] struct S<T>` gives
  `impl<T: Clone> Clone for S<T>`). For `PhantomData`-typed wrappers implement manually.

## Send and Sync

`Send`/`Sync` are auto traits: you get them if all fields have them. They are still part of your public API:

- A public type becoming `!Send` (an `Rc` or `RefCell` field added) breaks users who move it across threads.
- Futures and iterators returned as `impl Trait` leak their auto traits.
- Assert them in tests (`fn assert_send_sync<T: Send + Sync>() {}`); see
  [testing-trait-designs.md](testing-trait-designs.md).
- Trait objects: `Box<dyn Trait + Send + Sync>` when the value crosses threads.

## serde behind a feature

C-SERDE: data structures implement `Serialize`/`Deserialize`, but optional, so users who do not need serde
do not compile it.

```toml
[features]
serde = ["dep:serde"]          # `dep:` syntax: Cargo 1.60

[dependencies]
serde = { version = "1", optional = true, features = ["derive"] }
```

```rust,ignore
#[derive(Debug, Clone, PartialEq)]
#[cfg_attr(feature = "serde", derive(serde::Serialize, serde::Deserialize))]
#[cfg_attr(feature = "serde", serde(rename_all = "snake_case"))]
pub struct Config {
    pub max_retries: u32,
    #[cfg_attr(feature = "serde", serde(default))]
    pub verbose: bool,
}
```

Test with `cargo test --all-features` and `cargo test --no-default-features` (or `cargo hack --each-feature`).

## Conversions: From, TryFrom, AsRef, Borrow, FromStr

| Trait | Meaning | Rules |
|-------|---------|-------|
| `From<T>` | infallible, value-preserving conversion | implement this; `Into` comes from `impl<T, U: From<T>> Into<U> for T` |
| `Into<U>` | the caller-side view of From | use in bounds (`impl Into<String>`); never implement it directly (TR002, clippy `from_over_into`) |
| `TryFrom<T>` / `TryInto` | fallible conversion, `type Error` | stable 1.34; implement TryFrom only |
| `AsRef<T>` / `AsMut<T>` | cheap reference-to-reference view | no allocation, cannot fail; generic params `impl AsRef<Path>` |
| `Borrow<T>` | like AsRef, plus Eq/Hash/Ord equivalence | what lets `HashMap<String, V>::get(&str)` work |
| `ToOwned` | generalized Clone from a borrowed form | `str -> String`, `[T] -> Vec<T>`; used by `Cow` |
| `FromStr` | parse from text | enables `"..".parse::<T>()`; `type Err` |

```rust
use std::str::FromStr;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Port(u16);

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PortError {
    Zero,
    Parse(std::num::ParseIntError),
}

impl std::fmt::Display for PortError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PortError::Zero => f.write_str("port 0 is reserved"),
            PortError::Parse(_) => f.write_str("port is not a number"),
        }
    }
}

impl std::error::Error for PortError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            PortError::Parse(e) => Some(e),
            PortError::Zero => None,
        }
    }
}

impl TryFrom<u16> for Port {
    type Error = PortError;
    fn try_from(v: u16) -> Result<Self, Self::Error> {
        if v == 0 { Err(PortError::Zero) } else { Ok(Port(v)) }
    }
}

impl From<Port> for u16 {
    fn from(p: Port) -> u16 {
        p.0
    }
}

impl FromStr for Port {
    type Err = PortError;
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let n: u16 = s.trim().parse().map_err(PortError::Parse)?;
        Port::try_from(n)
    }
}

fn main() {
    let p: Port = "8080".parse().unwrap();
    let raw: u16 = p.into(); // Into via the blanket impl
    assert_eq!(raw, 8080);
    assert_eq!(Port::try_from(0), Err(PortError::Zero));
}
```

Rules of thumb:
- Do not implement `From` for lossy or surprising conversions (`From<f64> for Money` that rounds). Use a named
  method (`Money::from_f64_rounded`).
- Conversions live on the most specific type (C-CONV-SPECIFIC): `impl From<Port> for u16`, not a method on u16.
- Generic parameters: accept `impl Into<String>` only when you store an owned `String` (it saves the caller an
  allocation when they already have one); accept `&str` when you only read.
- `impl AsRef<Path>` for path parameters, like std (`fs::read(path: impl AsRef<Path>)`).

## Error types

C-GOOD-ERR: error types implement `std::error::Error` (thus `Debug + Display`), are `Send + Sync + 'static`,
and give a meaningful message. Library pattern with thiserror:

```rust,ignore
// Cargo.toml: thiserror = "2"
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum FetchError {
    #[error("request to {url} timed out after {secs}s")]
    Timeout { url: String, secs: u64 },
    #[error("server returned status {0}")]
    Status(u16),
    #[error("i/o error")]
    Io(#[from] std::io::Error), // From impl + source() generated
}
```

- Libraries: concrete enums (callers can match). Applications: `anyhow::Error` / `eyre::Report`, or
  `Box<dyn Error + Send + Sync + 'static>`.
- Display messages: lowercase, no trailing punctuation, do not repeat the source's message (report chains print
  sources separately).
- Implement `source()` (or `#[source]`/`#[from]`), not the deprecated `description()`/`cause()`.
- `Box<dyn Error>` without `Send + Sync` cannot cross threads or convert into `anyhow::Error` (TR009).
- `std::error::Error` is also `core::error::Error` since 1.81, usable in `no_std` crates.

## Iterators and collections

Expose iteration the way std collections do (C-ITER, C-ITER-TY): methods `iter`, `iter_mut`, `into_iter`
returning types named `Iter`, `IterMut`, `IntoIter`, and `IntoIterator` for `T`, `&T` and `&mut T`, so `for`
loops work.

```rust
pub struct Playlist {
    songs: Vec<String>,
}

pub struct Iter<'a> {
    inner: std::slice::Iter<'a, String>,
}

impl<'a> Iterator for Iter<'a> {
    type Item = &'a str;

    fn next(&mut self) -> Option<&'a str> {
        self.inner.next().map(String::as_str)
    }

    fn size_hint(&self) -> (usize, Option<usize>) {
        self.inner.size_hint()
    }
}

impl ExactSizeIterator for Iter<'_> {}
impl std::iter::FusedIterator for Iter<'_> {}

impl DoubleEndedIterator for Iter<'_> {
    fn next_back(&mut self) -> Option<Self::Item> {
        self.inner.next_back().map(String::as_str)
    }
}

impl Playlist {
    pub fn iter(&self) -> Iter<'_> {
        Iter { inner: self.songs.iter() }
    }
}

impl<'a> IntoIterator for &'a Playlist {
    type Item = &'a str;
    type IntoIter = Iter<'a>;
    fn into_iter(self) -> Iter<'a> {
        self.iter()
    }
}

impl IntoIterator for Playlist {
    type Item = String;
    type IntoIter = std::vec::IntoIter<String>;
    fn into_iter(self) -> Self::IntoIter {
        self.songs.into_iter()
    }
}

impl FromIterator<String> for Playlist {
    fn from_iter<I: IntoIterator<Item = String>>(iter: I) -> Self {
        Playlist { songs: iter.into_iter().collect() }
    }
}

impl Extend<String> for Playlist {
    fn extend<I: IntoIterator<Item = String>>(&mut self, iter: I) {
        self.songs.extend(iter);
    }
}

fn main() {
    let mut p: Playlist = ["a", "b"].into_iter().map(String::from).collect();
    p.extend(["c".to_string()]);
    let mut seen = Vec::new();
    for s in &p {
        seen.push(s);
    }
    assert_eq!(seen, ["a", "b", "c"]);
    assert_eq!(p.iter().rev().next(), Some("c"));
    assert_eq!(p.iter().len(), 3);
}
```

- Implement `size_hint` when cheap; `ExactSizeIterator` only when the hint is exact; `FusedIterator` when
  `next` keeps returning `None` after the first `None`.
- Wrapping a std iterator in a named newtype (`Iter`) keeps the concrete type private and changeable; returning
  `std::slice::Iter` directly makes it part of your API.
- Accept `impl IntoIterator<Item = T>` in parameters instead of `Vec<T>` or `&[T]` when you only iterate once.

## Operator overloading

C-OVERLOAD: only implement operators whose meaning is unsurprising (`+` on money, vectors, durations; not `+`
for "append to log").

```rust
use std::ops::{Add, AddAssign, Mul, Neg};

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Vec2 {
    pub x: f64,
    pub y: f64,
}

impl Add for Vec2 {
    type Output = Vec2;
    fn add(self, o: Vec2) -> Vec2 {
        Vec2 { x: self.x + o.x, y: self.y + o.y }
    }
}

impl AddAssign for Vec2 {
    fn add_assign(&mut self, o: Vec2) {
        *self = *self + o;
    }
}

impl Mul<f64> for Vec2 {
    type Output = Vec2;
    fn mul(self, k: f64) -> Vec2 {
        Vec2 { x: self.x * k, y: self.y * k }
    }
}

// Orphan rule allows this: the local type appears as the trait parameter.
impl Mul<Vec2> for f64 {
    type Output = Vec2;
    fn mul(self, v: Vec2) -> Vec2 {
        v * self
    }
}

impl Neg for Vec2 {
    type Output = Vec2;
    fn neg(self) -> Vec2 {
        Vec2 { x: -self.x, y: -self.y }
    }
}

impl std::iter::Sum for Vec2 {
    fn sum<I: Iterator<Item = Vec2>>(iter: I) -> Vec2 {
        iter.fold(Vec2::default(), Add::add)
    }
}

fn main() {
    let a = Vec2 { x: 1.0, y: 2.0 };
    let mut b = 2.0_f64 * a;
    b += -a;
    assert_eq!(b, a);
    assert_eq!([a, a].into_iter().sum::<Vec2>(), a * 2.0);
}
```

For non-`Copy` types (big integers, matrices) also implement the reference forms
(`impl Add<&Matrix> for &Matrix`) so users can write `&a + &b` without cloning.

## Deref: only for smart pointers

C-DEREF: implement `Deref` only for types that *are* a pointer to their target (`Box`, `Rc`, `String -> str`,
`Vec -> [T]`, `MutexGuard`, `Cow`). Using it to inherit methods from a "base" struct (TR005) causes:

- method resolution surprises (`admin.name()` silently calls `User::name`, `admin.clone()` may clone the inner
  type if the outer one is not Clone);
- no real subtyping: `fn f(u: &User)` accepts `&admin` by auto-deref, but `T: UserTrait` bounds and `Vec<User>`
  do not;
- your public API now includes every current and future method of the target (semver hazard).

Alternatives: composition with explicit delegating methods, a shared trait, `AsRef<User>`, or exposing the
inner value with an accessor (`admin.user()`). Transparent newtypes (`struct Html(String)`) may implement
`Deref<Target = str>` if they truly are "a string with a tag" and have no invariant that `&str` access could
violate; never `DerefMut` when there is an invariant.

## Builders

C-BUILDER: use a builder when construction has many optional parameters.

| Style | Signature | Use when |
|-------|-----------|----------|
| Consuming | `fn timeout(mut self, d: Duration) -> Self` | one-liner chains; build consumes the builder |
| Non-consuming | `fn timeout(&mut self, d: Duration) -> &mut Self` | builder reused, configured in branches (`std::process::Command`) |

```rust
use std::time::Duration;

#[derive(Debug, Clone, PartialEq)]
pub struct Client {
    pub base_url: String,
    pub timeout: Duration,
    pub retries: u32,
}

#[derive(Debug, Clone)]
#[must_use = "builders do nothing until .build() is called"]
pub struct ClientBuilder {
    base_url: String,
    timeout: Duration,
    retries: u32,
}

impl Client {
    pub fn builder(base_url: impl Into<String>) -> ClientBuilder {
        ClientBuilder { base_url: base_url.into(), timeout: Duration::from_secs(30), retries: 3 }
    }
}

impl ClientBuilder {
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = timeout;
        self
    }

    pub fn retries(mut self, retries: u32) -> Self {
        self.retries = retries;
        self
    }

    pub fn build(self) -> Client {
        Client { base_url: self.base_url, timeout: self.timeout, retries: self.retries }
    }
}

fn main() {
    let c = Client::builder("https://api.example.com").retries(5).build();
    assert_eq!(c.retries, 5);
}
```

Required parameters go in `builder(..)`; optional ones get methods. `#[must_use]` on the builder type makes
`builder.retries(5);` (result discarded) a warning (TR013). `bon` and `typed-builder` derive builders,
including compile-time checks for required fields.

## Typestate

Encode states in type parameters so invalid transitions do not compile. Zero runtime cost: state markers are
zero-sized and live in `PhantomData`.

```rust
use std::marker::PhantomData;

#[derive(Debug)]
pub struct Open;
#[derive(Debug)]
pub struct Closed;

#[derive(Debug)]
pub struct Connection<S> {
    addr: String,
    _state: PhantomData<S>,
}

impl Connection<Closed> {
    pub fn new(addr: &str) -> Self {
        Connection { addr: addr.to_owned(), _state: PhantomData }
    }
    pub fn open(self) -> Connection<Open> {
        Connection { addr: self.addr, _state: PhantomData }
    }
}

impl Connection<Open> {
    pub fn send(&mut self, msg: &str) -> usize {
        msg.len()
    }
    pub fn close(self) -> Connection<Closed> {
        Connection { addr: self.addr, _state: PhantomData }
    }
}

impl<S> Connection<S> {
    pub fn addr(&self) -> &str {
        &self.addr
    }
}

fn main() {
    let mut c = Connection::new("db:5432").open();
    assert_eq!(c.send("ping"), 4);
    let c = c.close();
    assert_eq!(c.addr(), "db:5432");
    // c.send("x"); // error[E0599]: no method named `send` found for struct `Connection<Closed>`
}
```

Trade-offs: states must be known at compile time (a connection that may be open or closed at runtime needs an
enum), and each state multiplies the API surface. Use typestate for protocols and builders with required
steps; `/tmp/scaffold_trait typestate` prints a builder version.

## must_use and non_exhaustive

`#[must_use]` (functions since 1.27): warn when the return value is ignored.
- On types: builders, guards, handles whose drop cancels work. `Result`, `Future`, iterator adapters are already
  must_use.
- On functions: pure functions and methods returning a modified copy (`fn with_x(self, ..) -> Self`,
  `fn trimmed(&self) -> String`). Optional message: `#[must_use = "this returns a new value"]`.
- On traits: `#[must_use]` on a trait makes `impl Trait` / `dyn Trait` returns of it must_use.

`#[non_exhaustive]` (1.40): reserve the right to add fields or variants.
- Enums: downstream `match` needs a `_` arm; adding variants becomes a minor change.
- Structs: downstream cannot construct with a literal or destructure exhaustively; provide constructors or
  `Default` + builder. Inside your crate it has no effect.
- Variants: `#[non_exhaustive]` on a single variant allows adding fields to it.
- Adding `#[non_exhaustive]` to an existing public item is itself a major change. Decide before 1.0.

## Naming conventions that interact with traits

| Convention | Rule | Id |
|------------|------|-----|
| `as_` / `to_` / `into_` | free borrowed view / expensive or owned conversion / consuming conversion | C-CONV |
| Getters | `fn name(&self)`, not `get_name`; `get` only for the single obvious item (`Cell::get`) | C-GETTER |
| Iterators | `iter`, `iter_mut`, `into_iter`; types `Iter`, `IterMut`, `IntoIter` | C-ITER, C-ITER-TY |
| Extension traits | `FooExt` | ecosystem convention |
| Method names that shadow std traits | do not name an inherent method `add`, `next`, `from_str`, `clone` with a different meaning; implement the trait | clippy `should_implement_trait` |

## Lints that enforce this

| Lint | Catches |
|------|---------|
| `missing_debug_implementations` (rustc, allow by default) | public types without Debug |
| `missing_docs` (rustc) | undocumented public items |
| `unreachable_pub` (rustc) | `pub` items not reachable from the crate root |
| `async_fn_in_trait` (rustc, warn) | `async fn` in public traits |
| `clippy::from_over_into` | `impl Into` instead of From |
| `clippy::new_without_default` | `new()` without Default |
| `clippy::derived_hash_with_manual_eq` | derived Hash + manual PartialEq |
| `clippy::ptr_arg`, `clippy::borrowed_box` | `&Vec<T>`, `&String`, `&PathBuf`, `&Box<T>` parameters |
| `clippy::return_self_not_must_use` (pedantic) | builder methods without must_use |
| `clippy::should_implement_trait` | inherent methods named like std trait methods |
| `clippy::wrong_self_convention` | `as_`/`to_`/`into_` receivers that break C-CONV |
| `clippy::len_without_is_empty` | `len()` without `is_empty()` |

Enable in `lib.rs`: `#![warn(missing_debug_implementations, missing_docs, unreachable_pub)]`, and run
`cargo clippy -- -W clippy::pedantic` in CI (allow individual pedantic lints that do not fit).
