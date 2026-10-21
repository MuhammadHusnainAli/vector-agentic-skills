# Trait Objects, 'static and impl Trait Lifetimes

Three places where lifetimes appear without being written: the default lifetime of a trait object, the meaning
of `T: 'static`, and which lifetimes a returned `impl Trait` captures (which changed in edition 2024).

## Contents

- [Default object lifetime rules](#default-object-lifetime-rules)
- [dyn Trait + 'a in structs and returns](#dyn-trait--a-in-structs-and-returns)
- [impl dyn Trait blocks](#impl-dyn-trait-blocks)
- [What T: 'static really means](#what-t-static-really-means)
- [E0310 and where 'static comes from](#e0310-and-where-static-comes-from)
- [T: 'a and 'a: 'b bounds](#t-a-and-a-b-bounds)
- [impl Trait in argument position](#impl-trait-in-argument-position)
- [Return-position impl Trait: capture rules](#return-position-impl-trait-capture-rules)
- [Precise capturing with use<..> (1.82)](#precise-capturing-with-use-182)
- [Migrating to edition 2024](#migrating-to-edition-2024)
- [impl Trait in traits and async fn](#impl-trait-in-traits-and-async-fn)

## Default object lifetime rules

Every trait object type has a lifetime bound: `dyn Trait + 'x`. When you do not write it, the compiler uses
the *default object lifetime bound* (this is not elision):

| Written | Means | Rule |
|---------|-------|------|
| `Box<dyn Trait>` | `Box<dyn Trait + 'static>` | container type has no lifetime bound on its parameter -> `'static` |
| `Rc<dyn Trait>`, `Arc<dyn Trait>`, `Vec<Box<dyn Trait>>` | `+ 'static` | same |
| `&'a dyn Trait` | `&'a (dyn Trait + 'a)` | a reference's lifetime becomes the default |
| `&'a mut dyn Trait` | `&'a mut (dyn Trait + 'a)` | same |
| `Ref<'a, dyn Trait>` where `struct Ref<'a, T: ?Sized + 'a>` | `dyn Trait + 'a` | the container's `T: 'a` bound is used |
| `&dyn Trait` in a fn signature | `&'1 (dyn Trait + '1)` | elided reference lifetime, then the rule above |
| `Box<dyn Trait + '_>` in a fn signature | elided lifetime, per normal elision | `'_` opts into elision |
| `dyn Trait` where `trait Trait: 'a` | `'a` | the trait's own lifetime bound is the default |
| `impl dyn Trait { .. }` | `impl dyn Trait + 'static` | see below |

So the most common surprise: a `Box<dyn Fn(&str)>` field or return type can never hold a closure that
borrows anything non-`'static`.

## dyn Trait + 'a in structs and returns

```rust
use std::fmt::Display;

pub struct Report<'a> {
    // Each formatter may borrow from the data the report is about.
    columns: Vec<Box<dyn Fn(usize) -> String + 'a>>,
}

impl<'a> Report<'a> {
    pub fn new() -> Self {
        Self { columns: Vec::new() }
    }

    pub fn column(mut self, f: impl Fn(usize) -> String + 'a) -> Self {
        self.columns.push(Box::new(f));
        self
    }

    pub fn row(&self, i: usize) -> Vec<String> {
        self.columns.iter().map(|c| c(i)).collect()
    }
}

// Returning a boxed iterator that borrows an argument: say '_ (or a named lifetime).
pub fn labels<'a, T: Display>(items: &'a [T]) -> Box<dyn Iterator<Item = String> + 'a> {
    Box::new(items.iter().map(|x| x.to_string()))
}

fn main() {
    let names = vec!["ada".to_string(), "grace".to_string()];
    let report = Report::new().column(|i| names[i].to_uppercase()); // borrows `names`
    println!("{:?}", report.row(1));
    println!("{:?}", labels(&[1, 2]).collect::<Vec<_>>());
}
```

Without `+ 'a` on the field, `column(|i| names[i]...)` fails with "`names` does not live long enough ...
argument requires that `names` is borrowed for `'static`" (or E0521 in a function taking `&[String]`).

When the object should be `'static` (stored in a global registry, sent to a thread), keep the default and own
the captured data (`move` + `String`/`Arc`). `static_bounds` (LT011) points at `Box<dyn ..>` fields in
structs that already borrow (`struct X<'a>`), because that combination is usually a mistake.

For errors, `Box<dyn Error + Send + Sync>` (implicitly `'static`) is the conventional type; it requires error
values that own their data, which is one more reason error structs should not carry lifetimes.

## impl dyn Trait blocks

Inherent methods on a trait object type default to `dyn Trait + 'static`:

```rust
pub trait Shape {
    fn area(&self) -> f64;
}

// impl dyn Shape { fn describe(&self) -> String { .. } }
// calling describe() on a `&dyn Shape` that borrows non-'static data fails
// (older compilers: E0772 "`self` has an anonymous lifetime `'_` but calling `describe` introduces
// an implicit `'static` lifetime requirement").
impl dyn Shape + '_ {
    pub fn describe(&self) -> String {
        format!("shape with area {:.1}", self.area())
    }
}

struct Square<'a>(&'a f64);

impl Shape for Square<'_> {
    fn area(&self) -> f64 {
        self.0 * self.0
    }
}

fn main() {
    let side = 2.0;
    let sq = Square(&side);
    let s: &dyn Shape = &sq;
    println!("{}", s.describe());
}
```

## What T: 'static really means

`T: 'static` reads "values of type `T` contain no references shorter than `'static`" (they own all their
data, or borrow only static data). It says nothing about how long a particular value lives.

| Type | `T: 'static`? | Why |
|------|---------------|-----|
| `String`, `Vec<u8>`, `u64`, `Box<str>` | yes | owns everything |
| `Arc<Mutex<Config>>` | yes | owns (shares) everything |
| `&'static str` | yes | borrows only static data |
| `&'a str` (non-static `'a`) | no | contains a shorter borrow |
| `Vec<&'a str>` | no | contains a shorter borrow |
| `Cow<'static, str>` | yes | |
| `Box<dyn Fn()>` | yes | `dyn Fn() + 'static` by default |

Common misconceptions:

1. **"`T: 'static` means the value lives until the program ends."** A `String` satisfies `'static` and is
   dropped at the end of its scope like any other value. The bound only means it *could* be kept forever.
2. **"`T: 'static` means `T` is `&'static something`."** Owned types satisfy it too; that is the normal case.
3. **"To fix E0310 I need `Box::leak`."** You need the value to *own* its data: convert `&str` to `String`,
   clone into an `Arc`, or restructure so the borrow does not escape (scoped threads, `+ 'a` objects).
4. **"`&'static T` and `T: 'static` are interchangeable."** `fn f(x: &'static str)` refuses a `String`'s
   contents; `fn f<T: AsRef<str> + 'static>(x: T)` accepts a `String`.
5. **"Adding `'static` everywhere is harmless."** It rejects every borrowed instantiation of a generic and
   spreads to callers. Ask for it only where data escapes (LT009 flags borrow-only functions).

`Box::leak(Box::new(value))` does produce a `&'static mut T`; reserve it for once-per-process data such as
configuration loaded at startup (or use `std::sync::OnceLock`, 1.70+, or `LazyLock`, 1.80+).

## E0310 and where 'static comes from

The requirement always has a source. Find it in the diagnostic ("...so that the type `T` will meet its
required lifetime bounds", "argument requires that ... is borrowed for `'static`") and decide at that point.

| Source of `'static` | Why it needs it | Options |
|---------------------|-----------------|---------|
| `std::thread::spawn` | thread may outlive the caller | `move` owned data / `Arc`; `std::thread::scope` (1.63+) to borrow |
| `tokio::spawn` | task may outlive the caller | owned data / `Arc`; `JoinSet` still needs `'static`; restructure as `join!` / `FuturesUnordered` in the same task to borrow |
| `Box<dyn Trait>` (default) | object bound defaults to `'static` | `Box<dyn Trait + 'a>` |
| `dyn Any`, `TypeId::of::<T>()`, `downcast_ref` | `Any: 'static` | own the data; `Any` cannot hold borrows |
| `static` / `OnceLock` / `lazy_static` | lives for the whole program | own the data |
| a trait with `trait Plugin: 'static` | supertrait bound | remove the bound if not needed |

```rust
use std::any::Any;
use std::fmt::Debug;

// E0310 without 'static: Box<dyn Any> requires T: 'static.
fn erase<T: Any>(value: T) -> Box<dyn Any> {
    Box::new(value)
}

// Only borrowing T: no 'static needed.
fn show<T: Debug + ?Sized>(value: &T) -> String {
    format!("{value:?}")
}

fn main() {
    let any = erase(String::from("owned"));
    assert!(any.downcast_ref::<String>().is_some());
    let local = String::from("borrowed");
    let words: Vec<&str> = local.split(' ').collect();
    println!("{}", show(&words)); // Vec<&str> is not 'static: fine here
}
```

## T: 'a and 'a: 'b bounds

- `T: 'a` - every reference inside `T` outlives `'a`. Required to form `&'a T`. Since Rust 1.31 (RFC 2093)
  these bounds are inferred for struct fields, so `struct Ref<'a, T> { r: &'a T }` needs no `T: 'a`.
  You still write them on trait objects (`Box<dyn Trait + 'a>`), on generic functions that build
  `&'a T` from scratch, and on GAT where clauses (`where Self: 'a`).
- `'long: 'short` - `'long` outlives `'short`. Needed when a function returns data of one lifetime through a
  reference of another, or a struct holds two related borrows.

```rust
// The cache reference may be shorter than the data it hands out.
struct Cache<'data> {
    items: Vec<&'data str>,
}

fn first<'c, 'data: 'c>(cache: &'c Cache<'data>) -> &'data str {
    cache.items.first().copied().unwrap_or("")
}
```

(`'data: 'c` is implied here by the type `&'c Cache<'data>` being well-formed, so it can be omitted; writing
it documents the relationship.)

## impl Trait in argument position

`fn f(x: impl Trait)` is sugar for an anonymous generic parameter. Lifetimes inside it follow the normal rules:
`impl Fn(&str) -> &str` is higher-ranked over the reference, and an `impl Iterator<Item = &str>` argument gets
a fresh elided lifetime. The caller cannot name the type with turbofish.

## Return-position impl Trait: capture rules

The returned *hidden type* (say `Filter<Iter<'a, u32>, {closure}>`) may only mention generic parameters the
opaque type *captures*. Capturing a lifetime means callers must treat the result as borrowing it.

| Position / edition | Type & const params | Lifetime params (incl. elided) |
|--------------------|---------------------|--------------------------------|
| free fn / inherent method, edition 2015-2021 | all in scope captured | only those named in the bounds (`+ 'a`, `+ '_`, `+ use<'a>`) |
| free fn / inherent method, edition 2024 | all captured | **all in scope captured** |
| `async fn` (all editions) | all | all |
| `-> impl Trait` in a trait or trait impl (RPITIT, 1.75+) | all | all |
| with `+ use<..>` (1.82+) | exactly the listed ones (in 1.82 every type param must be listed) | exactly the listed ones |

Edition 2021 failure (E0700) and its fixes:

```rust
// error[E0700] in edition 2021: hidden type captures lifetime that does not appear in bounds
// fn evens(xs: &[u32]) -> impl Iterator<Item = u32> { xs.iter().copied().filter(|x| x % 2 == 0) }

fn evens(xs: &[u32]) -> impl Iterator<Item = u32> + '_ {
    xs.iter().copied().filter(|x| x % 2 == 0)
}
```

`+ 'a` is an *outlives* bound that happens to force capture. With two lifetimes it is wrong:
`fn f<'a, 'b>(x: &'a str, y: &'b str) -> impl Iterator<Item = char> + 'a` cannot return something that
captures `'b`. Before `use<..>` the workaround was the `Captures` trick:

```rust
trait Captures<'a> {}
impl<'a, T: ?Sized> Captures<'a> for T {}

// Pre-1.82, edition 2021: capture both lifetimes without claiming the result outlives either.
fn zip_chars<'a, 'b>(x: &'a str, y: &'b str) -> impl Iterator<Item = (char, char)> + Captures<'a> + Captures<'b> {
    x.chars().zip(y.chars())
}
```

With Rust 1.82+ write `-> impl Iterator<Item = (char, char)> + use<'a, 'b>` instead, or rely on edition 2024.

## Precise capturing with use<..> (1.82)

`use<..>` lists exactly what the opaque type may capture. It works in every edition from Rust 1.82.

```rust
// Edition 2024: without use<T>, this would capture the slice lifetime and keep `v` borrowed.
fn indices<T>(xs: &[T]) -> impl Iterator<Item = usize> + use<T> {
    0..xs.len()
}

fn main() {
    let mut v = vec![10, 20, 30];
    let it = indices(&v);
    v.push(40); // allowed: `it` does not borrow `v`
    for i in it {
        println!("{i}");
    }
}
```

Rules worth knowing:
- `use<>` captures nothing; `use<'a, T>` captures `'a` and `T`.
- In Rust 1.82 all type and const parameters in scope must appear in the list; only lifetimes can be omitted.
- Only one `use<..>` bound is allowed per `impl Trait`.
- In trait definitions (RPITIT) all parameters are always captured; `use<..>` support there arrived after
  1.82, so check your toolchain before using it in traits.

## Migrating to edition 2024

- `cargo fix --edition` runs the `impl_trait_overcaptures` lint, which adds `use<..>` where the new rules
  would capture more than before and change borrow-checking for callers.
- After migrating, new code can usually drop `+ '_`/`Captures` workarounds: the default now captures.
- Add `use<..>` when callers need to keep using an argument while holding the result (iterators over
  owned copies, builders that return an independent value).
- Edition 2024 needs Rust 1.85+ and `edition = "2024"` in `Cargo.toml`. `lifetime_smells` (LT012) lists
  every `-> impl Trait` with borrowed inputs and no `use<..>` when the crate is on 2024.

## impl Trait in traits and async fn

- `async fn` in traits and `-> impl Trait` in traits are stable since Rust 1.75. Their returned types capture
  all generic parameters, including all input lifetimes.
- Callers cannot add `Send` to the returned future of a trait's `async fn`. If implementors are used with
  `tokio::spawn`, declare the method as `fn get(&self) -> impl Future<Output = T> + Send;` (implementors can
  still write `async fn`) or use the `trait-variant` crate to generate a `Send` variant.
- `async fn` in traits is not dyn-compatible (object safe); for `dyn Trait` use `Pin<Box<dyn Future + Send
  + '_>>` returns (the `async-trait` crate generates exactly that, with `'async_trait` lifetimes).
