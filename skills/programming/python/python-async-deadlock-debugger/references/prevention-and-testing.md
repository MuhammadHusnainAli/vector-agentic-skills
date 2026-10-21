# Prevention and Testing

Make hangs impossible by construction where you can, loud and diagnosable where you cannot, and caught by
tests that fail in seconds instead of hanging CI for an hour.

## Contents

- [Principles](#principles)
- [Timeouts everywhere, with one deadline](#timeouts-everywhere-with-one-deadline)
- [Lock hierarchy enforced at runtime](#lock-hierarchy-enforced-at-runtime)
- [Structured concurrency](#structured-concurrency)
- [Shutdown protocol](#shutdown-protocol)
- [Watchdogs and heartbeats](#watchdogs-and-heartbeats)
- [Event loop lag monitor](#event-loop-lag-monitor)
- [Testing: fail by timeout, never hang](#testing-fail-by-timeout-never-hang)
- [Deterministic deadlock reproductions](#deterministic-deadlock-reproductions)
- [Stress tests that find new interleavings](#stress-tests-that-find-new-interleavings)
- [pytest, pytest-asyncio and anyio setup](#pytest-pytest-asyncio-and-anyio-setup)
- [CI gates](#ci-gates)
- [Review checklist](#review-checklist)

## Principles

1. **Every wait is bounded.** Locks, queues, events, futures, joins, network IO. A bounded wait converts a
   deadlock into an exception with a stack trace at the exact place it happened.
2. **One lock order.** Document levels; enforce them in tests. Never hold a lock across an `await`, IO,
   a callback into user code, or a call into another component that may lock.
3. **Every task and thread has an owner** that waits for it, cancels it, and sees its exceptions
   (TaskGroup, executors, supervised threads). No fire-and-forget.
4. **Every wakeup is guaranteed.** `task_done`, `release`, `set_result`, `notify` in `finally`; failures
   are propagated to waiters, not just logged.
5. **Hangs are observable.** Heartbeats, loop-lag metrics, and a stack-dump trigger installed at startup.

## Timeouts everywhere, with one deadline

Per-call timeouts multiply (5 retries x 3 calls x 30 s = 7.5 minutes). Give each request or job one deadline
and derive the remaining budget for every wait from it.

```python
import asyncio
import time


class Deadline:
    def __init__(self, seconds: float) -> None:
        self.at = time.monotonic() + seconds

    def remaining(self, cap: float = float("inf")) -> float:
        left = self.at - time.monotonic()
        if left <= 0:
            raise TimeoutError("deadline exceeded")
        return min(left, cap)


async def retrieve(q: str) -> list:
    await asyncio.sleep(0.01)
    return [q]


async def generate(docs: list) -> str:
    await asyncio.sleep(0.5)                       # a slow model
    return "answer"


async def rag(q: str, budget_s: float) -> str:
    dl = Deadline(budget_s)
    docs = await asyncio.wait_for(retrieve(q), timeout=dl.remaining(cap=2.0))
    return await asyncio.wait_for(generate(docs), timeout=dl.remaining(cap=30.0))


async def main() -> None:
    print(await rag("what is rope?", budget_s=1.0))
    try:
        await rag("what is rope?", budget_s=0.2)
    except (TimeoutError, asyncio.TimeoutError):
        print("timed out within the 0.2 s budget")


asyncio.run(main())
# answer
# timed out within the 0.2 s budget
```

On 3.11+ `async with asyncio.timeout(budget):` around the whole operation does the same with less code;
`asyncio.timeout_at(loop.time() + budget)` and `cm.reschedule()` adjust it. Threads: pass `timeout=` to
`acquire`, `get`, `put`, `wait`, `join`, `result`; on expiry raise or degrade explicitly.

## Lock hierarchy enforced at runtime

Static analysis (`hang_scan.py` DLK001) finds cycles inside one module. Across modules, assign levels and
check them at runtime in tests (and optionally in staging): acquiring a lock whose level is not higher than
every lock the thread already holds raises immediately, on the first run, instead of deadlocking on the
millionth.

```python
import threading


class LockOrderError(RuntimeError):
    pass


class OrderedLock:
    """A threading.Lock with a level; a thread may only acquire locks in increasing level order."""

    _held = threading.local()

    def __init__(self, name: str, level: int) -> None:
        self.name, self.level = name, level
        self._lock = threading.Lock()

    def _stack(self) -> list:
        if not hasattr(self._held, "stack"):
            self._held.stack = []
        return self._held.stack

    def __enter__(self) -> "OrderedLock":
        stack = self._stack()
        if stack and stack[-1].level >= self.level:
            raise LockOrderError(f"acquiring {self.name}(L{self.level}) while holding "
                                 f"{stack[-1].name}(L{stack[-1].level})")
        if not self._lock.acquire(timeout=30):
            raise TimeoutError(f"{self.name} not acquired within 30s")
        stack.append(self)
        return self

    def __exit__(self, *exc) -> None:
        self._stack().remove(self)
        self._lock.release()


model_lock = OrderedLock("model", 1)
tokenizer_lock = OrderedLock("tokenizer", 2)

with model_lock, tokenizer_lock:
    print("correct order")
try:
    with tokenizer_lock, model_lock:
        pass
except LockOrderError as err:
    print("caught:", err)
# correct order
# caught: acquiring model(L1) while holding tokenizer(L2)
```

The asyncio version keeps the held stack in a `contextvars.ContextVar` (each task has its own context;
child tasks start with a copy of the parent's) and wraps `asyncio.Lock`.

## Structured concurrency

Unowned tasks are where lost exceptions and stuck waiters hide. Rules:
- 3.11+: `async with asyncio.TaskGroup() as tg:`; a failing child cancels its siblings, and the block does
  not exit until every child finished. Put a timeout around the block, or the group waits for its slowest
  child forever.
- 3.9/3.10: keep a set of tasks, `asyncio.wait(tasks, return_when=FIRST_EXCEPTION)`, then cancel and
  `gather(..., return_exceptions=True)` the rest.
- Background tasks that must outlive a request belong to an application-level supervisor created in the
  lifespan (FastAPI) and cancelled at shutdown.
- Threads: executors (`with ThreadPoolExecutor() as pool:`), or a context manager that starts, stops and
  joins (see [threading-and-multiprocessing-deadlocks.md](threading-and-multiprocessing-deadlocks.md#14-shutdown-hangs-non-daemon-threads-executors-atexit-dlk013)).

```python
import asyncio


async def embed_batch(i: int) -> int:
    await asyncio.sleep(0.01 * i)
    if i == 3:
        raise ValueError("batch 3: invalid UTF-8")
    return i


async def main() -> None:
    done = []
    try:
        async with asyncio.timeout(5):                     # 3.11+
            async with asyncio.TaskGroup() as tg:
                for i in range(6):
                    tg.create_task(embed_batch(i), name=f"batch-{i}").add_done_callback(
                        lambda t: done.append(t.get_name()) if not t.cancelled() and not t.exception() else None)
    except* ValueError as eg:
        print("failed:", eg.exceptions[0], "| completed before cancel:", sorted(done))


asyncio.run(main())  # failed: batch 3: invalid UTF-8 | completed before cancel: ['batch-0', 'batch-1', 'batch-2']
```

## Shutdown protocol

Every long-lived worker needs a documented way to stop:

| Worker | Stop signal | Wait |
|--------|-------------|------|
| asyncio task | `task.cancel()` (re-raise `CancelledError` after cleanup) | `await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 10)` |
| asyncio queue consumer | `q.shutdown()` (3.13+) or one sentinel per consumer | `await q.join()` with a timeout, then cancel |
| thread | `threading.Event` checked via `q.get(timeout=...)` / `stop.wait(interval)` | `t.join(timeout)`, then log `is_alive()` |
| thread queue consumer | sentinel per worker, or `q.shutdown()` (3.13+) | `join(timeout)` |
| executor | `shutdown(wait=True, cancel_futures=True)` (3.9+) | bounded by your tasks' own timeouts |
| process | `terminate()` after a grace period, `kill()` after another | `join(timeout)`; drain its queues first |

Handle SIGTERM by setting the stop signal (never by doing the shutdown inside the handler) and give the
whole shutdown a deadline; if it is exceeded, dump stacks (`dump_all()`) and exit non-zero.

## Watchdogs and heartbeats

An in-process watchdog thread watches a progress counter; if it does not move for `stall_s`, it dumps all
threads and tasks and optionally aborts so the orchestrator restarts the process.

```python
import os
import sys
import threading
import time


class ProgressWatchdog:
    def __init__(self, stall_s: float, on_stall) -> None:
        self.stall_s, self.on_stall = stall_s, on_stall
        self._last = time.monotonic()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="progress-watchdog", daemon=True)

    def beat(self) -> None:                       # call after each processed item / step
        self._last = time.monotonic()

    def __enter__(self) -> "ProgressWatchdog":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self.stall_s / 4):
            idle = time.monotonic() - self._last
            if idle >= self.stall_s:
                self.on_stall(idle)
                self._last = time.monotonic()      # one report per stall period


def report(idle: float) -> None:
    import faulthandler
    print(f"no progress for {idle:.1f}s; dumping stacks", file=sys.stderr)
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
    # in production: dump_all() from hang_watchdog for asyncio tasks too; os.abort() to get restarted


stalls = []
with ProgressWatchdog(stall_s=0.2, on_stall=stalls.append) as wd:
    for item in range(3):
        time.sleep(0.05)
        wd.beat()
    time.sleep(0.35)                               # a stall
print("stalls detected:", len(stalls), "pid", os.getpid() > 0)  # stalls detected: 1 pid True
```

Externally, `hang_watchdog.py --idle 120` does the same for any script: progress is output on
stdout/stderr or a call to `heartbeat()`. In Kubernetes, a liveness probe that checks "last progress
timestamp is recent" (not just "the HTTP server answers") restarts stalled workers; dump stacks before
failing the probe.

## Event loop lag monitor

```python
import asyncio
import time


async def lag_monitor(interval: float, samples: list, n: int) -> None:
    loop = asyncio.get_running_loop()
    for _ in range(n):
        start = loop.time()
        await asyncio.sleep(interval)
        samples.append(loop.time() - start - interval)   # how late the loop woke us


async def main() -> None:
    samples: list = []
    mon = asyncio.create_task(lag_monitor(0.01, samples, 10))
    await asyncio.sleep(0.03)
    time.sleep(0.2)                                       # simulated sync call on the loop
    await mon
    print(f"max loop lag: {max(samples):.2f}s")


asyncio.run(main())  # max loop lag: 0.20s (approximately)
```

Export the lag as a metric; alert above ~100 ms. A lag spike pinpoints the time window; debug mode or a
stack dump during the spike names the call.

## Testing: fail by timeout, never hang

A deadlock test must **terminate** on the buggy code. Put a timeout at three levels:
1. Inside the test: `asyncio.wait_for`/`asyncio.timeout` around the scenario, `join(timeout)` on threads.
2. Per test: `pytest-timeout` (`@pytest.mark.timeout(10)` or `--timeout=60`), which dumps stacks and fails
   the test; pytest's built-in `faulthandler_timeout` dumps stacks of slow tests (does not fail them).
3. Per job: the CI step timeout, with `faulthandler.dump_traceback_later(..., exit=True)` or
   `hang_watchdog.py --kill-after` so you get stacks instead of "job cancelled".

Thread-based scenarios cannot be cancelled: run them in a daemon thread and check `is_alive()` after a
join timeout, so a deadlocked thread does not keep the test process alive.

```python
import threading
import unittest


def run_bounded(fn, timeout: float) -> None:
    """Run fn in a daemon thread; fail (do not hang) if it does not finish in time."""
    errors = []

    def target():
        try:
            fn()
        except BaseException as err:  # re-raised in the test thread below
            errors.append(err)

    t = threading.Thread(target=target, daemon=True, name="scenario")
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise AssertionError(f"scenario did not finish within {timeout}s (deadlock?)")
    if errors:
        raise errors[0]


class Cache:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}

    def put(self, k, v):
        with self.lock:
            self.data[k] = v
            self._evict_locked()

    def _evict_locked(self):
        while len(self.data) > 2:
            self.data.pop(next(iter(self.data)))


class CacheTest(unittest.TestCase):
    def test_put_does_not_self_deadlock(self):
        c = Cache()
        run_bounded(lambda: [c.put(i, i) for i in range(5)], timeout=2)
        self.assertEqual(sorted(c.data), [3, 4])


if __name__ == "__main__":
    unittest.main(argv=["x", "-v"], exit=False)  # test_put_does_not_self_deadlock ... ok
```

## Deterministic deadlock reproductions

Do not rely on `sleep()` to create the bad interleaving: force it with events/barriers, so the test
reproduces the deadlock on every run before the fix and proves its absence after.

```python
import asyncio


async def scenario(fixed: bool) -> str:
    index_lock, memory_lock = asyncio.Lock(), asyncio.Lock()
    upsert_holds_first, summarise_holds_first = asyncio.Event(), asyncio.Event()

    async def wait_briefly(ev: asyncio.Event) -> None:
        try:                                             # let the other task take its first lock, if it can
            await asyncio.wait_for(ev.wait(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

    async def upsert() -> None:
        async with index_lock:
            upsert_holds_first.set()
            await wait_briefly(summarise_holds_first)
            async with memory_lock:
                pass

    async def summarise() -> None:
        first, second = (index_lock, memory_lock) if fixed else (memory_lock, index_lock)
        async with first:
            summarise_holds_first.set()
            await wait_briefly(upsert_holds_first)
            async with second:
                pass

    try:
        await asyncio.wait_for(asyncio.gather(upsert(), summarise()), timeout=1)
        return "ok"
    except asyncio.TimeoutError:
        return "deadlock"


print(asyncio.run(scenario(fixed=False)), asyncio.run(scenario(fixed=True)))  # deadlock ok
```

The same technique works for threads with `threading.Barrier(2, timeout=...)`: the barrier itself raises
`BrokenBarrierError` instead of hanging if the other party never arrives.

## Stress tests that find new interleavings

When you do not know the bad interleaving yet:
- Run the concurrent scenario hundreds of times with randomised small sleeps/`await asyncio.sleep(0)`
  injected at yield points, each run bounded by a timeout.
- For threads, shrink the GIL switch interval to force more context switches:
  `sys.setswitchinterval(1e-6)` (default 0.005 s), and test on the free-threaded build (3.13t/3.14t) where
  threads really run in parallel.
- Run with `PYTHONASYNCIODEBUG=1` / `-X dev` so blocking calls and never-awaited coroutines show up.
- Wrap the whole stress job in `hang_watchdog.py --kill-after` so a hit produces a stack dump.

## pytest, pytest-asyncio and anyio setup

```python
# conftest.py / test_agent.py  (requires pytest, pytest-asyncio, pytest-timeout)
import asyncio

import pytest


@pytest.mark.timeout(10)                 # pytest-timeout: fail + dump stacks after 10 s
@pytest.mark.asyncio                     # pytest-asyncio; with anyio use @pytest.mark.anyio
async def test_agent_step_does_not_hang_on_dead_tool():
    async def dead_tool():
        await asyncio.Event().wait()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(dead_tool(), timeout=0.1)
```

```ini
# pytest.ini
[pytest]
timeout = 120
faulthandler_timeout = 60
asyncio_mode = strict
```

`pytest-timeout`'s default `signal` method raises in the main thread (POSIX); the `thread` method dumps all
stacks and hard-exits, which also works when the main thread is stuck in C code. Use
`--timeout-method=thread` in CI for deadlock-prone suites.

## CI gates

```bash
python scripts/hang_scan.py src/ --strict --ignore DLK011,DLK015      # static: high/medium rules block merges
python scripts/hang_watchdog.py --kill-after 1800 --dump-file hang-dump.txt -m pytest -x tests/
```

Upload `hang-dump.txt` as a CI artifact on failure: the next "the job timed out" ticket arrives with
every thread and task stack attached.

## Review checklist

- [ ] Each lock has a documented level; nested acquisitions go upward; no lock held across `await`/IO
- [ ] No method that takes a lock calls another public method that takes the same lock
- [ ] No `threading` primitives, `time.sleep`, `.result()`, `.join()` or sync clients in `async def`
- [ ] `asyncio.run` only at entry points; no `run_until_complete` inside coroutines
- [ ] Each `get()` matched by `task_done()` in `finally`; each `acquire()` by `release()` in `finally`
- [ ] Every `create_future()` resolved on all paths, with timeouts on the await
- [ ] Every task/thread/process owned, stoppable, and joined with a timeout
- [ ] Nothing submitted to an executor waits on the same executor
- [ ] Multiprocessing: spawn/forkserver, drain before join, timeouts on results
- [ ] Signal handlers only set flags
- [ ] Tests for concurrency paths have per-test timeouts and deterministic interleavings
