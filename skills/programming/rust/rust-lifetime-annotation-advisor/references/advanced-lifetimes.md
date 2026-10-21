# Advanced Lifetimes

Outlives bounds, variance, `PhantomData`, higher-ranked trait bounds, generic associated types, iterators that
hand out references, closures, and the places where the borrow checker is stricter than necessary. Every
block compiles on stable Rust 2021 unless it says otherwise.

## Contents

- [Outlives bounds: `'a: 'b` and `T: 'a`](#outlives-bounds-a-b-and-t-a)
- [Variance](#variance)
- [`PhantomData`](#phantomdata)
- [Higher-ranked trait bounds (HRTB)](#higher-ranked-trait-bounds-hrtb)
- [Iterators over borrowed data](#iterators-over-borrowed-data)
- [Lending iterators with GATs](#lending-iterators-with-gats)
- [Closures that take or return references](#closures-that-take-or-return-references)
- [When the checker is too strict](#when-the-checker-is-too-strict)

## Outlives bounds: `'a: 'b` and `T: 'a`

`'a: 'b` reads "`'a` outlives `'b`": data valid for `'a` is valid for at least `'b`. You rarely need it,
because covariance already shortens lifetimes for you. It appears when a function must return data of the
*longer* lifetime through a structure of the shorter one.

```rust
struct Context<'cfg> { prefix: &'cfg str }

// The returned &str lives as long as the config ('cfg), not as long as the short borrow of the context ('c).
fn prefix<'c, 'cfg: 'c>(ctx: &'c Context<'cfg>) -> &'cfg str {
    ctx.prefix
}
```

`T: 'a` means "every reference inside `T` lives at least `'a`". Since Rust 2018 the compiler infers these
bounds on struct fields (`struct Ref<'a, T> { r: &'a T }` no longer needs `where T: 'a`), but you still write
them on functions and impls that place a `T` behind `&'a`:

```rust
fn store<'a, T: 'a>(slot: &mut Vec<Box<dyn std::fmt::Debug + 'a>>, v: T)
where
    T: std::fmt::Debug,
{
    slot.push(Box::new(v)); // without T: 'a -> E0310 "the parameter type `T` may not live long enough"
}
```

## Variance

Variance decides whether `Type<'long>` may be used where `Type<'short>` is expected.

| Type | In `'a` | In `T` | Consequence |
|------|---------|--------|-------------|
| `&'a T` | covariant | covariant | a longer borrow can always be used as a shorter one |
| `&'a mut T` | covariant | **invariant** | `&mut Vec<&'static str>` cannot be passed as `&mut Vec<&'a str>` |
| `Box<T>`, `Vec<T>`, `Option<T>` | - | covariant | behave like `T` |
| `Cell<T>`, `RefCell<T>`, `UnsafeCell<T>` | - | invariant | interior mutability = mutation through `&` |
| `fn(T) -> U` | - | contravariant in `T`, covariant in `U` | |
| `*const T` / `*mut T` | - | covariant / invariant | |
| `PhantomData<X>` | as `X` | as `X` | used to *choose* variance |

Invariance is why `&'a mut X<'a>` hurts (LT007): the inner `'a` cannot shrink, so the outer mutable borrow
must last for all of `'a`.

```rust
fn push_local<'a>(v: &mut Vec<&'a str>, s: &'a str) {
    v.push(s);
}

fn demo() {
    let mut names: Vec<&'static str> = vec!["a"];
    let owned = String::from("b");
    // push_local(&mut names, &owned); // error: `owned` does not live long enough
    //                                 // (&mut is invariant: 'a is forced to 'static)
    let mut names2: Vec<&str> = names.clone(); // a Vec with a shorter element lifetime
    push_local(&mut names2, &owned);
    names.push("c");
}
```

## `PhantomData`

Use `PhantomData` when a type logically holds a lifetime or a `T` that no field mentions (E0392 otherwise).
Pick the form that gives the right variance and auto traits:

| Marker | Means | Variance | Send/Sync like |
|--------|-------|----------|---------------|
| `PhantomData<&'a T>` | borrows a `T` for `'a` | covariant in `'a`, `T` | `&'a T` |
| `PhantomData<&'a mut T>` | mutably borrows | covariant `'a`, invariant `T` | `&'a mut T` |
| `PhantomData<T>` | owns a `T` (drop check considers it) | covariant | `T` |
| `PhantomData<fn() -> T>` | produces `T`, owns none | covariant, no drop-check impact | always `Send + Sync` |
| `PhantomData<fn(T)>` | consumes `T` | contravariant | always `Send + Sync` |
| `PhantomData<*const T>` | opts out of `Send`/`Sync` | covariant | neither |

```rust
use std::marker::PhantomData;

/// A cursor into a buffer it does not store, tied to the buffer's lifetime.
struct Cursor<'buf> {
    ptr: *const u8,
    len: usize,
    _buf: PhantomData<&'buf [u8]>,
}

impl<'buf> Cursor<'buf> {
    fn new(buf: &'buf [u8]) -> Self {
        Cursor { ptr: buf.as_ptr(), len: buf.len(), _buf: PhantomData }
    }
    fn len(&self) -> usize { self.len }
}

/// A typed id that borrows nothing.
struct Id<T> { raw: u32, _t: PhantomData<fn() -> T> }
```

## Higher-ranked trait bounds (HRTB)

`for<'a> F: Fn(&'a str) -> &'a str` means "for every lifetime the caller picks, `F` works". It is what the
compiler writes for you when you elide lifetimes inside `Fn` sugar:

```rust
// These two bounds are identical:
fn apply<F: Fn(&str) -> &str>(f: F, s: &str) -> String { f(s).to_string() }
fn apply_explicit<F>(f: F, s: &str) -> String
where
    F: for<'a> Fn(&'a str) -> &'a str,
{
    f(s).to_string()
}
```

You write `for<'a>` explicitly when:

- the bound is not in `Fn` sugar: `where for<'a> &'a T: IntoIterator<Item = &'a u32>`
- you store such closures: `Box<dyn for<'a> Fn(&'a str) -> &'a str>` (the sugar works here too)
- a trait method takes a reference whose lifetime the implementor must accept for any caller

```rust
fn sum_all<T>(c: &T) -> u32
where
    for<'a> &'a T: IntoIterator<Item = &'a u32>,
{
    c.into_iter().sum()
}

fn main() {
    let v = vec![1, 2, 3];
    assert_eq!(sum_all(&v), 6);
}
```

A closure written inline does not always infer a higher-ranked signature; `|s: &str| s` may be inferred with
one specific lifetime, giving "expected signature `for<'a> fn(&'a str) -> &'a str`". Annotate the parameter
and return type, or pass it straight into a function with the `Fn` bound so the expected signature is known.

## Iterators over borrowed data

An iterator struct borrows its source; the items carry the source's lifetime, not the lifetime of `&mut self`
in `next`:

```rust
struct Lines<'a> { rest: &'a str }

impl<'a> Iterator for Lines<'a> {
    type Item = &'a str;                 // items outlive each call to next()

    fn next(&mut self) -> Option<&'a str> {
        if self.rest.is_empty() {
            return None;
        }
        let (line, rest) = self.rest.split_once('\n').unwrap_or((self.rest, ""));
        self.rest = rest;
        Some(line)
    }
}

fn lines(s: &str) -> Lines<'_> { Lines { rest: s } }
```

Returning an iterator from a function: `-> impl Iterator<Item = &'a T> + 'a` (2021) or plain
`-> impl Iterator<Item = &T>` (2024, captures automatically). `Box<dyn Iterator<Item = &'a T> + 'a>` when the
concrete type varies.

## Lending iterators with GATs

A *lending* iterator yields items that borrow the iterator itself (windows over an internal buffer). The
standard `Iterator` cannot express it because `Item` has no lifetime parameter. Generic associated types
(Rust 1.65) can:

```rust
trait LendingIterator {
    type Item<'a>
    where
        Self: 'a;

    fn next<'a>(&'a mut self) -> Option<Self::Item<'a>>;
}

struct WindowsMut<'t, T> { data: &'t mut [T], start: usize, size: usize }

impl<'t, T> LendingIterator for WindowsMut<'t, T> {
    type Item<'a> = &'a mut [T] where Self: 'a;

    fn next<'a>(&'a mut self) -> Option<&'a mut [T]> {
        let end = self.start + self.size;
        if end > self.data.len() {
            return None;
        }
        let w = &mut self.data[self.start..end];
        self.start += 1;
        Some(w)
    }
}

fn main() {
    let mut v = [1, 2, 3, 4];
    let mut it = WindowsMut { data: &mut v, start: 0, size: 2 };
    while let Some(w) = it.next() {
        w[0] += w[1];                    // each window is dropped before the next call
    }
    assert_eq!(v, [3, 5, 7, 4]);
}
```

The `where Self: 'a` clause is required on the GAT; the compiler asks for it. No `for` loop or adapters
come for free: consume with `while let`. Crates such as `lending-iterator` add adapters.

## Closures that take or return references

```rust
// Returning a closure that borrows an argument: tie the closure to the borrow.
fn contains_any<'a>(needles: &'a [&str]) -> impl Fn(&str) -> bool + 'a {
    move |hay| needles.iter().any(|n| hay.contains(n))
}

// Returning a reference from a closure parameter needs an explicit signature or a helper:
fn first_word(s: &str) -> &str { s.split(' ').next().unwrap_or("") }

fn main() {
    let f = contains_any(&["err", "warn"]);
    assert!(f("warn: disk"));
    let words: Vec<&str> = ["a b", "c d"].iter().map(|s| first_word(s)).collect();
    assert_eq!(words, ["a", "c"]);
}
```

`let g = |s: &str| -> &str { s };` fails to infer a higher-ranked signature on stable ("lifetime may not live
long enough"); use a `fn` item or pass the closure directly to a function whose bound says
`Fn(&str) -> &str`.

## When the checker is too strict

Some sound code is rejected by today's NLL checker; recognise it and use the standard workaround instead of
adding lifetimes:

| Shape | Symptom | Workaround |
|-------|---------|-----------|
| Return a borrow on one branch, mutate on the other (get-or-insert) | E0499/E0502, "returning this value requires that ..." | `entry` API; check with `contains_key` first; return an index |
| Cursor loop `while let Some(n) = cur.next.as_mut() { cur = n; }` | E0499 | test with `is_some()`, then borrow unconditionally |
| `&'a mut self` method on `impl<'a> S<'a>` | second call fails | `&mut self` (LT007) |
| Closure stored in a struct borrowing another field of the struct | self-reference | pass data as a closure argument, or split the struct |

These are covered with full code in the borrow-checker skill; the Polonius analysis (nightly) accepts the first
two.
