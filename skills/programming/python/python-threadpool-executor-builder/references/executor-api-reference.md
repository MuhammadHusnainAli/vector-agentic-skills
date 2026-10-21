# ThreadPoolExecutor and Future API Reference

Precise semantics of `concurrent.futures` for threads, with the version that introduced each behaviour.
Everything here was checked against CPython 3.11 and 3.14 sources; where behaviour differs by version, the
version is named.

## Contents

1. [Constructor and defaults](#1-constructor-and-defaults)
2. [submit](#2-submit)
3. [map: ordering, eagerness, timeout, exceptions, buffersize](#3-map)
4. [as_completed](#4-as_completed)
5. [wait and return_when](#5-wait-and-return_when)
6. [The Future object](#6-the-future-object)
7. [Done callbacks](#7-done-callbacks)
8. [shutdown and the with-block](#8-shutdown-and-the-with-block)
9. [Interpreter exit](#9-interpreter-exit)
10. [initializer and BrokenThreadPool](#10-initializer-and-brokenthreadpool)
11. [threading.Thread basics](#11-threadingthread-basics)
12. [InterpreterPoolExecutor (3.14)](#12-interpreterpoolexecutor-314)
13. [Version table](#13-version-table)

## 1. Constructor and defaults

```python
from concurrent.futures import ThreadPoolExecutor

ex = ThreadPoolExecutor(
    max_workers=None,          # default below
    thread_name_prefix="",     # 3.6+: threads are named f"{prefix}_{n}"
    initializer=None,          # 3.7+: called once in each worker thread before any task
    initargs=(),               # 3.7+
)
ex.shutdown()
```

| Version | Default `max_workers` |
|---------|------------------------|
| 3.5-3.7 | `os.cpu_count() * 5` |
| 3.8-3.12 | `min(32, (os.cpu_count() or 1) + 4)` |
| 3.13+ | `min(32, (os.process_cpu_count() or 1) + 4)` (respects CPU affinity, e.g. `taskset`) |

The default is tuned for "a few I/O calls plus some GIL-releasing CPU work"; it knows nothing about your
latency or rate limit. On an 8-core laptop it is 12, on a 2-vCPU container it is 6, on a 64-core box it is 32.
For API fan-out set it explicitly (see [bounding-backpressure-and-rate-limits.md](bounding-backpressure-and-rate-limits.md)).
`max_workers <= 0` raises `ValueError`.

Threads are created **lazily**: each `submit()` starts a new thread if no idle thread is available and the
pool is below `max_workers` (idle-thread reuse since 3.8). A pool that never receives work never starts a
thread. Thread names default to `ThreadPoolExecutor-<n>_<i>`; always pass `thread_name_prefix` so thread dumps,
logs and py-spy output say `embed_3` instead of `ThreadPoolExecutor-7_3`.

## 2. submit

```text
fut = ex.submit(fn, /, *args, **kwargs)     # returns concurrent.futures.Future immediately
```

- Never blocks: the work item goes onto an unbounded `queue.SimpleQueue`. Backpressure is your job.
- Raises `RuntimeError('cannot schedule new futures after shutdown')` once `shutdown()` was called (including
  by leaving a `with` block), and `RuntimeError('cannot schedule new futures after interpreter shutdown')`
  once the interpreter's exit hook has run.
- Raises `BrokenThreadPool` if an initializer failed.
- `fn` runs in a worker thread in **that thread's** contextvars context, not the caller's (see
  [thread-safety-and-shared-state.md](thread-safety-and-shared-state.md#contextvars)).

## 3. map

```text
results = ex.map(fn, *iterables, timeout=None, chunksize=1, buffersize=None)   # buffersize: 3.14+
```

| Aspect | Behaviour |
|--------|-----------|
| Submission | Before 3.14, and with `buffersize=None`, **every** element of `zip(*iterables)` is submitted before `map()` returns. A generator is fully drained up front |
| `buffersize=N` (3.14) | At most N tasks submitted ahead of the consumer; the input is consumed lazily as results are yielded |
| Order | Results are yielded in input order, regardless of completion order. A slow first item delays everything behind it |
| Exceptions | `fn`'s exception is raised when its result is reached during iteration. Iteration stops there; queued (not yet started) tasks are cancelled; running ones finish and their results are discarded |
| `timeout` | One deadline for the whole iteration, measured **from the `map()` call**. Raises `TimeoutError` from `__next__`; the late task keeps running |
| `chunksize` | Ignored by `ThreadPoolExecutor` (only `ProcessPoolExecutor` batches) |
| Unconsumed iterator | Exceptions are never raised; inside a `with` block all tasks still run to completion |
| Multiple iterables | Stops at the shortest, like built-in `map` |

```python
import time
from concurrent.futures import ThreadPoolExecutor

ran = []


def work(i: int) -> int:
    time.sleep(0.02)
    ran.append(i)
    if i == 1:
        raise ValueError(f"item {i} failed")
    return i


with ThreadPoolExecutor(max_workers=1) as ex:
    try:
        for value in ex.map(work, range(6)):
            print("got", value)
    except ValueError as exc:
        print("raised:", exc)
print("ran:", sorted(ran))
# got 0
# raised: item 1 failed
# ran: [0, 1, 2]
```

Item 2 had already started when item 1's exception reached the consumer; items 3-5 were cancelled. With more
workers, more items are already running and will finish even though their results are dropped.

## 4. as_completed

```text
for fut in as_completed(fs, timeout=None):
    ...
```

- Yields each future as soon as it finishes (completed, failed or cancelled), already-finished ones first.
- `fs` may be any iterable; duplicates are yielded once. A dict of `future -> metadata` is the idiom.
- `timeout` is a deadline for the whole iteration from the call; when it passes, `__next__` raises
  `TimeoutError` and the remaining futures keep running.
- Futures added to your dict **after** calling `as_completed` are not seen: for a sliding window use `wait`.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import time


def fetch(delay: float) -> float:
    time.sleep(delay)
    return delay


with ThreadPoolExecutor(max_workers=3) as ex:
    futures = {ex.submit(fetch, d): d for d in (0.06, 0.02, 0.04)}
    print([futures[f] for f in as_completed(futures)])   # [0.02, 0.04, 0.06]
```

## 5. wait and return_when

```text
done, not_done = wait(fs, timeout=None, return_when=ALL_COMPLETED)
```

| `return_when` | Returns when |
|---------------|--------------|
| `ALL_COMPLETED` | every future is done or cancelled |
| `FIRST_COMPLETED` | any future finishes or is cancelled |
| `FIRST_EXCEPTION` | any future finishes by raising; if none raises, same as `ALL_COMPLETED` |

`wait` **never raises** on timeout: it returns whatever is done. It is the right primitive for sliding
windows, for loops that must stay responsive to Ctrl-C (`timeout=0.25`), and for fail-fast:

```python
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
import time


def step(i: int) -> int:
    time.sleep(0.01 * i)
    if i == 2:
        raise RuntimeError("tool call 2 failed")
    return i


with ThreadPoolExecutor(max_workers=2) as ex:
    fs = [ex.submit(step, i) for i in range(10)]
    done, not_done = wait(fs, return_when=FIRST_EXCEPTION)
    for f in not_done:
        f.cancel()                                       # queued ones are dropped
    failed = [f for f in done if not f.cancelled() and f.exception() is not None]
    print(repr(failed[0].exception()), sum(f.cancelled() for f in fs) > 0)
# RuntimeError('tool call 2 failed') True
```

## 6. The Future object

| Method | Semantics |
|--------|-----------|
| `result(timeout=None)` | Blocks; returns the value, re-raises the task's exception, raises `CancelledError` if cancelled, `TimeoutError` if not done in time (the task keeps running) |
| `exception(timeout=None)` | Like `result` but returns the exception (or `None`) instead of raising it |
| `cancel()` | `True` if the future was pending and is now cancelled (or was already cancelled); `False` if it is running or done. Threads cannot be interrupted |
| `cancelled()` / `running()` / `done()` | State queries; `done()` is true for finished, failed and cancelled futures |
| `add_done_callback(fn)` | See section 7 |

States: `PENDING -> RUNNING -> FINISHED`, or `PENDING -> CANCELLED`. A raised exception keeps its traceback
(`fut.exception().__traceback__`), so `log.error("...", exc_info=fut.exception())` shows the worker frames.

`concurrent.futures.TimeoutError` is an alias of the builtin `TimeoutError` since 3.11 (before that a separate
class). `concurrent.futures.CancelledError` derives from `concurrent.futures.Error`, an `Exception`, and is a
different class from `asyncio.CancelledError` (a `BaseException` since 3.8). So `except Exception` around
`fut.result()` also catches cancellation of a thread-pool future: handle `CancelledError` first when you need
to count cancelled items separately.

## 7. Done callbacks

```text
fut.add_done_callback(fn)          # fn(fut) is called once the future is done or cancelled
```

- Called in the **thread that completes the future** (a worker thread) or, if the future is already done,
  **immediately in the calling thread**. Never assume which; keep callbacks short and thread-safe.
- Called in the order they were added.
- An `Exception` raised by the callback is caught and logged on the `concurrent.futures` logger as
  `exception calling callback for <Future ...>` and otherwise ignored. A `BaseException` is undefined behaviour.
- A callback does not "handle" an error unless it calls `fut.result()` or `fut.exception()` and acts on it.
- Common uses: release a semaphore slot, update progress, record latency. Not: submit more work to a pool that
  may be shutting down, or block.

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor

seen = []


def slow_parse(text: str) -> int:
    time.sleep(0.05)                                     # still running when the callback is added
    return int(text)


def on_done(fut) -> None:
    exc = fut.exception()
    seen.append((threading.current_thread().name.split("_")[0], type(exc).__name__ if exc else "ok"))


with ThreadPoolExecutor(max_workers=1, thread_name_prefix="w") as ex:
    ex.submit(slow_parse, "x").add_done_callback(on_done)   # fails later, in the worker
    ok = ex.submit(int, "7")
    ok.result()
    ok.add_done_callback(on_done)                        # already done: runs here, in MainThread
print(seen)   # [('w', 'ValueError'), ('MainThread', 'ok')]
```

## 8. shutdown and the with-block

```text
ex.shutdown(wait=True, *, cancel_futures=False)          # cancel_futures: 3.9+
```

| Call | Queued tasks | Running tasks | Returns |
|------|--------------|---------------|---------|
| `shutdown()` / end of `with` | run | run | after all finish |
| `shutdown(wait=False)` | **still run** | run | immediately |
| `shutdown(cancel_futures=True)` | cancelled | run | after running ones finish |
| `shutdown(wait=False, cancel_futures=True)` | cancelled | run | immediately |

- Idempotent: calling it twice is fine (the `with` exit after an explicit shutdown is harmless).
- After shutdown, `submit` raises `RuntimeError`. A worker task that tries to submit follow-up work to its own
  (shutting down) pool gets that error.
- `with ThreadPoolExecutor() as ex:` exits with `shutdown(wait=True)`: if the body raised (including
  `KeyboardInterrupt`), the exit still **waits for every queued task**. That is why Ctrl-C "does nothing" in a
  naive script. Catch it inside the block and call `shutdown(cancel_futures=True)` yourself.
- An executor that is garbage-collected wakes its workers so they exit, but you cannot rely on GC timing.

## 9. Interpreter exit

Since 3.9 pool workers are **non-daemon** threads; `concurrent.futures.thread` registers an exit hook with
`threading._register_atexit` that, during interpreter shutdown:
1. sets a global flag so new `submit` calls raise `cannot schedule new futures after interpreter shutdown`;
2. puts a wake-up sentinel on each pool's queue **behind** the queued work;
3. joins every worker thread.

So all already-queued work runs before the process exits, even for executors you never shut down. Before 3.9
the workers were daemon threads joined by an `atexit` handler, with the same practical effect. Consequences:
- A forgotten executor with 50,000 queued API calls keeps the process alive until they are all done.
- There is no "daemon executor". If work may be abandoned, cancel it (`cancel_futures=True`) and make running
  tasks check a stop event.
- `os._exit()` skips all of this (no flush, no joins): only for a forked child or a hard watchdog kill.

## 10. initializer and BrokenThreadPool

```python
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures.thread import BrokenThreadPool

_local = threading.local()


def init_worker(api_key: str) -> None:
    if not api_key:
        raise RuntimeError("missing API key")
    _local.client = {"key": api_key}                     # e.g. requests.Session() per thread


with ThreadPoolExecutor(max_workers=2, initializer=init_worker, initargs=("",)) as ex:
    fut = ex.submit(len, "x")
    try:
        fut.result(timeout=5)
    except BrokenThreadPool as exc:
        print(type(exc).__name__)                        # BrokenThreadPool
```

- The initializer runs once per worker thread, before its first task, in that thread.
- If it raises, the traceback is logged (`Exception in initializer:` on the `concurrent.futures` logger), the
  pool is marked broken, pending futures fail with `BrokenThreadPool`, and later `submit` calls raise it.
- Keep initializers cheap and idempotent; they run lazily as threads start, so the first tasks pay for them.
- `BrokenThreadPool` lives in `concurrent.futures.thread` and subclasses `concurrent.futures.BrokenExecutor`.

## 11. threading.Thread basics

Use a pool for task fan-out; use a `Thread` for a long-lived role (a writer that drains a queue, a heartbeat,
a watchdog, an event-loop thread).

```python
import queue
import threading

q: "queue.Queue[str | None]" = queue.Queue(maxsize=100)
written = []


def writer() -> None:
    while (item := q.get()) is not None:
        written.append(item)                             # single owner: no lock needed


t = threading.Thread(target=writer, name="jsonl-writer")
t.start()
for i in range(5):
    q.put(f"row {i}")
q.put(None)                                              # sentinel
t.join(timeout=10)
print(len(written), t.is_alive())                        # 5 False
```

| Topic | Rule |
|-------|------|
| `daemon=True` | Killed abruptly at exit: no `finally`, no flush. Only for heartbeats/watchdogs whose loss is harmless |
| Non-daemon, never joined | The process waits for it at exit; its exception only reaches `threading.excepthook` (3.8+) |
| Results | Threads return nothing; use a queue, a pool, or a result holder |
| Exceptions | Print to stderr via `threading.excepthook`; set a custom hook to log them |
| `join(timeout)` | Returns `None` either way: check `is_alive()` afterwards |
| Names | `name="writer"` shows up in dumps and `%(threadName)s` |
| Context | `Thread(context=...)` (3.14) sets the context the thread runs in; on free-threaded builds threads inherit a copy of the caller's context by default (`sys.flags.thread_inherit_context`), on the default build they start empty |

## 12. InterpreterPoolExecutor (3.14)

`concurrent.futures.InterpreterPoolExecutor` is a `ThreadPoolExecutor` subclass whose worker threads each run
their own sub-interpreter (PEP 734) with its own GIL. CPU-bound Python can run in parallel inside one process.
Constraints: the callable and arguments are passed between interpreters (pickled for most objects), module
state is per interpreter, and many C extensions do not support sub-interpreters yet. For I/O fan-out it adds
cost without benefit; use threads. Details: [free-threading and sub-interpreters in the GIL skill](../../python-gil-bottleneck-analyzer/references/free-threading-and-subinterpreters.md).

## 13. Version table

| Version | Change |
|---------|--------|
| 3.2 | `concurrent.futures`: `ThreadPoolExecutor`, `ProcessPoolExecutor`, `Future`, `wait`, `as_completed` |
| 3.5 | `max_workers` may be omitted (default `cpu_count() * 5`); `Executor.map(chunksize=)` |
| 3.6 | `thread_name_prefix` |
| 3.7 | `initializer`, `initargs`, `BrokenThreadPool` |
| 3.8 | Default `min(32, cpu_count() + 4)`; idle threads reused; `threading.excepthook` |
| 3.9 | `shutdown(cancel_futures=)`; workers non-daemon, joined by `threading._register_atexit`; `asyncio.to_thread` |
| 3.11 | `concurrent.futures.TimeoutError` aliases builtin `TimeoutError` |
| 3.12 | `loop.shutdown_default_executor(timeout=)`; `asyncio.run` waits up to 300 s for the default executor |
| 3.13 | Default workers from `os.process_cpu_count()`; free-threaded build `python3.13t` (experimental) |
| 3.14 | `Executor.map(buffersize=)`; `InterpreterPoolExecutor`; free-threaded build supported (PEP 779); `Thread(context=)` |
