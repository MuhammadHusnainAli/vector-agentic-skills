# Send, 'static and Other Compile Errors in Async Rust

The errors that block every new Tokio codebase, how to read them, and the fix for each. The compiler output
below is abridged; the key lines are verbatim.

## Contents

- [Why spawn needs Send + 'static](#why-spawn-needs-send--static)
- [Reading "future cannot be sent between threads safely"](#reading-future-cannot-be-sent-between-threads-safely)
- [MutexGuard held across await](#mutexguard-held-across-await)
- [Rc and RefCell in async code](#rc-and-refcell-in-async-code)
- [Other !Send values: dyn Error, raw pointers, ThreadRng](#other-send-values-dyn-error-raw-pointers-threadrng)
- [E0373: async block may outlive the current function](#e0373-async-block-may-outlive-the-current-function)
- [E0597 and borrowed for 'static](#e0597-and-borrowed-for-static)
- [axum: Handler trait is not satisfied](#axum-handler-trait-is-not-satisfied)
- [Router state type mismatches](#router-state-type-mismatches)
- [async fn in traits](#async-fn-in-traits)
- [Recursion and boxing](#recursion-and-boxing)
- [Asserting Send in tests](#asserting-send-in-tests)
- [Runtime panics that look like type errors](#runtime-panics-that-look-like-type-errors)

## Why spawn needs Send + 'static

```rust,ignore
pub fn spawn<F>(future: F) -> JoinHandle<F::Output>
where
    F: Future + Send + 'static,
    F::Output: Send + 'static;
```

- **`'static`**: the task may outlive the function that spawned it, so it cannot borrow the caller's locals.
  Own the data (`move`, clone, `Arc`).
- **`Send`**: on the multi-thread runtime the task can resume on another worker after any `.await`. Every
  value **alive across an `.await`** is stored in the future's state machine, so all of them must be `Send`.
  Values created and dropped between two awaits do not matter.

## Reading "future cannot be sent between threads safely"

```text
error: future cannot be sent between threads safely
   --> src/main.rs:20:18
    |
20  |     tokio::spawn(update(state));
    |                  ^^^^^^^^^^^^^ future returned by `update` is not `Send`
    |
    = help: within `impl Future<Output = ()>`, the trait `Send` is not implemented for `std::sync::MutexGuard<'_, Vec<u64>>`
note: future is not `Send` as this value is used across an await
   --> src/main.rs:12:28
    |
11  |     let mut guard = state.lock().unwrap();
    |         --------- has type `std::sync::MutexGuard<'_, Vec<u64>>` which is not `Send`
12  |     tick().await;
    |            ^^^^^ await occurs here, with `mut guard` maybe used later
note: required by a bound in `tokio::spawn`
```

Read it bottom-up: the `note` names **which value** (`guard`), **its type** (`MutexGuard`), and **which
await** it crosses. The fix is always one of:
1. End the value's lifetime before the `.await` (inner block, `drop(x)`, or extract a clone).
2. Replace it with a `Send` alternative (`Arc` for `Rc`, `tokio::sync::Mutex` guard, `Box<dyn Error + Send +
   Sync>`).
3. Run the future on a `LocalSet` (`spawn_local`) when it truly must be `!Send`.

Note that `drop(guard)` before the await works on current compilers; older compilers sometimes still counted
the variable as live. If `drop` does not help, use an inner block.

## MutexGuard held across await

```rust
use std::sync::{Arc, Mutex};

// Does not compile when spawned: guard lives across .await
async fn bad(state: Arc<Mutex<Vec<u64>>>) {
    let mut v = state.lock().unwrap();
    v.push(1);
    tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    v.push(2);
}

// Fix 1: scope the guard
async fn good_scoped(state: Arc<Mutex<Vec<u64>>>) {
    {
        let mut v = state.lock().unwrap();
        v.push(1);
    }
    tokio::time::sleep(std::time::Duration::from_millis(10)).await;
    state.lock().unwrap().push(2);
}

// Fix 2: move the locking into a sync helper
fn push(state: &Mutex<Vec<u64>>, x: u64) {
    state.lock().unwrap().push(x);
}

// Fix 3: the guard really must span the await -> tokio::sync::Mutex
async fn good_async_mutex(state: Arc<tokio::sync::Mutex<Vec<u64>>>) {
    let mut v = state.lock().await;
    v.push(1);
    tokio::time::sleep(std::time::Duration::from_millis(10)).await; // other lockers wait, by design
    v.push(2);
}
```

Same for `RwLockReadGuard`/`RwLockWriteGuard`, `parking_lot` guards, `dashmap::mapref::one::Ref`, and
`tokio::sync::watch::Ref` (from `borrow()`). Clippy has lints for this: `clippy::await_holding_lock` and
`clippy::await_holding_refcell_ref` (both warn by default in the `suspicious` group).

If it compiles because you are on `current_thread` or a `LocalSet`, it is still wrong: a std mutex held while
the task is suspended blocks any other task that tries to lock it, and on a single thread that is a deadlock.

## Rc and RefCell in async code

```text
error: future cannot be sent between threads safely
    = help: within `impl Future<Output = ()>`, the trait `Send` is not implemented for `Rc<RefCell<Vec<String>>>`
note: future is not `Send` as this value is used across an await
```

Also seen as `` `Rc<...>` cannot be sent between threads safely `` when an `Rc` is moved into a spawned
block.

```rust
use std::sync::{Arc, Mutex};

async fn collect(urls: Vec<String>) -> Vec<String> {
    let seen = Arc::new(Mutex::new(Vec::new())); // was Rc<RefCell<Vec<_>>>
    let mut set = tokio::task::JoinSet::new();
    for url in urls {
        let seen = Arc::clone(&seen);
        set.spawn(async move {
            tokio::task::yield_now().await;
            seen.lock().unwrap().push(url);
        });
    }
    while set.join_next().await.is_some() {}
    let out = seen.lock().unwrap().clone();
    out
}
```

`Rc` is fine in sync helper functions called from async code as long as it does not live across an
`.await`. `Cell`/`RefCell` are `Send` (if the content is) but not `Sync`, so `&RefCell` across an await or an
`Arc<RefCell<_>>` fails similarly; use `Mutex` or atomics.

## Other !Send values: dyn Error, raw pointers, ThreadRng

| Value alive across `.await` | Fix |
|-----------------------------|-----|
| `Box<dyn std::error::Error>` | `Box<dyn Error + Send + Sync>` or `anyhow::Error` |
| `rand::rngs::ThreadRng` (`rand::thread_rng()`/`rand::rng()`) | generate the number before the await, or keep a `Send` RNG such as `rand::rngs::StdRng` (seeded once) |
| `*const T` / `*mut T` | wrap in a type with a justified `unsafe impl Send`, or keep it out of async code |
| `std::sync::MutexGuard`, `RwLock*Guard`, `Ref`/`RefMut` | scope it, see above |
| `tracing::span::Entered` (`span.enter()`) | never `enter()` across await; use `.instrument(span)` or `#[instrument]` |
| `&T` where `T: !Sync` | `T: Sync` (Mutex) or own a clone |
| non-Send SDK client | `LocalSet` + `spawn_local`, or a dedicated thread/actor that owns it |

```rust
use tracing::Instrument;

async fn traced(id: u64) {
    let span = tracing::info_span!("job", id);
    async move {
        tokio::task::yield_now().await;
        tracing::info!("inside span across awaits");
    }
    .instrument(span) // correct; `let _e = span.enter();` across .await is wrong
    .await;
}
```

## E0373: async block may outlive the current function

```text
error[E0373]: async block may outlive the current function, but it borrows `name`, which is owned by the current function
  --> src/main.rs:6:18
   |
6  |     tokio::spawn(async {
   |                  ^^^^^ may outlive borrowed value `name`
7  |         println!("{name}");
   |                    ---- `name` is borrowed here
help: to force the async block to take ownership of `name` (and any other referenced variables), use the `move` keyword
```

```rust,ignore
async fn start(name: String, state: std::sync::Arc<AppState>) {
    let task_state = state.clone();            // clone what the task needs
    tokio::spawn(async move {                   // move ownership into the task
        task_state.log(&name).await;
    });
    state.log("parent still has its Arc").await;
}
```

Pattern for loops: clone inside the loop, right before the `async move`.

## E0597 and borrowed for 'static

```text
error[E0597]: `config` does not live long enough
  ...
  argument requires that `config` is borrowed for `'static`
```

Triggered by passing `&local` into `tokio::spawn`, `JoinSet::spawn`, `std::thread::spawn`, or storing a
reference in a `'static` struct. Fixes:
- Put shared data in an `Arc` and clone the `Arc`.
- For read-only config that lives for the whole program, `Box::leak(Box::new(cfg))` yields `&'static Config`
  (acceptable once at startup, never per request).
- For structured fan-out that genuinely borrows, do not spawn: run the futures concurrently on the current task
  with `futures::future::join_all` or `FuturesUnordered`, which have no `'static` bound.

```rust
use futures::{StreamExt, stream::FuturesUnordered};

async fn check_all(urls: &[String], http: &reqwest::Client) -> usize {
    let mut pending: FuturesUnordered<_> = urls.iter().map(|u| http.head(u).send()).collect();
    let mut ok = 0;
    while let Some(res) = pending.next().await {
        if res.is_ok_and(|r| r.status().is_success()) {
            ok += 1;
        }
    }
    ok
}
```

Concurrent but not parallel: everything runs inside the calling task. Bound it (`buffer_unordered(n)`) for
large inputs.

## axum: Handler trait is not satisfied

```text
error[E0277]: the trait bound `fn(Json<NewOrder>, State<Arc<AppState>>) -> impl Future<Output = ...> {create}: Handler<_, _>` is not satisfied
```

The message never says why. Causes, in order of frequency:
1. A body extractor (`Json`, `Form`, `String`, `Bytes`, `Request`) is not the **last** argument.
2. The handler's future is not `Send` (a guard/`Rc` across an await inside it).
3. An argument does not implement `FromRequestParts`/`FromRequest` (a plain `u64` instead of `Path<u64>`, a
   custom type without an extractor impl).
4. The return type does not implement `IntoResponse` (e.g. `Result<T, anyhow::Error>`: implement
   `IntoResponse` for your own error type).
5. `State<T>` where `T` differs from the router's state type (and no `FromRef`).
6. More than 16 arguments.

Add `#[axum::debug_handler]` (feature `macros`) above the handler: it produces a targeted error such as
"`Json<_>` consumes the request body and thus must be the last argument to the handler function" or "future
cannot be sent between threads safely". Remove it afterwards or keep it; it has no runtime cost.

## Router state type mismatches

| Error | Cause | Fix |
|-------|-------|-----|
| `expected Router, found Router<Arc<AppState>>` at `axum::serve` | `with_state` not called | `.with_state(state)` last |
| `the trait bound ... Handler<_, Arc<AppState>>` for a sub-router | nested router has a different state type | give both the same `S`, or `with_state` on the nested router first |
| `FromRef<AppState>` not implemented for `PgPool` | handler extracts a substate | `#[derive(FromRef)]` on the state struct (needs `Clone`) |

## async fn in traits

Stable since Rust 1.75:

```rust,ignore
pub trait OrderRepo {
    async fn find(&self, id: i64) -> anyhow::Result<Option<Order>>;
}
```

Limitations:
- **Not dyn-compatible:** `Box<dyn OrderRepo>` / `Arc<dyn OrderRepo>` does not work. Use generics
  (`AppState<R: OrderRepo>`), an enum of implementations, or the `async_trait` crate (boxes every future), or
  write the method as returning `Pin<Box<dyn Future<Output = _> + Send + '_>>` yourself.
- **No `Send` guarantee for callers:** generic code that spawns `repo.find(1)` cannot prove the future is
  `Send`. rustc warns (`async_fn_in_trait` lint) on public traits. Declare the bound explicitly:

```rust,ignore
use std::future::Future;

pub trait OrderRepo: Send + Sync + 'static {
    fn find(&self, id: i64) -> impl Future<Output = anyhow::Result<Option<Order>>> + Send;
}

pub struct PgRepo { pool: sqlx::PgPool }

impl OrderRepo for PgRepo {
    async fn find(&self, id: i64) -> anyhow::Result<Option<Order>> { // async fn satisfies the impl Future signature
        Ok(sqlx::query_as::<_, Order>("SELECT id, sku, qty FROM orders WHERE id = $1")
            .bind(id)
            .fetch_optional(&self.pool)
            .await?)
    }
}
```

The `trait-variant` crate (`#[trait_variant::make(SendOrderRepo: Send)]`) generates a `Send` variant from an
`async fn` trait. For `Arc<dyn Repo>` in axum state, `async_trait` is still the practical choice.

## Recursion and boxing

```text
error[E0733]: recursion in an async fn requires boxing
```

```rust
use std::{future::Future, pin::Pin};

fn walk(depth: u32) -> Pin<Box<dyn Future<Output = u32> + Send>> {
    Box::pin(async move {
        if depth == 0 { 0 } else { 1 + walk(depth - 1).await }
    })
}
```

Since Rust 1.77 an `async fn` may recurse when the recursive call is boxed: `Box::pin(walk(depth - 1)).await`.

## Asserting Send in tests

Catch `!Send` regressions where they are introduced, not three layers up at `tokio::spawn`:

```rust,ignore
#[allow(dead_code)]
fn assert_send<T: Send>(_: &T) {}

#[test]
fn handler_futures_are_send() {
    let state = test_state();
    let fut = load_order_for_test(state, 1); // do not await; just build the future
    assert_send(&fut);
}
```

## Runtime panics that look like type errors

| Panic message | Cause | Fix |
|---------------|-------|-----|
| `Cannot start a runtime from within a runtime. This happens because a function (like block_on) attempted to block the current thread while the thread is being used to drive asynchronous tasks.` | `Runtime::new().block_on`, `Handle::block_on`, `futures::executor::block_on` of tokio I/O inside async code | `.await`; or call from `spawn_blocking` |
| `Cannot drop a runtime in a context where blocking is not allowed` | `reqwest::blocking::Client` (owns a runtime) created/dropped in async code | use the async client |
| `can call blocking only when running on the multi-threaded runtime` | `block_in_place` on current_thread / `#[tokio::test]` | `spawn_blocking`, or `flavor = "multi_thread"` |
| `there is no reactor running, must be called from the context of a Tokio 1.x runtime` | tokio API used on a non-runtime thread, or with another executor | pass a `Handle`, `handle.spawn`; or a runtime started with `enable_all()` |
| `A Tokio 1.x context was found, but timers are disabled` | builder without `enable_time()` | `enable_all()` |
| `Path segments must not start with ':'` | axum 0.7 path syntax on 0.8 | `/{id}` |
| `Overlapping method route` | same method registered twice for a path | remove duplicate |
