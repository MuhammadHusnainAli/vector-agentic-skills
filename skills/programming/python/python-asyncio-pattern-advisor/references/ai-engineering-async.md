# Asyncio for AI Engineering

Production patterns for LLM apps, RAG pipelines, agents, eval harnesses and embedding jobs. Runnable
examples use fake clients (`asyncio.sleep` for latency) so they work offline; the structure is what you keep
when you plug in a real SDK. Limits, retries and cancellation helpers come from
[concurrency-limits-and-rate-limiting.md](concurrency-limits-and-rate-limiting.md) and
[cancellation-timeouts-and-errors.md](cancellation-timeouts-and-errors.md).

## Contents

- [A resilient async LLM client wrapper](#a-resilient-async-llm-client-wrapper)
- [Fan-out over thousands of prompts](#fan-out-over-thousands-of-prompts)
- [Streaming tokens](#streaming-tokens)
- [Server-sent events from FastAPI](#server-sent-events-from-fastapi)
- [Embedding batches](#embedding-batches)
- [Parallel tool calls in agents](#parallel-tool-calls-in-agents)
- [Eval harness with checkpoint and resume](#eval-harness-with-checkpoint-and-resume)
- [FastAPI: lifespan clients and route types](#fastapi-lifespan-clients-and-route-types)
- [Async databases and vector stores](#async-databases-and-vector-stores)
- [CPU-bound stages: parsing and chunking](#cpu-bound-stages-parsing-and-chunking)
- [GPU inference with dynamic batching](#gpu-inference-with-dynamic-batching)
- [Scraping corpora politely](#scraping-corpora-politely)
- [Checklist](#checklist)

## A resilient async LLM client wrapper

One object per provider/model that owns: concurrency limit, rate limiter, per-attempt timeout, retries for
transient errors only, and metrics. Every call site goes through it.

```python
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field


class TransientLLMError(Exception):
    def __init__(self, msg: str, retry_after: float | None = None) -> None:
        super().__init__(msg)
        self.retry_after = retry_after


class PermanentLLMError(Exception):
    pass


@dataclass
class Stats:
    calls: int = 0
    retries: int = 0
    failures: int = 0
    peak_in_flight: int = 0
    in_flight: int = field(default=0, repr=False)


class FakeTransport:
    """Stands in for an SDK: ~10% of calls get a 429, prompts containing 'bad' are rejected."""

    def __init__(self, seed: int = 7) -> None:
        self.rng = random.Random(seed)

    async def complete(self, prompt: str) -> str:
        await asyncio.sleep(self.rng.uniform(0.001, 0.005))
        if "bad" in prompt:
            raise PermanentLLMError("400 invalid request")
        if self.rng.random() < 0.1:
            raise TransientLLMError("429 rate limited", retry_after=0.001)
        return f"answer to {prompt}"


class LLMClient:
    def __init__(self, transport, *, max_concurrency: int = 16, attempt_timeout: float = 60.0,
                 attempts: int = 5) -> None:
        self.transport = transport
        self.sem = asyncio.Semaphore(max_concurrency)
        self.attempt_timeout = attempt_timeout
        self.attempts = attempts
        self.stats = Stats()

    async def complete(self, prompt: str) -> str:
        for attempt in range(self.attempts):
            try:
                async with self.sem:
                    self.stats.calls += 1
                    self.stats.in_flight += 1
                    self.stats.peak_in_flight = max(self.stats.peak_in_flight, self.stats.in_flight)
                    try:
                        async with asyncio.timeout(self.attempt_timeout):
                            return await self.transport.complete(prompt)
                    finally:
                        self.stats.in_flight -= 1
            except (TransientLLMError, TimeoutError) as err:
                if attempt == self.attempts - 1:
                    self.stats.failures += 1
                    raise
                self.stats.retries += 1
                delay = getattr(err, "retry_after", None) or random.uniform(0, min(30.0, 0.5 * 2 ** attempt))
                await asyncio.sleep(delay)          # sleep OUTSIDE the semaphore: do not hold a slot
            except PermanentLLMError:
                self.stats.failures += 1
                raise
        raise AssertionError("unreachable")


async def main() -> None:
    client = LLMClient(FakeTransport(), max_concurrency=8)
    prompts = [f"q{i}" for i in range(200)] + ["bad prompt"]
    results = await asyncio.gather(*(client.complete(p) for p in prompts), return_exceptions=True)
    ok = sum(not isinstance(r, BaseException) for r in results)
    print(ok, "ok;", "peak in flight:", client.stats.peak_in_flight, "; retried:", client.stats.retries > 0)


asyncio.run(main())
# Output: 200 ok; peak in flight: 8 ; retried: True
```

Notes:
- Backoff sleeps happen **outside** the semaphore, so a retrying call does not block a slot.
- Permanent errors (400, 401, 422, context length) fail immediately.
- With a real SDK, disable its built-in retries (`max_retries=0`) or remove yours; double retry layers
  multiply attempts (5 x 3 = 15 calls per prompt during an outage).
- Add the `DualRateLimiter` from the rate-limiting reference inside the semaphore for RPM/TPM quotas.

## Fan-out over thousands of prompts

| Input size | Pattern |
|------------|---------|
| < ~1,000 prompts | `gather` over a client that has its own Semaphore (above) |
| 1,000 - 1,000,000 | sliding window `bounded_map` (no task per item up front), stream results to disk |
| Unbounded / streaming source | worker pool on a bounded `asyncio.Queue` |
| Must survive restarts | durable queue (DB table, Redis stream, SQS) + async workers; checkpoint results |

Order: `gather` keeps input order. With `as_completed`/`bounded_map`, carry the item id with the result.

## Streaming tokens

An async generator turns a provider stream into plain tokens. Always release the HTTP response when the
consumer stops early (client disconnected, stop sequence found, moderation tripped).

```python
import asyncio
import json
from contextlib import aclosing


async def fake_sse_lines(text: str):
    """What `response.aiter_lines()` yields for an SSE chat stream."""
    for word in text.split():
        await asyncio.sleep(0)
        yield "data: " + json.dumps({"delta": word + " "})
        yield ""
    yield "data: [DONE]"


async def stream_tokens(lines):
    async with aclosing(lines) as it:              # closes the HTTP stream even on early exit
        async for line in it:
            if not line.startswith("data: "):
                continue                           # blank separators, comments, event: lines
            payload = line[len("data: "):]
            if payload == "[DONE]":
                return
            yield json.loads(payload)["delta"]


async def main() -> None:
    out = []
    async with aclosing(stream_tokens(fake_sse_lines("retrieval augmented generation works"))) as tokens:
        async for tok in tokens:
            out.append(tok)
            if "generation" in tok:
                break                              # early stop: both generators are closed
    print("".join(out).strip())


asyncio.run(main())
# Output: retrieval augmented generation
```

Stream timeouts: use an idle timeout per chunk (see the cancellation reference), not one deadline for the
whole answer. Fan-in several streams (e.g. ask three models, show whichever streams first) by having each
stream task `put` tokens onto one queue tagged with its source, and cancel the losers when you pick a winner.

## Server-sent events from FastAPI

```python
import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()


async def generate(prompt: str) -> AsyncIterator[str]:
    for tok in ("Hello", " from", " the", " model"):
        await asyncio.sleep(0.05)
        yield tok


@app.get("/chat")
async def chat(request: Request, q: str) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        try:
            async for tok in generate(q):
                if await request.is_disconnected():     # cheap check; stop paying for tokens
                    break
                yield f"data: {json.dumps({'token': tok})}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            # Raised into the generator when the server cancels the response (client gone, shutdown).
            raise
        finally:
            pass                                       # close upstream stream / record usage here

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

- `X-Accel-Buffering: no` stops nginx from buffering the stream.
- Send a comment line (`": keep-alive\n\n"`) every ~15 s on long tool runs so proxies do not cut the
  connection.
- Record token usage in `finally`, so aborted streams are billed and logged too.

## Embedding batches

Batch by item count **and** token budget, run batches with bounded concurrency, keep input order, and split a
failing batch to isolate the bad input instead of failing the whole job.

```python
from __future__ import annotations

import asyncio


class BatchTooLarge(Exception):
    pass


class BadInput(Exception):
    pass


async def embed_batch(texts: list[str]) -> list[list[float]]:
    await asyncio.sleep(0.001)
    if any(t == "<binary garbage>" for t in texts):
        raise BadInput("input 400: invalid characters")
    if sum(len(t) for t in texts) > 200:
        raise BatchTooLarge("413: batch exceeds token limit")
    return [[float(len(t))] for t in texts]


def make_batches(texts: list[str], max_items: int, max_chars: int) -> list[list[int]]:
    batches, cur, size = [], [], 0
    for i, t in enumerate(texts):
        if cur and (len(cur) >= max_items or size + len(t) > max_chars):
            batches.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += len(t)
    if cur:
        batches.append(cur)
    return batches


async def embed_all(texts: list[str], max_items: int = 8, max_chars: int = 400,
                    concurrency: int = 4) -> tuple[list[list[float] | None], dict[int, str]]:
    vectors: list[list[float] | None] = [None] * len(texts)
    errors: dict[int, str] = {}
    sem = asyncio.Semaphore(concurrency)

    async def run(idx: list[int]) -> None:
        try:
            async with sem:
                result = await embed_batch([texts[i] for i in idx])
        except (BatchTooLarge, BadInput) as err:
            if len(idx) == 1:
                errors[idx[0]] = str(err)               # isolated the bad input
                return
            mid = len(idx) // 2                          # halve and retry both parts
            await asyncio.gather(run(idx[:mid]), run(idx[mid:]))
            return
        for i, vec in zip(idx, result):
            vectors[i] = vec

    await asyncio.gather(*(run(b) for b in make_batches(texts, max_items, max_chars)))
    return vectors, errors


async def main() -> None:
    texts = [f"chunk {i} " * (i % 5 + 1) for i in range(30)]
    texts[13] = "<binary garbage>"
    vectors, errors = await embed_all(texts)
    print(sum(v is not None for v in vectors), "embedded;", errors)


asyncio.run(main())
# Output: 29 embedded; {13: 'input 400: invalid characters'}
```

Production additions: count tokens with the provider tokenizer instead of characters, write vectors to the
store in batches as they complete (bounded queue to the upsert stage), retry 429/5xx with backoff (the halving
above is only for size/content errors), and record failed ids for a re-run.

## Parallel tool calls in agents

Models can return several tool calls in one turn. Run independent calls concurrently with a per-tool timeout,
and turn every failure into a tool result the model can read; one broken tool must not cancel the others, so
catch per call instead of letting a TaskGroup cancel siblings.

```python
import asyncio
import json


async def search_docs(query: str) -> str:
    await asyncio.sleep(0.01)
    return json.dumps({"hits": [f"doc about {query}"]})


async def get_weather(city: str) -> str:
    await asyncio.sleep(1.0)                      # a hung upstream
    return "sunny"


async def run_sql(query: str) -> str:
    raise PermissionError("read-only role cannot run DELETE")


TOOLS = {"search_docs": search_docs, "get_weather": get_weather, "run_sql": run_sql}


async def execute_tool_call(call: dict, timeout: float = 0.1) -> dict:
    fn = TOOLS.get(call["name"])
    try:
        if fn is None:
            raise LookupError(f"unknown tool {call['name']!r}")
        async with asyncio.timeout(timeout):
            content = await fn(**json.loads(call["arguments"]))
        return {"tool_call_id": call["id"], "content": content}
    except Exception as err:                      # CancelledError is not an Exception: it propagates
        detail = str(err) or f"no result within {timeout}s"
        return {"tool_call_id": call["id"], "content": f"ERROR {type(err).__name__}: {detail}", "is_error": True}


async def main() -> None:
    calls = [
        {"id": "c1", "name": "search_docs", "arguments": json.dumps({"query": "refund policy"})},
        {"id": "c2", "name": "get_weather", "arguments": json.dumps({"city": "Paris"})},
        {"id": "c3", "name": "run_sql", "arguments": json.dumps({"query": "DELETE FROM users"})},
    ]
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(execute_tool_call(c), name=f"tool-{c['name']}") for c in calls]
    for t in tasks:
        r = t.result()
        print(r["tool_call_id"], r["content"])


asyncio.run(main())
# Output:
# c1 {"hits": ["doc about refund policy"]}
# c2 ERROR TimeoutError: no result within 0.1s
# c3 ERROR PermissionError: read-only role cannot run DELETE
```

Rules for agent loops:
- Keep result order aligned with the model's tool-call ids.
- Side-effecting tools (send email, write DB) should not run in parallel with each other unless the model's
  plan is order-independent; mark tools as `parallel_safe` and serialize the rest.
- Put an overall step budget (`asyncio.timeout`) around a whole agent turn and a max-iterations counter around
  the loop.
- Sync tools (a pandas query, a local file read) go through `asyncio.to_thread`.

## Eval harness with checkpoint and resume

Thousands of prompts, judge calls, flaky providers: run with a sliding window, write each result as it
arrives (JSONL), and skip finished ids on restart.

```python
import asyncio
import json
import os
import tempfile


async def model_answer(prompt: str) -> str:
    await asyncio.sleep(0.001)
    return prompt[::-1]


async def judge(prompt: str, answer: str) -> float:
    await asyncio.sleep(0.001)
    return 1.0 if answer == prompt[::-1] else 0.0


def _read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _append(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)


async def run_eval(cases: list[dict], out_path: str, concurrency: int = 16) -> float:
    done_ids = {row["id"] for row in await asyncio.to_thread(_read_rows, out_path)}   # resume
    todo = [c for c in cases if c["id"] not in done_ids]
    sem = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()

    async def one(case: dict) -> None:
        async with sem:
            answer = await model_answer(case["prompt"])
            score = await judge(case["prompt"], answer)
        line = json.dumps({"id": case["id"], "score": score}) + "\n"
        async with write_lock:                                   # one writer at a time
            await asyncio.to_thread(_append, out_path, line)    # file I/O off the loop

    await asyncio.gather(*(one(c) for c in todo))
    scores = [row["score"] for row in await asyncio.to_thread(_read_rows, out_path)]
    return sum(scores) / len(scores)


async def main() -> None:
    cases = [{"id": i, "prompt": f"prompt-{i}"} for i in range(100)]
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "results.jsonl")
        await run_eval(cases[:40], path)              # "crashed" after 40
        mean = await run_eval(cases, path)            # resume: only the remaining 60 run
        rows = await asyncio.to_thread(_read_rows, path)
        print(len(rows), "rows, mean score", mean)


asyncio.run(main())
# Output: 100 rows, mean score 1.0
```

At larger scale replace `gather` with `bounded_map` so you do not create 100k tasks, add the rate limiter per
model (answer model and judge model have separate budgets), and log cost from `usage` per row.

## FastAPI: lifespan clients and route types

| Route | Runs on | Use for |
|-------|---------|---------|
| `async def` | the event loop | async clients (httpx.AsyncClient, async SDKs, asyncpg, redis.asyncio) |
| `def` | anyio threadpool (40 threads by default) | blocking SDKs, sync DB drivers, CPU-light sync code |
| `async def` + `await asyncio.to_thread(...)` | loop + default executor | mostly-async route with one blocking call |

Never block in an `async def` route (one slow request then stalls all of them), and never call
`asyncio.run` in a `def` route (linter AIO023). Dependencies follow the same rule.

```python
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm_http = httpx.AsyncClient(
        base_url="https://llm.internal",
        timeout=httpx.Timeout(120, connect=5, pool=10),
        limits=httpx.Limits(max_connections=64, max_keepalive_connections=32),
    )
    try:
        yield
    finally:
        await app.state.llm_http.aclose()


app = FastAPI(lifespan=lifespan)


def llm_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.llm_http


@app.post("/v1/answer")
async def answer(payload: dict, http: httpx.AsyncClient = Depends(llm_http)) -> dict:
    resp = await http.post("/generate", json=payload)
    resp.raise_for_status()
    return resp.json()
```

- One `AsyncClient` per upstream for the app's lifetime: connection reuse, TLS session reuse, shared limits.
  A client per request costs a TLS handshake each time and leaks sockets if not closed (AIO019).
- Official async SDK clients (`AsyncOpenAI`, `AsyncAnthropic`, ...) are also app-lifetime objects; create them
  in lifespan and close them in `finally` (`await client.close()`).
- Request timeouts: put `asyncio.timeout` around the work inside the route; the ASGI server does not cancel a
  slow handler for you while the client is still connected.
- Long jobs (ingest a 2 GB corpus) do not belong in a request: enqueue and return 202 with a job id.

## Async databases and vector stores

| Store | Async client | Notes |
|-------|--------------|-------|
| Postgres / pgvector | `asyncpg` pool, `psycopg` 3 `AsyncConnectionPool`, SQLAlchemy 2 `AsyncEngine` | one pool per process, created in lifespan |
| Redis (cache, queues, rate limits) | `redis.asyncio.Redis` | `await r.aclose()` on shutdown (`close()` in older redis-py) |
| SQLite | `aiosqlite` | single writer; fine for local eval results |
| Qdrant | `qdrant_client.AsyncQdrantClient` | batch `upsert` with `wait=True` only when you need read-after-write |
| Elasticsearch / OpenSearch | `AsyncElasticsearch`, `opensearchpy.AsyncOpenSearch` | bulk helpers have async variants |
| MongoDB | `pymongo.AsyncMongoClient` (recent PyMongo 4.x; supersedes Motor) | |
| Chroma, FAISS, other sync-only | `asyncio.to_thread` around calls, or a dedicated worker thread | FAISS search is CPU-bound: use threads (it releases the GIL) |

Bounded, batched upserts that overlap embedding with writing:

```python
async def upsert_stage(queue: asyncio.Queue, store, batch_size: int = 256) -> None:
    batch = []
    while True:
        item = await queue.get()
        try:
            if item is None:                            # sentinel: flush and stop
                if batch:
                    await store.upsert(batch)
                return
            batch.append(item)
            if len(batch) >= batch_size:
                await store.upsert(batch)
                batch = []
        finally:
            queue.task_done()
```

Transactions: never hold a DB transaction open across an LLM call (seconds) - it pins a pooled connection and
holds locks. Read what you need, release the connection, call the model, then write in a short transaction.

## CPU-bound stages: parsing and chunking

PDF/HTML parsing, OCR post-processing, tokenizing and chunking big documents are CPU-bound. On the loop they
block everything; in threads they serialize on the GIL (unless the library releases it, or you run the
free-threaded build). Use a process pool created once:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor


def chunk_document(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    step = size - overlap
    return [text[i:i + size] for i in range(0, max(len(text) - overlap, 1), step)]


async def chunk_all(texts: list[str], pool: ProcessPoolExecutor) -> list[list[str]]:
    loop = asyncio.get_running_loop()
    return await asyncio.gather(*(loop.run_in_executor(pool, chunk_document, t) for t in texts))


async def main() -> None:
    with ProcessPoolExecutor(max_workers=2) as pool:
        chunks = await chunk_all(["x" * 1000, "y" * 120], pool)
    print([len(c) for c in chunks])


if __name__ == "__main__":
    asyncio.run(main())
# Output: [3, 1]
```

- Send small inputs (paths, ids) to workers rather than megabytes of text; pickling is not free.
- Cap in-flight submissions (sliding window) so a 1M-document job does not queue 1M futures.
- 3.14 alternatives: `InterpreterPoolExecutor` (subinterpreters) for pure-Python work; the free-threaded build
  makes plain threads parallel if all your C extensions support it.

## GPU inference with dynamic batching

A model server should not run one forward pass per request, and must not run it on the loop. Collect requests
for a few milliseconds into a batch, run the batch in a worker thread, resolve each request's future.

```python
import asyncio


class DynamicBatcher:
    def __init__(self, infer_batch, max_batch: int = 16, max_wait: float = 0.005) -> None:
        self.infer_batch = infer_batch            # sync function: list[input] -> list[output]
        self.max_batch, self.max_wait = max_batch, max_wait
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_batch * 8)
        self.batches_run = 0

    async def submit(self, x):
        fut = asyncio.get_running_loop().create_future()
        await self.queue.put((x, fut))            # backpressure when the GPU falls behind
        return await fut

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            items = [await self.queue.get()]
            deadline = loop.time() + self.max_wait
            while len(items) < self.max_batch:
                timeout = deadline - loop.time()
                if timeout <= 0:
                    break
                try:
                    async with asyncio.timeout(timeout):
                        items.append(await self.queue.get())
                except TimeoutError:
                    break
            inputs = [x for x, _ in items]
            try:
                outputs = await asyncio.to_thread(self.infer_batch, inputs)   # GPU work off the loop
            except Exception as err:
                for _, fut in items:
                    if not fut.done():
                        fut.set_exception(err)
            else:
                for (_, fut), out in zip(items, outputs):
                    if not fut.done():                                     # caller may have been cancelled
                        fut.set_result(out)
            self.batches_run += 1


def fake_model(batch: list[str]) -> list[int]:
    return [len(s) for s in batch]


async def main() -> None:
    batcher = DynamicBatcher(fake_model, max_batch=16)
    worker = asyncio.create_task(batcher.run())
    results = await asyncio.gather(*(batcher.submit("x" * i) for i in range(64)))
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    print(results[:5], "batches:", batcher.batches_run)


asyncio.run(main())
# Output: [0, 1, 2, 3, 4] batches: 4
```

One batcher (and one worker thread) per GPU; torch releases the GIL inside kernels, so the loop stays
responsive. For serious serving, dedicated servers (vLLM, TGI, Triton) do continuous batching better; use this
pattern for embedding/reranker models inside your own service.

## Scraping corpora politely

- Per-host concurrency (1-4) with a keyed Semaphore, plus a global cap; a per-host delay or token bucket.
- One `aiohttp.ClientSession`/`httpx.AsyncClient` for the crawl, `async with` around it.
- Bounded frontier queue; dedupe URLs before enqueueing; `robots.txt` cached per host.
- Timeouts on connect and read; retry 429/503 honouring `Retry-After`; give up on 4xx.
- Parse HTML in a process pool if pages are large; write raw pages to disk with `to_thread` or `aiofiles`.

## Checklist

- [ ] Every provider call goes through one client wrapper with Semaphore + rate limiter + timeout + retry.
- [ ] Fan-out over large inputs uses a sliding window or worker pool, not `gather` over everything.
- [ ] Partial failures are recorded with the item id; successes are not thrown away.
- [ ] Streams are closed on early exit (`aclosing`, `finally`), usage recorded on abort.
- [ ] No blocking SDK, file or CPU work on the loop (`scripts/async_lint.py --strict` passes).
- [ ] Clients and pools are created once (lifespan / main) and closed on shutdown.
- [ ] Background tasks are owned; shutdown drains, then cancels.
- [ ] Metrics: in-flight, queue depth, 429s, retries, latency p50/p95, tokens and cost per job.
