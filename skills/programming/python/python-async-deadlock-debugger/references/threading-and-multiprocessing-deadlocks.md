# Threading and Multiprocessing Deadlocks

Hangs in threads, executors and processes: lock order, conditions, queues, pool exhaustion, multiprocessing
queues and pipes, fork, logging, the GIL, signal handlers and the shutdown hang. Every reproduction is
bounded by a timeout so it terminates; the fix follows. Rule ids refer to `scripts/hang_scan.py`.

## Contents

- [1. Lock-order cycles (DLK001)](#1-lock-order-cycles-dlk001)
- [2. Lock vs RLock and self-deadlock (DLK002)](#2-lock-vs-rlock-and-self-deadlock-dlk002)
- [3. Acquire without release on error paths (DLK009)](#3-acquire-without-release-on-error-paths-dlk009)
- [4. Condition and Event lost wakeups (DLK010, DLK011)](#4-condition-and-event-lost-wakeups-dlk010-dlk011)
- [5. queue.Queue: join, sentinels, dead consumers (DLK008, DLK015)](#5-queuequeue-join-sentinels-dead-consumers-dlk008-dlk015)
- [6. Thread pool exhaustion (DLK012)](#6-thread-pool-exhaustion-dlk012)
- [7. Threads that die silently](#7-threads-that-die-silently)
- [8. multiprocessing: joining before draining (DLK014)](#8-multiprocessing-joining-before-draining-dlk014)
- [9. Pipes: OS buffer full](#9-pipes-os-buffer-full)
- [10. Killed workers and Pool.map that never returns](#10-killed-workers-and-poolmap-that-never-returns)
- [11. fork while other threads hold locks (DLK017)](#11-fork-while-other-threads-hold-locks-dlk017)
- [12. The GIL and C extensions](#12-the-gil-and-c-extensions)
- [13. Signal handlers (DLK018)](#13-signal-handlers-dlk018)
- [14. Shutdown hangs: non-daemon threads, executors, atexit (DLK013)](#14-shutdown-hangs-non-daemon-threads-executors-atexit-dlk013)
- [15. Free-threaded Python (3.13t, 3.14t)](#15-free-threaded-python-313t-314t)

## 1. Lock-order cycles (DLK001)

```python
import threading
import time

model_lock = threading.Lock()
tokenizer_lock = threading.Lock()
results = []


def worker(first, second, name):
    with first:
        time.sleep(0.05)
        if second.acquire(timeout=1):        # timeout only to make the demo terminate
            second.release()
            results.append(f"{name}: ok")
        else:
            results.append(f"{name}: would deadlock")


a = threading.Thread(target=worker, args=(model_lock, tokenizer_lock, "embedder"))
b = threading.Thread(target=worker, args=(tokenizer_lock, model_lock, "refresher"))
a.start(); b.start(); a.join(); b.join()
print(sorted(results))  # ['embedder: would deadlock', 'refresher: would deadlock']
```

Fixes, best first:
1. **One lock** if both always protect one logical resource.
2. **Global order**: assign each lock a level and acquire in increasing level. For dynamic pairs (e.g. two
   accounts, two shards), sort: `first, second = sorted((l1, l2), key=id)`.
3. **No nested locking**: copy what you need under lock A, release, then take lock B.
4. **Try-lock with back-off** (`acquire(timeout=...)`, release everything, sleep with jitter, retry) only
   when ordering is impossible; it trades deadlock for possible livelock.

Enforce the order in tests with an ordered-lock wrapper
([prevention-and-testing.md](prevention-and-testing.md#lock-hierarchy-enforced-at-runtime)).

## 2. Lock vs RLock and self-deadlock (DLK002)

`threading.Lock` deadlocks when the holder acquires it again; `threading.RLock` counts re-entries by the
owning thread. `threading.Condition()` uses an `RLock` by default. A self-deadlock is usually a public method
calling another public method that also locks:

```python
import threading


class VectorCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def put(self, key, vec):
        with self._lock:
            self._data[key] = vec
            if len(self._data) > 2:
                self._evict_locked()          # not self.evict(): that would re-take _lock

    def evict(self):
        with self._lock:
            self._evict_locked()

    def _evict_locked(self):
        self._data.pop(next(iter(self._data)))


c = VectorCache()
for i in range(4):
    c.put(f"doc{i}", [i])
print(sorted(c._data))  # ['doc2', 'doc3']
```

Prefer the `_locked` helper over switching to `RLock`: RLock hides re-entrancy bugs (invariants broken
mid-method are visible to the re-entrant call) and does not help when the second acquire happens in a
different thread (a callback run by an executor), where it deadlocks exactly like a `Lock`.

## 3. Acquire without release on error paths (DLK009)

```python
import threading

gpu_slots = threading.BoundedSemaphore(2)


def run_batch(batch):
    with gpu_slots:                  # released on exceptions too
        if not batch:
            raise ValueError("empty batch")
        return len(batch)


for b in ([], [1, 2]):
    try:
        print(run_batch(b))
    except ValueError as err:
        print("error:", err)
print("free slots:", gpu_slots._value)  # private, for illustration: 2 (no leak)
# error: empty batch
# 2
# free slots: 2
```

The leaking form is `gpu_slots.acquire(); ...; gpu_slots.release()` without `try/finally`. If acquire and
release must live in different places (a permit handed to a callback), release in a `finally` of the
callback and add a timeout to the acquire so a leak becomes an error, not a hang:
`if not gpu_slots.acquire(timeout=30): raise TimeoutError("no GPU slot in 30s")`.

## 4. Condition and Event lost wakeups (DLK010, DLK011)

Rules for `threading.Condition`:
- Change the shared state and `notify()` **while holding the condition's lock**.
- Wait in a predicate loop: `while not pred(): cond.wait(timeout)` or simply `cond.wait_for(pred, timeout)`.
  Wakeups can be spurious, and another consumer can take the item between notify and your wake-up.
- Use `notify_all()` when waiters wait for different predicates.

```python
import threading

cond = threading.Condition()
ready = []


def producer():
    with cond:
        ready.append("embedding batch 1")
        cond.notify()                        # may run before the consumer waits


def consumer(out):
    with cond:
        if cond.wait_for(lambda: ready, timeout=2):   # checks the predicate first: no lost wakeup
            out.append(ready.pop())


p = threading.Thread(target=producer)
p.start(); p.join()                          # notify happens before anyone waits
out = []
c = threading.Thread(target=consumer, args=(out,))
c.start(); c.join()
print(out)  # ['embedding batch 1']
```

With `if not ready: cond.wait()` instead, the consumer would sleep forever: the only notify already
happened. `threading.Event` is level-triggered (once `set()`, `wait()` returns immediately), so it does not
lose a `set()`; it loses **pulses**: `ev.set(); ev.clear()` can complete before a waiter wakes up, and the
waiter sleeps again. Use a counter or a queue for "something happened N times", and always wait with a
timeout in loops that must observe a stop flag (DLK011).

## 5. queue.Queue: join, sentinels, dead consumers (DLK008, DLK015)

- `q.join()` waits until `task_done()` was called once per `put()`. Call it in `finally` (DLK008).
- `q.join()` has **no timeout parameter**. To bound it, join the worker threads with a timeout, or poll:
  `while q.unfinished_tasks and time.monotonic() < deadline: time.sleep(0.1)`.
- Stop workers with a sentinel per worker (`for _ in workers: q.put(None)`), a stop `Event` checked with
  `q.get(timeout=...)`, or on 3.13+ `q.shutdown()`: blocked `get()` raises `queue.ShutDown` once the queue is
  empty, blocked `put()` raises immediately; `shutdown(immediate=True)` also drains it and releases `join()`.
- A bounded `put()` whose consumer died blocks forever: supervise consumers, or `put(item, timeout=...)` and
  treat `queue.Full` as "the pipeline is broken".

```python
import queue
import threading


def worker(q, out):
    while True:
        item = q.get()
        try:
            if item is None:
                return
            out.append(item.upper())
        finally:
            q.task_done()


q, out = queue.Queue(maxsize=4), []
threads = [threading.Thread(target=worker, args=(q, out), name=f"chunker-{i}") for i in range(2)]
for t in threads:
    t.start()
for doc in ["intro", "methods", "results", "appendix"]:
    q.put(doc, timeout=5)
for _ in threads:
    q.put(None, timeout=5)                 # one sentinel per worker
q.join()
for t in threads:
    t.join(timeout=5)
print(sorted(out))  # ['APPENDIX', 'INTRO', 'METHODS', 'RESULTS']
```

## 6. Thread pool exhaustion (DLK012)

A task running in an executor that submits more work to the **same** executor and waits for it deadlocks
when all workers are outer tasks: no worker is free for the inner ones.

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError

pool = ThreadPoolExecutor(max_workers=2)


def embed_chunk(chunk):
    return len(chunk)


def process_document(doc):
    inner = [pool.submit(embed_chunk, c) for c in doc.split()]
    return sum(f.result(timeout=1) for f in inner)       # waits on the same pool


outer = [pool.submit(process_document, d) for d in ["a b", "c d", "e f"]]
try:
    print([f.result() for f in outer])
except TimeoutError:
    print("pool exhausted: outer tasks wait for inner tasks that cannot start")
pool.shutdown(cancel_futures=True)
```

Fixes: a separate executor per level (`doc_pool` for documents, `embed_pool` for chunks); run the inner work
inline in the worker; or flatten: the caller submits all leaf tasks and aggregates. The same applies to
asyncio's default executor (`to_thread` calling back into `to_thread` via the loop), to `multiprocessing.Pool`
tasks that use the pool, and to Ray/Dask tasks that block on sub-tasks in a fixed-size worker set.

Other executor hangs:
- `fut.result()` / `as_completed(futs)` / `wait(futs)` without `timeout=` waits forever for a stuck task.
- `executor.shutdown(wait=True)` (and leaving a `with ThreadPoolExecutor()` block) waits for running tasks;
  queued tasks still start unless `shutdown(cancel_futures=True)` (3.9+). A running task cannot be killed:
  cooperative stop flags or processes are the only way.

## 7. Threads that die silently

An exception in a thread prints a traceback via `threading.excepthook` (3.8+) and the thread ends. Anything
waiting for that thread's output (a queue item, an event, `task_done()`) now waits forever, and the traceback
scrolled away hours ago. Route thread failures to the waiters:

```python
import queue
import threading

results: queue.Queue = queue.Queue()


def parse_pdf(path):
    try:
        if path.endswith(".bad"):
            raise ValueError(f"cannot parse {path}")
        results.put(("ok", path))
    except Exception as err:            # propagate the failure instead of dying silently
        results.put(("error", err))


t = threading.Thread(target=parse_pdf, args=("report.bad",))
t.start()
status, value = results.get(timeout=5)
t.join(timeout=5)
print(status, value)  # error cannot parse report.bad
```

Executors already do this: the exception is stored in the `Future` and re-raised by `result()`.
Set `threading.excepthook` to log through your logging setup so thread deaths are visible.

## 8. multiprocessing: joining before draining (DLK014)

A process that put data on a `multiprocessing.Queue` does not exit until a background feeder thread has
flushed it into the underlying pipe. If the parent calls `p.join()` before reading, and the data is larger
than the pipe buffer (typically 64 KiB on Linux), parent and child wait for each other. The
multiprocessing docs call this out under "Joining processes that use queues".

```python
import multiprocessing as mp


def embed_shard(n, out):
    out.put([0.1] * n)                          # ~n * 9 bytes pickled


if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    out = ctx.Queue()
    p = ctx.Process(target=embed_shard, args=(200_000, out))
    p.start()
    p.join(timeout=2)                            # BUG order: join before get
    print("child exited before drain:", not p.is_alive())
    vecs = out.get(timeout=10)                   # drain ...
    p.join(timeout=10)                           # ... then join
    print("after drain:", not p.is_alive(), len(vecs))
# child exited before drain: False
# after drain: True 200000
```

Fix: drain first (`results = [out.get(timeout=...) for _ in procs]`), then `join(timeout=...)`. Prefer
`ProcessPoolExecutor`/`Pool.map`, which handle this for you. `Queue.cancel_join_thread()` lets the child
exit without flushing, which loses data: use only for best-effort telemetry.

## 9. Pipes: OS buffer full

Any pipe has a finite kernel buffer. A writer blocks when it is full; if the reader is waiting for the writer
to finish first, both hang.

- `subprocess.Popen(cmd, stdout=PIPE, stderr=PIPE)` followed by `proc.wait()` hangs when the child writes
  more than the buffer: use `proc.communicate(timeout=...)` or `subprocess.run(..., capture_output=True,
  timeout=...)`, which read both pipes concurrently.
- `multiprocessing.Pipe()`: `conn.send(big)` blocks until the other side `recv()`s. Two processes that both
  `send` large objects before `recv` deadlock. Alternate, use a thread for receiving, or use queues.
- Reading only stdout while the child fills stderr: same deadlock. Merge (`stderr=STDOUT`) or read both.

```python
import subprocess
import sys

code = "import sys; sys.stdout.write('x' * 1_000_000); sys.stderr.write('done')"
proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
print(len(proc.stdout), proc.stderr)  # 1000000 done
```

## 10. Killed workers and Pool.map that never returns

When a `multiprocessing.Pool` worker is killed (OOM killer on a big embedding batch, segfault in a C
library), the pool replaces the worker but the task it was running is lost, and `pool.map()` waits for it
forever. `concurrent.futures.ProcessPoolExecutor` detects the death and raises `BrokenProcessPool` instead.

- Prefer `ProcessPoolExecutor` for robustness; catch `BrokenProcessPool`, recreate the pool, resubmit.
- With `Pool`, use `map_async(...).get(timeout=...)` / `apply_async(...).get(timeout=...)`.
- Set `maxtasksperchild` (Pool) or `max_tasks_per_child` (ProcessPoolExecutor, 3.11+) to bound leaks.
- Cap memory per batch so the OOM killer is not part of the design.

## 11. fork while other threads hold locks (DLK017)

`fork()` copies the process memory but only the calling thread. Any lock held by another thread at that
instant stays locked forever in the child: the allocator, a `logging` handler lock, an import lock, CUDA,
gRPC, OpenBLAS/MKL thread pools, an `httpx` connection pool, `queue.Queue` internals.

- Python 3.12+ emits `DeprecationWarning` when `os.fork()` is called in a process with other threads.
- Python 3.14 changed the default `multiprocessing` start method on Linux (and other POSIX except macOS)
  from `fork` to `forkserver`; macOS has defaulted to `spawn` since 3.8. Code that explicitly selects
  `"fork"` keeps the old behaviour and the risk.
- CPython reinitialises its own `logging` locks in the child via `os.register_at_fork` (current versions);
  third-party locks and C libraries are not reset. CUDA cannot be used in a forked child after the parent
  initialised it.
- Fix: `mp.get_context("spawn")` or `"forkserver"` for every pool; create thread pools, clients and models
  after starting worker processes (or inside the workers); never call `os.fork()` in a threaded program.

```python
import multiprocessing as mp


def tokenize(text):
    return len(text.split())


if __name__ == "__main__":
    ctx = mp.get_context("spawn")                # safe with threads, CUDA, gRPC in the parent
    with ctx.Pool(2) as pool:
        print(pool.map(tokenize, ["a b c", "d e"], chunksize=1))  # [3, 2]
```

## 12. The GIL and C extensions

A C extension that blocks **without releasing the GIL** (a long native computation, a blocking call in a
binding that forgot `Py_BEGIN_ALLOW_THREADS`) stops every Python thread, including your watchdog and the
asyncio loop. Symptoms: Python-level dumpers (and `hang_watchdog.py`'s in-process dumper) do not answer;
faulthandler's C-level signal handler still dumps (it does not need the GIL), and `py-spy dump --native`
shows the native frames. A pure-Python example is catastrophic regex backtracking: `re.match(r"(a+)+$",
"a" * 40 + "b")` holds the GIL for the whole match.

Deadlock variant: a C extension calls back into Python (acquiring the GIL) while holding its own mutex, and
another thread holds the GIL while waiting for that mutex. Fix belongs in the extension (release the GIL
before taking its own locks); workaround: serialise access to it from Python, or run it in a separate process.

## 13. Signal handlers (DLK018)

Python signal handlers run in the **main thread**, between bytecodes, at an arbitrary point in whatever the
main thread was doing. If it was inside `with lock:` and the handler takes the same non-reentrant lock, the
process deadlocks. If it was writing to a buffered stream and the handler prints or logs to the same
stream, you get `RuntimeError: reentrant call inside <_io.BufferedWriter>` or interleaved output.
`logging` handler locks are `RLock`s, so re-entry from the same thread does not deadlock, but it can corrupt
a half-written record and still deadlock if the handler also waits on something the interrupted code holds.

```python
import signal
import threading

stop = threading.Event()


def on_sigterm(signum, frame):
    stop.set()                     # only set a flag; do the work in normal code


signal.signal(signal.SIGTERM, on_sigterm)
signal.raise_signal(signal.SIGTERM)  # 3.8+
print("stop requested:", stop.wait(timeout=1))  # stop requested: True
```

In asyncio use `loop.add_signal_handler(signal.SIGTERM, stop_event.set)` (Unix), which runs the callback in
the loop instead of interrupting arbitrary code. Long blocking waits in the main thread (`lock.acquire()`,
`queue.get()`, `thread.join()` without timeout) delay signal handling; on POSIX lock acquisition is
interruptible by signals since 3.2, but a C call that does not return to the interpreter is not.

## 14. Shutdown hangs: non-daemon threads, executors, atexit (DLK013)

At exit the interpreter joins every **non-daemon** thread (`threading._shutdown`). A worker blocked on
`queue.get()` keeps the process alive forever after `main()` returns, and Ctrl+C only interrupts the join
attempt.

- Give every long-lived thread a stop mechanism (Event checked via `get(timeout=...)`, sentinel, or
  `Queue.shutdown()`), and stop + `join(timeout=...)` it in a `finally` or a context manager.
- `daemon=True` only for helpers that may be killed mid-operation (no files half-written, no transactions):
  daemon threads are stopped abruptly at interpreter exit.
- `ThreadPoolExecutor` workers are not daemon threads (since 3.9); the executor joins them at exit
  (`threading._register_atexit`, which runs **before** `atexit` handlers). Submitting work from an `atexit`
  handler raises `RuntimeError: cannot schedule new futures after interpreter shutdown`; a running task that
  never ends blocks exit. Shut down executors explicitly, with `cancel_futures=True` when results are no
  longer needed.
- `multiprocessing.Queue` joins its feeder thread at exit: unflushed data to a dead reader can block exit.
  Use `q.close(); q.join_thread()` deliberately, or `cancel_join_thread()` for best-effort data.
- `asyncio.run()` cancels leftover tasks and waits for them, then shuts down the default executor (with a
  300 s timeout since 3.12). A task that swallows `CancelledError`, or a `to_thread` call stuck in IO,
  delays exit.

```python
import threading
import time
from contextlib import contextmanager


@contextmanager
def background_worker(fn, name):
    stop = threading.Event()
    t = threading.Thread(target=fn, args=(stop,), name=name)
    t.start()
    try:
        yield t
    finally:
        stop.set()
        t.join(timeout=5)
        if t.is_alive():
            raise RuntimeError(f"thread {name} did not stop within 5s")


def heartbeat(stop):
    while not stop.wait(0.05):
        pass


with background_worker(heartbeat, "heartbeat") as t:
    time.sleep(0.1)
print("exited cleanly:", not t.is_alive())  # exited cleanly: True
```

## 15. Free-threaded Python (3.13t, 3.14t)

The free-threaded build (experimental in 3.13, officially supported in 3.14 per PEP 779, still optional)
runs Python threads truly in parallel. Code that was "accidentally safe" because the GIL serialised it can
now race and deadlock: lock-order cycles fire more often, and C extensions that relied on the GIL for their
own locking may need fixes (the interpreter may re-enable the GIL when it imports an extension not marked
as free-threading safe, with a warning). Everything in this file applies with higher probability: run
`hang_scan.py`, enforce lock hierarchies, and stress-test with many threads under timeouts.
