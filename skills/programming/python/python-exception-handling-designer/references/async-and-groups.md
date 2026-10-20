# Async Errors, Cancellation and Exception Groups

How exceptions behave in asyncio, how cancellation and timeouts work, and how to handle multiple concurrent
failures with `ExceptionGroup` and `except*` (3.11+). Examples use LLM fan-out, streaming and embedding jobs.

## Contents

- [1. Where exceptions go in asyncio](#1-where-exceptions-go-in-asyncio)
- [2. Cancellation](#2-cancellation)
- [3. Timeouts](#3-timeouts)
- [4. TaskGroup](#4-taskgroup)
- [5. ExceptionGroup and except*](#5-exceptiongroup-and-except)
- [6. gather, wait, as_completed](#6-gather-wait-as_completed)
- [7. Bounded fan-out with partial failure](#7-bounded-fan-out-with-partial-failure)
- [8. Async generators and streaming](#8-async-generators-and-streaming)
- [9. Background tasks and unobserved exceptions](#9-background-tasks-and-unobserved-exceptions)
- [10. Threads and processes](#10-threads-and-processes)
- [11. Shutdown and signals](#11-shutdown-and-signals)
- [12. 3.9/3.10 compatibility](#12-3910-compatibility)

## 1. Where exceptions go in asyncio

| Construct | Exception surfaces |
|-----------|--------------------|
| `await coro()` | raised at the `await`, like a normal call |
| `task = asyncio.create_task(coro())` | stored in the task; raised when you `await task` or call `task.result()` |
| task never awaited | logged as "Task exception was never retrieved" at garbage collection; otherwise lost |
| `asyncio.gather(a, b)` | first exception propagates; others keep running (not cancelled) |
| `asyncio.gather(..., return_exceptions=True)` | exceptions returned as list values |
| `asyncio.TaskGroup` (3.11) | first failure cancels siblings; all failures raised together as `ExceptionGroup` |
| `loop.run_in_executor` / `asyncio.to_thread` | raised at the `await` |
| callbacks (`call_soon`, `add_done_callback`) | passed to the loop's exception handler (logged) |

## 2. Cancellation

`task.cancel()` raises `asyncio.CancelledError` at the task's current `await`. Since 3.8 it derives from
`BaseException`, so `except Exception` does not catch it. Sources of cancellation: explicit `cancel()`,
`asyncio.timeout()`/`wait_for`, a failing sibling in a `TaskGroup`, client disconnect in ASGI servers, and
shutdown of `asyncio.run()`.

Rules:
1. Catch `CancelledError` only to clean up; always `raise` at the end.
2. Prefer `finally` / `async with` for cleanup; they run on cancellation too.
3. Never `await` long operations in cleanup without a bound; a second cancel can interrupt it. Shield short
   critical writes if required.
4. Do not convert `CancelledError` into another exception or a return value.

```python
async def generate_and_store(prompt: str, conv_id: str) -> str:
    parts = []
    try:
        async for delta in llm.stream(prompt):
            parts.append(delta)
    except asyncio.CancelledError:
        # user hit "stop": persist the partial answer, then let cancellation continue
        await asyncio.shield(store.save_partial(conv_id, "".join(parts)))
        raise
    text = "".join(parts)
    await store.save(conv_id, text)
    return text
```

`asyncio.shield(aw)` protects the inner awaitable from being cancelled, but the outer `await` still raises
`CancelledError`, which is exactly what we want here.

Uncancel semantics (3.11+): structured primitives (`TaskGroup`, `asyncio.timeout`) use `task.cancelling()` and
`task.uncancel()` to tell their own cancellations from external ones. If you catch `CancelledError` and
deliberately suppress it (rare, e.g. a supervisor), call `asyncio.current_task().uncancel()` so enclosing
timeouts keep working.

## 3. Timeouts

```python
# 3.11+
async def chat_with_deadline(messages: list, seconds: float = 30.0) -> str:
    try:
        async with asyncio.timeout(seconds):
            return await llm.chat(messages)
    except TimeoutError as err:
        raise ProviderTimeoutError(f"no response in {seconds}s", provider="openai", timeout=seconds) from err
```

| API | Version | Raises | Notes |
|-----|---------|--------|-------|
| `asyncio.timeout(s)` | 3.11 | `TimeoutError` | context manager; `asyncio.timeout_at(when)`; reschedulable via `cm.reschedule()` |
| `asyncio.wait_for(aw, s)` | all | `asyncio.TimeoutError` (= `TimeoutError` in 3.11+) | cancels the inner task and waits for it |
| `asyncio.wait(tasks, timeout=s)` | all | nothing | returns `(done, pending)`; you cancel `pending` yourself |
| `httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3))` | - | `httpx.ConnectTimeout`, `ReadTimeout`, ... | prefer client-level timeouts for I/O |
| SDK `timeout=` (openai/anthropic) | - | `APITimeoutError` | SDKs also retry internally (`max_retries`) |

Layer timeouts: per-attempt timeout (client) < per-call deadline including retries (`asyncio.timeout`) <
request timeout (server). Streaming needs an idle timeout between chunks too:

```python
async def stream_with_idle_timeout(agen, idle: float = 15.0):
    it = agen.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(it.__anext__(), idle)
        except StopAsyncIteration:
            return
        except asyncio.TimeoutError as err:
            raise StreamInterruptedError(f"no tokens for {idle}s", provider="x") from err
        yield chunk
```

## 4. TaskGroup

```python
async def embed_corpus(batches: list) -> list:
    async with asyncio.TaskGroup() as tg:                       # 3.11+
        tasks = [tg.create_task(embedder.embed(b)) for b in batches]
    return [vec for t in tasks for vec in t.result()]
```

Semantics:
- When any task raises (non-`CancelledError`), the group cancels all remaining tasks and the body.
- After all tasks finish, the group raises `ExceptionGroup` containing every non-cancellation failure.
- Even a single failure arrives wrapped: `ExceptionGroup("unhandled errors in a TaskGroup", [err])`.
- `KeyboardInterrupt`/`SystemExit` in a child still cancel the siblings, but are then re-raised as
  themselves instead of a group.

TaskGroup is all-or-nothing. For partial success, catch inside each task:

```python
async def embed_one_batch(i: int, batch: list, results: dict, failures: dict) -> None:
    try:
        results[i] = await embedder.embed(batch)
    except ProviderError as err:            # expected per-batch failure: record, do not cancel siblings
        failures[i] = err


async def embed_tolerant(batches: list):
    results, failures = {}, {}
    async with asyncio.TaskGroup() as tg:
        for i, b in enumerate(batches):
            tg.create_task(embed_one_batch(i, b, results, failures))
    return results, failures
```

## 5. ExceptionGroup and except*

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(search_vectors(query))
        tg.create_task(search_keywords(query))
        tg.create_task(fetch_user_profile(user_id))
except* VectorStoreError as eg:
    logger.warning("vector search failed: %s", [str(e) for e in eg.exceptions])
    raise RetrievalError("retrieval degraded") from eg
except* (TimeoutError, ProviderTimeoutError) as eg:
    raise ProviderTimeoutError(f"{len(eg.exceptions)} lookups timed out", provider="mixed") from eg
```

| Behaviour | Detail |
|-----------|--------|
| Matching | each `except*` clause receives the **sub-group** of matching leaves (`eg` is always a group) |
| Multiple clauses | every matching clause runs (unlike `except`, which runs at most one) |
| Unmatched leaves | re-raised automatically as a group after all clauses run |
| Naked exceptions | `except* ValueError` also catches a bare `ValueError`, wrapped into a group |
| Forbidden | `except* ExceptionGroup`, mixing `except` and `except*` in one `try`, `break`/`continue`/`return` inside `except*` |
| Raising inside | a new exception raised in an `except*` clause is chained and grouped with the unhandled rest |

Working with groups directly:

```python
eg = ExceptionGroup("batch failed", [RateLimitError("429", provider="a"), ValueError("bad chunk")])

rate_limited, rest = eg.split(RateLimitError)      # (matching group or None, rest or None)
only_values = eg.subgroup(ValueError)              # matching group or None


def iter_leaves(group):
    """Flatten nested exception groups into leaf exceptions."""
    for exc in group.exceptions:
        if isinstance(exc, BaseExceptionGroup):
            yield from iter_leaves(exc)
        else:
            yield exc


leaves = list(iter_leaves(eg))
```

`split`/`subgroup` also accept a predicate: `eg.split(lambda e: getattr(e, "retryable", False))`.
Subclass `ExceptionGroup` and override `derive()` if your group carries extra attributes, so `split` keeps them.

Raise your own group when you collect independent failures (validation of many items, closing many clients):

```python
def validate_tools(tools: list) -> None:
    errors = []
    for t in tools:
        try:
            validate_tool_schema(t)
        except ValueError as err:
            err.add_note(f"tool={t.get('name')!r}")
            errors.append(err)
    if errors:
        raise ExceptionGroup(f"{len(errors)} invalid tool schemas", errors)
```

## 6. gather, wait, as_completed

```python
results = await asyncio.gather(*(classify(doc) for doc in docs), return_exceptions=True)
ok = [r for r in results if not isinstance(r, BaseException)]
failed = [(d, r) for d, r in zip(docs, results) if isinstance(r, BaseException)]
for doc, err in failed:
    logger.warning("classify failed for %s", doc.id, exc_info=err)
```

| Tool | On failure | Pick when |
|------|------------|-----------|
| `TaskGroup` | cancel siblings, raise group | all results required |
| `gather()` | raise first, others keep running unobserved | legacy code; prefer TaskGroup |
| `gather(return_exceptions=True)` | exceptions as values (also `CancelledError`!) | partial success |
| `wait(FIRST_EXCEPTION)` | returns early with `done/pending` | custom policies |
| `as_completed()` | each `await` raises its task's error | stream results as they finish |

With `return_exceptions=True`, check `isinstance(r, BaseException)` (not `Exception`), otherwise a cancelled
child's `CancelledError` is treated as a result.

## 7. Bounded fan-out with partial failure

```python
async def summarise_all(docs: list, concurrency: int = 8) -> dict:
    sem = asyncio.Semaphore(concurrency)
    results: dict = {}
    errors: dict = {}

    async def one(doc) -> None:
        async with sem:
            try:
                results[doc.id] = await with_retry(lambda: llm.summarise(doc.text))
            except (ProviderError, StructuredOutputError) as err:
                errors[doc.id] = err

    async with asyncio.TaskGroup() as tg:
        for d in docs:
            tg.create_task(one(d))

    if errors and not results:
        raise ExceptionGroup("every summary failed", list(errors.values()))
    return {"results": results, "failed": {k: repr(v) for k, v in errors.items()}}
```

Expected, per-item errors are caught inside the task; unexpected ones (bugs) still cancel the group and
surface.

## 8. Async generators and streaming

- An exception raised inside the generator propagates to the consumer's `async for`.
- If the consumer stops early (`break`, exception, cancellation), the generator receives `GeneratorExit` at
  its current `yield` when closed. Do not `yield` in response; just clean up.
- Async generators are closed by the event loop's asyncgen hooks later unless you close them; use
  `contextlib.aclosing()` (3.10) to close deterministically.

```python
from contextlib import aclosing


async def first_sentence(prompt: str) -> str:
    buf = ""
    async with aclosing(llm.stream(prompt)) as stream:
        async for delta in stream:
            buf += delta
            if "." in buf:
                break                 # stream is closed now, HTTP connection released
    return buf.split(".")[0] + "."
```

Server-side streaming (FastAPI `StreamingResponse`/SSE): after the first chunk, the status code is sent, so a
mid-stream failure must be reported in-band:

```python
async def sse_events(prompt: str):
    try:
        async for delta in llm.stream(prompt):
            yield f"data: {json.dumps({'delta': delta})}\n\n"
    except ProviderError as err:
        logger.exception("stream failed")
        yield f"event: error\ndata: {json.dumps({'error': err.code, 'retryable': err.retryable})}\n\n"
    yield "data: [DONE]\n\n"
```

`CancelledError` (client disconnected) is not caught there and propagates, which is correct.

## 9. Background tasks and unobserved exceptions

```python
background: set = set()


def spawn(coro, *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    background.add(task)                       # keep a strong reference: tasks can be GC'd otherwise
    task.add_done_callback(_on_done)
    return task


def _on_done(task: asyncio.Task) -> None:
    background.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background task %s failed", task.get_name(), exc_info=exc)
```

Install a loop-level handler as a last resort:

```python
def loop_exception_handler(loop, context):
    exc = context.get("exception")
    logger.error("asyncio: %s", context.get("message"), exc_info=exc)


asyncio.get_running_loop().set_exception_handler(loop_exception_handler)
```

## 10. Threads and processes

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(ocr_page, p): p for p in pages}
    for fut in as_completed(futures):
        page = futures[fut]
        try:
            text = fut.result()          # re-raises the worker's exception here
        except OCRError as err:
            logger.warning("page %s failed: %s", page, err)
```

| Context | Uncaught exception |
|---------|--------------------|
| `threading.Thread` target | printed via `threading.excepthook`; the thread dies, the main thread never knows |
| `Future.result()` | re-raised in the caller with the worker traceback attached |
| `ProcessPoolExecutor` | exception is pickled back; unpicklable exceptions cause `BrokenProcessPool`/errors - implement `__reduce__` |
| worker process killed (OOM killer) | `BrokenProcessPool` for every pending future |
| `asyncio.to_thread` | raised at the `await` |

Set `threading.excepthook` and `sys.excepthook` to route crashes into logging in long-running services.

## 11. Shutdown and signals

```python
async def main() -> None:
    server = await start_server()
    try:
        await server.serve_forever()
    finally:
        await vector_store.close()
        await llm_client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)   # asyncio.run already cancelled main(); finally blocks ran
```

Since 3.11, `asyncio.run` turns SIGINT into cancellation of the main task, so `finally` blocks and
`except CancelledError: ...; raise` cleanups run; the `KeyboardInterrupt` surfaces after cleanup.

## 12. 3.9/3.10 compatibility

| Feature | 3.9/3.10 alternative |
|---------|----------------------|
| `ExceptionGroup`, `except*` | `pip install exceptiongroup` backport: `with catch({ValueError: handler}):` |
| `asyncio.TaskGroup` | `anyio.create_task_group()` (raises exception groups via the backport) |
| `asyncio.timeout()` | `asyncio.wait_for()` or `async_timeout.timeout()` |
| `add_note` | set `__notes__` manually (printed only by 3.11+ / backport) |
| `TimeoutError` catching asyncio timeouts | catch `asyncio.TimeoutError` (subclass of `Exception` before 3.11) |

```python
try:
    from builtins import ExceptionGroup  # 3.11+
except ImportError:  # pragma: no cover
    from exceptiongroup import ExceptionGroup  # type: ignore[no-redef]
```

Catching asyncio timeouts portably: `except (asyncio.TimeoutError, TimeoutError):` works on every version.
