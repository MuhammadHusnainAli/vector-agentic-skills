# Runtime, Tasks and Shutdown

How Tokio schedules work, how to own every task you start, how to cancel cleanly, how `select!` drops
futures, and the exact shutdown sequence for a service behind a load balancer.

## Contents

- [The runtime model in one page](#the-runtime-model-in-one-page)
- [Choosing and building the runtime](#choosing-and-building-the-runtime)
- [Spawning: JoinHandle semantics](#spawning-joinhandle-semantics)
- [JoinSet: structured groups with results](#joinset-structured-groups-with-results)
- [TaskTracker: wait for background work](#tasktracker-wait-for-background-work)
- [CancellationToken](#cancellationtoken)
- [select! in depth](#select-in-depth)
- [Cancel safety reference](#cancel-safety-reference)
- [Graceful shutdown sequence](#graceful-shutdown-sequence)
- [Bounding the drain](#bounding-the-drain)
- [Blocking and CPU-bound work](#blocking-and-cpu-bound-work)
- [Panics in tasks](#panics-in-tasks)
- [Checklist](#checklist)

## The runtime model in one page

- A **task** is a future handed to the scheduler (`tokio::spawn`). It runs until it returns `Poll::Pending`
  at an `.await` whose resource is not ready, then the worker picks another task. Tasks are cooperative:
  code between two `.await`s runs without interruption.
- The **multi-thread** scheduler runs N worker threads (default: number of CPU cores) with work stealing.
  Spawned futures may move between threads at every `.await`, so they must be `Send + 'static`.
- The **current_thread** scheduler runs every task on the thread that called `block_on`. Futures still need
  `Send` for `tokio::spawn` (the API is the same), but `LocalSet::spawn_local` accepts `!Send` futures.
- A separate **blocking pool** (default cap 512 threads, created lazily) runs `spawn_blocking` closures and
  the internals of `tokio::fs`.
- Tokio has **cooperative budgeting**: each task gets a budget of operations per poll; when exhausted, tokio
  resources return `Pending` to force a yield. This prevents one busy task looping over a ready channel from
  starving the worker, but it cannot interrupt your own CPU loops: call `tokio::task::yield_now().await` in
  long async loops that do real CPU work per iteration, or move the work off the runtime.

What "blocking" means in practice: anything that takes more than ~10-100 µs without reaching an `.await`. A
40 ms `std::fs::read` on a worker delays every other task scheduled on that worker by 40 ms.

## Choosing and building the runtime

```rust
// 1. Macro, multi-thread (default): one worker per core.
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    Ok(())
}
```

```rust
// 2. Macro with options.
#[tokio::main(flavor = "multi_thread", worker_threads = 4)]
async fn main() -> anyhow::Result<()> {
    Ok(())
}
```

```rust
// 3. Explicit builder: needed for thread names, blocking pool size, hooks, or running sync code before
//    the runtime starts (parsing CLI, loading config, daemonizing).
fn main() -> anyhow::Result<()> {
    let workers = std::env::var("WORKERS").ok().and_then(|v| v.parse().ok()).unwrap_or(4);
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(workers)
        .max_blocking_threads(64)
        .thread_name("svc-worker")
        .thread_stack_size(4 * 1024 * 1024)
        .enable_all()
        .build()?;
    rt.block_on(async_main())
}

async fn async_main() -> anyhow::Result<()> {
    Ok(())
}
```

Container notes:
- `std::thread::available_parallelism()` (what tokio uses for the default) respects cgroup v2 CPU quotas on
  Linux in recent Rust versions, but fractional limits round up. Set `worker_threads` explicitly when the pod
  limit is small (1-2 CPUs) so you do not run 2 busy workers on 1 CPU of quota.
- `enable_all()` is required with the builder; without `enable_time()` `tokio::time::sleep` panics with
  "A Tokio 1.x context was found, but timers are disabled".
- The error "there is no reactor running, must be called from the context of a Tokio 1.x runtime" means a
  tokio resource (`TcpStream`, `sleep`, `spawn`) was used outside `block_on` / a runtime thread, often from a
  `std::thread` or a different executor (`futures::executor::block_on`). Pass a `tokio::runtime::Handle` to
  that thread and call `handle.spawn(..)` / `handle.block_on(..)` there.

| Flavor | Pick when | Avoid when |
|--------|-----------|------------|
| multi_thread | servers, anything with parallel load | you need `!Send` state everywhere |
| current_thread | CLIs, tests, one-connection clients, embedding a runtime per thread (thread-per-core designs) | any CPU or blocking work on the async path (it stalls everything) |
| LocalSet on either | a few `!Send` futures (e.g. a `!Send` SDK) | as a workaround for a `MutexGuard` across await (fix the code instead) |

## Spawning: JoinHandle semantics

```rust,ignore
let handle: tokio::task::JoinHandle<u64> = tokio::spawn(async move { compute().await });

match handle.await {
    Ok(value) => tracing::info!(value, "done"),
    Err(err) if err.is_panic() => tracing::error!("task panicked"),
    Err(err) if err.is_cancelled() => tracing::warn!("task was aborted"),
    Err(err) => tracing::error!(%err, "join error"),
}
```

Facts that matter:
- **Dropping a `JoinHandle` does not cancel the task.** It detaches it. The task keeps running, its output
  and any panic are discarded, and nothing waits for it at shutdown (lint TK009).
- `handle.abort()` requests cancellation: the task is dropped at its next `.await` point. A task inside a
  long synchronous section is not interrupted. `spawn_blocking` closures cannot be aborted once started.
- `handle.abort_handle()` gives a cloneable handle that can abort without owning the result.
- When the runtime shuts down (end of `#[tokio::main]`), all remaining tasks are dropped at their next
  `.await`; destructors run, but code after the `.await` never does. Work you care about must be awaited
  before `main` returns.
- `tokio::spawn` requires `F: Future + Send + 'static` and `F::Output: Send + 'static`.

## JoinSet: structured groups with results

`JoinSet` owns a set of tasks: results come back in completion order, and **dropping the set aborts every
task in it**. Use it for fan-out where you need the results or the errors.

```rust
use std::{sync::Arc, time::Duration};
use tokio::{sync::Semaphore, task::JoinSet};

async fn fetch_all(http: reqwest::Client, urls: Vec<String>) -> anyhow::Result<Vec<(String, u16)>> {
    let limit = Arc::new(Semaphore::new(16)); // at most 16 requests in flight
    let mut set = JoinSet::new();
    for url in urls {
        let http = http.clone();
        let permit = limit.clone().acquire_owned().await?; // backpressure on the spawner too
        set.spawn(async move {
            let _permit = permit; // released when the task ends
            let res = http.get(&url).timeout(Duration::from_secs(5)).send().await?;
            Ok::<_, reqwest::Error>((url, res.status().as_u16()))
        });
    }
    let mut out = Vec::with_capacity(set.len());
    while let Some(joined) = set.join_next().await {
        match joined {
            Ok(Ok(row)) => out.push(row),
            Ok(Err(err)) => tracing::warn!(%err, "fetch failed"),
            Err(join_err) => return Err(join_err.into()), // panic or abort: stop, set drop aborts the rest
        }
    }
    Ok(out)
}
```

- `set.join_all().await` (tokio 1.40+) collects every output and panics if a task panicked; use the
  `join_next` loop when you need per-task error handling.
- `set.abort_all()` cancels everything; `set.shutdown().await` aborts and waits.
- `set.spawn_blocking(..)` adds a blocking closure to the same set.
- Do not keep pushing into a `JoinSet` forever without draining it: finished tasks hold their output until
  joined. For a long-running server, use `try_join_next()` in the loop or a `TaskTracker`.

## TaskTracker: wait for background work

`tokio_util::task::TaskTracker` (feature `rt`) tracks tasks without storing their outputs, so it does not
grow with completed tasks. It is the right owner for "fire and track" work: audit writes, webhooks, cache
refresh.

```rust,ignore
use tokio_util::{sync::CancellationToken, task::TaskTracker};

let tracker = TaskTracker::new();
let token = CancellationToken::new();

// in a handler (tracker cloned into state; TaskTracker is cheap to clone)
tracker.spawn(async move { send_webhook(event).await });

// at shutdown
token.cancel();     // ask long-running loops to stop
tracker.close();    // wait() only resolves after close() AND every task finished
tracker.wait().await;
```

`TaskTracker` vs `JoinSet`:

| | JoinSet | TaskTracker |
|-|---------|-------------|
| Get each task's output | yes (`join_next`) | no (log inside the task) |
| Dropping it | aborts all tasks | tasks keep running |
| Memory for finished tasks | kept until joined | released immediately |
| Wait for all | loop `join_next` | `close()` + `wait()` |
| Typical use | fan-out/fan-in inside one request | background work across the whole app |

## CancellationToken

`tokio_util::sync::CancellationToken` is a cloneable, hierarchical "please stop" signal.

```rust,ignore
use std::time::Duration;
use tokio_util::sync::CancellationToken;

async fn consumer(token: CancellationToken, mut rx: tokio::sync::mpsc::Receiver<Job>) {
    loop {
        tokio::select! {
            biased;
            _ = token.cancelled() => {
                // drain what is already queued, but accept nothing new
                rx.close();
                while let Some(job) = rx.recv().await {
                    process(job).await;
                }
                break;
            }
            maybe = rx.recv() => match maybe {
                Some(job) => process(job).await,
                None => break, // all senders dropped
            },
        }
    }
}
```

- `token.child_token()` is cancelled when the parent is, but cancelling a child does not cancel the parent:
  one token per subsystem, all children of the root.
- `token.cancelled()` borrows the token; `token.clone().cancelled_owned()` returns a `'static` future you can
  pass to `with_graceful_shutdown` or move into a task.
- `token.drop_guard()` returns a guard that cancels the token when dropped: tie a subsystem's lifetime to a
  scope.
- Cancellation is cooperative: code must reach a `select!` on `cancelled()` (or be aborted). A task stuck in
  `process(job).await` will finish that job first; wrap long jobs in `tokio::time::timeout` if that matters.

## select! in depth

```rust,ignore
tokio::select! {
    biased;                                        // optional: poll branches top to bottom
    _ = token.cancelled() => { /* shutdown */ }
    Some(msg) = rx.recv() => { handle(msg).await } // pattern: if it does not match, the branch is disabled
    res = &mut in_flight, if !done => { done = true; res?; } // precondition; poll a pinned future by ref
    else => { /* every branch disabled */ }
}
```

Rules:
- All branch futures are created, then polled concurrently on the **same task** (not in parallel). When one
  completes, the others are **dropped**. That drop is cancellation.
- Without `biased;`, tokio picks a random starting branch each time for fairness. Use `biased;` when the
  order matters (shutdown first, or high-priority queue first), knowing a hot first branch can starve the
  rest.
- The handler (`=> { .. }`) runs after the other futures are dropped, so `.await` in the handler is not
  raced: a slow handler delays the next loop iteration, nothing more.
- To keep a future alive across iterations, create it outside the loop, pin it, and poll `&mut fut`:

```rust,ignore
let sleep = tokio::time::sleep(Duration::from_secs(30));
tokio::pin!(sleep);
loop {
    tokio::select! {
        _ = &mut sleep => { tracing::warn!("idle for 30s"); break; }
        Some(frame) = frames.next() => {
            handle(frame).await;
            sleep.as_mut().reset(tokio::time::Instant::now() + Duration::from_secs(30)); // idle timeout
        }
    }
}
```

A `sleep(..)` written inside the `select!` in a loop is recreated every iteration; if the other branch fires
every 10 s the 30 s timeout never fires (lint TK016). That is correct only when you want an idle timeout and
you intend the reset.

## Cancel safety reference

A future is cancel safe if dropping it before completion loses nothing. From the tokio docs:

| Cancel safe (fine in a `select!` loop) | Not cancel safe (create outside, or use another API) |
|----------------------------------------|------------------------------------------------------|
| `mpsc::Receiver::recv`, `UnboundedReceiver::recv` | `AsyncReadExt::read_exact`, `read_to_end`, `read_to_string` |
| `broadcast::Receiver::recv` | `AsyncBufReadExt::read_line`, `read_until` |
| `watch::Receiver::changed` | `AsyncWriteExt::write_all`, `write_all_buf` |
| `TcpListener::accept`, `UnixListener::accept` | `Mutex::lock`, `RwLock::read/write`, `Semaphore::acquire` (lose FIFO place; no data loss) |
| `AsyncReadExt::read`, `read_buf`; `AsyncWriteExt::write`, `write_buf` | `mpsc::Sender::send` (the message moved into the future is dropped) |
| `tokio::io::Lines::next_line`, `tokio_stream::StreamExt::next` | `tokio::io::copy` |
| `tokio::time::Interval::tick`, `sleep` polled by `&mut` | any `async fn` of your own unless you checked |
| `CancellationToken::cancelled`, `JoinSet::join_next`, `oneshot::Receiver` by `&mut` | |

For framed protocols use `tokio_util::codec::FramedRead` (+ `StreamExt::next`, cancel safe): the codec keeps
partial frames in its buffer. For sends, use `Sender::reserve()` in the select (cancel safe) and then
`permit.send(msg)` in the handler.

## Graceful shutdown sequence

What Kubernetes does on a rollout: marks the pod terminating, removes it from Service endpoints
(asynchronously, takes a few seconds to propagate), runs `preStop`, sends SIGTERM, waits
`terminationGracePeriodSeconds` (default 30), then SIGKILL.

The service should:
1. Catch SIGTERM and Ctrl+C (`tokio::signal::unix::signal(SignalKind::terminate())`, `tokio::signal::ctrl_c()`).
2. Flip readiness to 503 so no new traffic is routed; optionally wait a few seconds for endpoint
   propagation (or use a `preStop: sleep 5` hook).
3. Stop accepting connections and drain in-flight requests (`with_graceful_shutdown`).
4. Cancel background loops (`CancellationToken`), close the `TaskTracker`, wait with a deadline.
5. Flush telemetry, close pools (`pool.close().await` for sqlx), exit 0 before the grace period ends.

```rust
use std::{
    sync::{Arc, atomic::{AtomicBool, Ordering}},
    time::Duration,
};
use tokio_util::{sync::CancellationToken, task::TaskTracker};

async fn wait_for_signal() {
    let ctrl_c = async { tokio::signal::ctrl_c().await.expect("install Ctrl+C handler") };
    #[cfg(unix)]
    let term = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("install SIGTERM handler")
            .recv()
            .await;
    };
    #[cfg(not(unix))]
    let term = std::future::pending::<()>();
    tokio::select! { _ = ctrl_c => {}, _ = term => {} }
}

async fn serve(app: axum::Router, ready: Arc<AtomicBool>, db: sqlx::PgPool) -> anyhow::Result<()> {
    let token = CancellationToken::new();
    let tracker = TaskTracker::new();
    tracker.spawn(refresh_loop(token.child_token()));

    // signal watcher: readiness first, short propagation delay, then start the drain
    let shutdown = token.clone();
    let ready_flag = ready.clone();
    tokio::spawn(async move {
        wait_for_signal().await;
        ready_flag.store(false, Ordering::Relaxed);
        tokio::time::sleep(Duration::from_secs(5)).await;
        shutdown.cancel();
    });

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
    ready.store(true, Ordering::Relaxed);
    axum::serve(listener, app)
        .with_graceful_shutdown(token.clone().cancelled_owned())
        .await?;

    tracker.close();
    if tokio::time::timeout(Duration::from_secs(10), tracker.wait()).await.is_err() {
        tracing::warn!("background tasks still running at exit");
    }
    db.close().await;
    Ok(())
}

async fn refresh_loop(token: CancellationToken) {
    let mut every = tokio::time::interval(Duration::from_secs(60));
    loop {
        tokio::select! {
            _ = token.cancelled() => break,
            _ = every.tick() => { /* refresh caches */ }
        }
    }
}
```

The signal watcher above is a detached spawn on purpose: it lives for the whole process and ends with it.
Mark such lines `// noqa: TK009` if you run the linter in strict mode, or move it into the tracker.

## Bounding the drain

`with_graceful_shutdown` waits for **every** open connection to finish, including long-polling, SSE and
WebSocket connections. Bound it:

```rust,ignore
let server = axum::serve(listener, app).with_graceful_shutdown(token.clone().cancelled_owned());
let mut server_task = tokio::spawn(async move { server.await });

tokio::select! {
    res = &mut server_task => { res??; }               // finished on its own
    _ = async {
        token.cancelled().await;                       // shutdown started
        tokio::time::sleep(Duration::from_secs(20)).await
    } => {
        tracing::warn!("drain deadline hit, aborting remaining connections");
        server_task.abort();
    }
}
```

- Give streaming handlers the token too, so they end their streams when it is cancelled.
- Keep the drain deadline below `terminationGracePeriodSeconds` minus the readiness delay.
- `TimeoutLayer` on the router bounds normal requests, so the drain cannot be held by a stuck handler.

## Blocking and CPU-bound work

| Work | Use | Why |
|------|-----|-----|
| Short sync call (file read, sync SDK call, bcrypt/argon2, image decode) | `tokio::task::spawn_blocking(move \|\| ..).await?` | blocking pool; `await` gives the result |
| Many small file ops | one `spawn_blocking` with std::fs inside | `tokio::fs` does one pool hop per call |
| Parallel CPU (batch hashing, parsing, scoring) | `rayon::spawn` / `pool.install` + `oneshot` | bounded CPU pool, no oversubscription |
| Long-lived blocking loop (serial port, sync consumer) | `std::thread::spawn` + channel | does not occupy the blocking pool forever |
| Must block and you are deep in sync code on a multi-thread runtime | `tokio::task::block_in_place` | converts the worker; panics on current_thread |
| Sync code needs to call async | `Handle::block_on` from a non-runtime thread | `block_on` on a runtime thread panics |

```rust
use rayon::prelude::*;

async fn score_all(docs: Vec<String>) -> anyhow::Result<Vec<f32>> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    rayon::spawn(move || {
        let scores: Vec<f32> = docs.par_iter().map(|d| d.len() as f32).collect();
        let _ = tx.send(scores); // receiver may be gone if the request was cancelled
    });
    Ok(rx.await?)
}
```

`spawn_blocking` is not a CPU limiter: 512 concurrent calls create up to 512 threads. Put a `Semaphore` in
front of it for CPU-heavy closures, or use rayon.

## Panics in tasks

- A panic inside `tokio::spawn` is caught by the runtime; the `JoinHandle` returns `Err(JoinError)` with
  `is_panic()`. If the handle was dropped, the panic is only printed by the panic hook.
- A panic in an axum handler aborts that connection's task: the client sees a closed connection. Add
  `tower_http::catch_panic::CatchPanicLayer` (feature `catch-panic`) to turn it into a 500, but fix the
  panic; do not rely on it.
- `panic = "abort"` in the release profile turns any task panic into process exit: decide deliberately.
- Poisoned `std::sync::Mutex`: after a panic while holding the guard, `lock()` returns `Err(PoisonError)`.
  `.lock().expect("... poisoned")` propagates the crash; `.lock().unwrap_or_else(|e| e.into_inner())` keeps
  going with possibly inconsistent data. `parking_lot::Mutex` has no poisoning.

## Checklist

- [ ] Runtime flavor and worker count chosen for the deployment's CPU limit
- [ ] No `tokio::spawn(..);` with a dropped handle except the documented process-lifetime ones
- [ ] Every loop has a `select!` branch on a `CancellationToken` (or ends when its channel closes)
- [ ] `select!` loops only race cancel-safe futures; timers pinned outside the loop
- [ ] SIGTERM and Ctrl+C handled; readiness flips before the drain; drain has a deadline
- [ ] Background tasks tracked (`TaskTracker`) and awaited with a timeout at shutdown
- [ ] CPU and blocking work on `spawn_blocking`/rayon, with a concurrency bound
- [ ] the scanners (`blocking_in_async`, `await_holding`, `task_hygiene`, `service_hygiene`) pass with `--strict`
