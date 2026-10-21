# AI-Engineering Hangs

The hang shapes that show up in LLM apps, agents, RAG pipelines, embedding and batch inference jobs, eval
harnesses and GPU services, with fixes you can paste. The underlying mechanics are in
[asyncio-deadlocks.md](asyncio-deadlocks.md) and
[threading-and-multiprocessing-deadlocks.md](threading-and-multiprocessing-deadlocks.md).

## Contents

- [Timeout defaults you inherit](#timeout-defaults-you-inherit)
- [Agent loop waiting on a tool call that never returns](#agent-loop-waiting-on-a-tool-call-that-never-returns)
- [Streaming consumers that stop reading](#streaming-consumers-that-stop-reading)
- [Rate limiter semaphore leaks](#rate-limiter-semaphore-leaks)
- [GPU worker queues](#gpu-worker-queues)
- [FastAPI endpoints calling sync clients](#fastapi-endpoints-calling-sync-clients)
- [Connection pool exhaustion (vector stores, databases, HTTP)](#connection-pool-exhaustion-vector-stores-databases-http)
- [Eval harness stuck at 99%](#eval-harness-stuck-at-99)
- [Scraping and document parsing for corpora](#scraping-and-document-parsing-for-corpora)
- [Ray and Celery hung workers](#ray-and-celery-hung-workers)
- [Checklist for AI services](#checklist-for-ai-services)

## Timeout defaults you inherit

Most hangs in AI code are an `await` on the network with no effective timeout. Know your defaults:

| Client | Default | Implication |
|--------|---------|-------------|
| `requests` | **no timeout** | a silent server hangs the call forever; always pass `timeout=(connect, read)` |
| `httpx` | 5 s connect/read/write/pool | streaming responses still need an overall deadline (read timeout is per chunk) |
| `aiohttp` | 300 s total (`ClientTimeout`) | set `sock_read` for streams, `total` per request |
| LLM provider SDKs | often long (minutes) plus automatic retries | a stuck request can block a worker for 10+ minutes; set `timeout=` and `max_retries=` per call |
| `asyncio.Queue.get()`, `Event.wait()`, `Future` | **no timeout** | wrap in `asyncio.wait_for` / `asyncio.timeout` |
| `concurrent.futures` `result()` / `as_completed()` | **no timeout** | pass `timeout=` |
| `multiprocessing.Pool.map()` | **no timeout** | `map_async(...).get(timeout)`; a killed worker loses its task |

Read timeouts are per socket operation: a server that trickles one byte every 4 s never trips a 5 s read
timeout. Put an **overall deadline** around every logical operation (`asyncio.timeout(60)`, 3.11+).

## Agent loop waiting on a tool call that never returns

Symptoms: the agent prints "calling tool search_web" and nothing else; CPU idle; the task dump shows the step
task awaiting the tool coroutine, an HTTP read, or a bare `Future` from a tool runner.

Causes: a tool doing network IO without a timeout; a sync tool run with `to_thread` that blocks forever (a
thread cannot be cancelled, so the step's timeout fires but the thread lives on and holds an executor
slot); a tool-result future that the runner never resolves when the tool raises; the model calling the
same tool forever (livelock: no step budget).

```python
import asyncio
import time
from typing import Any, Awaitable, Callable, Dict

ToolFn = Callable[..., Awaitable[Any]]


async def run_tool(tools: Dict[str, ToolFn], name: str, args: dict, timeout: float) -> dict:
    """Never raises, never hangs: every outcome becomes a message the model can see."""
    fn = tools.get(name)
    if fn is None:
        return {"tool": name, "error": f"unknown tool {name!r}"}
    try:
        result = await asyncio.wait_for(fn(**args), timeout=timeout)
    except asyncio.TimeoutError:
        return {"tool": name, "error": f"timed out after {timeout}s"}
    except Exception as err:  # the agent must see tool failures, not stall on them
        return {"tool": name, "error": f"{type(err).__name__}: {err}"}
    return {"tool": name, "result": result}


async def search_web(query: str) -> str:
    await asyncio.sleep(0.01)
    return f"3 hits for {query!r}"


async def slow_sql(query: str) -> str:
    await asyncio.sleep(3600)  # a hung database
    return "never"


async def agent(plan: list, step_timeout: float = 0.2, max_steps: int = 8, deadline_s: float = 2.0) -> list:
    tools = {"search_web": search_web, "slow_sql": slow_sql}
    transcript, started = [], time.monotonic()
    for step, (name, args) in enumerate(plan):
        if step >= max_steps or time.monotonic() - started > deadline_s:
            transcript.append({"error": "step budget exhausted"})
            break
        transcript.append(await run_tool(tools, name, args, timeout=step_timeout))
    return transcript


for msg in asyncio.run(agent([("search_web", {"query": "rope scaling"}), ("slow_sql", {"query": "x"})])):
    print(msg)
# {'tool': 'search_web', 'result': "3 hits for 'rope scaling'"}
# {'tool': 'slow_sql', 'error': 'timed out after 0.2s'}
```

For **sync** tools you cannot cancel: run them in a dedicated, bounded executor (so stuck threads cannot
starve other work), give the underlying client its own timeouts, and for untrusted or crash-prone tools
(code execution, PDF parsing of hostile files) run them in a subprocess you can kill:
`await asyncio.wait_for(proc.communicate(), timeout)` then `proc.kill()` on timeout.

## Streaming consumers that stop reading

A token stream is a producer (reading the provider's SSE stream) and a consumer (your websocket, your
parser, a guardrail that decides to stop). When the consumer stops early and nobody tells the producer:
- with a bounded `asyncio.Queue` between them, the producer blocks in `put()` forever, holding the HTTP
  connection and its rate-limit permit;
- with an async generator, the generator stays suspended at `yield`; its `finally` (closing the HTTP stream)
  runs only at garbage collection or loop shutdown;
- the client disconnects from your SSE endpoint, but your handler keeps pulling tokens from the provider.

```python
import asyncio


async def provider_stream(n: int):
    """Stands in for an SDK streaming response."""
    try:
        for i in range(n):
            await asyncio.sleep(0.001)
            yield f"tok{i} "
    finally:
        print("provider stream closed")


async def pump(q: asyncio.Queue) -> None:
    async for tok in provider_stream(10_000):
        await q.put(tok)          # blocks when the consumer stops reading
    await q.put(None)


async def answer_until_guardrail() -> str:
    q: asyncio.Queue = asyncio.Queue(maxsize=8)
    producer = asyncio.create_task(pump(q), name="token-pump")
    parts = []
    try:
        while True:
            tok = await asyncio.wait_for(q.get(), timeout=10)
            if tok is None or len(parts) == 5:   # guardrail: stop early
                break
            parts.append(tok)
    finally:
        producer.cancel()                         # unblocks put(), closes the provider stream
        await asyncio.gather(producer, return_exceptions=True)
    return "".join(parts)


print(asyncio.run(answer_until_guardrail()))
# provider stream closed
# tok0 tok1 tok2 tok3 tok4
```

Rules: whoever stops consuming cancels the producer and awaits it; use `contextlib.aclosing()` (3.10+) or
`await stream.aclose()` around SDK streams; on 3.13+ `q.shutdown()` also wakes a producer blocked in
`put()`. In Starlette/FastAPI streaming endpoints, check `await request.is_disconnected()` in the generator
loop (or rely on the server cancelling the response task) and close the upstream stream in `finally`.

## Rate limiter semaphore leaks

A concurrency limiter around LLM calls that is acquired and released manually leaks a permit on every
exception between the two: a 429, a timeout, a cancellation from a parent TaskGroup. After `limit` errors,
throughput is zero and every caller waits in `acquire()` forever (starvation, DLK009).

```python
import asyncio
import random
import time


class RateLimiter:
    """Concurrency cap + requests-per-second token bucket; permits always come back."""

    def __init__(self, max_concurrency: int, rps: float) -> None:
        self._sem = asyncio.Semaphore(max_concurrency)
        self._rps = rps
        self._tokens = rps
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def _take_token(self) -> None:
        while True:
            async with self._lock:                   # never awaits anything slow while held
                now = time.monotonic()
                self._tokens = min(self._rps, self._tokens + (now - self._last) * self._rps)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait = (1 - self._tokens) / self._rps
            await asyncio.sleep(wait)                 # sleep outside the lock

    async def call(self, fn, *args, timeout: float = 30.0):
        async with self._sem:                         # released on 429s, timeouts, cancellation
            await asyncio.wait_for(self._take_token(), timeout=timeout)
            return await asyncio.wait_for(fn(*args), timeout=timeout)


async def flaky_llm(prompt: str) -> str:
    await asyncio.sleep(0.001)
    if random.random() < 0.3:
        raise RuntimeError("429 Too Many Requests")
    return prompt.upper()


async def main() -> None:
    random.seed(7)
    limiter = RateLimiter(max_concurrency=4, rps=500)
    results = await asyncio.gather(*(limiter.call(flaky_llm, f"q{i}") for i in range(40)),
                                   return_exceptions=True)
    ok = sum(isinstance(r, str) for r in results)
    print(ok + sum(isinstance(r, Exception) for r in results), "finished; permits back:", limiter._sem._value)


asyncio.run(main())  # 40 finished; permits back: 4
```

Monitor in-flight counts and "time waiting for a permit" as metrics; a permit count that only goes down
is a leak.

## GPU worker queues

The common serving shape: request handlers put `(input, future)` on a queue; one GPU worker (thread or
task) batches inputs, runs the model, and resolves the futures. Hangs come from the edges:
- the worker crashes (CUDA OOM, driver error) and the futures already queued are never resolved: every
  request waits forever;
- the worker thread resolves asyncio futures directly from its thread (not thread-safe; the loop may not
  wake);
- the bounded request queue fills while the worker is dead, so handlers block in `put()`;
- a forked worker process inherits CUDA state or a locked mutex from the parent (DLK017).

```python
import asyncio
import queue
import threading


class GpuWorker:
    """One thread owns the model; asyncio handlers submit and await. Failures fail every waiter."""

    def __init__(self, loop: asyncio.AbstractEventLoop, max_batch: int = 8) -> None:
        self.loop, self.max_batch = loop, max_batch
        self.requests: queue.Queue = queue.Queue(maxsize=256)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="gpu-worker", daemon=True)
        self.thread.start()

    async def embed(self, text: str, timeout: float = 5.0) -> list:
        if not self.thread.is_alive():
            raise RuntimeError("GPU worker is dead")
        fut = self.loop.create_future()
        self.requests.put_nowait((text, fut))           # Full -> fail fast instead of blocking the loop
        return await asyncio.wait_for(fut, timeout)

    def _run(self) -> None:
        batch = []
        try:
            while not self.stop.is_set():
                try:
                    batch = [self.requests.get(timeout=0.05)]
                except queue.Empty:
                    continue
                while len(batch) < self.max_batch:
                    try:
                        batch.append(self.requests.get_nowait())
                    except queue.Empty:
                        break
                vectors = self._model([t for t, _ in batch])  # may raise CUDA OOM
                for (_, fut), vec in zip(batch, vectors):
                    self.loop.call_soon_threadsafe(_resolve, fut, vec, None)
                batch = []
        except BaseException as err:                    # worker died: fail everything it owned
            for _, fut in batch:
                self.loop.call_soon_threadsafe(_resolve, fut, None, err)
            while True:
                try:
                    _, fut = self.requests.get_nowait()
                except queue.Empty:
                    break
                self.loop.call_soon_threadsafe(_resolve, fut, None, err)
            raise

    def _model(self, texts: list) -> list:
        if any(t == "huge" for t in texts):
            raise MemoryError("CUDA out of memory (simulated)")
        return [[float(len(t))] for t in texts]


def _resolve(fut: asyncio.Future, value, err) -> None:
    if fut.done():                                      # already timed out / cancelled
        return
    if err is not None:
        fut.set_exception(RuntimeError(f"GPU worker failed: {err}"))
    else:
        fut.set_result(value)


async def main() -> None:
    worker = GpuWorker(asyncio.get_running_loop())
    print(await asyncio.gather(worker.embed("rag"), worker.embed("tokens")))
    results = await asyncio.gather(worker.embed("huge"), worker.embed("x"), return_exceptions=True)
    print([type(r).__name__ for r in results])
    worker.stop.set()
    await asyncio.to_thread(worker.thread.join, 2)     # never join a thread on the loop thread


asyncio.run(main())
# [[3.0], [6.0]]
# ['RuntimeError', 'RuntimeError']
```

(The traceback the dying thread prints through `threading.excepthook` is expected in this demo.) In
production add a supervisor that restarts the worker, a health endpoint that reports `thread.is_alive()`,
and use the `spawn`/`forkserver` start method for GPU worker processes.

## FastAPI endpoints calling sync clients

An `async def` route runs on the event loop. A sync call inside it (`requests`, a sync OpenAI/Anthropic
client, a sync vector-DB or SQL driver, `time.sleep`, CPU-heavy tokenisation) blocks **every** request in
that worker process. Health checks time out, the load balancer marks the pod unhealthy, and it looks like a
hang.

| Route | Runs on | Use when |
|-------|---------|----------|
| `async def` + async client (`httpx.AsyncClient`, async SDK) | event loop | IO-bound, the default for LLM proxies |
| `def` (sync) | AnyIO worker thread pool (40 threads by default) | sync-only clients; beware: 40 slow calls exhaust the pool and new sync requests queue |
| `async def` + `await asyncio.to_thread(sync_call)` | default executor | one sync call inside an otherwise async route |
| CPU-heavy work | process pool via `run_in_executor` | tokenising huge documents, local model inference on CPU |

Other FastAPI hang sources: a dependency with `yield` whose cleanup blocks; a lifespan startup that awaits a
client that never connects (set connect timeouts; fail startup instead); `BackgroundTasks` running sync code
after the response (still on the thread pool); a global `asyncio.Lock` held across an upstream LLM call
(serialises every request). Detect with `PYTHONASYNCIODEBUG=1` in staging and a loop-lag metric
(schedule a callback every second and record how late it runs).

## Connection pool exhaustion (vector stores, databases, HTTP)

A pool of N connections where each leaked connection (not returned on an exception path, or held by a
cancelled task that never ran its cleanup, or held by a stream nobody closed) reduces capacity by one. At
zero, every request waits for a connection forever unless the pool has an acquire timeout. Fixes: always
`async with pool.acquire() as conn:` / `async with client.stream(...) as r:`; set the pool's acquire timeout
(`httpx.Limits` + `Timeout(pool=...)`, SQLAlchemy `pool_timeout`, asyncpg `timeout=`); export pool
in-use/idle metrics; never hold a connection across an LLM call.

## Eval harness stuck at 99%

"9,990 of 10,000 prompts done, then nothing" is almost always one of:
- a few requests with no effective timeout (stalled TCP connection, provider incident) and an
  `as_completed()`/`gather()` that waits for all of them;
- a retry loop that retries a permanently failing prompt forever (livelock);
- a worker thread/process that died, so its items were never marked done (`queue.join()` waits; `Pool.map`
  waits for the lost task);
- the progress bar counting submissions, not completions.

```python
import asyncio
import random


async def judge(prompt_id: int) -> float:
    if prompt_id in (17, 42):              # stragglers: the provider never answers
        await asyncio.sleep(3600)
    await asyncio.sleep(random.uniform(0, 0.01))
    return 1.0


async def run_eval(n: int, per_item_s: float = 0.3, concurrency: int = 32) -> dict:
    sem = asyncio.Semaphore(concurrency)
    scores, failures = {}, {}

    async def one(i: int) -> None:
        async with sem:
            for attempt in range(2):        # bounded retries
                try:
                    scores[i] = await asyncio.wait_for(judge(i), timeout=per_item_s)
                    return
                except asyncio.TimeoutError:
                    failures[i] = f"timeout after {attempt + 1} attempt(s)"
            # fall through: recorded as a failure, the run still completes

    await asyncio.gather(*(one(i) for i in range(n)))
    return {"scored": len(scores), "failed": sorted(failures)}


print(asyncio.run(run_eval(200)))  # {'scored': 198, 'failed': [17, 42]}
```

Rules: every item has a timeout and a retry budget; failures are recorded, not retried forever; the run
has a global deadline; results are written incrementally (resume instead of re-running 10,000 prompts);
progress counts completions; stragglers are reported by id at the end.

## Scraping and document parsing for corpora

- One slow host must not stall the crawl: per-host semaphores, `httpx` timeouts, an overall per-URL
  deadline, and a cap on response size (a server that streams forever).
- PDF/HTML parsers can hang or hit catastrophic regex backtracking on hostile input, holding the GIL so
  even your watchdog thread stops: parse in a `ProcessPoolExecutor` with per-document timeouts and recycle
  workers (`max_tasks_per_child`, 3.11+); on `BrokenProcessPool`, rebuild the pool and skip the document.
- `multiprocessing.Pool.map` over millions of documents: one OOM-killed worker loses its task and the map
  never returns; use `ProcessPoolExecutor` or `imap_unordered` with `AsyncResult.get(timeout)`.

## Ray and Celery hung workers

**Ray:** `ray.get(refs)` without `timeout=` waits forever on a task stuck in user code or on resources that
never free up. A single-threaded actor (default `max_concurrency=1`) that calls `ray.get` on another
method of **itself** deadlocks. Use `ray.get(ref, timeout=...)` (raises `GetTimeoutError`),
`ray.wait(refs, num_returns=..., timeout=...)`, async actors or `max_concurrency>1` for re-entrant calls,
and `ray stack` (py-spy under the hood) to dump all workers on a node. Watch for tasks requesting GPUs that
no node can satisfy: they stay pending forever (`ray status` shows pending demands).

**Celery:** set `soft_time_limit` (raises `SoftTimeLimitExceeded` inside the task so it can clean up) and
`time_limit` (kills the worker process) per task or globally; `worker_max_tasks_per_child` and
`worker_max_memory_per_child` recycle leaky workers. `celery -A app inspect active` lists what each worker
is running; py-spy the worker PID for the stack. With `acks_late=True` a task that hangs past the broker's
visibility timeout is re-delivered and may run twice: make tasks idempotent. Never call
`result.get()` inside a task (pool exhaustion: Celery refuses by default with "Never call result.get()
within a task!"; do not disable that with `disable_sync_subtasks=False`): use chains, chords or callbacks.

## Checklist for AI services

- [ ] Every provider/network call: client timeout **and** an overall `asyncio.timeout`/`wait_for` deadline
- [ ] Retries bounded by attempts and total time; permanent errors not retried
- [ ] Concurrency limits via `async with`; in-flight and waiting-for-permit metrics exported
- [ ] Streams closed with `aclosing()`/`async with`; producers cancelled when consumers stop
- [ ] Futures resolved on every path; transport/worker death fails all pending futures
- [ ] No sync clients in `async def` routes; loop-lag metric and debug mode in staging
- [ ] GPU/CPU workers supervised and restarted; spawn/forkserver for worker processes
- [ ] Eval and batch jobs: per-item timeout, failure records, global deadline, incremental results
- [ ] `install()` or faulthandler registered at startup so `kill -USR1` dumps threads and tasks
- [ ] `hang_scan.py --strict` in CI; deadlock regression tests that fail by timeout
