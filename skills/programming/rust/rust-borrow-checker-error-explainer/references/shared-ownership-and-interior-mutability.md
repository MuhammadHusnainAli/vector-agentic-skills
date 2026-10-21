# Shared Ownership and Interior Mutability

Tiers 3 and 4 of the fix ladder: own the data, or share it. These are correct, idiomatic tools when the design
really has several owners or mutation through shared references. Used only to silence the checker, they turn
compile errors into allocations, runtime panics and deadlocks.

## Contents

- [When cloning is the right fix](#when-cloning-is-the-right-fix)
- [`Cow` for borrow-or-own](#cow-for-borrow-or-own)
- [`Rc` and `Arc`](#rc-and-arc)
- [Getting a value back out of `Rc`/`Arc`](#getting-a-value-back-out-of-rcarc)
- [Clone-on-write with `make_mut`](#clone-on-write-with-make_mut)
- [Choosing an interior mutability type](#choosing-an-interior-mutability-type)
- [`Cell`](#cell)
- [`RefCell` and its runtime panics](#refcell-and-its-runtime-panics)
- [`Mutex`, `RwLock` and poisoning](#mutex-rwlock-and-poisoning)
- [Atomics and `OnceLock`/`LazyLock`](#atomics-and-oncelocklazylock)
- [Smells](#smells)

## When cloning is the right fix

| Clone is fine | Clone is a smell |
|---------------|------------------|
| Small values (`String` ids, config fields) cloned once per request or task | Cloning a large `Vec`/`HashMap` each loop iteration |
| `Arc`/`Rc`/`Sender`/`Bytes` handles (a refcount bump, no data copy) | `.clone()` added only because the checker complained, without asking who should own the data |
| The callee genuinely needs its own copy (stores it, sends it to a thread) | Cloning to work around a borrow that a reorder would fix |
| Prototyping; you will measure later | In a hot path a profiler already flagged |

Before cloning ask: can the callee take `&T`? Can I reorder? Can I move instead (it is the last use)?

## `Cow` for borrow-or-own

`std::borrow::Cow<'a, B>` holds either `&'a B` or the owned form. Use it for functions that usually return
their input unchanged but sometimes must allocate.

```rust
use std::borrow::Cow;

fn normalize_ws(s: &str) -> Cow<'_, str> {
    if s.contains('\t') {
        Cow::Owned(s.replace('\t', "    "))
    } else {
        Cow::Borrowed(s)
    }
}

fn main() {
    let a = normalize_ws("plain");
    let b = normalize_ws("a\tb");
    assert!(matches!(a, Cow::Borrowed(_)));
    assert_eq!(b, "a    b");
}
```

## `Rc` and `Arc`

`Rc<T>` (single thread) and `Arc<T>` (thread-safe, atomic count) give several owners of one value. They hand
out **shared** references only, so mutation needs one of the cells below or `make_mut`/`get_mut`.

```rust
use std::sync::Arc;
use std::thread;

struct Config { region: String, retries: u32 }

fn main() {
    let cfg = Arc::new(Config { region: "eu-west-1".into(), retries: 3 });
    let handles: Vec<_> = (0..4)
        .map(|i| {
            let cfg = Arc::clone(&cfg); // clone the handle, not the Config
            thread::spawn(move || format!("worker {i} in {} ({} retries)", cfg.region, cfg.retries))
        })
        .collect();
    for h in handles {
        println!("{}", h.join().unwrap());
    }
}
```

Write `Arc::clone(&x)` rather than `x.clone()` when you want readers to see that only a handle is copied.
Cycles of `Rc`/`Arc` leak; break them with `Weak` (`Rc::downgrade`) for parent or back pointers.

## Getting a value back out of `Rc`/`Arc`

| API | Since | Behaviour |
|-----|-------|-----------|
| `Rc::try_unwrap(rc)` / `Arc::try_unwrap` | 1.4 | `Ok(T)` if this is the only strong handle, else gives the `Rc` back |
| `Arc::into_inner(arc)` | 1.70 | `Some(T)` if last handle; race-free when several threads call it |
| `Rc::into_inner(rc)` | 1.70 | same for `Rc` |
| `Rc::unwrap_or_clone(rc)` / `Arc::unwrap_or_clone` | 1.76 | move out if unique, otherwise clone `T` |
| `Rc::get_mut(&mut rc)` | 1.4 | `Some(&mut T)` if unique |

These fix E0507 "cannot move out of an `Rc`" when you really hold the last handle.

## Clone-on-write with `make_mut`

```rust
use std::rc::Rc;

fn main() {
    let mut a = Rc::new(vec![1, 2, 3]);
    let b = Rc::clone(&a);
    Rc::make_mut(&mut a).push(4);       // `a` is shared, so its Vec is cloned first
    assert_eq!(*a, vec![1, 2, 3, 4]);
    assert_eq!(*b, vec![1, 2, 3]);      // `b` still sees the original
}
```

Good for persistent/snapshot data (configs, immutable-by-default state). `Arc::make_mut` is the threaded
version. Requires `T: Clone`.

## Choosing an interior mutability type

| Need | Single thread | Across threads |
|------|---------------|----------------|
| Replace a `Copy` value | `Cell<T>` | atomics (`AtomicU64`, `AtomicBool`, ...) |
| Mutate a non-`Copy` value through `&` | `RefCell<T>` | `Mutex<T>` |
| Many readers, rare writers | `RefCell<T>` | `RwLock<T>` |
| Initialise once, read forever | `OnceCell<T>` (1.70) / `LazyCell` (1.80) | `OnceLock<T>` (1.70) / `LazyLock` (1.80) |
| Shared + mutable + owned by several | `Rc<RefCell<T>>` | `Arc<Mutex<T>>` / `Arc<RwLock<T>>` |
| Held across `.await` in async code | — | `tokio::sync::Mutex` (only then; std `Mutex` otherwise) |

## `Cell`

No references into the value, so no runtime check and no panic: `get` copies out, `set`/`replace`/`take`
swap the whole value.

```rust
use std::cell::Cell;

struct Counter { hits: Cell<u64> }

impl Counter {
    fn hit(&self) { self.hits.set(self.hits.get() + 1); } // mutation through &self
}

fn main() {
    let c = Counter { hits: Cell::new(0) };
    c.hit();
    c.hit();
    assert_eq!(c.hits.get(), 2);
}
```

## `RefCell` and its runtime panics

`RefCell` moves the borrow rules to run time. `borrow()` returns a `Ref`, `borrow_mut()` a `RefMut`; while a
`RefMut` lives, any other borrow panics:

- `already borrowed: BorrowMutError` — `borrow_mut()` while another `Ref`/`RefMut` is alive
- `already mutably borrowed: BorrowError` — `borrow()` while a `RefMut` is alive

The usual cause is a guard kept alive across a call that re-enters the same cell (callbacks, observers,
recursive methods).

```rust
use std::cell::RefCell;

struct Registry { names: RefCell<Vec<String>> }

impl Registry {
    fn add(&self, n: &str) { self.names.borrow_mut().push(n.to_owned()); }

    fn add_all_upper(&self) {
        // for n in self.names.borrow().iter() { self.add(&n.to_uppercase()); } // panics: BorrowMutError
        let upper: Vec<String> = self.names.borrow().iter().map(|n| n.to_uppercase()).collect(); // Ref dropped here
        for n in upper {
            self.add(&n);
        }
    }

    fn try_add(&self, n: &str) -> bool {
        match self.names.try_borrow_mut() {     // no panic: report or defer instead
            Ok(mut v) => { v.push(n.to_owned()); true }
            Err(_) => false,
        }
    }
}

fn main() {
    let r = Registry { names: RefCell::new(vec!["a".into()]) };
    r.add_all_upper();
    assert!(r.try_add("b"));
    assert_eq!(r.names.borrow().len(), 3);
}
```

Rules that keep `RefCell` panic-free:

1. Never store a `Ref`/`RefMut` in a variable that lives across a call into code you do not control.
2. Take what you need and let the guard drop at the `;`: `let n = cell.borrow().len();`.
3. Snapshot (clone the `Vec` of `Rc` listeners) before invoking callbacks.
4. Use `try_borrow_mut` where re-entrancy is possible and queue the change.

`runtime_panic` reports these panics as BCK024.

## `Mutex`, `RwLock` and poisoning

```rust
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;

fn main() {
    let totals = Arc::new(Mutex::new(Vec::new()));
    let hs: Vec<_> = (0..4)
        .map(|i| {
            let totals = Arc::clone(&totals);
            thread::spawn(move || totals.lock().unwrap().push(i * 10))
        })
        .collect();
    for h in hs {
        h.join().unwrap();
    }
    // Recover from poisoning deliberately instead of unwrapping:
    let v = totals.lock().unwrap_or_else(PoisonError::into_inner);
    assert_eq!(v.len(), 4);
}
```

- If a thread panics while holding the guard, the mutex becomes **poisoned**: later `lock()` returns
  `Err(PoisonError)` and `lock().unwrap()` panics with `PoisonError { .. }`. The real bug is the first panic;
  `runtime_panic` links the two (BCK025).
- Recover with `unwrap_or_else(PoisonError::into_inner)` when the data is still valid; reset with
  `Mutex::clear_poison` (1.77).
- Keep critical sections short; never call user callbacks or block on I/O while holding a lock.
- Lock ordering: always acquire several locks in the same global order to avoid deadlocks.
- `std::sync::MutexGuard` is `!Send`: keep it out of `.await` points (BCK026). `parking_lot` mutexes do not
  poison and are smaller, but the same guard rules apply.

## Atomics and `OnceLock`/`LazyLock`

```rust
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::LazyLock; // 1.80
use std::collections::HashMap;

static REQUESTS: AtomicU64 = AtomicU64::new(0);
static LIMITS: LazyLock<HashMap<&'static str, u32>> =
    LazyLock::new(|| HashMap::from([("free", 10), ("pro", 1000)]));

fn handle(plan: &str) -> u32 {
    REQUESTS.fetch_add(1, Ordering::Relaxed); // counter: Relaxed is enough
    LIMITS.get(plan).copied().unwrap_or(0)
}

fn main() {
    assert_eq!(handle("pro"), 1000);
    assert_eq!(REQUESTS.load(Ordering::Relaxed), 1);
}
```

Use `Relaxed` for independent counters; `Acquire`/`Release` pairs when an atomic flag publishes other data;
`SeqCst` when in doubt. Replace `static mut` globals with these types; `static mut` references are denied
in edition 2024.

## Smells

| Smell | Better |
|-------|--------|
| `Rc<RefCell<T>>` everywhere in a single-owner program | plain ownership + `&mut` passed down; split structs |
| `Arc<Mutex<T>>` around data that is read-only after start-up | `Arc<T>` (or `LazyLock`/`OnceLock`) |
| Lock held while calling another component | copy out, unlock, then call |
| `.lock().unwrap()` everywhere with no plan for poisoning | decide: propagate as an error, recover with `into_inner`, or use `parking_lot` |
| `RefCell` borrow held across a callback | snapshot then call (BCK024) |
| `clone()` of a large collection inside a loop | borrow, iterate by reference, or restructure |
