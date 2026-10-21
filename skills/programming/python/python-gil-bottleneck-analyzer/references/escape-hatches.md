# Escape Hatches: Getting CPU Work Off the GIL

Once measurement says "GIL-bound", there are many exits. They differ by an order of magnitude in payoff and in
cost. Try them roughly in this order: fix the algorithm, vectorise, compile the hot loop, then parallelise.
Parallelism multiplies whatever per-item cost remains, so make that cost small first.

## Contents

1. [Decision table](#1-decision-table)
2. [Algorithmic fixes first](#2-algorithmic-fixes-first)
3. [Vectorisation: numpy, pandas, polars](#3-vectorisation-numpy-pandas-polars)
4. [numba](#4-numba)
5. [Cython](#5-cython)
6. [mypyc](#6-mypyc)
7. [Rust with PyO3](#7-rust-with-pyo3)
8. [Processes](#8-processes)
9. [Threads over GIL-releasing code](#9-threads-over-gil-releasing-code)
10. [GPU offload](#10-gpu-offload)
11. [asyncio for the waiting parts](#11-asyncio-for-the-waiting-parts)
12. [Free-threaded build and sub-interpreters](#12-free-threaded-build-and-sub-interpreters)
13. [Combining hatches without oversubscribing](#13-combining-hatches-without-oversubscribing)

## 1. Decision table

| Hot path looks like | Best hatch | Typical gain | Cost / risk | Loses when |
|---------------------|-----------|--------------|-------------|------------|
| Nested loops, repeated lookups, re-parsing | algorithm / data structure | 10-1000x | thinking | already optimal |
| Arithmetic over arrays, columns, embeddings | numpy / polars / pandas column ops | 10-100x | rewrite into array style | logic is branchy per element |
| Numeric loop with branches, custom kernel | numba `@njit(nogil=True)` | 10-200x | numba-supported subset only; JIT warm-up | strings, dicts of objects, pandas |
| Typed loops over C types, existing C libs | Cython (`with nogil:`) | 5-100x | build step, C compiler | heavy Python-object work |
| Plain typed Python, whole modules | mypyc | ~1.5-5x (varies) | build step; keeps the GIL | hot path is in C already |
| String parsing, tokenizing, long-lived lib | Rust + PyO3 (release with `allow_threads` / `detach`) | 10-100x | Rust skills, build tooling | tiny team, short-lived script |
| Independent pure-Python items ≥ ~1 ms | processes | ≈ cores (minus IPC) | pickling, RAM per worker, start-up | items tiny or arguments huge |
| Native code already releasing the GIL | threads | ≈ cores | oversubscription with native pools | native lib already parallel |
| Big batched tensor math | GPU (torch, CuPy) | 10-100x+ | transfer cost, memory, hardware | small batches, branchy code |
| Waiting on network/disk | asyncio or threads | ≈ concurrency limit | rate limits, backpressure | work is CPU |
| Pure-Python CPU needing shared state | free-threaded 3.14t + threads | ≈ cores | extension support; single-thread penalty | any dependency re-enables the GIL |
| Pure-Python CPU, stdlib-only, avoid processes | `InterpreterPoolExecutor` (3.14) | ≈ cores | extension support; copy semantics | numpy/torch in the task |

## 2. Algorithmic fixes first

Profile hot spots with huge `ncalls` or nested-loop shapes are usually algorithmic.

```python
import time

docs = [f"doc-{i}" for i in range(20_000)]
seen_list = docs[:5_000]

t0 = time.perf_counter()
dupes_slow = [d for d in docs if d in seen_list]        # O(n*m): list membership scans
t1 = time.perf_counter()
seen = set(seen_list)
dupes_fast = [d for d in docs if d in seen]             # O(n): hash lookups
t2 = time.perf_counter()
assert dupes_slow == dupes_fast
print(f"list {t1 - t0:.3f}s  set {t2 - t1:.4f}s")
```

Common wins in AI pipelines:

| Smell | Fix |
|-------|-----|
| `x in list` inside a loop | `set` / `dict` |
| re-compiling regexes per document | compile once at module level |
| re-tokenizing the same text for counting and chunking | tokenize once, reuse ids |
| sorting all scores to take the top 10 | `heapq.nlargest(10, ...)` or `np.argpartition` |
| building strings with `+=` in a loop | `"".join(parts)` |
| `json.dumps` → `json.loads` round trips to copy | `copy.deepcopy` or build the right structure once |
| per-item model or tokenizer construction | construct once, reuse |
| exact nearest-neighbour search over millions of vectors | an ANN index (FAISS, HNSW) |

## 3. Vectorisation: numpy, pandas, polars

Move the loop into C: one call over the whole batch instead of one Python operation per element. numpy
releases the GIL inside most numeric operations, so vectorised code can additionally be threaded.

```python
import numpy as np

rng = np.random.default_rng(0)
emb = rng.standard_normal((10_000, 384)).astype(np.float32)
query = rng.standard_normal(384).astype(np.float32)

# Python loop: holds the GIL, ~1000x slower
def top_k_loop(emb, query, k=5):
    scores = []
    for row in emb.tolist():
        dot = sum(a * b for a, b in zip(row, query.tolist()))
        scores.append(dot)
    return sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:k]

# Vectorised: normalise, one matrix-vector product, partial sort
def top_k_vec(emb, query, k=5):
    emb_n = emb / np.linalg.norm(emb, axis=1, keepdims=True)
    q_n = query / np.linalg.norm(query)
    scores = emb_n @ q_n
    idx = np.argpartition(-scores, k)[:k]
    return idx[np.argsort(-scores[idx])].tolist()

print(top_k_vec(emb, query))
```

pandas: replace `df.apply(f, axis=1)` and `iterrows` with column expressions.

```python
import numpy as np
import pandas as pd

df = pd.DataFrame({"tokens": [120, 5000, 800], "latency_ms": [200, 2500, 900]})
# slow: df["bucket"] = df.apply(lambda r: "long" if r.tokens > 1000 else "short", axis=1)
df["bucket"] = np.where(df["tokens"] > 1000, "long", "short")
df["tok_per_s"] = df["tokens"] / (df["latency_ms"] / 1000)
```

polars runs expressions in Rust on its own thread pool with the GIL released:

```python
import polars as pl

df = pl.DataFrame({"text": ["a b c", "d e"], "source": ["web", "pdf"]})
out = (
    df.with_columns(pl.col("text").str.split(" ").list.len().alias("n_words"))
      .group_by("source")
      .agg(pl.col("n_words").sum())
)
```

Avoid `np.vectorize` (a Python loop in disguise), object dtypes, and `map_elements`/`apply` with Python lambdas
in polars: those all run Python per element and hold the GIL.

## 4. numba

`@njit` compiles a numeric Python subset to machine code. `nogil=True` releases the GIL while the compiled
function runs, so ordinary threads then scale; `parallel=True` with `prange` parallelises inside the function.

```python
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from numba import njit, prange


@njit(nogil=True, cache=True)
def minhash_row(tokens: np.ndarray, seeds: np.ndarray) -> np.ndarray:
    out = np.empty(seeds.shape[0], dtype=np.uint64)
    for j in range(seeds.shape[0]):
        best = np.uint64(0xFFFFFFFFFFFFFFFF)
        for t in tokens:
            h = (t * np.uint64(0x9E3779B97F4A7C15) + seeds[j]) & np.uint64(0xFFFFFFFFFFFFFFFF)
            if h < best:
                best = h
        out[j] = best
    return out


@njit(parallel=True, cache=True)
def l2_normalise(x: np.ndarray) -> np.ndarray:
    out = np.empty_like(x)
    for i in prange(x.shape[0]):                       # rows split across numba's threads
        out[i] = x[i] / np.sqrt((x[i] ** 2).sum())
    return out


docs = [np.arange(i, i + 500, dtype=np.uint64) for i in range(64)]
seeds = np.arange(128, dtype=np.uint64)
with ThreadPoolExecutor(8) as ex:                       # threads scale because of nogil=True
    sigs = list(ex.map(lambda d: minhash_row(d, seeds), docs))
```

Notes: the first call compiles (seconds); `cache=True` writes the compiled code to `__pycache__`. Supported:
numpy arrays, scalars, tuples, typed containers; not arbitrary Python objects, pandas or most strings.
`parallel=True` uses numba's own threading layer: set `NUMBA_NUM_THREADS` or `numba.set_num_threads(n)` and
avoid also running it in many processes.

## 5. Cython

Cython compiles Python-like code with C types; inside `with nogil:` blocks the GIL is released, so only C-level
operations are allowed there.

```cython
# cython: language_level=3, boundscheck=False, wraparound=False
# file: fastscore.pyx
from cython.parallel cimport prange

def dot_rows(const float[:, ::1] emb, const float[::1] q, float[::1] out):
    cdef Py_ssize_t i, j, n = emb.shape[0], d = emb.shape[1]
    cdef float acc
    with nogil:                                   # other Python threads run meanwhile
        for i in prange(n, schedule="static"):    # OpenMP: compile with -fopenmp
            acc = 0
            for j in range(d):
                acc = acc + emb[i, j] * q[j]
            out[i] = acc
```

Build with `cythonize -i fastscore.pyx` (or setuptools/meson). Use typed memoryviews over numpy arrays, keep
Python objects out of `nogil` blocks, and declare `# cython: freethreading_compatible = True` (Cython 3.1+) once
the module is safe for free-threaded builds.

## 6. mypyc

mypyc compiles type-annotated Python modules to C extensions. It speeds up attribute access, calls and
arithmetic on typed code (often 1.5-5x, sometimes more); it does **not** release the GIL, so it helps serial
speed, not thread scaling.

```bash
pip install mypy
mypyc ingest/chunking.py          # builds chunking.<abi>.so next to the source
python -c "import ingest.chunking as c; print(c.__file__)"   # confirm the compiled module is used
```

Good fit: an existing well-typed pure-Python module (tokenizer helpers, rule engines). Poor fit: code that is
mostly calls into numpy/regex already, or heavy dynamic features (monkeypatching, `getattr` tricks).

## 7. Rust with PyO3

For string-heavy hot paths (custom tokenization, normalisation, chunking, parsing) Rust gives C speed with
memory safety. Release the GIL around pure-Rust work so Python threads run in parallel. The method is
`py.allow_threads(...)` in PyO3 up to 0.25 and `py.detach(...)` in newer releases.

```rust
use pyo3::prelude::*;

#[pyfunction]
fn count_tokens(py: Python<'_>, texts: Vec<String>) -> Vec<usize> {
    // texts were copied out of Python objects above; no Python access inside the closure
    py.allow_threads(|| texts.iter().map(|t| t.split_whitespace().count()).collect())
}

#[pymodule(gil_used = false)]          // declares free-threading support (recent PyO3)
fn fasttok(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_tokens, m)?)?;
    Ok(())
}
```

Build with `maturin develop --release`. Batch the API (accept lists, return arrays) so the Python ↔ Rust
crossing cost is paid once per batch, and use `rayon` inside for parallelism instead of Python threads when
the batch is large (then do not also parallelise around it).

## 8. Processes

The universal hatch for pure-Python CPU work: each process has its own GIL. Costs: start-up and imports per
worker, pickling every argument and result, RAM per worker. Design details (start methods, chunksize,
initializers, shared memory, failures) live in the
[multiprocessing pool designer](../../python-multiprocessing-pool-designer/SKILL.md).

```python
from concurrent.futures import ProcessPoolExecutor
import re

WS = re.compile(r"\s+")


def clean_shard(lines: list[str]) -> list[str]:          # module-level: picklable
    return [WS.sub(" ", ln).strip().lower() for ln in lines]


def shards(lines, size):
    for i in range(0, len(lines), size):
        yield lines[i:i + size]


if __name__ == "__main__":                               # required for spawn/forkserver
    corpus = [f"  Line {i}\twith   EXTRA   spaces " for i in range(200_000)]
    with ProcessPoolExecutor(max_workers=4) as ex:
        cleaned = [ln for part in ex.map(clean_shard, shards(corpus, 10_000)) for ln in part]
    print(len(cleaned), cleaned[0])
```

Rules of thumb: ship shards (thousands of items per task), not single items; send paths/ids instead of big
objects; load models once per worker with `initializer=`; cap native threads per worker
([troubleshooting-oversubscription-and-contention.md](troubleshooting-oversubscription-and-contention.md)).

## 9. Threads over GIL-releasing code

When the hot call releases the GIL (hashing, compression, numpy on large arrays, image decode, onnxruntime,
torch inference), threads are cheaper than processes: no pickling, shared model weights, one copy in memory.

```python
import hashlib
import zlib
from concurrent.futures import ThreadPoolExecutor

blobs = [bytes([i % 251]) * 2_000_000 for i in range(16)]   # 2 MB "documents"


def fingerprint_and_pack(blob: bytes) -> tuple[str, int]:
    digest = hashlib.sha256(blob).hexdigest()       # GIL released for big buffers
    packed = zlib.compress(blob, 6)                 # GIL released
    return digest, len(packed)


with ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(fingerprint_and_pack, blobs))
print(len(results), results[0][1])
```

Make sure the native library is not *also* spawning a full-size pool per call (BLAS, torch intra-op threads):
pick one level of parallelism.

## 10. GPU offload

When the work is batched tensor math (embedding, reranking with a cross-encoder, similarity over millions of
vectors), the GPU beats any CPU parallelism. The Python side must keep it fed: batch on the CPU, move once,
compute, move back once.

```python
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
emb = torch.randn(100_000, 768, device=device, dtype=torch.float16 if device == "cuda" else torch.float32)
queries = torch.randn(64, 768, device=device, dtype=emb.dtype)
with torch.inference_mode():
    emb = torch.nn.functional.normalize(emb, dim=1)
    q = torch.nn.functional.normalize(queries, dim=1)
    top = (q @ emb.T).topk(10, dim=1)              # one kernel for 64 x 100k similarities
print(top.indices.shape)
```

Python-side overhead (building tensors from lists, per-item `.item()` calls, tokenization on the main thread)
often becomes the new bottleneck: profile the CPU side again after moving to GPU.

## 11. asyncio for the waiting parts

If the profile is mostly `io-wait`, no CPU hatch helps; overlap the waiting. asyncio handles thousands of
concurrent requests on one thread; structure, rate limits and timeouts are covered in the
[asyncio pattern advisor](../../python-asyncio-pattern-advisor/SKILL.md).

```python
import asyncio


async def call_llm(prompt: str) -> str:
    await asyncio.sleep(0.1)                         # stands in for an HTTP call
    return prompt.upper()


async def main(prompts: list[str]) -> list[str]:
    sem = asyncio.Semaphore(16)                      # concurrency limit

    async def one(p: str) -> str:
        async with sem:
            return await call_llm(p)

    return await asyncio.gather(*(one(p) for p in prompts))


print(len(asyncio.run(main([f"q{i}" for i in range(100)]))))   # ~0.7 s, not 10 s
```

Mixed pipelines: asyncio for the network stages, a process pool (via `loop.run_in_executor`) for CPU stages.

## 12. Free-threaded build and sub-interpreters

For pure-Python CPU work with shared state, the free-threaded 3.14t build lets plain threads run in parallel,
and `InterpreterPoolExecutor` gives one GIL per worker in one process. Both have compatibility limits; see
[free-threading-and-subinterpreters.md](free-threading-and-subinterpreters.md).

## 13. Combining hatches without oversubscribing

| Combination | OK? | Rule |
|-------------|-----|------|
| processes × numpy BLAS threads | careful | `OMP_NUM_THREADS=1` per worker, or few workers × few threads |
| threads × numba `parallel=True` | careful | either outer threads or inner prange, not both at full size |
| processes × HF tokenizers | careful | `TOKENIZERS_PARALLELISM=false` in workers |
| asyncio + process pool | good | one pool created at startup, `run_in_executor` |
| threads over numba `nogil=True` (no parallel) | good | threads = cores |
| vectorised numpy + GPU | good | keep the transfer batched |

Total runnable threads should not exceed usable cores; details and env vars in
[troubleshooting-oversubscription-and-contention.md](troubleshooting-oversubscription-and-contention.md).
