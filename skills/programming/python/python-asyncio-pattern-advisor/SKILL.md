---
name: python-asyncio-pattern-advisor
description: "Recommend, implement and review Python asyncio patterns: async vs threads vs processes (IO vs CPU-bound), coroutines vs tasks vs futures, TaskGroup, gather and return_exceptions, wait and as_completed, Semaphore and Queue worker pools with backpressure, asyncio.timeout vs wait_for, cancellation, shield and cleanup, token-bucket RPM/TPM rate limits for LLM APIs, retries with backoff and jitter, async generators and SSE token streaming, to_thread/run_in_executor, background task references, eager tasks, asyncio.run/Runner, uvloop, Jupyter, FastAPI async vs def routes, httpx.AsyncClient lifespan, async DB/vector-store clients, debug mode and pytest-asyncio. Use when the user writes or reviews async def code, fans out LLM/embedding/scraping calls, hits 429s, sees 'coroutine was never awaited', 'Task exception was never retrieved', 'asyncio.run() cannot be called from a running event loop', 'This event loop is already running', hangs, slow callbacks or tasks that will not cancel, or asks gather vs TaskGroup."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python Asyncio Pattern Advisor

Pick the right concurrency tool for the workload, then write asyncio code that stays correct under load and
failure: bounded fan-out instead of 10,000 simultaneous LLM calls, rate limits that respect both requests per
minute and tokens per minute, timeouts and cancellation that actually stop work and clean up, no blocking calls
on the event loop, no background task left without an owner, and tests that are deterministic. Every
recommendation comes with runnable code, and `scripts/async_lint.py` catches the mechanical mistakes statically.

## Trigger Conditions

Activate this skill when the user:
- Writes or reviews `async def` code, or asks whether to use asyncio, threads or processes for a job
- Fans out LLM, embedding, reranking, scraping or vector-store calls, and needs concurrency limits, RPM/TPM rate
  limiting, retries with backoff, or partial-failure handling
- Streams tokens (SSE, WebSocket, async generators) or builds producer/consumer pipelines with `asyncio.Queue`
- Sees `RuntimeWarning: coroutine '...' was never awaited`, `Task exception was never retrieved`,
  `Task was destroyed but it is pending!`, `asyncio.run() cannot be called from a running event loop`,
  `This event loop is already running`, `Executing <Task ...> took 1.2 seconds`, `Unclosed client session`
- Has a hang, deadlock, Ctrl+C that does nothing, a timeout that does not fire, or a task that will not cancel
- Builds FastAPI/Starlette endpoints (async vs sync `def`), lifespan-managed clients, or async DB pools
- Runs asyncio inside Jupyter, needs `asyncio.Runner`/uvloop, or tests async code with pytest-asyncio/anyio

## Workflow

```
1. DIAGNOSE  -> What is the workload: network/disk wait (IO-bound) or Python computation (CPU-bound)?
                How many items, what latency per item, what provider limits (RPM, TPM, connections)?
                Run: python scripts/async_lint.py <path> to find blocking calls and lost tasks
2. CHOOSE    -> Tool from the tables below: asyncio / threads / processes; TaskGroup / gather / as_completed /
                Queue workers; Semaphore and/or token bucket; timeout scope; retry policy
3. IMPLEMENT -> Own every task (TaskGroup or a referenced set), bound concurrency, put a timeout on every
                network await, re-raise CancelledError, close clients with async with / lifespan
4. HARDEN    -> Partial failure (which items failed, retry or report), shutdown/Ctrl+C, backpressure,
                logging with task names, metrics (in-flight, queue depth, 429 count, latency)
5. VERIFY    -> python scripts/async_lint.py <path> --strict  (exit 0)
                PYTHONASYNCIODEBUG=1 run to surface slow callbacks and unawaited coroutines
                pytest with fakes: success, partial failure, timeout, cancellation paths
```

## Is Async the Right Tool?

| Workload | Best tool | Why |
|----------|-----------|-----|
| Many concurrent network calls (LLM APIs, embeddings, scraping, vector DB) | asyncio | Thousands of waits on one thread, cheap tasks |
| A few blocking SDK calls with no async client | `asyncio.to_thread` / `ThreadPoolExecutor` | Keeps the loop free, no rewrite |
| CPU-bound Python (PDF parsing, chunking, tokenizing big corpora, regex over GBs) | `ProcessPoolExecutor` (or `InterpreterPoolExecutor`, 3.14) | The GIL serializes Python bytecode across threads |
| CPU-bound in C extensions that release the GIL (NumPy, tokenizers, torch ops) | Threads | Real parallelism without pickling |
| GPU inference | One worker (thread/process) per device fed by a queue, batch requests | Do not run model forward passes on the loop |
| Simple script, < 20 sequential calls, latency irrelevant | Plain sync code | Async adds complexity for nothing |
| Free-threaded build (3.13 experimental, 3.14 supported) | Threads for CPU work become parallel | Check every C extension supports it first |

Rule of thumb: async gives concurrency while **waiting**; it never makes computation faster. A single
`json.loads` of a 50 MB file or a sentence-transformer forward pass on the loop blocks every other task.

## Situation -> Right Tool

| Situation | Use | Notes |
|-----------|-----|-------|
| Run N coroutines, all must succeed, 3.11+ | `asyncio.TaskGroup` | First failure cancels the rest, raises `ExceptionGroup` |
| Run N coroutines, collect successes and failures | `gather(..., return_exceptions=True)` | Check every result with `isinstance(r, BaseException)` |
| Process results as they finish (progress bar, early stop) | `asyncio.as_completed` (`async for` in 3.13+) | Results arrive out of order |
| First result wins (hedged requests, model fallback race) | `asyncio.wait(..., return_when=FIRST_COMPLETED)` then cancel the rest | Always cancel and await losers |
| Thousands of items, limited concurrency | `Semaphore` around the call, or N workers on a bounded `Queue` | Queue workers also give backpressure |
| Provider RPM/TPM limits | Token bucket(s) + Semaphore + honour `Retry-After` | Concurrency limit alone does not cap rate |
| Deadline over several awaits | `async with asyncio.timeout(s)` (3.11+) | `wait_for` for one awaitable / 3.9-3.10 |
| Cleanup that must finish even if cancelled | `try/finally` + `asyncio.shield` only for the commit | Re-raise `CancelledError` |
| Blocking library call | `await asyncio.to_thread(fn, *args)` | Default executor size is `min(32, cpu + 4)` |
| CPU-heavy step in an async pipeline | `loop.run_in_executor(process_pool, fn, arg)` | Arguments and results must pickle |
| Fire-and-forget (usage logging, cache warm) | Keep a reference in a set + `add_done_callback(discard)` | Or a supervised TaskGroup in lifespan |
| Stream tokens to a client | async generator + `StreamingResponse` / SSE | Handle client disconnect (cancellation) |
| App-lifetime clients/pools | FastAPI `lifespan` + `app.state` | One `httpx.AsyncClient` per upstream, not per request |
| Entry point | `asyncio.run(main())` or `asyncio.Runner` (3.11) | Never inside a running loop (Jupyter: `await main()`) |

## Core Rules

1. **Never block the loop.** No `time.sleep`, `requests`, sync DB drivers, `subprocess.run`, big file reads or
   CPU loops in `async def`; use async clients or `asyncio.to_thread`.
2. **Every coroutine is awaited, every task has an owner.** Prefer `TaskGroup`; otherwise keep the task in a
   collection, await it, or attach a done callback that logs its exception.
3. **Bound every fan-out.** `gather(*[call(x) for x in items])` over unbounded input means unbounded sockets,
   memory and 429s. Use a `Semaphore` or a fixed worker pool on a bounded `Queue`.
4. **Every network await has a deadline.** Client timeouts (`httpx.Timeout`) plus an overall
   `asyncio.timeout` for the operation.
5. **Cancellation must propagate.** Catch `asyncio.CancelledError` only to clean up, then `raise`. Never
   `except BaseException: pass` or bare `except:` in async code.
6. **Partial failure is explicit.** Decide per job: all-or-nothing (`TaskGroup`) or best-effort
   (`return_exceptions=True` + check + report which items failed).
7. **Retry only transient errors** (429, 5xx, timeouts, connection resets) with exponential backoff + full
   jitter, a cap on attempts and total time, and `Retry-After` honoured.
8. **Close what you open.** `async with` for clients, sessions, files, streams; app-lifetime resources in a
   lifespan with `aclose()` in `finally`.
9. **One loop per thread, created by `asyncio.run`/`Runner`.** No `get_event_loop()` in new code, no nested
   `asyncio.run`, no `run_until_complete` inside coroutines.
10. **Use asyncio primitives in async code.** `asyncio.Lock/Event/Queue/Semaphore`, never `threading.Lock` held
    across an `await` or `queue.Queue.get()` on the loop.

## Coroutines, Tasks and Futures

| Object | Created by | Runs when | Typical use |
|--------|------------|-----------|-------------|
| Coroutine | calling an `async def` | only when awaited or wrapped in a task | sequential steps |
| Task | `tg.create_task(coro)`, `asyncio.create_task(coro)` | scheduled immediately, runs at next loop iteration (or eagerly, 3.12 eager factory) | concurrency |
| Future | `loop.create_future()`, `run_in_executor` | resolved by someone calling `set_result`/`set_exception` | bridging callbacks/threads |

`await coro()` does **not** create concurrency; two awaits in a row run one after the other. Concurrency
starts when you create tasks (directly or through `gather`/`TaskGroup`).

## Structured Concurrency

```python
import asyncio


async def fetch_chunk_summaries(chunks: list[str]) -> list[str]:
    async with asyncio.TaskGroup() as tg:              # 3.11+
        tasks = [tg.create_task(summarize(c), name=f"summarize-{i}") for i, c in enumerate(chunks)]
    return [t.result() for t in tasks]                  # all succeeded, in input order


async def best_effort(chunks: list[str]) -> tuple[list[str], list[tuple[str, BaseException]]]:
    results = await asyncio.gather(*(summarize(c) for c in chunks), return_exceptions=True)
    ok = [r for r in results if not isinstance(r, BaseException)]
    failed = [(c, r) for c, r in zip(chunks, results) if isinstance(r, BaseException)]
    return ok, failed
```

| API | Failure behaviour | Cancels siblings? | Result order |
|-----|-------------------|-------------------|--------------|
| `TaskGroup` (3.11) | raises `ExceptionGroup` of all failures (handle with `except*`) | yes, on first failure | input order via `t.result()` |
| `gather()` | first exception propagates to the awaiter; others keep running | **no** | input order |
| `gather(return_exceptions=True)` | exceptions returned as values | no | input order |
| `wait(return_when=...)` | never raises task exceptions; you inspect `done` | no | sets |
| `as_completed()` | each await raises that task's exception | no | completion order |

`gather` without `return_exceptions` leaves the other tasks running after the first failure; if you return
early they become orphans. On 3.9/3.10 emulate a TaskGroup by cancelling and awaiting the rest on failure
(see [patterns-catalog.md](references/patterns-catalog.md)).

## Bounded Concurrency and Backpressure

Runnable: 20 fake LLM calls, at most 5 in flight.

```python
import asyncio
import random

MAX_IN_FLIGHT = 5
in_flight = peak = 0


async def fake_llm(prompt: str) -> str:
    global in_flight, peak
    in_flight += 1
    peak = max(peak, in_flight)
    await asyncio.sleep(random.uniform(0.01, 0.03))   # network latency stand-in
    in_flight -= 1
    return prompt.upper()


async def run_all(prompts: list[str]) -> list[str]:
    sem = asyncio.Semaphore(MAX_IN_FLIGHT)

    async def bounded(p: str) -> str:
        async with sem:
            return await fake_llm(p)

    return await asyncio.gather(*(bounded(p) for p in prompts))


answers = asyncio.run(run_all([f"q{i}" for i in range(20)]))
print(len(answers), answers[:3], "peak in flight:", peak)
# Output: 20 ['Q0', 'Q1', 'Q2'] peak in flight: 5
```

A Semaphore still creates one task per item. For 1M documents use a fixed worker pool on a **bounded** queue,
so the producer waits when workers fall behind (backpressure):

```python
async def ingest(paths: list[str], n_workers: int = 8) -> None:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=n_workers * 2)

    async def worker() -> None:
        while True:
            path = await queue.get()
            try:
                await embed_and_upsert(path)
            except Exception:
                logger.exception("ingest failed for %s", path)   # one bad doc must not kill the worker
            finally:
                queue.task_done()

    async with asyncio.TaskGroup() as tg:
        workers = [tg.create_task(worker()) for _ in range(n_workers)]
        for p in paths:
            await queue.put(p)        # blocks while the queue is full
        await queue.join()            # every item processed
        for w in workers:
            w.cancel()                # workers loop forever; cancel them so the group can exit
```

On 3.13+ `queue.shutdown()` replaces the cancel step: workers get `asyncio.QueueShutDown` from `get()`.

## Timeouts and Cancellation

```python
async def answer(question: str) -> str:
    try:
        async with asyncio.timeout(30):                 # 3.11+: one deadline for the whole operation
            context = await retrieve(question)
            return await generate(question, context)
    except TimeoutError:                                # asyncio.TimeoutError is TimeoutError since 3.11
        logger.warning("answer timed out", extra={"question_len": len(question)})
        raise


async def stream_to_client(prompt: str):
    stream = await open_stream(prompt)
    try:
        async for token in stream:
            yield token
    except asyncio.CancelledError:
        logger.info("client went away")                 # log, then let cancellation continue
        raise
    finally:
        await stream.aclose()                           # runs on success, error and cancellation
```

- `asyncio.timeout` cancels the inner work and converts that cancellation into `TimeoutError` at the block
  boundary; it requires 3.11. On 3.9/3.10 use `asyncio.wait_for(coro, timeout)` (one awaitable).
- `asyncio.shield(x)` protects `x` from cancellation of the *awaiter*; the awaiter still gets `CancelledError`.
  Use it for "finish writing this batch to the vector store", not as a general escape hatch.
- Cancellation is cooperative: a task is only cancelled at an `await`. A CPU loop with no awaits cannot be
  cancelled or timed out.
- Full semantics (uncancel, cancelling(), cleanup ordering, signals, Ctrl+C) are in
  [cancellation-timeouts-and-errors.md](references/cancellation-timeouts-and-errors.md).

## Rate Limits and Retries

Concurrency limits cap simultaneous requests; providers limit **rate** (requests per minute) and **tokens per
minute**. Use both: a Semaphore for sockets/memory, a token bucket for RPM, a second bucket charged with the
estimated prompt + max output tokens for TPM, and on 429 sleep for `Retry-After` before retrying with jittered
backoff. Ready-to-use `TokenBucket`, `DualRateLimiter`, adaptive (AIMD) concurrency and retry helpers are in
[concurrency-limits-and-rate-limiting.md](references/concurrency-limits-and-rate-limiting.md).

```python
async def call_with_limits(req: dict, limiter: "DualRateLimiter", sem: asyncio.Semaphore) -> dict:
    est_tokens = estimate_tokens(req["messages"]) + req.get("max_tokens", 512)
    async with sem:
        await limiter.acquire(tokens=est_tokens)      # waits until both RPM and TPM budgets allow
        return await with_retry(lambda: client.chat(req), attempts=6, base=1.0, cap=60.0)
```

## Streaming and Async Generators

- Produce tokens with an async generator; consume with `async for`. Close generators you stop early with
  `contextlib.aclosing(gen)` (3.10) so their `finally` runs promptly.
- In FastAPI return `StreamingResponse(gen(), media_type="text/event-stream")` and format SSE frames as
  `f"data: {json.dumps(chunk)}\n\n"`; a client disconnect cancels the generator, so clean up in `finally`.
- Fan-in several streams with a queue (each producer task puts tokens, the consumer reads until all producers
  report done). Examples in [ai-engineering-async.md](references/ai-engineering-async.md).

## Calling Blocking Code

| Blocking thing | Do this |
|----------------|---------|
| Sync SDK call (no async client) | `await asyncio.to_thread(client.call, arg)` |
| File read/write | `await asyncio.to_thread(path.read_text)` or `aiofiles` / `anyio.Path` |
| CPU-heavy function | `await loop.run_in_executor(process_pool, fn, arg)` (pool created once) |
| Sync DB driver | async driver (`asyncpg`, `psycopg` async, `aiosqlite`, `redis.asyncio`) or `to_thread` |
| `subprocess.run` | `asyncio.create_subprocess_exec` + `await proc.communicate()` |
| Thread wants to call async code | `asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)` |
| Thread wants to wake the loop | `loop.call_soon_threadsafe(event.set)` |

`to_thread` cannot be cancelled once the function is running: the await is cancelled, the thread keeps going.

## Background Tasks

The loop keeps only weak references to tasks. An unreferenced task can be garbage-collected mid-flight and its
exception is reported only as `Task exception was never retrieved`.

```python
background: set[asyncio.Task] = set()


def spawn(coro, *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    background.add(task)
    task.add_done_callback(background.discard)
    task.add_done_callback(_log_failure)
    return task


def _log_failure(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logger.error("background task %s failed", task.get_name(), exc_info=task.exception())
```

On shutdown cancel and await what is left: `for t in background: t.cancel()` then
`await asyncio.gather(*background, return_exceptions=True)`. Eager tasks (3.12,
`loop.set_task_factory(asyncio.eager_task_factory)`) start running synchronously inside `create_task` until
their first suspension; they speed up cache-hit-heavy code but change ordering, so test before enabling.

## Event Loop Lifecycle

| Situation | Do |
|-----------|----|
| Script / CLI | `asyncio.run(main())`: creates loop, runs, cancels leftovers, shuts down executor, closes loop |
| Several top-level calls sharing one loop (3.11+) | `with asyncio.Runner() as runner: runner.run(a()); runner.run(b())` |
| uvloop | `uvloop.run(main())` or, 3.12+, `asyncio.run(main(), loop_factory=uvloop.new_event_loop)` |
| Jupyter / IPython (loop already running) | `await main()` directly in a cell; `asyncio.run` raises RuntimeError |
| Sync library function must call async code | Run it in a worker thread with its own `asyncio.run`, or expose an async API |
| Inside a coroutine, need the loop | `asyncio.get_running_loop()` |

## FastAPI and Clients

- `async def` route: runs on the loop. Everything awaited must be non-blocking.
- `def` route: runs in a threadpool (40 threads by default via anyio). Fine for blocking SDKs, but each
  request holds a thread; never call `asyncio.run` inside it.
- Create clients once in `lifespan`, store on `app.state`, close in `finally`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5),
                                       limits=httpx.Limits(max_connections=100, max_keepalive_connections=20))
    app.state.db = await asyncpg.create_pool(DSN, min_size=2, max_size=10)
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.db.close()
```

Size client pools to your Semaphore: a Semaphore of 64 with `max_connections=10` just queues inside the client
(and its pool timeout fires). Async vector-store/DB clients and per-request dependency patterns are in
[ai-engineering-async.md](references/ai-engineering-async.md).

## Symptom -> Cause -> Fix

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `coroutine '...' was never awaited` | called `async def` without `await` | `await` it or wrap in a task you own (AIO007) |
| `Task exception was never retrieved` | task failed, nobody awaited it | TaskGroup, or done-callback that logs (AIO008/AIO020) |
| `Task was destroyed but it is pending!` | loop closed (or task GC'd) with tasks still running | keep references; cancel and await on shutdown |
| `asyncio.run() cannot be called from a running event loop` | nested `asyncio.run` / Jupyter | `await` instead (AIO009) |
| `This event loop is already running` | `run_until_complete` inside a coroutine | `await` (AIO011) |
| Everything stalls for seconds, `Executing <Task> took 2.1 seconds` | blocking call on the loop | async client or `to_thread` (AIO001-006) |
| Throughput no better than sequential | awaits in a for loop; or a global lock; or pool size 1 | gather/TaskGroup + Semaphore (AIO013) |
| Burst of 429s, then bans | unbounded fan-out, no rate limiter | Semaphore + token bucket + Retry-After (AIO012) |
| Memory grows during ingestion | unbounded queue or creating all tasks up front | bounded queue + workers (AIO021) |
| Timeout never fires | CPU loop with no await, or blocking call | `to_thread`/process pool; add awaits |
| Ctrl+C / timeout ignored, shutdown hangs | `CancelledError` swallowed | re-raise (AIO014) |
| `Unclosed client session` / too many open files | client per request, never closed | `async with` / lifespan (AIO019) |
| Silent wrong data in results | `return_exceptions=True` results not checked | filter `BaseException` (AIO022) |

Hangs, slow callbacks and lost tasks: [debugging-asyncio.md](references/debugging-asyncio.md).

## Testing

```python
import pytest


@pytest.mark.asyncio                      # pytest-asyncio; or asyncio_mode = "auto" in config
async def test_partial_failure_is_reported():
    async def flaky(x: int) -> int:
        if x == 3:
            raise ValueError("bad doc")
        return x * 2

    results = await asyncio.gather(*(flaky(i) for i in range(5)), return_exceptions=True)
    assert [r for r in results if not isinstance(r, BaseException)] == [0, 2, 4, 8]
    assert isinstance(results[3], ValueError)
```

Use fakes with `asyncio.sleep(0)` instead of real latency, `asyncio.Event` to order steps deterministically,
and test the timeout and cancellation paths explicitly. Full guide: [testing-async-code.md](references/testing-async-code.md).

## Output Format

When advising or reviewing, answer with:
1. **Diagnosis** - workload type (IO/CPU), scale (items, latency, provider limits), and the concrete problems,
   each with location and AIO rule id when the linter flags it.
2. **Recommendation** - the tool chosen from the tables above and why the alternatives lose.
3. **Code** - complete, runnable before/after: bounded concurrency, timeouts, cancellation-safe cleanup,
   owned tasks, explicit partial-failure handling. State the minimum Python version (3.9 baseline; tag 3.11+,
   3.12+, 3.13+, 3.14+ features).
4. **Failure modes covered** - timeout, cancellation, partial failure, 429/backpressure, shutdown; what is
   logged and measured.
5. **Verification** - `async_lint.py --strict` result, debug-mode run, and the tests to add.

## Scripts

```bash
# Static asyncio linter (AST only; never imports or runs the code)
python scripts/async_lint.py src/rag_service/
python scripts/async_lint.py app/llm_client.py --json
cat worker.py | python scripts/async_lint.py -
python scripts/async_lint.py src/ tests/ --strict                     # exit 1 on any finding (CI gate)
python scripts/async_lint.py src/ --target-version 3.9                # flags TaskGroup/timeout use (AIO024)
python scripts/async_lint.py src/ --select AIO001,AIO008,AIO014       # ids, id prefixes or names
python scripts/async_lint.py src/ --ignore sequential-await-loop,AIO017 --min-severity medium
python scripts/async_lint.py --list-rules                             # every rule with why + fix snippet
```

| Id | Name | Sev | Id | Name | Sev |
|----|------|-----|----|------|-----|
| AIO001 | blocking-sleep | high | AIO013 | sequential-await-loop | low |
| AIO002 | blocking-http | high | AIO014 | cancellation-swallowed | high |
| AIO003 | blocking-subprocess | high | AIO015 | wait-for-on-311 | low |
| AIO004 | blocking-file-io | medium | AIO016 | thread-primitive-in-async | medium |
| AIO005 | blocking-db | high | AIO017 | async-without-await | low |
| AIO006 | blocking-socket-or-input | high | AIO018 | sleep-zero-busy-wait | medium |
| AIO007 | coroutine-not-awaited | high | AIO019 | client-without-async-with | medium |
| AIO008 | dangling-task | high | AIO020 | task-never-awaited | medium |
| AIO009 | nested-asyncio-run | high | AIO021 | unbounded-queue | low |
| AIO010 | get-event-loop | medium | AIO022 | return-exceptions-unchecked | medium |
| AIO011 | run-until-complete-in-async | high | AIO023 | sync-route-asyncio-run | high |
| AIO012 | unbounded-gather | medium | AIO024 | version-feature | high |

`--target-version` (default 3.11) turns on AIO015 at 3.11+ and makes AIO024 report APIs newer than the
target. Heuristic rules (AIO012, AIO013, AIO017, AIO021, AIO022) say so in their message; silence a deliberate
case with `# noqa: AIO013`. Exit codes: 0 clean (or findings without `--strict`), 1 findings with `--strict`,
2 usage error or an unreadable/unparsable file named on the command line (files found while walking a
directory are skipped with a warning).

## Additional Resources

| File | Content |
|------|---------|
| [patterns-catalog.md](references/patterns-catalog.md) | Coroutines/tasks/futures, TaskGroup, gather, wait, as_completed, worker pools, pipelines, async generators, context managers, to_thread/executors, background tasks, eager tasks, loop lifecycle, uvloop, Jupyter |
| [cancellation-timeouts-and-errors.md](references/cancellation-timeouts-and-errors.md) | Cancellation semantics, uncancel, shield, timeout vs wait_for, cleanup on cancel, ExceptionGroup, retries with jitter, signals and graceful shutdown |
| [concurrency-limits-and-rate-limiting.md](references/concurrency-limits-and-rate-limiting.md) | Semaphores, bounded queues and backpressure, token bucket, RPM+TPM limiter, Retry-After, adaptive concurrency, connection pool sizing |
| [ai-engineering-async.md](references/ai-engineering-async.md) | LLM fan-out with limits, token streaming/SSE, embedding batches, parallel agent tool calls, eval harnesses, FastAPI lifespan clients, async DB/vector stores, CPU/GPU stages |
| [debugging-asyncio.md](references/debugging-asyncio.md) | Debug mode, slow callbacks, hangs and deadlocks, task dumps, `python -m asyncio ps/pstree` (3.14), lost exceptions, logging and metrics |
| [testing-async-code.md](references/testing-async-code.md) | pytest-asyncio, anyio plugin, IsolatedAsyncioTestCase, fakes, deterministic ordering, testing timeouts/cancellation/retries, FastAPI tests |
| [version-history.md](references/version-history.md) | asyncio changes 3.7 -> 3.14 and what to use for each target version |
