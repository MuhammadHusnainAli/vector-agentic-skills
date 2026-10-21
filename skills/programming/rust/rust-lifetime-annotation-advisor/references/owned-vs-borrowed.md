# Owned vs Borrowed: Removing Lifetimes by Design

Most lifetime pain comes from structs that borrow when they could own. This reference gives the cost model for
each string/slice representation, rules for when a struct should carry a lifetime, and refactorings that delete
lifetime parameters without measurable cost.

## Contents

- [The representations](#the-representations)
- [Cost model](#cost-model)
- [Function parameters: accept the most general borrow](#function-parameters-accept-the-most-general-borrow)
- [Return values](#return-values)
- [Struct fields: views vs values](#struct-fields-views-vs-values)
- [Cow in practice](#cow-in-practice)
- [Arc<str> and Rc<str>: shared immutable text](#arcstr-and-rcstr-shared-immutable-text)
- [Rc/Arc as an escape from lifetime soup](#rcarc-as-an-escape-from-lifetime-soup)
- [Refactoring a borrowing struct to an owning one](#refactoring-a-borrowing-struct-to-an-owning-one)
- [When borrowing is worth it](#when-borrowing-is-worth-it)
- [Checklist](#checklist)

## The representations

| Type | Owns? | Size (64-bit) | Mutable? | Lifetime param? | Typical use |
|------|-------|---------------|----------|-----------------|-------------|
| `&'a str` | no | 16 (ptr + len) | no | yes | parameters, short-lived views, parsers |
| `String` | yes | 24 (ptr + len + cap) | yes | no | building text, struct fields |
| `Box<str>` | yes | 16 | no (fixed length) | no | many immutable strings stored long-term |
| `Cow<'a, str>` | maybe | 24 or 32 (compiler-dependent) | via `to_mut()` | yes | "usually borrowed, sometimes rewritten" |
| `Cow<'static, str>` | maybe | as `Cow<'a, str>` | via `to_mut()` | no | literals and runtime strings in one field |
| `Rc<str>` / `Arc<str>` | shared | 16 | no | no | interned names, config, keys cloned often |
| `Arc<String>` | shared | 8 | no | no | avoid: double indirection; prefer `Arc<str>` |
| `&'a [T]` / `Vec<T>` / `Box<[T]>` / `Arc<[T]>` | as above | 16 / 24 / 16 / 16 | as above | as above | same trade-offs for slices |

Sizes are for the handle; heap bytes come on top. Check exact sizes with `std::mem::size_of` rather than
relying on layout.

## Cost model

| Operation | `&str` | `String` | `Arc<str>` | `Cow<str>` |
|-----------|--------|----------|------------|------------|
| Create from a literal | free | alloc + copy | alloc + copy | free (`Borrowed`) |
| Create from a `String` you own | borrow, free | move, free | alloc + copy (`Arc::from(s)`) | move into `Owned`, free |
| Clone | copy 16 bytes | alloc + copy | atomic increment | free if `Borrowed`, alloc if `Owned` |
| Drop | nothing | free | atomic decrement (+ free at zero) | free if `Owned` |
| Send to another thread / task | only if `'static` | yes | yes | only if `'static` |
| Store in a long-lived struct | struct gets `'a` | no lifetime | no lifetime | `'a` unless `'static` |

An allocation is tens of nanoseconds. A lifetime parameter costs every user of the type: every function that
mentions it, every struct that contains it, every trait object that holds it. In application code (services,
CLIs, agents) clone first; borrow in measured hot paths and in libraries whose whole point is zero-copy.

## Function parameters: accept the most general borrow

Parameters should usually borrow, because borrowing never forces the caller to give anything up.

| Want | Parameter type | Accepts |
|------|----------------|---------|
| read text | `&str` | `&String` (deref coercion), literals, slices |
| read a list | `&[T]` | `&Vec<T>`, arrays, slices |
| read a path | `&Path` or `impl AsRef<Path>` | `&str`, `String`, `PathBuf`, `&Path` |
| keep the text (store it) | `String` or `impl Into<String>` | caller decides whether to clone or move |
| keep shared text | `Arc<str>` or `impl Into<Arc<str>>` | caller clones the `Arc` |
| maybe keep it | `Cow<'_, str>` / `impl Into<Cow<'a, str>>` | literals without allocation |

Taking `String` when you store the value is not wasteful: if the caller has a `String` they move it (no copy);
if they have a `&str`, they write `.to_owned()` and the cost is visible. Taking `&str` and cloning internally
hides an allocation and forces a copy even when the caller could have moved.

```rust
pub struct User {
    name: String,
}

impl User {
    // Caller moves a String in, or passes "literal" and pays one allocation.
    pub fn new(name: impl Into<String>) -> Self {
        Self { name: name.into() }
    }

    pub fn name(&self) -> &str {
        &self.name
    }
}

fn main() {
    let a = User::new("ada");
    let b = User::new(String::from("grace"));
    println!("{} {}", a.name(), b.name());
}
```

## Return values

| Returned data | Return type |
|---------------|-------------|
| part of an input | `&str` / `&[T]` (elided or tied with `'a`) |
| part of an input, sometimes modified | `Cow<'_, str>` |
| newly built | `String` / `Vec<T>` |
| a fixed set of literals | `&'static str` |
| many items borrowing an input | `impl Iterator<Item = &str> + '_` |
| shared with other owners | `Arc<str>` / `Arc<T>` |

Never return a reference to a local (E0515). If you are tempted to add a lifetime to make it compile, return
the owned value instead.

## Struct fields: views vs values

A struct with a lifetime parameter is a **view**: it is valid only while what it borrows is alive, cannot be
returned past its source, cannot be sent to `tokio::spawn`, cannot be stored in a `static`, and every type that
contains it needs the parameter too.

Good views:

```rust
/// Created, used and dropped within one function call.
pub struct Lexer<'src> {
    src: &'src str,
    pos: usize,
}

/// A borrowed window over a buffer, like std::slice::Iter.
pub struct Rows<'a> {
    data: &'a [f32],
    width: usize,
}

impl<'a> Iterator for Rows<'a> {
    type Item = &'a [f32];

    fn next(&mut self) -> Option<&'a [f32]> {
        if self.data.is_empty() || self.width == 0 {
            return None;
        }
        let n = self.width.min(self.data.len());
        let (row, rest) = self.data.split_at(n);
        self.data = rest;
        Some(row)
    }
}
```

Bad views (should own):

| Struct | Problem | Owning version |
|--------|---------|----------------|
| `struct Config<'a> { name: &'a str, url: &'a str }` | lives for the whole program; every service struct now needs `'a` | `name: String, url: String` or `Arc<str>` |
| `struct Request<'a> { body: &'a [u8] }` passed to a spawned task | `tokio::spawn` needs `'static` | `body: bytes::Bytes` or `Vec<u8>` |
| `struct AppError<'a> { path: &'a Path }` | errors propagate up with `?` past the borrowed data | `path: PathBuf` |
| `struct Cache<'a> { entries: HashMap<&'a str, Entry> }` | keys borrowed from what? cache outlives requests | `HashMap<String, Entry>` or `HashMap<Arc<str>, Entry>` |
| `struct Session<'a, 'b, 'c>` | three lifetimes infect every caller | own, or split into an owned core + short-lived view |

Error types in particular should be `'static` so they can be boxed into `Box<dyn Error + Send + Sync>`,
`anyhow::Error`, or returned from `main`.

## Cow in practice

`Cow<'a, B>` ("clone on write") holds either `&'a B` or `B::Owned`. It derefs to `&B`, so readers do not care
which variant they have.

```rust
use std::borrow::Cow;

/// Escape HTML only when needed: most inputs are returned borrowed (no allocation).
pub fn escape_html(input: &str) -> Cow<'_, str> {
    if !input.contains(|c| matches!(c, '<' | '>' | '&')) {
        return Cow::Borrowed(input);
    }
    let mut out = String::with_capacity(input.len() + 8);
    for ch in input.chars() {
        match ch {
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '&' => out.push_str("&amp;"),
            c => out.push(c),
        }
    }
    Cow::Owned(out)
}

/// A field that accepts literals for free and runtime strings by value, without a lifetime.
pub struct Column {
    pub name: Cow<'static, str>,
}

fn main() {
    let a = escape_html("plain");
    let b = escape_html("a < b");
    assert!(matches!(a, Cow::Borrowed(_)));
    assert_eq!(b, "a &lt; b");

    let fixed = Column { name: Cow::Borrowed("id") };
    let dynamic = Column { name: Cow::Owned(format!("col_{}", 3)) };
    println!("{} {}", fixed.name, dynamic.name);
}
```

Useful `Cow` methods: `to_mut()` (clones into `Owned` on first write), `into_owned()` (get a `String`, cloning
only if borrowed), `is_borrowed()`/`is_owned()` are unstable, so match on the variant instead.

`Cow` keeps the lifetime parameter unless you use `Cow<'static, str>`. If a struct field is
`Cow<'a, str>` and the struct is long-lived, you have not removed the lifetime: call `into_owned()` at the
boundary.

## Arc<str> and Rc<str>: shared immutable text

```rust
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Clone, Debug)]
pub struct Model {
    pub name: Arc<str>,
    pub provider: Arc<str>,
}

fn main() {
    let provider: Arc<str> = Arc::from("local");
    let mut by_name: HashMap<Arc<str>, Model> = HashMap::new();
    for raw in ["small", "large"] {
        let name: Arc<str> = Arc::from(raw);
        let model = Model { name: Arc::clone(&name), provider: Arc::clone(&provider) };
        by_name.insert(name, model); // key and value share the same allocation
    }
    // HashMap<Arc<str>, _> can be queried with &str because Arc<str>: Borrow<str>.
    println!("{:?}", by_name.get("small").map(|m| &*m.provider));
}
```

- `Arc<str>` is one allocation (refcounts + bytes) and a 16-byte handle; `Arc<String>` is two allocations.
- Conversions: `Arc::<str>::from("lit")`, `Arc::<str>::from(string)` (copies the bytes into the new
  allocation), `Arc::<str>::from(cow)`.
- Use `Rc<str>` in single-threaded code (non-atomic counts), `Arc<str>` when anything is `Send`.
- For many small strings with heavy cloning, interning (a `HashSet<Arc<str>>` or crates such as `lasso`) turns
  string comparisons into pointer comparisons.

## Rc/Arc as an escape from lifetime soup

When borrows form a web (A borrows B, which borrows C, and A must outlive the function that created C), shared
ownership removes all of them at the cost of refcounting.

```rust
use std::sync::Arc;

pub struct Schema {
    pub fields: Vec<String>,
}

// Before: struct Validator<'s> { schema: &'s Schema } and struct Pipeline<'s> { v: Validator<'s> }
// After: no lifetimes; validators can be stored, cloned, sent to threads.
#[derive(Clone)]
pub struct Validator {
    schema: Arc<Schema>,
}

impl Validator {
    pub fn new(schema: Arc<Schema>) -> Self {
        Self { schema }
    }

    pub fn check(&self, field: &str) -> bool {
        self.schema.fields.iter().any(|f| f == field)
    }
}

fn main() {
    let schema = Arc::new(Schema { fields: vec!["id".into(), "name".into()] });
    let v = Validator::new(Arc::clone(&schema));
    let handle = std::thread::spawn(move || v.check("id"));
    assert!(handle.join().unwrap());
}
```

Costs: an atomic increment per clone and decrement per drop (uncontended: a few nanoseconds), one extra pointer
hop on access, and shared data is immutable unless you add `Mutex`/`RwLock`/atomics. Cycles of `Rc`/`Arc`
leak; break them with `Weak` (parent pointers) or use indices.

## Refactoring a borrowing struct to an owning one

Before:

```rust
pub struct Job<'a> {
    pub id: &'a str,
    pub tags: Vec<&'a str>,
}

pub fn parse_job(line: &str) -> Job<'_> {
    let mut parts = line.split(',');
    let id = parts.next().unwrap_or("");
    Job { id, tags: parts.collect() }
}
```

Every function storing a `Job` now needs `'a`, and `parse_job(&read_line())` fails with E0716 because the
line is a temporary. After:

```rust
#[derive(Clone, Debug)]
pub struct Job {
    pub id: String,
    pub tags: Vec<String>,
}

pub fn parse_job(line: &str) -> Job {
    let mut parts = line.split(',');
    let id = parts.next().unwrap_or("").to_owned();
    Job { id, tags: parts.map(str::to_owned).collect() }
}
```

Cost: one allocation per field. If profiling shows it matters, keep both: a borrowed `JobRef<'a>` for the hot
parse loop and `impl JobRef<'_> { fn to_owned(&self) -> Job }` at the storage boundary (the
`serde_json::Value` vs `&RawValue`, `String` vs `&str` pattern).

## When borrowing is worth it

- Zero-copy parsers and deserialisers over large inputs (`serde` with `#[serde(borrow)]`, `nom`, tokenizers).
- Iterators and adaptors (`Iter<'a, T>`, `Chars<'a>`, `Split<'a, P>`): they must borrow.
- Guards and handles that release something on drop (`MutexGuard<'a, T>`, `Ref<'a, T>`, transactions).
- Hot loops where profiling shows allocation dominates.
- APIs returning parts of `self` (`fn name(&self) -> &str`): borrow from self is free and elided.

## Checklist

- Parameters borrow (`&str`, `&[T]`, `&Path`); parameters you store are owned (`String`, `impl Into<String>`).
- Long-lived structs, errors, configs, messages and anything sent to threads/tasks own their data.
- Views (parsers, iterators, guards) borrow and carry exactly one lifetime where possible.
- `Cow<'static, str>` for "literal or runtime string" fields; `Arc<str>` for shared immutable text.
- More than one lifetime parameter on a struct is a design review item (LT010).
- `&'static str` fields only for genuinely static data such as names in a const table (LT008).
