# Asyncio Deadlocks and Hangs

Every way an asyncio program stops making progress, with a runnable reproduction (bounded by a timeout so it
finishes) and the fix. All examples run on Python 3.9+ unless tagged. The rule ids refer to
`scripts/hang_scan.py`.

## Contents

- [Why asyncio hangs look different](#why-asyncio-hangs-look-different)
- [1. Lock-order cycle between tasks (DLK001)](#1-lock-order-cycle-between-tasks-dlk001)
- [2. Re-acquiring a non-reentrant asyncio.Lock (DLK002)](#2-re-acquiring-a-non-reentrant-asynciolock-dlk002)
- [3. Holding a lock while awaiting work that needs it](#3-holding-a-lock-while-awaiting-work-that-needs-it)
- [4. Threading locks and blocking calls on the loop thread (DLK003, DLK004, DLK005)](#4-threading-locks-and-blocking-calls-on-the-loop-thread-dlk003-dlk004-dlk005)
- [5. Waiting for the loop from the loop (DLK006)](#5-waiting-for-the-loop-from-the-loop-dlk006)
- [6. Queue.join() without task_done() (DLK008)](#6-queuejoin-without-task_done-dlk008)
- [7. Consumers that exit while producers wait on a full queue](#7-consumers-that-exit-while-producers-wait-on-a-full-queue)
- [8. Event and Condition lost wakeups (DLK010)](#8-event-and-condition-lost-wakeups-dlk010)
- [9. Semaphore leaks (DLK009)](#9-semaphore-leaks-dlk009)
- [10. Awaiting a future nobody resolves (DLK016)](#10-awaiting-a-future-nobody-resolves-dlk016)
- [11. gather with a task waiting on a cancelled sibling](#11-gather-with-a-task-waiting-on-a-cancelled-sibling)
- [12. Nested event loops and Jupyter (DLK007)](#12-nested-event-loops-and-jupyter-dlk007)
- [13. Default executor exhaustion](#13-default-executor-exhaustion)
- [14. Swallowed cancellation and shutdown that never ends](#14-swallowed-cancellation-and-shutdown-that-never-ends)
- [15. Unclosed async generators and streams](#15-unclosed-async-generators-and-streams)
- [Quick reference](#quick-reference)

## Why asyncio hangs look different

- Tasks are cooperative. A task suspended on `await` has **no thread stack**: a thread dump of a deadlocked
  asyncio program shows only the loop idling in `select()`/`epoll`. You need task stacks
  (`hang_watchdog.py`, `asyncio.all_tasks()` + await-chain walking, or 3.14 `python -m asyncio pstree PID`).
- One blocking call in any task freezes **all** tasks, including heartbeats and timeouts:
  `asyncio.timeout()` cannot fire while the loop thread is stuck in `time.sleep()`.
- asyncio primitives (`Lock`, `Event`, `Condition`, `Semaphore`, `Queue`) are **not thread-safe** and
  `asyncio.Lock` is **not reentrant**. There is no `asyncio.RLock`.
- Timeouts turn hangs into exceptions. `asyncio.wait_for(aw, t)` (3.9+) and `asyncio.timeout(t)` (3.11+)
  cancel the inner work and raise `TimeoutError` (`asyncio.TimeoutError` before 3.11; the same class since).

## 1. Lock-order cycle between tasks (DLK001)

```python
import asyncio

index_lock = asyncio.Lock()
memory_lock = asyncio.Lock()


async def upsert() -> None:
    async with index_lock:
        await asyncio.sleep(0.01)          # any await lets the other task run
        async with memory_lock:
            pass


async def summarise() -> None:
    async with memory_lock:
        await asyncio.sleep(0.01)
        async with index_lock:             # opposite order: deadlock
            pass


async def main() -> None:
    try:
        await asyncio.wait_for(asyncio.gather(upsert(), summarise()), timeout=1)
    except asyncio.TimeoutError:
        print("deadlocked: each task holds one lock and waits for the other")


asyncio.run(main())  # deadlocked: each task holds one lock and waits for the other
```

Fix: acquire in one canonical order everywhere (`async with index_lock, memory_lock:` in both), or use one
lock for both resources, or restructure so no task holds one lock while acquiring another. Keep slow awaits
(LLM calls, embeddings, network) **outside** locked regions: compute first, then lock briefly to publish.

## 2. Re-acquiring a non-reentrant asyncio.Lock (DLK002)

```python
import asyncio


class Memory:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.turns: list = []

    async def add(self, turn: str) -> None:
        async with self.lock:
            self.turns.append(turn)
            if len(self.turns) > 2:
                await self.compact()   # compact() takes self.lock again -> waits for itself

    async def compact(self) -> None:
        async with self.lock:
            self.turns = self.turns[-2:]


async def main() -> None:
    m = Memory()
    try:
        for t in ["a", "b", "c"]:
            await asyncio.wait_for(m.add(t), timeout=1)
    except asyncio.TimeoutError:
        print("self-deadlock in Memory.add -> compact")


asyncio.run(main())  # self-deadlock in Memory.add -> compact
```

Fix: a public method takes the lock; a private `_compact_locked()` does the work and documents that the
caller holds the lock. Do not build a reentrant lock on `current_task()` unless you must: reentrancy hides
design problems and breaks as soon as work moves to a child task (a child task is a different owner).

```python
import asyncio


class Memory:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.turns: list = []

    async def add(self, turn: str) -> None:
        async with self.lock:
            self.turns.append(turn)
            if len(self.turns) > 2:
                self._compact_locked()

    async def compact(self) -> None:
        async with self.lock:
            self._compact_locked()

    def _compact_locked(self) -> None:
        self.turns = self.turns[-2:]


async def main() -> None:
    m = Memory()
    for t in ["a", "b", "c"]:
        await m.add(t)
    print(m.turns)


asyncio.run(main())  # ['b', 'c']
```

## 3. Holding a lock while awaiting work that needs it

The re-entry does not have to be in the same coroutine. Awaiting a **task** or `gather` that takes the lock
while you hold it is the same deadlock, and hang_scan cannot always see it:

```python
import asyncio

lock = asyncio.Lock()


async def refresh_index() -> None:
    async with lock:
        await asyncio.sleep(0)


async def handler() -> None:
    async with lock:
        task = asyncio.create_task(refresh_index())  # separate task, same lock
        await task                                   # waits for a task that waits for us


async def main() -> None:
    try:
        await asyncio.wait_for(handler(), timeout=1)
    except asyncio.TimeoutError:
        print("deadlock: awaited a child task that needs our lock")


asyncio.run(main())  # deadlock: awaited a child task that needs our lock
```

Fix: release before awaiting the child, or have the child receive the data it needs instead of the lock.

## 4. Threading locks and blocking calls on the loop thread (DLK003, DLK004, DLK005)

`threading.Lock.acquire()`, `time.sleep()`, `requests.get()`, `fut.result()`, `thread.join()`,
`queue.Queue.get()` and `threading.Event.wait()` all block the loop thread. If the party that would unblock
it is another task on the same loop, it can never run:

```python
import asyncio
import threading

shared = threading.Lock()


async def writer() -> None:
    with shared:                     # takes the thread lock on the loop thread
        await asyncio.sleep(0.05)    # suspends while holding it


async def reader() -> None:
    await asyncio.sleep(0.01)
    got = shared.acquire(timeout=0.5)  # blocks the loop; writer can never resume to release it
    print("reader got the lock:", got)
    if got:
        shared.release()


async def main() -> None:
    await asyncio.gather(writer(), reader())


asyncio.run(main())  # reader got the lock: False  (after 0.5 s; without a timeout: forever)
```

Rules:
- State shared **between tasks**: `asyncio.Lock`.
- State shared **with threads**: protect it with a `threading.Lock`, but only touch it from code that never
  awaits while holding it, and keep critical sections tiny; or move the access into a thread with
  `await asyncio.to_thread(fn)` (3.9+).
- Blocking IO/CPU: `await asyncio.to_thread(sync_call, ...)` / `loop.run_in_executor(pool, ...)`, or the
  async version of the client.
- Waiting for a `concurrent.futures.Future`: `await asyncio.wrap_future(fut)`.
- Waiting for a thread/process: `await asyncio.to_thread(t.join, 30)`.

Find these at runtime with debug mode: `asyncio.run(main(), debug=True)` logs every callback or task step
slower than `loop.slow_callback_duration` (default 0.1 s).

## 5. Waiting for the loop from the loop (DLK006)

`asyncio.run_coroutine_threadsafe(coro, loop)` is for **other threads**. Calling `.result()` on it from the
loop thread waits for a coroutine that can only run after the current callback returns: a guaranteed
deadlock (bounded here by `timeout=`):

```python
import asyncio
import concurrent.futures


async def fetch() -> str:
    return "doc"


async def main() -> None:
    loop = asyncio.get_running_loop()
    fut = asyncio.run_coroutine_threadsafe(fetch(), loop)
    try:
        fut.result(timeout=0.5)          # blocks the loop that must run fetch()
    except concurrent.futures.TimeoutError:
        print("deadlock: waited on our own loop")
    print(await asyncio.wrap_future(fut))  # correct: await it


asyncio.run(main())
# deadlock: waited on our own loop
# doc
```

The same shape appears when sync library code called from a coroutine internally does
`run_coroutine_threadsafe(...).result()` or `asyncio.run()` to "bridge" back to async. Fix the bridge: expose
an async API, or call the sync wrapper from a worker thread (`await asyncio.to_thread(sync_wrapper)`), where
`.result(timeout=...)` is legitimate.

## 6. Queue.join() without task_done() (DLK008)

`Queue.join()` returns when the unfinished-task counter reaches zero. Every `put()` increments it; only
`task_done()` decrements it. A worker that forgets, or skips it on an exception, makes `join()` wait forever:

```python
import asyncio


async def worker(q: asyncio.Queue) -> None:
    while True:
        doc = await q.get()
        try:
            if doc == "bad":
                raise ValueError("unparsable PDF")
        except ValueError:
            continue                      # BUG: task_done() skipped on the error path
        q.task_done()


async def main() -> None:
    q: asyncio.Queue = asyncio.Queue()
    w = asyncio.create_task(worker(q))
    for d in ["a", "bad", "c"]:
        q.put_nowait(d)
    try:
        await asyncio.wait_for(q.join(), timeout=1)
    except asyncio.TimeoutError:
        print("join() stuck: unfinished =", q._unfinished_tasks)  # private, for illustration only
    w.cancel()


asyncio.run(main())  # join() stuck: unfinished = 1
```

Fix: `try: ... finally: q.task_done()`, exactly once per `get()`. Never call `task_done()` for items you
did not `get()` (raises `ValueError: task_done() called too many times`).

## 7. Consumers that exit while producers wait on a full queue

Bounded queues give backpressure, which is exactly what deadlocks when the consumer dies: the producer
awaits `put()` forever. Supervise both sides so a failure on one side cancels the other.

```python
import asyncio


async def producer(q: asyncio.Queue) -> None:
    for i in range(100):
        await q.put(i)          # blocks forever once the consumer is gone


async def consumer(q: asyncio.Queue) -> None:
    for _ in range(3):
        await q.get()
    raise RuntimeError("vector store write failed")


async def main() -> None:
    q: asyncio.Queue = asyncio.Queue(maxsize=2)
    # gather() would raise the consumer error but leave the producer blocked and running;
    # a TaskGroup (3.11+) cancels the producer when the consumer fails.
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(producer(q))
            tg.create_task(consumer(q))
    except* RuntimeError as eg:
        print("pipeline failed cleanly:", eg.exceptions[0])


asyncio.run(main())  # pipeline failed cleanly: vector store write failed
```

On 3.9/3.10 emulate it: `asyncio.wait({p, c}, return_when=FIRST_EXCEPTION)`, then cancel and await the
rest. On 3.13+ `q.shutdown()` wakes everyone: blocked `put()` raises `asyncio.QueueShutDown`, `get()` raises
once the queue is empty, and `shutdown(immediate=True)` also drains the queue and unblocks `join()`.

## 8. Event and Condition lost wakeups (DLK010)

`asyncio.Event` is level-triggered: once set, waiters return immediately, so "set before wait" is fine. The
lost wakeup comes from `clear()`: a waiter that wakes after someone cleared the event goes back to sleep,
and a pulse (`set(); clear()`) can be missed by tasks that had not started waiting yet.

`Condition.wait()` must sit in a predicate loop: a notification can be consumed by another waiter, arrive
before you waited, or the predicate can change back before you reacquire the lock.

```python
import asyncio


async def main() -> None:
    cond = asyncio.Condition()
    results: list = []

    async def wait_for_result() -> str:
        async with cond:
            await cond.wait_for(lambda: results)   # loops on the predicate for you
            return results.pop()

    async def publish(item: str) -> None:
        async with cond:
            results.append(item)                   # change state first ...
            cond.notify()                          # ... then notify, under the same lock

    await publish("early")                         # notify before anyone waits: not lost
    print(await asyncio.wait_for(wait_for_result(), timeout=1))


asyncio.run(main())  # early
```

The bug version is `if not results: await cond.wait()`: if the notify happened before the wait, nobody
notifies again and the waiter sleeps forever. For one-shot signals use an `Event` per waiter or a `Future`.

## 9. Semaphore leaks (DLK009)

Manual `acquire()`/`release()` across an `await` leaks a permit whenever the awaited call raises or the task
is cancelled. With 4 permits, 4 timeouts later every caller waits forever:

```python
import asyncio

limiter = asyncio.Semaphore(2)


async def call_llm(prompt: str) -> str:
    await limiter.acquire()
    if prompt == "boom":
        raise RuntimeError("429 Too Many Requests")   # release() below never runs
    limiter.release()
    return prompt


async def main() -> None:
    for p in ["boom", "boom", "ok"]:
        try:
            print(await asyncio.wait_for(call_llm(p), timeout=0.5))
        except RuntimeError:
            pass
        except asyncio.TimeoutError:
            print("starved: both permits leaked")


asyncio.run(main())  # starved: both permits leaked
```

Fix: `async with limiter:` around the call. If you must acquire manually (e.g. acquire in one place,
release in a callback), release in `finally` and on cancellation. Monitor `limiter._value` only in debugging;
in production export "in-flight" counts you maintain yourself.

## 10. Awaiting a future nobody resolves (DLK016)

`loop.create_future()` is how request/response bridges are built (tool calls, RPC over websockets, GPU batch
schedulers). If the resolver crashes, takes a different error path, or the id lookup misses, the waiter
sleeps forever.

```python
import asyncio
from typing import Dict


class ToolBridge:
    def __init__(self) -> None:
        self.pending: Dict[str, asyncio.Future] = {}

    async def call(self, call_id: str, timeout: float = 5.0) -> str:
        fut = asyncio.get_running_loop().create_future()
        self.pending[call_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout)   # bounded
        finally:
            self.pending.pop(call_id, None)               # no leak on timeout/cancel

    def resolve(self, call_id: str, result: str) -> None:
        fut = self.pending.get(call_id)
        if fut is not None and not fut.done():
            fut.set_result(result)

    def fail_all(self, exc: BaseException) -> None:        # call when the transport dies
        for fut in self.pending.values():
            if not fut.done():
                fut.set_exception(exc)


async def main() -> None:
    bridge = ToolBridge()
    asyncio.get_running_loop().call_later(0.05, bridge.resolve, "c1", "42 results")
    print(await bridge.call("c1"))
    asyncio.get_running_loop().call_later(0.05, bridge.fail_all, ConnectionError("socket closed"))
    try:
        await bridge.call("c2")
    except ConnectionError as err:
        print("failed fast:", err)


asyncio.run(main())
# 42 results
# failed fast: socket closed
```

Also: resolving a future from another thread must use `loop.call_soon_threadsafe(fut.set_result, value)`;
calling `set_result` directly from a thread may not wake the loop until something else happens.

## 11. gather with a task waiting on a cancelled sibling

`asyncio.gather()` without `return_exceptions=True` propagates the first exception but **does not cancel**
the other tasks. A task that waits for an event the failed sibling would have set waits forever, and the
program hangs at shutdown (or leaks the task).

```python
import asyncio


async def main() -> None:
    index_ready = asyncio.Event()

    async def build_index() -> None:
        raise RuntimeError("embedding model failed to load")   # never sets index_ready

    async def answer_queries() -> str:
        await index_ready.wait()
        return "answers"

    t1 = asyncio.create_task(build_index(), name="build-index")
    t2 = asyncio.create_task(answer_queries(), name="answer-queries")
    try:
        await asyncio.gather(t1, t2)
    except RuntimeError as err:
        print("gather raised:", err, "| answer-queries still pending:", not t2.done())
    t2.cancel()                                                # without this it waits forever
    await asyncio.gather(t2, return_exceptions=True)


asyncio.run(main())
# gather raised: embedding model failed to load | answer-queries still pending: True
```

Fix: use `asyncio.TaskGroup` (3.11+), which cancels siblings on the first failure; or propagate failure to
dependents explicitly (store the exception and set the event; dependents check it); and bound dependent
waits with timeouts.

## 12. Nested event loops and Jupyter (DLK007)

`asyncio.run()` inside a running loop raises `RuntimeError: asyncio.run() cannot be called from a running
event loop`; `loop.run_until_complete()` raises `RuntimeError: This event loop is already running`. Libraries
that "helpfully" catch that and fall back to a thread + `run_coroutine_threadsafe(...).result()` on the same
loop deadlock instead. `nest_asyncio` (third party, unmaintained) patches the loop to allow re-entry and
turns some of these into hangs that are very hard to debug.

- Scripts: one `asyncio.run(main())` at the entry point; everything below is `await`.
- Jupyter/IPython: the kernel already runs a loop; use top-level `await main()` in a cell.
- Sync API over async code: run the async code in a dedicated loop thread and call
  `run_coroutine_threadsafe(coro, that_loop).result(timeout=...)` from sync callers, never from that loop.
- 3.11+: `asyncio.Runner` keeps one loop for several sync-to-async calls from **sync** code.

## 13. Default executor exhaustion

`asyncio.to_thread()` and `run_in_executor(None, ...)` share the loop's default `ThreadPoolExecutor`
(`min(32, os.cpu_count() + 4)` workers; 3.13 uses `os.process_cpu_count()`). If threads in that pool block
waiting for something that needs **another** default-executor thread (or for the loop thread, which is
waiting for them), the pool deadlocks once it is full. Typical: a sync callback run via `to_thread` that
calls `run_coroutine_threadsafe(coro, loop).result()` where `coro` itself uses `to_thread`. Fix: never
block executor threads on other executor work; give nested levels their own executor
(`loop.run_in_executor(dedicated_pool, ...)`); size pools for the worst case; bound every `.result()`.

## 14. Swallowed cancellation and shutdown that never ends

`asyncio.run()` cancels remaining tasks at exit and waits for them. A task that catches `CancelledError`
(or `BaseException`) and keeps looping never finishes, so `asyncio.run()` never returns and Ctrl+C appears
to do nothing.

```python
import asyncio


async def poller() -> None:
    while True:
        try:
            await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            print("cleanup, then re-raise")
            raise                         # removing this line makes shutdown hang forever


async def main() -> None:
    t = asyncio.create_task(poller())
    await asyncio.sleep(0.02)
    t.cancel()
    await asyncio.gather(t, return_exceptions=True)
    print("poller stopped:", t.cancelled())


asyncio.run(main())
# cleanup, then re-raise
# poller stopped: True
```

Also watch `asyncio.shield()` (the inner work keeps running after the outer is cancelled), `TaskGroup`
exit (waits for every child: one child without a timeout keeps the group open forever), and
`loop.shutdown_default_executor()` waiting for blocked executor threads (3.12 added a `timeout`
parameter, default 300 s used by `asyncio.run`).

## 15. Unclosed async generators and streams

A consumer that `break`s out of `async for` over a streaming response leaves the generator suspended; its
`finally` (closing the HTTP stream, releasing a connection or a semaphore) only runs when it is garbage
collected or when the loop shuts down async generators. Meanwhile the server-side producer blocks on a full
buffer and the connection pool slot stays taken.

```python
import asyncio
from contextlib import aclosing  # 3.10+


async def stream_tokens():
    try:
        for tok in ["The", " answer", " is", " 42", "."]:
            await asyncio.sleep(0)
            yield tok
    finally:
        print("stream closed, connection released")


async def main() -> None:
    async with aclosing(stream_tokens()) as tokens:
        async for tok in tokens:
            if tok == " is":
                break              # aclosing() runs the generator's finally right now
    print("after the loop")


asyncio.run(main())
# stream closed, connection released
# after the loop
```

On 3.9 call `await agen.aclose()` in a `finally`. See
[ai-engineering-hangs.md](ai-engineering-hangs.md#streaming-consumers-that-stop-reading) for the
producer/consumer version.

## Quick reference

| Pattern | Rule | One-line fix |
|---------|------|--------------|
| Locks in opposite order | DLK001 | canonical order / one lock |
| Lock re-acquired via helper | DLK002 | `_locked` helper |
| Thread lock / blocking call in `async def` | DLK003-005 | asyncio primitive, `to_thread`, `wrap_future` |
| `run_coroutine_threadsafe().result()` on the loop | DLK006 | `await` it |
| `asyncio.run` in a running loop | DLK007 | `await`; top-level await in Jupyter |
| `join()` without `task_done()` | DLK008 | `finally: task_done()` |
| Manual acquire/release | DLK009 | `async with sem:` |
| `cond.wait()` without loop | DLK010 | `wait_for(predicate)` |
| Bounded queue, no consumer | DLK015 | start consumer first, TaskGroup |
| Unresolved future | DLK016 | resolve on all paths, `fail_all`, `wait_for` |
| Waiting on a failed sibling | - | TaskGroup |
| Swallowed `CancelledError` | - | always re-raise |
| Unclosed async generator | - | `aclosing()` / `aclose()` |
