# Ownership and Borrowing Model

The rules the borrow checker enforces, stated precisely enough to predict its answers. Most "the borrow checker
is wrong" moments come from one of five misunderstandings: borrows last until their last use (not the closing
brace) unless a destructor or return keeps them alive; method calls borrow all of `self`; indexing hides which
element is borrowed; temporaries die at the end of the statement; `'static` bounds forbid all borrows.

## Contents

- [Ownership and moves](#ownership-and-moves)
- [Copy, Clone and when a move is a copy](#copy-clone-and-when-a-move-is-a-copy)
- [Borrows: shared XOR mutable](#borrows-shared-xor-mutable)
- [Non-lexical lifetimes: liveness](#non-lexical-lifetimes-liveness)
- [Destructors extend borrows](#destructors-extend-borrows)
- [Reborrowing](#reborrowing)
- [Two-phase borrows](#two-phase-borrows)
- [Places, paths and disjoint fields](#places-paths-and-disjoint-fields)
- [Closure capture rules](#closure-capture-rules)
- [Temporaries and drop scopes](#temporaries-and-drop-scopes)
- [Lifetime elision](#lifetime-elision)
- [Variance in one paragraph](#variance-in-one-paragraph)
- [Mental checklist](#mental-checklist)

## Ownership and moves

Every value has exactly one owner. Assigning, passing by value or returning a non-`Copy` value **moves** it; the
source binding becomes unusable (statically: E0382 if you touch it). Moves are shallow `memcpy`s of the stack
part (a `String` move copies pointer, length and capacity, never the heap bytes), so returning owned values is
cheap.

```rust
fn main() {
    let a = String::from("hi");
    let b = a;                 // move: `a` is now uninitialised
    let a = String::from("again"); // shadowing creates a new binding; fine
    println!("{a} {b}");
}
```

Things that move without looking like it:

| Expression | Moves |
|------------|-------|
| `for x in v` | `v` (calls `IntoIterator::into_iter(v)`) |
| `v.into_iter()`, `opt.unwrap()`, `s.into_bytes()`, builder `.build()` | the receiver (`self` by value) |
| `let x = s.field;` | the field (partial move: `s` cannot be used as a whole afterwards, other fields still can) |
| `match opt { Some(x) => .. }` on an owned `opt` | the payload into `x` (use `&opt` or `ref x` to borrow) |
| `move \|\| ...` / `async move { ... }` | every captured variable (references are copied, values are moved) |
| `drop(x)`, `mem::forget(x)` | `x` |

A partial move is legal on owned locals but not through references (E0507) and not out of types that implement
`Drop` (E0509).

## Copy, Clone and when a move is a copy

A type is `Copy` if a bitwise copy is a valid duplicate: integers, floats, `bool`, `char`, shared references
`&T`, raw pointers, function pointers, and tuples/arrays/structs made only of `Copy` types that opt in with
`#[derive(Clone, Copy)]`. `&mut T` is never `Copy` (it would alias), `String`/`Vec`/`Box` are never `Copy`.

`Clone` is an explicit, possibly expensive duplicate. A `.clone()` that only exists to silence E0382 is fine
for small values or one-off setup code and a smell in a hot loop. `Rc::clone(&x)`/`Arc::clone(&x)` are cheap
refcount bumps: write them in that form to make the cheapness visible.

## Borrows: shared XOR mutable

| Borrow | Allows | Forbids while live |
|--------|--------|--------------------|
| `&T` (shared) | any number of readers | mutation through any path, moves out |
| `&mut T` (unique) | one reader/writer | any other access to the same place, including reads through the owner |

Interior mutability (`Cell`, `RefCell`, `Mutex`, atomics) is the explicit opt-out: mutation through `&T`, with
the exclusivity check done at run time or by restricting the API. See
[shared-ownership-and-interior-mutability.md](shared-ownership-and-interior-mutability.md).

## Non-lexical lifetimes: liveness

Since NLL (edition 2018, Rust 1.31; all editions since 1.36), a borrow is live from its creation to its **last
use**, computed on the control-flow graph. The closing brace matters only for values with destructors.

```rust
fn main() {
    let mut scores = vec![10, 20];
    let first = &scores[0];
    println!("{first}");      // last use of `first`: the borrow ends here
    scores.push(30);          // OK under NLL
}
```

What keeps a borrow live longer than it looks:
1. A later use, possibly in a loop's next iteration ("borrow later used here, in later iteration of loop").
2. The borrow flowing into the return value ("returning this value requires that ..."): it is then live until
   the function returns on **every** path that follows, which is the source of NLL problem case #3
   ([nll-limitations-and-polonius.md](nll-limitations-and-polonius.md)).
3. Storage in a struct/collection that is used later (`cache.push(&item)`).
4. A destructor of the holder (next section).
5. A `'static` bound (spawned threads/tasks, `Box<dyn Any>`).

## Destructors extend borrows

If the value that holds a borrow implements `Drop` (directly or through a field), dropping it at scope end is a
use. Guards (`Ref`, `RefMut`, `MutexGuard`) and user types with `impl Drop` count. Standard collections such as
`Vec<&T>` do not: their `Drop` impls are marked `#[may_dangle]`, so dropping them is not a use of the references
they hold.

```rust
struct Logger<'a> { sink: &'a mut Vec<String> }

impl Drop for Logger<'_> {
    fn drop(&mut self) { self.sink.push("closed".into()); }
}

fn main() {
    let mut lines = Vec::new();
    {
        let mut log = Logger { sink: &mut lines };
        log.sink.push("start".into());
        // println!("{}", lines.len());   // E0502: `log` is dropped at `}` and uses `lines`
    }                                     // drop(log) runs here
    println!("{}", lines.len());          // fine after the block
}
```

Fix by shortening the holder's scope (`{ }` block or `drop(log)`) before the conflicting access.

## Reborrowing

Passing `&mut T` to a function that takes `&mut T` does not move the reference; the compiler inserts an implicit
reborrow `&mut *r` that lasts only for the call. That is why you can call `f(r); f(r);` twice.

```rust
fn bump(n: &mut u32) { *n += 1; }

fn main() {
    let mut n = 0;
    let r = &mut n;
    bump(r);           // implicit reborrow &mut *r
    bump(r);           // r still usable
    *r += 1;
    println!("{n}");
}
```

Implicit reborrows do **not** happen when the target type is generic (`fn take<T>(t: T)`), so `take(r); *r += 1;`
moves `r` and fails with E0382. Write `take(&mut *r)` to reborrow explicitly.

## Two-phase borrows

For autoref method calls, overloaded compound assignment (`a += ..` via `AddAssign`) and implicit mutable
reborrows of arguments, the `&mut` is first **reserved** (acts like a shared borrow) and only **activated** when
the call starts. Arguments evaluated in between may read the same value.

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    v.push(v.len());           // OK: `v.len()` reads during the reservation phase
    let i = v.len() - 1;
    v[i] += 1;                 // indexing + compound assignment on a primitive also fine
    println!("{v:?}");
}
```

Limits: the reservation still conflicts with another `&mut` (`v.push(v.pop().unwrap())` is E0499), and the
argument must not create a shared borrow that is still live at activation. Rewrite as
`let last = v.pop().unwrap(); v.push(last);`.

## Places, paths and disjoint fields

The checker tracks **places**: a local, a field path (`s.a.b`), a deref (`*r`), an index (`v[i]`). Two field
paths of the same struct are disjoint, so these coexist:

```rust
struct Game { players: Vec<String>, scores: Vec<u32>, round: u32 }

fn main() {
    let mut g = Game { players: vec!["a".into()], scores: vec![0], round: 1 };
    let players = &g.players;          // shared borrow of g.players
    let scores = &mut g.scores;        // mutable borrow of g.scores: disjoint, OK
    scores[0] += players.len() as u32 + g.round;   // reading g.round: disjoint too
}
```

What breaks disjointness:
- **Method calls**: `g.scores_mut()` borrows all of `g`; the signature is the contract and the checker does not
  look inside. Borrow fields directly, or make helpers take only the fields they need.
- **Indices**: `v[i]` and `v[j]` are treated as overlapping (`IndexMut::index_mut(&mut v, i)` borrows all of `v`).
- **Through `Box`**: field paths through `Box` work (`b.x` and `b.y` of a `Box<Point>` are disjoint) because `Box`
  is special-cased; through `Rc`, `RefMut`, `MutexGuard` or any other `Deref` type they are not, because each
  access calls `deref_mut(&mut guard)`. Reborrow the inner value once: `let inner = &mut *guard;` then borrow
  `inner.a` and `inner.b`.

## Closure capture rules

Closures capture each variable in the least powerful mode their body needs: by `&` if it only reads, by `&mut` if
it mutates, by value if it moves out. `move` forces by-value capture of everything mentioned (a captured `&T`
is copied, so `move` with a reference still borrows).

Since edition 2021 (Rust 1.56), closures capture **disjoint field paths** rather than whole variables:

```rust
struct Counter { hits: u32, name: String }

impl Counter {
    fn run(&mut self) {
        let name = &self.name;
        let mut bump = || self.hits += 1;   // 2021: captures only `self.hits` (by &mut)
        bump();
        println!("{name}");                 // edition 2018: rejected, the closure captured all of `self`
    }
}
```

A closure that captures by `&mut` holds that unique borrow until its **last call**, not just its creation
(E0500/E0501/E0524 and E0502 in [error-code-catalog.md](error-code-catalog.md#e0500-e0501-e0524-closures-with-unique-access)).

`Fn`/`FnMut`/`FnOnce` follow from captures: moving a captured value out makes the closure `FnOnce`; mutating
makes it `FnMut`. An `FnMut` closure cannot return a reference into its own captured state ("captured variable
cannot escape `FnMut` closure body").

## Temporaries and drop scopes

A temporary is created for a value expression used in a place context: `String::from("x").as_str()`,
`m.lock().unwrap().len()`, `cell.borrow().iter()`. Rules (edition 2021 unless noted):

| Context | Temporary lives until |
|---------|-----------------------|
| ordinary statement `expr;` | the end of the statement (`;`) |
| `let x = &temp;` / `let x = Struct { f: &temp };` | the end of the enclosing block (temporary lifetime extension) |
| `let x = temp.method();` | the `;` (method calls are not extended), so `x` may not borrow from `temp` (E0716) |
| `match temp_expr { .. }` scrutinee | the end of the whole `match` statement |
| `if let` scrutinee | edition 2021: end of the whole `if let ... else`; edition 2024: before the `else` block |
| block tail expression | edition 2021: after the block's locals are dropped (E0597 surprises); edition 2024: before them |

Practical consequences:

```rust
use std::sync::Mutex;

fn main() {
    let jobs = Mutex::new(vec![1, 2, 3]);

    // Guard lives for the whole match: a second lock() inside a match arm would deadlock.
    match jobs.lock().unwrap().pop() {
        Some(j) => println!("job {j}"),   // do NOT call jobs.lock() here
        None => {}
    }

    // One statement: the guard is dropped at the `;`, `n` is an owned usize.
    let n = jobs.lock().unwrap().len();

    // Bind the guard when you need a reference into the data.
    let guard = jobs.lock().unwrap();
    let first: &i32 = &guard[0];
    println!("{n} {first}");
}
```

The `match`/`if let` rule is the most common cause of `RefCell` "already borrowed" panics and same-thread
`Mutex` deadlocks: `if let Some(x) = self.cache.borrow().get(k) { self.cache.borrow_mut()... }` holds the `Ref`
for the whole body. Copy the value out first: `let hit = self.cache.borrow().get(k).cloned();`.

## Lifetime elision

When a function signature leaves lifetimes out, rustc fills them in:

1. Each elided input lifetime becomes a distinct parameter.
2. If there is exactly one input lifetime (elided or not), it is assigned to every elided output lifetime.
3. If there are several input lifetimes but one of them is `&self` or `&mut self`, the lifetime of `self` is
   assigned to every elided output lifetime.

Otherwise an elided output lifetime is an error (E0106 "missing lifetime specifier"). Rule 3 is why
`fn get(&self, key: &str) -> &str` cannot return `key` (see
[error-code-catalog.md](error-code-catalog.md#errors-without-a-code)): write `fn get<'k>(&self, key: &'k str) -> &'k str`.

`'_` in a type means "elided here, please infer" (`impl Iterator<Item = &u8> + '_`, `Cow<'_, str>`,
`Formatter<'_>`). Struct fields never elide: `struct View<'a> { s: &'a str }`.

`impl Trait` in return position: before edition 2024 it captures type parameters but only the lifetimes that
are named in its bounds; in edition 2024 it captures **all** in-scope lifetimes. Use precise capturing
`impl Iterator<Item = u32> + use<'a, T>` (Rust 1.82+) to restrict it.

## Variance in one paragraph

`&'a T` is covariant in `'a` (a longer-lived reference can be used where a shorter one is expected).
`&'a mut T` is covariant in `'a` but **invariant** in `T`: you cannot pass `&mut Vec<&'static str>` where
`&mut Vec<&'short str>` is expected, because the callee could push a short-lived `&str` into it. Errors that
mention "`'a` must outlive `'b`" on `&mut` arguments, `Cell<&'a T>` or `fn(&'a T)` positions are usually
invariance. The fix is to give both sides the same lifetime parameter instead of trying to shorten one.

## Mental checklist

1. Which **place** is borrowed (`self.items`, `*self`, `v`, `v[_]`)? A method call borrows its whole receiver.
2. Where is the borrow **created**, where is the **conflicting** access, where is the borrow **used later**?
3. Is the "later use" a destructor, a return value, a loop back-edge, or a `'static` bound?
4. Can the later use work with an owned copy, an index or a key instead?
5. Can the conflicting access target a disjoint place (a field, a split slice, an entry)?
6. Only then: clone, share (`Rc`/`Arc`), or move the check to run time (`RefCell`/`Mutex`).
