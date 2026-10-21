# Asyncio Patterns Catalog

Every core asyncio pattern with runnable code. Examples use small fakes (`asyncio.sleep` for latency) so
they run offline; swap in your real LLM, embedding or vector-store client. Baseline is Python 3.9; newer
features are tagged.

## Contents

- [Mental model](#mental-model)
- [Coroutines, tasks and futures](#coroutines-tasks-and-futures)
- [TaskGroup (3.11+)](#taskgroup-311)
- [gather](#gather)
- [TaskGroup emulation for 3.9 and 3.10](#taskgroup-emulation-for-39-and-310)
- [wait and as_completed](#wait-and-as_completed)
- [Hedged requests and racing models](#hedged-requests-and-racing-models)
- [Worker pools on a queue](#worker-pools-on-a-queue)
- [Multi-stage pipelines](#multi-stage-pipelines)
- [Async generators](#async-generators)
- [Async context managers](#async-context-managers)
- [Calling blocking code](#calling-blocking-code)
- [Threads calling into the loop](#threads-calling-into-the-loop)
- [Background tasks](#background-tasks)
- [Eager tasks (3.12+)](#eager-tasks-312)
- [Synchronization primitives](#synchronization-primitives)
- [Event loop lifecycle](#event-loop-lifecycle)
- [Context variables](#context-variables)

## Mental model

One thread runs the event loop. The loop runs one callback or task step at a time; a task step runs until it
hits an `await` on something that is not ready, then the loop switches to another ready task. Consequences:

- Code between two awaits is atomic with respect to other tasks (no lock needed for a dict update with no
  await in between).
- Anything that does not yield (a blocking call, a CPU loop) stops every other task.
- Concurrency comes from **tasks**, not from `await`. `await a(); await b()` is sequential.

## Coroutines, tasks and futures

```python
import asyncio
import time


async def call_model(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return name


async def main() -> None:
    start = time.perf_counter()
    await call_model("a", 0.1)                 # sequential: 0.2 s total
    await call_model("b", 0.1)
    seq = time.perf_counter() - start

    start = time.perf_counter()
    ta = asyncio.create_task(call_model("a", 0.1))   # both scheduled now
    tb = asyncio.create_task(call_model("b", 0.1))
    print(await ta, await tb)
    conc = time.perf_counter() - start
    print(f"sequential ~{seq:.1f}s, concurrent ~{conc:.1f}s")


asyncio.run(main())
# Output:
# a b
# sequential ~0.2s, concurrent ~0.1s
```

| | Coroutine | Task | Future |
|-|-----------|------|--------|
| What | paused function | coroutine scheduled on the loop | placeholder for a result |
| Starts | when awaited | at the next loop iteration (eager: immediately, 3.12) | n/a |
| Cancel | n/a (close()) | `task.cancel()` | `fut.cancel()` |
| Result | value of `await` | `await task` / `task.result()` | `await fut` / `fut.result()` |
| Await twice | RuntimeError | fine, same result | fine |

`asyncio.ensure_future` is legacy: it wraps coroutines in tasks and passes futures through. Use
`create_task` (or a TaskGroup) for coroutines.

## TaskGroup (3.11+)

Structured concurrency: tasks cannot outlive the `async with` block. When any task fails, the group cancels
the others, waits for them, then raises an `ExceptionGroup` of every non-cancellation error.

```python
import asyncio


async def embed(doc: str) -> list[float]:
    await asyncio.sleep(0.01)
    if doc == "corrupt":
        raise ValueError(f"cannot embed {doc!r}")
    return [float(len(doc))]


async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(embed(d), name=f"embed-{d}") for d in ["alpha", "corrupt", "gamma"]]
    except* ValueError as eg:
        print("failed:", [str(e) for e in eg.exceptions])
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(embed(d)) for d in ["alpha", "beta"]]
    print([t.result() for t in tasks])


asyncio.run(main())
# Output:
# failed: ["cannot embed 'corrupt'"]
# [[5.0], [4.0]]
```

Rules:
- Read results with `t.result()` **after** the block; inside the block tasks may still be running.
- The body of the `async with` is itself part of the group: if it raises, the tasks are cancelled.
- Tasks added from inside a running child (`tg.create_task` from a task) are fine while the group is open.
- `KeyboardInterrupt`/`SystemExit` in a child propagate as themselves, not wrapped.
- To keep going after failures, catch inside the child (`try/except` in a wrapper coroutine) and return an
  error value; the group only cancels on exceptions that escape a child.

## gather

```python
results = await asyncio.gather(*coros)                           # first error propagates, others keep running
results = await asyncio.gather(*coros, return_exceptions=True)   # errors returned in place
```

Semantics people get wrong:
- Without `return_exceptions`, the **first** exception is raised to the awaiter, but the other awaitables are
  **not cancelled**. If the caller then returns, they keep running unowned.
- If the gather itself is cancelled, all children are cancelled.
- With `return_exceptions=True`, `CancelledError` of a child is also returned as a value (it is a
  `BaseException`), so filter with `isinstance(r, BaseException)`, not `Exception`.
- Results are in argument order regardless of completion order.
- Passing an empty list returns `[]` immediately.

## TaskGroup emulation for 3.9 and 3.10

```python
import asyncio
from typing import Awaitable, List, TypeVar

T = TypeVar("T")


async def gather_all_or_cancel(*aws: Awaitable[T]) -> List[T]:
    """Like TaskGroup: on the first failure cancel the rest, wait for them, re-raise."""
    tasks = [asyncio.ensure_future(a) for a in aws]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)   # reap; never leave orphans
        raise


async def ok(x: int) -> int:
    await asyncio.sleep(0.05)
    return x


async def boom() -> int:
    await asyncio.sleep(0.01)
    raise RuntimeError("upstream 500")


async def main() -> None:
    slow = ok(1)
    try:
        await gather_all_or_cancel(slow, boom())
    except RuntimeError as err:
        print("raised:", err)
    print(await gather_all_or_cancel(ok(1), ok(2)))


asyncio.run(main())
# Output:
# raised: upstream 500
# [1, 2]
```

The `anyio` library offers task groups with the same semantics on 3.9+ (`anyio.create_task_group()`), and
`exceptiongroup` backports `ExceptionGroup`/`catch()` for pre-3.11 code.

## wait and as_completed

`asyncio.wait(tasks, timeout=None, return_when=ALL_COMPLETED)` returns `(done, pending)` sets and never raises
task exceptions; you inspect them. Since 3.11 it accepts only tasks/futures, not bare coroutines.

```python
import asyncio


async def score(i: int) -> int:
    await asyncio.sleep(0.02 * (5 - i))     # later items finish first
    return i


async def main() -> None:
    tasks = [asyncio.create_task(score(i)) for i in range(5)]
    order = []
    for fut in asyncio.as_completed(tasks):  # 3.13+: `async for task in asyncio.as_completed(tasks)`
        order.append(await fut)
    print("completion order:", order)

    tasks = [asyncio.create_task(score(i)) for i in range(5)]
    done, pending = await asyncio.wait(tasks, timeout=0.05)
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    print("done in time:", sorted(t.result() for t in done))


asyncio.run(main())
# Output:
# completion order: [4, 3, 2, 1, 0]
# done in time: [3, 4]
```

Use `as_completed` for progress reporting and "stop after the first K good results"; remember to cancel what
is left when you stop early. `wait(timeout=...)` does **not** cancel pending tasks for you.

## Hedged requests and racing models

Send the same request to a second replica (or a fallback model) if the first is slow, keep whichever answers
first, cancel the loser.

```python
import asyncio


async def replica(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"answer from {name}"


async def hedged(hedge_after: float = 0.05) -> str:
    primary = asyncio.create_task(replica("primary", 0.2))
    done, _ = await asyncio.wait({primary}, timeout=hedge_after)
    if done:
        return primary.result()
    backup = asyncio.create_task(replica("backup", 0.02))
    done, pending = await asyncio.wait({primary, backup}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    winner = done.pop()
    return winner.result()          # re-raises if the winner failed; add fallback logic as needed


print(asyncio.run(hedged()))
# Output: answer from backup
```

Hedging doubles cost for the hedged fraction; set `hedge_after` near your p95 latency so only ~5% of requests
are duplicated, and never hedge non-idempotent calls (tool calls with side effects, writes).

## Worker pools on a queue

A fixed number of workers pulling from a bounded queue: constant memory, natural backpressure, easy per-item
error handling. Preferred over "one task per item" when the input is large or unbounded (a corpus, a Kafka
topic, a crawl frontier).

```python
import asyncio


async def process(doc_id: int) -> None:
    await asyncio.sleep(0.001)
    if doc_id == 7:
        raise ValueError("unparseable PDF")


async def run(doc_ids: list[int], n_workers: int = 4) -> tuple[int, list[int]]:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=n_workers * 2)
    ok, failed = 0, []

    async def worker() -> None:
        nonlocal ok
        while True:
            doc_id = await queue.get()
            try:
                await process(doc_id)
                ok += 1
            except Exception:
                failed.append(doc_id)
            finally:
                queue.task_done()

    workers = [asyncio.create_task(worker(), name=f"worker-{i}") for i in range(n_workers)]
    try:
        for d in doc_ids:
            await queue.put(d)
        await queue.join()
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    return ok, failed


print(asyncio.run(run(list(range(20)))))
# Output: (19, [7])
```

Details:
- `task_done()` must be called exactly once per `get()`, in `finally`, or `join()` hangs forever.
- If a worker can die (an exception escapes), `join()` may hang; the `try/except` inside the loop prevents it.
- A worker that crashes inside a TaskGroup cancels the whole pool; that is often what you want for
  all-or-nothing batch jobs.
- 3.13+: `queue.shutdown()` makes blocked `get()` calls raise `asyncio.QueueShutDown` (after the queue drains,
  unless `immediate=True`), which is a cleaner stop signal than cancelling workers. Before 3.13 use a sentinel
  (`None`) per worker or cancellation.

## Multi-stage pipelines

Separate stages (fetch -> parse -> embed -> upsert) with bounded queues, so each stage gets its own
concurrency and the slowest stage throttles the rest.

```python
import asyncio

STOP = object()


def stage(name, inq, outq, fn, workers):
    async def run():
        while True:
            item = await inq.get()
            try:
                if item is STOP:
                    return
                result = await fn(item)
                if outq is not None:
                    await outq.put(result)
            finally:
                inq.task_done()

    tasks = [asyncio.create_task(run(), name=f"{name}-{i}") for i in range(workers)]
    return tasks


async def fetch(url):
    await asyncio.sleep(0.001)
    return f"<html>{url}</html>"


async def parse(html):
    return html.removeprefix("<html>").removesuffix("</html>")


async def embed(text):
    await asyncio.sleep(0.001)
    return (text, len(text))


async def main():
    q1, q2, q3 = (asyncio.Queue(maxsize=8) for _ in range(3))
    results = []

    async def sink(item):
        results.append(item)

    fetchers = stage("fetch", q1, q2, fetch, 4)
    parsers = stage("parse", q2, q3, parse, 2)
    embedders = stage("embed", q3, None, lambda t: _embed_and_sink(t, sink), 3)
    for i in range(10):
        await q1.put(f"doc{i}")
    for group, q in ((fetchers, q1), (parsers, q2), (embedders, q3)):
        for _ in group:
            await q.put(STOP)          # one stop marker per worker, after the real items
        await asyncio.gather(*group)   # stage drained before stopping the next one
    print(len(results), sorted(results)[:2])


async def _embed_and_sink(text, sink):
    await sink(await embed(text))


asyncio.run(main())
# Output: 10 [('doc0', 4), ('doc1', 4)]
```

Shutting stages down in order (stop markers after the data, gather each stage before stopping the next)
guarantees nothing is dropped. For CPU-heavy stages (PDF parsing) call a process pool inside `fn`.

## Async generators

```python
import asyncio
from contextlib import aclosing          # 3.10+


async def token_stream(prompt: str):
    try:
        for tok in prompt.split():
            await asyncio.sleep(0)
            yield tok
    finally:
        print("stream closed")           # runs on exhaustion, break (with aclosing) and cancellation


async def main() -> None:
    async with aclosing(token_stream("the quick brown fox")) as stream:
        async for tok in stream:
            if tok == "brown":
                break                    # aclosing() runs the generator's finally right here
    print("after loop")


asyncio.run(main())
# Output:
# stream closed
# after loop
```

- Without `aclosing`, breaking out of `async for` leaves the generator suspended until it is garbage-collected
  or the loop shuts down (`asyncio.run` finalizes async generators at exit), so cleanup is delayed.
- Never `yield` inside an `async with asyncio.timeout()` or TaskGroup block in a generator that the consumer may
  stop early: the cancel scope would be exited in a different task context. Collect into a queue instead.
- Async comprehensions: `[x async for x in agen()]`, `[await f(x) for x in xs]` (sequential!).
- Built-ins `aiter()` and `anext()` exist since 3.10.

## Async context managers

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def vector_transaction(client):
    tx = await client.begin()
    try:
        yield tx
    except BaseException:
        await tx.rollback()
        raise
    else:
        await tx.commit()
```

- `AsyncExitStack` manages a runtime-determined number of async resources
  (`await stack.enter_async_context(httpx.AsyncClient())`).
- A class implements `__aenter__`/`__aexit__`; `__aexit__` must not swallow exceptions unless intended.
- Cleanup that awaits during cancellation: the `finally` block runs, and awaits inside it work, but a second
  cancellation can interrupt them; keep cleanup short or shield the critical part.

## Calling blocking code

```python
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor


def parse_pdf(path: str) -> int:          # CPU-bound stand-in
    return sum(i * i for i in range(200_000)) % 97 + len(path)


def slow_sdk_call(x: int) -> int:         # blocking I/O stand-in
    time.sleep(0.05)
    return x * 10


async def main() -> None:
    io_results = await asyncio.gather(*(asyncio.to_thread(slow_sdk_call, i) for i in range(5)))
    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(max_workers=2) as pool:
        cpu_results = await asyncio.gather(*(loop.run_in_executor(pool, parse_pdf, f"doc{i}.pdf")
                                             for i in range(4)))
    print(io_results, len(cpu_results))


if __name__ == "__main__":
    asyncio.run(main())
# Output: [0, 10, 20, 30, 40] 4
```

- `to_thread` (3.9) uses the loop's default `ThreadPoolExecutor` and copies `contextvars`.
- The default executor has `min(32, cpu_count + 4)` threads; 100 concurrent `to_thread` calls queue behind
  them. Set a bigger one with `loop.set_default_executor(ThreadPoolExecutor(64))` or bound with a Semaphore.
- Cancellation does not stop the thread; the await is abandoned, the function runs to completion.
- Process pools: functions and arguments must be picklable (module-level functions), and the
  `if __name__ == "__main__":` guard is required with spawn/forkserver start methods (forkserver is the
  Linux default since 3.14).
- 3.14: `concurrent.futures.InterpreterPoolExecutor` runs work in subinterpreters (separate GILs) in one
  process; good for pure-Python CPU work, but many C extensions do not support subinterpreters yet.

## Threads calling into the loop

```python
import asyncio
import threading


async def main() -> None:
    loop = asyncio.get_running_loop()
    done = asyncio.Event()
    results: list[int] = []

    async def record(x: int) -> int:
        results.append(x)
        return x * 2

    def gpu_worker() -> None:                          # e.g. a CUDA thread finishing batches
        fut = asyncio.run_coroutine_threadsafe(record(21), loop)
        print("worker got", fut.result(timeout=5))
        loop.call_soon_threadsafe(done.set)            # never call done.set() directly from a thread

    threading.Thread(target=gpu_worker, daemon=True).start()
    await done.wait()
    print("results", results)


asyncio.run(main())
# Output:
# worker got 42
# results [21]
```

asyncio objects are not thread-safe. From another thread only `call_soon_threadsafe` and
`run_coroutine_threadsafe` are allowed.

## Background tasks

```python
import asyncio
import logging

logger = logging.getLogger(__name__)


class TaskSupervisor:
    """Owns fire-and-forget tasks: keeps references, logs failures, cancels on shutdown."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def spawn(self, coro, *, name: str) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._done)
        return task

    def _done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("task %s failed", task.get_name(), exc_info=task.exception())

    async def aclose(self, timeout: float = 10.0) -> None:
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=timeout)
```

In a FastAPI app create one supervisor in lifespan and `await supervisor.aclose()` in its `finally`.
Starlette's `BackgroundTasks` runs after the response is sent, in the same request lifecycle; it is fine for
short work but not for jobs that must survive a restart (use a real queue: Celery, Arq, RQ, a DB outbox).

## Eager tasks (3.12+)

```python
loop = asyncio.get_running_loop()
loop.set_task_factory(asyncio.eager_task_factory)
```

With eager execution `create_task(coro)` runs the coroutine synchronously until its first real suspension. If
it finishes without suspending (cache hit, validation error) the task is already done and never goes through
the scheduler: big wins for memoized lookups. Costs: code before the first await now runs **before**
`create_task` returns, so ordering assumptions ("the task starts after I set up X") can break. Test with it on
before enabling in production. `asyncio.create_eager_task_factory(custom_task_constructor)` builds one for a
custom Task class.

## Synchronization primitives

| Primitive | Use | Pitfall |
|-----------|-----|---------|
| `asyncio.Lock` | protect a read-modify-write that spans an await (token refresh) | not reentrant; not thread-safe |
| `asyncio.Semaphore(n)` | cap concurrent operations | `release()` without `acquire()` silently raises the cap; use `BoundedSemaphore` |
| `asyncio.Event` | one-shot or resettable signal (index ready, shutdown requested) | `clear()` races with waiters that just woke |
| `asyncio.Condition` | wait for a predicate under a lock | use `wait_for(predicate)` |
| `asyncio.Queue(maxsize)` | hand-off with backpressure | `task_done` per `get` |
| `asyncio.Barrier(n)` (3.11) | n tasks rendezvous (synchronized eval phases) | broken barrier raises `BrokenBarrierError` |

Single-flight token refresh (one refresh even if 50 tasks see an expired token):

```python
class TokenProvider:
    def __init__(self, fetch):
        self._fetch, self._token, self._expires = fetch, None, 0.0
        self._lock = asyncio.Lock()

    async def get(self) -> str:
        loop = asyncio.get_running_loop()
        if self._token and loop.time() < self._expires - 30:
            return self._token
        async with self._lock:
            if self._token and loop.time() < self._expires - 30:   # re-check after waiting
                return self._token
            self._token, ttl = await self._fetch()
            self._expires = loop.time() + ttl
            return self._token
```

## Event loop lifecycle

```python
import asyncio


async def job(n: int) -> int:
    await asyncio.sleep(0)
    return n * n


with asyncio.Runner() as runner:          # 3.11+: one loop for several top-level calls
    print(runner.run(job(3)), runner.run(job(4)))
# Output: 9 16
```

`asyncio.run(coro, debug=None, loop_factory=None)` (loop_factory 3.12+): creates a new loop, runs the
coroutine, cancels remaining tasks, finalizes async generators, shuts down the default executor (3.9+) and
closes the loop. Call it once per program (or per thread).

uvloop (libuv-based loop, often 2-4x faster for socket-heavy servers):

```python
import asyncio

import uvloop

uvloop.run(main())                                               # uvloop >= 0.18
asyncio.run(main(), loop_factory=uvloop.new_event_loop)          # Python 3.12+
```

`uvloop.install()` sets the event loop policy; policies are deprecated in 3.14, so prefer the two forms above.
Uvicorn uses uvloop automatically when installed (`--loop uvloop`). uvloop does not support Windows.

Jupyter / IPython: the kernel already runs a loop, so `asyncio.run()` raises
`RuntimeError: asyncio.run() cannot be called from a running event loop`. Use top-level `await main()` in a
cell (IPython autoawait). Library code that must work in both worlds should expose `async` functions and let
the caller choose; if a sync wrapper is unavoidable, run the coroutine in a separate thread with its own loop:

```python
import asyncio
import concurrent.futures


def run_sync(coro):
    """Run a coroutine from sync code, even when this thread already has a running loop (Jupyter)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()
```

`nest_asyncio` patches the loop to allow re-entrancy; it is unmaintained and breaks with newer Python
versions and uvloop, so avoid it.

## Context variables

`contextvars.ContextVar` values (request id, tenant, trace span) are copied into each task at creation and
into `to_thread` calls, so per-request context flows through fan-out automatically. A task's changes do not
leak back to its parent. Use them instead of globals for request-scoped data in async servers.

```python
import asyncio
import contextvars

request_id = contextvars.ContextVar("request_id", default="-")


async def log_step(step: str) -> str:
    await asyncio.sleep(0)
    return f"[{request_id.get()}] {step}"


async def handle(rid: str) -> list[str]:
    request_id.set(rid)
    return list(await asyncio.gather(log_step("retrieve"), log_step("generate")))


async def main() -> None:
    print(await asyncio.gather(handle("req-1"), handle("req-2")))


asyncio.run(main())
# Output: [['[req-1] retrieve', '[req-1] generate'], ['[req-2] retrieve', '[req-2] generate']]
```
