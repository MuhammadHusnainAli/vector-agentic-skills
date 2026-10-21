---
name: python-threadpool-executor-builder
description: "Build correct, production-grade thread-based concurrency for I/O-bound Python: ThreadPoolExecutor submit/map/as_completed/wait (FIRST_COMPLETED, FIRST_EXCEPTION), Future callbacks, shutdown(cancel_futures), default max_workers (min(32, cpu+4), process_cpu_count in 3.13), initializer, BrokenThreadPool, Little's-law sizing, bounded submission and sliding windows, map buffersize (3.14), token-bucket RPM limiting, retries with backoff and jitter, cooperative cancellation, Ctrl-C, progress, thread-safe clients (requests.Session per thread, httpx, boto3, sqlite3), locks, queues, contextvars propagation, asyncio.to_thread and run_coroutine_threadsafe, free-threading, and testing. Ships a 19-rule linter and recipes. Use when fanning out LLM, embedding, scraping, S3 or vector-store calls from sync code, building an eval harness, or on lost exceptions, 429s, memory blowups from submit loops, hangs at exit, Ctrl-C ignored, 'cannot schedule new futures after shutdown' or 'Connection pool is full'."
metadata:
  category: programming
  subcategory: python
  version: "1.0.0"
---

# Python ThreadPool Executor Builder

Build thread pools for I/O-bound work that are correct before they are fast: pick threads only when they are
the right tool, size the pool from latency and the provider's rate limit instead of guessing, bound what is
queued, make every exception surface, stop cleanly on Ctrl-C, and keep shared clients and state thread-safe.
`scripts/executor_tool.py check` finds the mechanical mistakes statically (19 rules); `scripts/executor_tool.py
scaffold` prints complete, runnable recipes (bounded map, RPM limiter, retries, progress, per-thread sessions,
graceful shutdown, context propagation, and an LLM eval harness that combines them).

## Trigger Conditions

Activate this skill when the user:
- Fans out blocking I/O from synchronous code: LLM or embedding API calls, HTTP scraping for a corpus, S3
  uploads/downloads, vector-store upserts, database reads, tool calls in a sync agent, Streamlit/Gradio callbacks
- Writes or reviews `ThreadPoolExecutor`, `executor.submit`/`map`, `as_completed`, `wait`, `Future`,
  `threading.Thread`, `threading.local`, `Lock`, `queue.Queue`, `asyncio.to_thread` or `run_in_executor`
- Builds an eval harness or batch job over thousands of prompts that must respect RPM/TPM limits
- Sees exceptions disappear, memory grow while "submitting", 429 storms, a job that ignores Ctrl-C or never
  exits, `RuntimeError: cannot schedule new futures after shutdown` / `after interpreter shutdown`,
  `BrokenThreadPool`, `Connection pool is full, discarding connection`, `SQLite objects created in a thread can
  only be used in that same thread`, request ids missing from worker logs
- Asks how many threads to use, how to add timeouts/retries/rate limits, or whether a client is thread-safe

## Workflow

```
1. CLASSIFY  -> Is the hot path waiting on I/O? (CPU-bound -> GIL skill / processes; async codebase -> asyncio)
2. MEASURE   -> p50/p95 latency per call, provider limits (RPM, TPM, concurrent), item count, payload size
3. SIZE      -> workers = target_rate x p95 latency (Little's law), capped by rate limit and connection pool
4. SHAPE     -> one executor per job/app (with-block or lifespan), bounded submission, per-thread clients
5. HARDEN    -> results AND errors collected, timeouts, retries for transient errors only, rate limiter,
               stop event + cancel_futures on Ctrl-C, contextvars copied, logs carry thread + request id
6. CHECK     -> python scripts/executor_tool.py check src/ --strict
7. VERIFY    -> deterministic tests (barriers, fake clocks), no leaked threads, measured throughput vs limit
```

## Step 1: Are Threads the Right Tool?

| Situation | Right tool | Why |
|-----------|-----------|-----|
| Sync code, tens to a few hundred concurrent blocking calls (requests, boto3, DB drivers, SDK clients) | `ThreadPoolExecutor` | Threads release the GIL while blocked in sockets; no rewrite needed |
| Already async (FastAPI `async def`, httpx.AsyncClient, thousands of connections) | asyncio, see [python-asyncio-pattern-advisor](../python-asyncio-pattern-advisor/SKILL.md) | One thread, cheap tasks, structured cancellation |
| One blocking call inside async code | `await asyncio.to_thread(fn, ...)` | Keeps the event loop free |
| Pure-Python CPU work (parsing, chunking, scoring) | Processes, see [python-multiprocessing-pool-designer](../python-multiprocessing-pool-designer/SKILL.md) | The GIL serializes bytecode; threads give no speedup |
| CPU work in numpy/torch/tokenizers (Rust)/hashlib/zlib that releases the GIL | Threads can scale; measure first | Diagnose with [python-gil-bottleneck-analyzer](../python-gil-bottleneck-analyzer/SKILL.md) |
| CPU-bound and you control the interpreter (3.13t/3.14t free-threaded build) | Threads | No GIL; check that your C extensions support it |
| Thousands of concurrent connections, long-lived streams | asyncio | Threads cost a stack each and context switches |
| Program hangs, freezes or never exits | [python-async-deadlock-debugger](../python-async-deadlock-debugger/SKILL.md) | Dump every thread before changing code |

## Step 2: The Executor API in One Screen

| Call | Behaviour that matters |
|------|------------------------|
| `ThreadPoolExecutor(max_workers=None, thread_name_prefix="", initializer=None, initargs=())` | Default workers `min(32, os.cpu_count() + 4)` (3.8-3.12), `min(32, os.process_cpu_count() + 4)` (3.13+). Threads start lazily, one per submit until the max; idle threads are reused (3.8+) |
| `submit(fn, /, *args, **kwargs) -> Future` | Never blocks: the work queue is unbounded |
| `map(fn, *iterables, timeout=None, chunksize=1, buffersize=None)` | Submits everything before returning (3.14 `buffersize=` bounds it); yields in input order; the first exception stops iteration and cancels queued items; `timeout` is a deadline for the whole iteration from the `map()` call; `chunksize` is ignored by threads |
| `as_completed(fs, timeout=None)` | Yields futures as they finish; `TimeoutError` if the whole set is not done in time |
| `wait(fs, timeout=None, return_when=ALL_COMPLETED)` | Returns `(done, not_done)`, never raises on timeout; `FIRST_COMPLETED`, `FIRST_EXCEPTION` (acts like ALL_COMPLETED if nothing raises) |
| `fut.result(timeout=None)` / `fut.exception(timeout=None)` | Re-raises the task's exception / returns it; `TimeoutError` only stops waiting, the task keeps running |
| `fut.cancel()` | Succeeds only while the task is still queued; a running task cannot be cancelled or killed |
| `fut.add_done_callback(cb)` | Runs in the worker thread that finished it, or immediately in the caller if already done; exceptions in `cb` are only logged (`exception calling callback for ...`) |
| `shutdown(wait=True, *, cancel_futures=False)` | `cancel_futures=True` (3.9+) drops queued work; `wait=False` returns early but queued work still runs |
| `initializer` fails | Pool becomes broken: pending futures and later submits raise `BrokenThreadPool` (3.7+) |
| Interpreter exit | Workers are non-daemon (3.9+) and joined by an exit hook after draining the queue: queued work delays exit |

`concurrent.futures.TimeoutError` is the builtin `TimeoutError` since 3.11. Full signatures, semantics and
version tags: [executor-api-reference.md](references/executor-api-reference.md).

## Step 3: Size the Pool from Latency and Limits

Little's law: **in-flight requests = throughput x latency**. To sustain 10 requests/s at a p95 of 2 s you need
about 20 calls in flight, so ~20-25 workers. More threads than that do nothing but queue on the rate limiter.

| Ceiling | Typical value | Consequence |
|---------|---------------|-------------|
| Provider rate limit (RPM/TPM, concurrent requests) | e.g. 500 RPM = 8.3/s | The real cap: `workers ~= rpm / 60 x p95_s x 1.2` |
| HTTP connection pool | requests `HTTPAdapter(pool_maxsize=10)`, httpx `max_connections=100` | More threads than connections: `Connection pool is full, discarding connection`, new TLS handshakes |
| Server capacity / your DB pool | DB pool size, vector DB write QPS | Match workers to it or you only add contention |
| Memory per in-flight item | documents, images, responses | Bound in-flight items, not just workers |
| Threads themselves | ~8 MB virtual stack each, scheduler cost | > 64-128 threads rarely helps; consider asyncio |

```python
def pool_size(rpm: float, p95_latency_s: float, connection_pool: int = 64, headroom: float = 1.2) -> int:
    """Workers needed to saturate a rate limit, capped by the connection pool."""
    needed = rpm / 60.0 * p95_latency_s * headroom
    return max(1, min(connection_pool, round(needed)))


print(pool_size(rpm=500, p95_latency_s=3.0))     # 30
print(pool_size(rpm=10_000, p95_latency_s=1.5))  # 64 (capped: raise the pool size or use asyncio)
```

The rate limiter, not the worker count, enforces the limit: always add a token bucket when a provider limits you.

## Step 4: Bound What You Submit

`submit()` never blocks and `map()` drains its input up front, so a loop over a 10-million-line JSONL file
queues 10 million futures before the first finishes. Keep a sliding window of at most N futures:

```python
import itertools
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def call_llm(prompt: str) -> int:
    return len(prompt)                                   # stand-in for a blocking API call


def prompts():                                           # lazy source, e.g. a JSONL reader
    for i in range(10_000):
        yield f"prompt {i}"


total, max_in_flight = 0, 64
with ThreadPoolExecutor(max_workers=16, thread_name_prefix="llm") as ex:
    source = iter(prompts())
    pending = {ex.submit(call_llm, p) for p in itertools.islice(source, max_in_flight)}
    while pending:
        done, pending = wait(pending, return_when=FIRST_COMPLETED)
        for fut in done:
            total += fut.result()                        # surfaces task exceptions
        for p in itertools.islice(source, len(done)):    # refill one slot per finished task
            pending.add(ex.submit(call_llm, p))
print(total)                                             # 108890
```

On 3.14+ `ex.map(fn, items, buffersize=64)` gives the same bound for ordered results. A
`threading.BoundedSemaphore` acquired before `submit` and released in a done-callback also works when you
cannot restructure the loop. Patterns and trade-offs (ordered vs unordered, fail-fast vs collect, semaphore vs
window vs `queue.Queue(maxsize)`): [bounding-backpressure-and-rate-limits.md](references/bounding-backpressure-and-rate-limits.md).

## Step 5: Never Lose an Exception

An exception raised in a task lives on its `Future` until someone calls `result()` or `exception()`. Every
future must be read, and every error must be kept or re-raised:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed


def embed(doc: str) -> list:
    if not doc:
        raise ValueError("empty document")
    return [float(len(doc))]


docs = ["alpha", "", "gamma"]
vectors, errors = {}, {}
with ThreadPoolExecutor(max_workers=4, thread_name_prefix="embed") as ex:
    futures = {ex.submit(embed, d): i for i, d in enumerate(docs)}
    for fut in as_completed(futures):
        i = futures[fut]
        try:
            vectors[i] = fut.result()
        except Exception as exc:                         # keep it: count, log, report, maybe retry
            errors[i] = exc
print(sorted(vectors), {i: repr(e) for i, e in errors.items()})
# [0, 2] {1: "ValueError('empty document')"}
```

| Pattern | Exceptions | Use |
|---------|-----------|-----|
| `list(ex.map(fn, items))` | First one raised, later results lost | All-or-nothing jobs, small inputs |
| `as_completed` + try/except per future | Every one kept | Batch jobs, eval harnesses, ingestion |
| `wait(fs, return_when=FIRST_EXCEPTION)` then cancel the rest | First one, fail fast | Dependent work where one failure invalidates the batch |
| `add_done_callback(cb)` | Only if `cb` calls `result()`/`exception()`; errors inside `cb` are just logged | Progress and metrics, not error handling |

## Step 6: Timeouts, Retries, Rate Limits, Cancellation

- **Threads cannot be killed.** `fut.result(timeout=5)` stops *waiting*; the call keeps running and holds a
  worker. Put the real timeout in the I/O call (`requests.get(url, timeout=(3.05, 30))`, SDK `timeout=`), and
  use a `threading.Event` that long tasks check between steps.
- **Retry only transient errors** (429, 5xx, timeouts, connection resets) with exponential backoff and full
  jitter, honouring `Retry-After`; never retry a 400 or a context-length error. Sleep with `stop.wait(delay)`,
  not `time.sleep`, so shutdown is immediate.
- **Rate limit with one shared token bucket** (RPM and, for LLMs, TPM): every attempt, including retries, takes
  a token. On a 429 with Retry-After, pause the whole bucket, not just one thread.
- **Circuit breaker** for a dependency that is down: after N consecutive failures fail fast for a cool-down.
- **Ctrl-C:** wait with a timeout in the main thread, then `stop.set()` and
  `ex.shutdown(wait=True, cancel_futures=True)`; report partial results; exit 130.

```python
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def upload(part: int, stop: threading.Event) -> int:
    for _ in range(3):                                   # long task: check the stop flag between steps
        if stop.is_set():
            raise InterruptedError(f"part {part} stopped")
        time.sleep(0.01)
    return part


stop = threading.Event()
done_parts = []
with ThreadPoolExecutor(max_workers=4) as ex:
    pending = {ex.submit(upload, p, stop) for p in range(100)}
    try:
        while pending:
            done, pending = wait(pending, timeout=0.25, return_when=FIRST_COMPLETED)   # Ctrl-C lands here
            done_parts += [f.result() for f in done]
            if len(done_parts) >= 8:
                raise KeyboardInterrupt                  # simulate Ctrl-C for this example
    except KeyboardInterrupt:
        stop.set()
        ex.shutdown(wait=True, cancel_futures=True)
        print(f"stopped: {len(done_parts) >= 8}, cancelled: {sum(f.cancelled() for f in pending) > 50}")
# stopped: True, cancelled: True
```

Retry, token bucket, circuit breaker, deadlines, partial results and Ctrl-C in full:
[reliability-timeouts-retries-cancellation.md](references/reliability-timeouts-retries-cancellation.md).
Exception hierarchy design for retryable errors: [python-exception-handling-designer](../python-exception-handling-designer/SKILL.md).

## Step 7: Thread Safety of Clients and Shared State

| Object | Share across threads? | Do this |
|--------|----------------------|---------|
| `requests.Session` | Not guaranteed (no documented thread-safety; cookies/adapters mutate) | One Session per thread: `threading.local()` filled by the executor `initializer` |
| `httpx.Client` | Designed to be shared (its pool is lock-protected) | One client per app; set `limits=httpx.Limits(max_connections=...)` >= workers |
| `openai.OpenAI` / `anthropic.Anthropic` (sync) | Built on `httpx.Client`; create once and reuse | Do not create a client per call; check your SDK version's docs; per-thread clients are the conservative choice |
| `boto3.session.Session` / resources | No | Session per thread; never create clients concurrently from the default session |
| boto3 low-level client (`session.client("s3")`) | Yes (documented) | Create it in the main thread before starting workers, then share |
| `sqlite3.Connection` | No by default (`check_same_thread=True` raises `ProgrammingError`) | Connection per thread, or one writer thread fed by a `queue.Queue` |
| DB-API drivers (psycopg, etc.) | Connections usually not; pools yes | Use the driver's thread-safe pool (`psycopg_pool.ConnectionPool`) |
| `logging` loggers and handlers | Yes (handlers lock internally) | Add `%(threadName)s`; slow handlers behind `QueueHandler` |
| `queue.Queue`, `threading.Event`, `Lock` | Yes | The building blocks for coordination |
| Module-level list/dict/counter | Single operations are atomic in CPython; compound updates (`+=`, check-then-set) race | Return values from tasks; otherwise guard with a `Lock` |
| `threading.local` values | Per thread, but persist across tasks on the same pool thread | Never store per-task state there |
| `ContextVar` values | Not propagated into pool tasks | `ex.submit(contextvars.copy_context().run, fn, *args)` |

```python
import contextvars
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

request_id = contextvars.ContextVar("request_id", default="-")
_local = threading.local()


def session() -> dict:
    """Per-thread client (a dict stands in for requests.Session())."""
    if not hasattr(_local, "s"):
        _local.s = {"owner": threading.current_thread().name}
    return _local.s


def fetch(url: str) -> str:
    return f"{request_id.get()} {url} via {session()['owner'].split('_')[0]}"


request_id.set("req-7")
with ThreadPoolExecutor(max_workers=2, thread_name_prefix="fetch", initializer=session) as ex:
    plain = ex.submit(fetch, "a").result()                        # noqa: TPE019 (the bug, for contrast)
    ctx = ex.submit(contextvars.copy_context().run, fetch, "b").result()
print(plain)   # - a via fetch
print(ctx)     # req-7 b via fetch
```

Locks, RLock, Condition, queues, contextvars and logging in depth:
[thread-safety-and-shared-state.md](references/thread-safety-and-shared-state.md).

## Step 8: Mixing Threads and asyncio

| Need | Use | Notes |
|------|-----|-------|
| Blocking call from a coroutine | `await asyncio.to_thread(fn, *args, **kwargs)` (3.9+) | Default executor; copies contextvars |
| Blocking call with your own pool/limits | `await loop.run_in_executor(pool, functools.partial(fn, **kw))` | No kwargs, no context copy (wrap with `copy_context().run`) |
| Coroutine from a worker thread | `asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)` | Never call `.result()` on the loop's own thread: deadlock |
| Notify the loop from a thread | `loop.call_soon_threadsafe(fut.set_result, value)` | asyncio objects are not thread-safe |
| Sync app that needs an async library | One loop in a background thread + `run_coroutine_threadsafe` | Start once, stop with `loop.call_soon_threadsafe(loop.stop)` |

`asyncio.run()` shuts the default executor down on exit (3.9+), waiting for running `to_thread` calls. The
loop-thread deadlocks are covered in [python-async-deadlock-debugger](../python-async-deadlock-debugger/SKILL.md).

## Step 9: Free-Threaded Builds and InterpreterPoolExecutor

- On free-threaded CPython (3.13t experimental, 3.14t officially supported but still optional) threads run
  Python bytecode in parallel, so a thread pool can speed up CPU-bound work. Data races that the GIL used to
  hide (lost `+=` updates, check-then-set) become frequent: fix TPE006 findings first. Diagnosis, scaling
  tests and extension compatibility: [python-gil-bottleneck-analyzer](../python-gil-bottleneck-analyzer/SKILL.md).
- `concurrent.futures.InterpreterPoolExecutor` (3.14) runs each worker in its own sub-interpreter with its own
  GIL: CPU parallelism in one process, but functions and arguments must be shareable (pickled), and many C
  extensions do not support sub-interpreters yet. For I/O it offers nothing over threads.

## Symptom -> Cause -> Fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job "succeeds" but rows are missing | Futures never read (TPE001), `map` not iterated (TPE005), `except Exception: pass` (TPE015) | Collect results and errors per future |
| Memory climbs while submitting, nothing finishes for minutes | Unbounded submit loop or `map` over a generator (TPE003/TPE004) | Sliding window / semaphore / `buffersize=` |
| Ctrl-C ignored, or the job keeps calling the API after Ctrl-C | Main thread blocked in `result()` with no timeout; `shutdown(wait=False)` without `cancel_futures` (TPE012) | Wait with timeouts, stop event, `cancel_futures=True` |
| Process will not exit after the work is done | Non-daemon thread never stopped (TPE017), executor never shut down (TPE002), queued work draining at exit | Join/stop threads, shut down executors, cancel queued work |
| Hang under load only | A task waits on futures of its own executor (TPE009): pool exhaustion | Separate pools per level or flatten; see the deadlock skill |
| 429 storm, then bans | Workers > rate limit, retries without jitter | Token bucket shared by all threads, backoff with full jitter |
| `Connection pool is full, discarding connection` | More threads than `pool_maxsize` on one Session/host | Raise `pool_maxsize` (HTTPAdapter) or `limits` (httpx) to >= workers |
| Wrong/duplicated counts | `+=` or check-then-set on shared state (TPE006) | Return values and aggregate, or use a Lock |
| `ProgrammingError: SQLite objects created in a thread...` | Connection shared with workers (TPE008) | Connection per thread or a writer thread |
| Logs from workers lack the request id / trace | ContextVar not propagated (TPE019) | `copy_context().run` per task |
| `RuntimeError: cannot schedule new futures after shutdown` | Submitting after `with` exit or `shutdown()` | Keep submits inside the block; app-wide executor in lifespan |
| `RuntimeError: cannot schedule new futures after interpreter shutdown` | Submitting from atexit, `__del__` or a daemon thread during exit | Stop producers before exit; join threads in `main()` |
| `BrokenThreadPool` | The `initializer` raised | Fix/guard the initializer; log its traceback (logged as "Exception in initializer") |
| 8 threads no faster than 1 | CPU-bound pure Python (TPE018), a global lock, a shared single connection, or the rate limiter | Profile; see the GIL skill; check pool and limiter |

Live debugging (thread dumps, py-spy, faulthandler, naming threads, metrics):
[debugging-thread-pools.md](references/debugging-thread-pools.md).

## AI-Engineering Patterns

| Job | Shape |
|-----|-------|
| Eval harness over 10k prompts with an RPM limit | Sliding window + token bucket + retries + results/errors per item: `scaffold --recipe llm-eval-harness` |
| Embedding a corpus via API | Batch texts (provider max batch / token limit), pool of `rpm/60 x latency` workers, TPM bucket on token counts, write vectors in input order |
| Downloading/scraping a corpus | Session per thread, per-host concurrency cap, robots/backoff, stream to disk, bounded window over the URL source |
| Vector-store upserts | Batches of 100-1000, a few workers (the DB is the ceiling), idempotent ids so retries are safe |
| S3 uploads of chunks | One boto3 client shared (created first), or `TransferConfig(max_concurrency=...)` which already uses threads |
| Parallel tool calls in a sync agent | One executor per agent process, `wait(fs, timeout=step_deadline)`, tool errors returned to the model as results |
| Streamlit / Gradio app | One cached executor (`st.cache_resource`), never a pool per rerun/click, no Streamlit calls from worker threads |

Worked, runnable versions: [ai-engineering-threadpools.md](references/ai-engineering-threadpools.md).

## Version Notes

| Version | Change |
|---------|--------|
| 3.2 | `concurrent.futures` |
| 3.5 | `max_workers` optional (default `cpu_count() * 5`); `map(chunksize=)` (ignored by threads) |
| 3.6 | `thread_name_prefix` |
| 3.7 | `initializer`/`initargs`, `BrokenThreadPool`; `contextvars` module |
| 3.8 | Default `max_workers = min(32, cpu_count() + 4)`; idle workers reused before new threads start |
| 3.9 | `shutdown(cancel_futures=True)`; workers no longer daemon threads (joined by an exit hook); `asyncio.to_thread` |
| 3.11 | `concurrent.futures.TimeoutError` is the builtin `TimeoutError` |
| 3.13 | Default `max_workers` uses `os.process_cpu_count()`; free-threaded build (experimental) |
| 3.14 | `Executor.map(buffersize=)`; `InterpreterPoolExecutor`; free-threaded build officially supported; `threading.Thread(context=)` and `sys.flags.thread_inherit_context` |

## Output Format

When building or reviewing thread-pool code, answer with:
1. **Verdict** - threads vs asyncio vs processes for this workload, with the reason (I/O wait share, library).
2. **Sizing** - workers, max in-flight, rate limit and connection pool settings, with the Little's-law arithmetic.
3. **Findings** - numbered, with location, TPE rule id when the linter flagged it, the failure it causes
   (lost data, hang, memory blowup, 429s, race) and severity.
4. **Code** - complete, runnable before/after: executor lifetime, bounded submission, result/error collection,
   timeouts, retries, rate limiter, Ctrl-C handling, per-thread clients, context propagation.
5. **Verification** - the tests to add (deterministic, see [testing-threaded-code.md](references/testing-threaded-code.md)),
   a thread-leak check, and the throughput to expect vs the provider limit.

## Scripts

```bash
# Lint (AST only; never imports or runs the analysed code)
python scripts/executor_tool.py check src/                            # files or directories
python scripts/executor_tool.py check worker.py --json                # machine-readable
cat job.py | python scripts/executor_tool.py check -                  # stdin
python scripts/executor_tool.py check src/ --strict                   # exit 1 on any finding (CI gate)
python scripts/executor_tool.py check src/ --select TPE001,TPE005 --ignore pool-size-smell
python scripts/executor_tool.py check src/ --min-severity medium
python scripts/executor_tool.py check --list-rules                    # why + fix snippet per rule (--json too)
```
Rules: TPE001 future-never-read, TPE002 executor-not-shutdown, TPE003 unbounded-submit, TPE004
map-over-generator, TPE005 map-results-unconsumed, TPE006 shared-read-modify-write, TPE007
shared-container-mutation (low), TPE008 shared-unsafe-client, TPE009 executor-self-wait, TPE010 pool-size-smell
(low), TPE011 result-without-timeout (low), TPE012 shutdown-nowait-at-exit, TPE013 daemon-thread-side-effects,
TPE014 polling-future-done, TPE015 swallowed-future-exception, TPE016 executor-per-call, TPE017
thread-not-joined, TPE018 cpu-bound-thread-pool (low), TPE019 contextvar-not-propagated. Silence a line with
`# noqa: TPE010`. Exit codes: 0 clean (or not strict), 1 findings with `--strict`, 2 usage/read/syntax error
(directory walks warn and skip unparsable files).

```bash
# Recipes: complete, typed, documented modules that run offline with stub work (verified with ast.parse)
python scripts/executor_tool.py scaffold --list
python scripts/executor_tool.py scaffold --recipe bounded-map > bounded_map.py && python bounded_map.py
python scripts/executor_tool.py scaffold --recipe llm-eval-harness --json      # {recipe, summary, code}
```
Recipes: `bounded-map`, `rate-limited`, `retrying`, `progress`, `thread-local-client`, `graceful-shutdown`
(simulates Ctrl-C, exits 130), `context-propagation`, `llm-eval-harness`. Flags: `--recipe NAME`, `--list`,
`--json`. Exit 2 for an unknown recipe or generated code that fails `ast.parse`.

## Additional Resources

| File | Content |
|------|---------|
| [executor-api-reference.md](references/executor-api-reference.md) | Every executor/Future/wait/as_completed/map detail, defaults by version, callbacks, shutdown and exit behaviour, BrokenThreadPool, threading.Thread basics |
| [bounding-backpressure-and-rate-limits.md](references/bounding-backpressure-and-rate-limits.md) | Little's law sizing, sliding windows, semaphores, bounded queues, map buffersize, token buckets for RPM/TPM, per-host limits |
| [reliability-timeouts-retries-cancellation.md](references/reliability-timeouts-retries-cancellation.md) | Per-task timeouts, cooperative cancellation, retries with jitter, circuit breaker, progress, partial results, Ctrl-C |
| [thread-safety-and-shared-state.md](references/thread-safety-and-shared-state.md) | Client thread-safety table, Lock/RLock/Condition/Event/Barrier, queue.Queue pipelines, threading.local, contextvars, logging, asyncio bridges, free-threading |
| [ai-engineering-threadpools.md](references/ai-engineering-threadpools.md) | Eval harness, embedding batching, corpus download, vector upserts, S3 chunks, parallel tool calls, Streamlit/Gradio |
| [debugging-thread-pools.md](references/debugging-thread-pools.md) | Every TPE rule with before/after, error messages explained, thread dumps, hangs at exit, slow pools, observability |
| [testing-threaded-code.md](references/testing-threaded-code.md) | Inline executors, barriers and events for determinism, fake clocks, mocking clients, leak detection, stress tests |
