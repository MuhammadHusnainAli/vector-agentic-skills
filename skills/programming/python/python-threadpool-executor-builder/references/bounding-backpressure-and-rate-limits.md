# Sizing, Bounding, Backpressure and Rate Limits

How many threads, how much queued work, and how fast: the three numbers that decide whether an I/O fan-out
is fast, cheap on memory and polite to the provider. All code is stdlib only and runnable.

## Contents

1. [Little's law: sizing from latency](#1-littles-law-sizing-from-latency)
2. [The real ceilings](#2-the-real-ceilings)
3. [Why submit loops and map blow up memory](#3-why-submit-loops-and-map-blow-up-memory)
4. [Sliding window, unordered](#4-sliding-window-unordered)
5. [Sliding window, ordered](#5-sliding-window-ordered)
6. [Semaphore-bounded executor](#6-semaphore-bounded-executor)
7. [Bounded queue with fixed worker threads](#7-bounded-queue-with-fixed-worker-threads)
8. [map(buffersize=) on 3.14](#8-mapbuffersize-on-314)
9. [Token bucket for RPM](#9-token-bucket-for-rpm)
10. [Token budgets (TPM) and combined limits](#10-token-budgets-tpm-and-combined-limits)
11. [Retry-After, per-host limits and adaptive concurrency](#11-retry-after-per-host-limits-and-adaptive-concurrency)
12. [Connection pools must match the worker count](#12-connection-pools-must-match-the-worker-count)
13. [Choosing a technique](#13-choosing-a-technique)

## 1. Little's law: sizing from latency

For any stable system: **L = lambda x W** — items in flight = arrival rate x time each spends inside.

For a thread pool calling an API: `workers_needed = target_requests_per_second x latency_seconds`.

| Workload | Target | Latency | Workers |
|----------|--------|---------|---------|
| Eval harness, provider limit 500 RPM | 8.3 req/s | p95 4 s (long completions) | ~33, round to 32-40 |
| Embedding API, 3,000 RPM, batches of 64 texts | 50 req/s | 0.4 s | 20 |
| Scraping 20 hosts, 2 req/s per host politeness | 40 req/s | 0.8 s | 32 (plus per-host caps) |
| Vector DB upserts, DB sustains 200 batch writes/s | 200/s | 0.05 s | 10 |
| S3 uploads of 8 MB chunks, 1 Gbit/s link | ~15 chunks/s | 0.6 s | ~9-10: bandwidth-bound, more threads only queue |

Use the **p95** latency (or p90), not the mean: with the mean you are short of workers exactly when latency
spikes, which is when you need them. Add ~20% headroom. If the result exceeds ~64-128, threads get expensive;
switch to asyncio (see [python-asyncio-pattern-advisor](../../python-asyncio-pattern-advisor/SKILL.md)).

```python
import math


def workers_for(rate_per_s: float, p95_latency_s: float, headroom: float = 1.2, cap: int = 64) -> int:
    return max(1, min(cap, math.ceil(rate_per_s * p95_latency_s * headroom)))


print(workers_for(500 / 60, 4.0))      # 40
print(workers_for(3000 / 60, 0.4))     # 24
print(workers_for(200, 0.05))          # 12
```

Then **measure**: log achieved requests/s and latency; if achieved rate < limit and the limiter is idle,
raise workers; if the limiter queue is long, workers are already enough.

## 2. The real ceilings

Workers are only one of several limits; the lowest one wins.

| Ceiling | How you see it | Fix |
|---------|----------------|-----|
| Provider RPM/TPM | HTTP 429, `retry-after` headers, `x-ratelimit-remaining-*` | Token bucket below the limit; never more workers than needed to hit it |
| Provider concurrent-request cap | 429 "too many concurrent requests" with low RPM | A `BoundedSemaphore(concurrency)` around the call |
| Connection pool | `Connection pool is full, discarding connection` (urllib3), pool timeouts (httpx `PoolTimeout`) | Pool size >= workers (section 12) |
| Server / DB capacity | Latency grows with workers, throughput flat | Fewer workers; batch bigger |
| Bandwidth | Throughput flat at link speed | Fewer workers; compress |
| Local CPU (JSON parsing, tokenizing) | One core at 100%, GIL contention | Move parsing to processes; see the GIL skill |
| Memory | RSS grows with queued items | Bound in-flight items (sections 4-8) |

## 3. Why submit loops and map blow up memory

`ThreadPoolExecutor` keeps an unbounded `queue.SimpleQueue` of work items. `submit()` appends and returns.
Before 3.14 `Executor.map()` is implemented as `fs = [self.submit(fn, *args) for args in zip(*iterables)]`
followed by a generator over `fs`: the **entire input is submitted before the first result is yielded**.

```python
import tracemalloc
from concurrent.futures import ThreadPoolExecutor


def lines(n: int):
    for i in range(n):
        yield "x" * 200 + str(i)                     # stands in for a JSONL record


tracemalloc.start()
with ThreadPoolExecutor(max_workers=4) as ex:
    it = ex.map(len, lines(50_000))                  # noqa: TPE004 - all 50,000 submitted right here
    peak_after_map = tracemalloc.get_traced_memory()[1]
    total = sum(it)
tracemalloc.stop()
print(total, peak_after_map > 10_000_000)            # 10238890 True  (>10 MB for 50k small items)
```

Each pending item holds a `Future`, a work item, its arguments and eventually its result. With 10 M prompts
that is gigabytes, minutes of submitting before any progress, and a Ctrl-C that has to cancel 10 M futures.
The linter flags this as TPE003 (submit loop) and TPE004 (map over a generator, file or huge range).

## 4. Sliding window, unordered

Keep at most `max_in_flight` futures; refill one slot per finished task. Results arrive in completion order.

```python
import itertools
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Iterable, Iterator, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def window_map(fn: Callable[[T], R], items: Iterable[T], ex: ThreadPoolExecutor,
               max_in_flight: int = 64) -> Iterator[Tuple[int, R]]:
    """Yield (index, result) as tasks finish; never more than max_in_flight pending."""
    source = enumerate(items)
    pending = {ex.submit(fn, item): i for i, item in itertools.islice(source, max_in_flight)}
    try:
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                yield pending.pop(fut), fut.result()
            for i, item in itertools.islice(source, len(done)):
                pending[ex.submit(fn, item)] = i
    finally:
        for fut in pending:
            fut.cancel()


with ThreadPoolExecutor(max_workers=8) as ex:
    out = dict(window_map(lambda s: s.upper(), (f"doc{i}" for i in range(1000)), ex, max_in_flight=16))
print(len(out), out[999])                            # 1000 DOC999
```

`scripts/executor_tool.py scaffold --recipe bounded-map` prints a typed, documented version with a timeout.
Choose `max_in_flight` around 2-4 x `max_workers`: enough queued work that no worker idles between tasks, small
enough to bound memory.

## 5. Sliding window, ordered

When results must come out in input order (writing a JSONL file aligned with the input), keep a deque and
always wait on the oldest future. A slow item stalls the window, so make the window larger than for the
unordered version.

```python
import collections
import itertools
import time
from concurrent.futures import ThreadPoolExecutor


def ordered_window_map(fn, items, ex, max_in_flight=32):
    source = iter(items)
    window = collections.deque(ex.submit(fn, x) for x in itertools.islice(source, max_in_flight))
    try:
        while window:
            result = window.popleft().result()      # oldest first: preserves order
            for x in itertools.islice(source, 1):
                window.append(ex.submit(fn, x))
            yield result
    finally:
        for fut in window:
            fut.cancel()


def slow_even(i: int) -> int:
    time.sleep(0.01 if i % 2 == 0 else 0.001)
    return i * i


with ThreadPoolExecutor(max_workers=4) as ex:
    print(list(ordered_window_map(slow_even, range(10), ex, max_in_flight=4)))
# [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

This is what 3.14's `map(buffersize=)` does internally.

## 6. Semaphore-bounded executor

When code already calls `submit` from many places, wrap the executor so `submit` blocks once `bound` tasks are
queued or running. The slot is released in a done-callback, which also runs for failed and cancelled futures.

```python
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional


class BoundedExecutor:
    """submit() blocks while `bound` tasks are pending (queued + running)."""

    def __init__(self, bound: int, max_workers: int, **kwargs: Any) -> None:
        self._slots = threading.BoundedSemaphore(bound)
        self._ex = ThreadPoolExecutor(max_workers=max_workers, **kwargs)

    def submit(self, fn: Callable[..., Any], *args: Any, timeout: Optional[float] = None, **kwargs: Any) -> Future:
        if not self._slots.acquire(timeout=timeout):
            raise TimeoutError("no free slot")
        try:
            fut = self._ex.submit(fn, *args, **kwargs)
        except BaseException:
            self._slots.release()
            raise
        fut.add_done_callback(lambda _f: self._slots.release())
        return fut

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        self._ex.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __enter__(self) -> "BoundedExecutor":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.shutdown()


peak = 0
lock = threading.Lock()
active = 0


def task(i: int) -> int:
    global peak, active
    with lock:
        active += 1
        peak = max(peak, active)
    with lock:
        active -= 1
    return i


with BoundedExecutor(bound=8, max_workers=4) as bx:
    futures = [bx.submit(task, i) for i in range(200)]
print(sum(f.result() for f in futures), peak <= 4)   # 19900 True
```

Note the futures list still grows with the input here; the semaphore bounds *queued work*, not your own
bookkeeping. Combine with a window (section 4) or process results in a done-callback when the input is huge.

## 7. Bounded queue with fixed worker threads

For long-running pipelines (crawler -> parser -> writer) a `queue.Queue(maxsize=N)` between stages gives
natural backpressure: `put` blocks when the stage behind is slow. Workers stop on a sentinel.

```python
import queue
import threading

STOP = object()


def stage(inbox: queue.Queue, outbox: queue.Queue, fn) -> None:
    while True:
        item = inbox.get()
        try:
            if item is STOP:
                return
            outbox.put(fn(item))
        finally:
            inbox.task_done()


urls: queue.Queue = queue.Queue(maxsize=32)          # producer blocks when parsers fall behind
pages: queue.Queue = queue.Queue(maxsize=32)
workers = [threading.Thread(target=stage, args=(urls, pages, str.upper), name=f"parse-{i}") for i in range(4)]
for t in workers:
    t.start()


def produce() -> None:
    for i in range(100):
        urls.put(f"https://site/{i}")
    for _ in workers:
        urls.put(STOP)                               # one sentinel per worker


producer = threading.Thread(target=produce, name="producer")
producer.start()
results = [pages.get() for _ in range(100)]          # consumer drains so parsers never block forever
producer.join()
for t in workers:
    t.join()
print(len(results), results[0].startswith("HTTPS://"))   # 100 True
```

Errors inside a stage must be caught and forwarded (put an error record on `outbox`), otherwise the thread
dies and the pipeline hangs waiting for items that never come. The futures-based window is usually simpler.

## 8. map(buffersize=) on 3.14

```python
import sys
from concurrent.futures import ThreadPoolExecutor


def records():
    for i in range(100_000):
        yield i


with ThreadPoolExecutor(max_workers=8) as ex:
    if sys.version_info >= (3, 14):
        total = sum(ex.map(abs, records(), buffersize=64))   # at most 64 submitted ahead
    else:
        total = sum(abs(r) for r in records())               # use a window on older versions
print(total)                                                 # 4999950000
```

Ordered output, lazy input, first exception stops iteration. Pick `buffersize` like `max_in_flight`.

## 9. Token bucket for RPM

A token bucket refills `rate` tokens per second up to `capacity` (the allowed burst). Every request takes one
token; when empty, callers sleep. Share one bucket across all threads; sleep **outside** the lock.

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor


class TokenBucket:
    def __init__(self, rate_per_minute: float, burst: int,
                 clock=time.monotonic, sleep=time.sleep) -> None:
        self.rate = rate_per_minute / 60.0
        self.capacity = float(burst)
        self.tokens = float(burst)
        self.clock, self.sleep = clock, sleep
        self.updated = clock()
        self.lock = threading.Lock()

    def acquire(self, n: float = 1.0) -> None:
        while True:
            with self.lock:
                now = self.clock()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                wait_s = (n - self.tokens) / self.rate
            self.sleep(wait_s)


bucket = TokenBucket(rate_per_minute=600, burst=3)    # 10/s
stamps = []


def call(i: int) -> None:
    bucket.acquire()
    stamps.append(time.monotonic())


t0 = time.monotonic()
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(call, range(13)))
print(f"{time.monotonic() - t0:.1f}s")               # 1.0s  (3 burst + 10 more at 10/s)
```

Injecting `clock` and `sleep` makes the bucket testable without real time (see
[testing-threaded-code.md](testing-threaded-code.md)). Set the rate ~10% under the published limit: other
processes and retries share it, and providers measure over windows you do not see. Retries must acquire
tokens too, or a 429 storm amplifies itself.

## 10. Token budgets (TPM) and combined limits

LLM providers limit tokens per minute as well as requests. Estimate tokens before the call
(`len(text) / 4` is a crude English heuristic; use the provider's tokenizer when it matters), acquire that
many from a TPM bucket, and reconcile with the usage the response reports if you need precision.

```python
import threading
import time


class Limits:
    """Acquire one request token and `tokens` TPM tokens atomically enough for a client-side limiter."""

    def __init__(self, rpm: float, tpm: float) -> None:
        self.rpm_rate, self.tpm_rate = rpm / 60, tpm / 60
        self.req, self.tok = rpm / 60, tpm / 60          # start with one second of budget
        self.cap_req, self.cap_tok = rpm / 60, tpm / 60
        self.t = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: int) -> float:
        if tokens > self.cap_tok:
            raise ValueError("single request exceeds one second of TPM budget; raise the cap")
        waited = 0.0
        while True:
            with self.lock:
                now = time.monotonic()
                dt, self.t = now - self.t, now
                self.req = min(self.cap_req, self.req + dt * self.rpm_rate)
                self.tok = min(self.cap_tok, self.tok + dt * self.tpm_rate)
                if self.req >= 1 and self.tok >= tokens:
                    self.req -= 1
                    self.tok -= tokens
                    return waited
                need = max((1 - self.req) / self.rpm_rate, (tokens - self.tok) / self.tpm_rate)
            time.sleep(need)
            waited += need


limits = Limits(rpm=6000, tpm=60_000)                    # 100 req/s, 1000 tok/s
waits = [limits.acquire(tokens=400) for _ in range(5)]
print(round(sum(waits), 1))                              # 1.0  (TPM is the binding limit here)
```

## 11. Retry-After, per-host limits and adaptive concurrency

- **Retry-After is global.** A 429 says the *account* is over the limit. Pause the shared bucket (drain it so
  `acquire` waits `retry_after` seconds) instead of only sleeping in the thread that got the 429; otherwise the
  other 31 threads keep hammering. The `rate-limited` recipe has `TokenBucket.pause(seconds)`.
- **Per-host politeness** when scraping: a `dict[host, BoundedSemaphore]` caps concurrency per domain while the
  pool serves many domains.

```python
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

_host_slots = defaultdict(lambda: threading.BoundedSemaphore(2))
_host_lock = threading.Lock()
_active = defaultdict(int)
_peak = defaultdict(int)


def slots_for(url: str) -> threading.BoundedSemaphore:
    with _host_lock:                                    # defaultdict insert is check-then-set
        return _host_slots[urlsplit(url).netloc]


def fetch(url: str) -> str:
    host = urlsplit(url).netloc
    with slots_for(url):                                # at most 2 concurrent requests per host
        with _host_lock:
            _active[host] += 1
            _peak[host] = max(_peak[host], _active[host])
        try:
            return url                                  # requests.get(url, timeout=...) here
        finally:
            with _host_lock:
                _active[host] -= 1


urls = [f"https://site{i % 3}.example/p{i}" for i in range(60)]
with ThreadPoolExecutor(max_workers=12) as ex:
    list(ex.map(fetch, urls))
print(max(_peak.values()) <= 2)                         # True
```

- **Adaptive concurrency (AIMD)**: start low, add one permit per N successes, halve on a 429/timeout. Useful
  when the real limit is unknown or shared; implement with a `threading.Condition` guarding a permit count.
  Most jobs are fine with a fixed bucket set under the documented limit.

## 12. Connection pools must match the worker count

| Client | Default pool | Set it to >= workers |
|--------|--------------|----------------------|
| `requests.Session` | `HTTPAdapter(pool_connections=10, pool_maxsize=10)` per mounted prefix | `s.mount("https://", HTTPAdapter(pool_maxsize=workers))` |
| `urllib3.PoolManager` | `maxsize=1` per host | `PoolManager(maxsize=workers, block=True)` |
| `httpx.Client` | `Limits(max_connections=100, max_keepalive_connections=20)` | `httpx.Client(limits=httpx.Limits(max_connections=workers, max_keepalive_connections=workers))` |
| boto3 client | `Config(max_pool_connections=10)` | `boto3.client("s3", config=Config(max_pool_connections=workers))` |
| DB pools | driver-specific | pool size >= workers that use the DB |

When the pool is smaller than the number of threads, urllib3 logs `Connection pool is full, discarding
connection: <host>` and opens extra connections that are thrown away after use (a TLS handshake per request);
httpx waits for a free connection and may raise `PoolTimeout`.

## 13. Choosing a technique

| Situation | Technique |
|-----------|-----------|
| A list of a few thousand items, all results needed | `list(ex.map(fn, items))` or `as_completed` over all futures |
| Huge or lazy input, order irrelevant | Sliding window (section 4) |
| Huge input, ordered output | Ordered window (section 5) or `map(buffersize=)` on 3.14 |
| Many call sites already use `submit` | `BoundedExecutor` (section 6) |
| Multi-stage pipeline with different speeds | Bounded queues between stages (section 7) |
| Provider RPM/TPM | Token bucket shared by all threads (sections 9-10), plus a window |
| Provider concurrent-request cap | `BoundedSemaphore(cap)` around the call |
| Scraping many hosts | Pool + per-host semaphores + bucket per host if required |
