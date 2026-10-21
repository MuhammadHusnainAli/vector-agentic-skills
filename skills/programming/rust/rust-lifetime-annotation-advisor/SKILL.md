---
name: rust-lifetime-annotation-advisor
description: "Decide when Rust lifetime annotations are needed and which ones: the three elision rules, structs holding references (struct Parser<'a>), owned vs borrowed (String, &str, Cow<'a, str>, Arc<str>), one vs several lifetimes, 'a: 'b bounds, T: 'static misconceptions, Box<dyn Trait + 'a> default object lifetimes, impl Trait + '_ and edition 2024 capture rules with use<..>, variance and PhantomData, HRTB for<'a> Fn(&'a T), GATs and lending iterators, async fn and tokio::spawn 'static, self-referential structs (ouroboros, self_cell, indices, arenas), Rc/Arc to escape lifetime soup. Ships std-only Rust checkers for redundant, missing, unused and over-restrictive lifetimes. Use when rustc reports E0106 missing lifetime specifier, E0621, E0310 parameter type `T` may not live long enough, E0392, E0700, E0521 borrowed data escapes, E0597, E0515, E0373, older E0495/E0623/E0759/E0772, 'lifetime may not live long enough', or when designing structs, iterators and APIs that borrow."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Lifetime Annotation Advisor

Decide whether a signature or type needs a lifetime at all, which one, and whether owning the data would make
the lifetime disappear. Start from the three elision rules (most signatures need nothing), add a named lifetime
only to express a real relationship ("the result borrows from `text`, not from `sep`"), and treat a struct
that grows two or three lifetime parameters as a design smell: owning the data (`String`, `Arc<str>`, indices)
usually costs one allocation and removes the lifetime from every caller. Four small std-only Rust programs in
`scripts/` read source text (they never build your crate) and report redundant, missing, unused and
over-restrictive lifetimes with the corrected signature.

## Trigger Conditions

Activate this skill when the user:
- Hits `error[E0106]: missing lifetime specifier`, `expected named lifetime parameter`, E0621 `explicit
  lifetime required in the type of`, E0310 `the parameter type T may not live long enough`, E0392 `lifetime
  parameter 'a is never used`, E0700 `hidden type for impl Trait captures lifetime`, E0521 `borrowed data
  escapes outside of`, `lifetime may not live long enough`, E0597 `does not live long enough`, E0515, E0373
- Sees `'static` demanded by `tokio::spawn`, `thread::spawn`, `Box<dyn Trait>` or `dyn Any`
- Asks "do I need `<'a>` here?", "why does my struct need a lifetime?", "String or &str or Cow?", "one lifetime
  or two?", "what does `'_` mean?", "what does `T: 'static` mean?", "`impl Trait + '_` vs `use<'a>`?"
- Designs a parser, tokenizer, iterator, view or config type that borrows input; or a struct that wants to
  own data and borrow from it at the same time (self-referential)
- Migrates to edition 2024 and sees `impl_trait_overcaptures` warnings or new borrow errors around `-> impl Trait`
- Uses HRTB (`for<'a> Fn(&'a T)`), GATs (`type Item<'a> where Self: 'a`), `PhantomData`, variance questions

## Workflow

```
1. LOCATE    -> Which item needs the lifetime: fn signature, struct field, impl header, trait object, impl Trait?
                Read the compiler's labels ('1, '2, "argument requires that ... is borrowed for 'static").
2. AUDIT     -> build once: for t in elision_check missing_lifetime static_bounds lifetime_smells; do
                  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
                /tmp/missing_lifetime src/     (E0106/E0392 before compiling)   /tmp/elision_check src/
                /tmp/static_bounds src/        /tmp/lifetime_smells src/   (edition from Cargo.toml)
3. ELIDE     -> Apply the three elision rules (table below). If elision already gives the right answer,
                write nothing; use '_ where a path type hides a lifetime (Formatter<'_>, Cow<'_, str>).
4. DECIDE    -> Borrow or own? (decision table). Prefer owning in long-lived structs, async tasks, threads,
                caches and public APIs; borrow in short-lived views, parsers and hot loops.
5. ANNOTATE  -> One lifetime per independent source of borrowed data. Tie outputs only to the inputs they
                really borrow from. Spell out object lifetimes (dyn Trait + 'a) and captures (use<..>).
6. VERIFY    -> cargo check; cargo clippy (needless_lifetimes, extra_unused_lifetimes);
                each script with --strict exits 1 on findings (CI gate)
```

## Do You Need an Annotation? The Three Elision Rules

| Rule | Applies to | Effect | Example (as written -> as the compiler sees it) |
|------|------------|--------|------------------------------------------------|
| 1 | every elided lifetime in the inputs | each gets its own fresh parameter | `fn f(a: &str, b: &str)` -> `fn f<'1, '2>(a: &'1 str, b: &'2 str)` |
| 2 | output, when there is exactly one input lifetime (elided or named, `'static` included) | that lifetime goes to every elided output lifetime | `fn trim(s: &str) -> &str` -> `-> &'1 str` |
| 3 | output of a method with `&self` / `&mut self` (also `self: &Self`, `Pin<&mut Self>`) | the receiver's lifetime goes to every elided output lifetime | `fn name(&self, k: &str) -> &str` -> borrows `self`, not `k` |

When none applies (two or more input lifetimes and no `&self`, or no input lifetime at all) the output needs a
name: E0106. Elision never happens in struct/enum fields, `static`/`const` items default to `'static`, and
trait objects follow separate *default object lifetime* rules (`Box<dyn T>` = `dyn T + 'static`, `&'a dyn T`
= `dyn T + 'a`).

| Situation | Write | Why |
|-----------|-------|-----|
| One reference in, reference out | `fn first(s: &str) -> &str` | rule 2 |
| Method returns data from `self` | `fn get(&self, key: &str) -> Option<&V>` | rule 3 |
| Method returns data from an *argument*, not self | `fn pick<'a>(&self, xs: &'a [T]) -> &'a T` | rule 3 would pick `self` |
| Result may come from either of two inputs | `fn longest<'a>(a: &'a str, b: &'a str) -> &'a str` | both must outlive the result |
| Result only from the first of two inputs | `fn before<'a>(text: &'a str, sep: &str) -> &'a str` | leaves `sep` free |
| No borrowed input | return owned (`String`, `Vec<T>`), or `&'static str` for literals | nothing to borrow from |
| Path type with a hidden lifetime | `fmt::Formatter<'_>`, `Cow<'_, str>`, `Ref<'_, T>` | `elided_lifetimes_in_paths` (in `rust_2018_idioms`) |
| Impl for a borrowing type that never names `'a` | `impl fmt::Display for Token<'_>` | impl header elision (2018+) |
| Struct field borrows | `struct Token<'a> { text: &'a str }`, or own: `text: String` | types never elide |

## Borrow or Own?

| Data lives in... | Field / return type | Cost | Lifetime impact |
|------------------|---------------------|------|-----------------|
| A caller buffer that outlives the value (parse, tokenize, view) | `&'a str`, `&'a [T]` | zero copy | `'a` spreads to every user of the type |
| Usually borrowed, sometimes modified (escape, normalize) | `Cow<'a, str>` | allocates only on change | still has `'a`; `Cow<'static, str>` takes literals and owned strings |
| A long-lived struct, async task, thread, cache, error type, public API | `String`, `Vec<T>`, `Box<str>` | one allocation + copy | none: the type is `'static` |
| Shared immutable text cloned often (config, interned names, keys) | `Arc<str>` / `Rc<str>` | one allocation; clone = refcount bump | none |
| Shared mutable state | `Arc<Mutex<T>>`, `Rc<RefCell<T>>` | refcount + lock/borrow flag | none; runtime checks instead |
| Graph / tree with back edges, "parent" links | `Vec<Node>` + `usize` ids, arena, `slotmap` | index bounds checks | none, or one arena lifetime |
| Both the owner and borrows of it in one struct | split into two values, indices, or `self_cell`/`ouroboros` | see reference | self-referential structs cannot be written with plain lifetimes |

Rule of thumb: borrow in functions, own in structs, unless the struct is a short-lived *view* created and
dropped within one scope (parser over a file buffer, iterator, guard). Cloning a 40-byte string to delete a
lifetime parameter from 30 call sites is almost always the right trade; profile before reintroducing borrows.

## Error -> Cause -> Fix

| Compiler says | Cause | Fix |
|---------------|-------|-----|
| E0106 missing lifetime specifier, "does not say whether it is borrowed from `a` or `b`" | two input lifetimes, no `&self` | name one lifetime; tie only the inputs the result borrows from (LT003) |
| E0106 "there is no value for it to be borrowed from" | reference returned with no reference input | return owned data, or `&'static` for literals |
| E0106 on a struct field | `struct S { s: &str }` | `struct S<'a> { s: &'a str }` or `s: String` (LT004) |
| E0621 explicit lifetime required in the type of `x` | output is `'a`, an input has an elided lifetime but is returned | add `'a` to that input |
| "lifetime may not live long enough ... returning this value requires that `'1` must outlive `'2`" | result tied to the wrong input (often rule 3 picked `self`) | name the lifetime on the input actually returned |
| E0515 cannot return reference to local variable / value referencing local data | data is created inside the fn | return the owned value; no lifetime can fix this |
| E0597 `x` does not live long enough / E0716 temporary value dropped while borrowed | borrow outlives the owner | bind the owner to a longer-lived `let`, or own the data in the struct |
| E0310 the parameter type `T` may not live long enough | `T` stored in `Box<dyn Trait>`/spawned/`Any` | add `T: 'static` (it means "no short borrows inside", not "lives forever") or `+ 'a` |
| E0521 borrowed data escapes outside of function/method | a borrowed argument flows into something `'static` (spawn, `Box<dyn T>`) | own/clone/`Arc` the data, or `dyn T + '_` / `thread::scope` |
| E0373 closure may outlive the current function, but it borrows `x` | closure passed to `thread::spawn`/`tokio::spawn` | `move` + owned/`Arc` data, or `std::thread::scope` (1.63+) |
| E0700 hidden type for `impl Trait` captures lifetime that does not appear in bounds (edition <= 2021) | returned iterator/future borrows an argument | `+ '_` / `+ use<'a>` (1.82+), or edition 2024 |
| E0499/E0502 after one call to a method taking `&'a mut self` in `impl<'a> S<'a>` | `&'a mut self` borrows for the struct's whole lifetime | `&mut self`; keep `'a` only on the returned data (LT007) |
| E0392 lifetime parameter `'a` is never used | unused param | remove it or `PhantomData<&'a ()>` (LT006) |
| Old compilers: E0495 cannot infer an appropriate lifetime, E0623 lifetime mismatch, E0759/E0772 `'static` requirement | same problems; these codes are no longer emitted by current rustc | read as the modern equivalents above |

Full catalogue with failing and fixed code: [elision-and-errors.md](references/elision-and-errors.md).

## Core Rules

**Structs that borrow return data tied to the struct's lifetime, not to `&self`.**

```rust
pub struct Parser<'a> {
    src: &'a str,
    pos: usize,
}

impl<'a> Parser<'a> {
    pub fn new(src: &'a str) -> Self {
        Self { src, pos: 0 }
    }

    // `&mut self` is a short borrow; the token borrows the *source* ('a), so callers can
    // keep tokens while calling next_token again. Never write `&'a mut self` here (LT007).
    pub fn next_token(&mut self) -> Option<&'a str> {
        let rest = self.src[self.pos..].trim_start();
        if rest.is_empty() {
            return None;
        }
        let start = self.src.len() - rest.len();
        let end = rest.find(char::is_whitespace).unwrap_or(rest.len());
        self.pos = start + end;
        Some(&rest[..end])
    }
}

fn main() {
    let text = String::from("let x = 1");
    let mut p = Parser::new(&text);
    let a = p.next_token();
    let b = p.next_token(); // fine: `a` borrows `text`, not `p`
    println!("{a:?} {b:?}");
}
```

**One lifetime per independent source; tie outputs only where data flows.**

```rust
// Result may be either input: one lifetime, the shorter of the two at the call site.
fn longest<'a>(a: &'a str, b: &'a str) -> &'a str {
    if a.len() >= b.len() { a } else { b }
}

// Result only borrows `text`: `sep` keeps its own elided lifetime and can be a temporary.
fn before<'a>(text: &'a str, sep: &str) -> &'a str {
    text.split(sep).next().unwrap_or(text)
}
```

Covariance means one lifetime usually suffices: `&'long T` coerces to `&'short T`. A second lifetime is needed
when two borrows must be *independent*, typically behind `&mut` (invariant) or when returning one of them:
`struct Split<'text, 'pat>` lets the caller drop the pattern while keeping pieces of the text.

**`Cow` when you usually borrow; `Arc<str>` when you share; `String` when you just want it to compile.**

```rust
use std::borrow::Cow;
use std::sync::Arc;

fn normalize(input: &str) -> Cow<'_, str> {
    if input.contains('\t') { Cow::Owned(input.replace('\t', "    ")) } else { Cow::Borrowed(input) }
}

#[derive(Clone)]
struct Label {
    name: Arc<str>, // clone is a refcount bump; no lifetime parameter
}

fn main() {
    let n = normalize("a\tb");
    let label = Label { name: Arc::from(&*n) };
    let copy = label.clone();
    assert_eq!(&*copy.name, "a    b");
}
```

**Trait objects default to `'static` in boxes; say `+ 'a` when they borrow.**

```rust
struct Filter<'a> {
    // Box<dyn Fn(&str) -> bool> would mean `+ 'static`: no closure capturing `pattern` by reference.
    predicate: Box<dyn Fn(&str) -> bool + 'a>,
}

impl<'a> Filter<'a> {
    fn new(pattern: &'a str) -> Self {
        Self { predicate: Box::new(move |line: &str| line.contains(pattern)) }
    }
}
```

**`T: 'static` means "owns everything or borrows only `'static` data", not "lives forever".** `String`,
`Vec<u8>`, `Arc<Config>` and `&'static str` are all `'static`; `&'a str` and `Vec<&'a str>` are not. A
`'static` value can still be dropped at any time. Require it only where data truly escapes the caller's scope:
`thread::spawn`, `tokio::spawn`, `Box<dyn Any>`, globals.

```rust
use std::fmt::Debug;
use std::thread;

fn log_later<T: Debug + Send + 'static>(value: T) -> thread::JoinHandle<()> {
    thread::spawn(move || println!("{value:?}")) // without 'static: E0310
}

fn log_now<T: Debug + ?Sized>(value: &T) {
    println!("{value:?}"); // only borrows: no 'static bound (LT009)
}
```

**Return-position `impl Trait`: know what it captures.** Edition 2021 captures type parameters but not
lifetimes unless named (`+ '_` or `+ use<'a>`, else E0700). Edition 2024 captures every in-scope lifetime, so
the result keeps arguments borrowed; opt out with precise capturing (Rust 1.82+), which must still list every
type parameter in scope.

```rust
// Borrows `xs`: '_ (any edition) or use<'_> says so.
fn evens(xs: &[u32]) -> impl Iterator<Item = u32> + '_ {
    xs.iter().copied().filter(|x| x % 2 == 0)
}

// Owns its data: use<> lets callers drop `xs` while iterating (needed in edition 2024).
fn evens_owned(xs: &[u32]) -> impl Iterator<Item = u32> + use<> {
    xs.to_vec().into_iter().filter(|x| x % 2 == 0)
}
```

**Self-referential structs do not exist in safe Rust.** `struct Doc { text: String, words: Vec<&'? str> }`
has no lifetime to write because moving `Doc` would move `text`. Store ranges (`Vec<Range<usize>>`), keep
owner and view as two values (`let doc = load(); let view = View::new(&doc);`), use an arena, or a vetted
crate (`self_cell`, `ouroboros`, `yoke`). See
[self-referential-and-escape-hatches.md](references/self-referential-and-escape-hatches.md).

## Advanced Quick Reference

| Need | Syntax | Since |
|------|--------|-------|
| `'long` outlives `'short` | `fn f<'s, 'l: 's>(x: &'s T, y: &'l T)` / `where 'l: 's` | 1.0 |
| Type may hold borrows of at least `'a` | `T: 'a` (inferred on struct fields since 2018) | 1.0 / 1.31 |
| Closure must accept any borrow | `F: for<'a> Fn(&'a str) -> &'a str` (sugar: `F: Fn(&str) -> &str`) | 1.0 |
| Borrow-free marker of a lifetime or type | `PhantomData<&'a ()>`, `PhantomData<fn() -> T>` | 1.0 |
| Lending iterator / item borrowing the container | `type Item<'a> where Self: 'a;` (GAT) | 1.65 |
| Scoped threads that borrow locals | `std::thread::scope(\|s\| { s.spawn(\|\| ...); })` | 1.63 |
| `async fn` / `-> impl Trait` in traits | `trait Store { async fn get(&self, k: &str) -> Option<String>; }` | 1.75 |
| Precise capturing | `-> impl Trait + use<'a, T>` | 1.82 |
| Edition 2024 (RPIT captures all lifetimes) | `edition = "2024"` in Cargo.toml | 1.85 |
| Async closures | `async \|x\| { ... }`, `F: AsyncFn(&str) -> usize` | 1.85 |

Variance, HRTB, GATs, closures returning references and NLL limitations:
[advanced-lifetimes.md](references/advanced-lifetimes.md). Async and `Send`:
[async-lifetimes.md](references/async-lifetimes.md).

## Output Format

When advising, answer with:
1. **Verdict** - "no annotation needed (rule N)", "needs `'a` on X and the return", or "own the data instead",
   with the elision rule or error code that decides it.
2. **Signature/type** - the exact corrected signature or struct definition, compiling as written; state the MSRV
   or edition when it relies on one (GATs 1.65, `use<..>` 1.82, edition 2024 = 1.85).
3. **Why** - one or two sentences on what the lifetime promises the caller ("the token borrows the source text,
   not the parser").
4. **Cost of the alternative** - when suggesting owned data: what is allocated/cloned and how often; when
   keeping borrows: which types and callers inherit the lifetime.
5. **Verification** - `cargo check` expectations and the script run (`--strict`) that now passes.

## Scripts

Small, standard-library-only Rust programs that read source text; they never compile or run your code. Build
each once with `rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>` (no Cargo project, no crates).

| Script | Rules | Job |
|--------|-------|-----|
| `scripts/elision_check.rs` | LT001, LT002, LT005 | annotations elision makes unnecessary, with the elided signature; unused fn lifetimes |
| `scripts/missing_lifetime.rs` | LT003, LT004, LT006 | what rustc will reject: E0106 returns and fields, E0392 unused type lifetimes, with a fix |
| `scripts/static_bounds.rs` | LT008, LT009, LT011 | `'static` stricter than needed: `&'static` fields/params, `T: 'static` on borrow-only fns, `Box<dyn T>` = `+ 'static` |
| `scripts/lifetime_smells.rs` | LT007, LT010, LT012 | compiles but hurts callers: `&'a mut` tied to its own data, too many lifetimes, edition-2024 RPIT capture |
| `scripts/rsparse.rs` | - | shared module: blanks comments/strings, finds fn signatures, structs/enums and impl blocks |
| `scripts/cli.rs` | - | shared module: options, file walking, edition from Cargo.toml, text/JSON report |

```bash
/tmp/missing_lifetime src/                           # files and/or directories (.rs, skips target/)
/tmp/elision_check src/parser.rs --json              # machine-readable findings with fix
cat lib.rs | /tmp/lifetime_smells - --edition 2024   # stdin (edition defaults to 2021 there)
/tmp/static_bounds src/ --strict                     # exit 1 on any finding (CI gate)
/tmp/lifetime_smells src/ --max-lifetimes 1          # LT010 threshold (default 2)
/tmp/elision_check src/ --select LT001 --ignore LT005
/tmp/missing_lifetime --list-rules                   # each script lists its rules with why and fix
```

| Rule | Name | Severity | Flags |
|------|------|----------|-------|
| LT001 | needless-lifetime | low | `fn f<'a>(x: &'a str) -> &'a str`; prints the elided signature |
| LT002 | elidable-impl-lifetime | low | `impl<'a> Display for T<'a>` with `'a` unused in the body -> `T<'_>` |
| LT003 | missing-lifetime-return | high | E0106: returned reference with 0 or 2+ input lifetimes and no `&self`; prints a signature |
| LT004 | missing-lifetime-field | high | E0106: `&T` field in a struct/enum without a lifetime |
| LT005 | unused-fn-lifetime | medium | lifetime declared on a fn and never used |
| LT006 | unused-type-lifetime | high | E0392: struct/enum lifetime parameter never used |
| LT007 | mut-borrow-own-lifetime | medium | `&'a mut self` in `impl<'a> S<'a>`; `&'a mut X<'a>` params/fields |
| LT008 | static-borrow | low | `&'static` fields and fn params (not in `const fn` or all-`'static` data tables) |
| LT009 | static-bound-borrow-only | low | `T: 'static` on a fn that only takes `&T` and never stores/spawns |
| LT010 | too-many-lifetimes | low | more than `--max-lifetimes` (default 2) lifetime params on an item |
| LT011 | boxed-dyn-default-static | low | `Box/Rc/Arc<dyn Trait>` field in a struct with lifetime params |
| LT012 | rpit-captures-2024 | low | `-> impl Trait` with borrowed inputs, no lifetime or `use<..>`, under edition 2024 |

The edition comes from the nearest `Cargo.toml` (`--edition` overrides; stdin defaults to 2021). The scanner
is not a compiler: rules stay quiet when a path type might hide a lifetime, so a clean run is not a proof;
`cargo check` is. Silence a deliberate case with `// noqa: LT008` on the item's line. Exit codes: 0 clean (or
findings without `--strict`), 1 findings with `--strict`, 2 usage error or unreadable file.

## Additional Resources

| File | Content |
|------|---------|
| [elision-and-errors.md](references/elision-and-errors.md) | Elision rules in depth, `'_`, every lifetime error code with failing and fixed code, reading `'1`/`'2` diagnostics |
| [owned-vs-borrowed.md](references/owned-vs-borrowed.md) | String/&str/Cow/Box<str>/Arc<str>, struct design, cost model, Rc/Arc escape hatch, API guidelines |
| [trait-objects-and-impl-trait.md](references/trait-objects-and-impl-trait.md) | Default object lifetimes, `dyn Trait + 'a`, `T: 'static`, E0310, RPIT capture rules 2021 vs 2024, `use<..>` |
| [advanced-lifetimes.md](references/advanced-lifetimes.md) | `'a: 'b`, variance and PhantomData, HRTB, GATs and lending iterators, iterators over references, closures, NLL limits |
| [async-lifetimes.md](references/async-lifetimes.md) | async fn capture, `tokio::spawn` + `'static`, scoped threads, `Send` across `.await`, async traits and closures |
| [self-referential-and-escape-hatches.md](references/self-referential-and-escape-hatches.md) | Why self-reference fails, indices, arenas, self_cell, ouroboros, yoke, Pin, Rc/Arc graphs |
| [versions-and-testing.md](references/versions-and-testing.md) | Editions and stabilisations (NLL, `'_`, GATs, RPITIT, `use<..>`, 2024), lints, compile-fail tests, CI |
