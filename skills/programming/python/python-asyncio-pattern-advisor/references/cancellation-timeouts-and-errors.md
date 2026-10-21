# Cancellation, Timeouts and Errors

How cancellation really works, how timeouts are built on it, how to clean up correctly, and how to handle
errors from many concurrent tasks (partial failure, ExceptionGroup, retries, graceful shutdown).

## Contents

- [How cancellation works](#how-cancellation-works)
- [Rules for handling CancelledError](#rules-for-handling-cancellederror)
- [Swallowed cancellation breaks timeouts](#swallowed-cancellation-breaks-timeouts)
- [Reaping a task you cancelled](#reaping-a-task-you-cancelled)
- [Timeouts: asyncio.timeout vs wait_for](#timeouts-asynciotimeout-vs-wait_for)
- [Layered timeouts for LLM calls](#layered-timeouts-for-llm-calls)
- [shield](#shield)
- [Cleanup on cancel](#cleanup-on-cancel)
- [Errors from many tasks](#errors-from-many-tasks)
- [ExceptionGroup and except*](#exceptiongroup-and-except)
- [Retries with backoff and jitter](#retries-with-backoff-and-jitter)
- [Circuit breaker](#circuit-breaker)
- [Graceful shutdown, signals and Ctrl+C](#graceful-shutdown-signals-and-ctrlc)
- [Unhandled errors in callbacks](#unhandled-errors-in-callbacks)

## How cancellation works

`task.cancel(msg=None)` (msg since 3.9) does not stop anything immediately. It schedules a
`CancelledError` to be **thrown into the coroutine at its next suspension point** (the `await` it is currently
parked on, or the next one). The coroutine can run `except`/`finally` code, including more awaits, and then
the task ends cancelled if the error propagates out.

- `CancelledError` subclasses `BaseException` since 3.8, so `except Exception` does not catch it.
- Code with no `await` cannot be cancelled: a CPU loop or a blocking call runs to completion first.
- `task.cancelling()` (3.11) returns how many cancel requests are pending; `task.uncancel()` (3.11) decrements
  that count. TaskGroup and `asyncio.timeout` use this to tell their own cancellations from outside ones.
- Cancelling a task that awaits another task cancels the inner one too (the cancel is forwarded to the
  awaited future), unless it is shielded.
- Cancelling an `await asyncio.to_thread(...)` abandons the result; the thread keeps running.

```python
import asyncio


async def generate(prompt: str) -> str:
    try:
        await asyncio.sleep(10)                  # waiting on the model
        return "done"
    except asyncio.CancelledError:
        print("cleanup: releasing GPU slot")
        raise
    finally:
        print("finally runs too")


async def main() -> None:
    task = asyncio.create_task(generate("hi"))
    await asyncio.sleep(0.01)
    task.cancel("user pressed stop")
    try:
        await task
    except asyncio.CancelledError:
        print("cancelled:", task.cancelled())


asyncio.run(main())
# Output:
# cleanup: releasing GPU slot
# finally runs too
# cancelled: True
```

## Rules for handling CancelledError

1. Prefer `try/finally` (or `async with`) for cleanup; it runs on cancellation without catching anything.
2. If you catch `CancelledError` (to log, to send a "stopped" event), end the handler with a bare `raise`.
3. Never write `except BaseException:` or bare `except:` without re-raising in async code (AIO014).
4. Do not convert cancellation into a return value. Callers (TaskGroup, timeout, shutdown) rely on it
   propagating.
5. If you deliberately absorb a cancellation (rare: a supervisor that restarts a worker), call
   `asyncio.current_task().uncancel()` (3.11+) so enclosing timeouts and task groups keep working.

## Swallowed cancellation breaks timeouts

```python
import asyncio


async def bad_call() -> str:
    try:
        await asyncio.sleep(1)
        return "answer"
    except asyncio.CancelledError:          # swallowed
        return "partial"


async def good_call() -> str:
    try:
        await asyncio.sleep(1)
        return "answer"
    except asyncio.CancelledError:
        raise


async def main() -> None:
    for fn in (bad_call, good_call):
        try:
            async with asyncio.timeout(0.05):
                result = await fn()
            print(fn.__name__, "returned", result, "- timeout did not fire")
        except TimeoutError:
            print(fn.__name__, "timed out as expected")


asyncio.run(main())
# Output:
# bad_call returned partial - timeout did not fire
# good_call timed out as expected
```

The bad version turns a 50 ms deadline into "returns garbage, and the caller never learns it timed out".
Inside a TaskGroup the same bug makes shutdown hang, because the group waits for a child that refuses to stop.

## Reaping a task you cancelled

The common shutdown idiom is fine and the linter allows it:

```python
monitor.cancel()
try:
    await monitor
except asyncio.CancelledError:
    pass
```

Caveat: if the **current** task is cancelled while it waits here, that cancellation is swallowed too. On 3.11+
the precise version checks whether the cancel was meant for us:

```python
monitor.cancel()
try:
    await monitor
except asyncio.CancelledError:
    current = asyncio.current_task()
    if current is not None and current.cancelling():
        raise                                   # we are being cancelled as well: propagate
```

## Timeouts: asyncio.timeout vs wait_for

| | `async with asyncio.timeout(s)` (3.11+) | `await asyncio.wait_for(aw, s)` |
|-|-----------------------------------------|---------------------------------|
| Scope | any block, many awaits | one awaitable |
| Extra task | no | wraps coroutines in a task on 3.9-3.11 |
| Reschedule deadline | `cm.reschedule(new_deadline)`, `cm.when()` | no |
| Absolute deadline | `asyncio.timeout_at(loop.time() + s)` | no |
| Raises | `TimeoutError` | `TimeoutError` (`asyncio.TimeoutError` alias since 3.11) |
| No timeout | `asyncio.timeout(None)` | `timeout=None` |

On 3.12+ `wait_for` is implemented with `asyncio.timeout`, which fixed older edge cases where a result
arriving exactly at the deadline could be lost or a cancellation swallowed. On 3.9/3.10, before 3.11's
`asyncio.TimeoutError is TimeoutError`, catch `asyncio.TimeoutError`.

```python
import asyncio


async def retrieve() -> list[str]:
    await asyncio.sleep(0.01)
    return ["chunk-1", "chunk-2"]


async def generate(chunks: list[str]) -> str:
    await asyncio.sleep(0.5)
    return "answer"


async def main() -> None:
    try:
        async with asyncio.timeout(0.1) as cm:
            chunks = await retrieve()
            print("retrieved", len(chunks), "deadline set:", cm.when() is not None)
            await generate(chunks)
    except TimeoutError:
        print("whole RAG request exceeded 100 ms; expired =", cm.expired())


asyncio.run(main())
# Output:
# retrieved 2 deadline set: True
# whole RAG request exceeded 100 ms; expired = True
```

## Layered timeouts for LLM calls

Use three layers, each catching a different failure:

| Layer | Example | Catches |
|-------|---------|---------|
| Client connect/read timeouts | `httpx.Timeout(60, connect=5)` | dead hosts, stalled sockets |
| Per-attempt deadline | `async with asyncio.timeout(90):` around one call | slow generations |
| Whole-operation budget | `asyncio.timeout(300)` around retries + fallbacks | retry storms exceeding the user's patience |

For streaming, a total deadline is wrong for long answers; use an **idle** timeout per chunk instead:

```python
async def with_idle_timeout(stream, idle: float):
    it = stream.__aiter__()
    while True:
        try:
            async with asyncio.timeout(idle):
                chunk = await it.__anext__()
        except StopAsyncIteration:
            return
        yield chunk
```

## shield

`asyncio.shield(aw)` returns an awaitable that, when cancelled, does **not** cancel `aw`. The caller still gets
`CancelledError`; the shielded work continues in the background.

```python
import asyncio


async def write_batch(batch: list[str], log: list[str]) -> None:
    await asyncio.sleep(0.05)               # vector-store upsert
    log.append(f"wrote {len(batch)}")


async def handler(log: list[str]) -> None:
    write = asyncio.ensure_future(write_batch(["a", "b"], log))
    try:
        await asyncio.shield(write)
    except asyncio.CancelledError:
        await write                         # let the write finish, then propagate
        raise


async def main() -> None:
    log: list[str] = []
    task = asyncio.create_task(handler(log))
    await asyncio.sleep(0.01)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print(log)


asyncio.run(main())
# Output: ['wrote 2']
```

Rules: keep a reference to the inner task (above: `write`), otherwise it can be garbage-collected after the
caller is cancelled; shield short, critical sections only (commit, ack); never shield whole request handlers
(shutdown will wait forever).

## Cleanup on cancel

```python
async def stream_answer(client, prompt: str):
    stream = await client.open_stream(prompt)
    try:
        async for event in stream:
            yield event
    finally:
        # Runs on normal end, error, consumer break (with aclosing), and cancellation.
        # A second cancel during this await would interrupt it; keep it short or shield it.
        await asyncio.shield(stream.aclose())
```

Ordering: `except CancelledError` runs before `finally`; cleanup awaits run with the task still marked
"cancelling", which is fine. Avoid starting new long operations during cleanup. In TaskGroups, cleanup of
siblings happens before the group raises, so the `ExceptionGroup` arrives after all children finished.

## Errors from many tasks

| Goal | Pattern |
|------|---------|
| All must succeed, fail fast | `TaskGroup` (3.11) or `gather_all_or_cancel` helper (3.9/3.10) |
| Best effort, report failures | `gather(..., return_exceptions=True)` + split by `isinstance(r, BaseException)` |
| Best effort with per-item retry | wrap each item: `async def safe(x): try: return Ok(await f(x)) except Exception as e: return Err(x, e)` |
| Stop after N failures | worker pool with a shared failure counter; cancel workers when it trips |
| Log failures as they happen | `as_completed` loop with `try/except` per result |

Best-effort embedding of a batch, recording failures without losing the successful vectors:

```python
import asyncio


async def embed(doc: str) -> list[float]:
    await asyncio.sleep(0)
    if not doc:
        raise ValueError("empty document")
    return [float(len(doc))]


async def main() -> None:
    docs = ["alpha", "", "gamma"]
    results = await asyncio.gather(*(embed(d) for d in docs), return_exceptions=True)
    vectors = {i: r for i, r in enumerate(results) if not isinstance(r, BaseException)}
    failures = {i: repr(r) for i, r in enumerate(results) if isinstance(r, BaseException)}
    print(vectors)
    print(failures)


asyncio.run(main())
# Output:
# {0: [5.0], 2: [5.0]}
# {1: "ValueError('empty document')"}
```

## ExceptionGroup and except*

A TaskGroup raises `ExceptionGroup` (or `BaseExceptionGroup`) containing every child failure. `except*`
(3.11) matches by type inside the group; each clause gets a sub-group; unmatched exceptions re-raise.

```python
import asyncio


class RateLimited(Exception):
    pass


async def call(i: int) -> int:
    await asyncio.sleep(0.01)
    if i == 1:
        raise RateLimited("429 on call 1")
    if i == 2:
        raise TimeoutError("call 2 timed out")
    return i


async def main() -> None:
    try:
        async with asyncio.TaskGroup() as tg:
            for i in range(4):
                tg.create_task(call(i))
    except* RateLimited as eg:
        print("rate limited:", [str(e) for e in eg.exceptions])
    except* TimeoutError as eg:
        print("timeouts:", [str(e) for e in eg.exceptions])


asyncio.run(main())
# Output:
# rate limited: ['429 on call 1']
# timeouts: ['call 2 timed out']
```

Notes: both failing tasks hit at the same time here so both are in the group; a task that was cancelled
because a sibling failed does not appear. `eg.split(TypeOrPredicate)` and `eg.subgroup(...)` work outside
`except*`. Pre-3.11: the `exceptiongroup` backport provides `ExceptionGroup` and a `catch()` context manager.
`except*` cannot be mixed with plain `except` in one `try`, and `break`/`continue`/`return` inside an
`except*` clause is a SyntaxError.

## Retries with backoff and jitter

```python
import asyncio
import email.utils
import random
import time
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


class TransientError(Exception):
    def __init__(self, msg: str, retry_after: Optional[float] = None) -> None:
        super().__init__(msg)
        self.retry_after = retry_after


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Retry-After is either delta-seconds or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        dt = email.utils.parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - time.time())


async def with_retry(call: Callable[[], Awaitable[T]], *, attempts: int = 5, base: float = 0.5,
                     cap: float = 30.0, budget: float = 120.0) -> T:
    start = time.monotonic()
    for attempt in range(attempts):
        try:
            return await call()
        except TransientError as err:
            if attempt == attempts - 1:
                raise
            delay = err.retry_after if err.retry_after is not None else random.uniform(0, min(cap, base * 2 ** attempt))
            if time.monotonic() - start + delay > budget:
                raise
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def main() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("503 overloaded", retry_after=0.01)
        return "ok"

    print(await with_retry(flaky), "after", calls["n"], "calls")
    print(parse_retry_after("2"))


asyncio.run(main())
# Output:
# ok after 3 calls
# 2.0
```

- **Full jitter** (`uniform(0, min(cap, base * 2**n))`) spreads synchronized clients; plain exponential
  backoff makes 500 workers retry in lockstep.
- Retry: 408, 409 (some APIs), 429, 500, 502, 503, 504, 529 (overloaded), connect/read timeouts, connection
  resets. Do not retry: 400, 401, 403, 404, 422, context-length errors, content-policy refusals.
- Retries multiply load: with 3 retries a provider outage quadruples traffic. Combine with a circuit breaker
  and a shared rate limiter so retries also wait for capacity.
- Only retry idempotent operations, or make them idempotent (idempotency keys for writes and tool calls).
- `tenacity` provides the same as decorators (`@retry(wait=wait_random_exponential(max=60),
  stop=stop_after_attempt(6), retry=retry_if_exception_type(...))`) and supports `async def`.

## Circuit breaker

When a dependency is down, fail fast instead of making every request wait for its timeout:

```python
import asyncio


class CircuitOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, threshold: int = 5, reset_after: float = 30.0) -> None:
        self.threshold, self.reset_after = threshold, reset_after
        self.failures, self.opened_at = 0, None

    async def call(self, fn):
        loop = asyncio.get_running_loop()
        if self.opened_at is not None:
            if loop.time() - self.opened_at < self.reset_after:
                raise CircuitOpen("vector store unavailable; using keyword fallback")
            self.opened_at = None                  # half-open: let one call through
        try:
            result = await fn()
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = loop.time()
            raise
        self.failures = 0
        return result
```

## Graceful shutdown, signals and Ctrl+C

- `asyncio.run` (3.11+, via `Runner`) installs a SIGINT handler in the main thread that **cancels the main
  task**, so Ctrl+C runs your `finally` blocks and cleanup awaits; a second Ctrl+C raises
  `KeyboardInterrupt` immediately. On 3.9/3.10 `KeyboardInterrupt` is raised wherever the loop happens to be.
- On exit `asyncio.run` cancels all remaining tasks and waits for them, then finalizes async generators and
  shuts down the default executor (waits for running `to_thread` calls).
- Containers send SIGTERM. Handle it on Unix with `loop.add_signal_handler`:

```python
import asyncio
import signal


async def serve_forever(stop: asyncio.Event) -> None:
    while not stop.is_set():
        await asyncio.sleep(0.1)          # stand-in for consuming a job queue


async def main() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)     # Unix only
    worker = asyncio.create_task(serve_forever(stop))
    await stop.wait()
    # Drain: stop taking new jobs, give in-flight work a deadline, then cancel.
    try:
        async with asyncio.timeout(25):            # below the orchestrator's kill grace period
            await worker
    except TimeoutError:
        worker.cancel()
```

Shutdown checklist: stop accepting work; let in-flight work finish with a deadline; flush buffers (usage
logs, vector-store batches); cancel and await background tasks; close clients and pools; exit non-zero if work
was dropped. Uvicorn handles SIGTERM itself and then runs your lifespan shutdown.

## Unhandled errors in callbacks

Exceptions in `call_soon` callbacks, in protocol callbacks, and in tasks that are garbage-collected with an
unretrieved exception go to the loop's exception handler, which logs to the `asyncio` logger. Route them to
your logging/alerting:

```python
import asyncio
import logging

logger = logging.getLogger("app")


def handle_loop_error(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    exc = context.get("exception")
    logger.error("asyncio: %s", context.get("message"), exc_info=exc,
                 extra={"task": repr(context.get("task") or context.get("future"))})


async def main() -> None:
    asyncio.get_running_loop().set_exception_handler(handle_loop_error)
```

This is a safety net, not a strategy: own your tasks so exceptions are retrieved by someone who can act.
