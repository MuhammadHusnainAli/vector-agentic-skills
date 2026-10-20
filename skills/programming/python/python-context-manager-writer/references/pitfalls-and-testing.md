# Pitfalls and Testing

Every common context-manager bug with the symptom, the cause and the fix, the
`ctx_tool.py` rule that catches it, and how to unit-test managers properly.

## Contents

- [Pitfall catalogue](#pitfall-catalogue)
- [Generator-based manager pitfalls in detail](#generator-based-manager-pitfalls-in-detail)
- [Exceptions inside `__exit__` and cleanup ordering](#exceptions-inside-__exit__-and-cleanup-ordering)
- [Generators and lazy iteration escaping the block](#generators-and-lazy-iteration-escaping-the-block)
- [Thread safety](#thread-safety)
- [Testing context managers](#testing-context-managers)
- [Detecting leaks at runtime](#detecting-leaks-at-runtime)

## Pitfall catalogue

| # | Bug | Symptom | Fix | Rule |
|---|-----|---------|-----|------|
| 1 | Resource opened without `with` | `ResourceWarning`, `Too many open files`, locked SQLite DB, zombie processes | `with` / `ExitStack` / `closing` | CTX001 |
| 2 | `close()` not in `finally` | Leak only on error paths (hard to reproduce) | `with` or `try/finally` | CTX001 |
| 3 | `lock.acquire()` without `try/finally` | Deadlock after the first exception | `with lock:` | CTX002 |
| 4 | Cleanup after `yield` not in `finally` | Transaction left open / temp dir left behind when the body raises | `try: yield ... finally:` | CTX003 |
| 5 | Two yields / yield in loop / no yield | `RuntimeError: generator didn't stop` / `didn't yield` | Exactly one `yield` per path | CTX004 |
| 6 | `__exit__` returns `True` (or `self`) | Errors silently disappear; code after `with` runs with bad state | Return `None`; suppress specific types only | CTX005 |
| 7 | `__enter__` returns nothing | `AttributeError: 'NoneType' object has no attribute ...` on the `as` variable | `return self` | CTX006 |
| 8 | `except` around `yield` without `raise` | Body errors swallowed | Re-raise | CTX007 |
| 9 | Wrong `__exit__` signature | `TypeError: __exit__() takes 3 positional arguments but 4 were given` | `(self, exc_type, exc, tb)` or `(self, *exc_info)` | CTX008 |
| 10 | `async def __exit__` / `def __aexit__` / `@contextmanager` on `async def` | `TypeError`, coroutine never awaited | Match protocol to `with`/`async with` | CTX009 |
| 11 | `with httpx.AsyncClient()` | `TypeError` / `AttributeError` | `async with` | CTX010 |
| 12 | `with threading.Lock():` | Race conditions remain | Create the lock once | CTX011 |
| 13 | `torch.no_grad()` as a statement | Memory blow-up during eval (graph recorded) | `with torch.no_grad():` | CTX012 |
| 14 | Setup inside `try` in a generator | `finally` references names never assigned → `NameError` masks the real error | Setup before `try` | — |
| 15 | Reusing a `@contextmanager` object | `RuntimeError: generator didn't yield` on second `with` | Call the function again | — |
| 16 | Returning a lazy iterator from inside `with open(...)` | `ValueError: I/O operation on closed file` | Materialise (`list(...)`) inside the block | — |
| 17 | `return` in `finally` | Silently discards the in-flight exception (3.14 warns: `SyntaxWarning`) | Never return/break/continue in `finally` | — |
| 18 | Mutable state on a shared `ContextDecorator` instance | Wrong timings / crossed spans under concurrency | Per-call state, `contextvars` | — |
| 19 | `with conn:` assumed to close (sqlite3/psycopg2) | Connection leak | `closing(conn)` + `with conn:` | — |
| 20 | `multiprocessing.Pool` exited before collecting async results | Lost results (`terminate()` on exit) | Call `.get()` inside the block | — |

## Generator-based manager pitfalls in detail

### Cleanup skipped on exception

```python
@contextmanager
def gpu_lease(device_pool):                 # BUG
    dev = device_pool.take()
    yield dev
    device_pool.give_back(dev)              # never runs if the body raises -> pool drains


@contextmanager
def gpu_lease(device_pool):                 # FIX
    dev = device_pool.take()
    try:
        yield dev
    finally:
        device_pool.give_back(dev)
```

### Swallowing by accident

```python
@contextmanager
def logged(step):                           # BUG: suppresses everything
    try:
        yield
    except Exception as exc:
        log.error("%s failed: %s", step, exc)

@contextmanager
def logged(step):                           # FIX
    try:
        yield
    except Exception as exc:
        log.error("%s failed: %s", step, exc)
        raise
```

### Setup inside try

```python
@contextmanager
def connected(dsn):                         # BUG: if connect() raises, finally hits NameError
    try:
        conn = connect(dsn)
        yield conn
    finally:
        conn.close()

@contextmanager
def connected(dsn):                         # FIX
    conn = connect(dsn)
    try:
        yield conn
    finally:
        conn.close()
```

### Yield twice

```python
@contextmanager
def with_fallback(primary, backup):         # BUG: second yield after throw()
    try:
        yield primary
    except ConnectionError:
        yield backup                        # RuntimeError: generator didn't stop after throw()
```

A context manager cannot re-run the body. Retry logic belongs in a loop
*around* the `with`, or in a function that takes a callable:

```python
def with_fallback(fn, primary, backup):
    try:
        return fn(primary)
    except ConnectionError:
        return fn(backup)
```

### StopIteration and GeneratorExit

- A `StopIteration` raised by the *body* is thrown into the generator; PEP 479
  turns it into `RuntimeError` inside the generator, and `contextlib` unwraps
  that so the original `StopIteration` propagates out of the `with`. You do not
  need to handle it, but never `return` from an `except StopIteration` around
  the `yield` (that suppresses it).
- Do not catch `GeneratorExit` around the `yield`. It is raised when the
  generator is closed without `__exit__` (e.g. `cm.__enter__()` called by hand
  and the object dropped); yielding again raises
  `RuntimeError: generator ignored GeneratorExit`.

## Exceptions inside `__exit__` and cleanup ordering

- Exceptions in `__exit__` replace the body's exception (the original survives
  as `__context__`). Log rather than raise secondary cleanup failures when an
  exception is already in flight (see
  [protocol-reference.md](protocol-reference.md#exceptions-raised-inside-__exit__)).
- Several cleanups in one `__exit__`: nest `try/finally` so each runs, or push
  them on an `ExitStack` in acquisition order (unwound LIFO).
- Order matters: close the consumer before the producer (HTTP response before
  client, cursor before connection, writer before file).
- 3.11+: with `except*`/`ExceptionGroup`, a manager may receive an
  `ExceptionGroup` (e.g. from a `TaskGroup` in its body). Use
  `exc.subgroup(...)`/`split` to check for types, or `contextlib.suppress`
  (3.12+ handles groups).

## Generators and lazy iteration escaping the block

```python
def read_chunks(path):                              # BUG
    with open(path) as f:
        return (line.strip() for line in f)         # generator escapes; file closed on return

def read_chunks(path):                              # FIX 1: materialise
    with open(path) as f:
        return [line.strip() for line in f]

def iter_chunks(path):                              # FIX 2: make the function itself a generator
    with open(path) as f:
        for line in f:
            yield line.strip()
```

FIX 2 keeps the file open until the generator is exhausted **or closed**. If
consumers may stop early, close it explicitly: `with closing(iter_chunks(p)) as it:`.
Same for async generators with `aclosing` (3.10).

Same trap with DB cursors and streaming HTTP responses: returning `r.iter_lines()`
from inside `with client.stream(...) as r:`.

## Thread safety

| Question | Answer |
|----------|--------|
| Is a `@contextmanager` function thread-safe? | Each call creates its own generator, so per-entry state is isolated. The *effects* (globals it touches) may not be. |
| Is a class-based manager thread-safe? | Only if each thread uses its own instance, or state is protected/thread-local. |
| Can I share one `threading.Lock` across `with` blocks in many threads? | Yes — that is the point. |
| Are `redirect_stdout`, `chdir`, env overrides thread-safe? | No — process-global. |
| `decimal.localcontext`, `torch.no_grad`, `torch.autocast`? | Thread-local: safe. |
| asyncio tasks? | Use `contextvars`; thread-locals are shared between tasks on one thread. |

## Testing context managers

Test these behaviours for every manager:

1. Setup happens and the `as` value is correct.
2. Teardown happens on normal exit.
3. Teardown happens when the body raises, **and the exception propagates**.
4. Teardown happens on early `return`/`break`.
5. If setup fails, teardown is not attempted on unacquired resources.
6. Reuse/re-entrancy behaves as documented.
7. Async: teardown happens on cancellation.

```python
import asyncio
import os

import pytest

from mypkg.ctx import atomic_write, temp_env, transaction


def test_temp_env_restores_on_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "real")
    with pytest.raises(ZeroDivisionError):
        with temp_env(OPENAI_API_KEY="test"):
            assert os.environ["OPENAI_API_KEY"] == "test"
            1 / 0                                         # exception must propagate...
    assert os.environ["OPENAI_API_KEY"] == "real"         # ...and state must be restored


def test_atomic_write_keeps_old_file_on_error(tmp_path):
    target = tmp_path / "manifest.json"
    target.write_text("old")
    with pytest.raises(ValueError):
        with atomic_write(target) as f:
            f.write("partial")
            raise ValueError
    assert target.read_text() == "old"
    assert list(tmp_path.iterdir()) == [target]           # no stray temp files


def test_transaction_rolls_back(mocker):
    conn = mocker.Mock()
    with pytest.raises(KeyError):
        with transaction(conn):
            raise KeyError("x")
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_cleanup_on_cancel():
    closed = []

    class Res:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            closed.append(exc[0])

    async def body():
        async with Res():
            await asyncio.sleep(10)

    async def main():
        t = asyncio.create_task(body())
        await asyncio.sleep(0)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t

    asyncio.run(main())
    assert closed == [asyncio.CancelledError]
```

Driving the protocol by hand (useful for asserting exact `__exit__` return
values):

```python
def test_exit_does_not_suppress():
    cm = SkipOnRateLimit()
    cm.__enter__()
    assert cm.__exit__(KeyError, KeyError("k"), None) is False
    assert cm.__exit__(RateLimitError, RateLimitError(), None) is True
```

Mocking a context manager returned by a factory (e.g. `httpx.Client()`):

```python
from unittest import mock

def test_fetch_uses_client(monkeypatch):
    fake_client = mock.MagicMock()
    fake_client.__enter__.return_value = fake_client       # MagicMock supports dunder config
    fake_client.get.return_value.json.return_value = {"ok": True}
    monkeypatch.setattr("mypkg.fetch.httpx.Client", lambda **kw: fake_client)
    assert fetch_status() == {"ok": True}
    fake_client.__exit__.assert_called_once()
```

`unittest.mock.AsyncMock` / `MagicMock` (3.8+) support `__aenter__`/`__aexit__`
the same way.

## Detecting leaks at runtime

| Tool | How |
|------|-----|
| `python -X dev` or `-W error::ResourceWarning` | Unclosed files/sockets become warnings/errors |
| `pytest -W error::ResourceWarning` | Fail tests that leak; add `filterwarnings = error::ResourceWarning` to config |
| `tracemalloc.start(25)` | `ResourceWarning` messages then include the allocation traceback |
| `lsof -p <pid>` / `ls /proc/<pid>/fd` | Count open descriptors in a long-running worker |
| `asyncio` debug mode (`PYTHONASYNCIODEBUG=1`) | Reports never-awaited coroutines and slow callbacks |
| `ctx_tool.py leaks src/` | Static scan before review |

```bash
python -X dev -W error::ResourceWarning -m pytest -q
python scripts/ctx_tool.py leaks src/ --strict
```
