---
name: rust-borrow-checker-error-explainer
description: "Explain and fix Rust borrow-checker, ownership, move and lifetime compiler errors: E0382 use of moved value, E0499 cannot borrow as mutable more than once, E0502 also borrowed as immutable, E0505, E0506, E0503, E0507 cannot move out of index/Rc/reference, E0515 return reference to local, E0597 does not live long enough, E0716 temporary value dropped while borrowed, E0373 closure may outlive (spawn needs move), E0521 borrowed data escapes, E0384, E0596, E0594, E0381, E0713, 'lifetime may not live long enough', RefCell 'already borrowed: BorrowMutError' panics. Ranks fixes from restructuring (split borrows, entry API, split_at_mut, get_disjoint_mut, mem::take, Option::take, indices, thread::scope) down to clone and Rc<RefCell>/Arc<Mutex>; never unsafe. Covers NLL limits (get-or-insert), iterator invalidation, closure captures, self-referential structs. Ships std-only Rust triage tools. Use when Rust fails to compile with a borrow/ownership error or the user is fighting the borrow checker."
metadata:
  category: programming
  subcategory: rust
  version: "1.0.0"
---

# Rust Borrow Checker Error Explainer

Turn a wall of `error[E0502]` output into a named root cause and the least invasive fix. Read the three
points every borrow error has (where the borrow starts, where the conflicting access happens, where the first
borrow is used later), recognise which of a dozen recurring shapes it is (iterate-and-mutate, conditional return
of a borrow, two `&mut` into one Vec, whole-`self` method borrows, move into a spawned task, temporary guard),
and fix it by restructuring first. `clone()`, `Rc<RefCell<_>>` and `Arc<Mutex<_>>` are legitimate but come
last; `unsafe` is never a fix for a borrow error. Three small std-only Rust programs in `scripts/` do the
triage: on real `cargo check` output (text or `--message-format=json`), on a single error code, and on runtime
RefCell/Mutex panics.

## Trigger Conditions

Activate this skill when the user:
- Pastes `cargo build` / `cargo check` / `cargo test` / rust-analyzer output containing E0382, E0499, E0502,
  E0503, E0505, E0506, E0507, E0508, E0509, E0515, E0521, E0373, E0381, E0384, E0594, E0596, E0597, E0713,
  E0716, E0500/E0501/E0524, or `lifetime may not live long enough`
- Sees "first mutable borrow occurs here", "immutable borrow later used here", "value moved here",
  "returning this value requires that", "argument requires that `x` is borrowed for `'static`", "dropped here
  while still borrowed", "creates a temporary value which is freed while still in use"
- Hits a runtime panic `already borrowed: BorrowMutError`, `already mutably borrowed: BorrowError`, or
  `called Result::unwrap() on an Err value: PoisonError`
- Gets "future cannot be sent between threads safely" because a `MutexGuard`/`Rc` lives across `.await`
- Asks how to mutate a Vec while iterating, get two `&mut` into a slice/HashMap, return a reference from a
  function, share state with `thread::spawn`/`tokio::spawn`, or store a reference in a struct
- Says "fighting the borrow checker", "should I just clone?", "do I need Rc<RefCell>?"

## Workflow

```
0. BUILD     -> once per session; std only, about 1 s each ($SKILL = this skill's folder):
                for t in parse_diagnostics explain_code runtime_panic; do
                  rustc -O --edition 2021 "$SKILL/scripts/$t.rs" -o "/tmp/$t"; done
1. CAPTURE   -> cargo check 2> build.txt   (or: cargo check --message-format=json > build.jsonl)
2. TRIAGE    -> /tmp/parse_diagnostics build.txt
                Extracts code, location and labels, names the pattern (BCK0xx), ranks fixes
3. READ      -> For each error find the three points: borrow created / conflicting use / borrow later used
                Fix the FIRST error per function; later ones are often consequences
4. CHOOSE    -> Walk the fix ladder top-down (restructure > std API > own > share > last resort)
                /tmp/explain_code E0502          # one code (or pattern, e.g. BCK002) in full
5. FIX       -> Smallest change that removes the overlap; keep the original intent and data flow
6. VERIFY    -> cargo check again; panics in tests: cargo test 2>&1 | /tmp/runtime_panic -
```

## Reading a Borrow Error

Every borrow conflict has the same anatomy. Find the three labels before touching code:

```
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> src/main.rs:4:5
  |
3 |     let first = &v[0];          <- 1. borrow CREATED ("immutable borrow occurs here")
4 |     v.push(4);                  <- 2. CONFLICTING access ("mutable borrow occurs here", primary ^^^)
5 |     println!("{first}");        <- 3. borrow still USED LATER ("immutable borrow later used here")
```

The fix always removes one of the three: end the borrow before point 2 (copy the value out, reorder), make
point 2 not need the whole value (borrow a field, use a disjoint API), or make point 3 not need the reference
(use an index/key, an owned copy). If label 3 is missing, the borrow is held by something that outlives the
statement: a returned value ("returning this value requires that ..."), a `'static` bound ("argument requires
that `x` is borrowed for `'static`"), or a destructor ("borrow might be used here, when `guard` is dropped").

## Error Code Decision Table

| Code | Message (abridged) | Usually means | First fix to try |
|------|--------------------|---------------|------------------|
| E0382 | use/borrow of moved value | value moved (call, `for x in v`, `move` closure, `self` method) then reused | borrow instead (`&v`, `.iter()`, `.as_ref()`), reorder, clone per iteration |
| E0499 | cannot borrow as mutable more than once | two live `&mut` to one place | end the first; split fields; `split_at_mut`/`get_disjoint_mut`; entry API |
| E0502 | borrowed as immutable / mutable | `&` kept alive across a mutation | copy out first; collect-then-apply; `retain`/`extract_if`; index |
| E0503 | cannot use because mutably borrowed | read the original while a `&mut` is live | use through the `&mut`, or finish with it first |
| E0505 | cannot move out because it is borrowed | move/`drop` while a reference is used later | move after last use; take owned data from the borrow first |
| E0506 | cannot assign because it is borrowed | overwrite while a reference is used later | finish with the reference; `mem::replace` |
| E0507 | cannot move out of `*x` / index / `Rc` | taking ownership through a borrow | borrow; `Option::take`/`mem::take`/`mem::replace`; `swap_remove`; `Rc::unwrap_or_clone` |
| E0508/E0509 | move out of array / Drop type | by-value index of `[T; N]`, destructuring a `Drop` struct | borrow, destructure the array, `mem::take` the field |
| E0515 | cannot return reference to local | returning `&` into data the fn owns | return owned (`String`, `Vec`), borrow from an input, `Cow` |
| E0597 | does not live long enough | reference outlives its owner (scope or `'static`) | move the owner outward; own the data; `thread::scope`; `Arc` |
| E0716 | temporary value dropped while borrowed | reference into a statement temporary (`lock()`, `format!`) | `let`-bind the temporary; keep the owned value |
| E0373 | closure may outlive the current function | non-`move` closure/async block given to `spawn` | `move` + owned/`Arc` data; `thread::scope` |
| E0521 | borrowed data escapes outside of function | `&` parameter sent into a `'static` context | owned data / `Arc` parameter; `thread::scope` |
| E0596/E0594 | cannot borrow/assign as mutable | not `mut`, behind `&`, or inside `Rc`/`Arc` | `let mut`; `&mut self`/`iter_mut`; `RefCell`/`Mutex`/`make_mut` |
| E0384 | cannot assign twice to immutable variable | missing `mut` | `let mut` or shadow with a new `let` |
| E0381 | used binding isn't initialized | assigned on some paths only | `let x = if/match ...`, `let ... else` |
| E0713 | borrow may still be in use when destructor runs | returning a reborrow through a `Drop` type | return owned data or take the inner `&'a mut` |
| (none) | lifetime may not live long enough | signature lifetimes do not match the data flow | tie output to the right input; return owned |
| (none) | future cannot be sent between threads safely | `MutexGuard`/`Rc`/`RefMut` alive at `.await` | scope the guard in a block before `.await` |

Every code with a minimal failing program and the fixed version: [error-code-catalog.md](references/error-code-catalog.md).

## The Fix Ladder

Try fixes in this order; stop at the first that keeps the code clear. The script labels every fix with its tier.

| Tier | Examples | Cost |
|------|----------|------|
| 1. restructure | reorder statements, shorten a borrow with a block, copy a `Copy` value out, borrow disjoint fields, collect-then-apply, pass `&` instead of moving | none |
| 2. std api | `entry()`, `split_at_mut`, `get_disjoint_mut` (1.86+), `swap`, `retain`/`retain_mut`, `extract_if` (1.87+), `mem::take`/`replace`, `Option::take`/`as_ref`/`as_mut`, `thread::scope` (1.63+) | none |
| 3. own the data | return `String`/`Vec`, indices or keys instead of references, arenas (`Vec<Node>` + `usize`), `clone()` of small or once-per-request data | an allocation/copy |
| 4. shared ownership | `Rc<T>`/`Arc<T>` clones of a handle; `Arc<Mutex<T>>`/`Rc<RefCell<T>>` when shared mutation is the real design | refcount, runtime checks, possible panics/deadlocks |
| 5. last resort | `Box::leak` for program-lifetime data; `polonius-the-crab` for the conditional-return case | leaks / extra dependency |

Never: `unsafe` pointer casts, `transmute` of lifetimes, `&T as *const T as *mut T`. They turn a compile error
into undefined behaviour. If a design truly needs aliasing mutation, use `Cell`/`RefCell`/atomics/`Mutex`.

## Core Rules

1. **Shared XOR mutable.** At any point, a place has either any number of live `&` or exactly one live `&mut`.
2. **Liveness, not scope (NLL).** A borrow lasts until its last use, not until the closing brace, unless the
   type has a destructor that uses it (guards, iterators holding borrows) or it flows into a return value.
3. **Moves end bindings.** After `let b = a;` / `f(a)` / `for x in a` / `a.into_iter()`, `a` is dead unless
   its type is `Copy`. Borrow (`&a`) when the callee does not need ownership.
4. **Methods borrow all of `self`.** `self.a_mut()` and `self.b()` conflict even if they touch different fields;
   direct field access (`&mut self.a`, `&self.b`) does not.
5. **The checker cannot see indices.** `&mut v[i]` and `&mut v[j]` conflict because `i == j` is possible; use
   APIs that prove disjointness.
6. **`'static` bounds mean "owns everything".** `thread::spawn`, `tokio::spawn`, `Box<dyn Any>` need owned or
   `Arc` data; `move` alone does not help if what is moved is a reference.
7. **Fix the first error.** One bad borrow often produces several errors; recheck after each fix.
8. **Clone deliberately.** Cloning a small `String` once per request is fine; cloning a `Vec` inside a hot loop to
   silence the checker is a design smell. Prefer restructuring, then decide.

## Fix Patterns (runnable, edition 2021, MSRV noted)

**Iterate-and-mutate (BCK001): collect first, then mutate.**

```rust
#[derive(Clone, Debug)]
struct Order { id: u32, qty: u32 }

fn split_large(orders: &mut Vec<Order>) {
    // for o in orders.iter() { if o.qty > 10 { orders.push(..) } }   // E0502
    let extra: Vec<Order> = orders
        .iter()
        .filter(|o| o.qty > 10)
        .map(|o| Order { id: o.id + 1000, qty: o.qty - 10 })
        .collect();
    for o in orders.iter_mut().filter(|o| o.qty > 10) {
        o.qty = 10;
    }
    orders.extend(extra);
    orders.retain(|o| o.qty > 0); // remove-while-iterating: retain / extract_if (1.87+)
}
```

**Conditional return of a borrow (BCK002): use the entry API.** Current NLL rejects returning `map.get_mut(k)`
on one path and inserting on the other (E0499), even though it is sound.

```rust
use std::collections::HashMap;

fn get_or_default<'m>(map: &'m mut HashMap<String, Vec<u32>>, key: &str) -> &'m mut Vec<u32> {
    // if let Some(v) = map.get_mut(key) { return v; }   // E0499 on the insert below
    // map.insert(key.to_owned(), Vec::new());
    map.entry(key.to_owned()).or_default()
}

fn get_or_default_lookup_first<'m>(map: &'m mut HashMap<String, Vec<u32>>, key: &str) -> &'m mut Vec<u32> {
    if map.contains_key(key) {         // check first: no borrow escapes the condition, no to_owned() on hits
        return map.get_mut(key).unwrap();
    }
    map.entry(key.to_owned()).or_default()
}
```

**Two `&mut` into one slice (BCK003).**

```rust
struct Account { balance: i64 }

fn transfer(accounts: &mut [Account], from: usize, to: usize, amount: i64) -> Result<(), String> {
    // let a = &mut accounts[from]; let b = &mut accounts[to];      // E0499
    let [a, b] = accounts
        .get_disjoint_mut([from, to])                              // Rust 1.86+
        .map_err(|e| format!("bad indices: {e:?}"))?;
    a.balance -= amount;
    b.balance += amount;
    Ok(())
}

fn transfer_pre_1_86(accounts: &mut [Account], from: usize, to: usize, amount: i64) {
    assert!(from != to);
    let (lo, hi) = (from.min(to), from.max(to));
    let (left, right) = accounts.split_at_mut(hi);                 // any Rust version
    let (low, high) = (&mut left[lo], &mut right[0]);
    let (a, b) = if from < to { (low, high) } else { (high, low) };
    a.balance -= amount;
    b.balance += amount;
}
```

**Whole-`self` method borrows (BCK004): borrow fields, not `self`.**

```rust
struct Cart { items: Vec<u32>, discount: u32, log: Vec<String> }

impl Cart {
    fn apply(&mut self) {
        // for i in self.items.iter_mut() { self.record(*i) }   // E0499: record takes &mut self
        let discount = self.discount;                       // Copy value out
        let log = &mut self.log;                            // disjoint field borrows are fine
        for item in self.items.iter_mut() {
            *item = item.saturating_sub(discount);
            log.push(format!("item now {item}"));
        }
    }
}
```

**Moving out of `&mut self` (BCK013): `Option::take`, `mem::take`, `mem::replace`.**

```rust
use std::mem;

enum Conn { Idle, Open(String), Closed }

struct Client { conn: Conn, pending: Vec<String>, token: Option<String> }

impl Client {
    fn close(&mut self) -> Option<String> {
        // let Conn::Open(addr) = self.conn else { .. }      // E0507 move out of borrow
        match mem::replace(&mut self.conn, Conn::Closed) {
            Conn::Open(addr) => Some(addr),
            other => { self.conn = other; None }
        }
    }
    fn drain(&mut self) -> Vec<String> { mem::take(&mut self.pending) }
    fn take_token(&mut self) -> Option<String> { self.token.take() }
}
```

**Threads and tasks (BCK015): `move` owned or `Arc` data; scoped threads to borrow.**

```rust
use std::sync::Arc;
use std::thread;

fn spawn_workers(config: Arc<String>, rows: &[u64]) -> u64 {
    let handles: Vec<_> = (0..2)
        .map(|i| {
            let config = Arc::clone(&config);               // clone the handle, move the clone
            thread::spawn(move || format!("{config}-{i}").len())
        })
        .collect();
    for h in handles { h.join().unwrap(); }

    thread::scope(|s| {                                     // Rust 1.63+: may borrow `rows`
        let (a, b) = rows.split_at(rows.len() / 2);
        // `a`/`b` are locals of this closure: `move` copies the slice references in
        let left = s.spawn(move || a.iter().sum::<u64>());
        let right = s.spawn(move || b.iter().sum::<u64>());
        left.join().unwrap() + right.join().unwrap()
    })
}
```

Tokio is the same rule: `tokio::spawn` needs `Future + Send + 'static`, so write `tokio::spawn(async move { ... })`
with owned/`Arc` captures, and never keep a `std::sync::MutexGuard` alive across `.await`. Details and async
patterns: [threads-async-and-closures.md](references/threads-async-and-closures.md).

**RefCell panics (BCK024): end the guard before calling out.**

```rust
use std::cell::RefCell;
use std::rc::Rc;

struct Bus { listeners: RefCell<Vec<Rc<dyn Fn(&Bus, &str)>>> }

impl Bus {
    fn emit(&self, msg: &str) {
        // for l in self.listeners.borrow().iter() { l(self, msg) }  // panics if a listener subscribes
        let snapshot: Vec<_> = self.listeners.borrow().clone();     // Ref dropped at the `;`
        for l in snapshot { l(self, msg); }
    }
    fn subscribe(&self, f: Rc<dyn Fn(&Bus, &str)>) { self.listeners.borrow_mut().push(f); }
}
```

More patterns (state machines, arenas and indices, graphs, self-referential structs, lending iterators):
[restructuring-patterns.md](references/restructuring-patterns.md).

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| E0502 with `for x in &v` / `v.iter()` and `v.push` in the body | iterator invalidation (BCK001) | collect then `extend`; `retain`; index/`VecDeque` worklist |
| E0499/E0502 + "returning this value requires that" | conditional return of borrow, NLL limitation (BCK002) | `entry()`; `contains_key` then `get_mut`; return index |
| E0499 with `&mut v[i]` twice | checker cannot prove `i != j` (BCK003) | `swap`, `split_at_mut`, `get_disjoint_mut` (1.86+) |
| E0499/E0502 on `*self` across two method calls | methods borrow the whole struct (BCK004) | borrow fields directly; associated fn on fields; sub-struct |
| E0382 "value moved here, in previous iteration of loop" | move inside a loop (BCK006) | borrow; clone per iteration (`Arc`, `Sender`) |
| E0382 "moved due to this implicit call to `.into_iter()`" | `for x in v` consumes `v` (BCK007) | `for x in &v` / `&mut v` |
| E0507 "cannot move out of index of `Vec<T>`" | by-value index (BCK011) | `&v[i]`, `swap_remove`, `mem::take`, `into_iter` |
| E0507 "behind a mutable reference" | moving a field out of `&mut self` (BCK013) | `take()`, `mem::take`, `mem::replace` |
| E0507 "cannot move out of an `Rc`" | ownership through shared pointer (BCK012) | borrow; `Rc::try_unwrap`; `Rc::unwrap_or_clone` (1.76+) |
| E0373 / E0597 "borrowed for `'static`" with `spawn` | spawned work must own its data (BCK015) | `move` + owned/`Arc`; `thread::scope` |
| E0716 on `x.lock().unwrap().iter()` | guard temporary dropped at `;` (BCK019) | `let guard = x.lock().unwrap();` |
| E0515 returning `&str` from `format!`/`String` | returning reference to local (BCK018) | return `String`; `Cow<'_, str>` |
| E0596 "behind a `&` reference" | `&self` method mutates (BCK023) | `&mut self`, `iter_mut`; `Cell`/`RefCell` if by design |
| E0596/E0594 "data in an `Rc`" | `Rc`/`Arc` only hand out `&T` (BCK022) | `Rc::make_mut`, `Rc<RefCell<T>>`, `Arc<Mutex<T>>` |
| `already borrowed: BorrowMutError` at run time | overlapping `RefCell` guards / re-entrant callback (BCK024) | shorter guards; snapshot before callbacks; `try_borrow_mut` |
| `PoisonError` on `lock().unwrap()` | an earlier panic while holding the lock (BCK025) | fix the first panic; `unwrap_or_else(PoisonError::into_inner)` |
| "future cannot be sent between threads safely" + `MutexGuard` | guard held across `.await` (BCK026) | scope guard in a block; `tokio::sync::Mutex` only if held across await |
| Compiled on edition 2021, E0502/E0505 after moving to 2024 | RPIT now captures all in-scope lifetimes | `+ use<'a, T>` precise capturing (1.82+) on the return type |
| `struct Parser { text: String, tokens: Vec<&str> }` will not compile | self-referential struct | store ranges/indices; split owner and view; `self_cell`/`yoke` |

NLL limitations (problem case #3, cursor loops), Polonius status and two-phase borrows:
[nll-limitations-and-polonius.md](references/nll-limitations-and-polonius.md). Ownership model, drop scopes and
temporaries: [ownership-and-borrowing-model.md](references/ownership-and-borrowing-model.md).

## Version Notes

| Rust | Change relevant to borrow errors |
|------|----------------------------------|
| 1.31 (edition 2018) | NLL borrow checker (2015 edition from 1.36; old AST checker removed in 1.63) |
| 1.56 (edition 2021) | closures capture disjoint fields (`self.a`), not the whole `self` |
| 1.63 | `std::thread::scope` (scoped threads borrow locals) |
| 1.65 | `let ... else`; generic associated types (lending iterators) |
| 1.70 / 1.76 | `Arc::into_inner` / `Rc::unwrap_or_clone`, `Arc::unwrap_or_clone` |
| 1.77 | `Mutex::clear_poison`, `RwLock::clear_poison` |
| 1.80 | `LazyLock`, `LazyCell`, `Option::take_if` |
| 1.82 | precise capturing `impl Trait + use<'a, T>` |
| 1.85 (edition 2024) | tail-expression temporaries dropped before locals; `if let` scrutinee temporaries dropped before `else`; RPIT captures all in-scope lifetimes; async closures |
| 1.86 | `<[T]>::get_disjoint_mut`, `HashMap::get_disjoint_mut` |
| 1.87 | `Vec::extract_if` |

Full table and migration notes: [version-history-and-testing.md](references/version-history-and-testing.md).

## Output Format

When explaining a borrow error, answer with:
1. **Diagnosis** - the code, the place (`self.orders`, `map`), and the three points (created / conflicting /
   used later) quoted from the labels, with file:line.
2. **Pattern** - the named shape (BCK id when the script reports one) in one sentence: why the code is rejected.
3. **Fix** - the best rung of the ladder as complete before/after code that compiles on the user's edition and
   MSRV; name any feature that needs a newer Rust.
4. **Alternatives** - one or two lower rungs with their cost (allocation, refcount, runtime panic risk).
5. **Verify** - `cargo check` (and the test or `--strict` script run) that should now pass.

If the snippet is too short to see the conflicting use, ask for the full `cargo check` output or the function,
and run the script on it rather than guessing.

## Scripts

Small, standard-library-only Rust programs. They read text you give them and never run cargo. Compile each
once with `rustc -O --edition 2021 scripts/<name>.rs -o /tmp/<name>` (no Cargo project, no crates).

| Script | Job |
|--------|-----|
| `scripts/parse_diagnostics.rs` | Every error in rustc/cargo output (text or JSON lines, mixed is fine): code, location, labels with source line numbers, compiler `help:` lines, pattern, fixes ranked by tier. Warnings are counted and skipped |
| `scripts/explain_code.rs` | One code (`E0502`, `lifetime`, `not-send`) or pattern (`BCK002`, `iterate-and-mutate`) in full; `--list` shows everything covered |
| `scripts/runtime_panic.rs` | Panics in `cargo test`/program output: `already borrowed: BorrowMutError` (BCK024) and `PoisonError` (BCK025), linked to the earlier panic that poisoned the lock |
| `scripts/catalog.rs` | Shared module: codes, patterns and ranked fixes (add new patterns here) |
| `scripts/common.rs` | Shared module: input reading, JSON output, extraction of cargo JSON `rendered` text |

```bash
/tmp/parse_diagnostics build.txt                         # cargo check 2> build.txt
cargo check --message-format=json | /tmp/parse_diagnostics -
/tmp/parse_diagnostics build.jsonl --json                # machine-readable report
/tmp/parse_diagnostics build.txt --strict                # CI: exit 1 if an error is not borrow-related
/tmp/explain_code E0502                                  # also: BCK002, iterate-and-mutate, lifetime
/tmp/explain_code --list --json
cargo test 2>&1 | /tmp/runtime_panic - --strict
```

Exit codes (all three): 0 done, 1 with `--strict` when an error or panic is not a borrow/ownership problem
(listed as "other", never guessed at), 2 usage error, unreadable or empty input, or an unknown code.

| Pattern | Name | Codes |
|---------|------|-------|
| BCK001 | iterate-and-mutate | E0499, E0502 |
| BCK002 | conditional-return-of-borrow (NLL problem case #3) | E0499, E0502, E0505, E0506 |
| BCK003 | two-elements-mut | E0499 |
| BCK004 | whole-self-borrow | E0499, E0502 |
| BCK005 | shared-borrow-held-across-mutation | E0502 |
| BCK006-BCK010 | loop-move, implicit-into-iter, moved-into-closure, consumed-by-method, partial-move | E0382 |
| BCK011-BCK014 | move-out-of-index, move-out-of-rc, move-out-of-mut-ref, move-out-of-shared-ref | E0507, E0508 |
| BCK015-BCK017 | spawn-needs-move, static-requirement, closure-borrow-escapes | E0373, E0597, E0521, E0716, lifetime |
| BCK018-BCK020 | return-ref-to-local, lock-or-borrow-temporary, temporary-dropped | E0515, E0716 |
| BCK021-BCK023 | binding-not-mut, mutate-through-rc, mutate-behind-shared-ref | E0384, E0594, E0596 |
| BCK024-BCK026 | refcell-double-borrow, mutex-poisoned, guard-across-await | runtime panics, not-Send future |
| BCK027-BCK030 | uninitialized-on-some-path, drop-needs-exclusive, mutability-mismatch, closure-unique-access | E0381, E0713, E0308, E0500/E0501/E0524 |

## Additional Resources

| File | Content |
|------|---------|
| [error-code-catalog.md](references/error-code-catalog.md) | Every borrow/ownership code: exact messages, minimal failing program, fixed program, ranked fixes |
| [ownership-and-borrowing-model.md](references/ownership-and-borrowing-model.md) | Moves, Copy, reborrows, NLL liveness, two-phase borrows, places and disjoint fields, closure captures, temporaries and drop scopes, lifetime elision |
| [restructuring-patterns.md](references/restructuring-patterns.md) | Collect-then-apply, split borrows, `split_at_mut`/`get_disjoint_mut`, entry API, `mem::take`/`replace`, state machines, indices/arenas, graphs, self-referential structs |
| [nll-limitations-and-polonius.md](references/nll-limitations-and-polonius.md) | Sound code NLL rejects: conditional return, cursor loops, get-or-insert; workarounds; Polonius status |
| [shared-ownership-and-interior-mutability.md](references/shared-ownership-and-interior-mutability.md) | Clone tradeoffs, `Cow`, `Rc`/`Arc`, `Cell`/`RefCell`/`Mutex`/`RwLock`/atomics, runtime borrow panics, poisoning |
| [threads-async-and-closures.md](references/threads-async-and-closures.md) | E0373/E0521/E0597 with `thread::spawn`/`tokio::spawn`, `move`, `Arc`, scoped threads, guards across `.await`, `FnMut` escapes |
| [version-history-and-testing.md](references/version-history-and-testing.md) | Editions and stabilisations that change borrow errors, edition 2024 migration, `compile_fail` doctests, trybuild, CI with the script |
