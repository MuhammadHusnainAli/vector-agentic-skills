# AI-Engineering Multiprocessing

Process pools in LLM, RAG, embedding and evaluation pipelines: which jobs benefit, the shape that works for
each, and the traps specific to ML libraries (CUDA, intra-op threads, big models per worker). Examples run
with the stdlib (plus numpy where noted); library calls you would use in production are shown in comments
next to stand-ins.

## Contents

- [1. Which AI jobs are CPU-bound](#1-which-ai-jobs-are-cpu-bound)
- [2. RAG ingestion: parse and chunk documents](#2-rag-ingestion-parse-and-chunk-documents)
- [3. Per-document timeouts for hostile inputs](#3-per-document-timeouts-for-hostile-inputs)
- [4. Tokenizing a large corpus](#4-tokenizing-a-large-corpus)
- [5. CPU embedding with a per-worker model](#5-cpu-embedding-with-a-per-worker-model)
- [6. Image preprocessing](#6-image-preprocessing)
- [7. Eval scoring](#7-eval-scoring)
- [8. Dataset dedup with minhash](#8-dataset-dedup-with-minhash)
- [9. GPUs, CUDA and fork](#9-gpus-cuda-and-fork)
- [10. Mixing asyncio API calls with CPU work](#10-mixing-asyncio-api-calls-with-cpu-work)
- [11. Seeds and determinism](#11-seeds-and-determinism)
- [12. Alternatives: joblib, Ray, Dask, torch DataLoader, datasets.map](#12-alternatives-joblib-ray-dask-torch-dataloader-datasetsmap)

## 1. Which AI jobs are CPU-bound

| Job | Bound by | Processes help? |
|-----|----------|-----------------|
| Calling an LLM / embedding API | Network | No: asyncio with a semaphore (`python-asyncio-pattern-advisor`) |
| PDF/HTML/DOCX parsing (pypdf, pdfminer, BeautifulSoup, trafilatura) | Python CPU | Yes, the classic case |
| Chunking with regex / recursive splitters | Python CPU | Yes, if docs are large; batch small ones |
| Tokenization with HF fast tokenizers (Rust) | Native, already multi-threaded with `batch` | Rarely; use `tokenizer(batch)` and its threads |
| Tokenization with a pure-Python tokenizer, `tiktoken` per string | Mixed | Yes with batches per task |
| CPU embedding (sentence-transformers, onnxruntime) | Native BLAS, multi-threaded | Sometimes: a few workers x few threads can beat one process x all threads for small batches |
| Image decode/resize (PIL, OpenCV) | Native, mostly releases the GIL | Threads first; processes if decode is Python-heavy |
| Metric computation (ROUGE, BLEU, exact match, JSON validation) | Python CPU | Yes |
| Running generated code in evals | Untrusted CPU | Yes: one process per task, hard kill timeout, sandboxed |
| Minhash / n-gram dedup | Python CPU | Yes, signatures in parallel, banding in the parent |
| GPU inference | GPU | One process per GPU, never a pool of GPU workers per GPU |

## 2. RAG ingestion: parse and chunk documents

Shape: the parent lists files; workers parse and chunk, returning compact records; the parent writes to
the vector store (or workers write in batches themselves, see section 13 of the sharing reference). Slow
documents dominate, so use `imap_unordered` with a small chunksize and sort big files first.

```python
import hashlib
import multiprocessing as mp
import os
import re
import tempfile

CHUNK_WORDS, OVERLAP = 120, 20


def parse(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as fh:   # stand-in for pypdf / trafilatura
        html = fh.read()
    return re.sub(r"<[^>]+>", " ", html)


def chunk_file(path: str) -> list:
    words = parse(path).split()
    step = CHUNK_WORDS - OVERLAP
    out = []
    for i in range(0, max(1, len(words)), step):
        text = " ".join(words[i:i + CHUNK_WORDS])
        if text:
            cid = hashlib.sha1(f"{path}:{i}".encode()).hexdigest()[:12]
            out.append({"id": cid, "source": os.path.basename(path), "text": text})
    return out


def make_corpus(n: int) -> list:
    root = tempfile.mkdtemp()
    paths = []
    for i in range(n):
        p = os.path.join(root, f"page{i}.html")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("<p>" + " ".join(f"token{j}" for j in range(50 * (i % 7 + 1))) + "</p>")
        paths.append(p)
    return paths


if __name__ == "__main__":
    paths = sorted(make_corpus(40), key=os.path.getsize, reverse=True)   # big first: shorter tail
    records = []
    with mp.get_context("spawn").Pool(4) as pool:
        for chunks in pool.imap_unordered(chunk_file, paths, chunksize=2):
            records.extend(chunks)                       # parent: batch upserts to the vector store here
    print(len(records), len({r["id"] for r in records}))   # 89 89
```

Design notes:
- Return records, not parser objects. Large return values serialize through the parent.
- Deterministic chunk ids (`hash(source, offset)`) make re-ingestion idempotent and let you dedup.
- Keep failures per document: catch inside `chunk_file`, return `{"source": ..., "error": repr(exc)}`, and
  write a failure report, so one corrupt PDF does not abort a 2-hour run.

## 3. Per-document timeouts for hostile inputs

PDF and HTML parsers can loop for minutes on malformed input. Neither stdlib pool can stop a running task
(`future.result(timeout=...)` only stops waiting, the worker stays busy). Options:

| Option | Kills the stuck task | Cost |
|--------|----------------------|------|
| One `Process` per document with `join(timeout)` + `kill()` | Yes | Process start per document (use fork/forkserver to keep it ~ms) |
| Watchdog: `pebble.ProcessPool` (third-party) `schedule(fn, timeout=...)` | Yes | Dependency |
| `signal.alarm` inside the worker (POSIX, main thread of the worker) | Only if the parser returns to Python bytecode | Cheap |
| 3.14 `ProcessPoolExecutor.kill_workers()` then a new executor | Yes, all workers | Restart cost |

Signal-based soft timeout inside a pool worker:

```python
import multiprocessing as mp
import signal
import sys
import time


class TaskTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise TaskTimeout("document took too long")


def parse_with_deadline(args: tuple) -> tuple:
    doc_id, seconds_of_work = args
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(1)                                      # per-task deadline in whole seconds
    try:
        time.sleep(seconds_of_work)                      # stand-in for a parser stuck on a bad PDF
        return doc_id, "ok"
    except TaskTimeout as exc:
        return doc_id, f"timeout: {exc}"
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    if sys.platform != "win32":
        with mp.get_context("spawn").Pool(2) as pool:
            print(pool.map(parse_with_deadline, [("a", 0.1), ("b", 5), ("c", 0.1)]))
        # [('a', 'ok'), ('b', 'timeout: document took too long'), ('c', 'ok')]
```

Native code that never returns to the interpreter ignores the alarm; for those, the process-per-task
pattern with `kill()` is the only reliable bound (see the debugging reference).

## 4. Tokenizing a large corpus

Shape: shard by file or byte range; each worker loads the tokenizer once (initializer), reads its shard,
tokenizes in batches, writes `.npy`/Arrow output, and returns `(shard, n_tokens)`. The parent never sees
the tokens.

```python
import multiprocessing as mp
import os
import tempfile

import numpy as np

_vocab = None


def init_tokenizer(vocab_size: int) -> None:
    global _vocab
    os.environ["TOKENIZERS_PARALLELISM"] = "false"       # HF fast tokenizers: avoid nested threads
    _vocab = vocab_size                                   # stand-in for AutoTokenizer.from_pretrained(...)


def tokenize_shard(job: tuple) -> tuple:
    in_path, out_path = job
    ids = []
    with open(in_path, encoding="utf-8") as fh:
        for line in fh:                                   # real code: tokenizer(batch_of_lines)["input_ids"]
            ids.extend(hash(w) % _vocab for w in line.split())
    np.save(out_path, np.asarray(ids, dtype=np.int32))
    return os.path.basename(out_path), len(ids)


if __name__ == "__main__":
    root = tempfile.mkdtemp()
    jobs = []
    for s in range(8):
        src = os.path.join(root, f"shard{s}.txt")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("the quick brown fox\n" * 1000)
        jobs.append((src, os.path.join(root, f"shard{s}.npy")))
    with mp.get_context("spawn").Pool(4, initializer=init_tokenizer, initargs=(50_000,)) as pool:
        stats = pool.map(tokenize_shard, jobs, chunksize=1)
    print(sum(n for _, n in stats))   # 32000
```

(`hash()` of str is salted per process, which is fine for this stand-in but not for real token ids.)
With HF fast tokenizers, first try one process: `tokenizer(list_of_texts, batch_size=1000)` already uses
all cores via Rust threads. Use processes when there is surrounding Python work (cleaning, filtering,
packing) that dominates.

## 5. CPU embedding with a per-worker model

```python
import os
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

_model = None


def init_model(model_name: str, threads: int) -> None:
    global _model
    os.environ["OMP_NUM_THREADS"] = str(threads)
    # import torch; torch.set_num_threads(threads)
    # from sentence_transformers import SentenceTransformer
    # _model = SentenceTransformer(model_name, device="cpu")
    _model = lambda texts: [[float(len(t)), float(t.count(" "))] for t in texts]   # stand-in, set in-worker


def embed_batch(texts: list) -> list:
    return _model(texts)                                  # real: _model.encode(texts, batch_size=32).tolist()


if __name__ == "__main__":
    texts = [f"passage number {i} about retrieval" for i in range(1000)]
    batches = [texts[i:i + 64] for i in range(0, len(texts), 64)]
    workers, threads = 2, 1                               # workers x threads <= cores
    ctx = mp.get_context("spawn")
    with ProcessPoolExecutor(workers, mp_context=ctx, initializer=init_model,
                             initargs=("all-MiniLM-L6-v2", threads)) as ex:
        vectors = [v for batch in ex.map(embed_batch, batches) for v in batch]
    print(len(vectors))   # 1000
```

(The lambda is created inside the worker, so nothing unpicklable crosses a process boundary.)

Checklist:
- Model loaded in the initializer, never per task and never in the parent with spawn (it would be pickled).
- `workers x threads <= cores`. Benchmark (1 x cores) vs (cores/2 x 2) vs (cores x 1); batched BLAS often
  prefers fewer workers with more threads.
- Memory: each worker holds a full model copy. A 400 MB model x 16 workers = 6.4 GB. Quantized ONNX
  (int8) cuts it 4x; or use one process with threads when the runtime releases the GIL (onnxruntime and
  torch inference do).
- Batches of 32-128 texts per task: amortizes IPC and uses the model's batched kernels.
- `max_tasks_per_child` caps slow growth but reloads the model each time: use a large value (thousands).

## 6. Image preprocessing

```python
import multiprocessing as mp
import os
import tempfile

import numpy as np


def preprocess(job: tuple) -> tuple:
    src, dst = job
    img = np.load(src)                                    # real: PIL.Image.open(src).convert("RGB")
    small = img[::2, ::2].astype(np.float32) / 255.0      # real: resize to 224x224, normalize
    np.save(dst, small)
    return os.path.basename(dst), small.shape


if __name__ == "__main__":
    root = tempfile.mkdtemp()
    jobs = []
    rng = np.random.default_rng(0)
    for i in range(16):
        src = os.path.join(root, f"img{i}.npy")
        np.save(src, rng.integers(0, 255, (448, 448, 3), dtype=np.uint8))
        jobs.append((src, os.path.join(root, f"img{i}_224.npy")))
    with mp.get_context("spawn").Pool(4) as pool:
        out = pool.map(preprocess, jobs, chunksize=2)
    print(out[0])   # ('img0_224.npy', (224, 224, 3))
```

Pass paths and write outputs to disk: a 224x224x3 float32 image is 600 KB, and returning 100k of them through
the parent costs minutes of pickling. PIL and OpenCV release the GIL in decode/resize, so also benchmark a
`ThreadPoolExecutor` before committing to processes. For training, a `DataLoader` with `num_workers` does
this per batch (section 12).

## 7. Eval scoring

Thousands of model outputs scored with CPU metrics (exact match, F1, ROUGE, JSON schema validation, regex
graders) parallelise cleanly. Keep the input order (`map`) so scores line up with prompts, or carry an id.

```python
import multiprocessing as mp
import re
from collections import Counter


def f1(pred: str, gold: str) -> float:
    p, g = re.findall(r"\w+", pred.lower()), re.findall(r"\w+", gold.lower())
    common = sum((Counter(p) & Counter(g)).values())
    if not common:
        return 0.0
    prec, rec = common / len(p), common / len(g)
    return 2 * prec * rec / (prec + rec)


def score(row: tuple) -> dict:
    qid, pred, gold = row
    return {"id": qid, "em": float(pred.strip().lower() == gold.strip().lower()), "f1": f1(pred, gold)}


if __name__ == "__main__":
    rows = [(i, "Paris is the capital", "Paris") for i in range(2000)]
    with mp.get_context("spawn").Pool(4) as pool:
        scores = pool.map(score, rows, chunksize=100)
    print(round(sum(s["f1"] for s in scores) / len(scores), 3))   # 0.4
```

Executing model-generated code (HumanEval-style): each sample in its own process (or container) with
`resource.setrlimit` for CPU/memory, a wall-clock `join(timeout)` and `kill()`, no network, a temp working
dir. Never `exec` generated code inside a pool worker that also scores other samples.

## 8. Dataset dedup with minhash

Signature computation is embarrassingly parallel and CPU-heavy; banding and clustering need global state
and stay in the parent.

```python
import hashlib
import multiprocessing as mp
import random
from collections import defaultdict

NUM_PERM, BANDS = 64, 16
ROWS = NUM_PERM // BANDS
_seeds = None


def init(seed: int) -> None:
    global _seeds
    rng = random.Random(seed)                                     # same seeds in every worker
    _seeds = [rng.getrandbits(32) for _ in range(NUM_PERM)]


def signature(doc: tuple) -> tuple:
    doc_id, text = doc
    words = text.split()
    shingles = {" ".join(words[i:i + 3]) for i in range(max(1, len(words) - 2))}
    hashes = [int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "little") for s in shingles]
    return doc_id, tuple(min(h ^ seed for h in hashes) for seed in _seeds)


if __name__ == "__main__":
    base = "retrieval augmented generation combines search with a language model to answer questions"
    docs = [(i, base + (" extra" if i % 2 else "")) for i in range(200)] + [(999, "a totally different text here")]
    with mp.get_context("spawn").Pool(4, initializer=init, initargs=(42,)) as pool:
        sigs = pool.map(signature, docs, chunksize=25)
    buckets = defaultdict(set)
    for doc_id, sig in sigs:                                       # LSH banding in the parent
        for b in range(BANDS):
            buckets[(b, sig[b * ROWS:(b + 1) * ROWS])].add(doc_id)
    dupes = {d for ids in buckets.values() if len(ids) > 1 for d in ids}
    print(len(dupes), 999 in dupes)   # 200 False
```

The permutation seeds must be identical in every worker (seeded from one value in the initializer);
otherwise signatures from different workers are not comparable.

## 9. GPUs, CUDA and fork

| Rule | Why |
|------|-----|
| Use `spawn` (or `torch.multiprocessing.get_context("spawn")`) for any process that touches CUDA | `RuntimeError: Cannot re-initialize CUDA in forked subprocess` |
| Do not call `torch.cuda.*` in the parent before starting workers | Even `torch.cuda.is_available()` can initialise the driver in some versions; the child then inherits a broken context under fork |
| One process per GPU; set `CUDA_VISIBLE_DEVICES` per worker before importing torch | Each process creates its own CUDA context (~300-500 MB VRAM) |
| Batch inside the GPU process; feed it with CPU workers via a queue | GPU utilisation comes from batch size, not process count |
| Send CPU tensors or numpy arrays between processes, never CUDA tensors unless you use `torch.multiprocessing` with spawn and keep the producer alive | CUDA IPC handles require the producer to outlive consumers |

Per-GPU worker pattern:

```python
import multiprocessing as mp
import os


def gpu_worker(device: int, jobs, results) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(device)     # before importing torch in this process
    # import torch; model = load_model().to("cuda").eval()
    while (batch := jobs.get(timeout=60)) is not None:
        results.put((device, [len(t) for t in batch]))   # real: model(**tokenize(batch)) under no_grad
    results.put(None)


if __name__ == "__main__":
    ctx = mp.get_context("spawn")
    n_gpus = 2                                           # torch.cuda.device_count() in a subprocess, or nvidia-smi -L
    jobs, results = ctx.Queue(maxsize=8), ctx.Queue()
    procs = [ctx.Process(target=gpu_worker, args=(d, jobs, results)) for d in range(n_gpus)]
    for p in procs:
        p.start()
    batches = [[f"text {i}"] * 32 for i in range(20)]
    for b in batches:
        jobs.put(b, timeout=60)
    for _ in procs:
        jobs.put(None)
    done, outputs = 0, []
    while done < n_gpus:
        item = results.get(timeout=120)
        if item is None:
            done += 1
        else:
            outputs.append(item)
    for p in procs:
        p.join(timeout=30)
    print(len(outputs))   # 20
```

`torch.set_num_threads(1)` (or a small number) in CPU workers alongside GPU workers prevents CPU
oversubscription; set it in the initializer before heavy ops.

## 10. Mixing asyncio API calls with CPU work

Common in ingestion: download/fetch with asyncio, parse in processes, embed via API with asyncio again.
Run CPU steps through `loop.run_in_executor(process_pool, fn, arg)` with a bounded number in flight:

```python
import asyncio
import concurrent.futures as cf
import multiprocessing as mp


def parse(html: str) -> int:                              # CPU-bound, module level
    return len(html.split())


async def fetch(i: int) -> str:
    await asyncio.sleep(0.01)                             # stand-in for httpx.AsyncClient.get
    return "<p>" + "word " * (i + 1) + "</p>"


async def pipeline(n: int, pool: cf.ProcessPoolExecutor) -> int:
    loop = asyncio.get_running_loop()
    sem = asyncio.Semaphore(8)                            # bound fetches and parse jobs in flight

    async def one(i: int) -> int:
        async with sem:
            html = await fetch(i)
            return await loop.run_in_executor(pool, parse, html)

    return sum(await asyncio.gather(*(one(i) for i in range(n))))


if __name__ == "__main__":
    with cf.ProcessPoolExecutor(max_workers=2, mp_context=mp.get_context("spawn")) as pool:
        print(asyncio.run(pipeline(20, pool)))   # 230
```

Create the process pool before the event loop starts (or at least before threads exist if you rely on
fork), and shut it down after the loop finishes. Async patterns themselves are covered by the
`python-asyncio-pattern-advisor` skill.

## 11. Seeds and determinism

- fork copies the parent's RNG state into every worker: all workers draw the same "random" numbers (a
  real bug in data augmentation and sampling). spawn reseeds `random` from the OS, so runs are not
  reproducible either.
- Make randomness a function of the item, not of the worker: `random.Random(stable_seed(base, item_id))`
  gives the same output for any worker count, chunksize or scheduling order.
- Stable seed: `int.from_bytes(hashlib.blake2b(f"{base}:{item_id}".encode(), digest_size=8).digest(),
  "little")`. Do not use `hash()` of strings (salted per process unless `PYTHONHASHSEED` is set).
- numpy: `np.random.SeedSequence(base).spawn(n_tasks)` gives independent, reproducible streams;
  `np.random.default_rng(child_seq)` per task.
- torch DataLoader: `worker_init_fn` + `generator=torch.Generator().manual_seed(base)`; inside workers
  `torch.initial_seed()` differs per worker and epoch.

```python
import hashlib
import multiprocessing as mp
import random


def stable_seed(base: int, item_id: str) -> int:
    return int.from_bytes(hashlib.blake2b(f"{base}:{item_id}".encode(), digest_size=8).digest(), "little")


def augment(item_id: str) -> float:
    rng = random.Random(stable_seed(1234, item_id))
    return round(rng.random(), 6)


if __name__ == "__main__":
    ids = [f"doc{i}" for i in range(100)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(2) as a, ctx.Pool(4) as b:
        r1 = a.map(augment, ids, chunksize=7)
        r2 = b.map(augment, ids, chunksize=1)
    print(r1 == r2 == [augment(i) for i in ids])   # True
```

## 12. Alternatives: joblib, Ray, Dask, torch DataLoader, datasets.map

| Tool | Use when | Notes |
|------|----------|-------|
| `joblib.Parallel(n_jobs=k)` (loky) | Notebooks, scikit-learn style code, lambdas/closures, numpy args | cloudpickle; reusable worker pool; auto memmap of big arrays; `return_as="generator"` streams |
| `concurrent.futures` / `multiprocessing` | Library code, no deps, full control | Everything in this skill |
| Ray (`@ray.remote`, Ray Data) | Multi-node, GPUs as resources, object store for large shared objects, retries | Cluster to operate; actors keep models loaded |
| Dask (`dask.bag`, `dask.dataframe`, `distributed`) | Out-of-core dataframes/bags, multi-node, dashboard | Task-graph overhead per task ~1 ms |
| `torch.utils.data.DataLoader(num_workers=k)` | Feeding a training/inference loop | `persistent_workers=True`, `prefetch_factor`, `worker_init_fn`, `pin_memory`; uses `torch.multiprocessing` |
| HF `datasets.Dataset.map(fn, num_proc=k, batched=True)` | Transforming HF datasets | Shards Arrow data across processes; caches results; `fn` pickled with dill |
| `pebble` | Per-task timeouts that kill, decorators | Third-party |
| Free-threaded 3.13t / 3.14t | CPU-bound threads with shared memory | Needs extension support; see the `python-gil-bottleneck-analyzer` skill |

DataLoader specifics:
- `num_workers=0` runs in the main process (easiest to debug); start with `min(8, cores)` and tune.
- Each worker holds a copy of the `Dataset` object: keep it light (paths, not loaded tensors), open files
  lazily in `__getitem__` or `worker_init_fn`.
- With fork (Linux <= 3.13) a dataset holding big Python lists suffers copy-on-write growth (refcounts);
  store indices in numpy arrays.
- `multiprocessing_context="spawn"` when the main process has CUDA initialised or threads running.
