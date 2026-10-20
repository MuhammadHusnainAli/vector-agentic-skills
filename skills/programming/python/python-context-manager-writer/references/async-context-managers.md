# Async Context Managers

`async with`, `__aenter__`/`__aexit__`, cancellation, client lifecycles,
semaphores, task groups and async generators.

## Contents

- [Protocol](#protocol)
- [Class-based async managers](#class-based-async-managers)
- [@asynccontextmanager](#asynccontextmanager)
- [Cancellation and cleanup](#cancellation-and-cleanup)
- [Concurrency limits: Semaphore and Lock](#concurrency-limits-semaphore-and-lock)
- [Cancelling background tasks on exit](#cancelling-background-tasks-on-exit)
- [TaskGroup and timeout (3.11)](#taskgroup-and-timeout-311)
- [HTTP client lifecycle: httpx and aiohttp](#http-client-lifecycle-httpx-and-aiohttp)
- [Async generators need aclosing](#async-generators-need-aclosing)
- [Dual sync/async managers](#dual-syncasync-managers)
- [Common async mistakes](#common-async-mistakes)

## Protocol

```python
async with EXPR as TARGET:
    BODY
```

is equivalent to:

```python
manager = EXPR
aexit = type(manager).__aexit__
value = await type(manager).__aenter__(manager)
try:
    TARGET = value
    BODY
except BaseException as exc:
    if not await aexit(manager, type(exc), exc, exc.__traceback__):
        raise
else:
    await aexit(manager, None, None, None)
```

| Rule | Detail |
|------|--------|
| `__aenter__`/`__aexit__` must be `async def` (or return awaitables) | A plain `def __aexit__` returning `False` makes `await False` fail with `TypeError`. |
| `async with` only works inside `async def` | (or an async REPL / Jupyter top level) |
| Truthy return from `__aexit__` suppresses | Same as sync |
| `async with` on a sync-only manager fails | `TypeError: 'X' object does not support the asynchronous context manager protocol` (3.11+ wording). |
| `with` on an async-only manager fails | `TypeError` (`httpx.AsyncClient`, `aiohttp.ClientSession`, `asyncio.Lock` (3.9+ removed `with await lock`)) |

## Class-based async managers

```python
from types import TracebackType
from typing import Optional, Type

import asyncpg


class VectorTxn:
    """asyncpg transaction around pgvector writes."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def __aenter__(self) -> asyncpg.Connection:
        self._conn = await self._pool.acquire()
        try:
            self._tx = self._conn.transaction()
            await self._tx.start()
        except BaseException:
            await self._pool.release(self._conn)   # __aexit__ will not run
            raise
        return self._conn

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        try:
            if exc_type is None:
                await self._tx.commit()
            else:
                await self._tx.rollback()
        finally:
            await self._pool.release(self._conn)


async def upsert_chunks(pool, chunks) -> None:
    async with VectorTxn(pool) as conn:
        await conn.executemany(
            "INSERT INTO chunks (id, text, embedding) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO UPDATE SET text = EXCLUDED.text, embedding = EXCLUDED.embedding",
            [(c.id, c.text, c.embedding) for c in chunks],
        )
```

(asyncpg already provides `async with pool.acquire() as conn, conn.transaction():`;
the class shows the protocol.)

## @asynccontextmanager

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator


@asynccontextmanager
async def leased_connection(pool) -> AsyncIterator["asyncpg.Connection"]:
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)
```

Typing: `AsyncIterator[T]` (or `AsyncGenerator[T, None]`). A plain `def` with
`@asynccontextmanager`, or an `async def` with `@contextmanager`, is a bug
(`ctx_tool.py` CTX009).

## Cancellation and cleanup

`asyncio.CancelledError` is a `BaseException` (3.8+). When a task is cancelled
while inside `async with`, the error is raised at the current `await` in the
body, then `__aexit__` runs with it.

| Concern | Guidance |
|---------|----------|
| Never swallow `CancelledError` | `except Exception` does not catch it (good); `except BaseException` / bare `except` must re-raise. |
| Cleanup that awaits can be cancelled again | If cleanup **must** finish (release a lease, write a checkpoint), use `asyncio.shield` and keep it short. |
| `asyncio.timeout()` / `wait_for` cancel the inner task | Cleanup inside the body's managers still runs. |
| Uncancel semantics (3.11) | Code that catches `CancelledError` to do cleanup then continues should call `task.uncancel()`; most code should simply re-raise. |

```python
import asyncio


class Lease:
    def __init__(self, broker, job_id: str) -> None:
        self.broker, self.job_id = broker, job_id

    async def __aenter__(self) -> "Lease":
        await self.broker.claim(self.job_id)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # The job must be released even if we are being cancelled; shield the await
        # so a second cancellation does not interrupt the release request itself.
        await asyncio.shield(self.broker.release(self.job_id))
```

Note: `shield` protects the inner coroutine, but the outer `await` still raises
`CancelledError` if cancelled again; the release keeps running in the background.

## Concurrency limits: Semaphore and Lock

```python
import asyncio

EMBED_LIMIT = asyncio.Semaphore(16)        # create ONCE, share across tasks
                                           # (3.10+: no loop binding at construction)


async def embed_one(client, text: str) -> list[float]:
    async with EMBED_LIMIT:                # acquire; release guaranteed
        resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
        return resp.data[0].embedding


async def embed_all(client, texts: list[str]) -> list[list[float]]:
    return await asyncio.gather(*(embed_one(client, t) for t in texts))
```

Rules:

- `async with asyncio.Semaphore(16):` inside the function creates a new
  semaphore per call — no limit at all (CTX011).
- Never `await sem.acquire()` without `try/finally: sem.release()` (CTX002).
- `BoundedSemaphore` raises if released more than acquired — catches double
  release bugs.
- Python 3.9: asyncio primitives created at import time bind to the loop that
  first uses them in some versions; on 3.9 prefer creating them inside
  `async def main()` and passing them down. 3.10+ removed the `loop` binding.

Rate limiting (requests per second) is different from concurrency limiting;
see the `semaphore` recipe printed by `ctx_tool.py scaffold --recipe semaphore`
which combines both.

## Cancelling background tasks on exit

A common agent pattern: start a heartbeat / token-refresh / progress task for
the lifetime of a block, and make sure it dies with the block.

```python
import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable


@asynccontextmanager
async def background(fn: Callable[[], Awaitable[None]], interval: float) -> AsyncIterator[asyncio.Task]:
    async def loop() -> None:
        while True:
            await fn()
            await asyncio.sleep(interval)

    task = asyncio.create_task(loop())
    try:
        yield task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task                    # wait for it to actually stop


async def run_long_agent(session) -> None:
    async with background(session.heartbeat, interval=10):
        await session.run_steps()
```

If the task may have failed with a real error before cancellation, inspect it:
`if task.done() and not task.cancelled() and task.exception(): log...`.

## TaskGroup and timeout (3.11)

`asyncio.TaskGroup` is an async context manager that waits for all child tasks
and cancels the rest when one fails, raising an `ExceptionGroup`.

```python
import asyncio


async def answer_with_tools(question: str) -> dict:
    async with asyncio.timeout(30):                 # 3.11+: cancels the block on expiry
        async with asyncio.TaskGroup() as tg:       # 3.11+
            web = tg.create_task(search_web(question))
            docs = tg.create_task(search_vector_store(question))
            sql = tg.create_task(query_warehouse(question))
    return {"web": web.result(), "docs": docs.result(), "sql": sql.result()}


try:
    result = asyncio.run(answer_with_tools("Q3 revenue by region?"))
except* TimeoutError:                                # 3.11+ except*
    ...
```

Notes: `asyncio.timeout` raises `TimeoutError` (builtin) out of the block.
Pre-3.11 use `asyncio.wait_for(coro, 30)` and `asyncio.gather(..., return_exceptions=False)`
plus manual cancellation. Exceptions from a `TaskGroup` arrive wrapped in an
`ExceptionGroup`, so handle them with `except*`.

## HTTP client lifecycle: httpx and aiohttp

Creating a client per request throws away connection pooling (TLS handshake per
call, often +50–200 ms to an LLM API) and leaks sockets if not closed.

| Pattern | When |
|---------|------|
| `async with httpx.AsyncClient() as client:` around a batch | Scripts, jobs, notebooks |
| One client created in FastAPI `lifespan`, closed after `yield` | Services |
| Client owned by a wrapper class with `aclose()` + `__aenter__/__aexit__` | SDK-style wrappers |

```python
import httpx


class ChatClient:
    """Thin LLM API wrapper that owns its HTTP pool."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(60.0, connect=5.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def complete(self, messages: list[dict], model: str) -> str:
        r = await self._http.post("/v1/chat/completions", json={"model": model, "messages": messages})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "ChatClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()
```

aiohttp: `ClientSession` must be created inside a running loop and closed with
`await session.close()`; responses must be released (`async with session.get(...) as r:`).

```python
import aiohttp


async def fetch_all(urls: list[str]) -> list[str]:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def one(url: str) -> str:
            async with session.get(url) as r:      # releases the connection back to the pool
                r.raise_for_status()
                return await r.text()
        return await asyncio.gather(*(one(u) for u in urls))
```

Streaming responses (`httpx` `client.stream(...)`) are themselves context
managers; leaving them un-exited leaks the connection:

```python
async with client.stream("POST", "/v1/chat/completions", json=payload) as r:
    async for line in r.aiter_lines():
        handle(line)
```

## Async generators need aclosing

An async generator abandoned mid-iteration is not finalized immediately; its
`finally` runs later (via the loop's asyncgen hooks) or never, if the loop
closes first. Wrap generators that hold resources:

```python
from contextlib import aclosing   # 3.10+


async def read_events(stream):
    async with aclosing(sse_events(stream)) as events:
        async for ev in events:
            if ev.type == "done":
                break
```

## Dual sync/async managers

Some resources are used from both worlds (a tracing span, a timer). Implement
both protocols on one class; keep shared logic in plain methods.

```python
import time


class Span:
    def __init__(self, name: str) -> None:
        self.name = name

    def _start(self) -> "Span":
        self.t0 = time.perf_counter()
        return self

    def _end(self, exc: BaseException | None) -> None:   # 3.10+ union syntax; use Optional on 3.9
        status = "error" if exc else "ok"
        export(self.name, time.perf_counter() - self.t0, status)

    def __enter__(self) -> "Span":
        return self._start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self._end(exc)

    async def __aenter__(self) -> "Span":
        return self._start()

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._end(exc)
```

Never call blocking cleanup (e.g. `requests` or a sync DB driver) inside
`__aexit__`; it stalls the event loop. Offload with `await asyncio.to_thread(fn)` (3.9+).

## Common async mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `with httpx.AsyncClient()` | `TypeError` / `AttributeError: __enter__` | `async with` |
| Forgetting `await` on `client.aclose()` | "coroutine was never awaited" warning, socket leak | `await client.aclose()` |
| New `AsyncClient` per request | Latency, `Too many open files` | One client per app/batch |
| `async with asyncio.Semaphore(n)` inside the worker | No limiting | Create once, share |
| Swallowing `CancelledError` in `__aexit__` | Task cannot be cancelled; shutdown hangs | Return falsy; re-raise |
| Blocking I/O in `__aexit__` | Event loop stalls | `asyncio.to_thread` |
| Fire-and-forget `create_task` without keeping a reference | Task garbage-collected mid-run; errors lost | Keep tasks in a set or `TaskGroup`, cancel on exit |
| `asyncio.run()` inside a running loop (Jupyter) | `RuntimeError` | `await` directly |
