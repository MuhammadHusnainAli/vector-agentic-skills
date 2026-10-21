# Thread Pools in AI Engineering

Worked, runnable patterns for the I/O-bound jobs AI engineers run from synchronous code. Every example uses an
offline stub in place of the real client (marked `# real:`) so it runs anywhere; swap the stub for the SDK call.
For an all-in-one starting point run `python scripts/executor_tool.py scaffold --recipe llm-eval-harness`.

## Contents

1. [Eval harness over thousands of prompts with an RPM limit](#1-eval-harness-over-thousands-of-prompts-with-an-rpm-limit)
2. [Embedding a corpus through an API](#2-embedding-a-corpus-through-an-api)
3. [Downloading and scraping a corpus](#3-downloading-and-scraping-a-corpus)
4. [Parallel vector-store upserts](#4-parallel-vector-store-upserts)
5. [S3 uploads of chunks](#5-s3-uploads-of-chunks)
6. [Parallel tool calls in a sync agent](#6-parallel-tool-calls-in-a-sync-agent)
7. [Streaming tokens from a worker thread](#7-streaming-tokens-from-a-worker-thread)
8. [FastAPI sync endpoints, Streamlit and Gradio](#8-fastapi-sync-endpoints-streamlit-and-gradio)
9. [Checklist](#9-checklist)

## 1. Eval harness over thousands of prompts with an RPM limit

Requirements: 10k prompts, provider limit 500 RPM, p95 latency 6 s, nothing lost, resumable, Ctrl-C safe.

- **Sizing:** 500 RPM = 8.3 req/s; x 6 s = 50 in flight; x 1.2 = 60 workers. The token bucket keeps the rate
  at ~450 RPM (10% under the limit); the window keeps memory flat.
- **Resumable:** append each result to a JSONL file as it completes (single writer: the main thread), and on
  restart skip ids already in the file.
- **Deterministic scoring:** temperature 0 where possible, record model, prompt hash and parameters per row.
- **Errors are data:** a row per failure with the error type, so the report shows "ok 9,812 / failed 188
  (BadRequest 150: context length, RateLimit 38 after 5 attempts)".

```python
import itertools
import json
import os
import tempfile
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait


def call_model(prompt: str) -> str:                     # real: client.chat.completions.create(...)
    time.sleep(0.005)
    if int(prompt.split("#")[1]) % 97 == 13:
        raise ValueError("400 context length exceeded")
    return prompt[::-1]


def load_done(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {json.loads(line)["id"] for line in fh}


def evaluate(item: dict) -> dict:
    started = time.monotonic()
    try:
        return {"id": item["id"], "output": call_model(item["prompt"]), "error": None,
                "latency_s": round(time.monotonic() - started, 3)}
    except Exception as exc:                            # every failure becomes a row
        return {"id": item["id"], "output": None, "error": f"{type(exc).__name__}: {exc}",
                "latency_s": round(time.monotonic() - started, 3)}


def run(dataset, out_path: str, workers: int = 16, max_in_flight: int = 64) -> dict:
    done_ids = load_done(out_path)
    todo = (item for item in dataset if item["id"] not in done_ids)   # resume: skip finished ids
    counts = {"ok": 0, "failed": 0, "skipped": len(done_ids)}
    with open(out_path, "a", encoding="utf-8") as out, \
            ThreadPoolExecutor(max_workers=workers, thread_name_prefix="eval") as ex:
        pending = {ex.submit(evaluate, it) for it in itertools.islice(todo, max_in_flight)}
        while pending:
            done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)
            for fut in done:
                row = fut.result()                      # evaluate() never raises; a bug here should
                out.write(json.dumps(row) + "\n")       # crash loudly
                counts["failed" if row["error"] else "ok"] += 1
            pending |= {ex.submit(evaluate, it) for it in itertools.islice(todo, len(done))}
    return counts


dataset = [{"id": i, "prompt": f"question #{i}"} for i in range(300)]
path = os.path.join(tempfile.mkdtemp(), "results.jsonl")
print(run(dataset[:100], path))     # {'ok': 99, 'failed': 1, 'skipped': 0}
print(run(dataset, path))           # {'ok': 198, 'failed': 2, 'skipped': 100}   (resumed)
```

Add the token bucket and retry helpers from
[bounding-backpressure-and-rate-limits.md](bounding-backpressure-and-rate-limits.md) and
[reliability-timeouts-retries-cancellation.md](reliability-timeouts-retries-cancellation.md) inside
`evaluate`; the scaffolded `llm-eval-harness` recipe has all of it wired together. Note that the main thread
is the only writer of the output file, so no lock is needed.

LLM-as-judge evals double the calls (generate, then judge): run them as two passes over the JSONL (simple,
resumable) or chain inside one task (one in-flight item uses two sequential calls, so size the pool for the
summed latency).

## 2. Embedding a corpus through an API

Embedding endpoints accept batches (often up to 2,048 inputs or a token cap per request). Batch first, then
parallelize the batches; reassemble in input order; never embed the same text twice.

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List


def embed_batch(texts: List[str]) -> List[List[float]]:    # real: client.embeddings.create(model=..., input=texts)
    time.sleep(0.01)
    return [[float(len(t)), float(t.count(" "))] for t in texts]


def batches_by_budget(texts: List[str], max_items: int = 64, max_tokens: int = 8000) -> List[List[int]]:
    """Group indexes so each request respects both the item cap and a token budget (~4 chars/token)."""
    out, cur, cur_tokens = [], [], 0
    for i, t in enumerate(texts):
        tokens = max(1, len(t) // 4)
        if cur and (len(cur) == max_items or cur_tokens + tokens > max_tokens):
            out.append(cur)
            cur, cur_tokens = [], 0
        cur.append(i)
        cur_tokens += tokens
    if cur:
        out.append(cur)
    return out


def embed_corpus(texts: List[str], workers: int = 8) -> List[List[float]]:
    unique: Dict[str, int] = {}
    for t in texts:
        unique.setdefault(t, len(unique))               # dedupe identical chunks (boilerplate, headers)
    uniq_texts = list(unique)
    groups = batches_by_budget(uniq_texts)
    vectors: List[List[float]] = [[] for _ in uniq_texts]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="embed") as ex:
        for group, vecs in zip(groups, ex.map(lambda g: embed_batch([uniq_texts[i] for i in g]), groups)):
            for i, v in zip(group, vecs):               # map preserves order: results align with groups
                vectors[i] = v
    return [vectors[unique[t]] for t in texts]


chunks = [f"chunk {i % 700} of the handbook" for i in range(1000)]
vecs = embed_corpus(chunks)
print(len(vecs), vecs[0] == vecs[700])                  # 1000 True
```

Production additions: a TPM bucket charged with each batch's token estimate, retries on 429/5xx inside the
task, a per-batch error record instead of failing the whole corpus, and writing vectors to disk (`.npy` or
Parquet) per completed batch so a crash does not lose an hour of paid calls.

## 3. Downloading and scraping a corpus

- One `requests.Session` per worker thread (connection reuse without sharing a non-thread-safe Session).
- Per-host concurrency caps and a delay, honour robots.txt and `Retry-After`.
- Stream large bodies to a temp file and rename atomically, so a crash never leaves half a file.
- Dedupe by URL and by content hash.

```python
import hashlib
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

_local = threading.local()
_host_slots: dict = {}
_slots_lock = threading.Lock()
OUT = tempfile.mkdtemp()


def session():
    if not hasattr(_local, "s"):
        _local.s = object()                             # real: requests.Session() + HTTPAdapter(pool_maxsize=...)
    return _local.s


def host_slot(url: str) -> threading.BoundedSemaphore:
    host = urlsplit(url).netloc
    with _slots_lock:
        if host not in _host_slots:
            _host_slots[host] = threading.BoundedSemaphore(2)
        return _host_slots[host]


def download(url: str) -> str:
    session()
    with host_slot(url):
        body = f"<html>{url}</html>".encode()          # real: s.get(url, timeout=(5, 60), stream=True)
    digest = hashlib.sha256(body).hexdigest()[:16]
    final = os.path.join(OUT, digest + ".html")
    fd, tmp = tempfile.mkstemp(dir=OUT)
    with os.fdopen(fd, "wb") as fh:
        fh.write(body)                                  # real: for chunk in r.iter_content(1 << 16)
    os.replace(tmp, final)                              # atomic: readers never see partial files
    return final


urls = sorted({f"https://site{i % 4}.example/doc/{i % 50}" for i in range(120)})   # URL dedupe
saved, failed = [], {}
with ThreadPoolExecutor(max_workers=8, thread_name_prefix="crawl") as ex:
    futures = {ex.submit(download, u): u for u in urls}
    for fut in as_completed(futures):
        try:
            saved.append(fut.result())
        except Exception as exc:
            failed[futures[fut]] = exc
print(len(urls), len(saved), len(failed))               # 100 100 0
```

For millions of URLs read them lazily and use a sliding window instead of a dict of all futures. Parsing the
downloaded HTML/PDF is CPU-bound: hand it to a process pool
([python-multiprocessing-pool-designer](../../python-multiprocessing-pool-designer/SKILL.md)).

## 4. Parallel vector-store upserts

The database is the ceiling: a handful of workers with large batches beats many workers with small ones.
Upserts must be **idempotent** (deterministic ids from document id + chunk index) so retries and re-runs do not
duplicate vectors.

```python
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

store: dict = {}
store_lock = threading.Lock()


def upsert(points: list) -> int:                        # real: qdrant.upsert(collection, points=...) etc.
    time.sleep(0.005)
    with store_lock:                                    # the stub's storage; a real DB handles this
        for pid, vec in points:
            store[pid] = vec
    return len(points)


def point_id(doc_id: str, chunk_no: int) -> str:
    return hashlib.sha1(f"{doc_id}:{chunk_no}".encode()).hexdigest()


points = [(point_id(f"doc{d}", c), [float(d), float(c)]) for d in range(50) for c in range(20)]
batches = [points[i:i + 200] for i in range(0, len(points), 200)]
written = 0
with ThreadPoolExecutor(max_workers=4, thread_name_prefix="upsert") as ex:
    for _ in range(2):                                  # running twice must not duplicate anything
        futures = [ex.submit(upsert, b) for b in batches]
        written += sum(f.result() for f in as_completed(futures))
print(written, len(store))                              # 2000 1000
```

Verify after the job: count points per collection and compare with the number of chunks; log mismatches.

## 5. S3 uploads of chunks

boto3 clients are thread-safe; sessions and resources are not. Create the client once in the main thread
(creating clients concurrently from the default session is not safe) and size its connection pool.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed


class FakeS3:                                           # real: boto3.client("s3", config=Config(max_pool_connections=16))
    def __init__(self) -> None:
        self.objects = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> dict:
        self.objects[f"{Bucket}/{Key}"] = len(Body)    # dict item assignment: atomic in the stub
        return {"ETag": str(len(Body))}


s3 = FakeS3()                                           # one client, created before the threads


def upload(key: str, body: bytes) -> str:
    return s3.put_object(Bucket="corpus", Key=key, Body=body)["ETag"]


chunks = {f"chunks/{i:05d}.jsonl": b"x" * (100 + i) for i in range(64)}
with ThreadPoolExecutor(max_workers=16, thread_name_prefix="s3") as ex:
    futures = {ex.submit(upload, k, v): k for k, v in chunks.items()}
    etags = {futures[f]: f.result() for f in as_completed(futures)}
print(len(etags), len(s3.objects))                      # 64 64
```

For single large files use `s3.upload_file(..., Config=TransferConfig(max_concurrency=10,
multipart_chunksize=64 * 1024 * 1024))`: boto3 already runs multipart parts in its own thread pool. Do not wrap
it in another pool of 32 threads (32 x 10 connections). For many small objects, your own pool as above is the
right tool. For a manual multipart upload, abort the upload (`abort_multipart_upload`) in the error path so
orphaned parts do not accrue storage costs.

## 6. Parallel tool calls in a sync agent

When the model requests several tool calls in one turn, run them concurrently, bound the step by a deadline,
and return every outcome (including errors and timeouts) to the model as a tool result, in the order the
model asked.

```python
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait

TOOLS_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool")   # one per agent process


def search_docs(query: str) -> list:
    time.sleep(0.02)
    return [f"doc about {query}"]


def run_sql(sql: str) -> list:
    raise PermissionError("read-only role cannot run UPDATE")


def slow_web(url: str) -> str:
    time.sleep(2)
    return "page"


TOOLS = {"search_docs": search_docs, "run_sql": run_sql, "slow_web": slow_web}


def run_tool_calls(calls: list, deadline_s: float = 0.5) -> list:
    futures = {}
    for call in calls:
        fn = TOOLS.get(call["name"])
        if fn is None:
            futures[call["id"]] = None
            continue
        futures[call["id"]] = TOOLS_POOL.submit(fn, **json.loads(call["arguments"]))
    wait([f for f in futures.values() if f], timeout=deadline_s)
    results = []
    for call in calls:                                  # same order as the model's request
        fut = futures[call["id"]]
        if fut is None:
            content = {"error": f"unknown tool {call['name']}"}
        elif not fut.done():
            fut.cancel()                                # no-op if running; it finishes in the background
            content = {"error": f"timed out after {deadline_s}s"}
        elif fut.exception() is not None:
            content = {"error": f"{type(fut.exception()).__name__}: {fut.exception()}"}
        else:
            content = {"result": fut.result()}
        results.append({"tool_call_id": call["id"], "content": json.dumps(content)})
    return results


calls = [{"id": "c1", "name": "search_docs", "arguments": '{"query": "refunds"}'},
         {"id": "c2", "name": "run_sql", "arguments": '{"sql": "UPDATE t SET x=1"}'},
         {"id": "c3", "name": "slow_web", "arguments": '{"url": "https://x"}'}]
for r in run_tool_calls(calls):
    print(r["tool_call_id"], r["content"])
TOOLS_POOL.shutdown(wait=False, cancel_futures=True)   # slow_web keeps running until it returns
# c1 {"result": ["doc about refunds"]}
# c2 {"error": "PermissionError: read-only role cannot run UPDATE"}
# c3 {"error": "timed out after 0.5s"}
```

Timed-out tools keep a worker busy until they return, so tools need their own client timeouts; size the pool
for "tools per turn x concurrent conversations". In an async agent, use `asyncio.TaskGroup` instead
([python-asyncio-pattern-advisor](../../python-asyncio-pattern-advisor/SKILL.md)).

## 7. Streaming tokens from a worker thread

A sync UI loop that must stay responsive while a completion streams: run the stream in a thread, push chunks
onto a queue, consume them with a timeout, and stop the producer through an event.

```python
import queue
import threading
import time

END = object()


def stream_completion(prompt: str):                     # real: client.chat.completions.create(..., stream=True)
    for word in f"answer to {prompt} in five tokens".split():
        time.sleep(0.01)
        yield word


def producer(prompt: str, out: queue.Queue, stop: threading.Event) -> None:
    try:
        for token in stream_completion(prompt):
            if stop.is_set():
                break                                   # real: also close the stream to free the connection
            out.put(token)
    except Exception as exc:                            # forward errors; never let the thread die silently
        out.put(exc)
    finally:
        out.put(END)


tokens: queue.Queue = queue.Queue(maxsize=100)
stop = threading.Event()
t = threading.Thread(target=producer, args=("refunds", tokens, stop), name="stream")
t.start()
received = []
while True:
    item = tokens.get(timeout=30)
    if item is END:
        break
    if isinstance(item, Exception):
        raise item
    received.append(item)                               # e.g. st.write / gradio yield here
t.join()
print(" ".join(received))                               # answer to refunds in five tokens
```

## 8. FastAPI sync endpoints, Streamlit and Gradio

**FastAPI / Starlette:** `def` (sync) endpoints already run in AnyIO's worker thread pool (40 threads by
default), so each request is a thread. Inside, use one **application-wide** executor created in the lifespan
handler and shut down when the app stops; never `ThreadPoolExecutor()` per request (TPE016). Bound every wait
(`fut.result(timeout=...)`, TPE011). For high concurrency prefer `async def` endpoints with async clients.

```python
import contextlib
from concurrent.futures import ThreadPoolExecutor


@contextlib.contextmanager
def lifespan_executor(workers: int = 32):
    """Shape of a FastAPI lifespan: create once at startup, shut down at exit."""
    ex = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="io")
    try:
        yield ex                                        # app.state.io = ex
    finally:
        ex.shutdown(wait=True, cancel_futures=True)


with lifespan_executor() as io_pool:
    futures = [io_pool.submit(str.upper, q) for q in ("a", "b")]
    print([f.result(timeout=10) for f in futures])      # ['A', 'B']
```

**Streamlit:** the script reruns on every interaction, so a pool created at top level is created again on
every rerun. Cache it with `@st.cache_resource` (one per server process). Streamlit calls (`st.write`,
`st.progress`) from worker threads raise or warn about a missing `ScriptRunContext`: collect results in the
script thread (`as_completed` loop) and update the UI there.

**Gradio:** sync event handlers run in a thread pool managed by Gradio, and the queue limits concurrent runs
per event (`concurrency_limit`, default 1 in Gradio 4+). A handler that fans out to an API can use a shared
module-level executor; yield partial results from the handler (a generator) to stream progress. Check the
Gradio version you use for the exact queue defaults.

## 9. Checklist

- [ ] Workers sized from rate limit x p95 latency; connection pool >= workers
- [ ] Token bucket (RPM, and TPM for LLMs) shared by all threads; retries also pass through it
- [ ] Sliding window over lazy input; no `map` over a generator before 3.14 without a bound
- [ ] Every future read; results and errors both recorded; error budget aborts systemic failures
- [ ] Client timeouts on every call; SDK retries off if you retry yourself
- [ ] Non-thread-safe clients per thread (requests.Session, sqlite3, boto3 sessions)
- [ ] Idempotent writes (deterministic ids) so retries and re-runs are safe
- [ ] Incremental output (JSONL per item), resumable by id
- [ ] Ctrl-C: stop event + `cancel_futures=True`, partial results kept, exit 130
- [ ] Thread names and request ids in logs; contextvars copied per task
- [ ] `python scripts/executor_tool.py check` clean
