# Concurrency Limits and Rate Limiting

Limiting how many operations run at once (concurrency) and how many start per unit of time (rate) are
different controls. LLM providers enforce rate (requests per minute, tokens per minute), your machine and the
upstream's connection pool enforce concurrency. Production code needs both, plus backpressure so that
producers slow down when consumers cannot keep up.

## Contents

- [Concurrency vs rate](#concurrency-vs-rate)
- [Semaphore patterns](#semaphore-patterns)
- [Sliding window over huge inputs](#sliding-window-over-huge-inputs)
- [Backpressure with bounded queues](#backpressure-with-bounded-queues)
- [Token bucket](#token-bucket)
- [RPM and TPM together](#rpm-and-tpm-together)
- [Estimating and reconciling tokens](#estimating-and-reconciling-tokens)
- [Reading provider rate-limit headers](#reading-provider-rate-limit-headers)
- [Adaptive concurrency (AIMD)](#adaptive-concurrency-aimd)
- [Per-provider limiter registry](#per-provider-limiter-registry)
- [Connection pools must match](#connection-pools-must-match)
- [Several processes or pods](#several-processes-or-pods)
- [Choosing numbers](#choosing-numbers)

## Concurrency vs rate

Little's law ties them together: **throughput = concurrency / latency**.

| Concurrency | Mean latency | Throughput | Per minute |
|-------------|--------------|------------|------------|
| 10 | 2.0 s | 5 req/s | 300 RPM |
| 50 | 2.0 s | 25 req/s | 1,500 RPM |
| 50 | 0.2 s (embeddings) | 250 req/s | 15,000 RPM |

So a Semaphore of 50 can exceed a 500 RPM limit by 30x when calls are fast. A concurrency limit protects
sockets, memory and the upstream's connection count; a rate limiter keeps you under quota. When latency drops
(cache hits, short prompts), only the rate limiter still holds the line.

## Semaphore patterns

```python
from __future__ import annotations

import asyncio
from collections import defaultdict


class KeyedLimiter:
    """Separate concurrency cap per key (host, provider, tenant)."""

    def __init__(self, default: int, overrides: dict[str, int] | None = None) -> None:
        overrides = overrides or {}
        self._sems: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(default))
        for key, n in overrides.items():
            self._sems[key] = asyncio.Semaphore(n)

    def __call__(self, key: str) -> asyncio.Semaphore:
        return self._sems[key]


async def main() -> None:
    limits = KeyedLimiter(default=4, overrides={"slow-site.example": 1})
    active: dict[str, int] = defaultdict(int)
    peak: dict[str, int] = defaultdict(int)

    async def fetch(host: str) -> None:
        async with limits(host):
            active[host] += 1
            peak[host] = max(peak[host], active[host])
            await asyncio.sleep(0.01)
            active[host] -= 1

    hosts = ["slow-site.example"] * 5 + ["fast.example"] * 10
    await asyncio.gather(*(fetch(h) for h in hosts))
    print(dict(peak))


asyncio.run(main())
# Output: {'slow-site.example': 1, 'fast.example': 4}
```

- Use `BoundedSemaphore` when releases are manual: an extra `release()` raises `ValueError` instead of silently
  raising the cap.
- Hold the semaphore only around the limited resource (the HTTP call), not around post-processing.
- On 3.9, asyncio primitives (Semaphore, Lock, Queue, Event) created outside a running loop bind to
  `get_event_loop()` at construction and then fail under `asyncio.run` with "attached to a different loop".
  Since 3.10 they bind lazily on first use. Create them inside the running loop to be safe on 3.9.

## Sliding window over huge inputs

`gather` + Semaphore still creates one task per item up front: 1M tasks is ~1 GB of RAM. A sliding window
keeps at most `limit` tasks alive and pulls items lazily from any iterable or async iterable:

```python
import asyncio
from typing import AsyncIterator, Awaitable, Callable, Iterable, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def bounded_map(fn: Callable[[T], Awaitable[R]], items: Iterable[T], limit: int) -> AsyncIterator[Tuple[T, R]]:
    """Yield (item, result) as they complete, with at most `limit` in flight. Errors propagate."""
    it = iter(items)
    pending: dict[asyncio.Task, T] = {}

    def refill() -> None:
        while len(pending) < limit:
            try:
                item = next(it)
            except StopIteration:
                return
            pending[asyncio.ensure_future(fn(item))] = item

    refill()
    try:
        while pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                item = pending.pop(task)
                yield item, task.result()
            refill()
    finally:
        for task in pending:                       # consumer stopped early or an error escaped
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


async def main() -> None:
    peak = active = 0

    async def embed(i: int) -> int:
        nonlocal peak, active
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.001)
        active -= 1
        return i * 2

    total = 0
    async for _, vec in bounded_map(embed, range(1000), limit=8):
        total += vec
    print(total, "peak", peak)


asyncio.run(main())
# Output: 999000 peak 8
```

## Backpressure with bounded queues

Backpressure means the slow stage pushes back on the fast stage. With `asyncio.Queue(maxsize=n)`,
`await queue.put(x)` suspends the producer while the queue is full. Without `maxsize` (the default, 0 =
unbounded) a fast reader of a 50 GB corpus fills RAM while embeddings crawl along (linter rule AIO021).

| Stage pair | Queue size guideline |
|------------|---------------------|
| Fetch -> parse | 2 x parser workers |
| Parse -> embed (batched) | 2 x batch size |
| Anything -> GPU worker | 1-2 batches; the GPU is the bottleneck, more buffering only adds latency |

`put_nowait()` raises `asyncio.QueueFull` instead of waiting; use it when dropping or rejecting is the right
policy (e.g. a live telemetry buffer, or returning HTTP 503 when a request queue is full).

## Token bucket

A bucket holds up to `capacity` tokens and refills at `rate` per second; each request takes one (or `cost`)
tokens and waits if there are not enough. Capacity sets the allowed burst.

```python
import asyncio
import time


class TokenBucket:
    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self.rate, self.capacity = rate, capacity
        self._tokens = capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()          # FIFO fairness: waiters are served in arrival order

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
        self._updated = now

    async def acquire(self, cost: float = 1.0) -> None:
        if cost > self.capacity:
            raise ValueError(f"cost {cost} exceeds bucket capacity {self.capacity}")
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= cost:
                    self._tokens -= cost
                    return
                await asyncio.sleep((cost - self._tokens) / self.rate)

    def refund(self, amount: float) -> None:
        self._refill()
        self._tokens = min(self.capacity, self._tokens + amount)


async def main() -> None:
    bucket = TokenBucket(rate=50, capacity=5)          # 50 req/s, burst of 5
    start = time.monotonic()
    await asyncio.gather(*(bucket.acquire() for _ in range(30)))
    elapsed = time.monotonic() - start
    print("30 requests:", 0.45 <= elapsed <= 0.8)      # 5 immediately, 25 more at 50/s = 0.5 s


asyncio.run(main())
# Output: 30 requests: True
```

For a limit "N per minute", use `rate = N / 60`. Set `capacity` small (a few seconds' worth) if the provider
enforces the limit over short sub-windows; many providers do, so a full minute of burst at once can still
return 429. `aiolimiter.AsyncLimiter(max_rate, time_period)` is a maintained library implementation of the
same leaky-bucket idea.

## RPM and TPM together

LLM APIs limit requests and tokens independently; whichever runs out first throttles you. Charge the request
bucket 1 and the token bucket the **estimated** tokens (prompt + max output), reserved before sending.

```python
import asyncio


class DualRateLimiter:
    """Waits until both the request-per-minute and token-per-minute budgets allow the call."""

    def __init__(self, rpm: int, tpm: int, burst_seconds: float = 6.0) -> None:
        self.requests = TokenBucket(rate=rpm / 60, capacity=max(1.0, rpm / 60 * burst_seconds))
        self.tokens = TokenBucket(rate=tpm / 60, capacity=max(1.0, tpm / 60 * burst_seconds))

    async def acquire(self, tokens: int) -> None:
        # Take tokens first: it is the scarcer budget for long prompts, and holding a request
        # slot while waiting for tokens would starve short requests.
        await self.tokens.acquire(min(tokens, self.tokens.capacity))
        await self.requests.acquire(1)

    def reconcile(self, estimated: int, actual: int) -> None:
        """Give back over-estimated tokens once the response reports real usage."""
        if actual < estimated:
            self.tokens.refund(estimated - actual)
```

(`TokenBucket` is the class above.) A request bigger than the bucket capacity is clamped so it can still go
through once the bucket is full; size `burst_seconds` so `tpm / 60 * burst_seconds` exceeds your largest
request, or such requests will be admitted early.

Wrap the client call:

```python
async def chat(limiter: DualRateLimiter, sem: asyncio.Semaphore, client, messages, max_tokens: int = 512):
    estimate = estimate_tokens(messages) + max_tokens
    async with sem:                                   # concurrency (sockets, memory)
        await limiter.acquire(estimate)               # rate (RPM + TPM)
        resp = await with_retry(lambda: client.complete(messages, max_tokens=max_tokens))
    limiter.reconcile(estimate, resp.usage.total_tokens)
    return resp
```

## Estimating and reconciling tokens

| Method | Accuracy | Cost |
|--------|----------|------|
| `len(text) / 4` (English) | +/- 20-30% | free |
| Provider tokenizer (e.g. `tiktoken` for OpenAI models) | exact for that model family | ~microseconds per KB, CPU |
| Provider token-count endpoint | exact | an extra request (counts against RPM on some providers) |
| `usage` field in the response | exact, after the fact | free; use it to reconcile |

Estimate conservatively before the call (include the system prompt, tool schemas and images), then refund the
difference from `usage`. For embeddings, TPM is usually the binding limit: batch inputs (e.g. 100-2,048 texts
per request, model dependent) and charge the batch's total tokens.

Tokenizing large prompts is CPU work; for big batches run it in `asyncio.to_thread` or once per document at
ingestion time, not per request on the loop.

## Reading provider rate-limit headers

Providers return remaining budget and reset times in response headers; using them avoids guessing:

| Provider family | Headers (examples) |
|-----------------|--------------------|
| OpenAI-compatible | `x-ratelimit-remaining-requests`, `x-ratelimit-remaining-tokens`, `x-ratelimit-reset-requests`, `x-ratelimit-reset-tokens` |
| Anthropic | `anthropic-ratelimit-requests-remaining`, `anthropic-ratelimit-tokens-remaining`, `...-reset` (RFC 3339 time) |
| Most HTTP APIs on 429/503 | `Retry-After` (seconds or HTTP date) |

Header names and formats change; treat them as hints, log them, and always fall back to backoff. On a 429:
sleep `Retry-After` (plus jitter) in the task that got it **and** tell the shared limiter, so other tasks stop
sending too:

```python
class PausableLimiter:
    def __init__(self) -> None:
        self._resume_at = 0.0

    def pause_for(self, seconds: float) -> None:
        loop = asyncio.get_running_loop()
        self._resume_at = max(self._resume_at, loop.time() + seconds)

    async def wait(self) -> None:
        loop = asyncio.get_running_loop()
        delay = self._resume_at - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
```

## Adaptive concurrency (AIMD)

When limits are unknown or shared with other services, adapt: additive increase on success, multiplicative
decrease on 429/timeouts (the TCP congestion-control idea).

```python
import asyncio


class RateLimited(Exception):
    pass


class AdaptiveLimiter:
    def __init__(self, initial: int = 8, minimum: int = 1, maximum: int = 128) -> None:
        self.limit, self.minimum, self.maximum = initial, minimum, maximum
        self.in_flight = 0
        self._cond = asyncio.Condition()

    async def __aenter__(self) -> "AdaptiveLimiter":
        async with self._cond:
            await self._cond.wait_for(lambda: self.in_flight < self.limit)
            self.in_flight += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        async with self._cond:
            self.in_flight -= 1
            if exc_type is None:
                self.limit = min(self.maximum, self.limit + 1 / self.limit)   # about +1 per window
            elif issubclass(exc_type, (RateLimited, TimeoutError)):
                self.limit = max(self.minimum, int(self.limit * 0.5))         # halve on overload
            self._cond.notify_all()


async def main() -> None:
    limiter = AdaptiveLimiter(initial=16)
    for _ in range(3):
        try:
            async with limiter:
                raise RateLimited("429")
        except RateLimited:
            pass
    print("limit after three 429s:", limiter.limit)


asyncio.run(main())
# Output: limit after three 429s: 2
```

Increase is fractional per success so the limit grows by about one per "window" of successful requests.
Combine with the RPM/TPM buckets when the provider documents its limits.

## Per-provider limiter registry

Multi-model apps (router, fallbacks, judge models in evals) need separate budgets per provider/model/key:

```python
from dataclasses import dataclass, field


@dataclass
class ModelBudget:
    rpm: int
    tpm: int
    max_concurrency: int
    limiter: "DualRateLimiter" = field(init=False)
    sem: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self.limiter = DualRateLimiter(self.rpm, self.tpm)
        self.sem = asyncio.Semaphore(self.max_concurrency)


BUDGETS = {
    "provider-a/large": ModelBudget(rpm=500, tpm=200_000, max_concurrency=32),
    "provider-a/small": ModelBudget(rpm=5_000, tpm=2_000_000, max_concurrency=128),
    "provider-b/embed": ModelBudget(rpm=3_000, tpm=1_000_000, max_concurrency=64),
}
```

Build the registry inside the running loop (lifespan / `main()`), not at import time on 3.9.
Numbers above are placeholders: read your account's actual tier limits from the provider console.

## Connection pools must match

| Client | Setting | Default |
|--------|---------|---------|
| `httpx.AsyncClient` | `limits=httpx.Limits(max_connections=..., max_keepalive_connections=...)` | 100 / 20 |
| `httpx` | `timeout=httpx.Timeout(read, connect=..., pool=...)` | 5 s for all |
| `aiohttp.ClientSession` | `connector=aiohttp.TCPConnector(limit=..., limit_per_host=...)` | 100 / 0 (unlimited per host) |
| `asyncpg.create_pool` | `min_size`, `max_size` | 10 / 10 |
| Official LLM SDK async clients | wrap an httpx client; pass `http_client=` to tune | SDK specific |

If your Semaphore allows more in-flight calls than the pool has connections, extra calls wait inside the
client and can fail with a **pool timeout** that looks like a network problem. Keep
`semaphore <= max_connections`, and remember the default 5 s httpx timeout is far too short for LLM
generations (set read timeouts of 60-600 s depending on output length).

## Several processes or pods

In-process limiters only see their own traffic. With N replicas either:
- give each replica `limit / N` (simple, wastes headroom when traffic is uneven), or
- use a shared limiter (Redis token bucket via a Lua script, or a gateway/proxy that enforces limits), or
- send all LLM calls through one queue consumed by a fixed worker fleet.

Always keep 429 handling in the client too: shared limiters drift, and providers apply limits you do not see.

## Choosing numbers

1. Start from provider limits: `RPM`, `TPM`, maximum concurrent requests (some providers have one).
2. Measure p50/p95 latency and average tokens per request.
3. Concurrency needed to hit the rate: `rpm / 60 * p50_latency`, plus ~20% headroom; cap by memory and pool size.
4. TPM check: `requests_per_minute * avg_tokens <= tpm`; if not, TPM is your real limit, size from that.
5. Burst: 2-10 seconds' worth of rate.
6. Load-test with production-like prompt sizes; watch 429 rate (target well under 1%), p95 latency,
   queue depth and event-loop lag (see [debugging-asyncio.md](debugging-asyncio.md)).
