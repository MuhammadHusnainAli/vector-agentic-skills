# Testing Threaded Code

Threaded code is hard to test when tests depend on timing. Make concurrency explicit and controllable: inject
the executor, the clock, the sleep function and the client; force interleavings with barriers and events
instead of `sleep`; check for leaked threads; and put a hard timeout on every test so a deadlock fails fast
instead of hanging CI. The examples use stdlib `unittest` so they run anywhere; the same code works under
pytest (shown where pytest adds something).

## Contents

1. [Design for testability](#1-design-for-testability)
2. [An inline executor for logic tests](#2-an-inline-executor-for-logic-tests)
3. [Forcing interleavings with Barrier and Event](#3-forcing-interleavings-with-barrier-and-event)
4. [Fake clocks for rate limiters and retries](#4-fake-clocks-for-rate-limiters-and-retries)
5. [Mocking clients from many threads](#5-mocking-clients-from-many-threads)
6. [Testing bounds, cancellation and Ctrl-C](#6-testing-bounds-cancellation-and-ctrl-c)
7. [Testing context propagation](#7-testing-context-propagation)
8. [Detecting leaked threads](#8-detecting-leaked-threads)
9. [Timeouts so a deadlock fails instead of hanging](#9-timeouts-so-a-deadlock-fails-instead-of-hanging)
10. [Stress tests for races](#10-stress-tests-for-races)
11. [CI checklist](#11-ci-checklist)

## 1. Design for testability

| Dependency | Inject as | Test double |
|------------|-----------|-------------|
| Executor | parameter (`executor: Executor`) or factory | `InlineExecutor` (section 2) or a real small pool |
| Time | `clock: Callable[[], float] = time.monotonic` | `FakeClock` (section 4) |
| Sleep / waiting | `sleep=time.sleep` or a `threading.Event` | fake sleep that advances the fake clock |
| API client | constructor argument / factory per thread | `unittest.mock.Mock` or a small fake class |
| Stop signal | `threading.Event` argument | set it from the test |
| Randomness (jitter) | `rng: random.Random` | `random.Random(0)` |

Keep the per-item logic a plain function (`evaluate(item) -> Result`) tested without threads; test the
concurrency shell (windowing, limits, shutdown) separately with trivial work functions.

## 2. An inline executor for logic tests

An `Executor` that runs each task synchronously in `submit` makes orchestration code deterministic: same order
every run, exceptions on the right future, no threads to leak. It cannot find concurrency bugs; pair it with
real-pool tests.

```python
import unittest
from concurrent.futures import Executor, Future, as_completed


class InlineExecutor(Executor):
    """Runs tasks immediately in the caller's thread; returns completed futures."""

    def submit(self, fn, /, *args, **kwargs):
        fut: Future = Future()
        if fut.set_running_or_notify_cancel():
            try:
                fut.set_result(fn(*args, **kwargs))
            except BaseException as exc:
                fut.set_exception(exc)
        return fut


def collect(executor: Executor, fn, items):
    """Code under test: results and errors per item."""
    futures = {executor.submit(fn, x): x for x in items}
    ok, failed = {}, {}
    for fut in as_completed(futures):
        try:
            ok[futures[fut]] = fut.result()
        except Exception as exc:
            failed[futures[fut]] = type(exc).__name__
    return ok, failed


def parse(x: str) -> int:
    return int(x)


class CollectTests(unittest.TestCase):
    def test_errors_are_kept(self):
        ok, failed = collect(InlineExecutor(), parse, ["1", "x", "3"])
        self.assertEqual(ok, {"1": 1, "3": 3})
        self.assertEqual(failed, {"x": "ValueError"})

    def test_map_works_too(self):
        self.assertEqual(list(InlineExecutor().map(parse, ["4", "5"])), [4, 5])


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 2
```

`Executor.map` is implemented on top of `submit`, so the inline executor supports it for free.

## 3. Forcing interleavings with Barrier and Event

`time.sleep` in tests makes them slow and still flaky. Use synchronization to put threads exactly where you
want them.

```python
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor


class ConcurrencyTests(unittest.TestCase):
    def test_tasks_really_overlap(self):
        """Fails (BrokenBarrierError) if the pool runs tasks one at a time."""
        barrier = threading.Barrier(4, timeout=5)
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(barrier.wait) for _ in range(4)]
            for f in futures:
                f.result(timeout=5)

    def test_second_writer_waits_for_lock(self):
        lock, inside, release = threading.Lock(), threading.Event(), threading.Event()
        order = []

        def first():
            with lock:
                inside.set()
                release.wait(5)
                order.append("first")

        def second():
            with lock:
                order.append("second")

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(first)
            self.assertTrue(inside.wait(5))            # first holds the lock now
            f2 = ex.submit(second)
            self.assertFalse(f2.done())                # blocked on the lock
            release.set()
            f1.result(timeout=5)
            f2.result(timeout=5)
        self.assertEqual(order, ["first", "second"])


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 2
```

Every wait has a timeout so a bug fails the test instead of hanging it. The `assertFalse(f2.done())` check is a
point-in-time observation; it can only be wrong in the "passes by accident" direction, never flake red.

## 4. Fake clocks for rate limiters and retries

Inject `clock` and `sleep`; the fake `sleep` advances the fake clock instantly. A one-minute RPM test then runs
in microseconds and asserts exact numbers.

```python
import threading
import unittest


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps = []
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.now += seconds


class TokenBucket:
    def __init__(self, rate_per_minute, burst, clock, sleep):
        self.rate, self.capacity, self.tokens = rate_per_minute / 60, float(burst), float(burst)
        self.clock, self.sleep = clock, sleep
        self.updated = clock()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = self.clock()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            self.sleep(wait)


def retry(fn, attempts, base, sleep):
    for attempt in range(attempts):
        try:
            return fn()
        except ConnectionError:
            if attempt == attempts - 1:
                raise
            sleep(base * 2 ** attempt)                   # jitter omitted: inject an rng to test it


class TimeTests(unittest.TestCase):
    def test_bucket_allows_burst_then_rate(self):
        clock = FakeClock()
        bucket = TokenBucket(rate_per_minute=60, burst=5, clock=clock, sleep=clock.sleep)
        for _ in range(65):
            bucket.acquire()
        self.assertAlmostEqual(clock.now, 60.0)        # 5 immediate, then 1/s for 60 more

    def test_retry_backoff_schedule(self):
        clock = FakeClock()
        calls = iter([ConnectionError(), ConnectionError(), "ok"])

        def flaky():
            item = next(calls)
            if isinstance(item, Exception):
                raise item
            return item

        self.assertEqual(retry(flaky, attempts=5, base=0.5, sleep=clock.sleep), "ok")
        self.assertEqual(clock.sleeps, [0.5, 1.0])


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 2
```

For jittered backoff inject `rng=random.Random(0)` and assert the bounds (`0 <= delay <= cap`) rather than
exact values.

## 5. Mocking clients from many threads

`unittest.mock.Mock` records calls thread-safely enough for assertions (`call_count`, `call_args_list`), but a
`side_effect` **iterator** shared by threads hands out items in an unpredictable order. Make the fake decide by
argument (deterministic per item), not by call order:

```python
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock


class RateLimited(Exception):
    pass


def score_all(client, prompts, workers=8):
    """Code under test: one retry on RateLimited."""
    def one(p):
        try:
            return client.complete(p)
        except RateLimited:
            return client.complete(p)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return dict(zip(prompts, ex.map(one, prompts)))


class ClientTests(unittest.TestCase):
    def test_each_prompt_retried_once_on_429(self):
        seen = {}
        lock = threading.Lock()

        def fake_complete(prompt):
            with lock:
                seen[prompt] = seen.get(prompt, 0) + 1
                first = seen[prompt] == 1
            if prompt.endswith("7") and first:
                raise RateLimited(prompt)
            return prompt.upper()

        client = mock.Mock()
        client.complete.side_effect = fake_complete
        prompts = [f"p{i}" for i in range(20)]
        out = score_all(client, prompts)
        self.assertEqual(out["p17"], "P17")
        self.assertEqual(client.complete.call_count, 22)   # 20 + retries for p7 and p17
        self.assertEqual(seen["p7"], 2)


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 1
```

`mock.patch("mymodule.requests.Session")` patches where the name is **used**. For per-thread clients created in
an `initializer`, patch the factory and assert it was called once per worker thread
(`factory.call_count <= max_workers`).

## 6. Testing bounds, cancellation and Ctrl-C

```python
import itertools
import threading
import time
import unittest
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def window_run(fn, items, ex, max_in_flight):
    source = iter(items)
    pending = {ex.submit(fn, x) for x in itertools.islice(source, max_in_flight)}
    results = []
    while pending:
        done, pending = wait(pending, return_when=FIRST_COMPLETED)
        results += [f.result() for f in done]
        pending |= {ex.submit(fn, x) for x in itertools.islice(source, len(done))}
    return results


class BoundTests(unittest.TestCase):
    def test_never_more_than_window_pending(self):
        lock, live, peak = threading.Lock(), [0], [0]
        pulled = []

        def lazy():
            for i in range(200):
                pulled.append(i)
                with lock:                               # items pulled but not yet finished
                    live[0] += 1
                    peak[0] = max(peak[0], live[0])
                yield i

        def work(i):
            time.sleep(0.001)
            with lock:
                live[0] -= 1
            return i

        with ThreadPoolExecutor(max_workers=4) as ex:
            out = window_run(work, lazy(), ex, max_in_flight=8)
        self.assertEqual(sorted(out), list(range(200)))
        self.assertLessEqual(peak[0], 8)

    def test_cancel_futures_drops_queued_work(self):
        gate, ran = threading.Event(), []

        def task(i):
            gate.wait(5)
            ran.append(i)

        ex = ThreadPoolExecutor(max_workers=2)
        futures = [ex.submit(task, i) for i in range(50)]
        gate.set()
        ex.shutdown(wait=True, cancel_futures=True)
        cancelled = sum(f.cancelled() for f in futures)
        self.assertEqual(cancelled + len(ran), 50)
        self.assertGreater(cancelled, 0)

    def test_ctrl_c_path_sets_stop_and_cancels(self):
        stop = threading.Event()

        def task(i):
            stop.wait(5)
            return i

        ex = ThreadPoolExecutor(max_workers=2)
        futures = [ex.submit(task, i) for i in range(20)]
        try:
            raise KeyboardInterrupt                      # what the main thread's wait() would raise
        except KeyboardInterrupt:
            stop.set()
            ex.shutdown(wait=True, cancel_futures=True)
        self.assertTrue(all(f.done() for f in futures))
        self.assertGreaterEqual(sum(f.cancelled() for f in futures), 18)


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 3
```

To test a real CLI's Ctrl-C handling end to end, run it as a subprocess, send `SIGINT` after it has started
(`proc.send_signal(signal.SIGINT)`), and assert exit code 130, the partial-results message and the elapsed
time; the `graceful-shutdown` recipe shows the in-process simulation with `_thread.interrupt_main`.

## 7. Testing context propagation

```python
import contextvars
import unittest
from concurrent.futures import ThreadPoolExecutor

request_id = contextvars.ContextVar("request_id", default="-")


class ContextExecutor(ThreadPoolExecutor):
    def submit(self, fn, /, *args, **kwargs):
        return super().submit(contextvars.copy_context().run, fn, *args, **kwargs)


class ContextTests(unittest.TestCase):
    def test_request_id_reaches_workers_and_does_not_leak(self):
        with ContextExecutor(max_workers=1) as ex:
            token = request_id.set("req-1")
            try:
                self.assertEqual(ex.submit(request_id.get).result(timeout=5), "req-1")
                ex.submit(request_id.set, "inner").result(timeout=5)
                self.assertEqual(ex.submit(request_id.get).result(timeout=5), "req-1")
            finally:
                request_id.reset(token)
            self.assertEqual(list(ex.map(lambda _: request_id.get(), [1, 2])), ["-", "-"])


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 1
```

## 8. Detecting leaked threads

A test that leaves threads running pollutes every later test (and hides "forgot to shut down" bugs). Compare
`threading.enumerate()` before and after, allowing a short grace period for threads that are finishing.

```python
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor


class LeakCheckMixin:
    def setUp(self):
        self._threads_before = set(threading.enumerate())
        super().setUp()

    def tearDown(self):
        super().tearDown()
        deadline = time.monotonic() + 2
        while True:
            leaked = [t for t in threading.enumerate() if t not in self._threads_before and t.is_alive()]
            if not leaked or time.monotonic() > deadline:
                break
            time.sleep(0.01)
        if leaked:
            raise AssertionError(f"leaked threads: {sorted(t.name for t in leaked)}")


def leaky_job():
    ex = ThreadPoolExecutor(max_workers=2, thread_name_prefix="leaky")
    ex.submit(time.sleep, 0.01).result()
    return ex                                            # never shut down


class Jobs(LeakCheckMixin, unittest.TestCase):
    def test_clean_job(self):
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="clean") as ex:
            ex.submit(time.sleep, 0.01).result()


class LeakyJobs(LeakCheckMixin, unittest.TestCase):
    def test_leaky_job_is_caught(self):
        self.ex = leaky_job()

    def tearDown(self):
        with self.assertRaises(AssertionError):
            super().tearDown()
        self.ex.shutdown()


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 2
```

With pytest, put the same logic in an autouse fixture in `conftest.py`:

```python
import threading
import time

import pytest


@pytest.fixture(autouse=True)
def no_leaked_threads():
    before = set(threading.enumerate())
    yield
    deadline = time.monotonic() + 2
    leaked = []
    while time.monotonic() < deadline:
        leaked = [t for t in threading.enumerate() if t not in before and t.is_alive()]
        if not leaked:
            return
        time.sleep(0.01)
    pytest.fail(f"leaked threads: {sorted(t.name for t in leaked)}")
```

`thread_name_prefix` on every executor makes the failure message point at the culprit.

## 9. Timeouts so a deadlock fails instead of hanging

- Every `result()`, `wait()`, `join()`, `Event.wait()` and `Barrier` in tests gets a timeout.
- A global watchdog: `faulthandler.dump_traceback_later(120, exit=True)` in `conftest.py` (or at the top of a
  unittest module) prints every thread's stack and exits if the suite hangs; cancel it with
  `faulthandler.cancel_dump_traceback_later()`.
- pytest: the `pytest-timeout` plugin (`--timeout=60`; `--timeout-method=thread` dumps all threads).
- CI: wrap the test command in `timeout 600` as the last line of defence.
- When a test does hang, the dump tells you which threads wait on what: read it with the guide in
  [debugging-thread-pools.md](debugging-thread-pools.md#4-seeing-what-every-thread-is-doing).

## 10. Stress tests for races

Races hide on the GIL build: CPython switches threads only at specific points (every 5 ms by default, and
only where the interpreter checks for a switch request, such as calls and loop back-edges), so a bare
`n = self.n; self.n = n + 1` almost never interleaves in a test. In production the read and the write are
separated by real work (a log call, I/O, a dict lookup through a function), or the build is free-threaded, and
updates get lost. To shake races out:
- Put a switch point inside the suspect region in the test double (`time.sleep(0)` releases the GIL), the
  way real code with I/O between read and write behaves.
- Lower the switch interval in the test: `sys.setswitchinterval(1e-6)` (restore it afterwards).
- Repeat the concurrent section many times with fresh state.
- Run the suite on a free-threaded build (`python3.14t`) in CI where possible: true parallelism exposes races
  that the GIL hides.

```python
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor


class Counter:
    def __init__(self, locked: bool) -> None:
        self.n = 0
        self.locked = locked
        self.lock = threading.Lock()

    def add(self) -> None:
        if self.locked:
            with self.lock:
                self.n += 1
        else:
            n = self.n                                  # explicit read-modify-write
            time.sleep(0)                               # stands in for real work between read and write
            self.n = n + 1


def hammer(counter: Counter, threads: int = 8, per_thread: int = 500) -> int:
    def run():
        for _ in range(per_thread):
            counter.add()
    with ThreadPoolExecutor(max_workers=threads) as ex:
        for f in [ex.submit(run) for _ in range(threads)]:
            f.result(timeout=30)
    return counter.n


class RaceTests(unittest.TestCase):
    def setUp(self):
        self.old = sys.getswitchinterval()
        sys.setswitchinterval(1e-6)

    def tearDown(self):
        sys.setswitchinterval(self.old)

    def test_locked_counter_is_exact(self):
        for _ in range(5):
            self.assertEqual(hammer(Counter(locked=True)), 4000)

    def test_unlocked_counter_loses_updates(self):
        lost = any(hammer(Counter(locked=False)) < 4000 for _ in range(5))
        self.assertTrue(lost)                            # demonstrates the race the linter's TPE006 flags


result = unittest.main(argv=["tests"], exit=False, verbosity=0).result
print(result.wasSuccessful(), result.testsRun)          # True 2
```

A test that asserts a race *happens* is inherently probabilistic; keep such demonstrations out of the main
suite (or mark them) and keep the assertion that the **locked** version is exact.

## 11. CI checklist

- [ ] `python scripts/executor_tool.py check src/ --strict` in CI (fails the build on findings)
- [ ] Unit tests of per-item logic without threads; orchestration tests with an inline executor
- [ ] Real-pool tests using barriers/events, never sleeps for ordering
- [ ] Fake clock for limiters, retries and deadlines
- [ ] Leak-check fixture; every executor named with `thread_name_prefix`
- [ ] Timeouts on every wait, plus a suite-level watchdog
- [ ] Stress job with a tiny switch interval, and a free-threaded build if the project supports it
- [ ] An end-to-end Ctrl-C test (subprocess + SIGINT) for CLIs that run long jobs
