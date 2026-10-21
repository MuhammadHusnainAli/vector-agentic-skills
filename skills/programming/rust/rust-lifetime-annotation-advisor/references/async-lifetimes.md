# Async Lifetimes

How lifetimes flow through `async fn`, futures, spawned tasks, async traits and async closures. Blocks
marked `rust,ignore` need the `tokio` crate; the rest compile with std only (type-checking async code needs no
runtime).

## Contents

- [An `async fn` returns a future that borrows its arguments](#an-async-fn-returns-a-future-that-borrows-its-arguments)
- [Writing the desugared signature](#writing-the-desugared-signature)
- [Spawned tasks need `'static`](#spawned-tasks-need-static)
- [Borrowing without `'static`: scoped work](#borrowing-without-static-scoped-work)
- [`Send` and what is alive across `.await`](#send-and-what-is-alive-across-await)
- [Boxed futures and `dyn` async](#boxed-futures-and-dyn-async)
- [Async functions in traits](#async-functions-in-traits)
- [Async closures](#async-closures)
- [Checklist](#checklist)

## An `async fn` returns a future that borrows its arguments

```rust
async fn word_count(text: &str) -> usize {
    text.split_whitespace().count()
}
// is roughly
// fn word_count<'a>(text: &'a str) -> impl Future<Output = usize> + 'a
```

The returned future **captures every input lifetime**: `text` stays borrowed until the future completes, not
until the call returns. Consequences:

- You cannot create the future from a temporary and keep it: `let f = word_count(&String::from("a b"));
  f.await` fails with E0716 (temporary dropped while borrowed). Bind the `String` first.
- A future borrowing locals is not `'static`, so it cannot be passed to `tokio::spawn`.
- `&mut self` async methods keep `self` mutably borrowed across every `.await` inside them.

## Writing the desugared signature

Sometimes you need the explicit form: to do work before the first `.await` (synchronously, in the caller),
or to return a future that borrows only *some* inputs.

```rust
use std::future::Future;

struct Client { base: String }

impl Client {
    // Clones what it needs up front; the returned future borrows nothing (`'static`).
    fn fetch(&self, path: &str) -> impl Future<Output = String> + 'static {
        let url = format!("{}/{}", self.base, path);
        async move { url }
    }

    // Borrows `self` for 'a; `path` is copied in, so the caller may drop its string right away.
    fn fetch_with_base<'a>(&'a self, path: &str) -> impl Future<Output = usize> + 'a {
        let path = path.to_owned();
        async move { self.base.len() + path.len() }
    }
}
```

In edition 2024 `-> impl Future` captures all in-scope lifetimes by default; add `+ use<>` (Rust 1.82+) to
promise the future borrows nothing, or `+ use<'a>` to list exactly what it borrows.

## Spawned tasks need `'static`

```rust,ignore
// tokio::spawn<F>(f: F) where F: Future + Send + 'static
async fn handle(state: &AppState) { /* ... */ }

async fn bad(state: AppState) {
    tokio::spawn(handle(&state));          // E0597: `state` does not live long enough
                                           // (argument requires that `state` is borrowed for `'static`)
}

async fn good(state: std::sync::Arc<AppState>) {
    let st = state.clone();
    tokio::spawn(async move { handle(&st).await });   // the task owns an Arc clone
}
```

`'static` here means "owns its data": owned values, `Arc<T>`, channels. Adding `'static` bounds or
`Box::leak` to make references fit is almost always wrong. Fixes in order: move owned data in; share with
`Arc`; restructure so the work happens inside the current future (`join!`, `select!`, `FuturesUnordered`)
where borrowing is allowed.

## Borrowing without `'static`: scoped work

Concurrency *inside* one future can borrow freely, because everything finishes before the future does:

```rust,ignore
async fn enrich(items: &mut [Item], client: &Client) {
    // join_all / FuturesUnordered / tokio::join! poll the futures in place: no 'static needed.
    let lookups = items.iter().map(|it| client.lookup(&it.id));
    let results = futures::future::join_all(lookups).await;
    for (it, r) in items.iter_mut().zip(results) {
        it.extra = r;
    }
}
```

For threads, `std::thread::scope` (1.63) gives the same "borrow, then join before returning" guarantee:

```rust
fn parallel_len(parts: &[String]) -> usize {
    std::thread::scope(|s| {
        let handles: Vec<_> = parts.iter().map(|p| s.spawn(move || p.len())).collect();
        handles.into_iter().map(|h| h.join().unwrap()).sum()
    })
}
```

There is no sound "scoped spawn" for async tasks in Tokio; `async-scoped`-style crates rely on blocking or
unsafe guarantees. Prefer in-place concurrency or owned data.

## `Send` and what is alive across `.await`

A multi-threaded runtime may resume a task on another thread at each `.await`, so everything alive across an
`.await` must be `Send`. The usual culprits are not lifetimes but `!Send` guards and pointers:

```rust
use std::sync::Mutex;

async fn tick() {}

async fn record(m: &Mutex<Vec<u32>>, v: u32) {
    {
        let mut g = m.lock().unwrap();   // std MutexGuard is !Send
        g.push(v);
    }                                    // dropped before the await
    tick().await;
}

fn assert_send<T: Send>(_: T) {}
fn check(m: &'static Mutex<Vec<u32>>) { assert_send(record(m, 1)); }
```

Holding `g` across `tick().await` makes the future `!Send` ("future cannot be sent between threads safely").
`Rc`, `RefCell` borrows and `&T` where `T: !Sync` cause the same error. Use `Arc`, scope guards, or
`tokio::sync::Mutex` when a lock really must be held across an `.await`.

## Boxed futures and `dyn` async

When you need a trait object or recursion, box the future and spell out its lifetime:

```rust
use std::future::Future;
use std::pin::Pin;

type BoxFuture<'a, T> = Pin<Box<dyn Future<Output = T> + Send + 'a>>; // same shape as futures::future::BoxFuture

fn depth<'a>(name: &'a str, n: u32) -> BoxFuture<'a, usize> {
    Box::pin(async move {
        if n == 0 { name.len() } else { depth(name, n - 1).await + 1 } // recursion needs the box
    })
}
```

Without `+ 'a`, `Box<dyn Future>` means `+ 'static` and the future could not borrow `name`.

## Async functions in traits

`async fn` and `-> impl Trait` in traits are stable since Rust 1.75:

```rust
trait Store {
    async fn get(&self, key: &str) -> Option<String>;
}

struct Mem(std::collections::HashMap<String, String>);

impl Store for Mem {
    async fn get(&self, key: &str) -> Option<String> {
        self.0.get(key).cloned()
    }
}
```

Lifetime and `Send` notes:

- The returned future captures `&self` and `key` (all input lifetimes), like a free `async fn`.
- Callers cannot require the future to be `Send` (needed by `tokio::spawn`) with plain `async fn` in a public
  trait; the `async_fn_in_trait` lint warns about this. Options: declare `fn get(&self, key: &str) -> impl
  Future<Output = Option<String>> + Send;` in the trait, or generate a `Send` variant with
  `#[trait_variant::make(SendStore: Send)]` (the `trait-variant` crate).
- Traits with `async fn` are not dyn-compatible. For `dyn Store`, return `BoxFuture<'_, T>` explicitly or use
  the `async-trait` crate (boxes every call).

## Async closures

Rust 1.85 stabilised async closures (`async |x| { .. }`) and the `AsyncFn`, `AsyncFnMut`, `AsyncFnOnce`
traits. Their main lifetime benefit: the returned future may borrow from the closure's captures and from its
arguments, which `F: Fn(&str) -> Fut` with a separate `Fut` type parameter cannot express.

```rust
async fn for_each_line<F>(text: &str, f: F)
where
    F: AsyncFn(&str),
{
    for line in text.lines() {
        f(line).await;            // the future borrows `line`: fine with AsyncFn
    }
}
```

On older compilers the workaround is `F: Fn(String) -> Fut` (pass owned data) or boxing:
`F: for<'a> Fn(&'a str) -> BoxFuture<'a, ()>`.

## Checklist

| Situation | Do |
|-----------|----|
| `tokio::spawn` / `thread::spawn` with borrowed data | move owned data or `Arc` clones in; never `'static` bounds on references |
| Future must not borrow an argument | clone/own it before an `async move` block; `+ use<..>` in edition 2024 |
| Borrowing concurrency inside one request | `join!`, `join_all`, `FuturesUnordered`, `select!` |
| "future cannot be sent between threads safely" | find the `!Send` value alive across `.await`; scope or replace it |
| Recursive or `dyn` async | `Pin<Box<dyn Future<Output = T> + Send + 'a>>` |
| Async trait used with `tokio::spawn` | `-> impl Future<..> + Send` in the trait or `trait_variant` |
| Callback that receives a reference and awaits | `AsyncFn(&T)` (1.85+) or owned arguments |
