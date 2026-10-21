# Borrow and Ownership Error Code Catalog

Every borrow-checker, move and lifetime error you are likely to meet, with the exact message shapes rustc
prints, a minimal program that triggers it, the fixed program and the fixes ranked best first. Messages are
quoted from current stable rustc (edition 2021); wording of labels changes slightly between releases, the
codes and headline messages are stable. `rustc --explain E0XXX` prints the official long explanation.

## Contents

- [How to read the labels](#how-to-read-the-labels)
- [E0382 use of moved value](#e0382-use-of-moved-value)
- [E0499 two mutable borrows](#e0499-two-mutable-borrows)
- [E0502 shared and mutable borrow](#e0502-shared-and-mutable-borrow)
- [E0503 use while mutably borrowed](#e0503-use-while-mutably-borrowed)
- [E0505 move out while borrowed](#e0505-move-out-while-borrowed)
- [E0506 assign while borrowed](#e0506-assign-while-borrowed)
- [E0507 move out of a borrow](#e0507-move-out-of-a-borrow)
- [E0508 and E0509 move out of array or Drop type](#e0508-and-e0509-move-out-of-array-or-drop-type)
- [E0515 return reference to local](#e0515-return-reference-to-local)
- [E0597 does not live long enough](#e0597-does-not-live-long-enough)
- [E0716 temporary dropped while borrowed](#e0716-temporary-dropped-while-borrowed)
- [E0373 closure may outlive the function](#e0373-closure-may-outlive-the-function)
- [E0521 borrowed data escapes](#e0521-borrowed-data-escapes)
- [E0384, E0596, E0594 mutability](#e0384-e0596-e0594-mutability)
- [E0381 used before initialisation](#e0381-used-before-initialisation)
- [E0713 borrow in use when destructor runs](#e0713-borrow-in-use-when-destructor-runs)
- [E0500, E0501, E0524 closures with unique access](#e0500-e0501-e0524-closures-with-unique-access)
- [E0308 when it is about mutability](#e0308-when-it-is-about-mutability)
- [Errors without a code](#errors-without-a-code)
- [Runtime borrow panics](#runtime-borrow-panics)

## How to read the labels

| Label | Meaning |
|-------|---------|
| `^^^` (primary) | the access that is rejected |
| `---` (secondary) | the other borrow/move involved, or the later use that keeps it alive |
| "first ... borrow occurs here" / "borrow of `x` occurs here" | where the conflicting loan was created |
| "... later used here" | why the loan is still live (NLL liveness) |
| "returning this value requires that `x` is borrowed for `'1`" | the loan flows into the return value, so it is live until the function returns on every path |
| "argument requires that `x` is borrowed for `'static`" | a `'static` bound (spawn, global, `Box<dyn Trait>`) keeps the loan alive forever |
| "borrow might be used here, when `g` is dropped and runs the `Drop` code" | a destructor counts as a use |
| "let's call the lifetime of this reference `'1`" | rustc names anonymous lifetimes so it can talk about them |
| "move occurs because `x` has type `T`, which does not implement the `Copy` trait" | why it was a move, not a copy |

## E0382 use of moved value

Messages: ``use of moved value: `x` ``, ``borrow of moved value: `x` ``. Labels: "value moved here", "value used
here after move", "value moved here, in previous iteration of loop", "`x` moved due to this method call",
"`x` moved due to this implicit call to `.into_iter()`", "value moved into closure here".

```rust,compile_fail
fn consume(v: Vec<u32>) -> usize { v.len() }

fn main() {
    let v = vec![1, 2, 3];
    let n = consume(v);        // value moved here
    println!("{n} {}", v.len()); // E0382: borrow of moved value: `v`
}
```

Fixed (best first):

```rust
fn count(v: &[u32]) -> usize { v.len() }       // 1. borrow: the callee does not need ownership

fn main() {
    let v = vec![1, 2, 3];
    let n = count(&v);
    println!("{n} {}", v.len());
}
```

| Shape | Fix |
|-------|-----|
| passed to a function that only reads | change the parameter to `&T` / `&[T]` / `&str` |
| `for x in v` then `v` used | `for x in &v` (or `&mut v`); `.iter()` |
| `opt.unwrap()` / `opt.map(..)` consumes an `Option<String>` field | `opt.as_ref()`, `opt.as_deref()`, `opt.as_mut()` first |
| moved in a loop | borrow, or clone per iteration (`let tx = tx.clone();` before `spawn(move ..)`) |
| moved into a `move` closure then used | clone/`Arc::clone` into a new binding before the closure |
| builder `fn build(self)` then reuse | keep the built value; or make the builder `&mut self` returning `&mut Self` |
| genuinely need two owners | `.clone()` (small/one-off) or `Rc`/`Arc` |

`Copy` types (integers, `bool`, `char`, `&T`, tuples/arrays of `Copy`) never produce E0382. Deriving `Copy` on a
small plain-data struct (`#[derive(Clone, Copy)] struct Point { x: f32, y: f32 }`) is a legitimate fix.

## E0499 two mutable borrows

Message: ``cannot borrow `x` as mutable more than once at a time``. Labels: "first mutable borrow occurs here",
"second mutable borrow occurs here", "first borrow later used here".

```rust,compile_fail
fn main() {
    let mut s = String::from("a");
    let r1 = &mut s;
    let r2 = &mut s;   // E0499
    r1.push('b');
    r2.push('c');
}
```

Fixed: finish with `r1` before creating `r2` (NLL ends a borrow at its last use):

```rust
fn main() {
    let mut s = String::from("a");
    let r1 = &mut s;
    r1.push('b');      // last use of r1
    let r2 = &mut s;
    r2.push('c');
}
```

Common shapes and the fix that matches:

| Shape | Fix | Reference |
|-------|-----|-----------|
| `&mut v[i]` and `&mut v[j]` | `swap`, `split_at_mut`, `get_disjoint_mut` (1.86+) | [restructuring-patterns.md](restructuring-patterns.md#two-mutable-elements) |
| `map.get_mut(a)` and `map.get_mut(b)` | `HashMap::get_disjoint_mut` (1.86+) or copy one value out first | same |
| `self.helper_mut()` while holding `&mut self.field` | borrow fields directly; associated fn taking fields | [restructuring-patterns.md](restructuring-patterns.md#split-borrows-of-struct-fields) |
| return `map.get_mut(k)` on one path, `insert` on the other | entry API (NLL problem case #3) | [nll-limitations-and-polonius.md](nll-limitations-and-polonius.md) |
| cursor `cur = cur.next.as_mut().unwrap()` loops | condition-first loop | [nll-limitations-and-polonius.md](nll-limitations-and-polonius.md#cursor-loops-over-linked-structures) |
| storing `&mut` in a Vec while iterating | iterate with `iter_mut()` and collect the `&mut`s in one pass | [restructuring-patterns.md](restructuring-patterns.md) |

## E0502 shared and mutable borrow

Messages: ``cannot borrow `x` as mutable because it is also borrowed as immutable`` and the reverse ``... as
immutable because it is also borrowed as mutable``. Labels: "immutable borrow occurs here", "mutable borrow
occurs here", "immutable borrow later used here".

```rust,compile_fail
fn main() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];
    v.push(4);                // E0502: push may reallocate and dangle `first`
    println!("{first}");
}
```

Fixed:

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    let first = v[0];         // i32 is Copy: copy it out, no borrow kept
    v.push(4);
    println!("{first}");
}
```

| Shape | Fix |
|-------|-----|
| `let x = &v[..]`/`v.first()`/`map.get(k)` then mutate then use `x` | copy/clone out; move the use earlier; keep an index/key |
| `for x in &v { v.push(..) }` | collect, then `extend` after the loop; worklist with index or `VecDeque` |
| remove while iterating | `retain`, `retain_mut` (1.61+), `extract_if` (Vec 1.87+), `drain(..)` |
| `if let Some(x) = map.get(k) { map.insert(..) }` | entry API; compute the new value first, end the borrow, then insert |
| `self.items.iter()` then `self.update()` inside | borrow fields directly; snapshot the data the loop needs |
| `s.as_str()` held, then `s.push_str` | clone into `String` or finish using the slice first |

Two-phase borrows make `v.push(v.len())` legal: the `&mut v` for `push` is reserved first and activated after
the arguments are evaluated. They do not help when the argument itself needs `&mut v` (`v.push(v.pop().unwrap())`
is still E0499). Details: [ownership-and-borrowing-model.md](ownership-and-borrowing-model.md#two-phase-borrows).

## E0503 use while mutably borrowed

Message: ``cannot use `x` because it was mutably borrowed``.

```rust,compile_fail
fn main() {
    let mut value = 3;
    let borrow = &mut value;
    let sum = value + 1;      // E0503: reading `value` while `borrow` is live
    *borrow += sum;
}
```

Fixed: read before borrowing, or read through the borrow:

```rust
fn main() {
    let mut value = 3;
    let sum = value + 1;
    let borrow = &mut value;
    *borrow += sum;
}
```

## E0505 move out while borrowed

Message: ``cannot move out of `x` because it is borrowed``. Labels: "borrow of `x` occurs here", "move out of `x`
occurs here", "borrow later used here".

```rust,compile_fail
#[derive(Debug)]
struct Report { title: String, body: String }

fn publish(r: Report) { println!("{r:?}"); }

fn main() {
    let report = Report { title: "Q3".into(), body: "ok".into() };
    let title = &report.title;
    publish(report);          // E0505
    println!("published {title}");
}
```

Fixed (best first): use the borrow before the move, or take owned data out of it first.

```rust
#[derive(Debug)]
struct Report { title: String, body: String }

fn publish(r: Report) { println!("{r:?}"); }

fn main() {
    let report = Report { title: "Q3".into(), body: "ok".into() };
    let title = report.title.clone();  // small owned copy; or log before publishing
    publish(report);
    println!("published {title}");
}
```

`drop(x)` is a move too: dropping a `MutexGuard` while a reference derived from it is still used is E0505.

## E0506 assign while borrowed

Message: ``cannot assign to `x` because it is borrowed``. Labels: "`x` is borrowed here", "`x` is assigned to here
but it was already borrowed", "borrow later used here".

```rust,compile_fail
fn main() {
    let mut best = String::from("a");
    let view = &best;
    best = String::from("b");   // E0506
    println!("{view}");
}
```

Fixes: finish with `view` before assigning; or use `std::mem::replace(&mut best, new)` when you need the old
value as an owned value afterwards (`let old = mem::replace(&mut best, "b".into());`).

## E0507 move out of a borrow

Messages vary by what you move out of:

| Message | Source |
|---------|--------|
| ``cannot move out of `*r` which is behind a shared reference`` | `let x = *r;` with `r: &String` |
| ``cannot move out of `self.name` which is behind a mutable reference`` | `self.name` from `&mut self` |
| ``cannot move out of index of `Vec<String>` `` | `let s = v[0];` |
| ``cannot move out of an `Rc` `` / ``cannot move out of an `Arc` `` | `let s: String = *rc;` |
| ``cannot move out of `r` as enum variant `Some` which is behind a shared reference`` | `match *r { Some(s) => .. }` or `match self.opt { .. }` in a `&self` method |
| ``cannot move out of `cfg`, a captured variable in an `Fn` closure`` | `Fn` closure that gives away a captured value |

```rust,compile_fail
struct User { name: String, nickname: Option<String> }

fn display_name(u: &User) -> String {
    match u.nickname {           // E0507: cannot move out of `u.nickname` ... behind a shared reference
        Some(n) => n,
        None => u.name.clone(),
    }
}
```

Fixed:

```rust
struct User { name: String, nickname: Option<String> }

fn display_name(u: &User) -> &str {
    u.nickname.as_deref().unwrap_or(&u.name)   // borrow both: no allocation
}

fn take_nickname(u: &mut User) -> Option<String> {
    u.nickname.take()                          // through &mut: take and leave None
}
```

| From | Best fix |
|------|----------|
| `&T` | borrow (`&x.field`, `as_ref`, `as_deref`, `iter`), change the API to take `T`, last: `clone` |
| `&mut T` | `Option::take`, `mem::take` (needs `Default`), `mem::replace`, `Vec::drain(..)`, `Vec::swap_remove` |
| `v[i]` | `&v[i]`, `v.swap_remove(i)`, `v.remove(i)`, `mem::take(&mut v[i])`, `v.into_iter().nth(i)` when consuming |
| `Rc<T>` / `Arc<T>` | borrow; `Rc::try_unwrap(rc)`; `Arc::into_inner(arc)` (1.70+); `Rc::unwrap_or_clone` / `Arc::unwrap_or_clone` (1.76+) |
| `Fn` closure capture | make it `FnOnce`, or clone inside the closure |

## E0508 and E0509 move out of array or Drop type

E0508 ``cannot move out of type `[String; 2]`, a non-copy array``:

```rust
fn main() {
    let names = [String::from("a"), String::from("b")];
    // let first = names[0];          // E0508
    let first = &names[0];            // 1. borrow the element
    println!("{first}");
    let [a, b] = names;               // 2. or destructure to own every element (after the borrow ends)
    println!("{a} {b}");
}
```

Borrowing and consuming cannot overlap: using `first` after `let [a, b] = names;` would be E0505.

E0509 ``cannot move out of type `Conn`, which implements the `Drop` trait``:

```rust
struct Conn { addr: String }
impl Drop for Conn { fn drop(&mut self) { println!("closing {}", self.addr); } }

fn into_addr(mut c: Conn) -> String {
    // let Conn { addr } = c;            // E0509: Drop needs the whole value
    std::mem::take(&mut c.addr)          // leaves an empty String for drop() to see
}
```

## E0515 return reference to local

Messages: ``cannot return reference to local variable `x` ``, ``cannot return value referencing local variable
`x` ``, ``cannot return reference to temporary value``, ``cannot return value referencing function parameter `x` ``.

```rust,compile_fail
fn label(id: u32) -> &'static str {
    let s = format!("order-{id}");
    &s                                  // E0515: cannot return reference to local variable `s`
}
```

Fixed (best first):

```rust
use std::borrow::Cow;

fn label(id: u32) -> String { format!("order-{id}") }     // 1. return the owned value

fn trimmed(input: &str) -> &str { input.trim() }           // 2. borrow from an input instead

fn normalised(input: &str) -> Cow<'_, str> {               // 3. borrow when possible, allocate when needed
    if input.contains(' ') { Cow::Owned(input.replace(' ', "_")) } else { Cow::Borrowed(input) }
}

fn render(id: u32, out: &mut String) {                     // 4. caller owns the buffer
    use std::fmt::Write;
    write!(out, "order-{id}").unwrap();
}
```

Iterators: `fn evens(&self) -> impl Iterator<Item = &u32> + '_ { self.v.iter().filter(|x| *x % 2 == 0) }`
returns a lazy view instead of collecting references to a local `Vec`.

## E0597 does not live long enough

Message: ``` `x` does not live long enough ```. Labels: "binding `x` declared here", "borrowed value does not
live long enough", "`x` dropped here while still borrowed", "borrow later used here", and for `'static`
bounds "argument requires that `x` is borrowed for `'static`".

```rust,compile_fail
fn main() {
    let r;
    {
        let s = String::from("hi");
        r = &s;                // E0597
    }                          // `s` dropped here while still borrowed
    println!("{r}");
}
```

Fixes: declare `s` in the outer scope; store the owned `String` in `r`; for spawned work see
[threads-async-and-closures.md](threads-async-and-closures.md). A frequent edition-2021-only variant:

```rust
use std::cell::RefCell;

fn len_2021() -> usize {
    let cell = RefCell::new(vec![1, 2, 3]);
    let n = cell.borrow().len();   // bind first: compiles in every edition
    n
    // `cell.borrow().len()` as the tail expression is E0597 in edition 2021 (the temporary `Ref`
    // lives until after `cell` is dropped) and compiles in edition 2024.
}
```

## E0716 temporary dropped while borrowed

Message: ``temporary value dropped while borrowed``. Labels: "creates a temporary value which is freed while
still in use", "temporary value is freed at the end of this statement", "borrow later used here"; note "consider
using a `let` binding to create a longer lived value".

```rust,compile_fail
fn main() {
    let words: Vec<&str> = String::from("a b c").split(' ').collect(); // E0716
    println!("{words:?}");
}
```

Fixed:

```rust
use std::sync::Mutex;

fn main() {
    let text = String::from("a b c");                  // owner lives as long as `words`
    let words: Vec<&str> = text.split(' ').collect();
    println!("{words:?}");

    let names = Mutex::new(vec![String::from("x")]);
    let guard = names.lock().unwrap();                 // bind the guard, borrow from it
    let first: &str = &guard[0];
    println!("{first}");
}
```

`let r = &String::from("x");` is fine: temporary lifetime extension applies to `&temp` directly in a `let`
initialiser, but not to method calls on the temporary (`String::from("x").as_str()`).

## E0373 closure may outlive the function

Messages: ``closure may outlive the current function, but it borrows `x`, which is owned by the current
function`` and the async variant ``async block may outlive the current function, but it borrows `x` ...``.
Help: "to force the closure to take ownership of `x` (and any other referenced variables), use the `move`
keyword".

```rust,compile_fail
use std::thread;

fn main() {
    let names = vec![String::from("a")];
    let h = thread::spawn(|| println!("{names:?}"));   // E0373
    h.join().unwrap();
}
```

Fixed: `thread::spawn(move || println!("{names:?}"))`; if `names` is still needed afterwards, clone or `Arc` it
first, or use `thread::scope`. Full treatment: [threads-async-and-closures.md](threads-async-and-closures.md).

## E0521 borrowed data escapes

Messages: ``borrowed data escapes outside of function`` (also "of closure", "of method", "of associated
function"). Labels: "`cfg` is a reference that is only valid in the function body", "`cfg` escapes the function
body here", "argument requires that `'1` must outlive `'static`".

```rust,compile_fail
struct Config { name: String }

fn start(cfg: &Config) {
    std::thread::spawn(move || println!("{}", cfg.name));   // E0521
}
```

Fixed: own the data (`let name = cfg.name.clone(); spawn(move || println!("{name}"))`), take
`cfg: Arc<Config>`, or use `thread::scope` if the thread may finish before `start` returns.

## E0384, E0596, E0594 mutability

| Code | Message | Fix |
|------|---------|-----|
| E0384 | ``cannot assign twice to immutable variable `x` `` | `let mut x`, or shadow with `let x = ...;` |
| E0596 | ``cannot borrow `v` as mutable, as it is not declared as mutable`` | `let mut v` / `fn f(mut v: Vec<T>)` |
| E0596 | ``cannot borrow `*v` as mutable, as it is behind a `&` reference`` | take `&mut`; `iter_mut()`; `get_mut()` |
| E0596 | ``cannot borrow data in an `Rc` as mutable`` | `Rc::get_mut`, `Rc::make_mut`, `Rc<RefCell<T>>` |
| E0596 | ``cannot borrow data in dereference of `Arc<Vec<u32>>` as mutable`` | `Arc::make_mut`, `Arc<Mutex<T>>` |
| E0594 | ``cannot assign to `p.x`, as `p` is not declared as mutable`` | `let mut p` |
| E0594 | ``cannot assign to `*r`, which is behind a `&` reference`` | `&mut` parameter; `Cell` for Copy fields |
| E0594 | ``cannot assign to data in an `Rc` `` | `RefCell`/`Cell` inside the `Rc` |

```rust
use std::rc::Rc;

fn main() {
    let mut shared = Rc::new(vec![1, 2, 3]);
    let other = Rc::clone(&shared);
    Rc::make_mut(&mut shared).push(4);   // clones the Vec because `other` still shares it
    assert_eq!(*other, vec![1, 2, 3]);
    assert_eq!(*shared, vec![1, 2, 3, 4]);
}
```

## E0381 used before initialisation

Messages: ``used binding `x` isn't initialized`` and ``used binding `x` is possibly-uninitialized`` (older
compilers: ``use of possibly-uninitialized `x` ``).

```rust,compile_fail
fn parse(flag: bool) -> u32 {
    let port: u32;
    if flag { port = 8080; }
    port                       // E0381: possibly-uninitialized
}
```

Fixed:

```rust
fn parse(flag: bool) -> u32 {
    let port = if flag { 8080 } else { 80 };
    port
}

fn parse_opt(input: Option<&str>) -> Result<u32, String> {
    let Some(text) = input else { return Err("missing".into()) };   // let-else, 1.65+
    text.parse().map_err(|e| format!("{e}"))
}
```

## E0713 borrow in use when destructor runs

Message: ``borrow may still be in use when destructor runs``.

```rust,compile_fail
pub struct Guard<'a> { data: &'a mut String }

impl Drop for Guard<'_> {
    fn drop(&mut self) { self.data.push_str(" (released)"); }
}

pub fn inner<'a>(g: Guard<'a>) -> &'a mut String {
    &mut *g.data                // E0713: drop(g) at the end needs exclusive access to *g.data
}
```

Fixes: return owned data, do the work inside the function and return a result, or design the API so callers
pass the `&'a mut String` directly and the guard is created inside a narrower scope.

## E0500, E0501, E0524 closures with unique access

| Code | Message | Typical cause |
|------|---------|---------------|
| E0500 | ``closure requires unique access to `x` but it is already borrowed`` | mutating closure created while `&x` is live |
| E0501 | ``cannot borrow `x` as mutable because previous closure requires unique access`` | using `x` while a mutating closure is still alive |
| E0524 | ``two closures require unique access to `x` at the same time`` | two live closures both mutate `x` |

```rust
fn main() {
    let mut count = 0;
    let mut inc = || count += 1;
    // println!("{count}");      // E0502 here: `inc` holds a unique borrow until its last call
    inc();
    inc();
    println!("{count}");          // fine: `inc` is no longer used
}
```

Fix by passing state as an argument (`let inc = |c: &mut u32| *c += 1;`), by ordering uses so the closure's last
call comes first, or by sharing a `Cell<u32>`.

## E0308 when it is about mutability

E0308 is the general "mismatched types" error; it is a borrow topic only when the note says ``types differ in
mutability`` or `expected &mut T, found &T`:

```rust
fn bump(n: &mut u32) { *n += 1; }

fn main() {
    let mut n = 0;
    // bump(&n);            // E0308: expected `&mut u32`, found `&u32` (types differ in mutability)
    bump(&mut n);
    println!("{n}");
}
```

## Errors without a code

| Message | Meaning | Fix |
|---------|---------|-----|
| `lifetime may not live long enough` | NLL needs `'a: 'b` that the signature does not state; label shows "returning this value requires that `'1` must outlive `'2`" | return a borrow of the input you actually borrow from; add the bound `'a: 'b` if correct; return owned |
| ``captured variable cannot escape `FnMut` closure body`` | an `FnMut` returns a reference into its captured state | return owned values; use a loop |
| `future cannot be sent between threads safely` | non-`Send` value alive across `.await` in a spawned future | scope the guard; `Arc` not `Rc` |
| ``the parameter type `T` may not live long enough`` (E0310/E0309) | storing `T` in something `'static` needs `T: 'static` | add `T: 'static` or a lifetime bound |

```rust
struct Store { items: Vec<String> }

impl Store {
    // fn find(&self, key: &str) -> &str { key }     // lifetime may not live long enough:
    //                                               // elision ties the output to &self, but we return `key`
    fn find<'k>(&self, key: &'k str) -> &'k str { key }
    fn first(&self) -> &str { &self.items[0] }       // borrowing from self: elision is right
}
```

## Runtime borrow panics

| Panic text | Cause | Fix |
|------------|-------|-----|
| `already borrowed: BorrowMutError` | `borrow_mut()` while a `Ref` or `RefMut` of the same `RefCell` is alive | end the earlier guard (block, `drop`, copy out in one statement) |
| `already mutably borrowed: BorrowError` | `borrow()` while a `RefMut` is alive | same; avoid calling back into the owner while holding `borrow_mut()` |
| ``called `Result::unwrap()` on an `Err` value: PoisonError { .. }`` | a thread panicked while holding a `Mutex`/`RwLock` | fix that first panic; `unwrap_or_else(PoisonError::into_inner)` if data is still valid |
| deadlock (no panic) on `std::sync::Mutex` | locking the same mutex twice on one thread | shorter critical sections; never call out while locked |

`RefCell` panics carry the caller location (`#[track_caller]`), so `panicked at src/bus.rs:41:38` points at the
`borrow_mut()` that failed; the guard that is still alive is usually a few lines above or in the caller. See
[shared-ownership-and-interior-mutability.md](shared-ownership-and-interior-mutability.md).
