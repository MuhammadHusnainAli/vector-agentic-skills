# Testing Async Code

Deterministic, fast tests for coroutines, task groups, rate limiters, retries, timeouts, cancellation,
streaming and FastAPI endpoints. The goal: no real network, no real sleeps, no timing-dependent assertions.

## Contents

- [Choosing a test runner](#choosing-a-test-runner)
- [pytest-asyncio setup](#pytest-asyncio-setup)
- [anyio pytest plugin](#anyio-pytest-plugin)
- [unittest.IsolatedAsyncioTestCase](#unittestisolatedasynciotestcase)
- [Fakes instead of mocks](#fakes-instead-of-mocks)
- [A complete test module](#a-complete-test-module)
- [Deterministic ordering with Events](#deterministic-ordering-with-events)
- [Testing timeouts without waiting](#testing-timeouts-without-waiting)
- [Testing cancellation and cleanup](#testing-cancellation-and-cleanup)
- [Testing retries and backoff](#testing-retries-and-backoff)
- [Testing streams](#testing-streams)
- [Catching blocking calls and lost coroutines in CI](#catching-blocking-calls-and-lost-coroutines-in-ci)
- [FastAPI endpoints](#fastapi-endpoints)
- [AsyncMock](#asyncmock)
- [Flaky async tests: causes and fixes](#flaky-async-tests-causes-and-fixes)

## Choosing a test runner

| Option | When | Notes |
|--------|------|-------|
| `pytest-asyncio` | most asyncio projects | `async def test_...` with a marker or auto mode |
| anyio pytest plugin (ships with `anyio`) | code built on anyio, or to run tests on asyncio and trio | `@pytest.mark.anyio`; already installed with FastAPI/httpx |
| `unittest.IsolatedAsyncioTestCase` (3.8+) | stdlib only, unittest code bases | `asyncSetUp`/`asyncTearDown`, fresh loop per test |
| `asyncio.run()` inside a sync test | one-off, no plugin available | simplest; no async fixtures |

Do not install and enable both pytest-asyncio auto mode and the anyio plugin for the same tests; pick one
runner per test (anyio's marker and pytest-asyncio's strict mode coexist fine).

## pytest-asyncio setup

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"                         # every async def test/fixture is handled; no markers needed
asyncio_default_fixture_loop_scope = "function"
filterwarnings = ["error::RuntimeWarning"]    # "coroutine ... was never awaited" fails the test
```

- **strict** mode (the default) requires `@pytest.mark.asyncio` on tests and `@pytest_asyncio.fixture` on
  async fixtures; use it when the project also uses other async plugins.
- Each test gets its own event loop by default. Share one loop across a module/session with
  `@pytest.mark.asyncio(loop_scope="module")` and fixtures declared with the same `loop_scope`, e.g. an
  expensive `asyncpg` pool. A fixture whose loop scope is wider than the test's loop raises "attached to a
  different loop" errors.
- Version notes: 0.24 introduced `loop_scope`; 1.0 (2025) removed the long-deprecated `event_loop` fixture.
  Code that overrides `event_loop` must move to `loop_scope` (and, for custom loops such as uvloop, the
  documented event-loop-policy fixture or `loop_factory` support of the version you use).

## anyio pytest plugin

```python
import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"                  # parametrize with ["asyncio", "trio"] to run on both


@pytest.mark.anyio
async def test_health(client) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
```

## unittest.IsolatedAsyncioTestCase

```python
import asyncio
import unittest


class FakeStore:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class TestRetriever(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.store = FakeStore()

    async def asyncTearDown(self) -> None:
        await self.store.aclose()

    async def test_gather_keeps_order(self) -> None:
        async def score(i: int) -> int:
            await asyncio.sleep(0)
            return i * i

        self.assertEqual(await asyncio.gather(*(score(i) for i in range(4))), [0, 1, 4, 9])


if __name__ == "__main__":
    unittest.main(argv=["x"], exit=False, verbosity=0)
    print("unittest done")
# Output: unittest done
```

## Fakes instead of mocks

A small fake with real async behaviour (it awaits, it can fail on cue, it records calls and concurrency) tests
much more than `AsyncMock(return_value=...)`:

```python
import asyncio
from dataclasses import dataclass, field


@dataclass
class FakeLLM:
    """Programmable fake: scripted failures per prompt, records concurrency, optional gate to hold calls."""

    failures: dict[str, list[Exception]] = field(default_factory=dict)
    gate: asyncio.Event | None = None
    calls: list[str] = field(default_factory=list)
    in_flight: int = 0
    peak: int = 0

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            if self.gate is not None:
                await self.gate.wait()
            else:
                await asyncio.sleep(0)          # yield once so concurrency actually overlaps
            queued = self.failures.get(prompt)
            if queued:
                raise queued.pop(0)
            return f"answer:{prompt}"
        finally:
            self.in_flight -= 1
```

## A complete test module

Code under test plus tests in one file; run with `pytest -q test_answers.py` (pytest-asyncio installed).

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest


class RateLimited(Exception):
    pass


@dataclass
class FakeLLM:
    failures: dict[str, list[Exception]] = field(default_factory=dict)
    gate: asyncio.Event | None = None
    calls: list[str] = field(default_factory=list)
    in_flight: int = 0
    peak: int = 0

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            if self.gate is not None:
                await self.gate.wait()
            else:
                await asyncio.sleep(0)
            queued = self.failures.get(prompt)
            if queued:
                raise queued.pop(0)
            return f"answer:{prompt}"
        finally:
            self.in_flight -= 1


# ---- code under test --------------------------------------------------------
async def answer_all(llm, prompts, *, limit=4, attempts=3, sleep=asyncio.sleep, timeout=30.0):
    sem = asyncio.Semaphore(limit)

    async def one(p):
        for attempt in range(attempts):
            try:
                async with sem:
                    async with asyncio.timeout(timeout):
                        return await llm.complete(p)
            except RateLimited:
                if attempt == attempts - 1:
                    raise
                await sleep(2 ** attempt)

    return await asyncio.gather(*(one(p) for p in prompts), return_exceptions=True)


# ---- tests ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_results_in_input_order():
    llm = FakeLLM()
    assert await answer_all(llm, ["a", "b", "c"]) == ["answer:a", "answer:b", "answer:c"]


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_limit():
    llm = FakeLLM()
    await answer_all(llm, [f"p{i}" for i in range(50)], limit=4)
    assert llm.peak == 4


@pytest.mark.asyncio
async def test_retries_rate_limits_with_backoff_without_sleeping():
    delays = []

    async def fake_sleep(d):
        delays.append(d)

    llm = FakeLLM(failures={"x": [RateLimited(), RateLimited()]})
    assert await answer_all(llm, ["x"], sleep=fake_sleep) == ["answer:x"]
    assert delays == [1, 2]
    assert llm.calls == ["x", "x", "x"]


@pytest.mark.asyncio
async def test_permanent_failure_is_returned_not_raised():
    llm = FakeLLM(failures={"bad": [ValueError("400")]})
    results = await answer_all(llm, ["ok", "bad"])
    assert results[0] == "answer:ok"
    assert isinstance(results[1], ValueError)


@pytest.mark.asyncio
async def test_timeout_fires_fast():
    llm = FakeLLM(gate=asyncio.Event())          # never released: simulates a hung provider
    results = await answer_all(llm, ["slow"], timeout=0.01)
    assert isinstance(results[0], TimeoutError)


@pytest.mark.asyncio
async def test_cancellation_propagates_and_releases_slots():
    llm = FakeLLM(gate=asyncio.Event())
    task = asyncio.create_task(answer_all(llm, ["a", "b"], limit=1))
    while llm.in_flight == 0:                     # wait until the first call is in flight
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert llm.in_flight == 0                     # finally blocks ran
```

## Deterministic ordering with Events

Never use `sleep(0.1)` to "let the other task get there first". Gate each step with an `asyncio.Event` (or
poll a condition with `await asyncio.sleep(0)` in a loop, as above), so the test is exact and instant:

```python
import asyncio


async def main() -> None:
    started, release = asyncio.Event(), asyncio.Event()
    order = []

    async def slow_tool() -> None:
        started.set()
        await release.wait()
        order.append("tool finished")

    task = asyncio.create_task(slow_tool())
    await started.wait()                  # tool is definitely running now
    order.append("user cancelled?")       # assert intermediate state here
    release.set()
    await task
    print(order)


asyncio.run(main())
# Output: ['user cancelled?', 'tool finished']
```

## Testing timeouts without waiting

- Inject the timeout value (`timeout=0.01` in tests) and a fake that never completes (an unset `Event`).
- Inject `sleep` (as in `answer_all` above) so backoff code records delays instead of waiting.
- asyncio has no built-in virtual clock. Third-party plugins (for example `looptime`) fake the loop's time so
  `asyncio.sleep(60)` completes instantly while `loop.time()` advances; use them for code with long
  schedules, cron-like loops or token buckets.
- For token buckets, pass a `clock` callable into the class instead of calling `time.monotonic()` directly,
  then advance a fake clock in the test.

## Testing cancellation and cleanup

Checklist for any long-running coroutine (stream handler, worker, agent loop):
1. Start it, wait until it reached the interesting await (Event or in-flight counter).
2. `task.cancel()`.
3. `with pytest.raises(asyncio.CancelledError): await task` (it must not swallow).
4. Assert cleanup happened: connection released, stream closed, semaphore slot free, partial results flushed.

Also test cancellation **during cleanup** for code that awaits in `finally` (cancel twice), and that a
TaskGroup with one failing child cancels and awaits the siblings (assert their cleanup ran).

## Testing retries and backoff

- Script failures per call (`failures={"x": [RateLimited(), RateLimited()]}`) and assert the call count.
- Assert delays from the injected sleep; with jitter, inject the RNG (`random.Random(0)`) or assert bounds
  (`0 <= d <= cap`).
- Assert non-retryable errors are raised after exactly one call.
- Assert the overall budget: with `budget=5` and `Retry-After: 10`, the helper gives up immediately.

## Testing streams

```python
import asyncio
from contextlib import aclosing


async def main() -> None:
    closed = []

    async def tokens():
        try:
            for t in ["a", "b", "c", "d"]:
                await asyncio.sleep(0)
                yield t
        finally:
            closed.append(True)

    collected = []
    async with aclosing(tokens()) as gen:
        async for t in gen:
            collected.append(t)
            if t == "b":
                break
    assert collected == ["a", "b"] and closed == [True]
    print("early close cleans up:", closed == [True])


asyncio.run(main())
# Output: early close cleans up: True
```

For SSE endpoints, read the response with `client.stream("GET", url)` and `aiter_lines()`, and assert on parsed
`data:` frames including the final `[DONE]`.

## Catching blocking calls and lost coroutines in CI

- `filterwarnings = ["error::RuntimeWarning"]` makes "never awaited" fail the test that caused it.
- Turn on debug mode for each test's loop and fail on slow-callback logs. Set it from inside the loop: the
  test runner may create its loop with an explicit `debug` flag, so `PYTHONASYNCIODEBUG=1` alone is not
  guaranteed to reach it.

```python
import asyncio
import logging

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def no_slow_callbacks(caplog):
    loop = asyncio.get_running_loop()
    loop.set_debug(True)
    loop.slow_callback_duration = 0.1                 # seconds a single step may hold the loop
    caplog.set_level(logging.WARNING, logger="asyncio")
    yield
    records = caplog.get_records("call")
    slow = [r.getMessage() for r in records if r.name == "asyncio" and "Executing" in r.getMessage()]
    assert not slow, f"event loop blocked: {slow}"
```

- Add `python scripts/async_lint.py src/ --strict` as a CI step.

## FastAPI endpoints

`httpx.ASGITransport` calls the app in-process. It does **not** run lifespan events, so start lifespan yourself
(or use `fastapi.testclient.TestClient` as a context manager, which does, in a sync test).

```python
from contextlib import asynccontextmanager

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cache = {"ping": "pong"}
    yield
    app.state.cache.clear()


app = FastAPI(lifespan=lifespan)


@app.get("/ping")
async def ping(request: Request) -> dict:
    return {"reply": request.app.state.cache["ping"]}


@pytest_asyncio.fixture          # strict mode; plain @pytest.fixture works in asyncio_mode = "auto"
async def client():
    async with app.router.lifespan_context(app):            # run startup/shutdown around the test
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_ping(client):
    resp = await client.get("/ping")
    assert resp.json() == {"reply": "pong"}
```

Override dependencies (`app.dependency_overrides[get_llm] = lambda: FakeLLM()`) to inject fakes, and clear the
overrides after the test. The `asgi-lifespan` package (`LifespanManager(app)`) is an alternative to calling
`lifespan_context` directly.

## AsyncMock

```python
import asyncio
from unittest.mock import AsyncMock


async def main() -> None:
    client = AsyncMock()
    client.embed.side_effect = [TimeoutError(), [0.1, 0.2]]   # first call fails, second succeeds
    try:
        await client.embed("doc")
    except TimeoutError:
        pass
    print(await client.embed("doc"), client.embed.await_count)
    client.embed.assert_awaited_with("doc")


asyncio.run(main())
# Output: [0.1, 0.2] 2
```

`AsyncMock` returns a coroutine for every call and tracks `await_count`/`assert_awaited_*`. It does not yield
to the loop, so it cannot reveal concurrency bugs; prefer fakes for anything about ordering, limits or
cancellation. `unittest.mock.patch` auto-uses `AsyncMock` when the patched target is an `async def`.

## Flaky async tests: causes and fixes

| Flake | Cause | Fix |
|-------|-------|-----|
| Passes alone, fails in suite | state shared across loops (module-level client/semaphore) | create per test or use matching `loop_scope` |
| "attached to a different loop" | session-scoped async fixture with function-scoped loop | align `loop_scope` |
| Timing assertion fails on CI | `sleep`-based ordering, wall-clock thresholds | Events, injected sleep/clock |
| Hangs forever | awaited future never resolved | `asyncio.timeout` in the test or `pytest-timeout` |
| Warnings about pending tasks at teardown | test started tasks it did not await | await/cancel in `finally`, use TaskGroup |
| Order-dependent results | relying on completion order | sort, or assert on sets, or key by id |
