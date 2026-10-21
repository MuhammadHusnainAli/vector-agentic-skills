# Dispatch and Dyn Compatibility

How Rust calls trait methods, what each form costs, and the complete set of rules that decide whether a trait
can be used as `dyn Trait` ("object safety", renamed "dyn compatibility" in the Reference in 2024; newer
compilers say `the trait X is not dyn compatible`, older ones `the trait X cannot be made into an object`,
both error[E0038]).

## Contents

- [Three ways to accept "something that implements Trait"](#three-ways-to-accept-something-that-implements-trait)
- [What monomorphization costs](#what-monomorphization-costs)
- [What a trait object is](#what-a-trait-object-is)
- [Choosing: decision list](#choosing-decision-list)
- [Dyn compatibility rules](#dyn-compatibility-rules)
- [Fixing E0038 pattern by pattern](#fixing-e0038-pattern-by-pattern)
- [Clone for trait objects](#clone-for-trait-objects)
- [Comparing and hashing trait objects](#comparing-and-hashing-trait-objects)
- [Trait upcasting and downcasting with Any](#trait-upcasting-and-downcasting-with-any)
- [Lifetimes and auto traits on trait objects](#lifetimes-and-auto-traits-on-trait-objects)
- [Enum dispatch instead of dyn](#enum-dispatch-instead-of-dyn)
- [Returning impl Trait](#returning-impl-trait)
- [Review checklist](#review-checklist)

## Three ways to accept "something that implements Trait"

```rust
use std::fmt::Display;

// 1. Named generic parameter: callers may write render::<u32>(..); bounds can be reused.
pub fn render<T: Display>(value: T) -> String {
    format!("<{value}>")
}

// 2. impl Trait in argument position (Rust 1.26): an anonymous generic parameter.
//    Same machine code as (1); the parameter cannot be turbofished.
pub fn render_impl(value: impl Display) -> String {
    format!("<{value}>")
}

// 3. Trait object: one compiled function, dynamic dispatch through a vtable.
pub fn render_dyn(value: &dyn Display) -> String {
    format!("<{value}>")
}

fn main() {
    assert_eq!(render(5), "<5>");
    assert_eq!(render_impl("x"), "<x>");
    assert_eq!(render_dyn(&2.5), "<2.5>");
}
```

| Property | `T: Trait` | `impl Trait` (arg) | `&dyn Trait` / `Box<dyn Trait>` |
|----------|-----------|--------------------|-------------------------------|
| Dispatch | static | static | dynamic (vtable) |
| Inlining across the call | yes | yes | only if devirtualized |
| Copies of the function | one per type | one per type | one |
| Heterogeneous collections | no | no | yes |
| Turbofish | yes | no (1.63+: other explicit params may be given) | n/a |
| Trait must be dyn compatible | no | no | yes |
| Unsized values (`str`, `[T]`) | with `T: ?Sized` and a reference | `&(impl Trait + ?Sized)` | yes |
| Name the type in a struct field | `struct S<T: Trait> { t: T }` | no | `Box<dyn Trait>` |

`impl Trait` in argument position is sugar. Use the named form when the parameter appears twice
(`fn eq<T: PartialEq>(a: T, b: T)`), in a `where` clause, or when callers need turbofish.

## What monomorphization costs

Every distinct `T` gets its own copy of a generic function (and of every generic function it calls). That is
what makes iterators and closures zero-cost, but large generic functions instantiated for many types inflate
binary size and compile time. Two standard mitigations:

```rust
use std::io;
use std::path::Path;

// 1. Generic shell, non-generic inner function (std::fs::read_to_string does exactly this).
pub fn read_config<P: AsRef<Path>>(path: P) -> io::Result<String> {
    fn inner(path: &Path) -> io::Result<String> {
        let text = std::fs::read_to_string(path)?;
        Ok(text.trim().to_owned())
    }
    inner(path.as_ref())
}

// 2. Accept &mut dyn for heavy internals that do not need speed.
pub fn write_report(out: &mut dyn io::Write, rows: &[(String, u64)]) -> io::Result<()> {
    for (name, n) in rows {
        writeln!(out, "{name:<20}{n:>10}")?;
    }
    Ok(())
}

fn main() -> io::Result<()> {
    let mut buf = Vec::new();
    write_report(&mut buf, &[("docs".into(), 3)])?;
    assert!(String::from_utf8(buf).unwrap().starts_with("docs"));
    Ok(())
}
```

Measure with `cargo bloat --crates` / `cargo llvm-lines` before optimizing; most code never needs this.

## What a trait object is

`&dyn Trait` and `Box<dyn Trait>` are fat pointers: a data pointer plus a pointer to a vtable. The vtable
holds the concrete type's size, alignment, `drop_in_place`, and one function pointer per dispatchable
method (including supertrait methods). The concrete type is erased, so:

- Every method callable through the vtable must have a single, non-generic signature (one function pointer).
- The method cannot mention the erased type `Self` except through the pointer it is called on.
- The value itself is unsized (`dyn Trait: ?Sized`), so it always lives behind a pointer:
  `&`, `&mut`, `Box`, `Rc`, `Arc`, `Pin<Box<..>>`.

## Choosing: decision list

1. Do callers need to store different implementors together, or choose one at runtime (config, plugins)?
   Use `dyn`. Otherwise prefer generics.
2. Is the set of implementors closed and known to you? Consider an `enum` (exhaustive match, no vtable).
3. Is this a hot inner loop (per element, per byte)? Generics, so the call can inline.
4. Is it called a few times per request (a storage backend, an HTTP client)? `dyn` costs nothing measurable
   and keeps signatures and compile times small: `Arc<dyn Storage + Send + Sync>` is a fine default for
   application-level dependency injection.
5. Library API: offer generics at the edges (`impl AsRef<Path>`, `impl IntoIterator`) and keep the trait dyn
   compatible so users can choose either form.

## Dyn compatibility rules

A trait is dyn compatible when all of these hold:

| Rule | Example that breaks it |
|------|------------------------|
| No `Sized` supertrait (directly or through supertraits) | `trait Shape: Clone` (`Clone: Sized`), `trait Cfg: Default`, `trait P: FromStr` |
| No supertrait that uses `Self` as a type parameter | `trait Key: PartialEq` (`PartialEq<Rhs = Self>`), `Eq`, `PartialOrd`, `Ord` |
| All supertraits dyn compatible | `trait Plugin: Serialize` where `Serialize` has a generic method |
| No associated constants | `const ID: u32;` |
| No generic associated types | `type Item<'a> where Self: 'a;` |
| Every method is either dispatchable or marked `where Self: Sized` | see below |

A method is **dispatchable** when:

- it has a receiver: `&self`, `&mut self`, `self: Box<Self>`, `self: Rc<Self>`, `self: Arc<Self>`,
  `self: Pin<P>` where `P` is one of those;
- it has no type or const parameters (lifetime parameters are fine), and no `impl Trait` arguments;
- `Self` appears only in the receiver: not in other argument types, not in the return type
  (`Self::Assoc` projections are fine);
- it does not return an opaque type: no `async fn`, no `-> impl Trait` (RPITIT);
- it has no `where Self: Sized` bound (that is what makes it explicitly non-dispatchable).

Methods with `where Self: Sized` do not appear in the vtable and cannot be called on `dyn Trait`, but are
callable on every concrete type. That is the escape hatch for constructors, generic helpers and
`Self`-returning methods.

Associated types are allowed, but a trait object must name them: `Box<dyn Iterator<Item = u32>>`;
`Box<dyn Iterator>` is error[E0191].

Trait-level generic parameters are allowed: `dyn Codec<Json>` is a type. Each instantiation is a different
trait object type.

## Fixing E0038 pattern by pattern

```rust
use std::fmt::Debug;

pub trait Shape: Debug {
    // dispatchable
    fn area(&self) -> f64;
    fn name(&self) -> &str;

    // constructor: no receiver -> needs Self: Sized
    fn unit() -> Self
    where
        Self: Sized;

    // returns Self -> needs Self: Sized ...
    fn scaled(&self, k: f64) -> Self
    where
        Self: Sized;
    // ... and offer a dyn-friendly twin
    fn scaled_boxed(&self, k: f64) -> Box<dyn Shape>;

    // generic method -> needs Self: Sized, or make it non-generic
    fn describe_with<F: Fn(&str) -> String>(&self, f: F) -> String
    where
        Self: Sized,
    {
        f(self.name())
    }
    fn describe_dyn(&self, f: &dyn Fn(&str) -> String) -> String {
        f(self.name())
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Square(f64);

impl Shape for Square {
    fn area(&self) -> f64 {
        self.0 * self.0
    }
    fn name(&self) -> &str {
        "square"
    }
    fn unit() -> Self {
        Square(1.0)
    }
    fn scaled(&self, k: f64) -> Self {
        Square(self.0 * k)
    }
    fn scaled_boxed(&self, k: f64) -> Box<dyn Shape> {
        Box::new(self.scaled(k))
    }
}

fn main() {
    let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Square::unit()), Square(2.0).scaled_boxed(2.0)];
    let total: f64 = shapes.iter().map(|s| s.area()).sum();
    assert_eq!(total, 17.0);
    assert_eq!(shapes[1].describe_dyn(&|n| n.to_uppercase()), "SQUARE");
}
```

| Offending item | Options, best first |
|----------------|---------------------|
| `fn new(..) -> Self` | `where Self: Sized`; or move construction to a separate factory trait |
| `fn merge(&self, other: &Self)` | `where Self: Sized`; or `other: &dyn Trait` and downcast if the types must match |
| `fn process<T: Serialize>(&self, v: &T)` | take `&dyn erased_serde::Serialize`-style erased input, bytes, or a concrete enum; or `where Self: Sized` |
| `fn iter(&self) -> impl Iterator<Item = u8>` | `-> Box<dyn Iterator<Item = u8> + '_>` |
| `async fn get(&self)` | `#[async_trait]`, or `-> Pin<Box<dyn Future<Output = T> + Send + '_>>` (see [async-and-advanced-generics.md](async-and-advanced-generics.md)) |
| `const VERSION: u32;` | `fn version(&self) -> u32` |
| `trait T: Clone` | remove the supertrait, add `box_clone` (below) |
| `trait T: PartialEq` | `fn key(&self) -> Key` and compare keys, or `fn eq_dyn(&self, other: &dyn Any) -> bool` |
| GAT `type Item<'a>` | separate "lending" trait used only generically |

Test it once so it stays true: a function that takes `&dyn Trait` in the crate (or a doc test) turns a future
accidental break into a compile error in your CI, not in your users'.

```rust
#[allow(dead_code)]
fn _assert_dyn_compatible(_: &dyn std::fmt::Debug) {}
```

## Clone for trait objects

`Clone` requires `Sized`, so `Box<dyn Trait>` is not Clone by default. Add an object-safe clone method and
implement `Clone` for the box:

```rust
pub trait Filter: FilterClone {
    fn keep(&self, x: i32) -> bool;
}

pub trait FilterClone {
    fn box_clone(&self) -> Box<dyn Filter>;
}

// Blanket impl: every Clone + 'static filter gets box_clone for free.
impl<T: Filter + Clone + 'static> FilterClone for T {
    fn box_clone(&self) -> Box<dyn Filter> {
        Box::new(self.clone())
    }
}

impl Clone for Box<dyn Filter> {
    fn clone(&self) -> Self {
        self.box_clone()
    }
}

#[derive(Clone)]
struct Even;
impl Filter for Even {
    fn keep(&self, x: i32) -> bool {
        x % 2 == 0
    }
}

fn main() {
    let a: Box<dyn Filter> = Box::new(Even);
    let b = a.clone();
    assert!(b.keep(4));
}
```

The `dyn-clone` crate packages exactly this (`DynClone` supertrait plus `clone_trait_object!`).

## Comparing and hashing trait objects

`PartialEq` cannot be a supertrait of a dyn trait. Compare through `Any`:

```rust
use std::any::Any;

pub trait Node: Any {
    fn eq_dyn(&self, other: &dyn Node) -> bool;
}

impl<T: Any + PartialEq> Node for T {
    fn eq_dyn(&self, other: &dyn Node) -> bool {
        // Rust 1.86+: &dyn Node upcasts to &dyn Any.
        let other: &dyn Any = other;
        other.downcast_ref::<T>().is_some_and(|o| self == o)
    }
}

impl PartialEq for dyn Node {
    fn eq(&self, other: &Self) -> bool {
        self.eq_dyn(other)
    }
}

fn main() {
    let a: Box<dyn Node> = Box::new(3_u8);
    let b: Box<dyn Node> = Box::new(3_u8);
    let c: Box<dyn Node> = Box::new("3");
    assert!(*a == *b);
    assert!(*a != *c);
}
```

On compilers older than 1.86 add `fn as_any(&self) -> &dyn Any;` to the trait and implement it as `self`.
`Option::is_some_and` needs Rust 1.70.

## Trait upcasting and downcasting with Any

Since Rust 1.86 a trait object coerces to a trait object of any supertrait:

```rust
use std::any::Any;
use std::sync::Arc;

trait Named {
    fn name(&self) -> String;
}

trait Plugin: Named + Any + Send + Sync {
    fn run(&self) -> u32;
}

struct Echo;
impl Named for Echo {
    fn name(&self) -> String {
        "echo".into()
    }
}
impl Plugin for Echo {
    fn run(&self) -> u32 {
        7
    }
}

fn main() {
    let p: Arc<dyn Plugin> = Arc::new(Echo);
    let named: Arc<dyn Named> = p.clone(); // upcast (1.86+)
    assert_eq!(named.name(), "echo");

    let any: &dyn Any = &*p; // upcast to Any
    assert!(any.downcast_ref::<Echo>().is_some());
    assert_eq!(p.run(), 7);
}
```

Notes:
- `Any` requires `'static`: plugins holding borrowed data cannot use it.
- `Box<dyn Any>::downcast::<T>()` returns `Result<Box<T>, Box<dyn Any>>`; `Arc<dyn Any + Send + Sync>` has
  `downcast` too.
- Downcasting is a smell in most designs. Prefer adding the needed method to the trait.

## Lifetimes and auto traits on trait objects

| Written | Means |
|---------|-------|
| `Box<dyn Trait>` | `Box<dyn Trait + 'static>` |
| `&'a dyn Trait` | `&'a (dyn Trait + 'a)` |
| `Box<dyn Trait + 'a>` | may borrow data living for `'a` |
| `Arc<dyn Trait>` used across threads | needs `dyn Trait + Send + Sync`, or `trait Trait: Send + Sync` |

Only auto traits (`Send`, `Sync`, `Unpin`, `UnwindSafe`, `RefUnwindSafe`) may be added with `+`. Two
regular traits are error[E0225]; define a combined trait:

```rust
use std::io::{Read, Write};

pub trait Stream: Read + Write + Send {}
impl<T: Read + Write + Send> Stream for T {}

pub fn handshake(conn: &mut dyn Stream) -> std::io::Result<()> {
    conn.write_all(b"HELLO\n")?;
    let mut buf = [0_u8; 3];
    conn.read_exact(&mut buf)?;
    Ok(())
}
```

Putting `Send + Sync` as supertraits (`trait Storage: Send + Sync`) forces every implementor to be
thread-safe and lets you write `Arc<dyn Storage>` without repeating bounds. Leave them off when
single-threaded implementations (`Rc`, `RefCell`) are legitimate, and write `dyn Storage + Send + Sync` at
the use sites that need it.

A method returning a borrowed trait object needs the right lifetime:
`fn items(&self) -> Box<dyn Iterator<Item = &Item> + '_>`; without `+ '_` the box defaults to `'static` and the
borrow of `self` is rejected.

## Enum dispatch instead of dyn

When you own every implementor:

```rust
pub enum Backend {
    Memory(Vec<u8>),
    File(std::path::PathBuf),
}

impl Backend {
    pub fn describe(&self) -> String {
        match self {
            Backend::Memory(v) => format!("memory ({} bytes)", v.len()),
            Backend::File(p) => format!("file {}", p.display()),
        }
    }
}
```

Pros: no allocation, inlinable, exhaustive matching, values are `Sized` and can be `Clone`/`PartialEq`.
Cons: closed set; adding a variant to a public enum is breaking unless `#[non_exhaustive]`. The
`enum_dispatch` crate generates the forwarding `impl Trait for Enum` when you want both.

## Returning impl Trait

`-> impl Trait` returns one concrete type chosen by the function body, hidden from the caller.

- One function can return only one concrete type: two closures in `if`/`else` are two types. Use
  `Box<dyn Fn..>`, `either::Either`, or an enum.
- Auto traits leak: callers can rely on the hidden type being `Send` if it is. Changing the body so the
  returned future or iterator stops being `Send` is a breaking change nobody sees in the signature.
- Lifetime capture: in edition 2024 `impl Trait` in return position captures all in-scope generic and lifetime
  parameters; in 2021 it captured type parameters but only the lifetimes named in the bounds. Rust 1.82
  stabilized precise capturing, `-> impl Iterator<Item = u8> + use<'a, T>`, to say exactly what is captured.
  The classic 2021 error is E0700 ("hidden type captures lifetime that does not appear in bounds").

```rust
pub fn evens(limit: u32) -> impl Iterator<Item = u32> + Clone {
    (0..limit).filter(|n| n % 2 == 0)
}

pub fn words(text: &str) -> impl Iterator<Item = &str> + '_ {
    text.split_whitespace()
}

fn main() {
    assert_eq!(evens(7).collect::<Vec<_>>(), [0, 2, 4, 6]);
    assert_eq!(words("a b").count(), 2);
}
```

## Review checklist

- [ ] Every trait used as `dyn` anywhere has a `&dyn Trait` usage in the crate (compile-time guard).
- [ ] Constructors, generic helpers and `Self`-returning methods carry `where Self: Sized`.
- [ ] No `Clone`/`Default`/`PartialEq` supertraits on traits meant for `dyn`; `box_clone` where needed.
- [ ] Trait objects stored in shared state are `dyn Trait + Send + Sync` (or the trait has those supertraits).
- [ ] Borrowed trait objects have explicit lifetimes (`+ '_`).
- [ ] Hot loops use generics; plumbing uses `dyn` where it simplifies signatures.
- [ ] `dyn_compat` reports no TR001.
