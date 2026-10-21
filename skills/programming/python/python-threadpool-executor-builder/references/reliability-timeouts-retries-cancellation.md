# Reliability: Timeouts, Retries, Cancellation, Progress and Shutdown

Thread pools fail in specific ways: a task that never returns, a provider that rate-limits, a dependency that
is down, a user who presses Ctrl-C, a job that silently drops 3% of its items. This file has a runnable
pattern for each. Exception design (custom hierarchies, `retryable` flags) is covered in
[python-exception-handling-designer](../../python-exception-handling-designer/SKILL.md).

## Contents

1. [What a timeout means for a thread](#1-what-a-timeout-means-for-a-thread)
2. [Layered timeouts and deadlines](#2-layered-timeouts-and-deadlines)
3. [Cooperative cancellation with threading.Event](#3-cooperative-cancellation-with-threadingevent)
4. [When you really need to kill work](#4-when-you-really-need-to-kill-work)
5. [Retries with backoff and jitter](#5-retries-with-backoff-and-jitter)
6. [Circuit breaker](#6-circuit-breaker)
7. [Progress reporting](#7-progress-reporting)
8. [Partial results and errors without losing exceptions](#8-partial-results-and-errors-without-losing-exceptions)
9. [Error budgets: abort when too much fails](#9-error-budgets-abort-when-too-much-fails)
10. [Structured shutdown on Ctrl-C and SIGTERM](#10-structured-shutdown-on-ctrl-c-and-sigterm)

## 1. What a timeout means for a thread

Python threads cannot be killed or interrupted from outside. `fut.result(timeout=5)` raises `TimeoutError`
in the **waiting** thread; the task keeps running, keeps its worker busy, and its result is discarded when it
eventually finishes. `fut.cancel()` only works while the task is still queued.

```python
import time
from concurrent.futures import ThreadPoolExecutor

finished = []


def slow_call() -> str:
    time.sleep(0.3)
    finished.append("slow")
    return "late answer"


with ThreadPoolExecutor(max_workers=1) as ex:
    fut = ex.submit(slow_call)
    try:
        fut.result(timeout=0.05)
    except TimeoutError:
        print("gave up waiting; cancel() ->", fut.cancel(), "running:", fut.running())
print("task still finished:", finished)
# gave up waiting; cancel() -> False running: True
# task still finished: ['slow']
```

Consequences:
- Abandoned tasks still consume workers, rate-limit tokens and money. Under sustained timeouts the pool fills
  with zombies and throughput collapses.
- The real timeout must live **inside** the blocking call: `requests.get(url, timeout=(3.05, 30))`,
  `httpx.Client(timeout=httpx.Timeout(30, connect=5))`, `openai.OpenAI(timeout=60, max_retries=0)`,
  boto3 `Config(connect_timeout=5, read_timeout=60)`, `sqlite3.connect(timeout=5)`, `socket.settimeout`.
- `requests` has **no default timeout**: a call without `timeout=` can block forever on a dead connection.

## 2. Layered timeouts and deadlines

| Layer | Mechanism | Purpose |
|-------|-----------|---------|
| Socket / client | `timeout=` on every call | Bounds each attempt; the only layer that frees the thread |
| Attempt budget | retries x per-attempt timeout + backoff | Bounds a task |
| Waiting for one task | `fut.result(timeout=...)` | Bounds the caller's wait (request handlers) |
| Batch / job deadline | `wait(fs, timeout=remaining)` / `as_completed(fs, timeout=...)` | Bounds the whole fan-out |

Pass an absolute deadline down instead of re-computing relative timeouts at each layer:

```python
import time
from concurrent.futures import ThreadPoolExecutor, wait


class Deadline:
    def __init__(self, seconds: float) -> None:
        self.at = time.monotonic() + seconds

    def remaining(self) -> float:
        return max(0.0, self.at - time.monotonic())

    def expired(self) -> bool:
        return self.remaining() == 0.0


def tool_call(name: str, deadline: Deadline) -> str:
    time.sleep(0.5 if name == "slow_search" else 0.02)  # real: client.call(..., timeout=deadline.remaining())
    return name


deadline = Deadline(0.2)
with ThreadPoolExecutor(max_workers=4) as ex:
    fs = {ex.submit(tool_call, n, deadline): n for n in ("calc", "sql", "slow_search")}
    done, not_done = wait(fs, timeout=deadline.remaining())
    print(sorted(fs[f] for f in done), [fs[f] for f in not_done])
# ['calc', 'sql'] ['slow_search']
```

In an agent step, tools that missed the deadline become a "timed out" tool result for the model rather than
an exception that kills the step.

## 3. Cooperative cancellation with threading.Event

Long tasks (paginating an API, uploading many parts, streaming a completion) should check a shared
`threading.Event` between steps and sleep with `event.wait(delay)` so a stop request interrupts the sleep.

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor


class Stopped(Exception):
    pass


def paginate(source: str, stop: threading.Event) -> int:
    pages = 0
    while pages < 100:
        if stop.is_set():
            raise Stopped(f"{source}: stopped after {pages} pages")
        time.sleep(0.01)                                 # fetch one page (with a client timeout)
        pages += 1
        if stop.wait(0.0):                               # back-off sleeps: stop.wait(delay), never time.sleep
            raise Stopped(f"{source}: stopped after {pages} pages")
    return pages


stop = threading.Event()
with ThreadPoolExecutor(max_workers=2) as ex:
    futs = [ex.submit(paginate, s, stop) for s in ("crm", "wiki")]
    time.sleep(0.1)
    stop.set()
    outcomes = []
    for f in futs:
        try:
            outcomes.append(f.result())
        except Stopped as exc:
            outcomes.append(str(exc).split(":")[0])
print(outcomes)                                          # ['crm', 'wiki']
```

Pass the event explicitly (as an argument or via a small `JobContext` object), not as a global, so tests can
control it. For streaming LLM responses, check the event between chunks and `close()` the stream.

## 4. When you really need to kill work

| Need | Option |
|------|--------|
| Hard limit on arbitrary code (untrusted eval code, a C call that ignores timeouts) | Run it in a subprocess (`subprocess.run(..., timeout=)` or a `multiprocessing.Process` you can `kill()`) |
| A stuck HTTP call | Set connect/read timeouts; for streaming, a total-time watchdog that closes the response from another thread |
| A thread stuck forever in a library | Nothing safe in-process. Make it a daemon only if losing its work is acceptable, and fix the timeout |

`signal.alarm` / `signal.setitimer` only interrupt the **main** thread, so they cannot time out pool tasks.
`ctypes.pythonapi.PyThreadState_SetAsyncExc` injects an exception at the next bytecode boundary, never inside
a blocking C call, and can corrupt state held by the interrupted code: do not use it.

## 5. Retries with backoff and jitter

Rules:
1. Retry only transient failures: 429, 408, 5xx/overloaded, connection resets, read timeouts. Never 400, 401,
   403, 404, context-length or content-policy errors.
2. Exponential backoff with **full jitter**: `sleep = uniform(0, min(cap, base * 2**attempt))`. Without jitter,
   32 threads that hit a 429 together retry together.
3. Honour `Retry-After` (seconds or HTTP date) when present: `max(jittered, retry_after)`.
4. Cap attempts and total time; make retried writes idempotent (upsert by id, idempotency keys).
5. Disable the SDK's own retries (`max_retries=0`) if you retry yourself, or you multiply attempts.
6. Every attempt goes through the rate limiter.

```python
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Tuple, Type, TypeVar

R = TypeVar("R")


class TransientError(Exception):
    def __init__(self, msg: str, retry_after: Optional[float] = None) -> None:
        super().__init__(msg)
        self.retry_after = retry_after


def retry(fn: Callable[[], R], *, attempts: int = 5, base: float = 0.05, cap: float = 2.0,
          retry_on: Tuple[Type[BaseException], ...] = (TransientError, TimeoutError, ConnectionError),
          stop: Optional[threading.Event] = None) -> R:
    for attempt in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            if attempt == attempts - 1:
                raise
            delay = random.uniform(0, min(cap, base * 2 ** attempt))
            delay = max(delay, getattr(exc, "retry_after", None) or 0.0)
            if stop is not None and stop.wait(delay):
                raise
            if stop is None:
                time.sleep(delay)
    raise AssertionError("unreachable")


calls = {"n": 0}
lock = threading.Lock()


def flaky() -> str:
    with lock:
        calls["n"] += 1
        n = calls["n"]
    if n < 3:
        raise TransientError("429", retry_after=0.01)
    return "ok"


with ThreadPoolExecutor(max_workers=1) as ex:
    print(ex.submit(retry, flaky).result(), calls["n"])  # ok 3
```

Retry **inside** the task (as above) rather than resubmitting from the caller: the worker keeps its context,
the caller's bookkeeping stays simple, and the attempt count is local. The `retrying` recipe adds an
`on_retry` hook for metrics.

## 6. Circuit breaker

When a dependency is down, 32 threads each burning 5 attempts with backoff is wasted time and quota. A
breaker opens after N consecutive failures, fails fast for a cool-down, then lets one trial call through.

```python
import threading
import time


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failures: int = 5, reset_after: float = 30.0) -> None:
        self.failures, self.reset_after = failures, reset_after
        self._count = 0
        self._opened_at: float = 0.0
        self._trial = False
        self._lock = threading.Lock()

    def call(self, fn, *args, **kwargs):
        with self._lock:
            if self._count >= self.failures:
                if time.monotonic() - self._opened_at < self.reset_after or self._trial:
                    raise CircuitOpen("dependency unavailable; failing fast")
                self._trial = True                       # half-open: exactly one trial call
        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._count += 1
                self._trial = False
                if self._count >= self.failures:
                    self._opened_at = time.monotonic()
            raise
        with self._lock:
            self._count, self._trial = 0, False
        return result


breaker = CircuitBreaker(failures=3, reset_after=0.1)


def down() -> None:
    raise ConnectionError("vector db unreachable")


outcomes = []
for _ in range(5):
    try:
        breaker.call(down)
    except (ConnectionError, CircuitOpen) as exc:
        outcomes.append(type(exc).__name__)
time.sleep(0.12)
try:
    breaker.call(lambda: "recovered")
    outcomes.append("closed")
except CircuitOpen:
    outcomes.append("still open")
print(outcomes)
# ['ConnectionError', 'ConnectionError', 'ConnectionError', 'CircuitOpen', 'CircuitOpen', 'closed']
```

Put the breaker outside the retry loop (a retry should not retry `CircuitOpen`), one breaker per dependency.

## 7. Progress reporting

`as_completed` gives a natural progress loop. Use tqdm when installed, a periodic log line otherwise (CI logs
and containers do not render carriage returns well).

```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def grade(i: int) -> bool:
    time.sleep(0.002)
    return i % 9 != 0


items = list(range(200))
ok = failed = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(grade, i) for i in items]
    bar = tqdm(total=len(futures), unit="item") if tqdm else None
    for n, fut in enumerate(as_completed(futures), start=1):
        if fut.result():
            ok += 1
        else:
            failed += 1
        if bar:
            bar.update(1)
            bar.set_postfix(ok=ok, failed=failed)
        elif n % 100 == 0:
            print(f"{n}/{len(futures)} ok={ok} failed={failed}", flush=True)
    if bar:
        bar.close()
# 100/200 ok=... failed=...   (counts depend on completion order)
# 200/200 ok=177 failed=23
```

tqdm updates from the consuming thread (as here) are safe; updating one bar from many worker threads works
(tqdm uses a lock) but costs contention, so prefer the consumer loop. Progress callbacks via
`add_done_callback` run in worker threads: guard shared counters with a lock.

## 8. Partial results and errors without losing exceptions

Collect a record per item with either a value or an error; decide at the end what failure means.

```python
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional


@dataclass
class Outcome:
    key: str
    value: Optional[int] = None
    error: Optional[BaseException] = None


def parse(doc: str) -> int:
    if doc.endswith(".bad"):
        raise ValueError(f"cannot parse {doc}")
    return len(doc)


docs = ["a.pdf", "b.bad", "c.pdf", "d.bad"]
outcomes = []
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = {ex.submit(parse, d): d for d in docs}
    for fut in as_completed(futures):
        try:
            outcomes.append(Outcome(futures[fut], value=fut.result()))
        except Exception as exc:
            outcomes.append(Outcome(futures[fut], error=exc))

errors = [o.error for o in outcomes if o.error]
print(sum(o.error is None for o in outcomes), "ok;", len(errors), "failed")   # 2 ok; 2 failed
if errors and sys.version_info >= (3, 11):
    try:
        raise ExceptionGroup("2 documents failed", errors)    # one raise carries every traceback
    except ExceptionGroup as group:                           # callers can also use except* (3.11)
        print(len(group.exceptions), "errors grouped")        # 2 errors grouped
```

- Log each failure **once** with `exc_info` (`log.warning("...", exc_info=exc)` keeps the worker traceback).
- Write successes as they arrive (JSONL), so a crash or Ctrl-C keeps finished work; record failures to a
  separate file for a re-run.
- `ExceptionGroup` (3.11) is a clean way to raise everything at the end of a batch; callers can split it with
  `except* ValueError:`. On 3.9/3.10 raise a custom aggregate exception that carries the list.

## 9. Error budgets: abort when too much fails

If 40% of calls fail, something systemic is wrong (bad key, wrong model name, outage). Stop early instead of
burning the whole dataset:

```python
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def call(i: int) -> int:
    time.sleep(0.002)
    if i >= 20:
        raise PermissionError("401 invalid API key")        # systemic failure from item 20 on
    return i


stop = threading.Event()
ok, failed, max_fail_ratio, min_samples = 0, 0, 0.2, 20
with ThreadPoolExecutor(max_workers=4) as ex:
    pending = {ex.submit(call, i) for i in range(1000)}
    while pending and not stop.is_set():
        done, pending = wait(pending, return_when=FIRST_COMPLETED)
        for f in done:
            if f.exception() is None:
                ok += 1
            else:
                failed += 1
        total = ok + failed
        if total >= min_samples and failed / total > max_fail_ratio:
            stop.set()
            ex.shutdown(wait=True, cancel_futures=True)
print(f"aborted={stop.is_set()} ok={ok} failed<100={failed < 100}")
# aborted=True ok=20 failed<100=True
```

## 10. Structured shutdown on Ctrl-C and SIGTERM

What goes wrong by default: the main thread sits in `fut.result()` or in the `with` block's exit, Ctrl-C
raises `KeyboardInterrupt`, the `with` exit calls `shutdown(wait=True)`, and every queued task runs anyway.
The process "ignores" Ctrl-C for minutes and keeps spending API quota.

The fix, in order:
1. Wait in short slices: `wait(pending, timeout=0.25, return_when=FIRST_COMPLETED)` (on Linux a blocking
   `result()` is interruptible too, but slices also make the loop responsive to a stop flag).
2. On `KeyboardInterrupt`: `stop.set()` so running tasks exit at their next check.
3. `ex.shutdown(wait=True, cancel_futures=True)` (3.9+): queued tasks are cancelled, running ones finish.
4. Record what completed; write partial output; exit with status 130 (128 + SIGINT).
5. Containers send SIGTERM: convert it to the same path with a signal handler that raises in the main thread.

```python
import signal
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


class Shutdown(Exception):
    pass


def on_sigterm(signum, frame):                            # runs in the main thread
    raise Shutdown(f"signal {signum}")


signal.signal(signal.SIGTERM, on_sigterm)
stop = threading.Event()


def work(i: int, stop: threading.Event) -> int:
    for _ in range(4):
        if stop.is_set():
            return -1
        time.sleep(0.01)
    return i


completed = []
try:
    with ThreadPoolExecutor(max_workers=4) as ex:
        pending = {ex.submit(work, i, stop) for i in range(200)}
        threading.Timer(0.2, signal.raise_signal, args=(signal.SIGTERM,)).start()   # demo: SIGTERM later
        try:
            while pending:
                done, pending = wait(pending, timeout=0.25, return_when=FIRST_COMPLETED)
                completed += [f.result() for f in done]
        except (KeyboardInterrupt, Shutdown):
            stop.set()
            ex.shutdown(wait=True, cancel_futures=True)
            raise
except (KeyboardInterrupt, Shutdown) as exc:
    print(f"stopped by {type(exc).__name__}: {len(completed) < 200} completed early, exit code 130")
# stopped by Shutdown: True completed early, exit code 130
```

`signal.raise_signal` from the timer thread delivers SIGTERM to the process; Python runs the handler in the
main thread at the next bytecode boundary, which the 0.25 s wait slices guarantee. In a real CLI end with
`sys.exit(130)`. The complete pattern with a report is `scripts/executor_tool.py scaffold --recipe
graceful-shutdown`. A second Ctrl-C during cleanup raises another `KeyboardInterrupt` out of `shutdown`; if
you want "press twice to force quit", catch it there and call `os._exit(130)` (no cleanup runs).

Windows note: Ctrl-C cannot interrupt a thread blocked in some C calls; waiting in short slices is what makes
the pattern portable.
