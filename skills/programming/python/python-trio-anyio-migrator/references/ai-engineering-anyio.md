# AI-Engineering Patterns with AnyIO

Before/after migrations of the async code that shows up in LLM apps, RAG pipelines, agents and eval
harnesses. Every "after" example runs on anyio 4.x. Network calls are faked with `anyio.sleep`, or with
`httpx.MockTransport` where httpx is used, so the examples are deterministic. They were run with anyio 4.15 on
Python 3.13, and the FastAPI example with anyio 4.14 + FastAPI 0.141 on Python 3.14.

## Contents

- [1. LLM fan-out: gather + Semaphore -> task group + CapacityLimiter](#1-llm-fan-out-gather--semaphore---task-group--capacitylimiter)
- [2. Retries, backoff and rate limits](#2-retries-backoff-and-rate-limits)
- [3. Streaming tokens through memory object streams](#3-streaming-tokens-through-memory-object-streams)
- [4. Agent tool calls with cancel scopes](#4-agent-tool-calls-with-cancel-scopes)
- [5. FastAPI background work with anyio](#5-fastapi-background-work-with-anyio)
- [6. A backend-agnostic SDK wrapper](#6-a-backend-agnostic-sdk-wrapper)
- [7. Embedding pipeline with bounded stages](#7-embedding-pipeline-with-bounded-stages)
- [8. Eval harness for thousands of prompts](#8-eval-harness-for-thousands-of-prompts)

## 1. LLM fan-out: gather + Semaphore -> task group + CapacityLimiter

Before (asyncio):

```python
import asyncio

sem = asyncio.Semaphore(8)


async def complete(prompt: str) -> str:
    async with sem:
        return await asyncio.wait_for(client.complete(prompt), timeout=30)


async def run_batch(prompts: list) -> list:
    return await asyncio.gather(*(complete(p) for p in prompts))   # one failure: others keep running
```

After (anyio):

```python
import random

import anyio


async def fake_llm(prompt: str) -> str:
    await anyio.sleep(random.uniform(0.001, 0.01))
    return f"summary of {prompt}"


async def run_batch(prompts: list, *, concurrency: int = 8, timeout: float = 30) -> list:
    limiter = anyio.CapacityLimiter(concurrency)
    results: list = [None] * len(prompts)
    peak = 0

    async def run_one(i: int, prompt: str) -> None:
        nonlocal peak
        async with limiter:
            peak = max(peak, limiter.borrowed_tokens)
            with anyio.fail_after(timeout):
                results[i] = await fake_llm(prompt)

    async with anyio.create_task_group() as tg:
        for i, prompt in enumerate(prompts):
            tg.start_soon(run_one, i, prompt, name=f"llm-{i}")
    print("peak concurrency:", peak)
    return results


out = anyio.run(run_batch, [f"doc{i}" for i in range(50)])
print(len(out), out[0])
# Output:
# peak concurrency: 8
# 50 summary of doc0
```

Why `CapacityLimiter` instead of `Semaphore`:

- it tracks borrowers, and releasing a token the task does not hold is an error;
- `borrowed_tokens` and `statistics()` are free observability;
- `limiter.total_tokens = 4` changes the limit at run time, which allows adaptive concurrency (halve it on
  429s, raise it slowly on success).

Error semantics changed on purpose: the first failure cancels the in-flight siblings. For "keep going and
report", see section 8 or the MIG012 recipe in [migration-playbook.md](migration-playbook.md).

Starting 10,000 tasks at once is fine (each is cheap), but each one holds its arguments and result slot. For
very large inputs, feed a fixed pool of workers from a memory stream (section 7).

## 2. Retries, backoff and rate limits

```python
import random

import anyio


class RateLimitError(Exception):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"429, retry after {retry_after}s")
        self.retry_after = retry_after


class TokenBucket:
    """Requests-per-minute limiter shared by all tasks (single event loop, no threads)."""

    def __init__(self, rate_per_s: float, burst: int) -> None:
        self.rate, self.capacity, self.tokens = rate_per_s, burst, float(burst)
        self.updated = anyio.current_time()
        self.lock = anyio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            while True:
                now = anyio.current_time()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                await anyio.sleep((1 - self.tokens) / self.rate)


calls = {"n": 0}


async def flaky_llm(prompt: str) -> str:
    calls["n"] += 1
    await anyio.sleep(0)
    if calls["n"] % 3 == 0:
        raise RateLimitError(retry_after=0.01)
    return prompt[::-1]


async def with_retries(prompt: str, bucket: TokenBucket, attempts: int = 4) -> str:
    for attempt in range(attempts):
        await bucket.acquire()
        try:
            with anyio.fail_after(10):
                return await flaky_llm(prompt)
        except RateLimitError as exc:
            if attempt == attempts - 1:
                raise
            await anyio.sleep(exc.retry_after or random.uniform(0, 0.05 * 2 ** attempt))
    raise AssertionError("unreachable")


async def main() -> None:
    bucket = TokenBucket(rate_per_s=500, burst=10)
    results = {}

    async def run_one(p: str) -> None:
        results[p] = await with_retries(p, bucket)

    async with anyio.create_task_group() as tg:
        for p in ["abc", "rag", "eval", "agent", "tool"]:
            tg.start_soon(run_one, p)
    print(sorted(results.values()), calls["n"] > 5)


anyio.run(main)
# Output: ['cba', 'gar', 'lave', 'loot', 'tnega'] True
```

`anyio.sleep` and `anyio.Lock` make the retry helper backend-agnostic. Cancellation passes straight
through, because `except RateLimitError` never catches the cancel exception. More rate-limit designs (RPM
plus TPM, adaptive limits) are in the
[asyncio advisor](../../python-asyncio-pattern-advisor/SKILL.md); swap `asyncio.*` for `anyio.*` as in
[api-mapping-asyncio-anyio-trio.md](api-mapping-asyncio-anyio-trio.md).

## 3. Streaming tokens through memory object streams

Before: an `asyncio.Queue()` with no maxsize between the model stream and the HTTP response. A slow client
makes the queue grow without limit, and a `None` sentinel marks the end.

After: a bounded stream. When the client is slow, the producer blocks on `send`, and that blocking
propagates backpressure to the model stream (most SDKs stop reading from the socket). Closing the send side
ends the consumer's loop.

```python
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream


async def model_stream(prompt: str):
    for token in ("Retrieval ", "augmented ", "generation ", "grounds ", "answers."):
        await anyio.sleep(0.001)
        yield token


async def produce(prompt: str, send: MemoryObjectSendStream, stats: dict) -> None:
    async with send:
        async for token in model_stream(prompt):
            if send.statistics().current_buffer_used == send.statistics().max_buffer_size:
                stats["blocked"] += 1                  # client is slower than the model
            await send.send(token)


async def sse_client(receive: MemoryObjectReceiveStream, out: list) -> None:
    async with receive:
        async for token in receive:
            await anyio.sleep(0.005)                   # slow network write
            out.append(f"data: {token}")


async def main() -> None:
    out, stats = [], {"blocked": 0}
    send, receive = anyio.create_memory_object_stream[str](max_buffer_size=2)
    async with anyio.create_task_group() as tg:
        tg.start_soon(produce, "what is RAG?", send, stats)
        tg.start_soon(sse_client, receive, out)
    print(len(out), out[-1], stats["blocked"] > 0)


anyio.run(main)
# Output: 5 data: answers. True
```

Client disconnects: in Starlette, a cancelled response task cancels the consumer, and with it the task
group. The producer gets the cancel exception at `send`, and its `async with send` closes the stream. If the
client closes only its receive side, the producer's next `send` raises `anyio.BrokenResourceError`; catch it
in the producer to stop the model call early.

Iterating the model's async generator directly inside the producer is fine. Do not `yield` from inside a task
group, though: see
[cancellation-and-exception-groups.md](cancellation-and-exception-groups.md#async-generators-and-cancel-scopes).

## 4. Agent tool calls with cancel scopes

Each tool call gets its own timeout. A failing or slow tool becomes an error message for the model instead of
failing the whole turn. The turn as a whole has a budget, and a "final answer" cancels whatever is still
running.

```python
import anyio


class Tool:
    def __init__(self, name: str, delay: float, timeout: float, error: str = "") -> None:
        self.name, self.delay, self.timeout, self.error = name, delay, timeout, error

    async def __call__(self, args: dict) -> str:
        await anyio.sleep(self.delay)
        if self.error:
            raise RuntimeError(self.error)
        return f"{self.name} ok {args}"


async def run_tool(tool: Tool, args: dict, results: dict) -> None:
    try:
        with anyio.fail_after(tool.timeout):
            results[tool.name] = {"ok": True, "content": await tool(args)}
    except TimeoutError:
        results[tool.name] = {"ok": False, "content": f"{tool.name} timed out after {tool.timeout}s"}
    except Exception as exc:                          # tool bugs become messages for the model
        results[tool.name] = {"ok": False, "content": f"{tool.name} failed: {exc}"}


async def agent_turn(calls: list, budget: float) -> dict:
    results: dict = {}
    with anyio.move_on_after(budget) as turn:         # overall budget for the turn
        async with anyio.create_task_group() as tg:
            for tool, args in calls:
                tg.start_soon(run_tool, tool, args, results, name=f"tool:{tool.name}")
    for tool, _ in calls:
        results.setdefault(tool.name, {"ok": False, "content": "cancelled: turn budget exhausted"})
    results["_budget_hit"] = turn.cancelled_caught
    return results


async def main() -> None:
    calls = [
        (Tool("search", 0.01, timeout=1), {"q": "anyio"}),
        (Tool("sql", 0.5, timeout=0.05), {"query": "select 1"}),
        (Tool("python", 0.01, timeout=1, error="NameError: x"), {"code": "x"}),
        (Tool("browse", 5, timeout=10), {"url": "https://example.com"}),
    ]
    results = await agent_turn(calls, budget=0.2)
    for name in ("search", "sql", "python", "browse"):
        print(name, results[name]["ok"], results[name]["content"])
    print("budget hit:", results["_budget_hit"])


anyio.run(main)
# Output:
# search True search ok {'q': 'anyio'}
# sql False sql timed out after 0.05s
# python False python failed: NameError: x
# browse False cancelled: turn budget exhausted
# budget hit: True
```

Stop early as soon as one tool produces a final answer: call `tg.cancel_scope.cancel()` from that tool's
wrapper (race pattern, MIG022 recipe in [migration-playbook.md](migration-playbook.md)). For tools that wrap
blocking SDKs, use `await anyio.to_thread.run_sync(fn, args, abandon_on_cancel=True)` so a turn timeout is not
held hostage by a stuck thread. The function must then be safe to abandon.

## 5. FastAPI background work with anyio

FastAPI's `BackgroundTasks` run after the response, but they live inside the request. Long-lived work, such
as index refreshes, webhook fan-out or an embedding queue, belongs in a task group owned by the application
lifespan:

```python
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

processed: list = []


async def embed_and_upsert(doc_id: str) -> None:
    await anyio.sleep(0.01)                     # embedding call + vector-store write
    processed.append(doc_id)


async def worker(receive) -> None:
    async with receive:
        async for doc_id in receive:
            await embed_and_upsert(doc_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    send, receive = anyio.create_memory_object_stream[str](max_buffer_size=100)
    async with anyio.create_task_group() as tg:
        for _ in range(4):
            tg.start_soon(worker, receive.clone())
        receive.close()
        app.state.jobs = send
        yield                                   # app serves requests here
        await send.aclose()                     # shutdown: workers drain the buffer, then exit


app = FastAPI(lifespan=lifespan)


@app.post("/documents/{doc_id}", status_code=202)
async def ingest(doc_id: str, request: Request) -> dict:
    try:
        request.app.state.jobs.send_nowait(doc_id)   # 503 instead of unbounded memory
    except anyio.WouldBlock:
        return {"queued": False}
    return {"queued": True}


with TestClient(app) as client:
    print([client.post(f"/documents/d{i}").json()["queued"] for i in range(3)])
print(sorted(processed))
# Output:
# [True, True, True]
# ['d0', 'd1', 'd2']
```

Notes:

- On shutdown the lifespan closes the send side and waits for the workers to drain. Wrap the drain in
  `with anyio.move_on_after(25):` to stay inside the orchestrator's grace period.
- `def` (sync) endpoints run in anyio's thread pool, which defaults to 40 tokens. Raise it with
  `anyio.to_thread.current_default_thread_limiter().total_tokens = 100` in the lifespan if blocking SDKs
  saturate it.
- Need an asyncio-only client (asyncpg)? Fine: FastAPI runs on the asyncio backend under uvicorn.

## 6. A backend-agnostic SDK wrapper

Rules for a library that callers may run under asyncio or trio:

1. Import only `anyio` (and `httpx`, which is anyio-based), never `asyncio`; gate with
   `migrate_async.py src/ --check` in CI.
2. Locks, events, limiters, sleeps and timeouts come from anyio.
3. No module-level event loop state. Create clients in an async context manager.
4. Test on both backends (see [testing-with-anyio-and-trio.md](testing-with-anyio-and-trio.md)).
5. Offer a sync facade with a blocking portal instead of `asyncio.run` per call.

```python
import anyio
import httpx


class EmbeddingsClient:
    """Tiny embeddings SDK wrapper: shared token refresh, retries, bounded concurrency."""

    def __init__(self, base_url: str, *, transport: httpx.AsyncBaseTransport, concurrency: int = 4) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, transport=transport)
        self._limiter = anyio.CapacityLimiter(concurrency)
        self._token_lock = anyio.Lock()
        self._token = None
        self.refreshes = 0

    async def __aenter__(self) -> "EmbeddingsClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self._http.aclose()

    async def _auth(self) -> str:
        async with self._token_lock:            # one refresh even with 100 concurrent callers
            if self._token is None:
                await anyio.sleep(0.001)
                self._token, self.refreshes = "tok-1", self.refreshes + 1
            return self._token

    async def embed(self, texts: list) -> list:
        token = await self._auth()
        async with self._limiter:
            for attempt in range(3):
                with anyio.fail_after(10):
                    resp = await self._http.post("/embed", json={"input": texts},
                                                 headers={"Authorization": f"Bearer {token}"})
                if resp.status_code != 429:
                    resp.raise_for_status()
                    return resp.json()["data"]
                await anyio.sleep(0.01 * 2 ** attempt)
            raise RuntimeError("rate limited")


def fake_api(request: httpx.Request) -> httpx.Response:
    import json
    texts = json.loads(request.content)["input"]
    return httpx.Response(200, json={"data": [[float(len(t))] for t in texts]})


async def main() -> None:
    async with EmbeddingsClient("https://api.example", transport=httpx.MockTransport(fake_api)) as client:
        out: dict = {}

        async def run_one(i: int) -> None:
            out[i] = await client.embed([f"chunk {i}", "x"])

        async with anyio.create_task_group() as tg:
            for i in range(10):
                tg.start_soon(run_one, i)
        print(len(out), out[3], "token refreshes:", client.refreshes)


anyio.run(main)                                  # also: anyio.run(main, backend="trio") with trio installed
# Output: 10 [[7.0], [1.0]] token refreshes: 1
```

The sync facade for notebooks, Celery tasks and CLIs looks like this:

```python
from anyio.from_thread import start_blocking_portal


class SyncEmbeddingsClient:
    def __init__(self, **kwargs) -> None:
        self._portal_cm = start_blocking_portal()          # one event loop thread for this client
        self._portal = self._portal_cm.__enter__()
        self._client = self._portal.call(lambda: EmbeddingsClient(**kwargs))
        self._portal.call(self._client.__aenter__)

    def embed(self, texts: list) -> list:
        return self._portal.call(self._client.embed, texts)

    def close(self) -> None:
        self._portal.call(self._client.__aexit__, None, None, None)
        self._portal_cm.__exit__(None, None, None)
```

## 7. Embedding pipeline with bounded stages

Chunk (CPU, in threads), embed (I/O, limited) and upsert (batched) become three stages connected by bounded
streams. Each stage closes its output when its input is exhausted, so the shutdown order follows the data.

```python
import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream


def chunk(doc: str) -> list:
    words = doc.split()
    return [" ".join(words[i:i + 4]) for i in range(0, len(words), 4)]


async def chunker(docs: list, out: MemoryObjectSendStream) -> None:
    async with out:
        for doc in docs:
            for piece in await anyio.to_thread.run_sync(chunk, doc):
                await out.send(piece)


async def embedder(inp: MemoryObjectReceiveStream, out: MemoryObjectSendStream,
                   limiter: anyio.CapacityLimiter) -> None:
    async with inp, out:
        async for piece in inp:
            async with limiter:
                await anyio.sleep(0.001)                       # embedding API call
                await out.send((piece, [float(len(piece))]))


async def upserter(inp: MemoryObjectReceiveStream, batch_size: int, stored: list) -> None:
    batch = []
    async with inp:
        async for item in inp:
            batch.append(item)
            if len(batch) == batch_size:
                stored.append(len(batch))
                batch = []
    if batch:
        stored.append(len(batch))                              # flush the tail


async def main() -> None:
    docs = ["one two three four five six seven eight nine"] * 5    # 3 chunks each
    stored: list = []
    chunks_send, chunks_recv = anyio.create_memory_object_stream[str](16)
    vecs_send, vecs_recv = anyio.create_memory_object_stream[tuple](16)
    limiter = anyio.CapacityLimiter(4)
    async with anyio.create_task_group() as tg:
        tg.start_soon(chunker, docs, chunks_send)
        for _ in range(3):
            tg.start_soon(embedder, chunks_recv.clone(), vecs_send.clone(), limiter)
        chunks_recv.close()
        vecs_send.close()
        tg.start_soon(upserter, vecs_recv, 4, stored)
    print("upsert batches:", stored, "total:", sum(stored))


anyio.run(main)
# Output: upsert batches: [4, 4, 4, 3] total: 15
```

When one stage fails, the task group cancels the others and the run stops with an `ExceptionGroup`. That is
usually right for ingestion jobs. Add per-item `try/except Exception` in the embedder if a single bad
document should only be logged.

## 8. Eval harness for thousands of prompts

Requirements: bounded concurrency, partial failure recorded per item, a progress counter, results written
as JSONL without blocking the loop, and a global deadline.

```python
import json

import anyio


async def judge(prompt: str) -> dict:
    await anyio.sleep(0.0005)
    if prompt.endswith("7"):
        raise ValueError("judge returned invalid JSON")
    return {"prompt": prompt, "score": len(prompt) % 5}


async def run_eval(prompts: list, path: anyio.Path, concurrency: int = 32) -> dict:
    limiter = anyio.CapacityLimiter(concurrency)
    write_lock = anyio.Lock()
    counts = {"ok": 0, "error": 0}

    async with await anyio.open_file(path, "w") as fh:
        async def run_one(prompt: str) -> None:
            async with limiter:
                try:
                    with anyio.fail_after(60):
                        row = await judge(prompt)
                    counts["ok"] += 1
                except Exception as exc:
                    row = {"prompt": prompt, "error": repr(exc)}
                    counts["error"] += 1
            async with write_lock:                     # one writer at a time: whole lines
                await fh.write(json.dumps(row) + "\n")

        with anyio.move_on_after(600) as budget:
            async with anyio.create_task_group() as tg:
                for p in prompts:
                    tg.start_soon(run_one, p)
    counts["timed_out"] = budget.cancelled_caught
    return counts


async def main() -> None:
    async with anyio.TemporaryDirectory() as tmp:
        path = anyio.Path(tmp) / "results.jsonl"
        counts = await run_eval([f"prompt-{i}" for i in range(1000)], path)
        lines = (await path.read_text()).splitlines()
    print(counts, len(lines))


anyio.run(main)
# Output: {'ok': 900, 'error': 100, 'timed_out': False} 1000
```

For 100k+ prompts, feed a fixed set of workers from a memory stream (section 7) instead of starting one task
per prompt, and write a resume file (the IDs that are done) so a crash does not repeat paid API calls.
