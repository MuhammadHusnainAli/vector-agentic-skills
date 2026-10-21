# Async Traits and Advanced Generics

`async fn` and `-> impl Trait` in traits (Rust 1.75), the `Send` bound problem and its workarounds, boxing
for `dyn`, generic associated types (1.65), associated types vs generic parameters, associated type bounds
(1.79), higher-ranked trait bounds, and the `Fn`/`AsyncFn` closure traits.

## Contents

- [async fn in traits](#async-fn-in-traits)
- [The Send bound problem](#the-send-bound-problem)
- [Fix 1: declare the Send future in the trait](#fix-1-declare-the-send-future-in-the-trait)
- [Fix 2: trait_variant](#fix-2-trait_variant)
- [Fix 3: dyn with async methods](#fix-3-dyn-with-async-methods)
- [Return-type notation (not stable)](#return-type-notation-not-stable)
- [Decision table for async traits](#decision-table-for-async-traits)
- [RPITIT: -> impl Trait in traits](#rpitit---impl-trait-in-traits)
- [Associated types vs generic parameters](#associated-types-vs-generic-parameters)
- [Associated type bounds and associated consts](#associated-type-bounds-and-associated-consts)
- [Generic associated types](#generic-associated-types)
- [Higher-ranked trait bounds](#higher-ranked-trait-bounds)
- [Fn, FnMut, FnOnce and function pointers](#fn-fnmut-fnonce-and-function-pointers)
- [Async closures and AsyncFn (1.85)](#async-closures-and-asyncfn-185)
- [Review checklist](#review-checklist)

## async fn in traits

Since Rust 1.75 a trait may declare `async fn` directly:

```rust
pub trait Repo {
    async fn load(&self, id: u64) -> Option<String>;
}

pub struct MemRepo(Vec<String>);

impl Repo for MemRepo {
    async fn load(&self, id: u64) -> Option<String> {
        self.0.get(id as usize).cloned()
    }
}

// Generic use works out of the box.
pub async fn load_two<R: Repo>(repo: &R) -> (Option<String>, Option<String>) {
    (repo.load(0).await, repo.load(1).await)
}
```

It desugars to `fn load(&self, id: u64) -> impl Future<Output = Option<String>>`, an anonymous associated type
per implementation. Two consequences:

1. The trait is **not dyn compatible** (an opaque return type has no single vtable signature).
2. Callers **cannot name** that future, so they cannot add bounds to it, most importantly `Send`.

Because of (2), rustc warns on `async fn` in a publicly reachable trait:

```text
warning: use of `async fn` in public traits is discouraged as auto trait bounds cannot be specified
  = note: you can suppress this lint if you plan to use the trait only in your own code, or do not care
          about auto traits like `Send` on the `Future`
  = note: `#[warn(async_fn_in_trait)]` on by default
```

## The Send bound problem

Multi-threaded executors (`tokio::spawn`, `std::thread::spawn`-backed pools) need `Send` futures. With
`async fn` in the trait, generic code cannot prove the future is `Send`, even when every concrete impl is:

```rust,ignore
pub async fn spawn_load<R: Repo + Send + Sync + 'static>(repo: std::sync::Arc<R>) {
    tokio::spawn(async move {
        repo.load(1).await // error: future cannot be sent between threads safely
    });
}
```

`R: Send + Sync` is not enough: the future returned by `R::load` is a separate type whose `Send`-ness is
unknown in generic code. Concrete types do not have the problem (the compiler sees the actual future), which is
why the error often appears only after a function is made generic.

## Fix 1: declare the Send future in the trait

Write the desugared form with the bounds you need. Implementors can still use `async fn` in their impls, as
long as their future actually is `Send`:

```rust
use std::future::Future;

pub trait Repo: Send + Sync {
    fn load(&self, id: u64) -> impl Future<Output = Option<String>> + Send;
}

pub struct MemRepo(Vec<String>);

impl Repo for MemRepo {
    async fn load(&self, id: u64) -> Option<String> {
        self.0.get(id as usize).cloned()
    }
}

fn require_send<T: Send>(value: T) -> T {
    value // stands in for tokio::spawn, which requires Send
}

// Compiles in generic code: the trait guarantees the future is Send.
pub async fn load_first<R: Repo>(repo: &R) -> Option<String> {
    require_send(repo.load(0)).await
}
```

Cost: implementors that hold `Rc`, `RefCell` borrows or `MutexGuard`s across `.await` can no longer implement
the trait. That is usually what a library wants.

## Fix 2: trait_variant

The `trait-variant` crate (from the Rust async working group) generates the Send variant from a local one:

```rust,ignore
// Cargo.toml: trait-variant = "0.1"
#[trait_variant::make(Repo: Send)]
pub trait LocalRepo {
    async fn load(&self, id: u64) -> Option<String>;
}
```

This keeps `LocalRepo` (no Send requirement, for single-threaded runtimes) and generates `Repo`, whose
methods return `impl Future<Output = ..> + Send`, plus a blanket impl so every `Repo` is also a `LocalRepo`.
Implement `Repo` for thread-safe types and write generic multi-threaded code against `Repo`.

## Fix 3: dyn with async methods

Native async traits are not dyn compatible. Options:

**async-trait crate** (boxes every returned future):

```rust,ignore
// Cargo.toml: async-trait = "0.1"
use async_trait::async_trait;

#[async_trait]
pub trait Store: Send + Sync {
    async fn get(&self, key: &str) -> Option<String>;
}

pub struct Mem(std::collections::HashMap<String, String>);

#[async_trait]
impl Store for Mem {
    async fn get(&self, key: &str) -> Option<String> {
        self.0.get(key).cloned()
    }
}

// Works: Box<dyn Store>, Arc<dyn Store>, &dyn Store.
pub async fn read(store: &dyn Store) -> Option<String> {
    store.get("k").await
}
```

The macro rewrites methods to return `Pin<Box<dyn Future<Output = T> + Send + 'async_trait>>`. Futures are
`Send` by default; `#[async_trait(?Send)]` on both the trait and impls drops that. Cost: one heap allocation
per call, which is negligible next to network or disk I/O.

**Hand-written boxing** (no macro, same shape):

```rust
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;

pub type BoxFuture<'a, T> = Pin<Box<dyn Future<Output = T> + Send + 'a>>;

pub trait Store: Send + Sync {
    fn get<'a>(&'a self, key: &'a str) -> BoxFuture<'a, Option<String>>;
}

pub struct Mem(HashMap<String, String>);

impl Store for Mem {
    fn get<'a>(&'a self, key: &'a str) -> BoxFuture<'a, Option<String>> {
        Box::pin(async move { self.0.get(key).cloned() })
    }
}

pub async fn read(store: &dyn Store) -> Option<String> {
    store.get("k").await
}
```

Lifetime parameters on methods are allowed in dyn-compatible traits; type parameters are not. `futures::future::BoxFuture`
is the same alias if you already depend on `futures`.

**Both static and dyn**: keep the native trait for generic callers and add an object-safe twin with a blanket
impl:

```rust
use std::future::Future;
use std::pin::Pin;

pub trait Fetch: Send + Sync {
    fn fetch(&self, url: &str) -> impl Future<Output = String> + Send;
}

pub trait DynFetch: Send + Sync {
    fn fetch_dyn<'a>(&'a self, url: &'a str) -> Pin<Box<dyn Future<Output = String> + Send + 'a>>;
}

impl<T: Fetch> DynFetch for T {
    fn fetch_dyn<'a>(&'a self, url: &'a str) -> Pin<Box<dyn Future<Output = String> + Send + 'a>> {
        Box::pin(self.fetch(url))
    }
}
```

## Return-type notation (not stable)

The language-level fix is return-type notation, letting callers bound a method's future:
`fn spawn_load<R: Repo<load(..): Send>>(..)`. As of this writing it is available only on nightly
(`#![feature(return_type_notation)]`). Do not design a stable public API around it; use Fix 1 or Fix 2.

## Decision table for async traits

| Situation | Choose |
|-----------|--------|
| Trait used only inside your crate, concrete types or single-threaded runtime | `async fn`, `#[allow(async_fn_in_trait)]` if it is `pub` but internal |
| Public trait, generic callers on Tokio multi-thread | `-> impl Future<Output = T> + Send` or `#[trait_variant::make(X: Send)]` |
| Need `Box<dyn Trait>` / `Arc<dyn Trait>` (plugins, DI containers) | `#[async_trait]` or hand-written `BoxFuture` |
| Hot path, millions of calls per second, plus dyn | hand-written boxing per call is measurable: consider enum dispatch or a generic API |
| MSRV below 1.75 | `async-trait` or `BoxFuture` |

## RPITIT: -> impl Trait in traits

Also stable since 1.75: methods may return `impl Trait`:

```rust
pub trait Catalog {
    fn names(&self) -> impl Iterator<Item = &str>;
}

pub struct Shelf(Vec<String>);

impl Catalog for Shelf {
    fn names(&self) -> impl Iterator<Item = &str> {
        self.0.iter().map(String::as_str)
    }
}

pub fn count<C: Catalog>(c: &C) -> usize {
    c.names().count()
}
```

- Each impl picks its own concrete type; no `Box`, no allocation.
- Not dyn compatible: offer `fn names_boxed(&self) -> Box<dyn Iterator<Item = &str> + '_>` if `dyn` is needed.
- RPITIT captures all generic parameters and lifetimes in scope, including the `&self` lifetime.
- Auto traits are not implied: add `+ Send` in the trait if generic callers need it, exactly like futures.
- An impl may return a more specific type than the trait promises (refinement), but for public traits rustc
  warns (`refining_impl_trait`) because callers through the trait cannot rely on it.

## Associated types vs generic parameters

```rust
use std::ops::Add;

// Generic parameter (with default): a type can implement Add many times, once per Rhs.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Money {
    cents: i64,
}

impl Add for Money {
    type Output = Money; // associated type: one Output per (Self, Rhs) pair
    fn add(self, rhs: Money) -> Money {
        Money { cents: self.cents + rhs.cents }
    }
}

impl Add<i64> for Money {
    type Output = Money;
    fn add(self, rhs: i64) -> Money {
        Money { cents: self.cents + rhs }
    }
}

// Associated type: a parser produces exactly one kind of output.
pub trait Parser {
    type Output;
    type Error;
    fn parse(&self, input: &str) -> Result<Self::Output, Self::Error>;
}

fn main() {
    let a = Money { cents: 150 };
    assert_eq!(a + a, Money { cents: 300 });
    assert_eq!(a + 50_i64, Money { cents: 200 });
}
```

| Pick | When | Examples |
|------|------|----------|
| Associated type | the type is determined by the implementor; one impl per type | `Iterator::Item`, `Deref::Target`, `FromStr::Err`, `Future::Output`, `Service::Response` |
| Generic parameter | the same type implements the trait for several argument types | `From<T>`, `AsRef<T>`, `Add<Rhs>`, `PartialEq<Rhs>`, `Service<Request>` |
| Both | input chosen by caller, output determined by the pair | `Add<Rhs> { type Output; }`, tower `Service<Request> { type Response; }` |

Symptoms of the wrong choice:
- Generic parameter where an associated type belongs: callers need annotations everywhere,
  error[E0283] "type annotations needed", and bounds like `T: Parser<u32, MyErr>` repeated.
- Associated type where a parameter belongs: users cannot implement the trait twice for the same type and
  reach for wrapper types.

Trait-level generic parameters can have defaults (`trait Add<Rhs = Self>`); adding a defaulted parameter to an
existing trait is a minor change, adding one without a default is major.

## Associated type bounds and associated consts

Associated type bounds (Rust 1.79) put a bound on an associated type inline:

```rust
use std::fmt::Display;

pub fn join<I>(items: I) -> String
where
    I: IntoIterator<Item: Display>,
{
    items.into_iter().map(|i| i.to_string()).collect::<Vec<_>>().join(",")
}

// Before 1.79: where I: IntoIterator, I::Item: Display
fn main() {
    assert_eq!(join([1, 2]), "1,2");
}
```

Associated consts (Rust 1.20) give per-type constants usable in generic code, but make the trait not dyn
compatible:

```rust
pub trait Codec {
    const NAME: &'static str;
    const MAX_FRAME: usize = 64 * 1024; // default
    fn encode(&self, out: &mut Vec<u8>);
}

pub fn header<C: Codec>() -> String {
    format!("{} (max {} bytes)", C::NAME, C::MAX_FRAME)
}
```

Const generics (Rust 1.51) let traits be implemented over array lengths: `impl<const N: usize> Codec for [u8; N]`.

## Generic associated types

GATs (Rust 1.65) let an associated type take generic parameters, most often a lifetime tied to `&self`.
The canonical use is a "lending" iterator whose items borrow from the iterator itself, which `Iterator` cannot
express:

```rust
pub trait LendingIterator {
    type Item<'a>
    where
        Self: 'a;

    fn next(&mut self) -> Option<Self::Item<'_>>;
}

pub struct WindowsMut<'s, T> {
    slice: &'s mut [T],
    start: usize,
    size: usize,
}

impl<'s, T> LendingIterator for WindowsMut<'s, T> {
    type Item<'a> = &'a mut [T] where Self: 'a;

    fn next(&mut self) -> Option<Self::Item<'_>> {
        let window = self.slice.get_mut(self.start..self.start + self.size)?;
        self.start += 1;
        Some(window)
    }
}

fn main() {
    let mut data = [1, 2, 3, 4];
    let mut it = WindowsMut { slice: &mut data, start: 0, size: 2 };
    while let Some(w) = it.next() {
        w[1] += w[0];
    }
    assert_eq!(data, [1, 3, 6, 10]);
}
```

- The `where Self: 'a` clause is required by the compiler for GATs that borrow from `Self`.
- GATs make a trait not dyn compatible.
- Generic code over GATs can hit borrow-checker limitations with higher-ranked bounds
  (`for<'a> I::Item<'a>: Debug`); keep GAT traits small and test the generic consumers you expect.
- Prefer a plain associated type or `Iterator` when items do not borrow from the producer.

## Higher-ranked trait bounds

`for<'a>` says "for every lifetime": needed when a closure or trait must work with borrows created inside your
function.

```rust
// Elided form: Fn(&str) -> &str already means for<'a> Fn(&'a str) -> &'a str.
pub fn apply_to_lines<F>(text: &str, f: F) -> Vec<&str>
where
    F: Fn(&str) -> &str,
{
    text.lines().map(|l| f(l)).collect()
}

// Explicit form needed for non-Fn traits:
pub trait Visit<'a> {
    fn visit(&mut self, item: &'a str);
}

pub fn visit_all<V>(lines: &[String], v: &mut V)
where
    V: for<'a> Visit<'a>,
{
    for l in lines {
        v.visit(l);
    }
}

fn main() {
    let out = apply_to_lines("  a \n b", str::trim);
    assert_eq!(out, ["a", "b"]);
}
```

Symptom of a missing HRTB: "borrowed value does not live long enough" / "implementation of X is not general
enough" when a generic bound fixes one lifetime that the function body needs to vary.

## Fn, FnMut, FnOnce and function pointers

| Trait | Callable | Captures may be | Accept it when |
|-------|----------|-----------------|----------------|
| `FnOnce()` | once (consumes) | moved out | you call it at most once (`Option::map`, `thread::spawn`) |
| `FnMut()` | many times, `&mut` | mutated | you call it repeatedly, sequentially (`Iterator::for_each`) |
| `Fn()` | many times, `&` | only read | you call it concurrently or through `&` (shared handlers) |
| `fn()` pointer | many times | no captures | C callbacks, tables of functions, `Copy` + `'static` needed |

Every `Fn` is `FnMut`, every `FnMut` is `FnOnce`. Ask for the *least* capable trait that works: `FnOnce` accepts
the most closures.

```rust
use std::collections::HashMap;

// Parameters: generic (static dispatch) is the default.
pub fn retry<T, E>(attempts: u32, mut op: impl FnMut() -> Result<T, E>) -> Result<T, E> {
    let mut left = attempts.max(1);
    loop {
        match op() {
            Ok(v) => return Ok(v),
            Err(e) if left == 1 => return Err(e),
            Err(_) => left -= 1,
        }
    }
}

// Stored callbacks: boxed trait objects, Send + Sync if shared across threads.
type Handler = Box<dyn Fn(&str) -> String + Send + Sync>;

#[derive(Default)]
pub struct Router {
    routes: HashMap<String, Handler>,
}

impl Router {
    pub fn on(&mut self, path: &str, h: impl Fn(&str) -> String + Send + Sync + 'static) {
        self.routes.insert(path.to_owned(), Box::new(h));
    }

    pub fn call(&self, path: &str, body: &str) -> Option<String> {
        self.routes.get(path).map(|h| h(body))
    }
}

// Returning closures: impl Fn (one concrete type) or Box<dyn Fn> (several).
pub fn adder(n: i32) -> impl Fn(i32) -> i32 {
    move |x| x + n
}

fn main() {
    let mut calls = 0;
    let r: Result<u8, &str> = retry(3, || {
        calls += 1;
        if calls < 3 { Err("flaky") } else { Ok(7) }
    });
    assert_eq!(r, Ok(7));

    let mut router = Router::default();
    router.on("/echo", |b| b.to_uppercase());
    assert_eq!(router.call("/echo", "hi").as_deref(), Some("HI"));
    assert_eq!(adder(2)(3), 5);
}
```

`Router` has no `Debug` derive because `dyn Fn` is not `Debug`; implement Debug manually listing the route
keys if it is public.

## Async closures and AsyncFn (1.85)

Rust 1.85 stabilized async closures (`async || { .. }`, `async move |x| ..`) and the `AsyncFn`,
`AsyncFnMut`, `AsyncFnOnce` traits. They let a callback return a future that borrows from the closure's
captures, which `F: Fn() -> Fut` cannot express.

```rust
pub async fn with_retry<T, E>(attempts: u32, op: impl AsyncFn() -> Result<T, E>) -> Result<T, E> {
    let mut left = attempts.max(1);
    loop {
        match op().await {
            Ok(v) => return Ok(v),
            Err(e) if left == 1 => return Err(e),
            Err(_) => left -= 1,
        }
    }
}
```

There is no stable way to require the future returned by an `AsyncFn` to be `Send`. For callbacks whose
futures are spawned on a multi-threaded runtime keep the older form:

```rust
use std::future::Future;

pub async fn with_retry_send<T, E, F, Fut>(attempts: u32, op: F) -> Result<T, E>
where
    F: Fn() -> Fut,
    Fut: Future<Output = Result<T, E>> + Send,
{
    let mut left = attempts.max(1);
    loop {
        match op().await {
            Ok(v) => return Ok(v),
            Err(e) if left == 1 => return Err(e),
            Err(_) => left -= 1,
        }
    }
}
```

## Review checklist

- [ ] Public traits with async methods state their Send story (impl Future + Send, trait_variant, async_trait).
- [ ] Traits used as `dyn` have no `async fn`/RPITIT methods (or opt them out with `where Self: Sized`).
- [ ] `#[allow(async_fn_in_trait)]` only on traits that are public for internal reasons.
- [ ] Associated types for outputs determined by `Self`; generic parameters for inputs chosen by callers.
- [ ] Callback parameters ask for `FnOnce` < `FnMut` < `Fn` (least capable that works); stored callbacks are
      `Box<dyn Fn.. + Send + Sync>` when shared.
- [ ] GAT traits are small, tested with the generic consumers you intend, and not needed for `dyn`.
- [ ] MSRV noted for AFIT/RPITIT (1.75), associated type bounds (1.79), async closures (1.85).
