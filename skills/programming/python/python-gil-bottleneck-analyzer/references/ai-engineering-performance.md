# AI-Engineering Performance Cases

The CPU-side bottlenecks that show up around models: tokenization, parsing model outputs, embedding
post-processing, server batching, feature pipelines, corpus cleaning, reranking, data loading and API
endpoints. Each case gives the usual diagnosis (does it hold the GIL?), the fix, and how to verify it.

## Contents

1. [Triage for any AI pipeline](#1-triage-for-any-ai-pipeline)
2. [Tokenization throughput](#2-tokenization-throughput)
3. [JSON parsing of model outputs](#3-json-parsing-of-model-outputs)
4. [Embedding post-processing](#4-embedding-post-processing)
5. [Python-side batching in inference servers](#5-python-side-batching-in-inference-servers)
6. [pandas apply in feature pipelines](#6-pandas-apply-in-feature-pipelines)
7. [Regex-heavy corpus cleaning](#7-regex-heavy-corpus-cleaning)
8. [CPU-bound reranking](#8-cpu-bound-reranking)
9. [Data loaders](#9-data-loaders)
10. [FastAPI endpoints doing CPU work](#10-fastapi-endpoints-doing-cpu-work)
11. [Eval harnesses scoring thousands of outputs](#11-eval-harnesses-scoring-thousands-of-outputs)
12. [Case summary table](#12-case-summary-table)

## 1. Triage for any AI pipeline

Most pipelines mix stages: fetch (I/O), parse/clean (Python CPU), tokenize/embed (native, often GIL-free),
write (I/O). Time each stage separately before choosing a tool.

```python
import time
from contextlib import contextmanager

timings: dict[str, float] = {}


@contextmanager
def stage(name: str):
    wall0, cpu0 = time.perf_counter(), time.process_time()
    try:
        yield
    finally:
        wall, cpu = time.perf_counter() - wall0, time.process_time() - cpu0
        timings[name] = wall
        print(f"{name:<10} wall {wall:6.3f}s  cpu {cpu:6.3f}s  cores busy {cpu / wall if wall else 0:4.2f}")


with stage("fetch"):
    time.sleep(0.2)                                    # network: cores busy ~0
with stage("clean"):
    docs = [" ".join(f"tok{i}".split()) for i in range(300_000)]   # Python CPU: cores busy ~1
```

Then: I/O stages → asyncio/threads; Python CPU stages → algorithm/vectorise/processes; native stages → check
whether the library already parallelises before adding anything.

## 2. Tokenization throughput

| Tokenizer | GIL | Parallelism |
|-----------|-----|-------------|
| HF `tokenizers` / `AutoTokenizer(use_fast=True)` | released in batch calls | Rust rayon pool inside `encode_batch` / `tokenizer(list_of_texts)` |
| HF slow (Python) tokenizers, SentencePiece via Python loops | held | needs processes |
| `tiktoken` | releases the GIL while encoding batches (Rust) | `encode_batch(texts, num_threads=...)` uses a thread pool |

Rules:

- Call the fast tokenizer on **batches** (`tokenizer(texts, ...)` with a list of 256-2048 texts), not one text
  at a time in a Python loop: the per-call Python overhead dominates short texts.
- The rayon pool is controlled by `TOKENIZERS_PARALLELISM` (`true`/`false`) and rayon's thread-count variable
  (HF documents `RAYON_RS_NUM_CPUS`; check your version).
- Using the tokenizer and then forking (DataLoader workers, `multiprocessing` with fork) prints
  "huggingface/tokenizers: The current process just got forked, after parallelism has already been used.
  Disabling parallelism to avoid deadlocks..." Set `TOKENIZERS_PARALLELISM=false` before forking or use
  spawn/forkserver workers.
- Choose one level: either the tokenizer's own pool in one process, or N processes each with
  `TOKENIZERS_PARALLELISM=false`. Both at full size oversubscribes the CPU.

```python
import os

os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")   # single process: let Rust use the cores

from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)


def token_counts(texts: list[str], batch: int = 1024) -> list[int]:
    counts: list[int] = []
    for i in range(0, len(texts), batch):
        enc = tok(texts[i:i + batch], add_special_tokens=False, truncation=False)
        counts.extend(len(ids) for ids in enc["input_ids"])
    return counts
```

Verify with `py-spy record --native`: the time should sit in `tokenizers::` frames across several threads
(`native-release` in `profile_classify.py`), not in Python frames.

## 3. JSON parsing of model outputs

`json.loads` and `orjson.loads` both hold the GIL (they build Python objects). Threads do not help, and
processes rarely help: shipping the string to a worker costs about as much as parsing it. Make the parse
cheaper instead.

```python
import json

raw_outputs = ['{"answer": "Paris", "confidence": 0.93, "citations": [1, 4]}'] * 50_000

try:
    import orjson                                     # Rust; typically several times faster than json

    loads = orjson.loads
except ImportError:                                   # stdlib fallback keeps the code runnable
    loads = json.loads

parsed = [loads(s) for s in raw_outputs]
print(len(parsed), parsed[0]["answer"])
```

| Situation | Fix |
|-----------|-----|
| Many small outputs | `orjson` / `msgspec` (with a typed schema, `msgspec.json.Decoder(Answer)` validates while decoding) |
| Pydantic validation after parsing | `Model.model_validate_json(raw)` parses and validates in Rust in one step |
| Outputs arrive over the network | parse inside the async consumer as they arrive; it overlaps naturally |
| Huge JSONL eval dumps | split files and parse shards in processes: each worker reads its own file (no big strings over IPC) |
| Malformed JSON repair loops | separate concern: see the exception-handling skill for repair loops |

## 4. Embedding post-processing

Normalisation, deduplication by cosine similarity, top-k and quantisation are numeric: do them in one numpy
call per batch. numpy releases the GIL inside these operations, and BLAS uses several cores for matrix
products.

```python
import numpy as np

rng = np.random.default_rng(0)
batch = rng.standard_normal((4096, 768)).astype(np.float32)

# Slow: Python loop per vector (holds the GIL, ~100x slower)
# normed = [v / np.linalg.norm(v) for v in batch]

normed = batch / np.linalg.norm(batch, axis=1, keepdims=True)          # one call
sims = normed @ normed[:8].T                                           # BLAS, multi-core
near_dupes = np.argwhere(np.triu(sims[:8], k=1) > 0.95)                 # pairs among the first 8
scale = np.abs(normed).max(axis=1, keepdims=True) / 127.0
int8 = np.round(normed / scale).astype(np.int8)                        # int8 quantisation
print(normed.shape, int8.dtype, len(near_dupes))
```

Pitfalls: `float64` doubles memory traffic (use `float32`); `.tolist()` before storing to a vector DB converts
to Python floats under the GIL (most clients accept numpy arrays or bytes); converting `list[list[float]]` from
an API response with `np.array(...)` is GIL-held, do it once per batch.

## 5. Python-side batching in inference servers

An inference server's GPU can sit idle while Python collates requests: tokenizing on the event loop, padding
lists, building tensors from nested lists, decoding outputs one token at a time. Signs: GPU utilisation low,
one CPU core at 100%, p99 latency grows with concurrency.

A minimal micro-batcher that keeps the event loop free and does one model call per batch:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

model_pool = ThreadPoolExecutor(max_workers=1)        # model calls release the GIL inside torch/onnx


def model_forward(texts: list[str]) -> list[int]:      # stands in for tokenizer(texts) + model(**batch)
    return [len(t) for t in texts]


class MicroBatcher:
    def __init__(self, max_batch: int = 32, max_wait_s: float = 0.005):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_batch, self.max_wait_s = max_batch, max_wait_s

    async def submit(self, text: str) -> int:
        fut = asyncio.get_running_loop().create_future()
        await self.queue.put((text, fut))
        return await fut

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            text, fut = await self.queue.get()
            batch = [(text, fut)]
            deadline = loop.time() + self.max_wait_s
            while len(batch) < self.max_batch and (timeout := deadline - loop.time()) > 0:
                try:
                    batch.append(await asyncio.wait_for(self.queue.get(), timeout))
                except asyncio.TimeoutError:
                    break
            try:
                outs = await loop.run_in_executor(model_pool, model_forward, [t for t, _ in batch])
            except Exception as err:                    # fail every waiter, keep the batcher alive
                for _, f in batch:
                    if not f.done():
                        f.set_exception(err)
                continue
            for (_, f), out in zip(batch, outs):
                if not f.done():
                    f.set_result(out)


async def main() -> None:
    batcher = MicroBatcher()
    runner = asyncio.create_task(batcher.run())
    results = await asyncio.gather(*(batcher.submit(f"request {i}") for i in range(100)))
    runner.cancel()
    print(len(results), results[:3])


asyncio.run(main())
```

Then remove Python overhead inside `model_forward`: tokenize the batch in one call with
`return_tensors="pt"`, avoid `torch.tensor(list_of_lists)` (GIL-held and slow; use numpy arrays or the
tokenizer's tensors), decode outputs in batch (`batch_decode`). If pre/post-processing is still Python-heavy,
run several server processes (`uvicorn --workers N` or one process per GPU) rather than threads. Dedicated
servers (vLLM, TGI, Triton) exist precisely to keep this loop out of Python.

## 6. pandas apply in feature pipelines

`df.apply(f, axis=1)`, `iterrows`, `itertuples` with Python bodies and `Series.map(python_fn)` run Python per
row with the GIL held. Vectorise first; parallelise only what cannot be vectorised.

```python
import numpy as np
import pandas as pd

df = pd.DataFrame({
    "prompt": ["Summarise this", "Translate: hola", "Summarise that report"],
    "tokens_in": [120, 15, 900],
    "tokens_out": [80, 5, 300],
})

# Before: df["cost"] = df.apply(lambda r: r.tokens_in * 3e-6 + r.tokens_out * 15e-6, axis=1)
df["cost"] = df["tokens_in"] * 3e-6 + df["tokens_out"] * 15e-6
df["task"] = np.select(
    [df["prompt"].str.startswith("Summarise"), df["prompt"].str.startswith("Translate")],
    ["summarise", "translate"],
    default="other",
)
df["long"] = df["tokens_in"] > 500
print(df[["task", "cost", "long"]])
```

String columns: `.str` methods on object dtype still loop in Python internally (faster than `apply`, but
GIL-held); `dtype="string[pyarrow]"` makes many of them run in Arrow C++. polars expressions run in Rust,
multi-threaded. For row logic that truly needs Python (calling a parser per row), split the frame into chunks
and process chunks in a process pool, returning columns, not rows.

## 7. Regex-heavy corpus cleaning

`re` holds the GIL for the whole match, so threads serialise. Typical cleaning of a web-scraped corpus for
training or RAG ingestion:

```python
import re

PATTERNS = [
    (re.compile(r"<script.*?</script>", re.S | re.I), " "),
    (re.compile(r"<[^>]+>"), " "),
    (re.compile(r"https?://\S+"), " <url> "),
    (re.compile(r"[ \t ]+"), " "),
    (re.compile(r"\n{3,}"), "\n\n"),
]
BOILER = re.compile(r"(?:cookie policy|subscribe to our newsletter|all rights reserved)", re.I)


def clean(doc: str) -> str:
    if "<" not in doc and "http" not in doc:          # cheap prefilter skips most regex work
        return " ".join(doc.split())
    for rx, repl in PATTERNS:
        doc = rx.sub(repl, doc)
    return BOILER.sub("", doc).strip()


print(clean("<p>Hello   <b>world</b> see https://x.y/z</p>\n\n\n\nAll rights reserved"))
```

Speed-ups in order: compile once; prefilter with `in` / `str.startswith`; merge alternations into one pattern;
avoid catastrophic backtracking (`(a+)+`, `.*` followed by more `.*`); then shard files across processes (each
worker reads its own file and writes its own output, so only paths cross IPC). The third-party `regex` module
can release the GIL during matching with `concurrent=True` (safe only on immutable strings), making threads
viable.

## 8. CPU-bound reranking

| Reranker | GIL | Fix |
|----------|-----|-----|
| Cross-encoder (torch/onnx) on CPU | released inside the model | batch pairs (16-64), cap `torch.set_num_threads`, threads or one process per socket |
| BM25 / keyword scoring in Python loops | held | vectorise with numpy/scipy sparse, or a library implemented in C/Rust |
| LLM-as-reranker over an API | I/O | asyncio with a Semaphore |
| Feature-based (lengths, overlaps, recency) | held if per-pair Python | compute features as arrays |

Vectorised BM25-style scoring over a candidate set:

```python
import numpy as np

docs = ["vector search with hnsw", "bm25 keyword search", "reranking with cross encoders", "hnsw graph index"]
vocab = {w: i for i, w in enumerate(sorted({w for d in docs for w in d.split()}))}
tf = np.zeros((len(docs), len(vocab)), dtype=np.float32)
for r, d in enumerate(docs):                      # build once at index time
    for w in d.split():
        tf[r, vocab[w]] += 1
doc_len = tf.sum(axis=1)
idf = np.log(1 + (len(docs) - (tf > 0).sum(0) + 0.5) / ((tf > 0).sum(0) + 0.5))


def bm25(query: str, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
    cols = [vocab[w] for w in query.split() if w in vocab]
    f = tf[:, cols]
    denom = f + k1 * (1 - b + b * doc_len[:, None] / doc_len.mean())
    return (idf[cols] * f * (k1 + 1) / denom).sum(axis=1)


print(np.argsort(-bm25("hnsw search"))[:2])
```

## 9. Data loaders

PyTorch `DataLoader(num_workers=N)` uses worker **processes**, which sidesteps the GIL for Python-heavy
`__getitem__` (decode, augment, tokenize). Keep them efficient:

```python
import os

import torch
from torch.utils.data import DataLoader, Dataset


class TextDataset(Dataset):
    def __init__(self, paths: list[str]):
        self.paths = paths                       # store paths, not loaded data: cheap to send to workers

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, i: int) -> torch.Tensor:
        with open(self.paths[i], "rb") as fh:
            data = fh.read()
        return torch.frombuffer(bytearray(data[:512].ljust(512, b"\0")), dtype=torch.uint8)


def worker_init(_worker_id: int) -> None:
    torch.set_num_threads(1)                     # one intra-op thread per worker
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def make_loader(paths: list[str]) -> DataLoader:
    return DataLoader(TextDataset(paths), batch_size=64, num_workers=4, worker_init_fn=worker_init,
                      persistent_workers=True, prefetch_factor=4, pin_memory=torch.cuda.is_available())
```

Diagnose with the GPU utilisation and the main process's stack: if the training loop waits in the loader's
`_get_data` / queue `get`, the loader is the bottleneck; add workers until the GPU is busy or cores run out.
If `__getitem__` work releases the GIL (PIL decode, numpy), a thread-based loader can work too (less memory,
no pickling). HF `datasets.map(fn, num_proc=N, batched=True)` follows the same logic: `batched=True` amortises
Python overhead, `num_proc` adds processes.

## 10. FastAPI endpoints doing CPU work

| Route style | What happens with CPU work |
|-------------|---------------------------|
| `async def` doing CPU work | blocks the event loop: every other request on that worker stalls |
| `def` (sync) doing CPU work | runs in the threadpool (anyio, 40 threads by default): the loop stays free, but GIL-holding work still runs one at a time and competes with the loop thread for the GIL |
| `async def` + `run_in_executor(process_pool, fn)` | CPU work in other processes; loop responsive; real parallelism |
| background job queue (Celery, RQ, arq, Dramatiq) | best for long jobs (> a few seconds): return a job id |

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel


def chunk_document(text: str, size: int) -> list[str]:        # module-level: picklable
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cpu_pool = ProcessPoolExecutor(max_workers=4)   # created once, reused
    try:
        yield
    finally:
        app.state.cpu_pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(lifespan=lifespan)


class ChunkRequest(BaseModel):
    text: str
    size: int = 200


@app.post("/chunk")
async def chunk(req: ChunkRequest) -> dict:
    loop = asyncio.get_running_loop()
    chunks = await loop.run_in_executor(app.state.cpu_pool, chunk_document, req.text, req.size)
    return {"n_chunks": len(chunks)}
```

Sizing: `uvicorn --workers W` × pool size P ≤ cores. Ship small arguments (an id or a path rather than a 20 MB
document when possible). Detect loop blocking with asyncio debug mode (`PYTHONASYNCIODEBUG=1` logs callbacks
slower than 100 ms) or by running `profile_classify.py` on a py-spy recording of the worker: `python-cpu` on
the MainThread of an async server is the smoking gun. More on loop hygiene in the
[asyncio pattern advisor](../../python-asyncio-pattern-advisor/SKILL.md).

## 11. Eval harnesses scoring thousands of outputs

Calling the model is I/O (asyncio with rate limits); scoring is CPU (exact match, BLEU/ROUGE, regex
extraction, JSON-schema checks, code execution). Split them:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor


def score(pred: str, gold: str) -> float:            # CPU: normalise + token-overlap F1
    p, g = pred.lower().split(), gold.lower().split()
    common = len(set(p) & set(g))
    if not common:
        return 0.0
    prec, rec = common / len(p), common / len(g)
    return 2 * prec * rec / (prec + rec)


async def generate(prompt: str) -> str:              # I/O: stands in for the API call
    await asyncio.sleep(0.01)
    return prompt.replace("Q:", "A:")


async def run_eval(items: list[tuple[str, str]], pool: ProcessPoolExecutor) -> float:
    sem = asyncio.Semaphore(32)

    async def one(prompt: str, gold: str) -> float:
        async with sem:
            pred = await generate(prompt)
        return await asyncio.get_running_loop().run_in_executor(pool, score, pred, gold)

    scores = await asyncio.gather(*(one(p, g) for p, g in items))
    return sum(scores) / len(scores)


if __name__ == "__main__":
    data = [(f"Q: capital {i}", f"A: capital {i}") for i in range(200)]
    with ProcessPoolExecutor(max_workers=2) as pool:
        print(f"mean F1 {asyncio.run(run_eval(data, pool)):.2f}")
```

If scoring is cheap (< ~1 ms per item), skip the pool: the IPC costs more than the work. Batch items per pool
task when it is moderately cheap.

## 12. Case summary table

| Case | Holds GIL? | First fix | Then |
|------|-----------|-----------|------|
| Fast tokenizer, single texts in a loop | partly | batch calls | let rayon parallelise |
| Python tokenizer | yes | switch to a fast tokenizer | processes |
| `json.loads` of outputs | yes | orjson/msgspec | shard files across processes |
| Embedding normalise/top-k | no (numpy) | vectorise per batch | float32, BLAS threads |
| Server batching | mixed | micro-batcher, batch tokenization | more server processes |
| pandas `apply` | yes | column ops / `np.select` | polars, chunked processes |
| Regex cleaning | yes | precompile, prefilter, merge | processes per shard |
| BM25 / feature reranking | yes | numpy/sparse | processes |
| Cross-encoder rerank on CPU | no (torch) | batch pairs | cap torch threads |
| Data loading | depends | `num_workers` processes | threads if GIL-free decode |
| FastAPI CPU route | yes | process pool via `run_in_executor` | job queue |
| Eval scoring | yes | asyncio for calls + pool for scoring | batch scoring tasks |
