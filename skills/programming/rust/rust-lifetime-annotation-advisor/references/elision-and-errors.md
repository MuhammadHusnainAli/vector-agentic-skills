# Lifetime Elision and Lifetime Errors

How the compiler fills in lifetimes you did not write, where it refuses to, and what each lifetime-related
error means with a failing and a fixed version. Error texts are quoted from current rustc (1.8x); older
compilers used different codes for several of them, listed at the end.

## Contents

- [What a lifetime annotation is (and is not)](#what-a-lifetime-annotation-is-and-is-not)
- [The three elision rules](#the-three-elision-rules)
- [Where elision does not apply](#where-elision-does-not-apply)
- [The anonymous lifetime '_](#the-anonymous-lifetime-_)
- [Reading lifetime diagnostics: '1, '2 and "borrowed for"](#reading-lifetime-diagnostics-1-2-and-borrowed-for)
- [Error catalogue](#error-catalogue)
- [Codes from older compilers](#codes-from-older-compilers)
- [Decision procedure for a signature](#decision-procedure-for-a-signature)

## What a lifetime annotation is (and is not)

- A lifetime parameter is a **name for a region of code** during which a borrow is valid. Annotations
  describe relationships between borrows ("the output borrows from `text`"); they never make a value live
  longer and never change generated code.
- The caller picks concrete lifetimes at each call site; the callee's body is checked against the signature
  alone. That is why the signature must say which input the result borrows from: the body is not consulted.
- `'static` is the one named lifetime that exists without declaration: data valid for the rest of the
  program (literals, `static` items, leaked boxes) or, as a bound, a type that contains no shorter borrows.
- Lifetimes on references compose: `&'a T` requires `T: 'a` (implied, you rarely write it).

## The three elision rules

Elision is purely syntactic: the compiler looks at the *written* signature, not at the body.

**Rule 1 - inputs.** Every elided lifetime in a parameter type becomes a distinct, fresh lifetime parameter.

```rust
fn compare(a: &str, b: &str) -> bool { a == b }
// is
fn compare_explicit<'x, 'y>(a: &'x str, b: &'y str) -> bool { a == b }
```

**Rule 2 - one input lifetime.** If there is exactly one lifetime in the inputs (elided or named, `'static`
counts), it is assigned to every elided lifetime in the output.

```rust
fn first_word(s: &str) -> &str {
    s.split_whitespace().next().unwrap_or("")
}
// is fn first_word<'a>(s: &'a str) -> &'a str

fn label(prefix: &'static str, n: u32) -> &str {
    let _ = n;
    prefix // output gets 'static: the only input lifetime
}
```

Lifetimes hidden inside path types count as inputs too: `fn name(t: Token<'_>) -> &str` has one input
lifetime (the `'_` in `Token<'_>`), and so does `fn name(t: Token) -> &str` if `Token` has a lifetime parameter,
which is why the `elided_lifetimes_in_paths` lint asks you to write the `<'_>`.

**Rule 3 - methods.** If one of the parameters is `&self` or `&mut self` (also `self: &Self`,
`self: &mut Self`, `self: Pin<&mut Self>`), the receiver's lifetime is assigned to every
elided output lifetime, no matter how many other reference parameters exist.

```rust
use std::collections::HashMap;

struct Cache {
    map: HashMap<String, String>,
}

impl Cache {
    // Output borrows self, not key.
    fn get(&self, key: &str) -> Option<&String> {
        self.map.get(key)
    }

    // Output borrows the argument, not self: rule 3 would be wrong, so name it.
    fn or_default<'a>(&self, key: &str, fallback: &'a String) -> &'a String {
        let _ = key;
        fallback
    }
}
```

If rule 3 picks `self` but the body returns the argument, the error is not E0106 but a region error:

```text
error: lifetime may not live long enough
  |     fn pick(&self, other: &str) -> &str {
  |             -             - let's call the lifetime of this reference `'1`
  |             |
  |             let's call the lifetime of this reference `'2`
  |         other
  |         ^^^^^ method was supposed to return data with lifetime `'2` but it is returning data with lifetime `'1`
```

Fix: `fn pick<'a>(&self, other: &'a str) -> &'a str`.

**Elided output, no rule applies.** With zero input lifetimes, or two or more and no receiver, E0106.

## Where elision does not apply

| Position | What happens | Write instead |
|----------|--------------|---------------|
| struct / enum / union fields | E0106, always | `struct S<'a> { x: &'a str }` |
| `static` / `const` items | elided lifetimes default to `'static` | `const NAME: &str = "x";` is `&'static str` |
| `impl` headers (2018+) | elided lifetimes become fresh impl parameters | `impl Display for Token<'_>`, `impl From<&str> for Name` |
| `type` aliases | elision not allowed: E0106 | `type Words<'a> = Vec<&'a str>;` |
| trait objects | default object lifetime rules (not elision) | `Box<dyn Trait + 'a>`; see trait-objects reference |
| `Fn(&str) -> &str` sugar | elision applies *inside* the parentheses, higher-ranked | equivalent to `for<'a> Fn(&'a str) -> &'a str` |
| `fn(&str) -> &str` pointers | same, higher-ranked | `for<'a> fn(&'a str) -> &'a str` |
| closures `\|s: &str\| -> &str` | not tied: closure signature inference does not apply elision rule 2 | see advanced-lifetimes, "Closures that return references" |
| `async fn` | same elision as `fn`; the returned future captures all input lifetimes | see async-lifetimes |
| `where` clauses `T: Trait<&str>` | E0637 `'&' without an explicit lifetime name cannot be used here` | `for<'a> T: Trait<&'a str>` or a named lifetime |

## The anonymous lifetime '_

`'_` means "an elided lifetime here, please" and is valid wherever elision is:

- In paths, to make a hidden lifetime visible: `fmt::Formatter<'_>`, `Cow<'_, str>`, `Ref<'_, T>`,
  `std::str::Chars<'_>`, `Parser<'_>`.
- In impl headers: `impl Iterator for Words<'_>` when the impl body never needs to name it. If the body needs
  the name (`type Item = &'a str;`), declare it: `impl<'a> Iterator for Words<'a>`.
- In return types, to say "borrows from the obvious input": `-> impl Iterator<Item = u32> + '_`,
  `-> Box<dyn Error + '_>`.
- In trait object bounds of arguments: `fn run(job: Box<dyn Job + '_>)` accepts non-`'static` jobs.

`'_` is not allowed in struct field types or where a named lifetime must be declared, and outside signatures
it means "infer" (`let r: Ref<'_, T> = cell.borrow();`).

The `rust_2018_idioms` lint group includes `elided_lifetimes_in_paths` (allow-by-default): turning it on flags
`Formatter` without `<'_>`. Recommended in libraries:

```rust
#![warn(rust_2018_idioms)]
```

## Reading lifetime diagnostics: '1, '2 and "borrowed for"

- `'1`, `'2` are names rustc invents for elided lifetimes in the signature; the diagnostic labels which
  reference each one belongs to. "returning this value requires that `'1` must outlive `'2`" means the data
  you return lives for `'1` but the signature promised `'2`.
- "argument requires that `x` is borrowed for `'static`" points at the call that demands `'static`:
  `thread::spawn`, `tokio::spawn`, storing into `Box<dyn Trait>`, a `static`. Fix the data flow there.
- "borrow later used here" marks the use that keeps an earlier borrow alive. Under NLL a borrow lasts until
  its last use, not until the end of the scope; moving that use earlier often fixes E0502/E0499.
- "first borrow later captured here by closure" means a closure holds the borrow; the closure's lifetime is
  the borrow's lifetime.
- `rustc --explain E0106` (or the online error index) prints the long explanation for any code.

## Error catalogue

### E0106 missing lifetime specifier

```text
error[E0106]: missing lifetime specifier
 --> src/lib.rs:1:33
  |
1 | fn longer(a: &str, b: &str) -> &str {
  |              ----     ----     ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `a` or `b`
help: consider introducing a named lifetime parameter
```

```rust
fn longer<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() >= b.len() { a } else { b }
}
```

Variant with no input reference ("there is no value for it to be borrowed from"): returning a reference to
something created inside the function cannot work with any lifetime. Return the owned value:

```rust
fn greeting(name: &str) -> String {
    format!("hello {name}")
}

fn level_name(level: u8) -> &'static str {
    match level {
        0 => "error",
        1 => "warn",
        _ => "info",
    }
}
```

Variant on a type: `struct Token { text: &str }` gives E0106 with "expected named lifetime parameter".

```rust
struct Token<'a> {
    text: &'a str,
}

struct OwnedToken {
    text: String,
}
```

`missing_lifetime` (LT003, LT004) detects these statically and print the signature.

### E0621 explicit lifetime required in the type of `x`

The signature names `'a` for the output and for some inputs, but you return data from an input whose lifetime
was elided.

```rust
// error[E0621]: explicit lifetime required in the type of `fallback`
// fn get_or<'a>(map: &'a std::collections::HashMap<String, String>, k: &str, fallback: &str) -> &'a str {
//     map.get(k).map(String::as_str).unwrap_or(fallback)
// }

fn get_or<'a>(map: &'a std::collections::HashMap<String, String>, k: &str, fallback: &'a str) -> &'a str {
    map.get(k).map(String::as_str).unwrap_or(fallback)
}
```

### "lifetime may not live long enough"

The generic region error from the borrow checker. Typical shapes:

```rust
struct Holder<'a> {
    items: Vec<&'a str>,
}

impl<'a> Holder<'a> {
    // error: lifetime may not live long enough
    // fn add(&mut self, s: &str) { self.items.push(s); }
    //   argument `s` has lifetime '1, but items need 'a

    fn add(&mut self, s: &'a str) {
        self.items.push(s);
    }
}
```

When storing an argument into `self`, the argument must carry the struct's lifetime.

### E0515 cannot return reference to local variable / value referencing data owned by the current function

```rust
// fn names() -> Vec<&'static str> { let s = String::from("a,b"); s.split(',').collect() }  // E0515
fn names(csv: &str) -> Vec<&str> {
    csv.split(',').collect() // borrows the caller's string instead
}

fn names_owned() -> Vec<String> {
    let s = String::from("a,b");
    s.split(',').map(str::to_owned).collect()
}
```

No annotation fixes E0515: the data dies at the end of the function. Return owned data or take the source as a
parameter.

### E0597 `x` does not live long enough, E0716 temporary value dropped while borrowed

```rust
fn main() {
    let words: Vec<&str>;
    {
        let text = String::from("a b c");
        // words = text.split(' ').collect(); // E0597: `text` dropped here while still borrowed
        let _ = &text;
    }
    let text = String::from("a b c"); // move the owner to the outer scope
    words = text.split(' ').collect();
    println!("{words:?}");

    // E0716: let s: &str = String::from("tmp").as_str(); then use s
    let owned = String::from("tmp"); // bind the temporary
    let s: &str = owned.as_str();
    println!("{s}");
}
```

### E0310 the parameter type `T` may not live long enough

```text
error[E0310]: the parameter type `T` may not live long enough
  |
  |     Box::new(value)
  |     ^^^^^^^^^^^^^^^ the parameter type `T` must be valid for the static lifetime...
  |                     ...so that the type `T` will meet its required lifetime bounds
help: consider adding an explicit lifetime bound
  |
  | fn boxed<T: Debug + 'static>(value: T) -> Box<dyn Debug> {
```

```rust
use std::fmt::Debug;

fn boxed<T: Debug + 'static>(value: T) -> Box<dyn Debug> {
    Box::new(value)
}

// or keep borrowed T allowed by tying the object lifetime:
fn boxed_any<'a, T: Debug + 'a>(value: T) -> Box<dyn Debug + 'a> {
    Box::new(value)
}
```

`T: 'static` is about what `T` *contains*, not how long the value lives. See
[trait-objects-and-impl-trait.md](trait-objects-and-impl-trait.md).

### E0521 borrowed data escapes outside of function / method

```rust
use std::thread;

// fn spawn_print(s: &str) { thread::spawn(move || println!("{s}")); }
// error[E0521]: borrowed data escapes outside of function: `s` escapes the function body here

fn spawn_print(s: &str) -> thread::JoinHandle<()> {
    let owned = s.to_owned();
    thread::spawn(move || println!("{owned}"))
}

fn scoped_print(s: &str) {
    thread::scope(|scope| {
        scope.spawn(|| println!("{s}")); // scoped threads may borrow (1.63+)
    });
}
```

### E0373 closure may outlive the current function, but it borrows `x`

Raised when a closure that must be `'static` (spawn) borrows a local without `move`. Add `move` and make sure
the moved data is owned (`String`, `Arc<T>`), or use `thread::scope`.

### E0499 / E0502 after a method with `&'a mut self`

```rust
struct Lexer<'a> {
    src: &'a str,
    pos: usize,
}

impl<'a> Lexer<'a> {
    // BAD: fn next(&'a mut self) -> Option<&'a str>
    // let mut lx = Lexer { src, pos: 0 }; lx.next(); lx.next();
    // error[E0499]: cannot borrow `lx` as mutable more than once at a time
    fn next(&mut self) -> Option<&'a str> {
        let rest = self.src.get(self.pos..)?;
        let end = rest.find(' ').map_or(rest.len(), |i| i + 1);
        self.pos += end;
        if end == 0 { None } else { Some(rest[..end].trim_end()) }
    }
}
```

`&'a mut Lexer<'a>` asks for a mutable borrow lasting as long as the lexer's own data lifetime; because `&mut T`
is invariant in `T` the compiler cannot shrink it, so the lexer is unusable after the first call. LT007 flags it.

### E0392 parameter is never used

```rust
use std::marker::PhantomData;

// struct Slice<'a, T> { ptr: *const T, len: usize }   // error[E0392]: lifetime parameter `'a` is never used
struct Slice<'a, T> {
    ptr: *const T,
    len: usize,
    _borrow: PhantomData<&'a [T]>, // "behaves as if it holds &'a [T]": covariant, ties drop check
}
```

### E0700 hidden type for `impl Trait` captures lifetime that does not appear in bounds

Edition 2021 and earlier, free functions and inherent methods returning `impl Trait`:

```rust
// fn chars_of(s: &str) -> impl Iterator<Item = char> { s.chars() }
// edition 2021: error[E0700]: hidden type for `impl Iterator<Item = char>` captures lifetime
// that does not appear in bounds
fn chars_of(s: &str) -> impl Iterator<Item = char> + '_ {
    s.chars()
}
```

In edition 2024 the unannotated version compiles because return-position `impl Trait` captures all in-scope
lifetimes. `use<'_>` (1.82+) is the precise alternative to `+ '_`.

### E0261 use of undeclared lifetime name, E0262 invalid lifetime parameter name

```rust
// fn f(x: &'a str) {}            // E0261: declare it: fn f<'a>(x: &'a str)
// fn g<'static>(x: &'static str) // E0262: 'static cannot be declared
fn f<'a>(x: &'a str) -> &'a str { x }
```

### E0726 implicit elided lifetime not allowed here

```rust
struct Name<'a>(&'a str);

trait Greet {
    fn greet(&self) -> String;
}

// impl Greet for Name { .. }   // error[E0726]: implicit elided lifetime not allowed here
impl Greet for Name<'_> {
    fn greet(&self) -> String {
        format!("hi {}", self.0)
    }
}
```

### E0637 `'_` / `&` without an explicit lifetime name cannot be used here

Appears for `&T` in `where` bounds or generic bounds (`T: AsRef<&str>`) and for `'_` in positions where a
named lifetime must be declared. Name the lifetime, or use `for<'a>` for a higher-ranked bound.

## Codes from older compilers

| Code | Old message | Current equivalent |
|------|-------------|--------------------|
| E0495 | cannot infer an appropriate lifetime due to conflicting requirements | `lifetime may not live long enough`, E0521 |
| E0623 | lifetime mismatch | `lifetime may not live long enough` |
| E0759 | `x` has an anonymous lifetime `'_` but it needs to satisfy a `'static` lifetime requirement | E0521, or `lifetime may not live long enough` with a `'static` note |
| E0772 | `self` has an anonymous lifetime `'_` but calling a method requires `'static` | same as E0759 |

These came from the lexical region checker, retired after NLL replaced it completely. The error index marks
E0495, E0623, E0759 and E0772 as no longer emitted; the fixes are the same as for their modern equivalents.

## Decision procedure for a signature

```
1. Does it return a reference (or a type with a lifetime: Cow, Iter, impl Trait capturing, Token<'_>)?
   no  -> elide everything; name lifetimes only for bounds you need (T: 'a, 'a: 'b)
2. Is there &self / &mut self, and does the result borrow from self?
   yes -> elide (rule 3)
   result borrows from an argument instead -> name 'a on that argument and the output
3. Exactly one input lifetime?             -> elide (rule 2)
4. Several input lifetimes:
   result from exactly one input           -> 'a on that input + output only
   result from any of them                 -> 'a on all of them
5. No input lifetime                       -> return owned data, or &'static for literals/globals
6. Storing an argument into self?          -> the argument needs the struct's lifetime: s: &'a str
7. Run the scripts (`/tmp/missing_lifetime file.rs`, `/tmp/elision_check file.rs`) and cargo check
```
