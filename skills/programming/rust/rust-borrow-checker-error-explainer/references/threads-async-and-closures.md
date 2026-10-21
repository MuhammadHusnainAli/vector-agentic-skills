# Threads, Async and Closures

Borrow errors around `thread::spawn`, `tokio::spawn` and closures all come from one rule: work that may outlive
the current function must **own** everything it touches (`'static`), and futures sent to a multi-threaded
runtime must be `Send` at every `.await`.

## Contents

- [Why spawn needs `'static`](#why-spawn-needs-static)
- [E0373: add `move`, then own the data](#e0373-add-move-then-own-the-data)
- [E0597 / E0521: `move` is not enough when you move a reference](#e0597--e0521-move-is-not-enough-when-you-move-a-reference)
- [Scoped threads borrow safely](#scoped-threads-borrow-safely)
- [Sharing results back](#sharing-results-back)
- [Tokio: `spawn`, `Send` and guards across `.await`](#tokio-spawn-send-and-guards-across-await)
- [Closures: `Fn`, `FnMut`, `FnOnce` and captures](#closures-fn-fnmut-fnonce-and-captures)
- [Returning closures](#returning-closures)
- [Quick reference](#quick-reference)

## Why spawn needs `'static`

```rust,ignore
// std
pub fn spawn<F, T>(f: F) -> JoinHandle<T>
where F: FnOnce() -> T + Send + 'static, T: Send + 'static;
// tokio
pub fn spawn<F>(future: F) -> JoinHandle<F::Output>
where F: Future + Send + 'static, F::Output: Send + 'static;
```

The spawned thread/task may still run after the caller returns, so it cannot hold references to the caller's
locals. `'static` here means "contains no non-`'static` borrows", not "lives forever": an owned `String`,
`Vec`, `Arc<T>` or `Sender` is `'static`.

## E0373: add `move`, then own the data

Without `move`, a closure captures variables by reference. The compiler's help suggests `move`, which is
correct when the captured variables are owned values:

```rust
use std::thread;

fn report(lines: Vec<String>) -> usize {
    // let h = thread::spawn(|| lines.len());   // E0373: borrows `lines`
    let h = thread::spawn(move || lines.len()); // the Vec is moved into the thread
    h.join().unwrap()
}
```

If the caller still needs the value afterwards, clone it (or an `Arc` around it) **before** the closure and
move the clone in:

```rust
use std::sync::Arc;
use std::thread;

fn fan_out(data: Arc<Vec<u64>>) -> u64 {
    let workers: Vec<_> = (0..4)
        .map(|i| {
            let data = Arc::clone(&data);           // shadowed clone, moved below
            thread::spawn(move || data.iter().skip(i).step_by(4).sum::<u64>())
        })
        .collect();
    let total = workers.into_iter().map(|h| h.join().unwrap()).sum();
    println!("still usable here: {} items", data.len());
    total
}
```

## E0597 / E0521: `move` is not enough when you move a reference

If what you move is itself a reference (`&state`, a `&self` field, a `&str` parameter), the closure is still
borrowing, and the error becomes E0597 "`state` does not live long enough ... argument requires that `state`
is borrowed for `'static`", or E0521 "borrowed data escapes outside of method".

```rust
use std::sync::Arc;
use std::thread;

struct Service { name: String }

impl Service {
    // fn start(&self) { thread::spawn(move || println!("{}", self.name)); }   // E0521: `self` is &Service

    fn start(self: &Arc<Self>) -> thread::JoinHandle<()> {
        let me = Arc::clone(self);                 // own a handle
        thread::spawn(move || println!("{} started", me.name))
    }

    fn start_with_name(&self) -> thread::JoinHandle<()> {
        let name = self.name.clone();              // or own just the field you need
        thread::spawn(move || println!("{name} started"))
    }
}
```

Fixes, best first: move owned data (clone the small field), take `Arc<Self>`/`Arc<T>` parameters, or use a
scoped thread if the work finishes before the function returns.

## Scoped threads borrow safely

`std::thread::scope` (1.63) guarantees every thread spawned in the scope is joined before `scope` returns, so
the threads may borrow locals, including mutably and disjointly.

```rust
use std::thread;

fn parallel_sum_and_scale(values: &mut [f64], factor: f64) -> f64 {
    let (left, right) = values.split_at_mut(values.len() / 2);
    thread::scope(|s| {
        s.spawn(|| left.iter_mut().for_each(|x| *x *= factor));   // &mut left
        s.spawn(|| right.iter_mut().for_each(|x| *x *= factor));  // &mut right, disjoint
    });                                                            // both joined here
    values.iter().sum()
}
```

Use `move` inside the scope only to move copies of small locals (`s.spawn(move || ...)` copies `&` slices,
which is still borrowing the outer data). Rayon's `par_iter` and `rayon::scope` follow the same model.

## Sharing results back

| Need | Tool |
|------|------|
| One result per thread | return it from the closure and `join()` |
| Stream results while running | `std::sync::mpsc::channel` / `tokio::sync::mpsc` (clone the `Sender` per worker) |
| Accumulate into one value | `Arc<Mutex<T>>`, or atomics for counters |
| Borrow inputs, return outputs, all before the function ends | `thread::scope` with `ScopedJoinHandle::join` |

```rust
use std::sync::mpsc;
use std::thread;

fn crawl(urls: Vec<String>) -> Vec<(String, usize)> {
    let (tx, rx) = mpsc::channel();
    for url in urls {
        let tx = tx.clone();
        thread::spawn(move || {
            let len = url.len(); // stand-in for a fetch
            tx.send((url, len)).ok();
        });
    }
    drop(tx); // close the original sender so `rx` ends when workers finish
    rx.into_iter().collect()
}
```

## Tokio: `spawn`, `Send` and guards across `.await`

Same `'static` rule: `tokio::spawn(async move { ... })` with owned or `Arc` captures. The extra rule is
`Send`: on the multi-threaded runtime a task may move between threads at each `.await`, so every value alive
across an `.await` must be `Send`.

```rust,ignore
use std::sync::{Arc, Mutex};

async fn record(state: Arc<Mutex<Vec<u32>>>, v: u32) {
    // let mut g = state.lock().unwrap();
    // g.push(v);
    // flush().await;            // error: future cannot be sent between threads safely
    //                           // (`MutexGuard` is !Send and is still alive here)
    {
        let mut g = state.lock().unwrap();
        g.push(v);
    }                            // guard dropped before the await
    flush().await;
}

async fn flush() {}
```

| Value alive at `.await` | Problem | Fix |
|-------------------------|---------|-----|
| `std::sync::MutexGuard` | `!Send` | scope it in a block or `drop(guard)` before `.await` |
| `Rc<T>`, `RefCell` `Ref`/`RefMut` | `!Send` | `Arc`, or keep them out of the async fn's live state |
| A guard that truly must be held across `.await` | std guard is wrong here | `tokio::sync::Mutex` (async `lock().await`) |
| A `!Send` future you cannot change | multi-threaded runtime | `tokio::task::spawn_local` on a `LocalSet`, or `current_thread` runtime |

Older compilers did not see an explicit `drop(guard)` when checking `Send`; a block scope works on every
version, so prefer it. `parse_diagnostics` reports these as BCK026 (`not-send`).

## Closures: `Fn`, `FnMut`, `FnOnce` and captures

A closure captures each variable in the least powerful way its body needs:

| Body does | Captured as | Closure implements |
|-----------|-------------|--------------------|
| reads `x` | `&x` | `Fn` (+ `FnMut` + `FnOnce`) |
| mutates `x` | `&mut x` | `FnMut` (+ `FnOnce`) |
| moves `x` out (drops it, returns it, passes by value) | `x` by value | `FnOnce` only |
| `move` keyword | everything by value (copies for `Copy` types) | depends on the body as above |

Edition 2021 captures disjoint fields: `|| self.count += 1` captures `self.count`, not all of `self`.

Common errors:

```rust
fn counters() {
    let mut n = 0;
    let mut inc = || n += 1;      // FnMut: holds &mut n while `inc` is alive
    inc();
    inc();
    // println!("{n}"); inc();    // E0502: `n` read while `inc` (and its &mut n) is still used
    println!("{n}");              // fine: `inc` is not used after this point
}

fn call_twice<F: FnMut()>(mut f: F) { f(); f(); }

fn names() -> Vec<String> {
    let mut out = Vec::new();
    call_twice(|| out.push("x".to_string())); // FnMut is enough; `out` is usable again afterwards
    out
}
```

"cannot move out of `x`, a captured variable in an `FnMut` closure" (E0507) means a closure that may be
called again tries to give away a captured value: clone inside the closure, or use `Option::take`.

## Returning closures

```rust
fn make_prefixer(prefix: String) -> impl Fn(&str) -> String {
    move |s| format!("{prefix}{s}")            // owns `prefix`
}

fn make_matcher<'a>(words: &'a [&'a str]) -> impl Fn(&str) -> bool + 'a {
    move |s| words.iter().any(|w| *w == s)     // borrows `words` for 'a: lifetime in the return type
}
```

Returning a closure that borrows a local fails with E0373/E0597; move the data in, or tie the closure's
lifetime to an input as in `make_matcher`. In edition 2024, `impl Trait` in return position captures all
in-scope lifetimes automatically; use `+ use<'a>` (1.82) to state precisely which ones.

## Quick reference

| Error | Context | Fix |
|-------|---------|-----|
| E0373 | `thread::spawn(|| ..)` / `tokio::spawn(async { .. })` borrowing locals | `move` + owned data |
| E0597 "borrowed for `'static`" | moved a `&local` into a spawned task | own the data, `Arc`, or `thread::scope` |
| E0521 | `&self`/`&T` parameter used in a spawned task | clone the field or take `Arc<Self>` |
| future cannot be sent | `MutexGuard`/`Rc` alive at `.await` | scope the guard; `Arc`; `tokio::sync::Mutex` if needed |
| E0502 with a closure | `FnMut` closure still alive while the variable is used | finish using the closure first; pass as argument |
| E0507 in `FnMut` | closure gives away a captured value | clone inside, `Option::take`, or make it `FnOnce` |
