# Thread Safety, Shared State, Context and asyncio Bridges

Which objects can be shared between pool threads, how to share the ones that cannot, the synchronization
primitives and when each is right, how request ids and traces reach worker threads, and how threads and an
event loop talk to each other.

## Contents

1. [What the GIL does and does not protect](#1-what-the-gil-does-and-does-not-protect)
2. [Client and library thread-safety](#2-client-and-library-thread-safety)
3. [Four ways to give workers a client](#3-four-ways-to-give-workers-a-client)
4. [Lock, RLock, Condition, Event, Semaphore, Barrier](#4-lock-rlock-condition-event-semaphore-barrier)
5. [queue.Queue](#5-queuequeue)
6. [threading.local](#6-threadinglocal)
7. [contextvars](#contextvars)
8. [Logging from threads](#8-logging-from-threads)
9. [Threads and asyncio](#9-threads-and-asyncio)
10. [Free-threaded builds](#10-free-threaded-builds)

## 1. What the GIL does and does not protect

On the default CPython build one thread executes bytecode at a time, and many single operations on built-in
types are atomic: `lst.append(x)`, `d[k] = v`, `d.get(k)`, `q.put(x)`. Free-threaded builds (3.13t/3.14t) keep
these single operations safe with per-object locks.

**Compound operations are never atomic**: `counter += 1` (load, add, store), `d[k] = d.get(k, 0) + 1`,
`if k not in cache: cache[k] = compute()`, iterating a dict while another thread inserts
(`RuntimeError: dictionary changed size during iteration`). A thread switch between the read and the write
loses an update. The window is small on the GIL build, which is why these bugs pass tests and appear in
production; the demo below widens it deliberately:

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor

stats = {"tokens": 0}
lock = threading.Lock()


def unsafe_add(n: int) -> None:
    current = stats["tokens"]          # read
    time.sleep(0.001)                  # any I/O or switch here...
    stats["tokens"] = current + n      # ...and this write overwrites someone else's


def safe_add(n: int) -> None:
    with lock:
        current = stats["tokens"]
        time.sleep(0.001)
        stats["tokens"] = current + n


for fn in (unsafe_add, safe_add):
    stats["tokens"] = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(fn, [1] * 200))
    print(fn.__name__, stats["tokens"] == 200)
# unsafe_add False
# safe_add True
```

The best fix is usually structural: **return values from tasks and aggregate in one thread**. Locks are for
state that genuinely must be shared (caches, rate limiters, connection pools). The linter's TPE006 flags
read-modify-write on shared state in workers; TPE007 flags appends/item assignment on module-level containers.

## 2. Client and library thread-safety

| Object | Safe to share? | Notes |
|--------|----------------|-------|
| `requests.Session` | Not guaranteed | requests has never documented Session as thread-safe (a long-standing open GitHub issue); the cookie jar and adapters mutate per request. Simple GETs usually work, which is why the bug is latent. Use one per thread |
| `requests.get(...)` (module functions) | Yes | Each call builds and closes its own Session: safe but no connection reuse |
| `urllib3.PoolManager` | Yes | Thread-safe pools; set `maxsize` >= workers |
| `httpx.Client` | Yes, by design | Connection pool is lock-protected; share one per app; match `limits` to workers |
| `httpx.AsyncClient` | Only within its event loop | Never share across loops/threads |
| `openai.OpenAI`, `anthropic.Anthropic` (sync) | Built on httpx.Client; widely shared across threads | Create once, reuse; never per call (each client has its own pool). Check your SDK version's docs; per-thread clients via `initializer` are the conservative option |
| boto3 `Session` | No | boto3 docs: sessions and resources are not thread-safe |
| boto3 low-level client | Yes (documented) | Create from a session in the main thread, then share; `Config(max_pool_connections=workers)` |
| `sqlite3.Connection` | No by default | `check_same_thread=True` raises `ProgrammingError: SQLite objects created in a thread can only be used in that same thread`. With `False` you must serialize all use yourself |
| psycopg / most DB-API connections | Usually no (threadsafety level 2 at best) | Use the driver's pool (`psycopg_pool.ConnectionPool`, SQLAlchemy engine) and one connection per task |
| SQLAlchemy `Engine` / `sessionmaker` | Engine yes, Session no | Session per thread/task (`scoped_session` or create per task) |
| Redis (`redis.Redis`) | Yes (uses a connection pool) | `max_connections` >= workers |
| Vector DB SDKs (Qdrant, Pinecone, Weaviate, Chroma clients) | Varies by SDK/version | Check docs; when unsure, one client per thread via `threading.local` |
| tokenizers / tiktoken encoders | Encoding is safe for reads in practice | HF fast tokenizers parallelize internally; avoid nested parallelism |
| torch models in eval mode | Forward passes from threads work but serialize on the GPU stream | Batch instead; one inference thread per GPU |
| `random` module functions | Yes (single C calls) | For reproducibility give each task its own `random.Random(seed)` |
| `json`, `re` compiled patterns | Yes | Stateless |
| `logging` | Yes | Handlers hold an RLock |

## 3. Four ways to give workers a client

**a) Per thread with `threading.local` + `initializer`** (requests, sqlite, unknown SDKs):

```python
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

_local = threading.local()
DB_PATH = ":memory:"                                    # a file path in real code


def init_worker() -> None:
    _local.conn = sqlite3.connect(DB_PATH)              # created in, and owned by, this worker thread


def lookup(doc_id: int) -> str:
    row = _local.conn.execute("SELECT ? || '-' || ?", (doc_id, threading.current_thread().name)).fetchone()
    return row[0]


with ThreadPoolExecutor(max_workers=3, thread_name_prefix="db", initializer=init_worker) as ex:
    rows = list(ex.map(lookup, range(6)))
print(len(rows), all("-db_" in r for r in rows))        # 6 True
```

Connections opened in the initializer are never closed explicitly (threads end at shutdown and the objects are
collected). If you need deterministic closing, register each one in a list under a lock and close them after
`shutdown()` (the `thread-local-client` recipe does this).

**b) One shared thread-safe client** (httpx, boto3 client, OpenAI/Anthropic SDK): create it before the pool,
pass it in, size its connection pool to the worker count.

**c) A pool of N clients in a `queue.Queue`** when clients are expensive and not thread-safe:

```python
import queue
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor


class ClientPool:
    def __init__(self, factory, size: int) -> None:
        self._q: queue.Queue = queue.Queue()
        for _ in range(size):
            self._q.put(factory())

    @contextmanager
    def client(self, timeout: float = 30.0):
        c = self._q.get(timeout=timeout)                # blocks when all are checked out
        try:
            yield c
        finally:
            self._q.put(c)                              # always returned, even on error


created = []
pool = ClientPool(lambda: created.append(1) or {"id": len(created)}, size=2)


def call(i: int) -> int:
    with pool.client() as c:
        return c["id"]


with ThreadPoolExecutor(max_workers=8) as ex:
    ids = set(ex.map(call, range(50)))
print(len(created), ids <= {1, 2})                      # 2 True
```

**d) A single owner thread** (sqlite writes, a non-thread-safe file writer): workers `put` records on a queue,
one writer thread consumes them and is the only code touching the resource. See section 5.

## 4. Lock, RLock, Condition, Event, Semaphore, Barrier

| Primitive | Use | Pitfall |
|-----------|-----|---------|
| `Lock` | Protect a small critical section | Never hold it across I/O or `fut.result()`; never acquire it twice in one thread |
| `RLock` | Code that may re-enter while holding the lock (method calling another locked method) | Slightly slower; hides design smells |
| `Condition` | Wait until a predicate on shared state is true (`cond.wait_for(pred, timeout)`) | Always wait in a loop / `wait_for`; notify while holding the lock |
| `Event` | One-way flag: stop, ready | `wait(timeout)` returns the flag value; use it for interruptible sleeps |
| `Semaphore` / `BoundedSemaphore` | Limit concurrent access (N connections, N in-flight) | `BoundedSemaphore` raises on over-release, catching bugs |
| `Barrier` | Make N threads reach a point together (tests, benchmarks) | `BrokenBarrierError` if one times out |

Always use `with lock:` (released on exceptions). Acquire with a timeout in code that must not hang:
`if not lock.acquire(timeout=5): raise TimeoutError(...)`. When several locks are needed, take them in one
global order everywhere. Deadlocks from lock order, non-reentrant re-acquisition and lost wake-ups are covered
in [threading-and-multiprocessing-deadlocks.md](../../python-async-deadlock-debugger/references/threading-and-multiprocessing-deadlocks.md).

A `Condition` that lets the main thread wait until N results are ready (or a deadline passes):

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor

cond = threading.Condition()
ready = []


def produce(i: int) -> None:
    time.sleep(0.01 * (i % 3))
    with cond:
        ready.append(i)
        cond.notify_all()


with ThreadPoolExecutor(max_workers=4) as ex:
    for i in range(10):
        ex.submit(produce, i).add_done_callback(lambda f: f.result())
    with cond:
        got_five = cond.wait_for(lambda: len(ready) >= 5, timeout=2)
    print(got_five)                                     # True
```

(The done-callback reads `f.result()` so a failure is at least logged by `concurrent.futures`; in real code
keep the futures and check them.)

## 5. queue.Queue

- `Queue(maxsize=N)`: `put` blocks when full (backpressure), `get` blocks when empty; both take `timeout=`.
- `task_done()` + `join()`: `join` returns when every item put has been marked done. Forgetting `task_done`
  in an error path hangs `join` forever: put it in `finally`.
- Shut consumers down with a sentinel per consumer (or `Queue.shutdown()` on 3.13+, which makes `get` raise
  `queue.ShutDown` once the queue is empty).
- `SimpleQueue`: unbounded, no `task_done`, reentrant (safe from `__del__`/signal handlers).
- `PriorityQueue`: `(priority, seq, item)` tuples, with a sequence number so items never get compared.

Single-writer pattern: many workers produce, one thread owns the sqlite connection.

```python
import queue
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

DONE = object()
rows: queue.Queue = queue.Queue(maxsize=256)
written = []


def writer() -> None:
    conn = sqlite3.connect(":memory:")                  # owned by this thread only
    conn.execute("CREATE TABLE chunks (id INTEGER, text TEXT)")
    while (item := rows.get()) is not DONE:
        conn.execute("INSERT INTO chunks VALUES (?, ?)", item)
    conn.commit()
    written.append(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
    conn.close()


def chunk(i: int) -> None:
    rows.put((i, f"chunk {i}"))                         # blocks if the writer falls behind


w = threading.Thread(target=writer, name="sqlite-writer")
w.start()
try:
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(chunk, range(500)))
finally:
    rows.put(DONE)
    w.join()
print(written)                                          # [500]
```

## 6. threading.local

`threading.local()` gives each thread its own attribute namespace. In a pool, a worker thread runs many tasks,
so **values persist across tasks on the same thread**: perfect for clients, wrong for per-task state.

```python
import threading
from concurrent.futures import ThreadPoolExecutor

_local = threading.local()


def handle(user: str) -> str:
    previous = getattr(_local, "user", None)            # leftover from an earlier task on this thread
    _local.user = user
    return f"{user} saw {previous}"


with ThreadPoolExecutor(max_workers=1) as ex:
    print(list(ex.map(handle, ["alice", "bob"])))       # ['alice saw None', 'bob saw alice']
```

Never store request/tenant/user data in `threading.local` inside pool tasks; pass it as an argument or use a
ContextVar with `copy_context().run` (next section).

## contextvars

A `ContextVar` holds per-context values (request id, tenant, trace span, OpenTelemetry context). Pool tasks
run in the **worker thread's** context, not the submitter's:

- The caller's values are not visible: `.get()` returns the default (or raises `LookupError` without one).
- A `.set()` inside a task persists into later tasks on the same worker thread.
- `asyncio.to_thread` copies the caller's context; `executor.submit`, `executor.map`,
  `loop.run_in_executor` and `threading.Thread` (on the default build) do not.

Fix: run each task in a copy of the submitter's context.

```python
import contextvars
from concurrent.futures import ThreadPoolExecutor

tenant = contextvars.ContextVar("tenant", default="-")


def task(i: int) -> str:
    seen = tenant.get()
    tenant.set(f"leak-{i}")                              # leaks to later tasks unless run in a copy
    return seen


tenant.set("acme")
with ThreadPoolExecutor(max_workers=1) as ex:
    plain = [ex.submit(task, i).result() for i in range(2)]                              # noqa: TPE019
    copied = [ex.submit(contextvars.copy_context().run, task, i).result() for i in range(2)]
print(plain)    # ['-', 'leak-0']
print(copied)   # ['acme', 'acme']
```

- One `copy_context()` **per task**: sharing one copy between concurrently running tasks raises
  `RuntimeError: cannot enter context: ... is already entered`.
- A subclass that overrides `submit` covers `map` too (map calls submit): see
  `scripts/executor_tool.py scaffold --recipe context-propagation`.
- `threading.Thread(target=contextvars.copy_context().run, args=(fn, *args))` for raw threads; 3.14 adds
  `Thread(context=...)`, and free-threaded builds inherit a copy by default (`-X thread_inherit_context`).
- OpenTelemetry stores the active span in a ContextVar, so the same rule applies; its threading
  instrumentation package automates the copy if you prefer instrumentation over code.
- The linter flags workers that read a module-level ContextVar but were submitted without a copy (TPE019).

## 8. Logging from threads

`logging` is thread-safe: each handler serializes `emit` with an RLock. What to add:
- `%(threadName)s` in the format, and `thread_name_prefix` on every executor, so lines read `embed_3`.
- Request ids via a `logging.Filter` that reads a ContextVar (works only if the context was propagated).
- For slow handlers (HTTP log shippers, cloud logging), a `QueueHandler` in front and a `QueueListener` that
  does the I/O in one thread, so worker threads never block on logging.

```python
import logging
import logging.handlers
import queue
import sys
from concurrent.futures import ThreadPoolExecutor

log_q: queue.Queue = queue.Queue(-1)
stream = logging.StreamHandler(sys.stdout)
stream.setFormatter(logging.Formatter("%(threadName)s %(levelname)s %(message)s"))
listener = logging.handlers.QueueListener(log_q, stream)
log = logging.getLogger("ingest")
log.addHandler(logging.handlers.QueueHandler(log_q))
log.setLevel(logging.INFO)
log.propagate = False
listener.start()
try:
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed") as ex:
        ex.submit(log.info, "batch %d embedded", 7).result()
finally:
    listener.stop()                                     # flushes queued records
# embed_0 INFO batch 7 embedded
```

Unhandled exceptions in raw threads go to `threading.excepthook` (3.8+); install one that logs them:
`threading.excepthook = lambda a: log.error("thread %s died", a.thread.name, exc_info=(a.exc_type, a.exc_value,
a.exc_traceback))`. Pool tasks never reach it: their exceptions are stored on the Future.

## 9. Threads and asyncio

| Direction | API | Notes |
|-----------|-----|-------|
| async -> blocking | `await asyncio.to_thread(fn, *args, **kwargs)` (3.9) | Default executor (`min(32, cpus + 4)` threads); copies contextvars |
| async -> blocking, own pool | `await loop.run_in_executor(pool, partial(fn, x, key=v))` | Positional args only; no context copy; limit with the pool size |
| thread -> coroutine | `asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)` | Returns a `concurrent.futures.Future`; deadlocks if called on the loop thread |
| thread -> loop callback | `loop.call_soon_threadsafe(cb, *args)` | The only safe way to touch loop objects from a thread |
| sync code needs an async SDK | A loop running in a dedicated thread | Start once; stop with `call_soon_threadsafe(loop.stop)`; join |

```python
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor


class LoopThread:
    """Run coroutines from sync/threaded code on one background event loop."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="asyncio-loop")
        self.thread.start()

    def run(self, coro, timeout: float = 30.0):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.loop.close()


async def async_embed(text: str) -> int:
    await asyncio.sleep(0.01)                           # an async-only SDK call
    return len(text)


portal = LoopThread()
try:
    with ThreadPoolExecutor(max_workers=4) as ex:      # sync workers calling async code
        print(list(ex.map(lambda t: portal.run(async_embed(t)), ["a", "bb", "ccc"])))   # [1, 2, 3]
finally:
    portal.close()
```

Never call `portal.run` (or any `.result()` on a `run_coroutine_threadsafe` future) from a coroutine running
on that same loop: the loop waits for itself. `asyncio.run()` shuts the default executor down at exit (3.9+;
waits up to 300 s since 3.12), so a stuck `to_thread` call delays exit. For thousands of concurrent calls use
asyncio end to end: [python-asyncio-pattern-advisor](../../python-asyncio-pattern-advisor/SKILL.md).

## 10. Free-threaded builds

On `python3.13t` / `python3.14t` (`sys._is_gil_enabled()` returns `False`):
- Threads run Python code in parallel, so CPU-bound pools finally scale, and races that were rare become common.
  Every TPE006 finding is a real bug there.
- Built-in containers stay internally consistent (per-object locks), but compound operations still race.
- C extensions must declare support; importing one that does not re-enables the GIL (with a warning) unless
  `PYTHON_GIL=0` / `-X gil=0` forces it off.
- Threads inherit a copy of the creator's context by default (`sys.flags.thread_inherit_context`), but pool
  workers are created once and reused, so still copy the context per task.

Measuring whether a workload scales, and what to do when it does not:
[python-gil-bottleneck-analyzer](../../python-gil-bottleneck-analyzer/SKILL.md).
