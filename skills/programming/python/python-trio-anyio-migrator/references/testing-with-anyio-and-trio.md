# Testing with AnyIO and Trio

Switch the test suite first (Phase 1 of the [migration playbook](migration-playbook.md#phase-1-tests-first))
and keep it green after every commit. This reference covers the anyio pytest plugin, running every test on
both backends, moving off pytest-asyncio, pytest-trio, deterministic time with `MockClock`, deterministic
ordering, and how to test cancellation, timeouts, exception groups and FastAPI/httpx code. The examples
were run with anyio 4.15, trio 0.34, pytest 9, pytest-trio 0.8, httpx 0.28 and FastAPI 0.157 on Python 3.13.
asyncio-only test tricks (event-loop fixtures, `loop.slow_callback_duration`) are in the
[asyncio advisor](../../python-asyncio-pattern-advisor/SKILL.md).

## Contents

- [The anyio pytest plugin](#the-anyio-pytest-plugin)
- [Choosing backends: the anyio_backend fixture](#choosing-backends-the-anyio_backend-fixture)
- [Async fixtures](#async-fixtures)
- [Moving from pytest-asyncio](#moving-from-pytest-asyncio)
- [pytest-trio](#pytest-trio)
- [Deterministic time: MockClock and autojump](#deterministic-time-mockclock-and-autojump)
- [Deterministic ordering](#deterministic-ordering)
- [Testing cancellation and cleanup](#testing-cancellation-and-cleanup)
- [Testing timeouts](#testing-timeouts)
- [Testing exception groups](#testing-exception-groups)
- [Fakes instead of asyncio mocks](#fakes-instead-of-asyncio-mocks)
- [FastAPI, Starlette and httpx under anyio](#fastapi-starlette-and-httpx-under-anyio)
- [Threads and blocking portals in tests](#threads-and-blocking-portals-in-tests)
- [Warnings, leaks and the CI matrix](#warnings-leaks-and-the-ci-matrix)
- [Checklist](#checklist)

## The anyio pytest plugin

The plugin ships inside anyio and registers itself through a pytest entry point. There is nothing extra to
install, and `pytest-asyncio` is not needed.

| Mode | How to enable | Which tests it runs |
|------|---------------|---------------------|
| strict (default) | nothing | `async def` tests marked `@pytest.mark.anyio` (on the function, class or module via `pytestmark`) |
| auto | `anyio_mode = "auto"` in the pytest ini, or `--anyio-mode=auto` | every `async def` test function |

```toml
# pyproject.toml
[tool.pytest.ini_options]
anyio_mode = "auto"            # recent anyio 4.x; omit and use @pytest.mark.anyio on older releases
filterwarnings = [
    "error::RuntimeWarning",   # "coroutine ... was never awaited" fails the test
    "error::ResourceWarning",  # unclosed streams/sockets fail the test
]
```

```python
# Strict mode: mark per module
import pytest

pytestmark = pytest.mark.anyio
```

If anyio auto mode and pytest-asyncio auto mode are both on, anyio emits a `PytestConfigWarning`
("AnyIO auto mode has been enabled together with pytest-asyncio auto mode"). Pick one owner per test: during
a gradual move, keep pytest-asyncio in strict mode and let anyio take only the tests marked `anyio`.

How it works, in one paragraph: a marked test (or auto mode) gets the `anyio_backend` fixture added. The
plugin's `pytest_pyfunc_call` hook runs the coroutine on a test runner for that backend. Async fixtures are
wrapped only when the requesting test uses `anyio_backend`, and the test and its async fixtures share one
runner (one event loop) while any of them is alive.

## Choosing backends: the anyio_backend fixture

The built-in fixture is module-scoped and parametrised over `anyio.get_available_backends()`, so in recent
anyio 4.x every test runs once per *installed* backend: `test_x[asyncio]` and, if trio is importable,
`test_x[trio]`. Older releases ran only asyncio. Override it in `conftest.py` so the matrix does not depend
on which anyio is installed:

```python
# conftest.py
import importlib.util

import pytest

HAS_TRIO = importlib.util.find_spec("trio") is not None


@pytest.fixture(
    scope="module",                          # keep the built-in scope: see the ScopeMismatch note below
    params=[
        pytest.param("asyncio", id="asyncio"),
        pytest.param("trio", id="trio",
                     marks=pytest.mark.skipif(not HAS_TRIO, reason="trio not installed")),
    ],
)
def anyio_backend(request):
    return request.param
```

The value is either a backend name or a `(name, options)` tuple. The options go to the backend runner:

| Backend | Useful options | Example |
|---------|----------------|---------|
| asyncio | `debug`, `use_uvloop`, `loop_factory` | `("asyncio", {"debug": True})` logs slow callbacks and never-retrieved exceptions |
| trio | anything `trio.run` accepts: `clock`, `instruments`, `strict_exception_groups`, ... | `("trio", {"clock": MockClock(autojump_threshold=0)})` |

Other knobs:

| Need | How |
|------|-----|
| Read the current backend inside a test | request `anyio_backend_name` (always a string) or `anyio_backend_options` (dict) |
| One test on one backend only | `@pytest.mark.parametrize("anyio_backend", ["asyncio"])` on that test |
| A module that depends on asyncpg/aiohttp | a module-level `anyio_backend` fixture returning `"asyncio"` |
| Run one backend from the CLI | the ids are `asyncio` / `trio`: `pytest -k asyncio` or `pytest -k "not trio"` |
| Tuple params | give them an `id=` (`pytest.param(("trio", {...}), id="trio-mockclock")`), or the test id is unreadable |

**ScopeMismatch.** A module- or session-scoped async fixture depends on `anyio_backend`. If you override
`anyio_backend` with the default function scope, pytest fails with
`ScopeMismatch: You tried to access the function scoped fixture anyio_backend with a module scoped request
object`. Give the override a scope at least as wide as the widest async fixture (`scope="session"` if you
have session-scoped async fixtures).

## Async fixtures

Async fixtures are plain `@pytest.fixture` functions (`async def` with `return` or `yield`). There is no
special decorator such as `pytest_asyncio.fixture`.

```python
import anyio
import pytest


class FakeVectorStore:
    def __init__(self) -> None:
        self.closed = False
        self.docs: dict[str, str] = {}

    async def upsert(self, doc_id: str, text: str) -> None:
        await anyio.lowlevel.checkpoint()
        self.docs[doc_id] = text

    async def aclose(self) -> None:
        await anyio.lowlevel.checkpoint()
        self.closed = True


@pytest.fixture
async def store():
    s = FakeVectorStore()
    yield s
    await s.aclose()                            # teardown runs on the same backend as the test


@pytest.mark.anyio
async def test_upsert(store):
    await store.upsert("a", "alpha")
    assert store.docs == {"a": "alpha"}
```

Rules:

- The async fixture runs under anyio only when the test that requests it uses `anyio_backend` (marked test or
  auto mode). A sync test that requests an async fixture fails on pytest 9 with "requested an async fixture
  'x', with no plugin or hook that handled it"; older pytest handed the test an un-awaited coroutine.
- Calling `request.getfixturevalue("some_async_fixture")` from inside a running async test raises
  `RuntimeError: Cannot schedule a coroutine in the test runner while another is already running`. Request
  the fixture as a parameter instead.
- A task group opened in a yield fixture must be entered and exited in that fixture (the plugin runs setup and
  teardown of an async generator fixture in one task). Yield the task group itself, or a client that uses it.
  Do not yield from inside a cancel scope that the test is expected to exit.
- Fixtures that start background services use `tg.start(...)` so the test begins only after the service is
  ready:

```python
import anyio
import pytest


async def fake_embedding_server(port_box: list, *, task_status=anyio.TASK_STATUS_IGNORED) -> None:
    port_box.append(8123)                       # bind, then report readiness
    task_status.started(8123)
    await anyio.sleep_forever()


@pytest.fixture
async def embedding_port():
    async with anyio.create_task_group() as tg:
        port = await tg.start(fake_embedding_server, [])
        yield port
        tg.cancel_scope.cancel()                # stop the server; the group then exits cleanly


@pytest.mark.anyio
async def test_server_ready(embedding_port):
    assert embedding_port == 8123
```

## Moving from pytest-asyncio

| pytest-asyncio | anyio plugin | Note |
|----------------|--------------|------|
| `@pytest.mark.asyncio` | `@pytest.mark.anyio` | `scripts/migrate_async.py` does not rewrite tests; a sed over `tests/` is enough |
| `asyncio_mode = "auto"` | `anyio_mode = "auto"` | never both in auto mode |
| `@pytest_asyncio.fixture` | `@pytest.fixture` | scope argument stays the same |
| `@pytest_asyncio.fixture(loop_scope="module")` / `@pytest.mark.asyncio(loop_scope=...)` | widen the `anyio_backend` fixture scope | the plugin keeps one runner alive while any fixture or test holds it |
| `event_loop` fixture, `asyncio.get_event_loop()` in tests | none | tests must not touch the loop; use anyio APIs or `anyio_backend_name` |
| `loop.run_until_complete(...)` in sync tests | `anyio.run(...)` or a blocking portal | see [Threads and blocking portals](#threads-and-blocking-portals-in-tests) |
| `asyncio.sleep(0)` to "let tasks run" | `anyio.wait_all_tasks_blocked()` or an `Event` | `sleep(0)` ordering is backend-specific |
| `asyncio.wait_for(x, 1)` as a test timeout | `with anyio.fail_after(1):` | raises `TimeoutError` on both backends |
| `pytest.raises(ValueError)` around a `gather` | `pytest.RaisesGroup(ValueError)` around the task group | see [Testing exception groups](#testing-exception-groups) |
| `unittest.IsolatedAsyncioTestCase` | plain pytest functions + `@pytest.mark.anyio` | `IsolatedAsyncioTestCase` always runs on asyncio, so it can never cover trio |

Order of work: switch the plugin with `anyio_backend` pinned to `"asyncio"`, get green, migrate code, then
add `"trio"` to the fixture params module by module, starting with modules that have no asyncio-only
dependencies.

## pytest-trio

Use pytest-trio only for a codebase that targets trio directly and has no anyio layer. A library that must
run on both backends should use the anyio plugin, because pytest-trio runs every test on trio only.

| Feature | pytest-trio |
|---------|-------------|
| Mark a test | `@pytest.mark.trio`, or `trio_mode = true` in the ini to take every `async def` test |
| Async fixtures | `@pytest.fixture` async functions; they may run concurrently, and a fixture can yield inside a nursery |
| Built-in fixtures | `mock_clock` (a `MockClock`), `autojump_clock` (`MockClock(autojump_threshold=0)`), `nursery` (a nursery that lives for the test) |

```python
import trio


async def test_retry_backoff_is_fast(autojump_clock):     # pytest-trio, trio_mode = true
    start = trio.current_time()
    await trio.sleep(300)                                  # five minutes of backoff, in ~0 real seconds
    assert trio.current_time() - start == 300
```

Avoid running the same test under both plugins. With both installed, an anyio-marked test belongs to anyio,
and an unmarked `async def` test with no plugin claiming it fails with "async def functions are not natively
supported". Turning on `trio_mode` makes pytest-trio claim unmarked async tests, so do not enable it
together with `anyio_mode = "auto"`.

## Deterministic time: MockClock and autojump

`trio.testing.MockClock` replaces the clock of a trio run. With `autojump_threshold=0`, whenever every task
is blocked the clock jumps to the next deadline. A test that waits on a 30-second timeout then finishes in
milliseconds, and the elapsed virtual time is exact.

```python
import anyio
import pytest
from trio.testing import MockClock


@pytest.fixture(params=[pytest.param(("trio", {"clock": MockClock(autojump_threshold=0)}), id="trio-mock")])
def anyio_backend(request):
    return request.param


@pytest.mark.anyio
async def test_agent_budget_gives_up_after_120s():
    start = anyio.current_time()
    with anyio.move_on_after(120) as budget:
        await anyio.sleep(3600)                 # a tool that never answers
    assert budget.cancelled_caught
    assert anyio.current_time() - start == 120  # exact under MockClock, ~0 s of wall time
```

| MockClock API | Use |
|---------------|-----|
| `MockClock(autojump_threshold=0)` | jump as soon as everything is blocked (the usual test setting) |
| `MockClock(autojump_threshold=0.01)` | jump only after 10 ms of real idle time, which leaves room for threads and I/O to finish |
| `clock.jump(seconds)` | advance manually from the test |
| `clock.rate` | virtual seconds per real second (default 0: time stands still unless jumped) |

Caveats:

- MockClock only exists on trio. asyncio has no supported way to swap the loop clock, so keep timeout tests
  on a trio-only param (above) and test the logic, not the wall-clock duration, on asyncio.
- Each pytest param creates *one* `MockClock` at import time. It is reused across tests with that param,
  which is fine because each test only reads differences of `current_time()`. Build the clock inside a
  fixture if a test asserts absolute times.
- Autojump does not wait for real I/O or threads. A test that calls `to_thread.run_sync` or a real socket can
  hit its deadline before the thread finishes. Use a small positive threshold or keep threads out of
  MockClock tests.
- Compare `anyio.current_time()` differences, never absolute values or `time.monotonic()`. trio's normal
  clock adds a large random offset on purpose.

## Deterministic ordering

Never assert that `start_soon` children run in submission order. trio randomly reverses each batch of
runnable tasks, deliberately, so hidden ordering assumptions show up. asyncio happens to be FIFO, which is
why a test can pass on asyncio and flake on trio.

| Tool | Backends | What it gives you |
|------|----------|-------------------|
| `await anyio.wait_all_tasks_blocked()` | both | returns once every other task is waiting; the standard way to say "let the workers reach their await" |
| `anyio.Event` gates in fakes | both | the test decides exactly when a fake call completes |
| memory object stream with `max_buffer_size=0` | both | rendezvous: a send completes only when a receive happens |
| `trio.testing.Sequencer` | trio | `async with seq(0):`, `async with seq(1):` force numbered steps across tasks |
| results indexed by position | both | `results[i] = ...` instead of `append`, so completion order does not matter |

```python
import anyio
import pytest


@pytest.mark.anyio
async def test_worker_waits_for_permit():
    limiter = anyio.CapacityLimiter(1)
    log: list[str] = []

    async def worker(name: str, release: anyio.Event) -> None:
        async with limiter:
            log.append(f"{name} start")
            await release.wait()

    first_done, second_done = anyio.Event(), anyio.Event()
    async with anyio.create_task_group() as tg:
        tg.start_soon(worker, "a", first_done)
        tg.start_soon(worker, "b", second_done)
        await anyio.wait_all_tasks_blocked()
        assert len(log) == 1                    # exactly one holds the token; which one is not asserted
        assert limiter.borrowed_tokens == 1
        first_done.set()
        second_done.set()
    assert sorted(log) == ["a start", "b start"]
```

## Testing cancellation and cleanup

Three properties to check for every function that owns resources: it stops when cancelled, its cleanup
actually ran, and it re-raised the cancel exception (the caller's scope reports `cancelled_caught`).

```python
import anyio
import pytest


class Lease:
    def __init__(self) -> None:
        self.released = False

    async def release(self) -> None:
        await anyio.sleep(0.01)                 # cleanup that needs an await
        self.released = True


async def hold_lease(lease: Lease, started: anyio.Event) -> None:
    try:
        started.set()
        await anyio.sleep_forever()
    finally:
        with anyio.CancelScope(shield=True), anyio.move_on_after(1):
            await lease.release()


@pytest.mark.anyio
async def test_cancel_releases_lease():
    lease, started = Lease(), anyio.Event()
    async with anyio.create_task_group() as tg:
        tg.start_soon(hold_lease, lease, started)
        await started.wait()
        tg.cancel_scope.cancel()
    assert lease.released                       # fails without the shield: the await in finally is skipped
    assert tg.cancel_scope.cancelled_caught
```

To catch handlers that swallow cancellation (MIG031), run the function in a scope that is already
cancelled and assert it did not get past its first checkpoint:

```python
import anyio
import pytest


async def bad_retry(log: list) -> None:
    for attempt in range(3):
        try:
            await anyio.sleep(1)
        except anyio.get_cancelled_exc_class():
            log.append(f"swallowed {attempt}")  # bug: no raise
    log.append("finished")


@pytest.mark.anyio
async def test_bad_retry_ignores_cancellation():
    log: list = []
    with anyio.CancelScope() as scope:
        scope.cancel()
        await bad_retry(log)
    assert log == ["swallowed 0", "swallowed 1", "swallowed 2", "finished"]   # the bug, made visible
```

A correct function leaves `log == []` there. The same test shape also checks the
[cancellation rules](cancellation-and-exception-groups.md): replace the body under test and assert on what
ran.

For thread offload, assert that cancellation returns promptly when you rely on `abandon_on_cancel=True` or
`from_thread.check_cancelled()`. Measure with `time.monotonic()` here because the worker thread runs on real
time, and keep these tests off the MockClock param.

## Testing timeouts

| What you want to prove | Test shape |
|------------------------|------------|
| A call gives up after N seconds | trio + MockClock param; `with pytest.raises(TimeoutError): with anyio.fail_after(N): ...`, then assert elapsed `== N` |
| Giving up is not an error | `with anyio.move_on_after(N) as scope:`, then `assert scope.cancelled_caught` |
| A fallback runs on timeout | a fake whose call waits on an `Event` that is never set; assert the fallback value |
| The inner per-call timeout, not the outer budget, fired | the inner `fail_after` raises `TimeoutError`; the outer scope's `cancelled_caught` stays `False` |
| Code under test does not hang the suite | wrap the test body in `with anyio.fail_after(5):` as a guard |

Exception classes to expect: anyio's `fail_after` raises the builtin `TimeoutError` on both backends; trio's
own `trio.fail_after` raises `trio.TooSlowError`, which is not a `TimeoutError` subclass.

## Testing exception groups

Task groups raise `ExceptionGroup` even for a single failure, so `pytest.raises(ValueError)` no longer
matches. Use one of:

```python
import anyio
import pytest


async def boom(msg: str) -> None:
    await anyio.lowlevel.checkpoint()
    raise ValueError(msg)


@pytest.mark.anyio
async def test_raises_group():                   # pytest 8.4+
    with pytest.RaisesGroup(pytest.RaisesExc(ValueError, match="bad shard")):
        async with anyio.create_task_group() as tg:
            tg.start_soon(boom, "bad shard 3")


@pytest.mark.anyio
async def test_group_contains():                 # pytest 8.0+
    with pytest.raises(ExceptionGroup) as excinfo:
        async with anyio.create_task_group() as tg:
            tg.start_soon(boom, "bad shard 3")
    assert excinfo.group_contains(ValueError, match="bad shard")
```

| Tool | Behaviour |
|------|-----------|
| `pytest.RaisesGroup(ValueError)` | the group must contain exactly the listed types; nested groups need `pytest.RaisesGroup(pytest.RaisesGroup(...))` or `flatten_subgroups=True` |
| `pytest.RaisesGroup(ValueError, allow_unwrapped=True)` | also matches a bare `ValueError`, handy while code moves from gather to task groups |
| `excinfo.group_contains(T, match=..., depth=...)` | true if any leaf at that depth (any depth if omitted) is a `T` |
| `except* ValueError:` inside the test | fine on 3.11+, but an unmatched type escapes as a group and fails the test with a less readable traceback |

If the public API unwraps single errors at its boundary (see
[keeping a single-exception API](cancellation-and-exception-groups.md#keeping-a-single-exception-api-for-callers)),
test the boundary with plain `pytest.raises(ProviderError)`, and test the internals with `RaisesGroup`.

## Fakes instead of asyncio mocks

Fakes used in tests must not import asyncio, or the trio param fails with errors such as
`RuntimeError: no running event loop` (see [troubleshooting-migration.md](troubleshooting-migration.md)). Build
them from anyio primitives:

```python
import anyio
import pytest


class FakeLLM:
    """Completes calls only when the test says so; records peak concurrency."""

    def __init__(self) -> None:
        self.gate = anyio.Event()
        self.in_flight = 0
        self.peak = 0

    async def complete(self, prompt: str) -> str:
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await self.gate.wait()
            return prompt.upper()
        finally:
            self.in_flight -= 1


async def fan_out(llm: FakeLLM, prompts: list[str], limit: int) -> list[str]:
    limiter = anyio.CapacityLimiter(limit)
    results: list = [None] * len(prompts)

    async def one(i: int, p: str) -> None:
        async with limiter:
            results[i] = await llm.complete(p)

    async with anyio.create_task_group() as tg:
        for i, p in enumerate(prompts):
            tg.start_soon(one, i, p)
    return results


@pytest.mark.anyio
async def test_fan_out_respects_limit_and_order():
    llm = FakeLLM()
    out: list = []

    async def run() -> None:
        out.extend(await fan_out(llm, ["a", "b", "c", "d"], limit=2))

    async with anyio.create_task_group() as tg:
        tg.start_soon(run)
        await anyio.wait_all_tasks_blocked()
        assert llm.in_flight == 2               # the limiter holds the other two back
        llm.gate.set()
    assert out == ["A", "B", "C", "D"] and llm.peak == 2
```

Notes:

- `unittest.mock.AsyncMock` is backend-neutral: awaiting it does not touch any event loop. It is fine for
  "was it called with X" checks. It has no checkpoint, though, so a fake that must be cancellable or must
  yield needs a real `await anyio.sleep(...)` / `Event.wait()` in a `side_effect`.
- A streaming fake: give the code under test the receive end of `anyio.create_memory_object_stream[str](0)`
  and push tokens from the test with `await send.send(token)`. Closing `send` ends the consumer's `async for`.
- Outbound HTTP: use `httpx.MockTransport(handler)` with `httpx.AsyncClient(transport=...)`. It runs on both
  backends and needs no network.

## FastAPI, Starlette and httpx under anyio

Two ways to drive an ASGI app in tests:

| Client | Runs lifespan? | Backends | When |
|--------|----------------|----------|------|
| `fastapi.testclient.TestClient(app, backend="asyncio" or "trio")` | yes, when used as `with TestClient(app) as client:` | either, chosen by `backend=` | sync tests; it runs the app in a blocking portal on its own thread |
| `httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")` | **no**: lifespan events are never sent | the test's backend | async tests that also await other things |

Because `ASGITransport` skips lifespan, anything set up there (`app.state.http`, a task group, a limiter) is
missing and the endpoint fails with an `AttributeError`. Enter the lifespan yourself:

```python
from contextlib import asynccontextmanager

import anyio
import httpx
import pytest
from fastapi import FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.limiter = anyio.CapacityLimiter(4)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/answer")
async def answer(request: Request) -> dict:
    async with request.app.state.limiter:
        await anyio.sleep(0)
    return {"answer": 42}


@pytest.fixture
async def client():
    async with lifespan(app):                   # or app.router.lifespan_context(app)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.anyio
async def test_answer(client):
    r = await client.get("/answer")
    assert r.status_code == 200 and r.json() == {"answer": 42}
```

This runs on both backends. If the app depends on asyncpg, aiohttp or another asyncio-only client, pin that
test module to `"asyncio"`. `ASGITransport` re-raises app exceptions by default
(`raise_app_exceptions=True`), so a failing endpoint shows its real traceback instead of a 500. Pass
`raise_app_exceptions=False` to assert on the error response. More lifespan patterns:
[ai-engineering-anyio.md](ai-engineering-anyio.md).

## Threads and blocking portals in tests

- A sync test that must call async code: `anyio.run(fn, *args, backend="trio")`, or a blocking portal when
  several calls must share one loop:

```python
import anyio
from anyio.from_thread import start_blocking_portal


async def embed(text: str) -> list[float]:
    await anyio.sleep(0)
    return [float(len(text))]


def test_sync_caller_through_portal():
    with start_blocking_portal(backend="asyncio") as portal:
        assert portal.call(embed, "abc") == [3.0]
        assert portal.call(embed, "hello") == [5.0]
```

- Never call `anyio.run` from inside an async test: the loop is already running in that thread, and you get
  `RuntimeError: Already running asyncio in this thread` (or `trio`). A blocking portal started inside an
  async test does work (it runs its own loop in a new thread), but every `portal.call` blocks the test's loop,
  so the test's other tasks freeze. Inside async code, just `await`.
- Code that calls `anyio.from_thread.run` must run in a worker thread started by `to_thread.run_sync` (or be
  given a token). Called from the main test thread it raises `NoEventLoopError: Not running inside an AnyIO
  worker thread, and no event loop token was provided`.
- `trio.testing.wait_all_threads_completed()` (trio only) waits for `trio.to_thread` workers, useful after
  `abandon_on_cancel=True`.

## Warnings, leaks and the CI matrix

| Signal | Turn it into a failure |
|--------|------------------------|
| `RuntimeWarning: coroutine '...' was never awaited` (often `start_soon(f(x))` or a missing `await`) | `filterwarnings = ["error::RuntimeWarning"]` |
| unclosed memory streams, sockets, files | `error::ResourceWarning`; close streams with `async with send:` / `async with receive:` |
| asyncio "Task exception was never retrieved" | `("asyncio", {"debug": True})` param and treat logged errors as failures (e.g. with `caplog`) |
| a test that hangs | a `fail_after` guard in the test, or the `pytest-timeout` plugin as the outer net |

CI steps after a migration:

```bash
python scripts/migrate_async.py src/ --check         # no asyncio left outside "# noqa: MIG0xx" adapters
pytest -q -W error::RuntimeWarning                   # every anyio test on asyncio and trio
pytest -q -k asyncio                                 # optional: isolate a backend when triaging a failure
```

Run the trio column even for an app that ships on asyncio: it is the cheapest detector of leftover
`asyncio.*` calls, hidden ordering assumptions and swallowed cancellation.

## Checklist

- [ ] `@pytest.mark.asyncio`, `pytest_asyncio.fixture` and `event_loop` are gone; anyio owns async tests.
- [ ] `anyio_backend` is overridden in `conftest.py` with explicit params and a scope wide enough for the
      async fixtures.
- [ ] Modules with asyncio-only dependencies pin `"asyncio"`; everything else runs on both backends.
- [ ] Timeout and backoff tests use the trio + `MockClock(autojump_threshold=0)` param and assert exact
      virtual elapsed time.
- [ ] No test relies on `start_soon` order or `sleep(0)` scheduling; it uses events,
      `wait_all_tasks_blocked()` or indexed results.
- [ ] Cancellation tests assert that cleanup ran and that the cancel exception was not swallowed.
- [ ] Group errors are asserted with `pytest.RaisesGroup` or `group_contains`.
- [ ] Fakes use anyio primitives only; outbound HTTP uses `httpx.MockTransport`.
- [ ] ASGI tests either use `TestClient` as a context manager or enter the lifespan around `ASGITransport`.
- [ ] `RuntimeWarning` and `ResourceWarning` are errors in CI.
