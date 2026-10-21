# Pool API Reference

Every stdlib API for process parallelism, with defaults that matter, ordering guarantees and version tags.
Baseline is Python 3.9; newer features are tagged. Examples use small stand-in tasks so they run anywhere;
replace them with your parser, tokenizer or scorer.

## Contents

- [1. Choosing between the APIs](#1-choosing-between-the-apis)
- [2. concurrent.futures.ProcessPoolExecutor](#2-concurrentfuturesprocesspoolexecutor)
- [3. multiprocessing.Pool](#3-multiprocessingpool)
- [4. Pool method matrix](#4-pool-method-matrix)
- [5. apply_async, callbacks and error_callback](#5-apply_async-callbacks-and-error_callback)
- [6. Chunksize semantics per API](#6-chunksize-semantics-per-api)
- [7. Futures: as_completed, wait, cancellation](#7-futures-as_completed-wait-cancellation)
- [8. InterpreterPoolExecutor (3.14)](#8-interpreterpoolexecutor-314)
- [9. Process, Queue, Pipe, Event](#9-process-queue-pipe-event)
- [10. Contexts](#10-contexts)
- [11. Version table](#11-version-table)

## 1. Choosing between the APIs

| Question | ProcessPoolExecutor | multiprocessing.Pool |
|----------|--------------------|----------------------|
| Worker killed (OOM, segfault) | `BrokenProcessPool` raised on all pending futures | Worker replaced, its task lost, `map()` waits forever |
| Leaving the `with` block | `shutdown(wait=True)`: waits for all work | `terminate()`: kills outstanding work |
| Streaming over a huge iterable | `map` submits everything up front (3.14: `buffersize=`) | `imap`/`imap_unordered` pull input lazily (still read ahead) |
| Completion-order results | `as_completed(futures)` | `imap_unordered` |
| Recycling workers | `max_tasks_per_child` (3.11, not with fork) | `maxtasksperchild` (any start method) |
| Callbacks | `future.add_done_callback(fn)` (runs in a parent thread) | `callback=`, `error_callback=` (run in the result-handler thread) |
| Interop with asyncio | `loop.run_in_executor(executor, fn, *args)` | none (wrap `apply_async` manually) |
| Kill running tasks | 3.14: `terminate_workers()` / `kill_workers()` | `terminate()` |

Default to `ProcessPoolExecutor`; reach for `Pool` when you need lazy `imap_unordered` with chunks over a
generator, or `maxtasksperchild` together with fork.

## 2. concurrent.futures.ProcessPoolExecutor

```text
ProcessPoolExecutor(max_workers=None, mp_context=None, initializer=None, initargs=(),
                    *, max_tasks_per_child=None)          # max_tasks_per_child: 3.11
executor.submit(fn, /, *args, **kwargs) -> Future
executor.map(fn, *iterables, timeout=None, chunksize=1, buffersize=None)   # buffersize: 3.14
executor.shutdown(wait=True, *, cancel_futures=False)     # cancel_futures: 3.9
executor.terminate_workers() / executor.kill_workers()    # 3.14
```

Defaults and behaviour:
- `max_workers=None` -> `os.process_cpu_count()` on 3.13+, `os.cpu_count()` before. On Windows at most 61.
- `mp_context=None` -> the global default context, except that `max_tasks_per_child` alone selects `spawn`.
  `max_tasks_per_child` with a fork context raises `ValueError`.
- Workers are started on demand (3.9+ reuses idle workers before spawning new ones).
- `initializer` runs once per worker; if it raises, the pool becomes broken and pending futures raise
  `BrokenProcessPool`.
- `map` returns an iterator whose `__next__` raises the first task exception in input order, and
  `timeout` is measured from the original call to `map`.
- `map` without `buffersize` submits every item immediately: 10 million items create 10 million futures.
  On < 3.14 submit in windows (section 7).
- Exceptions raised in a task are re-raised by `result()` with the worker traceback as text in
  `exc.__cause__` (a `_RemoteTraceback`).

```python
import concurrent.futures as cf
import multiprocessing as mp


def score(prompt: str) -> int:
    return sum(map(ord, prompt)) % 97


if __name__ == "__main__":
    prompts = [f"prompt {i}" for i in range(100)]
    with cf.ProcessPoolExecutor(max_workers=4, mp_context=mp.get_context("spawn")) as ex:
        ordered = list(ex.map(score, prompts, chunksize=25))            # input order
        futs = {ex.submit(score, p): i for i, p in enumerate(prompts)}
        by_index = {futs[f]: f.result() for f in cf.as_completed(futs)}  # completion order
    assert ordered == [by_index[i] for i in range(100)]
    print(len(ordered))   # 100
```

## 3. multiprocessing.Pool

```text
multiprocessing.Pool(processes=None, initializer=None, initargs=(), maxtasksperchild=None, context=None)
pool.map(func, iterable, chunksize=None)               pool.map_async(func, iterable, chunksize=None,
pool.imap(func, iterable, chunksize=1)                                callback=None, error_callback=None)
pool.imap_unordered(func, iterable, chunksize=1)       pool.starmap(func, iterable, chunksize=None)
pool.apply(func, args=(), kwds={})                     pool.starmap_async(..., callback=None, error_callback=None)
pool.apply_async(func, args=(), kwds={}, callback=None, error_callback=None)
pool.close(); pool.join(); pool.terminate()
```

- `processes=None` -> `os.process_cpu_count()` (3.13+) or `os.cpu_count()`.
- `Pool` used as a context manager calls `terminate()` on exit. Collect every result inside the block, or
  call `close()` then `join()` before leaving it.
- Workers are daemonic: they cannot start child processes (no nested pools).
- `map`/`starmap` convert the iterable to a list (to compute `len`) and pick a chunksize automatically.
  `imap`/`imap_unordered` consume it lazily through a task-feeder thread, so a generator over 50 million
  lines is fine, but the feeder can run far ahead of the workers: results and inputs pile up in memory if
  the consumer is slow. Bound it by feeding windows (section 7).
- If a worker is killed, `Pool` starts a replacement but never re-runs or fails the lost task: `map()`
  blocks forever. Use `map_async(...).get(timeout=...)` or `ProcessPoolExecutor`.
- `multiprocessing.pool.ThreadPool` (and `multiprocessing.dummy.Pool`) have the same API on threads: no
  pickling, no GIL escape.

```python
import multiprocessing as mp


def count_words(line: str) -> int:
    return len(line.split())


if __name__ == "__main__":
    lines = (f"word {i} " * (i % 5) for i in range(10_000))        # a generator: never materialized
    total = 0
    with mp.get_context("spawn").Pool(4) as pool:
        for n in pool.imap_unordered(count_words, lines, chunksize=500):
            total += n
    print(total)   # 40000
```

## 4. Pool method matrix

| Method | Blocks | Input | Order | Args | Chunksize default | Errors surface |
|--------|--------|-------|-------|------|-------------------|----------------|
| `map` | yes | materialized | input | one | auto | first error raised, others dropped |
| `starmap` | yes | materialized | input | tuple unpacked | auto | same |
| `map_async` / `starmap_async` | no | materialized | input | one / tuple | auto | `get()` / `error_callback` |
| `imap` | per item | lazy | input | one | 1 | raised when that item is reached |
| `imap_unordered` | per item | lazy | completion | one | 1 | raised when that item is yielded |
| `apply` | yes | one call | n/a | args tuple | n/a | raised |
| `apply_async` | no | one call | n/a | args tuple | n/a | `get()` / `error_callback` |

`starmap` is `map` with argument unpacking: `pool.starmap(f, [(a1, b1), (a2, b2)])` calls `f(a1, b1)`.
For keyword parameters use `functools.partial(f, lower=True)` (module-level `f`).

## 5. apply_async, callbacks and error_callback

```python
import multiprocessing as mp

results, errors = [], []


def parse(doc_id: int) -> tuple:
    if doc_id % 7 == 0:
        raise ValueError(f"doc {doc_id} is encrypted")
    return doc_id, doc_id * 10


if __name__ == "__main__":
    with mp.get_context("spawn").Pool(4) as pool:
        handles = [pool.apply_async(parse, (i,), callback=results.append, error_callback=errors.append)
                   for i in range(1, 30)]
        pool.close()
        pool.join()                     # wait INSIDE the block; callbacks have all run after join()
    print(len(results), sorted(str(e) for e in errors)[:2])   # 25 ['doc 14 is encrypted', 'doc 21 is encrypted']
```

Callback rules:
- Callbacks run in the parent's single result-handler thread. Keep them tiny (append, counter, progress
  bar update). A slow or blocking callback stalls every result; an exception in a callback kills the
  result handler and the pool hangs.
- `error_callback` receives the exception instance; the worker traceback is in `exc.__cause__`.
- Callbacks fire in completion order, not submission order: sort or key results by id.
- With callbacks you may skip `get()`, but then you must `close()` + `join()` to know everything finished.
- Without `error_callback` and without `get()`, a task exception is never seen (linter rule MP006).

## 6. Chunksize semantics per API

| API | Default | Notes |
|-----|---------|-------|
| `Pool.map`, `starmap`, `*_async` | `ceil(len / (4 * processes))` | Computed as `divmod(len, 4 * processes)`, rounded up |
| `Pool.imap`, `imap_unordered` | 1 | Always pass one for many small items |
| `ProcessPoolExecutor.map` | 1 | Keyword-only; chunks are submitted as single futures |
| `ProcessPoolExecutor.submit` | n/a | One task per call: batch items yourself (`submit(fn, batch)`) |
| `joblib.Parallel` | `batch_size="auto"` | Adapts to measured task duration |

A chunk is one message: one pickle of `(func, [items])`, one worker wake-up, one result message. Larger
chunks amortize the fixed cost; smaller chunks balance better and report progress more often. The planner
(`scripts/pool_tool.py plan`) chooses the smallest chunk that keeps overhead within 1% and lasts >= 20 ms.

Batching manually is often better than relying on chunksize, because the task can do per-batch setup once:

```python
from concurrent.futures import ProcessPoolExecutor


def batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def embed_batch(texts: list) -> list:
    return [[float(len(t))] for t in texts]          # stand-in for model.encode(texts, batch_size=64)


if __name__ == "__main__":
    texts = [f"chunk {i}" for i in range(1000)]
    with ProcessPoolExecutor(max_workers=4) as ex:
        vectors = [v for batch in ex.map(embed_batch, batched(texts, 64)) for v in batch]
    print(len(vectors))   # 1000
```

## 7. Futures: as_completed, wait, cancellation

| Call | Use |
|------|-----|
| `as_completed(fs, timeout=None)` | Iterate futures as they finish; `timeout` bounds the whole iteration (`TimeoutError`) |
| `wait(fs, timeout=None, return_when=FIRST_COMPLETED / FIRST_EXCEPTION / ALL_COMPLETED)` | Windows of in-flight work, fail fast |
| `future.result(timeout=None)` | Wait for one; timeout stops waiting, does not stop the task |
| `future.exception()` | Get the exception without raising |
| `future.cancel()` | Only succeeds while the task is still pending (not running) |
| `future.add_done_callback(fn)` | Runs when done; in the parent, in a manager thread or immediately if already done |
| `executor.shutdown(cancel_futures=True)` (3.9) | Drop everything not yet started |

Bounded in-flight window (works on 3.9+; replaces `map` on huge inputs):

```python
import concurrent.futures as cf
import itertools


def work(x: int) -> int:
    return x * x


def bounded_map(ex, fn, items, max_in_flight: int):
    it = iter(items)
    pending = {ex.submit(fn, x) for x in itertools.islice(it, max_in_flight)}
    while pending:
        done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
        for fut in done:
            yield fut.result()
        for x in itertools.islice(it, len(done)):
            pending.add(ex.submit(fn, x))


if __name__ == "__main__":
    with cf.ProcessPoolExecutor(max_workers=4) as ex:
        print(sum(bounded_map(ex, work, range(10_000), max_in_flight=64)))   # 333283335000
```

Fail fast on the first error:

```python
import concurrent.futures as cf


def check(x: int) -> int:
    if x == 13:
        raise RuntimeError("bad shard 13")
    return x


if __name__ == "__main__":
    with cf.ProcessPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(check, i) for i in range(50)]
        done, not_done = cf.wait(futs, return_when=cf.FIRST_EXCEPTION)
        for f in not_done:
            f.cancel()                                   # pending ones are dropped
        errors = [f.exception() for f in done if f.exception()]
    print([str(e) for e in errors])   # ['bad shard 13']
```

## 8. InterpreterPoolExecutor (3.14)

`concurrent.futures.InterpreterPoolExecutor` runs each worker in its own sub-interpreter (PEP 734,
`concurrent.interpreters`) inside one process. Each interpreter has its own GIL, so CPU-bound Python runs
in parallel without process start-up or cross-process IPC.

```python
import sys

if sys.version_info >= (3, 14):
    from concurrent.futures import InterpreterPoolExecutor

    def fib(n: int) -> int:
        return n if n < 2 else fib(n - 1) + fib(n - 2)

    if __name__ == "__main__":
        with InterpreterPoolExecutor(max_workers=4) as ex:
            print(list(ex.map(fib, [20, 21, 22])))   # [6765, 10946, 17711]
```

Trade-offs (be conservative, the feature is new):
- Functions and arguments still cross interpreter boundaries (pickled or shared via the interpreters
  API); module-level functions only, as with processes.
- Every interpreter imports its own copy of modules: per-worker import time and memory still apply.
- C extensions must declare sub-interpreter support (multi-phase init); many scientific and ML packages did
  not at release. Test your imports in a sub-interpreter before choosing it.
- A crash in native code takes down the whole process, not just one worker.

## 9. Process, Queue, Pipe, Event

```text
ctx.Process(target=None, name=None, args=(), kwargs={}, *, daemon=None)
p.start(); p.join(timeout=None); p.is_alive(); p.exitcode; p.terminate() (SIGTERM); p.kill() (SIGKILL, 3.7)
p.interrupt()  (SIGINT, 3.14); p.close() (release resources, 3.7)
ctx.Queue(maxsize=0)   put/get(block, timeout), close(), join_thread(), cancel_join_thread()
ctx.SimpleQueue()      put/get, close() (3.9); no feeder thread
ctx.JoinableQueue()    task_done(), join()
ctx.Pipe(duplex=True)  -> (conn1, conn2); send/recv, poll(timeout)
ctx.Event / Lock / RLock / Semaphore / Condition / Barrier / Value / Array
```

- `exitcode` is negative for signals: `-9` means SIGKILL (often the OOM killer).
- A process that has put items on a `Queue` will not exit until its feeder thread has flushed them: drain
  the queue before `join()` (MP012).
- `Queue.get(timeout=...)` everywhere in production code; a dead producer otherwise blocks forever.
- Daemonic processes are killed when the parent exits and cannot have children.

Pipeline skeleton with sentinels and a bounded queue:

```python
import multiprocessing as mp

STOP = None


def parser(inbox, outbox) -> None:
    while (item := inbox.get(timeout=60)) is not STOP:
        outbox.put((item, len(item)))
    outbox.put(STOP)


if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    inbox, outbox = ctx.Queue(maxsize=100), ctx.Queue()
    workers = [ctx.Process(target=parser, args=(inbox, outbox)) for _ in range(3)]
    for w in workers:
        w.start()
    for doc in (f"doc-{i}" for i in range(500)):
        inbox.put(doc, timeout=60)          # bounded: back-pressure on the producer
    for _ in workers:
        inbox.put(STOP)
    results, stopped = [], 0
    while stopped < len(workers):           # drain BEFORE join
        msg = outbox.get(timeout=60)
        if msg is STOP:
            stopped += 1
        else:
            results.append(msg)
    for w in workers:
        w.join(timeout=10)
    print(len(results), [w.exitcode for w in workers])   # 500 [0, 0, 0]
```

The walrus operator needs 3.8+, which the 3.9 baseline covers.

## 10. Contexts

`multiprocessing.get_context(method)` returns an object with the whole multiprocessing API bound to one
start method: `ctx.Pool`, `ctx.Process`, `ctx.Queue`, `ctx.Manager`, `ctx.Lock`, ...

- Objects from different contexts must not be mixed (a spawn-context `Lock` passed to a fork-context
  `Process` raises or misbehaves).
- `ProcessPoolExecutor(mp_context=ctx)` and `Pool(context=ctx)` / `ctx.Pool(...)` take one.
- `multiprocessing.set_start_method(method)` sets the global default once; `force=True` overrides it (only
  for tests and only before any process was started). `get_start_method(allow_none=True)` returns `None` if
  not yet fixed.
- `multiprocessing.set_forkserver_preload(["mypkg.heavy"])` makes the forkserver import modules once, so
  workers fork from a warm server.

## 11. Version table

| Version | API change |
|---------|-----------|
| 3.7 | `Process.kill()`, `Process.close()`; `ProcessPoolExecutor(mp_context=, initializer=, initargs=)` |
| 3.8 | `multiprocessing.shared_memory`, `SharedMemoryManager`; macOS default -> spawn |
| 3.9 | `Executor.shutdown(cancel_futures=)`; `SimpleQueue.close()`; idle worker reuse in executors |
| 3.11 | `ProcessPoolExecutor(max_tasks_per_child=)` |
| 3.12 | `DeprecationWarning` when forking with threads alive (also from `os.fork`) |
| 3.13 | `os.process_cpu_count()` used for default worker counts; `SharedMemory(track=)` |
| 3.14 | forkserver default on Linux; `InterpreterPoolExecutor`; `Executor.map(buffersize=)`; `terminate_workers()`, `kill_workers()`; `Process.interrupt()` |
